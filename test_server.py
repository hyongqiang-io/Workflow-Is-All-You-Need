#!/usr/bin/env python3
"""
简单的服务器测试脚本
Simple server test script
"""

import requests
import time
import sys

def test_server():
    base_url = "http://localhost:8001/api/processors"
    
    print("测试服务器连接...")
    
    # 测试基本连接
    try:
        response = requests.get(f"{base_url}/test-no-auth", timeout=5)
        print(f"服务器连接成功: {response.status_code}")
        print(f"响应: {response.json()}")
    except Exception as e:
        print(f"服务器连接失败: {e}")
        return False
    
    # 测试删除路由
    test_id = "04939706-3a8d-46f1-a4f5-79ca6a6f2511"
    
    try:
        response = requests.delete(f"{base_url}/test-delete-simple/{test_id}", timeout=5)
        print(f"测试删除路由成功: {response.status_code}")
        print(f"响应: {response.json()}")
    except Exception as e:
        print(f"测试删除路由失败: {e}")
        return False
    
    # 测试实际删除路由（需要认证）
    try:
        response = requests.delete(f"{base_url}/delete/{test_id}", timeout=5)
        print(f"删除路由状态: {response.status_code}")
        if response.status_code == 401:
            print("删除路由存在，需要认证")
        elif response.status_code == 404:
            print("删除路由不存在")
        else:
            print(f"响应: {response.text}")
    except Exception as e:
        print(f"删除路由测试失败: {e}")
    
    return True

if __name__ == "__main__":
    test_server()