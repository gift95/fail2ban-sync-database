import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from datetime import datetime, timedelta
import configparser
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import time
from contextlib import closing
from flask_httpauth import HTTPTokenAuth, HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

# 获取真实IP地址（考虑代理情况）
def get_client_ip():
    # 优先获取X-Forwarded-For头部（多个代理情况下，第一个IP是客户端真实IP）
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        # X-Forwarded-For可能包含多个IP，格式为：客户端IP, 代理1IP, 代理2IP...
        # 取第一个IP作为客户端真实IP
        return x_forwarded_for.split(',')[0].strip()
    
    # 其次获取X-Real-IP头部
    x_real_ip = request.headers.get('X-Real-IP')
    if x_real_ip:
        return x_real_ip.strip()
    
    # 如果都没有，则使用默认的remote_addr
    return request.remote_addr


# 初始化Flask应用
app = Flask(__name__)
DATABASE = 'ip_management.db'

# 加载配置（启动时一次性加载）
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
        config.read('serverconfig.ini', encoding='utf-8')
        
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

# 时间转换
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
        return timedelta(minutes=3)  # 默认值3分钟

# 初始化配置和日志器
config = load_config()
BLOCK_DURATION = parse_time(config['bantime'])
INCREMENT_BLOCK = config['bantime_increment']
BLOCK_FACTOR = config['bantime_factor']
MAX_BLOCK_DURATION = parse_time(config['bantime_maxtime'])
KNOWN_DURATION = parse_time(config['known_duration'])
ALLOWED_DURATION = parse_time(config['allowed_duration'])

# 设置日志
def setup_logging():
    logger = logging.getLogger('ip_server')
    logger.setLevel(logging.INFO)
    
    # 清除已有的handler，避免重复添加
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 文件日志handler
    file_handler = RotatingFileHandler(
        'server.log',
        maxBytes=1024*1024,
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # 控制台日志handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 优化日志格式，使用简洁的时间戳和级别
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
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

# 创建数据库连接池
class DatabaseConnectionPool:
    def __init__(self, database_path, max_connections=5, timeout=10):
        self.database_path = database_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.connections = []
    
    def get_connection(self):
        # 为每个请求创建新连接，设置check_same_thread=False以支持多线程环境
        return sqlite3.connect(self.database_path, timeout=self.timeout, check_same_thread=False)
    
    def return_connection(self, conn):
        # 在Flask多线程环境中，我们简单关闭连接而不是重用
        try:
            conn.close()
        except:
            pass
    
    def close_all(self):
        # 清理连接池
        self.connections = []

# 初始化数据库连接池
db_pool = DatabaseConnectionPool(DATABASE, max_connections=5)

def get_db_connection():
    return db_pool.get_connection()

def update_ip_status():
    max_retries = 5
    retry_delay = 1  # 秒

    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 开始事务
            conn.execute('BEGIN TRANSACTION')

            # 将封禁时间已过的IP设置为'allowed'
            cursor.execute('''
                UPDATE ip_addresses
                SET status = 'allowed', allowed_since = ?
                WHERE status = 'blocked' AND blocked_until < ?
            ''', (datetime.now(), datetime.now()))

            # 将允许时间已过的IP设置为'known'
            cursor.execute('''
                UPDATE ip_addresses
                SET status = 'known', allowed_since = NULL
                WHERE status = 'allowed' AND allowed_since < ?
            ''', (datetime.now() - ALLOWED_DURATION,))

            # 删除已知时间已过的IP
            cursor.execute('''
                DELETE FROM ip_addresses
                WHERE status = 'known'
                AND (JULIANDAY('now') - JULIANDAY(blocked_until)) > ?
            ''', (KNOWN_DURATION.days,))

            # 提交事务
            conn.commit()
            logger.debug(f"IP状态更新成功，影响的行: 封禁过期 -> allowed: {cursor.rowcount}")
            break

        except sqlite3.OperationalError as e:
            if conn:
                conn.rollback()
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logger.warning(f"数据库已锁定，等待 {retry_delay} 秒（尝试 {attempt + 1}/{max_retries}）")
                time.sleep(retry_delay)
                retry_delay *= 2  # 指数退避
            else:
                logger.error(f"更新IP状态时出错: {e}")
                raise
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"更新IP状态时出错: {e}")
            raise
        finally:
            if conn:
                db_pool.return_connection(conn)

