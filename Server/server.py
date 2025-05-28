import sqlite3
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import configparser
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import time
from contextlib import closing
from flask_httpauth import HTTPTokenAuth


# Initialisierung der Flask-Anwendung
app = Flask(__name__)
DATABASE = 'ip_management.db'

# Konfiguration laden (einmalig beim Start)
def load_config():
    config = configparser.ConfigParser()
    config.read_dict({
        'DEFAULT': {
            'bantime': '3m',
            'bantime.increment': 'true',
            'bantime.factor': '24',
            'bantime.maxtime': '5w',
            'known_duration': '48h',
            'allowed_duration': '2m'
        }
    })

    if os.path.exists('serverconfig.ini'):
        config.read('serverconfig.ini')
        
    tokens = {}
    if 'api_tokens' in config:
        for client, token in config['api_tokens'].items():
            tokens[token] = client

    return {
        'bantime': config.get('DEFAULT', 'bantime', fallback='10m'),
        'bantime_increment': config.getboolean('DEFAULT', 'bantime.increment', fallback=True),
        'bantime_factor': config.getint('DEFAULT', 'bantime.factor', fallback=24),
        'bantime_maxtime': config.get('DEFAULT', 'bantime.maxtime', fallback='5w'),
        'known_duration': config.get('DEFAULT', 'known_duration', fallback='48h'),
        'allowed_duration': config.get('DEFAULT', 'allowed_duration', fallback='2m'),
        'api_tokens': tokens
    }

# Zeitkonvertierung
def parse_time(time_str):
    time_str = time_str.strip().lower()
    if time_str.endswith('m'):
        return timedelta(minutes=int(time_str[:-1]))
    elif time_str.endswith('h'):
        return timedelta(hours=int(time_str[:-1]))
    elif time_str.endswith('d'):
        return timedelta(days=int(time_str[:-1]))
    elif time_str.endswith('w'):
        return timedelta(weeks=int(time_str[:-1]))
    else:
        return timedelta(minutes=3)  # Standardwert 3 Minuten

# Konfiguration und Logger initialisieren
config = load_config()
BLOCK_DURATION = parse_time(config['bantime'])
INCREMENT_BLOCK = config['bantime_increment']
BLOCK_FACTOR = config['bantime_factor']
MAX_BLOCK_DURATION = parse_time(config['bantime_maxtime'])
KNOWN_DURATION = parse_time(config['known_duration'])
ALLOWED_DURATION = parse_time(config['allowed_duration'])

# Logging einrichten
def setup_logging():
    logger = logging.getLogger('ip_server')
    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        'server.log',
        maxBytes=1024*1024,
        backupCount=5
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger

logger = setup_logging()

