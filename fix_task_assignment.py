#!/usr/bin/env python3
"""
修复任务分配问题
Fix Task Assignment Issues
"""

import asyncio
import asyncpg
from loguru import logger

async def fix_task_assignment():
    """修复任务分配问题"""
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
        
        # 1. 获取主要的活跃用户（hhhh）
        logger.info("👤 获取主要活跃用户...")
        main_user_query = """
        SELECT user_id, username, email
        FROM "user"
        WHERE username = 'hhhh' AND is_deleted = FALSE
        """
        
        main_user = await conn.fetchrow(main_user_query)
        
        if not main_user:
            logger.error("❌ 找不到用户 'hhhh'")
            return
        
        main_user_id = main_user['user_id']
        logger.info(f"✅ 找到主用户: {main_user['username']} (ID: {main_user_id})")
        
        # 2. 更新人工处理器，将它们关联到主用户
        logger.info("🔧 更新人工处理器的用户分配...")
        
        # 获取所有人工处理器
        human_processors_query = """
        SELECT processor_id, name, user_id, agent_id
        FROM processor
        WHERE type = 'human' AND is_deleted = FALSE
        """
        
        human_processors = await conn.fetch(human_processors_query)
        
        updated_count = 0
        for processor in human_processors:
            processor_id = processor['processor_id']
            processor_name = processor['name']
            current_user_id = processor['user_id']
            
            if current_user_id != main_user_id:
                # 更新处理器的用户分配
                update_query = """
                UPDATE processor 
                SET user_id = $1, updated_at = NOW()
                WHERE processor_id = $2
                """
                
                await conn.execute(update_query, main_user_id, processor_id)
                logger.info(f"   ✅ 更新处理器 '{processor_name}' -> 用户 'hhhh'")
                updated_count += 1
        
        logger.info(f"🔧 更新了 {updated_count} 个人工处理器")
        
        # 3. 重新分配现有的pending任务
        logger.info("📋 重新分配pending任务...")
        
        # 获取所有pending状态的人工任务
        pending_tasks_query = """
        SELECT 
            ti.task_instance_id,
            ti.task_title,
            ti.assigned_user_id,
            p.name as processor_name,
            p.user_id as processor_user_id
        FROM task_instance ti
        JOIN processor p ON p.processor_id = ti.processor_id
        WHERE ti.status = 'pending' 
        AND p.type = 'human'
        AND ti.is_deleted = FALSE
        """
        
        pending_tasks = await conn.fetch(pending_tasks_query)
        
        reassigned_count = 0
        for task in pending_tasks:
            task_id = task['task_instance_id']
            task_title = task['task_title']
            current_assigned_user = task['assigned_user_id']
            processor_user_id = task['processor_user_id']
            
            # 如果任务没有分配或分配给了错误的用户，重新分配
            if current_assigned_user != processor_user_id:
                update_task_query = """
                UPDATE task_instance 
                SET assigned_user_id = $1, 
                    status = 'assigned',
                    assigned_at = NOW(),
                    updated_at = NOW()
                WHERE task_instance_id = $2
                """
                
                await conn.execute(update_task_query, processor_user_id, task_id)
                logger.info(f"   ✅ 重新分配任务 '{task_title}' -> 用户 'hhhh'")
                reassigned_count += 1
        
        logger.info(f"📋 重新分配了 {reassigned_count} 个任务")
        
        # 4. 验证修复结果
        logger.info("🔍 验证修复结果...")
        
        # 检查用户 hhhh 的任务
        user_tasks_query = """
        SELECT 
            ti.task_instance_id,
            ti.task_title,
            ti.status,
            ti.task_type,
            p.name as processor_name
        FROM task_instance ti
        JOIN processor p ON p.processor_id = ti.processor_id
        WHERE ti.assigned_user_id = $1 AND ti.is_deleted = FALSE
        ORDER BY ti.created_at DESC
        """
        
        user_tasks = await conn.fetch(user_tasks_query, main_user_id)
        
        if user_tasks:
            logger.info(f"✅ 用户 'hhhh' 现在有 {len(user_tasks)} 个分配的任务:")
            for task in user_tasks:
                logger.info(f"   - {task['task_title']} (状态: {task['status']}, 处理器: {task['processor_name']})")
        else:
            logger.warning("⚠️  用户 'hhhh' 仍然没有任务")
        
        # 5. 检查是否还有未分配的人工任务
        unassigned_human_query = """
        SELECT 
            ti.task_instance_id,
            ti.task_title,
            p.name as processor_name
        FROM task_instance ti
        JOIN processor p ON p.processor_id = ti.processor_id
        WHERE p.type = 'human' 
        AND ti.assigned_user_id IS NULL
        AND ti.is_deleted = FALSE
        """
        
        unassigned_tasks = await conn.fetch(unassigned_human_query)
        
        if unassigned_tasks:
            logger.warning(f"⚠️  仍有 {len(unassigned_tasks)} 个未分配的人工任务:")
            for task in unassigned_tasks:
                logger.warning(f"   - {task['task_title']} (处理器: {task['processor_name']})")
        else:
            logger.info("✅ 所有人工任务都已正确分配")
        
        await conn.close()
        
        # 6. 总结
        logger.info("\n" + "="*60)
        logger.info("🎉 任务分配修复完成!")
        logger.info(f"   - 更新了 {updated_count} 个处理器配置")
        logger.info(f"   - 重新分配了 {reassigned_count} 个任务")
        
        if user_tasks:
            logger.info(f"   - 用户 'hhhh' 现在有 {len(user_tasks)} 个待办任务")
            logger.info("\n💡 下一步:")
            logger.info("   1. 刷新前端页面")
            logger.info("   2. 检查用户任务列表")
            logger.info("   3. 确认任务可以正常执行")
        else:
            logger.warning("\n⚠️  如果用户仍然看不到任务，请检查:")
            logger.warning("   1. 前端是否使用正确的用户ID")
            logger.warning("   2. API是否正确返回用户任务")
            logger.warning("   3. 是否需要重新创建工作流实例")
        
    except Exception as e:
        logger.error(f"修复任务分配失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(fix_task_assignment())