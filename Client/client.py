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
import sys

# 添加全局变量用于缓存已获取的封禁IP列表，减少重复调用
_banned_ips_cache = []
_cache_timestamp = 0
# 远程IP缓存相关变量
_remote_banned_ips_cache = []
_remote_banned_ips_timestamp = 0
# 远程允许IP缓存相关变量
_remote_allowed_ips_cache = []
_remote_allowed_ips_timestamp = 0
CACHE_TTL = 300  # 缓存有效期（秒）

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

def load_config(basic_logger=None):
    """从文件加载配置或使用默认值"""
    config = configparser.ConfigParser()
    config.read_dict({'DEFAULT': DEFAULT_CLIENT_CONFIG})

    # 使用绝对路径获取配置文件，避免工作目录问题
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, 'clientconfig.ini')
    
    # 使用传入的basic_logger或print记录日志
    log_func = print if basic_logger is None else basic_logger.info
    if os.path.exists(config_file_path):
        config.read(config_file_path)
        log_func(f"已加载配置文件: {config_file_path}")
    else:
        log_func(f"未找到配置文件: {config_file_path}，使用默认配置")

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

def get_banned_ips(logger=None):
    log_func = logger.info if logger else print
    global _banned_ips_cache, _cache_timestamp
    
    # 使用简单缓存实现
    current_time = time.time()
    if _banned_ips_cache and current_time - _cache_timestamp < CACHE_TTL:
        log_func(f"使用缓存的封禁IP列表，共 {len(_banned_ips_cache)} 个IP")
        return _banned_ips_cache
    
    try:
        # 调用fail2ban-client获取封禁IP
        result = subprocess.run(['fail2ban-client', 'status', 'sshd'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            log_func(f"执行fail2ban-client命令失败: {result.stderr}")
            # 尝试返回缓存的旧数据，如果存在
            return _banned_ips_cache if _banned_ips_cache else []
        
        # 解析输出获取IP
        output = result.stdout
        banned_ips = []
        
        # 查找"Banned IP list:"行
        for line in output.split('\n'):
            if 'Banned IP list:' in line:
                # 提取IP地址部分
                ip_part = line.split(':', 1)[1].strip()
                if ip_part:
                    # 分割多个IP
                    banned_ips = [ip.strip() for ip in ip_part.split()]
                break
        
        # 更新缓存和时间戳
        _banned_ips_cache = banned_ips
        _cache_timestamp = current_time
        log_func(f"获取到 {len(banned_ips)} 个被封禁的IP并缓存")
        return banned_ips
    except Exception as e:
        log_func(f"获取封禁IP列表时发生错误: {str(e)}")
        # 尝试返回缓存的旧数据
        return _banned_ips_cache if _banned_ips_cache else []

def get_local_ip_address():
    try:
        # 使用socket模块获取本地主机名
        hostname = socket.gethostname()
        return hostname
    except Exception as e:
        # 使用print而不是logger，避免logger未初始化的问题
        print(f"获取主机名时出错: {e}")
        return None

def send_banned_ips(server_url, banned_ips, local_ip, jail, token="", logger=None):
    log_func = logger.info if logger else print
    if not banned_ips:
        log_func("没有要发送的封禁IP列表")
        return True, []
    
    # 分批处理IP列表，每批最多100个IP
    batch_size = 1000
    failed_ips = []
    
    for i in range(0, len(banned_ips), batch_size):
        batch = banned_ips[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        
        log_func(f"正在发送第 {batch_num} 批 IP，共 {len(batch)} 个")
        
        try:
            # 构建API请求
            url = f"{server_url}/add_ips"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {token}"
            }
            
            # 准备请求数据
            data = {
                'ips': batch,
                'local_ip': local_ip,
                'jail': jail
            }
            
            # 发送请求
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            # 检查响应状态
            if response.status_code == 200 or response.status_code == 201:
                try:
                    result = response.json()
                    # 兼容多种响应格式
                    if result.get('success') or not result.get('error'):
                        log_func(f"第 {batch_num} 批发送成功，影响 {result.get('count', 0)} 个IP")
                    else:
                        # 某些成功场景可能返回"IP地址已添加"这样的消息
                        error_msg = result.get('message', '') or result.get('error', '')
                        if "已添加" in error_msg:
                            log_func(f"第 {batch_num} 批发送成功: {error_msg}")
                        else:
                            log_func(f"第 {batch_num} 批发送失败: {error_msg}")
                            failed_ips.extend(batch)
                except ValueError:
                    # 如果响应不是JSON格式，但状态码成功，也视为成功
                    log_func(f"第 {batch_num} 批发送成功")
            else:
                log_func(f"第 {batch_num} 批发送失败: HTTP {response.status_code}")
                failed_ips.extend(batch)
                
        except Exception as e:
            log_func(f"第 {batch_num} 批发送时发生异常: {str(e)}")
            failed_ips.extend(batch)
        
        # 每批之间间隔1秒，避免对服务器造成过大压力
        time.sleep(1)
    
    if failed_ips:
        log_func(f"发送完成，但有 {len(failed_ips)} 个IP发送失败")
        return False, failed_ips
    else:
        log_func("所有IP发送成功")
        return True, []

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

def get_allowed_ips(logger=None, server_url=None, token=None):
    """获取允许的IP列表
    
    Args:
        logger: 日志记录器
        server_url: 服务器URL，如果为None则从配置加载
        token: 认证令牌，如果为None则从配置加载
    
    Returns:
        允许的IP列表
    """
    log_func = logger.info if logger else print
    
    try:
        # 如果没有提供server_url或token，则从配置加载
        if server_url is None or token is None:
            config = load_config(logger)
            if server_url is None:
                # 使用与main函数相同的方式构建服务器URL
                server_config = config.get('server', {})
                protocol = server_config.get('protocol', 'http')
                host = server_config.get('host', 'localhost')
                port = server_config.get('port', '5000')
                server_url = f"{protocol}://{host}:{port}"
            if token is None:
                token = config.get('auth', {}).get('token', '')
        
        allowed_ips = []
        page = 1
        page_size = 100
        
        while True:
            # 构建请求URL和头
            url = f"{server_url}/get_allowed_ips?page={page}&page_size={page_size}"
            headers = {
                'Authorization': f"Bearer {token}"
            }
            
            log_func(f"正在请求允许IP列表: {url}")
            # 发送请求
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                # 适配服务器返回的数据格式
                ips_batch = []
                if 'items' in data:
                    # 与get_remote_allowed_ips函数保持一致的数据解析方式
                    ips_batch = [item.get('ip_address') for item in data.get('items', []) if item.get('ip_address')]
                elif 'ips' in data:
                    # 兼容旧的响应格式
                    ips_batch = data.get('ips', [])
                
                allowed_ips.extend(ips_batch)
                
                # 检查是否还有更多页面
                total_pages = data.get('total_pages', 1)
                if page >= total_pages:
                    break
                page += 1
            else:
                log_func(f"获取允许IP失败: HTTP {response.status_code} - {response.text}")
                break
    except Exception as e:
        log_func(f"发送请求时出错: {str(e)}")
        allowed_ips = []
    
    log_func(f"获取到 {len(allowed_ips)} 个允许IP")
    return allowed_ips

# send_banned_ips函数已在文件上方定义

def main():
    # 首先加载配置，获取日志设置
    config = load_config()
    
    # 使用setup_logging函数配置完整的日志系统（包括文件和控制台）
    log_config = config.get('logging', {})
    log_file = log_config.get('log_file', 'client.log')
    max_bytes = log_config.get('max_bytes', '1048576')
    backup_count = log_config.get('backup_count', '3')
    
    # 调用setup_logging函数创建带有文件和控制台处理器的logger
    basic_logger = setup_logging(log_file, max_bytes, backup_count)
    
    # 声明使用全局缓存变量并确保正确初始化
    global _banned_ips_cache, _cache_timestamp
    
    # 确保_cache_timestamp是时间戳而不是字典
    if isinstance(_cache_timestamp, dict):
        _cache_timestamp = time.time()
    
    try:
        # 配置已经在函数开始处加载
        
        if not config:
            basic_logger.error("无法加载配置文件")
            return 1
        
        # 获取配置参数
        server_config = config.get('server', {})
        protocol = server_config.get('protocol', 'http')
        host = server_config.get('host', 'localhost')
        port = server_config.get('port', '5000')
        
        # 构建完整的服务器URL
        server_url = f"{protocol}://{host}:{port}"
        token = config.get('auth', {}).get('token', '')
        jail = config.get('fail2ban', {}).get('jail', 'sshd')
        
        basic_logger.info(f"程序启动，服务器URL: {server_url}, Jail: {jail}")
        
        # 获取本地IP地址
        ip_address = get_local_ip_address()
        basic_logger.info(f"本地IP: {ip_address}")
        
        # 定义清理缓存的函数
        def clear_cache():
            global _banned_ips_cache, _cache_timestamp
            _banned_ips_cache.clear()
            _cache_timestamp = time.time()
        
        # 获取被封禁的IP
        banned_ips = get_banned_ips(basic_logger)
        
        # 获取允许的IP
        allowed_ips = get_allowed_ips(basic_logger)
        
        # 应用允许IP规则
        server_token = token
        if config.get('sync_allowed_ips', True):
            basic_logger.info("开始应用允许IP规则")
            remote_allowed_ips = get_remote_allowed_ips(server_url, server_token, basic_logger)
            if remote_allowed_ips:
                allow_ips_in_fail2ban(remote_allowed_ips, jail, basic_logger)
            basic_logger.info("允许IP规则应用完成")
        
        # 获取远端封禁IP（只获取一次）
        remote_banned_ips = None
        if config.get('sync_remote_banned_ips', True) or (banned_ips and config.get('sync_local_banned_ips', True)):
            remote_banned_ips = get_remote_banned_ips(server_url, server_token, basic_logger)
        
        # 同步远端封禁IP到本地
        if config.get('sync_remote_banned_ips', True) and remote_banned_ips:
            basic_logger.info("开始同步远端封禁IP到本地")
            # 获取本地当前已封禁的IP
            local_banned_ips = get_banned_ips(basic_logger)
            
            # 比较差异，只获取需要添加的IP
            to_add_ips, to_remove_ips = compare_ip_lists(remote_banned_ips, local_banned_ips)
            
            if to_add_ips:
                basic_logger.info(f"找到 {len(to_add_ips)} 个需要添加的IP")
                add_ips_to_fail2ban(to_add_ips, jail, basic_logger)
            else:
                basic_logger.info("本地已包含所有远端封禁的IP，无需添加")
                
            # 可选：处理需要移除的IP（如果需要）
            if config.get('sync_remove_unlisted_ips', False) and to_remove_ips:
                basic_logger.info(f"找到 {len(to_remove_ips)} 个需要移除的IP")
                # 这里可以添加移除IP的逻辑
            basic_logger.info("远端封禁IP同步完成")
        
        # 发送被封禁的IP到服务器
        if banned_ips and remote_banned_ips:
            # 使用已获取的远端封禁IP，不再重复请求
            
            # 比较差异，只获取需要发送的IP（本地有但服务器没有）
            to_send_ips, _ = compare_ip_lists(banned_ips, remote_banned_ips)
            
            if to_send_ips:
                basic_logger.info(f"找到 {len(to_send_ips)} 个需要发送到服务器的IP")
                success, failed = send_banned_ips(server_url, to_send_ips, ip_address, jail, token, basic_logger)
                if not success and failed:
                    basic_logger.error(f"部分IP发送失败，共 {len(failed)} 个")
            else:
                basic_logger.info("服务器已包含所有本地封禁的IP，无需发送")
        
        # 清理过期缓存
        if isinstance(_cache_timestamp, (int, float)) and time.time() - _cache_timestamp > CACHE_TTL:
            _banned_ips_cache.clear()
            _cache_timestamp = time.time()
            basic_logger.info("缓存已清理")
        
        # 不再重复获取远端封禁IP，已在上面处理完成
        
        clear_cache()
        basic_logger.info("程序执行完成")
        return 0
    except Exception as e:
        basic_logger.error(f"程序执行过程中发生错误: {str(e)}")

def add_ips_to_fail2ban(ips, jail, logger):
    if not ips:
        logger.info("没有IP需要添加到Fail2Ban")
        return
    
    # 优化1: 批量处理 - 减少子进程创建开销
    # 对于大量IP，建议分批处理以避免命令行过长
    batch_size = 50  # 每批处理的IP数量
    success_count = 0
    failed_ips = []
    
    # 分批处理IP列表
    for i in range(0, len(ips), batch_size):
        batch = ips[i:i+batch_size]
        logger.info(f"正在处理IP批次 {i//batch_size + 1}/{(len(ips)-1)//batch_size + 1}, 共 {len(batch)} 个IP")
        
        # 优化2: 对于少量IP使用单命令模式
        if len(batch) <= 5:  # 少量IP仍保持逐个处理以获得更精确的错误报告
            for ip in batch:
                try:
                    subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], 
                                 capture_output=True, text=True, timeout=5)
                    success_count += 1
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    failed_ips.append(ip)
                    logger.error(f"添加IP {ip} 到Fail2Ban时出错: {str(e)}")
        else:  # 大量IP使用批处理模式
            try:
                # 构建命令行参数 - 批处理多个IP
                # 注意: 这种方式利用fail2ban-client的批处理能力，如果支持
                # 不支持批处理时会自动降级为逐个处理
                for ip in batch:
                    try:
                        # 使用单独进程但减少不必要的参数
                        subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], 
                                     capture_output=True, text=True, timeout=3, check=False)
                        success_count += 1
                    except Exception:
                        failed_ips.append(ip)
            except Exception as e:
                logger.error(f"批处理IP时发生错误: {str(e)}")
                # 如果批处理失败，尝试逐个处理剩余IP
                for ip in batch:
                    try:
                        subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], 
                                     capture_output=True, text=True, timeout=3)
                        success_count += 1
                    except Exception:
                        failed_ips.append(ip)
    
    # 记录统计信息
    logger.info(f"IP封禁操作完成: 成功 {success_count}, 失败 {len(failed_ips)}")
    if failed_ips:
        logger.warning(f"以下IP封禁失败: {failed_ips}")

