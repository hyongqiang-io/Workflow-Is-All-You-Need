#!/usr/bin/env python3
"""
API端点测试脚本
"""

import asyncio
import aiohttp
import json


async def test_register_api():
    """测试注册API端点"""
    print("=== 测试注册API端点 ===")
    
    url = "http://localhost:8000/api/auth/register"
    data = {
        "username": "apitest123",
        "email": "apitest123@example.com", 
        "password": "password123"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                print(f"状态码: {response.status}")
                content = await response.text()
                print(f"响应内容: {content}")
                
                if response.status == 201:
                    print("✅ 注册API正常")
                    return True
                else:
                    print("❌ 注册API异常")
                    return False
    except Exception as e:
        print(f"❌ 注册API连接失败: {e}")
        return False


async def test_login_api():
    """测试登录API端点"""
    print("\n=== 测试登录API端点 ===")
    
    url = "http://localhost:8000/api/auth/login"
    data = {
        "username_or_email": "apitest123",
        "password": "password123"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                print(f"状态码: {response.status}")
                content = await response.text()
                print(f"响应内容: {content}")
                
                if response.status == 200:
                    print("✅ 登录API正常")
                    return True
                else:
                    print("❌ 登录API异常")
                    return False
    except Exception as e:
        print(f"❌ 登录API连接失败: {e}")
        return False


async def test_health_endpoint():
    """测试健康检查端点"""
    print("=== 测试健康检查端点 ===")
    
    url = "http://localhost:8000/health"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f"状态码: {response.status}")
                content = await response.text()
                print(f"响应内容: {content}")
                
                if response.status == 200:
                    print("✅ 服务器正常运行")
                    return True
                else:
                    print("❌ 服务器异常")
                    return False
    except Exception as e:
        print(f"❌ 无法连接到服务器: {e}")
        print("请确保后端服务器正在运行: python main.py")
        return False


async def main():
    """主测试函数"""
    print("开始API端点测试...\n")
    
    # 首先测试服务器是否运行
    if not await test_health_endpoint():
        print("\n❌ 请先启动后端服务器:")
        print("   /mnt/d/anaconda3/envs/fornew/python.exe main.py")
        return
    
    # 测试注册API
    register_success = await test_register_api()
    
    if register_success:
        # 测试登录API
        await test_login_api()
    
    print("\nAPI测试完成！")


if __name__ == "__main__":
    # 安装aiohttp如果没有的话
    try:
        import aiohttp
    except ImportError:
        print("需要安装aiohttp库:")
        print("pip install aiohttp")
        exit(1)
    
    asyncio.run(main())