#!/usr/bin/env python3
"""
用户会话修复脚本
User Session Fix Script

使用方法：
python fix_user_sessions.py [选项]

选项：
--cleanup-test-users    清理测试用户
--fix-permissions      修复权限问题  
--monitor              监控用户状态
--all                  执行所有修复
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timedelta
from workflow_framework.utils.database import db_manager


async def cleanup_test_users():
    """清理测试用户"""
    print("🧹 开始清理测试用户...")
    
    try:
        # 查找测试用户
        test_users = await db_manager.fetch_all('''
            SELECT user_id, username, created_at
            FROM "user"
            WHERE username LIKE 'test_user_%'
            AND created_at < NOW() - INTERVAL '1 day'
            AND is_deleted = FALSE
        ''')
        
        print(f"发现 {len(test_users)} 个测试用户")
        
        if test_users:
            test_user_ids = [user['user_id'] for user in test_users]
            
            # 1. 先处理这些用户创建的工作流
            workflows_updated = await db_manager.execute('''
                UPDATE workflow 
                SET is_deleted = TRUE, updated_at = NOW()
                WHERE creator_id = ANY($1) AND is_deleted = FALSE
            ''', test_user_ids)
            
            # 2. 软删除测试用户
            users_deleted = await db_manager.execute('''
                UPDATE "user" 
                SET is_deleted = TRUE, updated_at = NOW()
                WHERE user_id = ANY($1)
            ''', test_user_ids)
            
            print(f"✅ 已清理 {len(test_users)} 个测试用户")
            print(f"✅ 已清理相关工作流")
        else:
            print("✅ 没有发现需要清理的测试用户")
            
    except Exception as e:
        print(f"❌ 清理失败: {e}")


async def fix_workflow_permissions():
    """修复工作流权限问题"""
    print("🔧 开始修复工作流权限...")
    
    try:
        # 查找孤儿工作流（创建者已删除的工作流）
        orphan_workflows = await db_manager.fetch_all('''
            SELECT w.workflow_base_id, w.name, w.creator_id
            FROM workflow w
            LEFT JOIN "user" u ON w.creator_id = u.user_id
            WHERE w.is_deleted = FALSE 
            AND (u.user_id IS NULL OR u.is_deleted = TRUE)
        ''')
        
        print(f"发现 {len(orphan_workflows)} 个孤儿工作流")
        
        if orphan_workflows:
            # 找到第一个活跃的管理员用户作为新所有者
            admin_user = await db_manager.fetch_one('''
                SELECT user_id, username
                FROM "user"
                WHERE is_deleted = FALSE
                AND status = TRUE
                AND (role = 'admin' OR role IS NULL)
                ORDER BY created_at ASC
                LIMIT 1
            ''')
            
            if admin_user:
                # 转移所有权
                for workflow in orphan_workflows:
                    await db_manager.execute('''
                        UPDATE workflow
                        SET creator_id = $1, updated_at = NOW()
                        WHERE workflow_base_id = $2
                    ''', admin_user['user_id'], workflow['workflow_base_id'])
                
                print(f"✅ 已将 {len(orphan_workflows)} 个工作流转移给用户: {admin_user['username']}")
            else:
                print("❌ 未找到可用的管理员用户")
        else:
            print("✅ 没有发现孤儿工作流")
            
    except Exception as e:
        print(f"❌ 权限修复失败: {e}")


async def monitor_user_status():
    """监控用户状态"""
    print("📊 用户状态监控报告")
    print("=" * 60)
    
    try:
        # 统计用户状态
        stats = await db_manager.fetch_one('''
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_deleted = FALSE THEN 1 END) as active_users,
                COUNT(CASE WHEN username LIKE 'test_user_%' THEN 1 END) as test_users,
                COUNT(CASE WHEN updated_at > NOW() - INTERVAL '1 day' THEN 1 END) as recent_active
            FROM "user"
        ''')
        
        print(f"总用户数:     {stats['total_users']}")
        print(f"活跃用户数:   {stats['active_users']}")
        print(f"测试用户数:   {stats['test_users']}")
        print(f"24h内活跃:   {stats['recent_active']}")
        
        # 显示最近活跃的用户
        recent_users = await db_manager.fetch_all('''
            SELECT 
                username,
                user_id,
                updated_at,
                EXTRACT(EPOCH FROM (NOW() - updated_at))/3600 as hours_ago,
                CASE 
                    WHEN username LIKE 'test_user_%' THEN 'TEST'
                    ELSE 'REAL'
                END as user_type
            FROM "user"
            WHERE is_deleted = FALSE
            AND updated_at > NOW() - INTERVAL '7 days'
            ORDER BY updated_at DESC
            LIMIT 10
        ''')
        
        print("\n最近活跃用户 (7天内):")
        print("-" * 60)
        print(f"{'用户名':<20} {'类型':<6} {'最后活跃':<8}")
        print("-" * 60)
        
        for user in recent_users:
            hours = round(user['hours_ago'], 1)
            user_type = user['user_type']
            print(f"{user['username']:<20} {user_type:<6} {hours}h前")
        
        # 工作流统计
        workflow_stats = await db_manager.fetch_one('''
            SELECT 
                COUNT(*) as total_workflows,
                COUNT(CASE WHEN is_deleted = FALSE THEN 1 END) as active_workflows
            FROM workflow
        ''')
        
        print(f"\n工作流统计:")
        print(f"总工作流数:   {workflow_stats['total_workflows']}")
        print(f"活跃工作流:   {workflow_stats['active_workflows']}")
        
    except Exception as e:
        print(f"❌ 监控失败: {e}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='用户会话修复工具')
    parser.add_argument('--cleanup-test-users', action='store_true', help='清理测试用户')
    parser.add_argument('--fix-permissions', action='store_true', help='修复权限问题')
    parser.add_argument('--monitor', action='store_true', help='监控用户状态')
    parser.add_argument('--all', action='store_true', help='执行所有修复')
    
    args = parser.parse_args()
    
    if not any([args.cleanup_test_users, args.fix_permissions, args.monitor, args.all]):
        print("请指定要执行的操作。使用 --help 查看帮助。")
        return
    
    print("🚀 用户会话修复工具启动")
    print("=" * 60)
    
    try:
        if args.all or args.monitor:
            await monitor_user_status()
            print()
        
        if args.all or args.cleanup_test_users:
            await cleanup_test_users()
            print()
        
        if args.all or args.fix_permissions:
            await fix_workflow_permissions()
            print()
        
        print("🎉 修复完成！")
        
    except Exception as e:
        print(f"💥 修复过程中发生错误: {e}")


if __name__ == '__main__':
    asyncio.run(main())