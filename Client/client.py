import subprocess
import requests
import json
import ast
import re
import logging
from logging.handlers import RotatingFileHandler
import os
import configparser
from datetime import datetime

# Standard-Konfiguration
DEFAULT_CLIENT_CONFIG = {
    'server': {
        'host': '192.168.1.1',
        'port': '5000',
        'protocol': 'http'
    },
    'logging': {
        'log_file': 'client.log',
        'max_bytes': '1048576',
        'backup_count': '3'
    },
    'fail2ban': {
        'jail': 'sshd'
    }
}

def load_config():
    """Lädt die Konfiguration aus der Datei oder verwendet Standardwerte"""
    config = configparser.ConfigParser()
    config.read_dict({'DEFAULT': DEFAULT_CLIENT_CONFIG})

    # Konfigurationsdatei lesen, falls vorhanden
    if os.path.exists('clientconfig.txt'):
        config.read('clientconfig.txt')

    return {
        'server': {
            'host': config.get('server', 'host', fallback='192.168.1.1'),
            'port': config.get('server', 'port', fallback='5000'),
            'protocol': config.get('server', 'protocol', fallback='http')
        },
        'logging': {
            'log_file': config.get('logging', 'log_file', fallback='client.log'),
            'max_bytes': config.get('logging', 'max_bytes', fallback='1048576'),
            'backup_count': config.get('logging', 'backup_count', fallback='3')
        },
        'fail2ban': {
            'jail': config.get('fail2ban', 'jail', fallback='sshd')
        }
    }

def setup_logging(log_file, max_bytes, backup_count):
    """Richtet das Logging-System ein"""
    logger = logging.getLogger('ip_client')
    logger.setLevel(logging.INFO)

    # Datei-Handler mit Rotation
    handler = RotatingFileHandler(
        log_file,
        maxBytes=int(max_bytes),
        backupCount=int(backup_count)
    )
    handler.setLevel(logging.INFO)

    # Formatierung
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger

def get_banned_ips(jail):
    """Ruft die gebannten IPs von Fail2Ban für das angegebene Jail ab."""
    try:
        result = subprocess.run(
            ['fail2ban-client', 'get', jail, 'banned'],
            capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        if output == 'None':
            return []
        if output.startswith("[") and output.endswith("]"):
            iplist = ast.literal_eval(output)
            return iplist
        # Falls jemals ein normales Whitespace-getrenntes Stringformat kommt:
        return output.split()
    except Exception as e:
        print(f"Fehler beim Abrufen gebannter IPs: {e}")
        return []

def get_local_mac_address():
    """Ermittelt die lokale MAC-Adresse"""
    try:
        result = subprocess.run(['ip', 'addr'], capture_output=True, text=True, check=True)
        mac_address_match = re.search(r'link/ether\s+([0-9A-Fa-f:]{17})', result.stdout)
        if mac_address_match:
            return mac_address_match.group(1)
        return None
    except Exception as e:
        print(f"Fehler beim Abrufen der MAC-Adresse: {e}")
        return None

def send_banned_ips(banned_ips, server_url, mac_address, logger):
    """Sendet gebannte IPs an den Server"""
    headers = {'Content-Type': 'application/json'}
    data = {
        'ips': banned_ips,
        'description': 'Gebannte IPs von fail2ban',
        'status': 'blocked',
        'reported_by': mac_address
    }
    try:
        response = requests.post(f"{server_url}/add_ips", headers=headers, data=json.dumps(data))
        if response.status_code == 201:
            logger.info("IPs erfolgreich gesendet.")
        else:
            logger.error(f"Fehler beim Senden der IPs: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"Fehler beim Senden der Anfrage: {e}")

def get_unknown_ips(server_url, mac_address, logger):
    """Ruft unbekannte IPs vom Server ab"""
    try:
        response = requests.get(f"{server_url}/get_ips?mac_address={mac_address}")
        if response.status_code == 200:
            return response.json()
        logger.error(f"Fehler beim Abrufen der IPs: {response.status_code} - {response.text}")
        return []
    except requests.RequestException as e:
        logger.error(f"Fehler beim Senden der Anfrage: {e}")
        return []

def get_allowed_ips(server_url, logger):
    """Ruft erlaubte IPs vom Server ab"""
    try:
        response = requests.get(f"{server_url}/get_allowed_ips")
        if response.status_code == 200:
            return response.json()
        logger.error(f"Fehler beim Abrufen der allowed IPs: {response.status_code} - {response.text}")
        return []
    except requests.RequestException as e:
        logger.error(f"Fehler beim Senden der Anfrage: {e}")
        return []

def add_ips_to_fail2ban(ips, jail, logger):
    """Fügt IPs zu Fail2Ban hinzu"""
    try:
        for ip in ips:
            subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], check=True)
        logger.info(f"IPs erfolgreich zu Fail2Ban hinzugefügt: {ips}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Fehler beim Hinzufügen der IPs zu Fail2Ban: {e}")

def allow_ips_in_fail2ban(ips, jail, logger):
    """Erlaubt IPs in Fail2Ban"""
    try:
        for ip in ips:
            subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], check=True)
        logger.info(f"IPs erfolgreich in Fail2Ban erlaubt: {ips}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Fehler beim Erlauben der IPs in Fail2Ban: {e}")

def main():
    """Hauptfunktion des Clients"""
    try:
        # Konfiguration laden
        config = load_config()

        # Server-URL erstellen
        server_url = f"{config['server']['protocol']}://{config['server']['host']}:{config['server']['port']}"
        jail = config['fail2ban']['jail']

        # Logging einrichten
        logger = setup_logging(
            config['logging']['log_file'],
            int(config['logging']['max_bytes']),
            int(config['logging']['backup_count'])
        )

        logger.info("Client gestartet")

        mac_address = get_local_mac_address()
        if not mac_address:
            logger.error("MAC-Adresse konnte nicht ermittelt werden.")
            return

        # Senden der gebannten IPs an den Server
        banned_ips = get_banned_ips(jail)
        if banned_ips:
            send_banned_ips(banned_ips, server_url, mac_address, logger)
        else:
            logger.info("Keine gebannten IPs gefunden.")

        # Abrufen und Blockieren der unbekannten IPs
        unknown_ips = get_unknown_ips(server_url, mac_address, logger)
        if unknown_ips:
            ip_addresses = [ip['ip_address'] for ip in unknown_ips]
            add_ips_to_fail2ban(ip_addresses, jail, logger)
        else:
            logger.info("Keine unbekannten IPs gefunden.")

        # Abrufen und Erlauben der allowed IPs
        allowed_ips = get_allowed_ips(server_url, logger)
        if allowed_ips:
            ip_addresses = [ip['ip_address'] for ip in allowed_ips]
            allow_ips_in_fail2ban(ip_addresses, jail, logger)
        else:
            logger.info("Keine allowed IPs gefunden.")

    except Exception as e:
        print(f"Fehler in der Hauptfunktion: {e}")
        raise

if __name__ == '__main__':
    main()