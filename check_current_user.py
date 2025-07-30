#!/usr/bin/env python3
"""
检查当前用户和任务分配
Check Current User and Task Assignment
"""

import asyncio
import asyncpg
from loguru import logger

async def check_current_user_tasks():
    """检查当前用户相关的任务分配问题"""
    try:
        # 连接数据库
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            database='workflow_db',
            user='postgres',
            password='postgresql'
        )
        
        logger.info("✅ 数据库连接成功")
        
        # 1. 检查活跃用户（未删除）
        logger.info("👥 检查活跃用户...")
        active_users_query = """
        SELECT user_id, username, email, is_deleted, created_at
        FROM "user"
        WHERE is_deleted = FALSE
        ORDER BY created_at DESC
        """
        
        active_users = await conn.fetch(active_users_query)
        
        if active_users:
            logger.info(f"找到 {len(active_users)} 个活跃用户:")
            for user in active_users:
                logger.info(f"   ✅ {user['username']} (ID: {user['user_id']}, Email: {user['email']})")
        else:
            logger.warning("❌ 没有找到任何活跃用户!")
            
            # 检查所有用户
            all_users_query = """
            SELECT user_id, username, email, is_deleted, created_at
            FROM "user"
            ORDER BY created_at DESC
            LIMIT 10
            """
            all_users = await conn.fetch(all_users_query)
            logger.info(f"系统中总共有 {len(all_users)} 个用户（包括已删除）")
            
        # 2. 检查分配给人工处理器的任务
        logger.info("\n🔍 检查分配给人工处理器的任务...")
        human_tasks_query = """
        SELECT 
            ti.task_instance_id,
            ti.task_title,
            ti.status,
            ti.assigned_user_id,
            p.name as processor_name,
            p.type as processor_type,
            p.user_id as processor_user_id,
            u.username as assigned_user_name,
            u.is_deleted as user_is_deleted,
            pu.username as processor_user_name,
            pu.is_deleted as processor_user_is_deleted
        FROM task_instance ti
        JOIN processor p ON p.processor_id = ti.processor_id
        LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
        LEFT JOIN "user" pu ON pu.user_id = p.user_id
        WHERE p.type = 'human' AND ti.is_deleted = FALSE
        ORDER BY ti.created_at DESC
        """
        
        human_tasks = await conn.fetch(human_tasks_query)
        
        if human_tasks:
            logger.info(f"找到 {len(human_tasks)} 个人工任务:")
            
            for task in human_tasks:
                logger.info(f"\n📋 任务: {task['task_title']}")
                logger.info(f"   任务状态: {task['status']}")
                logger.info(f"   处理器: {task['processor_name']}")
                
                if task['processor_user_id']:
                    deleted_status = "已删除" if task['processor_user_is_deleted'] else "活跃"
                    logger.info(f"   处理器配置用户: {task['processor_user_name']} ({deleted_status})")
                
                if task['assigned_user_id']:
                    user_deleted_status = "已删除" if task['user_is_deleted'] else "活跃"
                    logger.info(f"   分配给用户: {task['assigned_user_name']} ({user_deleted_status})")
                    
                    if task['user_is_deleted']:
                        logger.error(f"   ❌ 问题: 任务分配给了已删除的用户!")
                else:
                    logger.warning(f"   ⚠️  任务未分配给任何用户")
        
        # 3. 如果有活跃用户，检查他们是否有任务
        if active_users:
            logger.info(f"\n🔍 检查活跃用户的任务分配...")
            
            for user in active_users:
                user_id = user['user_id']
                username = user['username']
                
                # 检查该用户的任务
                user_tasks_query = """
                SELECT 
                    ti.task_instance_id,
                    ti.task_title,
                    ti.status,
                    ti.task_type,
                    wi.workflow_instance_name
                FROM task_instance ti
                LEFT JOIN workflow_instance wi ON wi.workflow_instance_id = ti.workflow_instance_id
                WHERE ti.assigned_user_id = $1 AND ti.is_deleted = FALSE
                ORDER BY ti.created_at DESC
                """
                
                user_tasks = await conn.fetch(user_tasks_query, user_id)
                
                if user_tasks:
                    logger.info(f"✅ 用户 {username} 有 {len(user_tasks)} 个任务:")
                    for task in user_tasks:
                        logger.info(f"   - {task['task_title']} (状态: {task['status']})")
                else:
                    logger.warning(f"❌ 用户 {username} 没有任何分配的任务")
                    
                    # 检查是否有处理器配置给这个用户
                    processor_query = """
                    SELECT processor_id, name, type
                    FROM processor 
                    WHERE user_id = $1 AND is_deleted = FALSE
                    """
                    user_processors = await conn.fetch(processor_query, user_id)
                    
                    if user_processors:
                        logger.info(f"   该用户有 {len(user_processors)} 个配置的处理器:")
                        for proc in user_processors:
                            logger.info(f"     - {proc['name']} (类型: {proc['type']})")
                    else:
                        logger.warning(f"   该用户没有配置任何处理器")
        
        # 4. 检查任务分配逻辑的问题
        logger.info(f"\n🔧 检查任务分配逻辑问题...")
        
        # 查找pending状态但应该被分配的任务
        pending_should_assign_query = """
        SELECT 
            ti.task_instance_id,
            ti.task_title,
            ti.status,
            p.name as processor_name,
            p.type as processor_type,
            p.user_id as processor_user_id,
            p.agent_id as processor_agent_id,
            u.username as processor_user_name,
            u.is_deleted as user_is_deleted,
            a.agent_name as processor_agent_name
        FROM task_instance ti
        JOIN processor p ON p.processor_id = ti.processor_id
        LEFT JOIN "user" u ON u.user_id = p.user_id
        LEFT JOIN agent a ON a.agent_id = p.agent_id
        WHERE ti.status = 'pending' 
        AND ti.assigned_user_id IS NULL 
        AND ti.assigned_agent_id IS NULL
        AND ti.is_deleted = FALSE
        """
        
        pending_tasks = await conn.fetch(pending_should_assign_query)
        
        if pending_tasks:
            logger.error(f"🔥 发现 {len(pending_tasks)} 个应该被分配但没有分配的pending任务:")
            for task in pending_tasks:
                logger.error(f"   - {task['task_title']} (处理器: {task['processor_name']})")
                if task['processor_user_id']:
                    deleted_status = "已删除" if task['user_is_deleted'] else "活跃"
                    logger.error(f"     应该分配给用户: {task['processor_user_name']} ({deleted_status})")
                elif task['processor_agent_id']:
                    logger.error(f"     应该分配给代理: {task['processor_agent_name']}")
        else:
            logger.info("✅ 没有发现未分配的pending任务")
        
        await conn.close()
        
        # 5. 总结和建议
        logger.info("\n" + "="*60)
        logger.info("🔍 问题诊断总结:")
        
        if not active_users:
            logger.error("❌ 核心问题: 系统中没有活跃用户!")
            logger.error("   解决方案: 需要创建或恢复活跃用户账户")
        elif human_tasks and all(task['user_is_deleted'] for task in human_tasks if task['assigned_user_id']):
            logger.error("❌ 核心问题: 任务分配给了已删除的用户!")
            logger.error("   解决方案: 需要将任务重新分配给活跃用户")
        else:
            logger.info("✅ 用户状态看起来正常")
            
        logger.info("\n💡 建议的修复步骤:")
        logger.info("1. 确保有活跃的用户账户")
        logger.info("2. 更新处理器配置，将其关联到活跃用户")
        logger.info("3. 重新分配现有的pending/assigned任务给活跃用户")
        logger.info("4. 检查前端是否使用正确的用户ID获取任务")
        
    except Exception as e:
        logger.error(f"检查当前用户任务失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(check_current_user_tasks())