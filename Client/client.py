import subprocess
import requests
import json
import ast
import re
import logging
from logging.handlers import RotatingFileHandler
import os
import configparser
import socket
from datetime import datetime
import time

# 默认配置
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


def setup_logging(log_file, max_bytes, backup_count):
    logger = logging.getLogger('ip_client')
    logger.setLevel(logging.INFO)
    
    # 清除已有的handler，避免重复添加
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 文件日志handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=int(max_bytes),
        backupCount=int(backup_count)
    )
    file_handler.setLevel(logging.INFO)
    
    # 控制台日志handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加handler
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 添加全局变量用于缓存已获取的封禁IP列表，减少重复调用
_banned_ips_cache = {}
_cache_timestamp = {}
CACHE_TTL = 30  # 缓存有效期（秒）
def load_config():
    """从文件加载配置或使用默认值"""
    config = configparser.ConfigParser()
    config.read_dict({'DEFAULT': DEFAULT_CLIENT_CONFIG})

    # 使用绝对路径获取配置文件，避免工作目录问题
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, 'clientconfig.ini')
    
    if os.path.exists(config_file_path):
        config.read(config_file_path)
        logger.info(f"已加载配置文件: {config_file_path}")
    else:
        logger.info(f"未找到配置文件: {config_file_path}，使用默认配置")

    token = ""
    if config.has_option('auth', 'token'):
        token = config.get('auth', 'token')

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
        },
        'auth': {
            'token': token
        }
    }

def get_banned_ips(jail):
    """
    获取Fail2Ban中指定jail的封禁IP列表
    使用缓存机制减少频繁调用fail2ban-client的开销
    """
    current_time = time.time()
    
    # 检查缓存是否存在且未过期
    if jail in _banned_ips_cache and jail in _cache_timestamp:
        if current_time - _cache_timestamp[jail] < CACHE_TTL:
            return _banned_ips_cache[jail]
    
    # 缓存不存在或已过期，重新获取数据
    try:
        result = subprocess.run(['fail2ban-client', 'status', jail], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True, 
                               check=True)
        
        # 使用正则表达式提取IP地址，效率高于逐行解析
        import re
        ip_pattern = r'[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'
        ips = re.findall(ip_pattern, result.stdout)
        
        # 更新缓存
        _banned_ips_cache[jail] = ips
        _cache_timestamp[jail] = current_time
        
        return ips
    except subprocess.CalledProcessError:
        # 重置该jail的缓存，避免缓存错误数据
        _banned_ips_cache.pop(jail, None)
        _cache_timestamp.pop(jail, None)
        return []

def get_local_ip_address():
    try:
        # 使用socket模块获取本地主机名
        hostname = socket.gethostname()
        return hostname
    except Exception as e:
        logger.error(f"获取主机名时出错: {e}")
        return None