def calculate_block_duration(block_count):
    if not INCREMENT_BLOCK:
        return BLOCK_DURATION

    # 基于事件数量的指数封禁时间
    duration = BLOCK_DURATION * (BLOCK_FACTOR ** max(0, block_count - 1))

    # 考虑上限
    if duration > MAX_BLOCK_DURATION:
        return MAX_BLOCK_DURATION
    return duration


# Token-Authentifizierung
auth = HTTPTokenAuth(scheme='Bearer')
# 使用已经加载的配置，避免重复加载
TOKENS = config['api_tokens'] 
# 添加测试令牌（用于开发测试）
TOKENS['test_token_123'] = 'test_client'

# 用户名密码认证（用于Web界面）
web_auth = HTTPBasicAuth()
# 初始化用户数据库（实际项目中应该从配置文件或数据库加载）
users = {
    "admin": generate_password_hash("admin123")  # 默认用户名: admin, 密码: admin123
}

@web_auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users[username], password):
        session['username'] = username
        return username
    return None

@web_auth.error_handler
def unauthorized():  
    return render_template('login.html', error='用户名或密码错误'), 401

@auth.verify_token
def verify_token(token):
    # 返回token对应的客户端名称
    if token in TOKENS:
        return TOKENS[token]
    return None

@app.route('/add_ips', methods=['POST'])
@auth.login_required
def add_ips():
    update_ip_status()
    
    # 获取真实客户端IP和认证后的客户端名称
    client_ip = get_client_ip()
    client_name = auth.current_user()
    
    data = request.json
    ips = data.get('ips', [])
    description = data.get('description', '')
    status = data.get('status', 'blocked')
    reported_by = data.get('reported_by', client_ip)

    if not ips:
        logger.warning(f"客户端 {client_name} ({client_ip}) 请求添加IP但未提供IP列表")
        return jsonify({"error": "需要IP地址列表"}), 400

    conn = None
    added_ips = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.execute('BEGIN TRANSACTION')

        # 批量处理IP，减少数据库操作次数
        for ip in ips:
            # 一次性查询状态和封禁计数
            cursor.execute('''
                SELECT status, block_count FROM ip_addresses WHERE ip_address = ?
            ''', (ip,))
            result = cursor.fetchone()
            current_status = result[0] if result else None
            block_count = result[1] if result else 0

            if current_status == 'allowed':
                logger.info(f"客户端 {client_name} ({client_ip}) 请求封禁IP {ip}，但当前为allowed状态 - 被忽略")
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
                logger.info(f"客户端 {client_name} ({client_ip}) 已封禁IP {ip} (封禁计数: {block_count}, 封禁时间: {block_duration}, 报告来源: {reported_by})")

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
                logger.info(f"客户端 {client_name} ({client_ip}) 已封禁IP {ip} (封禁时间: {block_duration}, 报告来源: {reported_by})")

        conn.commit()
        logger.info(f"客户端 {client_name} ({client_ip}) 成功添加 {len(added_ips)} 个IP地址到封禁列表")
        return jsonify({"message": "IP地址已添加", "added_ips": added_ips}), 201
    except sqlite3.IntegrityError as e:
        if conn:
            conn.rollback()
        logger.error(f"客户端 {client_name} ({client_ip}) 添加IP地址时发生完整性错误: {e}")
        return jsonify({"error": "添加IP地址时出错"}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"客户端 {client_name} ({client_ip}) 添加IP地址时出错: {e}")
        return jsonify({"error": "服务器内部错误"}), 500
    finally:
        if conn:
            db_pool.return_connection(conn)

