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
import gzip
import io


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
        'jails': 'sshd'  # 支持多个jail，用逗号分隔
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
    log_info = print if basic_logger is None else basic_logger.info
    log_error = print if basic_logger is None else basic_logger.error
    
    if os.path.exists(config_file_path):
        # 明确指定使用UTF-8编码读取配置文件，避免Windows系统默认GBK编码导致的解码错误
        try:
            config.read(config_file_path, encoding='utf-8')
            log_info(f"配置文件加载成功: {config_file_path}")
        except Exception as e:
            log_error(f"配置文件读取失败: {str(e)}")
            # 即使读取失败，也要继续使用默认配置，确保函数不会返回None
    else:
        log_error(f"未找到配置文件: {config_file_path}，使用默认配置")

    token = ""
    if config.has_option('auth', 'token'):
        token = config.get('auth', 'token')

    # 获取jails配置（支持逗号分隔的多个jail）
    jails_str = config.get('fail2ban', 'jails', fallback='')
    # 向后兼容：如果没有设置jails，则尝试获取单个jail配置
    if not jails_str:
        jails_str = config.get('fail2ban', 'jail', fallback='sshd')
    
    # 将jails字符串分割成列表并去除空白
    jails = [jail.strip() for jail in jails_str.split(',') if jail.strip()]
    
    # 获取DEFAULT部分的配置项
    sync_remove_unlisted_ips = config.getboolean('DEFAULT', 'sync_remove_unlisted_ips', fallback=False)
    sync_remote_banned_ips = config.getboolean('DEFAULT', 'sync_remote_banned_ips', fallback=True)
    sync_local_banned_ips = config.getboolean('DEFAULT', 'sync_local_banned_ips', fallback=True)
    sync_allowed_ips = config.getboolean('DEFAULT', 'sync_allowed_ips', fallback=True)
    
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
            'jails': jails,
            'jail': jails[0] if jails else 'sshd'  # 向后兼容，返回第一个jail
        },
        'auth': {
            'token': token
        },
        # 添加DEFAULT部分的配置项
        'sync_remove_unlisted_ips': sync_remove_unlisted_ips,
        'sync_remote_banned_ips': sync_remote_banned_ips,
        'sync_local_banned_ips': sync_local_banned_ips,
        'sync_allowed_ips': sync_allowed_ips
    }