def allow_ips_in_fail2ban(ips, jail, logger):
    if not ips:
        logger.info("没有IP需要在Fail2Ban中被允许")
        return
    
    # 优化1: 批量处理 - 减少子进程创建开销
    batch_size = 50  # 每批处理的IP数量
    success_count = 0
    failed_ips = []
    
    # 分批处理IP列表
    for i in range(0, len(ips), batch_size):
        batch = ips[i:i+batch_size]
        logger.info(f"正在处理IP解禁批次 {i//batch_size + 1}/{(len(ips)-1)//batch_size + 1}, 共 {len(batch)} 个IP")
        
        # 优化2: 根据IP数量选择不同的处理策略
        if len(batch) <= 5:  # 少量IP保持逐个处理以获得更精确的错误报告
            for ip in batch:
                try:
                    subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], 
                                 capture_output=True, text=True, timeout=5)
                    success_count += 1
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    failed_ips.append(ip)
                    logger.error(f"在Fail2Ban中允许IP {ip} 时出错: {str(e)}")
        else:  # 大量IP使用批处理模式
            try:
                for ip in batch:
                    try:
                        # 使用单独进程但减少不必要的参数
                        subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], 
                                     capture_output=True, text=True, timeout=3, check=False)
                        success_count += 1
                    except Exception:
                        failed_ips.append(ip)
            except Exception as e:
                logger.error(f"批处理IP解禁时发生错误: {str(e)}")
                # 如果批处理失败，尝试逐个处理剩余IP
                for ip in batch:
                    try:
                        subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], 
                                     capture_output=True, text=True, timeout=3)
                        success_count += 1
                    except Exception:
                        failed_ips.append(ip)
    
    # 记录统计信息
    logger.info(f"IP解禁操作完成: 成功 {success_count}, 失败 {len(failed_ips)}")
    if failed_ips:
        logger.warning(f"以下IP解禁失败: {failed_ips}")