# 通用的获取IP列表函数
@auth.login_required
def get_ip_list(status):
    update_ip_status()
    client_ip = get_client_ip()
    client_name = auth.current_user()
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ip_addresses WHERE status = ?', (status,))
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

        status_names = {
            'blocked': '被封禁',
            'allowed': '允许的',
            'known': '已知的'
        }
        logger.info(f"客户端 {client_name} ({client_ip}) 请求获取{status_names.get(status, status)}IP列表，共 {len(ip_addresses)} 个")
        return jsonify(ip_addresses), 200
    except Exception as e:
        logger.error(f"客户端 {client_name} ({client_ip}) 获取{status} IP列表时出错: {e}")
        return jsonify({"error": "服务器内部错误"}), 500
    finally:
        if conn:
            db_pool.return_connection(conn)

@app.route('/allow_ip', methods=['POST'])
@auth.login_required
def allow_ip():
    update_ip_status()
    
    # 获取真实客户端IP和认证后的客户端名称
    client_ip = get_client_ip()
    client_name = auth.current_user()
    
    data = request.json
    ip = data.get('ip')
    
    if not ip:
        logger.warning(f"客户端 {client_name} ({client_ip}) 请求放行IP但未提供IP地址")
        return jsonify({"error": "需要IP地址"}), 400

    conn = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.execute('BEGIN TRANSACTION')

        # 检查IP是否存在且被封禁
        cursor.execute('''
            SELECT status FROM ip_addresses WHERE ip_address = ?
        ''', (ip,))
        result = cursor.fetchone()
        
        if not result:
            logger.info(f"客户端 {client_name} ({client_ip}) 请求放行IP {ip}，但该IP不存在")
            return jsonify({"error": "IP地址不存在"}), 404
        
        current_status = result[0]
        
        if current_status != 'blocked':
            logger.info(f"客户端 {client_name} ({client_ip}) 请求放行IP {ip}，但该IP当前状态为 {current_status}")
            return jsonify({"error": f"IP地址当前状态为 {current_status}，不需要放行"}), 400
        
        # 将IP设置为allowed状态
        cursor.execute('''
            UPDATE ip_addresses
            SET status = 'allowed', allowed_since = ?
            WHERE ip_address = ? AND status = 'blocked'
        ''', (datetime.now(), ip))
        
        conn.commit()
        logger.info(f"客户端 {client_name} ({client_ip}) 已手动放行IP {ip}")
        return jsonify({"message": f"IP地址 {ip} 已成功放行"}), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"客户端 {client_name} ({client_ip}) 放行IP {ip} 时出错: {e}")
        return jsonify({"error": "服务器内部错误"}), 500
    finally:
        if conn:
            db_pool.return_connection(conn)

# API端点路由
@app.route('/get_ips', methods=['GET'])
def get_ips():
    return get_ip_list('blocked')

@app.route('/get_allowed_ips', methods=['GET'])
def get_allowed_ips():
    return get_ip_list('allowed')

@app.route('/get_known_ips', methods=['GET'])
def get_known_ips():
    return get_ip_list('known')

