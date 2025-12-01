import sqlite3
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_compress import Compress
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

# 配置gzip压缩
compress = Compress()
compress.init_app(app)

# 压缩配置选项
app.config['COMPRESS_MIMETYPES'] = ['text/html', 'text/css', 'text/xml', 'application/json', 'application/javascript']
app.config['COMPRESS_LEVEL'] = 6  # 压缩级别1-9，6是平衡压缩率和速度的选择
app.config['COMPRESS_MIN_SIZE'] = 500  # 只有大于500字节的响应才会被压缩

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
            'allowed_duration': '2m',
            'web_user': 'admin',
            'web_pass': 'admin123'
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
        'api_tokens': tokens,
        'web_user': config.get('DEFAULT', 'web_user', fallback='admin'),
        'web_pass': config.get('DEFAULT', 'web_pass', fallback='admin123')
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
WEB_USERS = config['web_user']
WEB_PASS = config['web_pass']
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
        
        # 添加数据库索引以优化查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ip_addresses_ip ON ip_addresses(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ip_addresses_status ON ip_addresses(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ip_addresses_status_ip ON ip_addresses(status, ip_address)')
        
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

# 用户名密码认证（用于Web界面）
web_auth = HTTPBasicAuth()
# 初始化用户数据库（实际项目中应该从配置文件或数据库加载）
users = {
    WEB_USERS: generate_password_hash(WEB_PASS)  # 默认用户名: admin, 密码: admin123
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
    
    # 处理gzip压缩的请求体
    if request.headers.get('Content-Encoding') == 'gzip':
        import gzip
        import io
        try:
            # 读取压缩数据
            compressed_data = request.get_data()
            # 解压数据
            gzip_stream = io.BytesIO(compressed_data)
            with gzip.GzipFile(fileobj=gzip_stream, mode='rb') as f:
                decompressed_data = f.read()
            # 解析JSON
            import json
            data = json.loads(decompressed_data.decode('utf-8'))
        except Exception as e:
            logger.error(f"解压gzip数据失败: {e}")
            return jsonify({"error": "无效的压缩数据"}), 400
    else:
        # 标准JSON请求
        data = request.json
    ips = data.get('ips', [])
    description = data.get('description', '')
    status = data.get('status', 'blocked')
    reported_by = f"{client_name}@{client_ip}"

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

# 通用的获取IP列表函数（支持分页和查询）
@auth.login_required
def get_ip_list(status):
    update_ip_status()
    client_ip = get_client_ip()
    client_name = auth.current_user()
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查是否需要分页（只有明确提供了page参数时才使用分页）
        page_param = request.args.get('page')
        use_pagination = page_param is not None
        
        # 初始化分页参数
        page = int(page_param) if page_param else 1
        per_page = int(request.args.get('per_page', 50))
        search_ip = request.args.get('search_ip', '').strip()
        
        # 构建查询SQL
        if search_ip:
            # 搜索过滤
            cursor.execute('SELECT COUNT(*) FROM ip_addresses WHERE status = ? AND ip_address LIKE ?', 
                          (status, f'%{search_ip}%'))
            total_count = cursor.fetchone()[0]
            
            if use_pagination:
                # 使用分页
                offset = (page - 1) * per_page
                cursor.execute('SELECT * FROM ip_addresses WHERE status = ? AND ip_address LIKE ? LIMIT ? OFFSET ?', 
                              (status, f'%{search_ip}%', per_page, offset))
            else:
                # 不使用分页，返回所有匹配结果
                cursor.execute('SELECT * FROM ip_addresses WHERE status = ? AND ip_address LIKE ?', 
                              (status, f'%{search_ip}%'))
        else:
            # 无搜索过滤
            cursor.execute('SELECT COUNT(*) FROM ip_addresses WHERE status = ?', (status,))
            total_count = cursor.fetchone()[0]
            
            if use_pagination:
                # 使用分页
                offset = (page - 1) * per_page
                cursor.execute('SELECT * FROM ip_addresses WHERE status = ? LIMIT ? OFFSET ?', 
                              (status, per_page, offset))
            else:
                # 不使用分页，返回所有结果
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
        
        # 根据是否使用分页构建不同的响应
        if use_pagination:
            # 计算总页数
            total_pages = (total_count + per_page - 1) // per_page
            
            # 构建包含分页信息的响应
            response = {
                "items": ip_addresses,
                "pagination": {
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "current_page": page,
                    "items_per_page": per_page,
                    "search_ip": search_ip
                }
            }
            
            status_names = {
                'blocked': '被封禁',
                'allowed': '允许的',
                'known': '已知的'
            }
            
            query_info = f"(搜索: {search_ip}) " if search_ip else ""
            logger.info(f"客户端 {client_name} ({client_ip}) 请求获取{status_names.get(status, status)}IP列表 {query_info}第 {page}/{total_pages} 页，共 {total_count} 个")
        else:
            # 不包含分页信息的响应
            response = {
                "items": ip_addresses,
                "total_items": total_count,
                "search_ip": search_ip
            }
            
            status_names = {
                'blocked': '被封禁',
                'allowed': '允许的',
                'known': '已知的'
            }
            
            query_info = f"(搜索: {search_ip}) " if search_ip else ""
            logger.info(f"客户端 {client_name} ({client_ip}) 请求获取{status_names.get(status, status)}IP列表 {query_info}共 {total_count} 个")
        
        return jsonify(response), 200
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

# 设置密钥用于session加密
app.secret_key = os.urandom(24)
# 设置session过期时间
app.permanent_session_lifetime = timedelta(minutes=30)

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