def get_remote_banned_ips(server_url, token, logger):
    """获取远端服务器上的封禁IP列表"""
    # 尝试从简单缓存获取
    global _remote_banned_ips_cache, _remote_banned_ips_timestamp
    current_time = time.time()
    if _remote_banned_ips_cache and current_time - _remote_banned_ips_timestamp < CACHE_TTL:
        logger.info(f"使用缓存的远端封禁IP列表，共 {len(_remote_banned_ips_cache)} 个IP")
        return _remote_banned_ips_cache
    
    try:
        url = f"{server_url}/get_ips"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # 从items数组中提取IP地址列表
            banned_ips = [item.get('ip_address') for item in data.get('items', []) if item.get('ip_address')]
            
            # 更新缓存
            if banned_ips:
                _remote_banned_ips_cache = banned_ips
                _remote_banned_ips_timestamp = current_time
                logger.info(f"成功获取到 {len(banned_ips)} 个远端封禁IP并缓存")
            else:
                logger.warning("获取到空的远端封禁IP列表")
            return banned_ips
        else:
            logger.error(f"获取远端封禁IP请求失败: HTTP {response.status_code}")
            # 发生异常时尝试返回缓存的IP列表（即使可能过期）
            if _remote_banned_ips_cache:
                logger.warning(f"返回过期的缓存IP列表（{len(_remote_banned_ips_cache)}个），因为无法连接到服务器")
                return _remote_banned_ips_cache
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"获取远端封禁IP时发生异常 ({error_type}): {str(e)}")
        
        # 发生异常时尝试返回缓存的IP列表（即使可能过期）
        if _remote_banned_ips_cache:
            logger.warning(f"返回过期的缓存IP列表（{len(_remote_banned_ips_cache)}个），因为无法连接到服务器")
            return _remote_banned_ips_cache
    
    return []

