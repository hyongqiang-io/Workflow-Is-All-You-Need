"""
认证调试脚本
"""

import asyncio
from workflow_framework.repositories.user.user_repository import UserRepository
from workflow_framework.services.auth_service import AuthService
from workflow_framework.models.user import UserLogin

async def debug_auth():
    print("=== 调试认证问题 ===")
    
    try:
        # 测试UserRepository
        print("1. 测试UserRepository...")
        user_repo = UserRepository()
        print(f"   表名: {user_repo.table_name}")
        
        # 直接测试数据库连接
        user_by_username = await user_repo.get_user_by_username("testuser")
        print(f"   根据用户名查找: {user_by_username is not None}")
        if user_by_username:
            print(f"   用户信息: {user_by_username['username']}, {user_by_username['email']}")
        
        # 测试AuthService
        print("\n2. 测试AuthService...")
        auth_service = AuthService()
        
        login_data = UserLogin(username_or_email="testuser", password="testpass123")
        print(f"   登录数据: {login_data}")
        
        # 测试认证过程
        try:
            token = await auth_service.authenticate_user(login_data)
            print(f"   认证成功: {token.access_token[:50]}...")
        except Exception as e:
            print(f"   认证失败: {e}")
            
    except Exception as e:
        print(f"调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_auth())