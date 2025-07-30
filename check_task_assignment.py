#!/usr/bin/env python3
"""
检查任务分配机制
Check Task Assignment Mechanism
"""

import asyncio
import asyncpg
from loguru import logger

async def check_task_assignment():
    """检查任务分配机制的完整性"""
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
        
        # 1. 检查所有任务实例的分配状态
        logger.info("📋 检查任务实例的分配状态...")
        task_query = """
        SELECT 
            ti.task_instance_id,
            ti.task_title,
            ti.task_type,
            ti.status,
            ti.assigned_user_id,
            ti.assigned_agent_id,
            ti.processor_id,
            p.name as processor_name,
            p.type as processor_type,
            p.user_id as processor_user_id,
            p.agent_id as processor_agent_id,
            u.username as assigned_user_name,
            a.agent_name as assigned_agent_name,
            pu.username as processor_user_name,
            pa.agent_name as processor_agent_name
        FROM task_instance ti
        LEFT JOIN processor p ON p.processor_id = ti.processor_id
        LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
        LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
        LEFT JOIN "user" pu ON pu.user_id = p.user_id
        LEFT JOIN agent pa ON pa.agent_id = p.agent_id
        WHERE ti.is_deleted = FALSE
        ORDER BY ti.created_at DESC
        LIMIT 10
        """
        
        tasks = await conn.fetch(task_query)
        
        if tasks:
            logger.info(f"找到 {len(tasks)} 个任务实例:")
            
            unassigned_count = 0
            assigned_count = 0
            
            for task in tasks:
                logger.info(f"\n📋 任务: {task['task_title']}")
                logger.info(f"   任务ID: {task['task_instance_id']}")
                logger.info(f"   任务类型: {task['task_type']}")
                logger.info(f"   任务状态: {task['status']}")
                logger.info(f"   处理器: {task['processor_name']} (类型: {task['processor_type']})")
                
                # 检查处理器的配置分配
                if task['processor_user_id']:
                    logger.info(f"   处理器配置的用户: {task['processor_user_name']} (ID: {task['processor_user_id']})")
                elif task['processor_agent_id']:
                    logger.info(f"   处理器配置的代理: {task['processor_agent_name']} (ID: {task['processor_agent_id']})")
                else:
                    logger.info(f"   ⚠️  处理器未配置用户或代理")
                
                # 检查任务的实际分配
                if task['assigned_user_id']:
                    logger.info(f"   ✅ 已分配给用户: {task['assigned_user_name']} (ID: {task['assigned_user_id']})")
                    assigned_count += 1
                elif task['assigned_agent_id']:
                    logger.info(f"   ✅ 已分配给代理: {task['assigned_agent_name']} (ID: {task['assigned_agent_id']})")
                    assigned_count += 1
                else:
                    logger.warning(f"   ❌ 任务未分配给任何执行者")
                    unassigned_count += 1
            
            logger.info(f"\n📊 分配统计:")
            logger.info(f"   已分配任务: {assigned_count}")
            logger.info(f"   未分配任务: {unassigned_count}")
            
        else:
            logger.warning("❌ 未找到任何任务实例")
        
        # 2. 检查用户表，看看有哪些用户
        logger.info("\n👥 检查系统中的用户...")
        user_query = """
        SELECT user_id, username, email, is_deleted, created_at
        FROM "user"
        ORDER BY created_at DESC
        LIMIT 10
        """
        
        users = await conn.fetch(user_query)
        if users:
            logger.info(f"找到 {len(users)} 个用户:")
            for user in users:
                logger.info(f"   - {user['username']} (ID: {user['user_id']}, 删除: {user['is_deleted']})")
        else:
            logger.warning("❌ 未找到任何用户")
        
        # 3. 检查处理器的用户分配配置
        logger.info("\n🔧 检查处理器的用户分配配置...")
        processor_query = """
        SELECT 
            p.processor_id,
            p.name as processor_name,
            p.type as processor_type,
            p.user_id,
            p.agent_id,
            u.username,
            a.agent_name,
            p.is_deleted
        FROM processor p
        LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
        LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
        WHERE p.is_deleted = FALSE
        ORDER BY p.created_at DESC
        LIMIT 10
        """
        
        processors = await conn.fetch(processor_query)
        if processors:
            logger.info(f"找到 {len(processors)} 个处理器:")
            
            human_unassigned = 0
            agent_unassigned = 0
            
            for proc in processors:
                logger.info(f"\n🔧 处理器: {proc['processor_name']} (类型: {proc['processor_type']})")
                
                if proc['processor_type'] == 'human':
                    if proc['user_id']:
                        logger.info(f"   ✅ 分配给用户: {proc['username']} (ID: {proc['user_id']})")
                    else:
                        logger.warning(f"   ❌ 人工处理器未分配用户")
                        human_unassigned += 1
                        
                elif proc['processor_type'] == 'agent':
                    if proc['agent_id']:
                        logger.info(f"   ✅ 分配给代理: {proc['agent_name']} (ID: {proc['agent_id']})")
                    else:
                        logger.warning(f"   ❌ 代理处理器未分配代理")
                        agent_unassigned += 1
            
            logger.info(f"\n📊 处理器分配统计:")
            logger.info(f"   未分配用户的人工处理器: {human_unassigned}")
            logger.info(f"   未分配代理的AI处理器: {agent_unassigned}")
        
        # 4. 检查当前登录用户可以看到的任务
        logger.info("\n📋 检查用户任务视图...")
        
        # 获取一个用户ID来测试
        if users:
            test_user_id = users[0]['user_id']
            test_username = users[0]['username']
            logger.info(f"测试用户: {test_username} (ID: {test_user_id})")
            
            # 检查该用户的分配任务
            user_task_query = """
            SELECT 
                ti.task_instance_id,
                ti.task_title,
                ti.task_type,
                ti.status,
                wi.workflow_instance_name,
                w.name as workflow_name
            FROM task_instance ti
            LEFT JOIN workflow_instance wi ON wi.workflow_instance_id = ti.workflow_instance_id
            LEFT JOIN workflow w ON w.workflow_base_id = wi.workflow_base_id AND w.is_current_version = TRUE
            WHERE ti.assigned_user_id = $1 AND ti.is_deleted = FALSE
            ORDER BY ti.created_at DESC
            """
            
            user_tasks = await conn.fetch(user_task_query, test_user_id)
            
            if user_tasks:
                logger.info(f"✅ 用户 {test_username} 有 {len(user_tasks)} 个分配的任务:")
                for task in user_tasks:
                    logger.info(f"   - {task['task_title']} (状态: {task['status']}, 工作流: {task['workflow_name']})")
            else:
                logger.warning(f"❌ 用户 {test_username} 没有分配任何任务")
                
                # 检查是否有任何PENDING任务应该分配给这个用户
                pending_query = """
                SELECT 
                    ti.task_instance_id,
                    ti.task_title,
                    p.name as processor_name,
                    p.type as processor_type,
                    p.user_id as processor_user_id
                FROM task_instance ti
                JOIN processor p ON p.processor_id = ti.processor_id
                WHERE ti.status = 'pending' 
                AND ti.assigned_user_id IS NULL 
                AND p.user_id = $1
                AND ti.is_deleted = FALSE
                """
                
                pending_tasks = await conn.fetch(pending_query, test_user_id)
                
                if pending_tasks:
                    logger.error(f"🔥 发现问题: 有 {len(pending_tasks)} 个pending任务应该分配给用户 {test_username} 但没有分配!")
                    for task in pending_tasks:
                        logger.error(f"   - 未分配任务: {task['task_title']} (处理器: {task['processor_name']})")
                else:
                    logger.info(f"   没有pending任务需要分配给用户 {test_username}")
        
        await conn.close()
        
        # 5. 总结分析
        logger.info("\n" + "="*60)
        logger.info("🔍 任务分配机制分析总结:")
        
        if tasks:
            if unassigned_count > 0:
                logger.error(f"❌ 发现问题: 有 {unassigned_count} 个任务未被分配")
                logger.error("   可能原因:")
                logger.error("   1. 处理器没有配置用户或代理")
                logger.error("   2. 任务创建时没有执行分配逻辑")
                logger.error("   3. 分配逻辑存在bug")
            else:
                logger.info("✅ 所有任务都已正确分配")
        
        logger.info("\n💡 建议检查:")
        logger.info("1. 确保所有人工处理器都分配了用户")
        logger.info("2. 确保所有AI处理器都分配了代理")
        logger.info("3. 检查任务创建时的分配逻辑")
        logger.info("4. 验证前端是否正确调用获取用户任务的API")
        
    except Exception as e:
        logger.error(f"检查任务分配失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(check_task_assignment())