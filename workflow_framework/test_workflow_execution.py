#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试工作流执行修复
"""

import asyncio
import uuid
from services.execution_service import ExecutionService
from repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from repositories.instance.node_instance_repository import NodeInstanceRepository
from utils.database import DatabaseManager
from utils.logger import logger

async def test_workflow_execution():
    """测试工作流执行"""
    try:
        logger.info("🧪 开始测试工作流执行修复")
        
        # 初始化数据库连接
        db_manager = DatabaseManager()
        await db_manager.connect()
        
        # 初始化服务
        execution_service = ExecutionService()
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 查找现有的运行中的工作流实例
        logger.info("查找现有的运行中工作流实例")
        running_instances = await workflow_instance_repo.get_instances_by_status('running')
        
        if running_instances:
            logger.info(f"找到 {len(running_instances)} 个运行中的工作流实例")
            
            # 选择第一个实例进行测试
            test_instance = running_instances[0]
            workflow_instance_id = test_instance.workflow_instance_id
            workflow_base_id = test_instance.workflow_base_id
            executor_id = test_instance.executor_id
            
            logger.info(f"测试工作流实例: {workflow_instance_id}")
            logger.info(f"工作流基础ID: {workflow_base_id}")
            logger.info(f"执行者ID: {executor_id}")
            
            # 尝试重新执行工作流（应该触发修复逻辑）
            logger.info("🔄 尝试重新执行工作流（测试修复逻辑）")
            try:
                result = await execution_service.execute_workflow(
                    workflow_base_id=workflow_base_id,
                    executor_id=executor_id,
                    input_data={"test": "修复测试"}
                )
                logger.info(f"✅ 工作流执行结果: {result}")
                
            except Exception as e:
                logger.error(f"❌ 工作流执行失败: {e}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
        else:
            logger.warning("没有找到运行中的工作流实例")
            
            # 查找所有工作流实例
            all_instances = await workflow_instance_repo.get_all_instances()
            if all_instances:
                logger.info(f"找到 {len(all_instances)} 个工作流实例")
                for instance in all_instances[:3]:  # 只显示前3个
                    logger.info(f"  - 实例: {instance.workflow_instance_id}, 状态: {instance.status}")
            else:
                logger.warning("数据库中没有任何工作流实例")
        
        await db_manager.disconnect()
        logger.info("🎉 测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_workflow_execution())