def send_banned_ips(banned_ips, server_url, ip_address, logger, token):
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    data = {
        'ips': banned_ips,
        'description': '来自fail2ban的被封禁IP',
        'status': 'blocked',
        'reported_by': ip_address
    }
    try:
        response = requests.post(f"{server_url}/add_ips", headers=headers, data=json.dumps(data))
        if response.status_code == 201:
            logger.info("IPs发送成功。")
        else:
            logger.error(f"发送IP时出错: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"发送请求时出错: {e}")

def get_unknown_ips(server_url, ip_address, logger, page_size=100, token=None):
    """
    从服务器获取未知IP列表
    支持分页获取，以处理大量IP数据
    """
    # 准备headers，包含认证信息
    headers = {}
    if token:
        headers = {'Authorization': f'Bearer {token}'}
    
    try:
        unknown_ips = []
        page = 1
        
        while True:
            # 构建带分页参数的URL
            paginated_url = f"{server_url}/get_ips?page={page}&page_size={page_size}"
            
            # 使用会话保持连接，提高多次请求的效率
            with requests.Session() as session:
                response = session.get(paginated_url, headers=headers, timeout=30)
                response.raise_for_status()
                
                try:
                    data = response.json()
                except ValueError:
                    logger.error(f"从服务器获取未知IP时收到无效的JSON响应: {response.text}")
                    return []
                
                # 处理数据格式
                items = data.get('items', [])
                
                # 没有更多数据时退出循环
                if not items:
                    break
                
                # 提取IP地址并过滤空值
                batch_ips = []
                for item in items:
                    ip = item.get('ip', '').strip() or item.get('ip_address', '').strip()
                    if ip:  # 只添加非空IP
                        batch_ips.append(ip)
                
                unknown_ips.extend(batch_ips)
                
                # 检查是否还有更多页面
                total = data.get('total', 0)
                if len(unknown_ips) >= total:
                    break
                
                page += 1
                
                # 添加短暂延迟，避免对服务器造成过大压力
                time.sleep(0.1)
        
        # 只在日志中显示部分IP以避免日志过大
        display_limit = 10
        if len(unknown_ips) <= display_limit:
            logger.info(f"从服务器获取到的未知IP: {unknown_ips}")
        else:
            logger.info(f"从服务器获取到 {len(unknown_ips)} 个未知IP，前{display_limit}个: {unknown_ips[:display_limit]}...")
            
        return unknown_ips
    except requests.exceptions.RequestException as e:
        logger.error(f"从服务器获取未知IP时出错: {e}")
        return []
    except Exception as e:
        logger.error(f"处理未知IP数据时发生错误: {e}")
        return []

def get_allowed_ips(server_url, logger, page_size=100, token=None):
    """
    从服务器获取允许IP列表
    支持分页获取，以处理大量IP数据
    """
    # 准备headers，包含认证信息
    headers = {}
    if token:
        headers = {'Authorization': f'Bearer {token}'}
    
    try:
        allowed_ips = []
        page = 1
        
        while True:
            # 构建带分页参数的URL
            paginated_url = f"{server_url}/get_allowed_ips?page={page}&page_size={page_size}"
            
            # 使用会话保持连接
            with requests.Session() as session:
                response = session.get(paginated_url, headers=headers, timeout=30)
                response.raise_for_status()
                
                try:
                    data = response.json()
                except ValueError:
                    logger.error(f"从服务器获取允许IP时收到无效的JSON响应: {response.text}")
                    return []
                
                # 处理数据格式
                items = data.get('items', [])
                
                # 没有更多数据时退出循环
                if not items:
                    break
                
                # 提取IP地址并过滤空值
                batch_ips = []
                for item in items:
                    ip = item.get('ip', '').strip() or item.get('ip_address', '').strip()
                    if ip:  # 只添加非空IP
                        batch_ips.append(ip)
                
                allowed_ips.extend(batch_ips)
                
                # 检查是否还有更多页面
                total = data.get('total', 0)
                if len(allowed_ips) >= total:
                    break
                
                page += 1
                time.sleep(0.1)  # 添加短暂延迟
        
        # 只在日志中显示部分IP以避免日志过大
        display_limit = 10
        if len(allowed_ips) <= display_limit:
            logger.info(f"从服务器获取到的允许IP: {allowed_ips}")
        else:
            logger.info(f"从服务器获取到 {len(allowed_ips)} 个允许IP，前{display_limit}个: {allowed_ips[:display_limit]}...")
            
        return allowed_ips
    except requests.exceptions.RequestException as e:
        logger.error(f"从服务器获取允许IP时出错: {e}")
        return []
    except Exception as e:
        logger.error(f"处理允许IP数据时发生错误: {e}")
        return []

def send_banned_ips(server_url, banned_ips, logger, token=None):
    """
    发送封禁IP到服务器
    支持批量发送，以处理大量IP数据
    """
    # 准备headers，包含认证信息
    headers = {}
    if token:
        headers = {'Authorization': f'Bearer {token}'}
    
    try:
        # 如果没有IP，直接返回
        if not banned_ips:
            logger.info("没有IP需要发送到服务器")
            return
        
        # 批量发送优化：每批发送固定数量的IP
        batch_size = 500
        total_ips = len(banned_ips)
        success_count = 0
        
        logger.info(f"准备发送 {total_ips} 个封禁IP到服务器")
        
        # 分批处理
        for i in range(0, total_ips, batch_size):
            batch = banned_ips[i:i + batch_size]
            batch_data = {'ips': batch}
            
            try:
                with requests.Session() as session:
                    response = session.post(f"{server_url}/add_ips", 
                                           json=batch_data, 
                                           headers=headers,
                                           timeout=60)  # 增加超时时间，应对大量数据传输
                    response.raise_for_status()
                    
                    success_count += len(batch)
                    logger.info(f"已成功发送批次 {i // batch_size + 1}/{(total_ips + batch_size - 1) // batch_size}，IP数量: {len(batch)}")
                    
                    # 添加短暂延迟，避免对服务器造成过大压力
                    if i + batch_size < total_ips:
                        time.sleep(0.2)
                        
            except requests.exceptions.RequestException as e:
                logger.error(f"发送IP批次时出错 (批次 {i // batch_size + 1}): {e}")
                # 继续处理下一批次
        
        logger.info(f"IP发送完成，共发送 {success_count}/{total_ips} 个IP")
        
    except Exception as e:
        logger.error(f"发送封禁IP到服务器时发生未知错误: {e}")

def main():
    # 导入time模块（如果之前没有导入）
    import time
    import traceback
    
    # 确保在开始时就初始化一个基本的logger，以防配置加载失败
    basic_logger = logging.getLogger('ip_client_basic')
    basic_logger.setLevel(logging.INFO)
    
    # 添加控制台handler
    if not basic_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        basic_logger.addHandler(console_handler)
    
    try:
        config = load_config()
        
        # 从配置中获取日志参数
        log_config = config.get('logging', {})
        log_file = log_config.get('log_file', 'client.log')
        max_bytes = log_config.get('max_bytes', '1048576')
        backup_count = log_config.get('backup_count', '3')
        
        # 获取服务器配置
        server_config = config.get('server', {})
        protocol = server_config.get('protocol', 'http')
        host = server_config.get('host', 'localhost')
        port = server_config.get('port', '5000')
        server_url = f"{protocol}://{host}:{port}"
        
        jail = config.get('fail2ban', {}).get('jail', 'sshd')
        
        # 获取认证token
        token = config.get('auth', {}).get('token', '')
        
        # 初始化正式logger
        logger = setup_logging(log_file, max_bytes, backup_count)
        logger.info(f"程序启动，服务器URL: {server_url}, Jail: {jail}")
        
        # 在main函数开始处添加缓存清理
        def clear_cache():
            """清理过期缓存"""
            current_time = time.time()
            for jail_name in list(_cache_timestamp.keys()):
                if current_time - _cache_timestamp[jail_name] > CACHE_TTL:
                    _banned_ips_cache.pop(jail_name, None)
                    _cache_timestamp.pop(jail_name, None)
        
        # 定期清理缓存
        clear_cache()
        
        # 获取本地IP地址
        local_ip = get_local_ip_address()
        logger.info(f"本地IP地址: {local_ip}")
        
        # 获取Fail2Ban中的被封禁IP列表
        banned_ips = get_banned_ips(jail)
        logger.info(f"当前Fail2Ban中被封禁的IP数量: {len(banned_ips)}")
        
        # 发送被封禁IP到服务器
        if banned_ips:
            send_banned_ips(server_url, banned_ips, logger, token)
        
        # 从服务器获取未知IP列表
        unknown_ips = get_unknown_ips(server_url, local_ip, logger, page_size=200, token=token)
        
        # 添加未知IP到Fail2Ban
        if unknown_ips:
            # 大批量IP处理时的优化策略
            if len(unknown_ips) > 1000:  # 当IP数量超过1000时使用更大的批次
                add_ips_to_fail2ban(unknown_ips, jail, logger)
            else:
                add_ips_to_fail2ban(unknown_ips, jail, logger)
        
        # 从服务器获取允许的IP列表
        allowed_ips = get_allowed_ips(server_url, logger, page_size=200, token=token)
        
        # 从Fail2Ban中允许这些IP
        if allowed_ips:
            allow_ips_in_fail2ban(allowed_ips, jail, logger)
        
        logger.info("程序执行完成")
        
    except Exception as e:
        # 使用basic_logger或尝试使用logger记录错误
        try:
            logger.error(f"程序执行过程中发生错误: {e}")
            logger.error(f"错误堆栈: {traceback.format_exc()}")
        except (NameError, AttributeError):
            # 如果logger未定义，使用basic_logger
            basic_logger.error(f"程序执行过程中发生错误: {e}")
            basic_logger.error(f"错误堆栈: {traceback.format_exc()}")

# 在文件顶部添加缺少的import
# 确保在文件开头导入所有必要的模块
def load_config():
    import os
    import json
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

# 确保文件底部有main函数调用
if __name__ == "__main__":
    main()