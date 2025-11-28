#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Web界面的功能

这个脚本用于测试Fail2BanSync的Web界面，包括：
1. 登录功能
2. 查看封禁IP列表
3. 手动放行IP
"""

import requests
import time
import sys

# 服务器配置
SERVER_URL = "http://127.0.0.1:5000"
LOGIN_URL = f"{SERVER_URL}/login"
DASHBOARD_URL = f"{SERVER_URL}/dashboard"
API_ADD_IP = f"{SERVER_URL}/add_ips"

# 登录凭证
USERNAME = "admin"
PASSWORD = "admin123"

# API测试凭证
API_TOKEN = "test_token_123"

def test_api_add_blocked_ip():
    """使用API添加一个被封禁的IP用于测试"""
    print("\n1. 测试API添加封禁IP...")
    
    # 测试IP地址
    test_ip = "192.168.200.100"
    
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

def test_web_login():
    """测试Web界面登录功能"""
    print("\n2. 测试Web界面登录...")
    
    # 创建会话
    session = requests.Session()
    
    # 获取登录页面，获取cookie和csrf token（如果有）
    try:
        response = session.get(LOGIN_URL)
        if response.status_code != 200:
            print(f"   ✗ 获取登录页面失败: {response.status_code}")
            return None
        
        # 构建登录表单数据
        login_data = {
            "username": USERNAME,
            "password": PASSWORD
        }
        
        # 发送登录请求
        response = session.post(LOGIN_URL, data=login_data)
        
        if response.status_code == 200 and "dashboard" in response.url:
            print(f"   ✓ 登录成功！")
            return session
        elif response.status_code == 200 and "login" in response.url:
            print("   ✗ 登录失败: 用户名或密码错误")
            return None
        else:
            print(f"   ✗ 登录请求失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ✗ 登录时发生错误: {e}")
        return None

def test_web_dashboard(session, test_ip):
    """测试Web界面仪表盘功能"""
    print("\n3. 测试Web界面仪表盘...")
    
    try:
        response = session.get(DASHBOARD_URL)
        if response.status_code == 200:
            print("   ✓ 成功访问仪表盘")
            
            # 检查测试IP是否在页面中
            if test_ip in response.text:
                print(f"   ✓ 测试IP {test_ip} 显示在仪表盘上")
                return True
            else:
                print(f"   ✗ 测试IP {test_ip} 未显示在仪表盘上")
                return False
        else:
            print(f"   ✗ 访问仪表盘失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ 访问仪表盘时发生错误: {e}")
        return False

def test_web_allow_ip(session, test_ip):
    """测试Web界面手动放行IP功能"""
    print("\n4. 测试Web界面手动放行IP...")
    
    try:
        # 构建放行IP的URL
        allow_ip_url = f"{SERVER_URL}/web_allow_ip/{test_ip}"
        
        # 发送POST请求放行IP
        response = session.post(allow_ip_url)
        
        if response.status_code == 200 and "dashboard" in response.url:
            print(f"   ✓ 成功放行IP {test_ip}")
            
            # 重新获取仪表盘，检查IP状态是否已更新
            dashboard_response = session.get(DASHBOARD_URL)
            if "已成功放行" in dashboard_response.text:
                print("   ✓ 放行成功消息显示在页面上")
                return True
            else:
                print("   ✗ 放行成功消息未显示在页面上")
                return False
        else:
            print(f"   ✗ 放行IP请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ 放行IP时发生错误: {e}")
        return False

def main():
    """主测试函数"""
    print("=== Fail2BanSync Web界面测试 ===")
    
    # 步骤1: 添加测试IP
    test_ip = test_api_add_blocked_ip()
    if not test_ip:
        print("\n测试失败: 无法添加测试IP")
        sys.exit(1)
    
    # 等待几秒钟，确保IP被正确添加到数据库
    time.sleep(2)
    
    # 步骤2: 测试登录
    session = test_web_login()
    if not session:
        print("\n测试失败: 无法登录到Web界面")
        sys.exit(1)
    
    # 步骤3: 测试仪表盘
    if not test_web_dashboard(session, test_ip):
        print("\n测试失败: 仪表盘功能异常")
        sys.exit(1)
    
    # 步骤4: 测试放行IP
    if not test_web_allow_ip(session, test_ip):
        print("\n测试失败: 放行IP功能异常")
        sys.exit(1)
    
    # 测试完成
    print("\n=== 所有测试通过！Web界面功能正常工作 ===")
    print(f"\n您可以通过以下方式访问Web界面:")
    print(f"  地址: {SERVER_URL}")
    print(f"  用户名: {USERNAME}")
    print(f"  密码: {PASSWORD}")

if __name__ == "__main__":
    main()
