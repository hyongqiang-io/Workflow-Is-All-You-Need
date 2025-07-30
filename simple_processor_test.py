#!/usr/bin/env python3
"""
简单的处理器集成测试
Simple Processor Integration Test
"""

import asyncio
import uuid
from datetime import datetime

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.auth_service import AuthService
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService
from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
from workflow_framework.services.execution_service import execution_engine
from workflow_framework.services.agent_task_service import agent_task_service
from workflow_framework.models.user import UserCreate
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType, NodeConnectionCreate
from workflow_framework.models.processor import ProcessorCreate, ProcessorType
from workflow_framework.models.instance import WorkflowExecuteRequest


async def test_simple_integration():
    """测试简单的处理器集成"""
    await initialize_database()
    
    try:
        print("开始处理器集成测试...")
        
        # 启动服务
        await execution_engine.start_engine()
        await agent_task_service.start_service()
        print("服务启动成功")
        
        # 创建服务实例
        auth_service = AuthService()
        workflow_service = WorkflowService()
        node_service = NodeService()
        processor_repo = ProcessorRepository()
        
        # 1. 创建测试用户
        print("1. 创建测试用户...")
        user_data = UserCreate(
            username=f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            email=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            password="test123456",
            role="admin",
            description="测试用户"
        )
        
        user_response = await auth_service.register_user(user_data)
        print(f"用户创建成功: {user_response.username}")
        
        # 2. 创建工作流
        print("2. 创建工作流...")
        workflow_data = WorkflowCreate(
            name=f"简单测试工作流_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description="简单的处理器测试工作流",
            creator_id=user_response.user_id
        )
        
        workflow_response = await workflow_service.create_workflow(workflow_data)
        print(f"工作流创建成功: {workflow_response.name}")
        
        # 3. 创建节点
        print("3. 创建节点...")
        
        # 开始节点
        start_node_data = NodeCreate(
            name="开始节点",
            type=NodeType.START,
            task_description="工作流开始",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=100,
            position_y=100
        )
        start_node = await node_service.create_node(start_node_data, user_response.user_id)
        print(f"开始节点创建成功: {start_node.name}")
        
        # 人工处理节点
        human_node_data = NodeCreate(
            name="人工处理节点",
            type=NodeType.PROCESSOR,
            task_description="人工处理任务",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=300,
            position_y=100
        )
        human_node = await node_service.create_node(human_node_data, user_response.user_id)
        print(f"人工处理节点创建成功: {human_node.name}")
        
        # 结束节点
        end_node_data = NodeCreate(
            name="结束节点",
            type=NodeType.END,
            task_description="工作流结束",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=500,
            position_y=100
        )
        end_node = await node_service.create_node(end_node_data, user_response.user_id)
        print(f"结束节点创建成功: {end_node.name}")
        
        # 4. 创建人工处理器
        print("4. 创建人工处理器...")
        human_processor_data = ProcessorCreate(
            name="人工分析师",
            type=ProcessorType.HUMAN,
            user_id=user_response.user_id
        )
        
        human_processor = await processor_repo.create_processor(human_processor_data)
        print(f"人工处理器创建成功: {human_processor['name']}")
        
        # 5. 关联处理器到节点
        print("5. 关联处理器到节点...")
        await node_service.assign_processor_to_node(
            human_node.node_base_id, 
            workflow_response.workflow_base_id,
            human_processor['processor_id'], 
            user_response.user_id
        )
        print("人工处理器已关联到节点")
        
        # 6. 创建节点连接
        print("6. 创建节点连接...")
        connection1 = NodeConnectionCreate(
            from_node_base_id=start_node.node_base_id,
            to_node_base_id=human_node.node_base_id,
            workflow_base_id=workflow_response.workflow_base_id
        )
        await node_service.create_node_connection(connection1, user_response.user_id)
        
        connection2 = NodeConnectionCreate(
            from_node_base_id=human_node.node_base_id,
            to_node_base_id=end_node.node_base_id,
            workflow_base_id=workflow_response.workflow_base_id
        )
        await node_service.create_node_connection(connection2, user_response.user_id)
        print("节点连接创建成功")
        
        # 7. 执行工作流
        print("7. 执行工作流...")
        execute_request = WorkflowExecuteRequest(
            workflow_base_id=workflow_response.workflow_base_id,
            instance_name=f"简单测试实例_{datetime.now().strftime('%H%M%S')}",
            input_data={"test": "data"},
            context_data={"test_type": "simple"}
        )
        
        execution_result = await execution_engine.execute_workflow(
            execute_request, user_response.user_id
        )
        
        print(f"工作流执行启动: {execution_result['instance_id']}")
        print(f"状态: {execution_result['status']}")
        
        # 8. 监控执行状态
        print("8. 监控执行状态...")
        instance_id = execution_result['instance_id']
        
        for i in range(5):
            await asyncio.sleep(2)
            status = await execution_engine.get_workflow_status(instance_id)
            if status:
                print(f"检查 {i+1}: 状态={status['instance']['status']}")
                if status['instance']['status'] in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    break
            else:
                print(f"检查 {i+1}: 无法获取状态")
        
        print("处理器集成测试完成")
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await execution_engine.stop_engine()
        await agent_task_service.stop_service()
        await close_database()


async def main():
    """主函数"""
    try:
        success = await test_simple_integration()
        if success:
            print("所有测试通过")
        else:
            print("测试失败")
            return False
    except Exception as e:
        print(f"测试异常: {e}")
        return False
    return True


if __name__ == "__main__":
    print("处理器集成测试")
    print("=" * 50)
    
    success = asyncio.run(main())
    
    if success:
        print("测试成功")
    else:
        print("测试失败")
        exit(1)