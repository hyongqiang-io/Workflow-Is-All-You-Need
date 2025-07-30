#!/usr/bin/env python3
"""
简单的认证测试脚本
"""

import asyncio
import sys
from loguru import logger

# 添加项目路径
sys.path.insert(0, '.')

from workflow_framework.services.auth_service import AuthService
from workflow_framework.models.user import UserCreate, UserLogin


async def test_register():
    """测试用户注册"""
    print("=== 测试用户注册 ===")
    
    auth_service = AuthService()
    
    # 创建测试用户数据
    user_data = UserCreate(
        username="testuser123",
        email="testuser123@example.com",
        password="password123"
    )
    
    try:
        result = await auth_service.register_user(user_data)
        print("注册成功！")
        print("用户ID:", result.user_id)
        print("用户名:", result.username)
        print("邮箱:", result.email)
        return True
    except Exception as e:
        print("注册失败:", str(e))
        logger.error(f"注册失败详细信息: {e}")
        return False


async def test_login():
    """测试用户登录"""
    print("\n=== 测试用户登录 ===")
    
    auth_service = AuthService()
    
    # 创建登录数据
    login_data = UserLogin(
        username_or_email="testuser123",
        password="password123"
    )
    
    try:
        result = await auth_service.authenticate_user(login_data)
        print("登录成功！")
        print("访问令牌:", result.access_token[:20] + "...")
        print("令牌类型:", result.token_type)
        return True
    except Exception as e:
        print("登录失败:", str(e))
        logger.error(f"登录失败详细信息: {e}")
        return False


async def main():
    """主测试函数"""
    print("开始认证功能测试...\n")
    
    # 测试注册
    register_success = await test_register()
    
    if register_success:
        # 测试登录
        await test_login()
    
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(main())