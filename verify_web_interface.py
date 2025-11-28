#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证Web界面IP放行功能

这个脚本使用API直接验证IP状态变化，不依赖于HTML内容检查
"""

import requests
import time

# 服务器配置
SERVER_URL = "http://127.0.0.1:5000"
LOGIN_URL = f"{SERVER_URL}/login"
DASHBOARD_URL = f"{SERVER_URL}/dashboard"
WEB_ALLOW_IP_URL = lambda ip: f"{SERVER_URL}/web_allow_ip/{ip}"
API_ADD_IP = f"{SERVER_URL}/add_ips"
API_GET_IPS = f"{SERVER_URL}/get_ips"  # 获取所有IP列表（包含状态信息）
API_GET_ALLOWED_IPS = f"{SERVER_URL}/get_allowed_ips"  # 获取允许的IP列表

# 登录凭证
USERNAME = "admin"
PASSWORD = "admin123"

# API测试凭证
API_TOKEN = "test_token_123"

def test_api_add_blocked_ip():
    """使用API添加一个被封禁的IP用于测试"""
    print("1. 测试API添加封禁IP...")
    
    # 测试IP地址
    test_ip = "192.168.200.200"
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "ips": [test_ip],
        "description": "测试IP - 用于Web界面测试",
        "source": "test_script"
    }
    
    try:
        response = requests.post(API_ADD_IP, json=data, headers=headers)
        if response.status_code in [200, 201]:
            print(f"   ✓ 成功添加封禁IP: {test_ip}")
            print(f"   ✓ API响应: {response.text}")
            return test_ip
        else:
            print(f"   ✗ 添加封禁IP失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"   ✗ 添加封禁IP时发生错误: {e}")
        return None

def get_ip_status(ip):
    """获取IP的当前状态"""
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    # 检查所有可能的IP状态列表
    status_endpoints = {
        'blocked': API_GET_IPS,         # /get_ips 返回封禁列表
        'allowed': API_GET_ALLOWED_IPS  # /get_allowed_ips 返回允许列表
    }
    
    # 检查所有状态列表
    for status, endpoint in status_endpoints.items():
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                for ip_data in data:
                    if isinstance(ip_data, dict) and ip_data.get('ip_address') == ip:
                        return status
    
    # 如果以上都没有找到，检查已知IP列表
    response = requests.get(f"{SERVER_URL}/get_known_ips", headers=headers)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            for ip_data in data:
                if isinstance(ip_data, dict) and ip_data.get('ip_address') == ip:
                    return 'known'
    
    return 'unknown'

def test_web_login():
    """测试Web界面登录功能"""
    print("\n2. 测试Web界面登录...")
    
    # 创建会话
    session = requests.Session()
    
    try:
        # 获取登录页面，可能需要获取cookies或CSRF令牌
        response = session.get(LOGIN_URL)
        if response.status_code != 200:
            print(f"   ✗ 获取登录页面失败: {response.status_code}")
            return None
        
        # 构建登录表单数据
        login_data = {
            "username": USERNAME,
            "password": PASSWORD
        }
        
        # 发送登录请求，允许重定向
        response = session.post(LOGIN_URL, data=login_data, allow_redirects=True)
        
        # 检查是否成功登录到dashboard
        if "dashboard" in response.url:
            print(f"   ✓ 登录成功！")
            return session
        else:
            print(f"   ✗ 登录失败: 最终URL: {response.url}")
            return None
    except Exception as e:
        print(f"   ✗ 登录时发生错误: {e}")
        return None

def test_web_allow_ip(session, test_ip):
    """测试Web界面手动放行IP功能"""
    print("\n4. 测试Web界面手动放行IP...")
    
    # 先检查IP当前状态
    initial_status = get_ip_status(test_ip)
    print(f"   ✓ IP初始状态: {initial_status}")
    
    if initial_status != 'blocked':
        print(f"   ✗ IP当前不是封禁状态，无法测试放行功能")
        return False
    
    try:
        # 发送POST请求放行IP，允许重定向
        response = session.post(WEB_ALLOW_IP_URL(test_ip), allow_redirects=True)
        
        # 打印请求详情用于调试
        print(f"   放行请求状态码: {response.status_code}")
        print(f"   最终URL: {response.url}")
        
        # 检查是否成功重定向到dashboard
        if "dashboard" in response.url:
            print(f"   ✓ 成功提交放行请求并重定向到dashboard")
            
            # 等待片刻，确保数据库更新完成
            time.sleep(1)
            
            # 检查IP状态是否已更新
            new_status = get_ip_status(test_ip)
            print(f"   ✓ IP更新后的状态: {new_status}")
            
            if new_status == 'allowed':
                print(f"   ✓ IP {test_ip} 成功从封禁状态(blocked)更新为放行状态(allowed)")
                return True
            else:
                print(f"   ✗ IP状态未如预期更新，当前状态: {new_status}")
                return False
        else:
            print(f"   ✗ 放行IP请求失败: 最终URL不包含dashboard")
            return False
    except Exception as e:
        print(f"   ✗ 放行IP时发生错误: {e}")
        return False

def main():
    """主验证函数"""
    print("=== Fail2BanSync Web界面验证 ===")
    
    # 步骤1: 添加测试IP
    test_ip = test_api_add_blocked_ip()
    if not test_ip:
        print("\n验证失败: 无法添加测试IP")
        return False
    
    # 等待几秒钟，确保IP被正确添加到数据库
    time.sleep(2)
    
    # 步骤2: 测试登录
    session = test_web_login()
    if not session:
        print("\n验证失败: 无法登录到Web界面")
        return False
    
    # 步骤3: 测试IP放行功能
    if not test_web_allow_ip(session, test_ip):
        print("\n验证失败: IP放行功能异常")
        return False
    
    # 验证完成
    print("\n=== 所有验证通过！Web界面功能正常工作 ===")
    print(f"\nWeb界面访问信息:")
    print(f"  地址: {SERVER_URL}")
    print(f"  用户名: {USERNAME}")
    print(f"  密码: {PASSWORD}")
    return True

if __name__ == "__main__":
    main()
