#!/usr/bin/env python3
"""
诊断并修复AI API网络连接问题
Diagnose and fix AI API network connectivity issues
"""

import asyncio
import httpx
import requests
import json
import socket
import ssl
from urllib.parse import urlparse

def test_dns_resolution():
    """测试DNS解析"""
    print("=== DNS解析测试 ===")
    try:
        hostname = "api.siliconflow.cn"
        ip = socket.gethostbyname(hostname)
        print(f"✅ DNS解析成功: {hostname} -> {ip}")
        return ip
    except Exception as e:
        print(f"❌ DNS解析失败: {e}")
        return None

def test_tcp_connection(ip):
    """测试TCP连接"""
    print("=== TCP连接测试 ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((ip, 443))
        sock.close()
        
        if result == 0:
            print("✅ TCP连接成功")
            return True
        else:
            print(f"❌ TCP连接失败: {result}")
            return False
    except Exception as e:
        print(f"❌ TCP连接异常: {e}")
        return False

def test_ssl_connection():
    """测试SSL连接"""
    print("=== SSL连接测试 ===")
    try:
        hostname = "api.siliconflow.cn"
        context = ssl.create_default_context()
        
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                print(f"✅ SSL连接成功: {ssock.version()}")
                return True
    except Exception as e:
        print(f"❌ SSL连接失败: {e}")
        return False

def test_requests_with_different_configs():
    """测试不同配置的requests请求"""
    print("=== requests库配置测试 ===")
    
    api_key = "sk-omusfjrjuzhvqjmteijszqyqahtvhbcbwfyfdkucvzbeynve"
    url = "https://api.siliconflow.cn/v1/chat/completions"
    
    payload = {
        "model": "Pro/deepseek-ai/DeepSeek-V3",
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 测试不同的配置
    configs = [
        {"timeout": 30, "verify": True, "name": "默认SSL验证"},
        {"timeout": 30, "verify": False, "name": "跳过SSL验证"},
        {"timeout": 60, "verify": False, "name": "长超时+跳过SSL"},
    ]
    
    for config in configs:
        print(f"\n--- 测试配置: {config['name']} ---")
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config['timeout'],
                verify=config['verify']
            )
            
            print(f"✅ 成功: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"响应: {result['choices'][0]['message']['content']}")
                return True
                
        except requests.exceptions.Timeout:
            print("❌ 超时")
        except requests.exceptions.SSLError as e:
            print(f"❌ SSL错误: {e}")
        except Exception as e:
            print(f"❌ 其他错误: {e}")
    
    return False

async def test_httpx_with_different_configs():
    """测试不同配置的httpx请求"""
    print("\n=== httpx库配置测试 ===")
    
    api_key = "sk-omusfjrjuzhvqjmteijszqyqahtvhbcbwfyfdkucvzbeynve"
    url = "https://api.siliconflow.cn/v1/chat/completions"
    
    payload = {
        "model": "Pro/deepseek-ai/DeepSeek-V3",
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 测试不同的配置
    configs = [
        {
            "timeout": httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=30.0),
            "verify": True,
            "name": "短超时+SSL验证"
        },
        {
            "timeout": httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=90.0),
            "verify": False,
            "name": "长超时+跳过SSL"
        },
        {
            "timeout": 120.0,
            "verify": False,
            "http2": True,
            "name": "超长超时+HTTP2"
        }
    ]
    
    for config in configs:
        print(f"\n--- 测试配置: {config['name']} ---")
        try:
            async with httpx.AsyncClient(**config) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                print(f"✅ 成功: {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    print(f"响应: {result['choices'][0]['message']['content']}")
                    return True
                    
        except httpx.TimeoutException:
            print("❌ 超时")
        except httpx.ConnectError as e:
            print(f"❌ 连接错误: {e}")
        except Exception as e:
            print(f"❌ 其他错误: {e}")
    
    return False

def test_proxy_detection():
    """检测是否有代理设置"""
    print("\n=== 代理设置检测 ===")
    
    import os
    
    proxy_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']
    found_proxy = False
    
    for var in proxy_vars:
        value = os.environ.get(var)
        if value:
            print(f"发现代理设置: {var}={value}")
            found_proxy = True
    
    if not found_proxy:
        print("未发现环境变量中的代理设置")
    
    return found_proxy

async def main():
    """主函数"""
    print("开始诊断AI API网络连接问题...\n")
    
    # 1. DNS解析测试
    ip = test_dns_resolution()
    if not ip:
        return False
    
    # 2. TCP连接测试
    tcp_ok = test_tcp_connection(ip)
    if not tcp_ok:
        return False
    
    # 3. SSL连接测试
    ssl_ok = test_ssl_connection()
    if not ssl_ok:
        print("SSL可能有问题，但继续测试...")
    
    # 4. 代理检测
    has_proxy = test_proxy_detection()
    
    # 5. requests库测试
    requests_ok = test_requests_with_different_configs()
    
    # 6. httpx库测试
    httpx_ok = await test_httpx_with_different_configs()
    
    print(f"\n=== 诊断总结 ===")
    print(f"DNS解析: {'✅' if ip else '❌'}")
    print(f"TCP连接: {'✅' if tcp_ok else '❌'}")
    print(f"SSL连接: {'✅' if ssl_ok else '❌'}")
    print(f"代理设置: {'有' if has_proxy else '无'}")
    print(f"requests成功: {'✅' if requests_ok else '❌'}")
    print(f"httpx成功: {'✅' if httpx_ok else '❌'}")
    
    if requests_ok or httpx_ok:
        print("\n✅ 找到了可用的配置！")
        return True
    else:
        print("\n❌ 所有配置都失败，可能需要检查网络环境")
        return False

if __name__ == "__main__":
    asyncio.run(main())