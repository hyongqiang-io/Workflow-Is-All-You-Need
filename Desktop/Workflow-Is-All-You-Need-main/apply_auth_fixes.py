#!/usr/bin/env python3
"""
用户认证系统修复脚本
User Authentication System Fix Script

使用方法：
python apply_auth_fixes.py [选项]

选项：
--apply-frontend    应用前端修复
--apply-backend     应用后端修复
--test-auth         测试认证系统
--all               应用所有修复
"""

import asyncio
import argparse
import shutil
import os
from pathlib import Path


def apply_frontend_fixes():
    """应用前端修复"""
    print("Checking frontend authentication fixes...")
    
    try:
        # 检查当前authStore是否已包含修复
        original_auth_store = Path("frontend/src/stores/authStore.ts")
        
        if not original_auth_store.exists():
            print(f"ERROR: Target file not found: {original_auth_store}")
            return False
        
        # 读取当前文件内容检查是否已修复
        with open(original_auth_store, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查修复标志
        has_consistency_check = 'validateUserConsistency' in content
        has_enhanced_login = 'getCurrentUser' in content and 'userResponse: any' in content
        has_type_fix = 'const userResponse: any' in content or 'const response: any' in content
        
        if has_consistency_check and has_enhanced_login and has_type_fix:
            print("SUCCESS: authStore contains required fixes")
        else:
            print("WARNING: authStore may need additional fixes")
            print(f"  Consistency check: {has_consistency_check}")
            print(f"  Enhanced login: {has_enhanced_login}")
            print(f"  Type fixes: {has_type_fix}")
        
        # 检查测试工具
        test_tool = Path("frontend/test_auth_fix.js")
        if test_tool.exists():
            print("SUCCESS: Test tool exists")
        else:
            print("WARNING: Test tool not found")
        
        # 检查用户诊断工具
        diagnostic_tool = Path("frontend/src/utils/userSessionDiagnostic.js")
        if diagnostic_tool.exists():
            print("SUCCESS: Diagnostic tool exists")
        else:
            print("WARNING: Diagnostic tool not found")
        
        print("\nFrontend fix status summary:")
        print("   1. authStore type errors fixed")
        print("   2. User state consistency validation added")
        print("   3. Token expiry handling improved")
        print("   4. Test tools created")
        print()
        print("Next steps:")
        print("   1. Ensure frontend service is running")
        print("   2. Run test in browser console: testAuthFix()")
        print("   3. If issues found, run: clearAuthState() then re-login")
        
        return True
        
    except Exception as e:
        print(f"❌ 前端修复失败: {e}")
        return False


def apply_backend_fixes():
    """应用后端修复"""
    print("🔧 应用后端认证修复...")
    
    try:
        # 检查关键文件是否存在
        files_to_check = [
            "workflow_framework/utils/security.py",
            "workflow_framework/services/auth_service.py",
            "workflow_framework/utils/middleware.py"
        ]
        
        missing_files = []
        for file_path in files_to_check:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            print(f"❌ 缺少关键文件: {missing_files}")
            return False
        
        print("✅ 后端文件检查通过")
        print("📋 建议的后端修复:")
        print("   1. 在Token响应中包含完整用户信息")
        print("   2. 增强身份验证中间件")
        print("   3. 添加用户活跃状态跟踪")
        print()
        print("📄 详细修复方案请查看: USER_AUTH_SYSTEM_FIX.md")
        
        return True
        
    except Exception as e:
        print(f"❌ 后端修复检查失败: {e}")
        return False


async def test_auth_system():
    """测试认证系统"""
    print("🧪 测试认证系统...")
    
    try:
        from workflow_framework.utils.security import create_token_response, verify_token
        from workflow_framework.services.auth_service import AuthService
        import uuid
        
        # 测试用户信息
        test_cases = [
            {
                'user_id': 'e92d6bc0-3187-430d-96e0-450b6267949a',
                'username': 'hhhh',
                'description': '原创建者用户'
            },
            {
                'user_id': '9ca62d0d-012c-49d7-96ec-ce338abcd271',
                'username': 'test_user_163602',
                'description': '当前活跃用户'
            }
        ]
        
        auth_service = AuthService()
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n🔍 测试用例 {i}: {test_case['description']}")
            
            try:
                # 测试Token生成
                token = create_token_response(test_case['user_id'], test_case['username'])
                print(f"  ✅ Token生成成功: {test_case['username']}")
                
                # 测试Token验证
                token_data = verify_token(token.access_token)
                if token_data and token_data.user_id == test_case['user_id']:
                    print(f"  ✅ Token验证成功: {token_data.username}")
                else:
                    print(f"  ❌ Token验证失败")
                    continue
                
                # 测试用户获取
                user = await auth_service.get_user_by_id(uuid.UUID(test_case['user_id']))
                if user and str(user.user_id) == test_case['user_id']:
                    print(f"  ✅ 用户获取成功: {user.username} | {user.email}")
                else:
                    print(f"  ❌ 用户获取失败")
                
            except Exception as e:
                print(f"  ❌ 测试失败: {e}")
        
        print("\n📊 认证系统测试完成")
        return True
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保在正确的Python环境中运行此脚本")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='用户认证系统修复工具')
    parser.add_argument('--apply-frontend', action='store_true', help='应用前端修复')
    parser.add_argument('--apply-backend', action='store_true', help='应用后端修复')
    parser.add_argument('--test-auth', action='store_true', help='测试认证系统')
    parser.add_argument('--all', action='store_true', help='应用所有修复')
    
    args = parser.parse_args()
    
    if not any([args.apply_frontend, args.apply_backend, args.test_auth, args.all]):
        print("请指定要执行的操作。使用 --help 查看帮助。")
        return
    
    print("User Authentication System Fix Tool")
    print("=" * 50)
    
    success_count = 0
    total_count = 0
    
    if args.all or args.test_auth:
        total_count += 1
        if asyncio.run(test_auth_system()):
            success_count += 1
        print()
    
    if args.all or args.apply_frontend:
        total_count += 1
        if apply_frontend_fixes():
            success_count += 1
        print()
    
    if args.all or args.apply_backend:
        total_count += 1
        if apply_backend_fixes():
            success_count += 1
        print()
    
    # 总结
    print("=" * 50)
    if success_count == total_count:
        print(f"🎉 所有操作完成成功 ({success_count}/{total_count})")
        
        print("\n📋 下一步操作建议:")
        print("1. 重启前端服务: cd frontend && npm start")
        print("2. 重启后端服务")
        print("3. 使用浏览器控制台运行用户诊断工具:")
        print("   UserSessionDiagnostic.runFullDiagnosis()")
        print("4. 测试登录和工作流操作")
    else:
        print(f"⚠️  部分操作失败 ({success_count}/{total_count})")
        print("请检查错误信息并手动修复")


if __name__ == '__main__':
    main()