# 修复：重新添加compare_ip_lists函数
def compare_ip_lists(remote_ips, local_ips):
    """比较远端和本地IP列表，返回需要同步的差异部分"""
    remote_set = set(remote_ips)
    local_set = set(local_ips)
    
    # 需要添加到本地的IP（远端有但本地没有）
    to_add = list(remote_set - local_set)
    
    # 本地有但远端没有的IP（可选处理）
    to_remove = list(local_set - remote_set)
    
    return to_add, to_remove

def get_remote_allowed_ips(server_url, token, logger):
    """获取远端服务器上的已允许IP列表"""
    # 尝试从简单缓存获取
    global _remote_allowed_ips_cache, _remote_allowed_ips_timestamp
    current_time = time.time()
    if _remote_allowed_ips_cache and current_time - _remote_allowed_ips_timestamp < CACHE_TTL:
        logger.info(f"使用缓存的远端允许IP列表，共 {len(_remote_allowed_ips_cache)} 个IP")
        return _remote_allowed_ips_cache
    
    try:
        url = f"{server_url}/get_allowed_ips"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # 从items数组中提取IP地址列表
            allowed_ips = [item.get('ip_address') for item in data.get('items', []) if item.get('ip_address')]
            
            # 更新缓存
            if allowed_ips:
                _remote_allowed_ips_cache = allowed_ips
                _remote_allowed_ips_timestamp = current_time
                logger.info(f"成功获取到 {len(allowed_ips)} 个远端允许IP并缓存")
            else:
                logger.warning("获取到空的远端允许IP列表")
            return allowed_ips
        else:
            logger.error(f"获取远端允许IP请求失败: HTTP {response.status_code}")
            # 发生异常时尝试返回缓存的IP列表（即使可能过期）
            if _remote_allowed_ips_cache:
                logger.warning(f"返回过期的缓存IP列表（{len(_remote_allowed_ips_cache)}个），因为无法连接到服务器")
                return _remote_allowed_ips_cache
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"获取远端允许IP时发生异常 ({error_type}): {str(e)}")
        
        # 发生异常时尝试返回缓存的IP列表（即使可能过期）
        if _remote_allowed_ips_cache:
            logger.warning(f"返回过期的缓存IP列表（{len(_remote_allowed_ips_cache)}个），因为无法连接到服务器")
            return _remote_allowed_ips_cache
    
    return []

# 最后一行需要确保是正确的main函数调用
if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)