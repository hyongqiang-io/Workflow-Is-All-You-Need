#!/usr/bin/env python3
"""
检查节点-处理器关联关系
Check Node-Processor Associations
"""

import asyncio
import asyncpg
from loguru import logger

async def check_database():
    """检查数据库中的节点和处理器关联"""
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
        
        # 1. 检查processor表
        logger.info("📋 检查processor表...")
        processor_query = """
        SELECT processor_id, name, type, is_deleted, user_id, agent_id
        FROM processor 
        WHERE is_deleted = FALSE
        ORDER BY created_at DESC
        LIMIT 5
        """
        processors = await conn.fetch(processor_query)
        
        if processors:
            logger.info(f"找到 {len(processors)} 个处理器:")
            for p in processors:
                logger.info(f"  - {p['name']} (类型: {p['type']}, ID: {p['processor_id']})")
        else:
            logger.warning("❌ 未找到任何处理器数据")
        
        # 2. 检查node表
        logger.info("📋 检查node表...")
        node_query = """
        SELECT node_id, node_base_id, name, type, is_current_version, is_deleted
        FROM node 
        WHERE is_deleted = FALSE
        ORDER BY created_at DESC
        LIMIT 5
        """
        nodes = await conn.fetch(node_query)
        
        if nodes:
            logger.info(f"找到 {len(nodes)} 个节点:")
            for n in nodes:
                logger.info(f"  - {n['name']} (类型: {n['type']}, node_id: {n['node_id']}, current: {n['is_current_version']})")
        else:
            logger.warning("❌ 未找到任何节点数据")
        
        # 3. 检查node_processor关联表
        logger.info("📋 检查node_processor关联表...")
        np_query = """
        SELECT np.*, n.name as node_name, p.name as processor_name
        FROM node_processor np
        LEFT JOIN node n ON n.node_id = np.node_id
        LEFT JOIN processor p ON p.processor_id = np.processor_id
        ORDER BY np.created_at DESC
        LIMIT 10
        """
        associations = await conn.fetch(np_query)
        
        if associations:
            logger.info(f"找到 {len(associations)} 个节点-处理器关联:")
            for a in associations:
                logger.info(f"  - 节点: {a['node_name']} <-> 处理器: {a['processor_name']}")
        else:
            logger.warning("❌ 未找到任何节点-处理器关联数据 - 这是问题的根源!")
        
        # 4. 检查最近的工作流实例
        logger.info("📋 检查最近的工作流实例...")
        instance_query = """
        SELECT wi.workflow_instance_id, wi.workflow_instance_name, wi.status,
               w.name as workflow_name
        FROM workflow_instance wi
        LEFT JOIN workflow w ON w.workflow_base_id = wi.workflow_base_id AND w.is_current_version = TRUE
        WHERE wi.is_deleted = FALSE
        ORDER BY wi.created_at DESC
        LIMIT 5
        """
        instances = await conn.fetch(instance_query)
        
        if instances:
            logger.info(f"找到 {len(instances)} 个工作流实例:")
            for i in instances:
                logger.info(f"  - {i['workflow_instance_name']} (状态: {i['status']}, 工作流: {i['workflow_name']})")
        else:
            logger.warning("❌ 未找到任何工作流实例")
        
        # 5. 检查任务实例
        logger.info("📋 检查任务实例...")
        task_query = """
        SELECT task_instance_id, task_title, task_type, status, processor_id
        FROM task_instance
        WHERE is_deleted = FALSE
        ORDER BY created_at DESC
        LIMIT 5
        """
        tasks = await conn.fetch(task_query)
        
        if tasks:
            logger.info(f"找到 {len(tasks)} 个任务实例:")
            for t in tasks:
                logger.info(f"  - {t['task_title']} (类型: {t['task_type']}, 状态: {t['status']})")
        else:
            logger.warning("❌ 未找到任何任务实例 - 证实了任务没有生成")
        
        await conn.close()
        logger.info("数据库检查完成")
        
        # 总结
        logger.info("=" * 50)
        logger.info("🔍 问题分析总结:")
        if not associations:
            logger.error("❌ 主要问题: node_processor表为空，节点没有关联处理器")
            logger.error("   因此在创建工作流实例时，_get_node_processors返回空列表")
            logger.error("   导致_create_tasks_for_nodes跳过所有processor节点的任务创建")
        
        if not tasks:
            logger.error("❌ 结果: 没有任务实例被创建")
            
        logger.info("💡 解决方案: 需要在节点编辑时正确建立node_processor关联")
        
    except Exception as e:
        logger.error(f"数据库检查失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(check_database())