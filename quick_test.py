#!/usr/bin/env python3
"""
快速测试修复后的认证系统
"""

import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8080"

async def test_auth_system():
    """测试认证系统"""
    async with httpx.AsyncClient() as client:
        try:
            print("=== 认证系统测试 ===")
            print()
            
            # 1. 健康检查
            print("1. 健康检查...")
            response = await client.get(f"{BASE_URL}/health")
            print(f"   状态: {response.status_code}")
            if response.status_code == 200:
                print("   [OK] 服务器运行正常")
            else:
                print("   [ERROR] 服务器无法访问")
                return
            print()
            
            # 2. 用户登录测试
            print("2. 用户登录测试...")
            login_data = {
                "username_or_email": "testuser",
                "password": "testpass123"
            }
            
            response = await client.post(f"{BASE_URL}/api/auth/login", json=login_data)
            print(f"   状态: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                token = result.get("access_token")
                print("   [OK] 登录成功")
                print(f"   令牌: {token[:50]}...")
                
                # 3. 获取用户信息测试
                print()
                print("3. 获取用户信息...")
                headers = {"Authorization": f"Bearer {token}"}
                response = await client.get(f"{BASE_URL}/api/auth/me", headers=headers)
                print(f"   状态: {response.status_code}")
                
                if response.status_code == 200:
                    user_info = response.json()
                    print("   [OK] 获取用户信息成功")
                    print(f"   用户: {user_info.get('username')}")
                    print(f"   邮箱: {user_info.get('email')}")
                else:
                    print("   [ERROR] 获取用户信息失败")
                    print(f"   错误: {response.text}")
                    
            else:
                print("   [ERROR] 登录失败")
                print(f"   错误: {response.text}")
            
            print()
            print("=== 测试完成 ===")
            
        except Exception as e:
            print(f"测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_auth_system())