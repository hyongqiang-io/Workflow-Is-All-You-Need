#!/usr/bin/env python3
"""
创建测试工作流
"""

import asyncio
import uuid
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService

async def create_test_workflow():
    """创建测试工作流"""
    
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
    
    workflow_service = WorkflowService()
    node_service = NodeService()
    
    # 创建工作流
    workflow_data = WorkflowCreate(
        name="测试工作流",
        description="用于测试执行功能的工作流",
        creator_id=user_id
    )
    
    print("创建工作流...")
    try:
        workflow = await workflow_service.create_workflow(workflow_data)
        print(f"工作流创建成功: {workflow.name}")
        print(f"工作流基础ID: {workflow.workflow_base_id}")
        print(f"工作流版本ID: {workflow.workflow_id}")
        
        # 创建开始节点
        start_node_data = NodeCreate(
            name="开始",
            type=NodeType.START,
            workflow_base_id=workflow.workflow_base_id,
            task_description="工作流开始节点",
            position_x=100,
            position_y=100
        )
        
        start_node = await node_service.create_node(start_node_data, user_id)
        print(f"开始节点创建成功: {start_node.name}")
        
        # 创建结束节点
        end_node_data = NodeCreate(
            name="结束",
            type=NodeType.END,
            workflow_base_id=workflow.workflow_base_id,
            task_description="工作流结束节点",
            position_x=300,
            position_y=100
        )
        
        end_node = await node_service.create_node(end_node_data, user_id)
        print(f"结束节点创建成功: {end_node.name}")
        
        return workflow.workflow_base_id
        
    except Exception as e:
        print(f"创建工作流失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("=== 创建测试工作流 ===")
    workflow_base_id = asyncio.run(create_test_workflow())
    if workflow_base_id:
        print(f"\n✅ 测试工作流创建成功！")
        print(f"工作流基础ID: {workflow_base_id}")
        print(f"可以用这个ID进行执行测试。")
    else:
        print(f"\n❌ 测试工作流创建失败！")