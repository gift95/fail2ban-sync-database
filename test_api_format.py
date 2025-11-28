#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试API响应格式

这个脚本用于测试Fail2BanSync API的响应格式，以便正确解析IP列表
"""

import requests
import json

# 服务器配置
SERVER_URL = "http://127.0.0.1:5000"
API_GET_IPS = f"{SERVER_URL}/get_ips"  # 获取所有IP列表
API_GET_ALLOWED_IPS = f"{SERVER_URL}/get_allowed_ips"  # 获取允许的IP列表
API_GET_KNOWN_IPS = f"{SERVER_URL}/get_known_ips"  # 获取已知的IP列表

# API测试凭证
API_TOKEN = "test_token_123"

def test_api_endpoint(url, name):
    """测试特定API端点的响应格式"""
    print(f"\n测试 {name} API...")
    print(f"URL: {url}")
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        # 尝试解析JSON响应
        try:
            data = response.json()
            print(f"响应类型: {type(data).__name__}")
            print("响应内容:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        except Exception as e:
            print(f"JSON解析错误: {e}")
            print("原始响应内容:")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"请求错误: {e}")
        return None

def main():
    """主测试函数"""
    print("=== Fail2BanSync API响应格式测试 ===")
    
    # 测试获取所有IP列表API
    all_ips_data = test_api_endpoint(API_GET_IPS, "获取所有IP列表")
    
    # 测试允许IP列表API
    allowed_ips_data = test_api_endpoint(API_GET_ALLOWED_IPS, "获取允许IP列表")
    
    # 测试已知IP列表API
    known_ips_data = test_api_endpoint(API_GET_KNOWN_IPS, "获取已知IP列表")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()