# Web界面路由
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username], password):
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            error = '用户名或密码错误'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    update_ip_status()
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 获取搜索和分页参数
        search_ip = request.args.get('search_ip', '').strip()
        
        # 封禁IP的分页
        blocked_page = int(request.args.get('blocked_page', 1))
        blocked_per_page = 50
        blocked_offset = (blocked_page - 1) * blocked_per_page
        
        # 已放行IP的分页
        allowed_page = int(request.args.get('allowed_page', 1))
        allowed_per_page = 50
        allowed_offset = (allowed_page - 1) * allowed_per_page
        
        # 查询被封禁的IP，支持搜索过滤和分页
        if search_ip:
            cursor.execute('SELECT COUNT(*) FROM ip_addresses WHERE status = ? AND ip_address LIKE ?', ('blocked', f'%{search_ip}%'))
            blocked_total = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM ip_addresses WHERE status = ? AND ip_address LIKE ? LIMIT ? OFFSET ?', 
                          ('blocked', f'%{search_ip}%', blocked_per_page, blocked_offset))
        else:
            cursor.execute('SELECT COUNT(*) FROM ip_addresses WHERE status = ?', ('blocked',))
            blocked_total = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM ip_addresses WHERE status = ? LIMIT ? OFFSET ?', 
                          ('blocked', blocked_per_page, blocked_offset))
        blocked_ips = cursor.fetchall()
        blocked_total_pages = (blocked_total + blocked_per_page - 1) // blocked_per_page
        
        # 查询已放行的IP，支持搜索过滤和分页
        if search_ip:
            cursor.execute('SELECT COUNT(*) FROM ip_addresses WHERE status = ? AND ip_address LIKE ?', ('allowed', f'%{search_ip}%'))
            allowed_total = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM ip_addresses WHERE status = ? AND ip_address LIKE ? LIMIT ? OFFSET ?', 
                          ('allowed', f'%{search_ip}%', allowed_per_page, allowed_offset))
        else:
            cursor.execute('SELECT COUNT(*) FROM ip_addresses WHERE status = ?', ('allowed',))
            allowed_total = cursor.fetchone()[0]
            cursor.execute('SELECT * FROM ip_addresses WHERE status = ? LIMIT ? OFFSET ?', 
                          ('allowed', allowed_per_page, allowed_offset))
        allowed_ips = cursor.fetchall()
        allowed_total_pages = (allowed_total + allowed_per_page - 1) // allowed_per_page
        
        return render_template('dashboard.html', 
                             blocked_ips=blocked_ips, 
                             allowed_ips=allowed_ips,
                             username=session['username'],
                             search_ip=search_ip,
                             # 封禁IP的分页信息
                             blocked_page=blocked_page,
                             blocked_per_page=blocked_per_page,
                             blocked_total=blocked_total,
                             blocked_total_pages=blocked_total_pages,
                             # 已放行IP的分页信息
                             allowed_page=allowed_page,
                             allowed_per_page=allowed_per_page,
                             allowed_total=allowed_total,
                             allowed_total_pages=allowed_total_pages)
    except Exception as e:
        logger.error(f"获取IP列表时出错: {e}")
        flash('获取IP列表时出错', 'error')
        return render_template('dashboard.html', blocked_ips=[], allowed_ips=[], username=session['username'])
    finally:
        if conn:
            db_pool.return_connection(conn)

@app.route('/web_allow_ip/<ip>', methods=['POST'])
def web_allow_ip(ip):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    update_ip_status()
    conn = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        conn.execute('BEGIN TRANSACTION')

        # 检查IP是否存在且被封禁
        cursor.execute('''
            SELECT status FROM ip_addresses WHERE ip_address = ?
        ''', (ip,))
        result = cursor.fetchone()
        
        if not result:
            flash(f'IP地址 {ip} 不存在', 'error')
            return redirect(url_for('dashboard'))
        
        current_status = result[0]
        
        if current_status != 'blocked':
            flash(f'IP地址 {ip} 当前状态为 {current_status}，不需要放行', 'warning')
            return redirect(url_for('dashboard'))
        
        # 将IP设置为allowed状态
        cursor.execute('''
            UPDATE ip_addresses
            SET status = 'allowed', allowed_since = ?
            WHERE ip_address = ? AND status = 'blocked'
        ''', (datetime.now(), ip))
        
        conn.commit()
        logger.info(f"用户 {session['username']} 已手动放行IP {ip}")
        flash(f'IP地址 {ip} 已成功放行', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"用户 {session['username']} 放行IP {ip} 时出错: {e}")
        flash('放行IP时发生错误', 'error')
        return redirect(url_for('dashboard'))
    finally:
        if conn:
            db_pool.return_connection(conn)

# 确保templates文件夹存在
if not os.path.exists('templates'):
    os.makedirs('templates')

# 设置密钥用于session加密
app.secret_key = os.urandom(24)
# 设置session过期时间
app.permanent_session_lifetime = timedelta(minutes=30)

