#!/usr/bin/env python3
import requests
import json

# 配置
SERVER_URL = 'http://localhost:5000'
TOKEN = 'test_token_123'

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json',
    'X-Forwarded-For': '192.168.0.1'
}

def test_add_ips():
    """测试添加IP功能"""
    print("=== 测试添加IP功能 ===")
    data = {
        "ips": ["192.168.100.1", "192.168.100.2"],
        "description": "测试IP",
        "reported_by": "test_script"
    }
    
    response = requests.post(f'{SERVER_URL}/add_ips', headers=headers, json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    return response.json()

def test_get_blocked_ips():
    """测试获取被封禁IP列表"""
    print("\n=== 测试获取被封禁IP列表 ===")
    response = requests.get(f'{SERVER_URL}/get_ips', headers=headers)
    print(f"状态码: {response.status_code}")
    ips = response.json()
    print(f"被封禁IP数量: {len(ips)}")
    for ip in ips:
        print(f"- {ip['ip_address']} (状态: {ip['status']}, 封禁至: {ip['blocked_until']})")
    return ips

def test_allow_ip(ip):
    """测试放行IP功能"""
    print(f"\n=== 测试放行IP: {ip} ===")
    data = {
        "ip": ip
    }
    
    response = requests.post(f'{SERVER_URL}/allow_ip', headers=headers, json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    return response.json()

def test_get_allowed_ips():
    """测试获取允许IP列表"""
    print("\n=== 测试获取允许IP列表 ===")
    response = requests.get(f'{SERVER_URL}/get_allowed_ips', headers=headers)
    print(f"状态码: {response.status_code}")
    ips = response.json()
    print(f"允许IP数量: {len(ips)}")
    for ip in ips:
        print(f"- {ip['ip_address']} (状态: {ip['status']}, 允许时间: {ip['allowed_since']})")
    return ips

def main():
    # 步骤1: 添加IP到封禁列表
    add_result = test_add_ips()
    
    if 'added_ips' not in add_result:
        print("\n❌ 添加IP失败，无法继续测试")
        return
    
    # 步骤2: 查看被封禁的IP列表
    blocked_ips = test_get_blocked_ips()
    
    if not blocked_ips:
        print("\n❌ 没有找到被封禁的IP，无法继续测试")
        return
    
    # 步骤3: 选择一个IP进行放行
    ip_to_allow = blocked_ips[0]['ip_address']
    allow_result = test_allow_ip(ip_to_allow)
    
    # 步骤4: 再次查看被封禁的IP列表，确认该IP已被移除
    print("\n=== 再次查看被封禁IP列表，确认IP已被放行 ===")
    blocked_ips_after = test_get_blocked_ips()
    
    # 步骤5: 查看允许的IP列表，确认该IP已被添加
    allowed_ips = test_get_allowed_ips()
    
    # 检查IP是否成功从blocked移到allowed
    ip_in_blocked = any(ip['ip_address'] == ip_to_allow for ip in blocked_ips_after)
    ip_in_allowed = any(ip['ip_address'] == ip_to_allow for ip in allowed_ips)
    
    print("\n=== 测试结果 ===")
    if not ip_in_blocked and ip_in_allowed:
        print(f"✅ IP {ip_to_allow} 成功从封禁列表移至允许列表")
        print("✅ 放行IP功能测试通过！")
    else:
        print(f"❌ IP {ip_to_allow} 状态不正确")
        print(f"   - 在封禁列表中: {ip_in_blocked}")
        print(f"   - 在允许列表中: {ip_in_allowed}")

if __name__ == "__main__":
    main()