def init_db():
    with closing(sqlite3.connect(DATABASE)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ip_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL UNIQUE,
                description TEXT,
                status TEXT CHECK( status IN ('blocked', 'allowed', 'known') ),
                reported_by TEXT,
                blocked_until TIMESTAMP,
                allowed_since TIMESTAMP,
                block_count INTEGER DEFAULT 1
            )
        ''')
        conn.commit()

def get_db_connection():
    return sqlite3.connect(DATABASE, timeout=10)

def update_ip_status():
    max_retries = 5
    retry_delay = 1  # Sekunden

    for attempt in range(max_retries):
        try:
            with closing(get_db_connection()) as conn:
                cursor = conn.cursor()

                # IPs, deren Blockzeit abgelaufen ist, auf 'allowed' setzen
                cursor.execute('''
                    UPDATE ip_addresses
                    SET status = 'allowed', allowed_since = ?
                    WHERE status = 'blocked' AND blocked_until < ?
                ''', (datetime.now(), datetime.now()))

                # IPs, deren Allowed-Zeit abgelaufen ist, auf 'known' setzen
                cursor.execute('''
                    UPDATE ip_addresses
                    SET status = 'known', allowed_since = NULL
                    WHERE status = 'allowed' AND allowed_since < ?
                ''', (datetime.now() - ALLOWED_DURATION,))

                # IPs, deren Known-Zeit abgelaufen ist, löschen
                cursor.execute('''
                    DELETE FROM ip_addresses
                    WHERE status = 'known'
                    AND (JULIANDAY('now') - JULIANDAY(blocked_until)) > ?
                ''', (KNOWN_DURATION.days,))

                conn.commit()
            break

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Datenbank gesperrt, warte {retry_delay} Sekunden (Versuch {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponentielles Backoff
            else:
                logger.error(f"Fehler beim Aktualisieren der IP-Status: {e}")
                raise
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der IP-Status: {e}")
            raise

def calculate_block_duration(block_count):
    if not INCREMENT_BLOCK:
        return BLOCK_DURATION

    # Exponentielle Blockzeit basierend auf der Anzahl der Vorfälle
    duration = BLOCK_DURATION * (BLOCK_FACTOR ** max(0, block_count - 1))

    # Obergrenze beachten
    if duration > MAX_BLOCK_DURATION:
        return MAX_BLOCK_DURATION
    return duration


# Token-Authentifizierung
auth = HTTPTokenAuth(scheme='Bearer')
config = load_config()
TOKENS = config['api_tokens'] 

@auth.verify_token
def verify_token(token):
    return TOKENS.get(token)

@app.route('/add_ips', methods=['POST'])
@auth.login_required
def add_ips():
    update_ip_status()

    data = request.json
    ips = data.get('ips', [])
    description = data.get('description', '')
    status = data.get('status', 'blocked')
    reported_by = data.get('reported_by', '')

    if not ips:
        return jsonify({"error": "Liste der IP-Adressen ist erforderlich"}), 400

    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        added_ips = []

        try:
            for ip in ips:
                # Status und Block-Count in einer Abfrage holen
                cursor.execute('''
                    SELECT status, block_count FROM ip_addresses WHERE ip_address = ?
                ''', (ip,))
                result = cursor.fetchone()
                current_status = result[0] if result else None
                block_count = result[1] if result else 0

                if current_status == 'allowed':
                    logger.info(f"IP {ip} ist gerade allowed - wird ignoriert")
                    continue

                if current_status == 'known':
                    block_count += 1
                    block_duration = calculate_block_duration(block_count)

                    cursor.execute('''
                        UPDATE ip_addresses
                        SET status = 'blocked',
                            blocked_until = ?,
                            reported_by = ?,
                            block_count = ?,
                            allowed_since = NULL
                        WHERE ip_address = ?
                    ''', (datetime.now() + block_duration, reported_by, block_count, ip))

                    added_ips.append(ip)
                    logger.info(f"IP {ip} geblockt (Block-Count: {block_count}, Blockzeit: {block_duration})")

                elif current_status != 'blocked':
                    block_duration = calculate_block_duration(block_count)

                    if not current_status:
                        cursor.execute('''
                            INSERT INTO ip_addresses
                            (ip_address, description, status, reported_by, blocked_until, block_count)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (ip, description, 'blocked', reported_by, datetime.now() + block_duration, 1))
                    else:
                        cursor.execute('''
                            UPDATE ip_addresses
                            SET status = 'blocked',
                                blocked_until = ?,
                                reported_by = ?,
                                block_count = ?
                            WHERE ip_address = ?
                        ''', (datetime.now() + block_duration, reported_by, block_count, ip))

                    added_ips.append(ip)
                    logger.info(f"IP {ip} geblockt (Blockzeit: {block_duration})")

            conn.commit()
            return jsonify({"message": "IP-Adressen hinzugefügt", "added_ips": added_ips}), 201
        except sqlite3.IntegrityError as e:
            logger.error(f"Fehler beim Hinzufügen der IP-Adressen: {e}")
            return jsonify({"error": "Fehler beim Hinzufügen der IP-Adressen"}), 400

@app.route('/get_ips', methods=['GET'])
@auth.login_required
def get_ips():
    update_ip_status()

    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ip_addresses WHERE status = ?', ('blocked',))
        rows = cursor.fetchall()

        ip_addresses = []
        for row in rows:
            ip_addresses.append({
                "id": row[0],
                "ip_address": row[1],
                "description": row[2],
                "status": row[3],
                "reported_by": row[4],
                "blocked_until": row[5],
                "allowed_since": row[6],
                "block_count": row[7]
            })

        logger.info(f"Anzahl der geblockten IPs: {len(ip_addresses)}")
        return jsonify(ip_addresses), 200

@app.route('/get_allowed_ips', methods=['GET'])
@auth.login_required
def get_allowed_ips():
    update_ip_status()

    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ip_addresses WHERE status = ?', ('allowed',))
        rows = cursor.fetchall()

        ip_addresses = []
        for row in rows:
            ip_addresses.append({
                "id": row[0],
                "ip_address": row[1],
                "description": row[2],
                "status": row[3],
                "reported_by": row[4],
                "blocked_until": row[5],
                "allowed_since": row[6],
                "block_count": row[7]
            })

        logger.info(f"Anzahl der erlaubten IPs: {len(ip_addresses)}")
        return jsonify(ip_addresses), 200

@app.route('/get_known_ips', methods=['GET'])
@auth.login_required
def get_known_ips():
    update_ip_status()

    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ip_addresses WHERE status = ?', ('known',))
        rows = cursor.fetchall()

        ip_addresses = []
        for row in rows:
            ip_addresses.append({
                "id": row[0],
                "ip_address": row[1],
                "description": row[2],
                "status": row[3],
                "reported_by": row[4],
                "blocked_until": row[5],
                "allowed_since": row[6],
                "block_count": row[7]
            })

        logger.info(f"Anzahl der bekannten IPs: {len(ip_addresses)}")
        return jsonify(ip_addresses), 200


if __name__ == '__main__':
    init_db()
    logger.info("Server gestartet")
    app.run(host='0.0.0.0', port=5000, debug=False)