# 创建必要的HTML模板
with open('templates/login.html', 'w', encoding='utf-8') as f:
    f.write('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录 - Fail2BanSync管理界面</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .login-container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            width: 300px;
        }
        h2 {
            text-align: center;
            color: #333;
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #666;
        }
        input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 10px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #45a049;
        }
        .error {
            color: red;
            text-align: center;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>Fail2BanSync管理界面</h2>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <div class="form-group">
                <label for="username">用户名</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">密码</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">登录</button>
        </form>
    </div>
</body>
</html>
''')

with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fail2BanSync管理界面</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 0;
        }
        .header {
            background-color: #333;
            color: white;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
        }
        .logout {
            color: white;
            text-decoration: none;
            padding: 8px 15px;
            background-color: #555;
            border-radius: 4px;
        }
        .logout:hover {
            background-color: #777;
        }
        .container {
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 20px;
        }
        .message {
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .warning {
            background-color: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }
        .section {
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }
        h2 {
            color: #333;
            margin-top: 0;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .action-btn {
            padding: 5px 10px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            font-size: 14px;
        }
        .action-btn:hover {
            background-color: #45a049;
        }
        .status {
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        .status.blocked {
            background-color: #ffdddd;
            color: #d8000c;
        }
        .status.allowed {
            background-color: #ddffdd;
            color: #4f8a10;
        }
        .status.known {
            background-color: #ffffcc;
            color: #9f6000;
        }
        .empty-state {
            text-align: center;
            padding: 30px;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Fail2BanSync管理界面</h1>
        <div>
            <span>欢迎，{{ username }} | </span>
            <a href="{{ url_for('logout') }}" class="logout">退出登录</a>
        </div>
    </div>
    
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="message {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="section">
            <h2>被封禁的IP地址</h2>
            {% if blocked_ips %}
            <table>
                <tr>
                    <th>IP地址</th>
                    <th>描述</th>
                    <th>状态</th>
                    <th>报告来源</th>
                    <th>封禁至</th>
                    <th>封禁次数</th>
                    <th>操作</th>
                </tr>
                {% for ip in blocked_ips %}
                <tr>
                    <td>{{ ip[1] }}</td>
                    <td>{{ ip[2] or '-' }}</td>
                    <td><span class="status {{ ip[3] }}">{{ ip[3] }}</span></td>
                    <td>{{ ip[4] }}</td>
                    <td>{{ ip[5] }}</td>
                    <td>{{ ip[7] }}</td>
                    <td>
                        <form method="post" action="{{ url_for('web_allow_ip', ip=ip[1]) }}">
                            <button type="submit" class="action-btn">放行</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <div class="empty-state">当前没有被封禁的IP地址</div>
            {% endif %}
        </div>
        
        <div class="section">
            <h2>已放行的IP地址</h2>
            {% if allowed_ips %}
            <table>
                <tr>
                    <th>IP地址</th>
                    <th>描述</th>
                    <th>状态</th>
                    <th>报告来源</th>
                    <th>封禁次数</th>
                    <th>放行时间</th>
                </tr>
                {% for ip in allowed_ips %}
                <tr>
                    <td>{{ ip[1] }}</td>
                    <td>{{ ip[2] or '-' }}</td>
                    <td><span class="status {{ ip[3] }}">{{ ip[3] }}</span></td>
                    <td>{{ ip[4] }}</td>
                    <td>{{ ip[7] }}</td>
                    <td>{{ ip[6] }}</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <div class="empty-state">当前没有已放行的IP地址</div>
            {% endif %}
        </div>
    </div>
</body>
</html>
''')

if __name__ == '__main__':
    try:
        init_db()
        logger.info("服务器已启动，监听地址: 0.0.0.0:5000")
        logger.info(f"配置信息: 封禁时间={BLOCK_DURATION}, 增量封禁={INCREMENT_BLOCK}, 封禁因子={BLOCK_FACTOR}, 最大封禁时间={MAX_BLOCK_DURATION}")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
    finally:
        # 关闭所有数据库连接
        db_pool.close_all()
        logger.info("服务器已关闭，所有资源已释放")