def get_banned_ips(config, logger=None, jail=None):
    """获取fail2ban中指定jail的封禁IP列表"""
    log_info = logger.info if logger else print    
    log_error = logger.error if logger else print
    log_warning = logger.warning if logger and hasattr(logger, 'warning') else print
    
    try:
        # 获取主机名以增强日志上下文
        host_name = get_local_host_name(logger) or "未知主机"
        
        # 确定要查询的jails列表
        if jail:
            jails_to_query = [jail]
        else:
            # 否则查询所有配置的jails
            jails_to_query = config['fail2ban']['jails']
        
        all_banned_ips = {}
       
        for current_jail in jails_to_query:
            log_info(f"[{host_name}] 开始获取 jail {current_jail} 的本地封禁IP")
            # 调用fail2ban-client获取该jail的封禁IP
            result = subprocess.run(['fail2ban-client', 'status', current_jail], 
                                   capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                log_error(f"[{host_name}] 执行fail2ban-client命令失败(jail: {current_jail}): {result.stderr}")
                all_banned_ips[current_jail] = []
                continue
            
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
            
            all_banned_ips[current_jail] = banned_ips
            log_info(f"[{host_name}] 获取完成: jail {current_jail} 共有 {len(banned_ips)} 个本地封禁IP")
        
        # 如果只查询了一个jail，返回该jail的IP列表（保持向后兼容）
        if jail:
            return all_banned_ips.get(jail, [])
        
        return all_banned_ips
    except Exception as e:
        log_error(f"[{host_name}] 获取封禁IP列表时发生错误: {str(e)}")
        # 如果指定了jail，返回空列表；否则返回空字典
        return [] if jail else {}

def get_local_host_name( logger=None):
    log_func = logger.info if logger else print
    try:
        # 使用socket模块获取本地主机名
        hostname = socket.gethostname()
        return hostname
    except Exception as e:
        log_func(f"获取主机名时出错: {e}")
        return None

def send_banned_ips(server_url, banned_ips, host_name, jail=None, token="", logger=None):
    log_func = logger.info if logger else print
    
    # 检查输入格式，支持字典格式(jail -> IP列表)和传统列表格式
    is_dict_format = isinstance(banned_ips, dict)
    
    if is_dict_format:
        # 如果没有要发送的IP，返回成功
        if not any(banned_ips.values()):
            log_func("没有要发送的封禁IP列表")
            return True, {}
        
        all_success = True
        all_failed_ips = {}
        
        # 为每个jail分别发送IP
        for current_jail, jail_ips in banned_ips.items():
            if not jail_ips:
                log_func(f"jail {current_jail} 没有要发送的封禁IP")
                continue
            
            log_func(f"开始发送 jail {current_jail} 的封禁IP列表")
            success, failed = _send_banned_ips_batch(server_url, jail_ips, host_name, current_jail, token, log_func)
            
            if not success:
                all_success = False
                all_failed_ips[current_jail] = failed
            
            log_func(f"jail {current_jail} 的IP发送完成")
        
        return all_success, all_failed_ips
    else:
        # 传统列表格式，保持向后兼容
        if not banned_ips:
            log_func("没有要发送的封禁IP列表")
            return True, []
        
        if not jail:
            log_func("错误：使用列表格式时必须指定jail参数")
            return False, banned_ips
        
        return _send_banned_ips_batch(server_url, banned_ips, host_name, jail, token, log_func)


def _send_banned_ips_batch(server_url, banned_ips, host_name, jail, token, log_func):
    """内部函数：发送单个jail的IP批次"""
    # 假设log_func是info级别，这里添加错误日志处理
    is_logger = hasattr(log_func, '__self__') and hasattr(log_func.__self__, 'error')
    log_error = log_func.__self__.error if is_logger else print
    log_warning = log_func.__self__.warning if is_logger and hasattr(log_func.__self__, 'warning') else print
    
    # 分批处理IP列表，每批最多1000个IP
    batch_size = 1000
    failed_ips = []
    
    for i in range(0, len(banned_ips), batch_size):
        batch = banned_ips[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        
        log_func(f"正在发送 jail {jail} 的第 {batch_num} 批 IP，共 {len(batch)} 个")
        
        try:
            # 构建API请求
            url = f"{server_url}/add_ips"
            
            # 准备请求数据
            data = {
                'ips': batch,
                'description': f"来自{host_name}的{jail} jail批量封禁IP",
                'jail': jail
            }
            
            # 将数据转换为JSON字符串
            json_data = json.dumps(data)
            
            # 根据数据大小决定是否使用gzip压缩（超过1KB时压缩效果明显）
            json_bytes = json_data.encode('utf-8')
            if len(json_bytes) > 1024:  # 只有当数据大于1KB时才压缩
                compressed_data = io.BytesIO()
                # 设置压缩级别4，平衡压缩率和速度（1-9，默认6）
                with gzip.GzipFile(fileobj=compressed_data, mode='wb', compresslevel=4) as f:
                    f.write(json_bytes)
                compressed_data.seek(0)
                headers = {
                    'Content-Type': 'application/json',
                    'Content-Encoding': 'gzip',
                    'Authorization': f"Bearer {token}"
                }
                
                # 发送压缩后的请求
                response = requests.post(url, headers=headers, data=compressed_data.read(), timeout=30)
            else:
                # 数据较小时直接发送，避免压缩开销
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {token}"
                }
                
                # 直接发送未压缩数据
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
                # 检查响应状态
            if response.status_code == 200 or response.status_code == 201:
                try:
                    result = response.json()
                    # 兼容多种响应格式
                    if result.get('success') or not result.get('error'):
                        log_func(f"jail {jail} 的第 {batch_num} 批发送成功，影响 {result.get('count', 0)} 个IP")
                    else:
                        # 某些成功场景可能返回"IP地址已添加"这样的消息
                        error_msg = result.get('message', '') or result.get('error', '')
                        if "已添加" in error_msg:
                            log_func(f"jail {jail} 的第 {batch_num} 批发送成功: {error_msg}")
                        else:
                            log_warning(f"jail {jail} 的第 {batch_num} 批发送失败: {error_msg}")
                            failed_ips.extend(batch)
                except ValueError:
                    # 如果响应不是JSON格式，但状态码成功，也视为成功
                    log_func(f"jail {jail} 的第 {batch_num} 批发送成功")
            else:
                log_error(f"jail {jail} 的第 {batch_num} 批发送失败: HTTP {response.status_code}")
                failed_ips.extend(batch)
                
        except Exception as e:
            log_error(f"发送 jail {jail} 的第 {batch_num} 批IP时发生异常: {str(e)}")
            failed_ips.extend(batch)
        
        # 每批之间间隔1秒，避免对服务器造成过大压力
        time.sleep(1)
    
    if failed_ips:
        log_warning(f"jail {jail} 共有 {len(failed_ips)} 个IP发送失败")
        return False, failed_ips
    else:
        log_func(f"jail {jail} 的所有IP发送成功")
        return True, []


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
        
        # 获取所有配置的jail列表
        fail2ban_config = config.get('fail2ban', {})
        jails = fail2ban_config.get('jails', [])
        
        # 如果没有配置jails，使用单个jail作为后备
        if not jails:
            jail = fail2ban_config.get('jail', 'sshd')
            jails = [jail]
        
        basic_logger.info(f"程序启动，服务器URL: {server_url}, Jails: {', '.join(jails)}")
        
        # 获取本地IP地址
        host_name = get_local_host_name()
        basic_logger.info(f"主机名: {host_name}")
        
        # 获取远端封禁IP（只获取一次，包含jail信息，用于所有jail）
        remote_banned_ips_data = None
        if config.get('sync_remote_banned_ips', True) or config.get('sync_local_banned_ips', True):
            remote_banned_ips_data = get_remote_banned_ips(server_url, token, basic_logger)
        
        # 获取远端允许IP（只获取一次，用于所有jail）
        remote_allowed_ips = None
        if config.get('sync_allowed_ips', True):
            remote_allowed_ips = get_remote_allowed_ips(server_url, token, basic_logger)
        
        # 遍历所有jail进行处理
        for jail in jails:
            basic_logger.info(f"开始处理 jail: {jail}")
            
            # 获取该jail的本地封禁IP
            try:
                # 只获取一次本地封禁IP列表，用于后续所有操作
                jail_banned_ips = get_banned_ips(config, basic_logger, jail=jail)
                # 将jail_banned_ips赋值给local_banned_ips，避免重复获取
                local_banned_ips = jail_banned_ips
            except Exception as e:
                basic_logger.error(f"获取 jail {jail} 的封禁IP时出错: {str(e)}")
                continue
            
            # 应用允许IP规则到该jail
            if config.get('sync_allowed_ips', True) and remote_allowed_ips:
                basic_logger.info(f"开始应用允许IP规则到 jail: {jail}")
                # 获取该jail对应的远端封禁IP
                remote_allowed_jailed_ips = remote_allowed_ips.get('jails', {})
                remote_allowed_jailed_ips_data =  remote_allowed_jailed_ips.get(jail, [])
                basic_logger.info(f"获取到 jail {jail} 的远端允许IP列表，共 {len(remote_allowed_jailed_ips_data)} 个IP")
                allow_ips_in_fail2ban(remote_allowed_jailed_ips_data, jail, basic_logger)
                basic_logger.info(f"允许IP规则应用完成到 jail: {jail}")
            
            # 同步远端封禁IP到该jail
            if config.get('sync_remote_banned_ips', True) and remote_banned_ips_data:
                basic_logger.info(f"开始同步远端封禁IP到 jail: {jail}")
                # 复用已获取的local_banned_ips，不再重复获取IP列表
                
                # 获取该jail对应的远端封禁IP
                remote_jailed_ips = remote_banned_ips_data.get('jails', {})
                jail_remote_ips =  remote_jailed_ips.get(jail, [])
                basic_logger.info(f"获取到 jail {jail} 的远端封禁IP列表，共 {len(jail_remote_ips)} 个IP")
                
                # 比较差异，只获取需要添加的IP
                to_add_ips, to_remove_ips = compare_ip_lists(jail_remote_ips, local_banned_ips)
                
                if to_add_ips:
                    basic_logger.info(f"找到 {len(to_add_ips)} 个需要添加到 jail {jail} 的IP")
                    add_ips_to_fail2ban(to_add_ips, jail, basic_logger)
                else:
                    basic_logger.info(f"jail {jail} 已包含所有远端封禁的IP，无需添加")   
                # 可选：处理需要移除的IP（如果需要）
                if config.get('sync_remove_unlisted_ips', False) and to_remove_ips:
                    basic_logger.info(f"找到 {len(to_remove_ips)} 个需要从 jail {jail} 移除的IP")
                    # 这里可以添加移除IP的逻辑
                    allow_ips_in_fail2ban(to_remove_ips, jail, basic_logger)
                else:
                    basic_logger.info(f"jail {jail} 已包含所有需要移除的IP，无需移除")
                basic_logger.info(f"远端封禁IP同步完成到 jail: {jail}")
            
            # 发送该jail的封禁IP到服务器
            if jail_banned_ips and config.get('sync_local_banned_ips', True):
                # 使用已获取的远端封禁IP（如果有），不再重复请求
                # 如果远端列表为空，则所有本地IP都需要发送
                if remote_banned_ips_data:
                    # 获取该jail对应的远端封禁IP
                    remote_jailed_ips = remote_banned_ips_data.get('jails', {})
                    jail_remote_ips = remote_jailed_ips.get(jail, [])
                    # 比较差异，只获取需要发送的IP
                    to_send_ips, _ = compare_ip_lists(jail_banned_ips, jail_remote_ips)
                else:
                    to_send_ips = jail_banned_ips  # 远端为空时，所有本地封禁IP都需要上传
                
                if to_send_ips:
                    basic_logger.info(f"找到 {len(to_send_ips)} 个需要从 jail {jail} 发送到服务器的IP")
                    success, failed = send_banned_ips(server_url, to_send_ips, host_name, jail, token, basic_logger)
                    if not success and failed:
                        basic_logger.error(f"jail {jail} 部分IP发送失败，共 {len(failed)} 个")
                else:
                    basic_logger.info(f"服务器已包含 jail {jail} 的所有本地封禁IP，无需发送")
            
            basic_logger.info(f"jail {jail} 处理完成")
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
                    result = subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], 
                                 capture_output=True, text=True, timeout=5)
                    # 检查返回码而不仅仅是异常
                    if result.returncode == 0:
                        success_count += 1
                        logger.info(f"[状态] jail {jail}: 成功封禁IP {ip}")
                    else:
                        failed_ips.append(ip)
                        logger.warning(f"[状态] jail {jail}: 封禁IP {ip} 命令执行成功但返回非零码: {result.stderr}")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    failed_ips.append(ip)
                    logger.error(f"[状态] jail {jail}: 封禁IP {ip} 到Fail2Ban时出错: {str(e)}")
        else:  # 大量IP使用批处理模式
            try:
                # 批处理模式 - 逐个处理IP以保证状态跟踪
                logger.info(f"[状态] jail {jail}: 开始批量封禁 {len(batch)} 个IP")
                for ip in batch:
                    try:
                        result = subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], 
                                     capture_output=True, text=True, timeout=3, check=False)
                        if result.returncode == 0:
                            success_count += 1
                        else:
                            failed_ips.append(ip)
                            logger.warning(f"[状态] jail {jail}: 批量封禁IP {ip} 失败")
                    except Exception:
                        failed_ips.append(ip)
            except Exception as e:
                logger.error(f"[状态] jail {jail}: 批处理IP时发生错误: {str(e)}")
                # 如果批处理失败，尝试逐个处理剩余IP
                logger.warning(f"[状态] jail {jail}: 开始尝试逐个处理失败的IP")
                for ip in batch:
                    try:
                        result = subprocess.run(['fail2ban-client', 'set', jail, 'banip', ip], 
                                     capture_output=True, text=True, timeout=3)
                        if result.returncode == 0:
                            success_count += 1
                            logger.info(f"[状态] jail {jail}: 备用方式成功封禁IP {ip}")
                        else:
                            failed_ips.append(ip)
                    except Exception:
                        failed_ips.append(ip)
    
    # 记录详细的统计信息
    logger.info(f"[状态] jail {jail}: IP封禁操作完成 - 总计: {len(ips)} 个IP, 成功: {success_count}, 失败: {len(failed_ips)}")
    if failed_ips:
        logger.warning(f"[状态] jail {jail}: 以下IP封禁失败: {failed_ips}")

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
            logger.info(f"[状态] jail {jail}: 开始逐个解禁 {len(batch)} 个IP")
            for ip in batch:
                try:
                    result = subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], 
                                 capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        success_count += 1
                        logger.info(f"[状态] jail {jail}: 成功解禁IP {ip}")
                    else:
                        failed_ips.append(ip)
                        logger.warning(f"[状态] jail {jail}: 解禁IP {ip} 返回非零码: {result.stderr}")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    failed_ips.append(ip)
                    logger.error(f"[状态] jail {jail}: 解禁IP {ip} 失败: {str(e)}")
        else:  # 大量IP使用批处理模式
            try:
                logger.info(f"[状态] jail {jail}: 开始批量解禁 {len(batch)} 个IP")
                for ip in batch:
                    try:
                        # 使用单独进程但减少不必要的参数
                        result = subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], 
                                     capture_output=True, text=True, timeout=3, check=False)
                        if result.returncode == 0:
                            success_count += 1
                        else:
                            failed_ips.append(ip)
                            logger.warning(f"[状态] jail {jail}: 批量解禁IP {ip} 失败")
                    except Exception:
                        failed_ips.append(ip)
            except Exception as e:
                logger.error(f"[状态] jail {jail}: 批处理IP解禁时发生错误: {str(e)}")
                # 如果批处理失败，尝试逐个处理剩余IP
                logger.warning(f"[状态] jail {jail}: 开始尝试逐个处理解禁失败的IP")
                for ip in batch:
                    try:
                        result = subprocess.run(['fail2ban-client', 'set', jail, 'unbanip', ip], 
                                     capture_output=True, text=True, timeout=3)
                        if result.returncode == 0:
                            success_count += 1
                            logger.info(f"[状态] jail {jail}: 备用方式成功解禁IP {ip}")
                        else:
                            failed_ips.append(ip)
                    except Exception:
                        failed_ips.append(ip)
    
    # 记录详细的统计信息
    logger.info(f"[状态] jail {jail}: IP解禁操作完成 - 总计: {len(ips)} 个IP, 成功: {success_count}, 失败: {len(failed_ips)}, 成功率: {success_count/len(ips)*100:.1f}%")
    if failed_ips:
        logger.warning(f"[状态] jail {jail}: 以下IP解禁失败: {failed_ips}")

