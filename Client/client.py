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

def get_local_mac_address():
    try:
        result = subprocess.run(['ip', 'addr'], capture_output=True, text=True, check=True)
        mac_address_match = re.search(r'link/ether\s+([0-9A-Fa-f:]{17})', result.stdout)
        if mac_address_match:
            return mac_address_match.group(1)
        return None
    except Exception as e:
        print(f"获取MAC地址时出错: {e}")
        return None

def send_banned_ips(banned_ips, server_url, mac_address, logger, token):
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    data = {
        'ips': banned_ips,
        'description': '来自fail2ban的被封禁IP',
        'status': 'blocked',
        'reported_by': mac_address
    }
    try:
        response = requests.post(f"{server_url}/add_ips", headers=headers, data=json.dumps(data))
        if response.status_code == 201:
            logger.info("IPs发送成功。")
        else:
            logger.error(f"发送IP时出错: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"发送请求时出错: {e}")

def get_unknown_ips(server_url, mac_address, logger, token):
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(f"{server_url}/get_ips?mac_address={mac_address}", headers=headers)
        if response.status_code == 200:
            return response.json()
        logger.error(f"获取IP时出错: {response.status_code} - {response.text}")
        return []
    except requests.RequestException as e:
        logger.error(f"发送请求时出错: {e}")
        return []

def get_allowed_ips(server_url, logger, token):
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(f"{server_url}/get_allowed_ips", headers=headers)
        if response.status_code == 200:
            return response.json()
        logger.error(f"获取允许IP时出错: {response.status_code} - {response.text}")
        return []
    except requests.RequestException as e:
        logger.error(f"发送请求时出错: {e}")
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

        logger = setup_logging(
            config['logging']['log_file'],
            int(config['logging']['max_bytes']),
            int(config['logging']['backup_count'])
        )

        logger.info("客户端已启动")
        mac_address = get_local_mac_address()
        if not mac_address:
            logger.error("无法获取MAC地址。")
            return

        banned_ips = get_banned_ips(jail)
        if banned_ips:
            send_banned_ips(banned_ips, server_url, mac_address, logger, token)
        else:
            logger.info("未找到被封禁的IP。")

        unknown_ips = get_unknown_ips(server_url, mac_address, logger, token)
        if unknown_ips:
            ip_addresses = [ip['ip_address'] for ip in unknown_ips]
            add_ips_to_fail2ban(ip_addresses, jail, logger)
        else:
            logger.info("未找到未知IP。")

        allowed_ips = get_allowed_ips(server_url, logger, token)
        if allowed_ips:
            ip_addresses = [ip['ip_address'] for ip in allowed_ips]
            allow_ips_in_fail2ban(ip_addresses, jail, logger)
        else:
            logger.info("未找到允许的IP。")

    except Exception as e:
        print(f"主函数出错: {e}")
        raise

if __name__ == '__main__':
    main()
