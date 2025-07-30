#!/usr/bin/env python3
"""
使用requests测试API端点
"""

import requests
import json


def test_health():
    """测试健康检查"""
    print("=== 测试健康检查 ===")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"连接失败: {e}")
        return False


def test_register():
    """测试注册API"""
    print("\n=== 测试注册API ===")
    
    url = "http://localhost:8000/api/auth/register"
    data = {
        "username": "webtest456",
        "email": "webtest456@example.com",
        "password": "password123"
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 201:
            print("✅ 注册成功")
            return True
        else:
            print("❌ 注册失败")
            return False
    except Exception as e:
        print(f"请求失败: {e}")
        return False


def test_login():
    """测试登录API"""
    print("\n=== 测试登录API ===")
    
    url = "http://localhost:8000/api/auth/login"
    data = {
        "username_or_email": "webtest456",
        "password": "password123"
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print("✅ 登录成功")
            return True
        else:
            print("❌ 登录失败")
            return False
    except Exception as e:
        print(f"请求失败: {e}")
        return False


def main():
    print("开始Web API测试...\n")
    
    # 测试服务器连接
    if not test_health():
        print("\n❌ 服务器未运行，请启动:")
        print("   /mnt/d/anaconda3/envs/fornew/python.exe main.py")
        return
    
    # 测试注册
    if test_register():
        # 测试登录
        test_login()
    
    print("\n测试完成！")


if __name__ == "__main__":
    main()