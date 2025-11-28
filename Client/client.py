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

def load_config():
    """从文件加载配置或使用默认值"""
    config = configparser.ConfigParser()
    config.read_dict({'DEFAULT': DEFAULT_CLIENT_CONFIG})

    if os.path.exists('clientconfig.ini'):
        config.read('clientconfig.ini')

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

def get_banned_ips(jail):
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
        return output.split()
    except Exception as e:
        print(f"获取被封禁IP时出错: {e}")
        return []

def get_local_ip_address():
    try:
        # 使用socket模块获取本地IP地址
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except Exception as e:
        print(f"获取IP地址时出错: {e}")
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

def get_unknown_ips(server_url, ip_address, logger, token):
    headers = {'Authorization': f'Bearer {token}'}
    try:
        logger.info(f"正在获取未知IP，服务器URL: {server_url}, IP地址: {ip_address}")
        response = requests.get(f"{server_url}/get_ips?ip_address={ip_address}", headers=headers)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"获取未知IP成功，响应数据: {data}")
            return data
        else:
            logger.error(f"获取IP时出错: {response.status_code} - {response.text}")
            return []
    except requests.RequestException as e:
        logger.error(f"发送请求时出错: {e}")
        return []
    except ValueError as e:
        logger.error(f"解析响应JSON时出错: {e}")
        return []

def get_allowed_ips(server_url, logger, token):
    headers = {'Authorization': f'Bearer {token}'}
    try:
        logger.info(f"正在获取允许的IP，服务器URL: {server_url}")
        response = requests.get(f"{server_url}/get_allowed_ips", headers=headers)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"获取允许IP成功，响应数据: {data}")
            return data
        else:
            logger.error(f"获取允许IP时出错: {response.status_code} - {response.text}")
            return []
    except requests.RequestException as e:
        logger.error(f"发送请求时出错: {e}")
        return []
    except ValueError as e:
        logger.error(f"解析响应JSON时出错: {e}")
        return []

def add_ips_to_fail2ban(ips, jail, logger):
    try:
        for ip in ips:
            subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], check=True)
        logger.info(f"IPs已成功添加到Fail2Ban: {ips}")
    except subprocess.CalledProcessError as e:
        logger.error(f"添加IP到Fail2Ban时出错: {e}")

def allow_ips_in_fail2ban(ips, jail, logger):
    try:
        for ip in ips:
            subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], check=True)
        logger.info(f"IPs已在Fail2Ban中被允许: {ips}")
    except subprocess.CalledProcessError as e:
        logger.error(f"在Fail2Ban中允许IP时出错: {e}")

def main():
    try:
        config = load_config()
        token = config['auth']['token']

        server_url = f"{config['server']['protocol']}://{config['server']['host']}:{config['server']['port']}"
        jail = config['fail2ban']['jail']

        # 先初始化logger
        logger = setup_logging(
            config['logging']['log_file'],
            int(config['logging']['max_bytes']),
            int(config['logging']['backup_count'])
        )
        
        # 然后再使用logger
        logger.info(f"配置加载成功，服务器信息: {config['server']}")
        logger.info("客户端已启动")
        logger.info("正在获取IP地址...")
        ip_address = get_local_ip_address()
        if not ip_address:
            logger.error("无法获取IP地址。")
            return
        logger.info(f"IP地址获取成功: {ip_address}")

        logger.info(f"正在获取被封禁IP，jail: {jail}")
        banned_ips = get_banned_ips(jail)
        logger.info(f"获取被封禁IP完成，数量: {len(banned_ips)}")
        if banned_ips:
            send_banned_ips(banned_ips, server_url, ip_address, logger, token)
        else:
            logger.info("未找到被封禁的IP。")

        logger.info("正在获取未知IP...")
        unknown_ips = get_unknown_ips(server_url, ip_address, logger, token)
        logger.info(f"获取未知IP完成，响应类型: {type(unknown_ips).__name__}, 值: {unknown_ips}")
        if unknown_ips:
            # 检查unknown_ips是否为字典且包含'items'键
            if isinstance(unknown_ips, dict) and 'items' in unknown_ips:
                ip_addresses = [ip.get('ip', '') for ip in unknown_ips['items'] if isinstance(ip, dict)]
            elif isinstance(unknown_ips, list):
                ip_addresses = [ip.get('ip_address', '') for ip in unknown_ips if isinstance(ip, dict)]
            else:
                logger.warning(f"未知IP数据格式异常: {unknown_ips}")
                ip_addresses = []
            logger.info(f"准备添加到Fail2Ban的IP数量: {len(ip_addresses)}, IP列表: {ip_addresses}")
            if ip_addresses:
                add_ips_to_fail2ban(ip_addresses, jail, logger)
        else:
            logger.info("未找到未知IP。")

        logger.info("正在获取允许的IP...")
        allowed_ips = get_allowed_ips(server_url, logger, token)
        logger.info(f"获取允许IP完成，响应类型: {type(allowed_ips).__name__}, 值: {allowed_ips}")
        if allowed_ips:
            # 检查allowed_ips是否为字典且包含'items'键
            if isinstance(allowed_ips, dict) and 'items' in allowed_ips:
                ip_addresses = [ip.get('ip', '') for ip in allowed_ips['items'] if isinstance(ip, dict)]
            elif isinstance(allowed_ips, list):
                ip_addresses = [ip.get('ip_address', '') for ip in allowed_ips if isinstance(ip, dict)]
            else:
                logger.warning(f"允许IP数据格式异常: {allowed_ips}")
                ip_addresses = []
            logger.info(f"准备在Fail2Ban中允许的IP数量: {len(ip_addresses)}, IP列表: {ip_addresses}")
            if ip_addresses:
                allow_ips_in_fail2ban(ip_addresses, jail, logger)
        else:
            logger.info("未找到允许的IP。")

    except Exception as e:
        logger.error(f"主函数出错: {e}")
        import traceback
        logger.error(f"错误堆栈: {traceback.format_exc()}")


if __name__ == '__main__':
    main()




