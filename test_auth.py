"""
用户认证功能测试脚本
Authentication Test Script
"""

import asyncio
import httpx
import json
from loguru import logger

# 测试配置
BASE_URL = "http://127.0.0.1:8080"
API_BASE = f"{BASE_URL}/api"

# 测试用户数据
TEST_USER = {
    "username": "testuser",
    "email": "test@example.com", 
    "password": "testpass123",
    "role": "user",
    "description": "测试用户账户"
}

async def test_health_check():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}")
            return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False

async def test_user_registration():
    """测试用户注册"""
    print("\n=== 测试用户注册 ===")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/auth/register",
                json=TEST_USER,
                headers={"Content-Type": "application/json"}
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 201:
                print("[OK] 用户注册成功")
                return True
            elif response.status_code == 409:
                print("[INFO] 用户已存在，跳过注册")
                return True
            else:
                print("[ERROR] 用户注册失败")
                return False
                
    except Exception as e:
        print(f"注册测试异常: {e}")
        return False

async def test_user_login():
    """测试用户登录"""
    print("\n=== 测试用户登录 ===")
    try:
        login_data = {
            "username_or_email": TEST_USER["username"],
            "password": TEST_USER["password"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("data", {}).get("token"):
                    token = result["data"]["token"]["access_token"]
                    print("✅ 用户登录成功")
                    print(f"访问令牌: {token[:50]}...")
                    return token
                else:
                    print("❌ 登录响应格式错误")
                    return None
            else:
                print("❌ 用户登录失败")
                return None
                
    except Exception as e:
        print(f"登录测试异常: {e}")
        return None

async def test_get_current_user(token):
    """测试获取当前用户信息"""
    print("\n=== 测试获取当前用户信息 ===")
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/auth/me",
                headers=headers
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200:
                print("✅ 获取用户信息成功")
                return True
            else:
                print("❌ 获取用户信息失败")
                return False
                
    except Exception as e:
        print(f"获取用户信息测试异常: {e}")
        return False

async def test_check_authentication(token):
    """测试认证状态检查"""
    print("\n=== 测试认证状态检查 ===")
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/auth/check",
                headers=headers
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200:
                print("✅ 认证状态检查成功")
                return True
            else:
                print("❌ 认证状态检查失败")
                return False
                
    except Exception as e:
        print(f"认证状态检查异常: {e}")
        return False

async def test_invalid_token():
    """测试无效令牌"""
    print("\n=== 测试无效令牌 ===")
    try:
        headers = {
            "Authorization": "Bearer invalid-token-12345",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE}/auth/me",
                headers=headers
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 401:
                print("✅ 无效令牌正确被拒绝")
                return True
            else:
                print("❌ 无效令牌未被正确处理")
                return False
                
    except Exception as e:
        print(f"无效令牌测试异常: {e}")
        return False

async def test_email_login():
    """测试邮箱登录"""
    print("\n=== 测试邮箱登录 ===")
    try:
        login_data = {
            "username_or_email": TEST_USER["email"],
            "password": TEST_USER["password"]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE}/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            print(f"状态码: {response.status_code}")
            print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
            if response.status_code == 200:
                print("✅ 邮箱登录成功")
                return True
            else:
                print("❌ 邮箱登录失败")
                return False
                
    except Exception as e:
        print(f"邮箱登录测试异常: {e}")
        return False

async def run_all_tests():
    """运行所有测试"""
    print("开始用户认证功能测试")
    print("=" * 50)
    
    results = []
    
    # 1. 健康检查
    results.append(await test_health_check())
    
    # 2. 用户注册
    results.append(await test_user_registration())
    
    # 3. 用户登录
    token = await test_user_login()
    results.append(token is not None)
    
    if token:
        # 4. 获取当前用户信息
        results.append(await test_get_current_user(token))
        
        # 5. 认证状态检查
        results.append(await test_check_authentication(token))
    else:
        results.extend([False, False])
    
    # 6. 无效令牌测试
    results.append(await test_invalid_token())
    
    # 7. 邮箱登录测试
    results.append(await test_email_login())
    
    # 输出测试结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    print("=" * 50)
    
    test_names = [
        "健康检查",
        "用户注册", 
        "用户登录",
        "获取用户信息",
        "认证状态检查",
        "无效令牌处理",
        "邮箱登录"
    ]
    
    passed = 0
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{i+1}. {name}: {status}")
        if result:
            passed += 1
    
    print("=" * 50)
    print(f"测试完成: {passed}/{len(results)} 个测试通过")
    
    if passed == len(results):
        print("🎉 所有测试均通过！用户认证功能正常工作。")
    else:
        print("⚠️ 部分测试失败，请检查服务器状态和配置。")

if __name__ == "__main__":
    print("启动认证功能测试...")
    asyncio.run(run_all_tests())