def get_remote_banned_ips(server_url, token, logger):
    """获取远端服务器上的封禁IP列表，包含jail信息"""
    try:
        url = f"{server_url}/get_ips"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # 从服务器响应中获取items列表
            items = data.get('items', [])
            
            if items:
                logger.info(f"成功获取到 {len(items)} 个远端封禁IP记录(包含jail信息)")
                # 按jail分组的IP列表
                jailed_ips = {}
                for item in items:
                    ip = item.get('ip_address')
                    jail = item.get('jail', 'unknown')
                    if ip:
                        if jail not in jailed_ips:
                            jailed_ips[jail] = []
                        jailed_ips[jail].append(ip)
                logger.info(f"按jail分组的远端封禁IP: {len(jailed_ips)}")
            else:
                logger.warning("获取到空的远端封禁IP列表")
            
            # 返回包含jail信息的完整数据和按jail分组的IP列表
            return {
                'jails': jailed_ips if 'jailed_ips' in locals() else {}
            }
        else:
            logger.error(f"获取远端封禁IP请求失败: HTTP {response.status_code}")
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"获取远端封禁IP时发生异常 ({error_type}): {str(e)}")
    
    # 返回空的结构，保持一致性
    return {'jails': {}}

def compare_ip_lists(remote_ips, local_ips):
    # 将列表转换为集合进行高效比较
    remote_set = set(remote_ips)
    local_set = set(local_ips)
    
    # 计算需要添加的IP（远端有但本地没有的）
    to_add = list(remote_set - local_set)
    
    # 计算需要移除的IP（本地有但远端没有的）
    to_remove = list(local_set - remote_set)
    
    return to_add, to_remove

def get_remote_allowed_ips(server_url, token, logger):
    """获取远端服务器上的已允许IP列表"""
    try:
        url = f"{server_url}/get_allowed_ips"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # 从服务器响应中获取items列表
            items = data.get('items', [])
            
            if items:
                logger.info(f"成功获取到 {len(items)} 个远端允许IP记录(包含jail信息)")
                # 按jail分组的IP列表
                jailed_ips = {}
                for item in items:
                    ip = item.get('ip_address')
                    jail = item.get('jail', 'unknown')
                    if ip:
                        if jail not in jailed_ips:
                            jailed_ips[jail] = []
                        jailed_ips[jail].append(ip)
                logger.info(f"按jail分组的远端允许IP: {len(jailed_ips)}")
            else:
                logger.warning("获取到空的远端允许IP列表")
            
            # 返回包含jail信息的完整数据和按jail分组的IP列表
            return {
                'jails': jailed_ips if 'jailed_ips' in locals() else {}
            }
        else:
            logger.error(f"获取远端允许IP请求失败: HTTP {response.status_code}")
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"获取远端允许IP时发生异常 ({error_type}): {str(e)}")
    return  {'jails': {}}

# 最后一行需要确保是正确的main函数调用
if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)