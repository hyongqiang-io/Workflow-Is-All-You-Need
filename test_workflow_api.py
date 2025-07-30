#!/usr/bin/env python3
"""
工作流API测试脚本
Test Workflow API
"""

import asyncio
import json
import uuid
from datetime import datetime

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.auth_service import AuthService
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService
from workflow_framework.models.user import UserCreate
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType, NodeConnectionCreate
from workflow_framework.models.processor import ProcessorType


async def test_complete_workflow():
    """测试完整的工作流创建流程"""
    
    # 初始化数据库
    await initialize_database()
    
    try:
        # 创建服务实例
        auth_service = AuthService()
        workflow_service = WorkflowService()
        node_service = NodeService()
        
        print("开始测试工作流创建流程...")
        
        # 1. 创建测试用户
        print("\n1. 创建测试用户...")
        user_data = UserCreate(
            username=f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            email=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            password="test123456",
            role="admin",
            description="测试用户"
        )
        
        user_response = await auth_service.register_user(user_data)
        print(f"用户创建成功: {user_response.username} (ID: {user_response.user_id})")
        
        # 2. 创建工作流
        print("\n2. 创建工作流...")
        workflow_data = WorkflowCreate(
            name=f"测试工作流_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description="这是一个测试工作流，包含多个节点和连接",
            creator_id=user_response.user_id
        )
        
        workflow_response = await workflow_service.create_workflow(workflow_data)
        print(f"✅ 工作流创建成功: {workflow_response.name} (ID: {workflow_response.workflow_base_id})")
        
        # 3. 创建开始节点
        print("\n🟢 3. 创建开始节点...")
        start_node_data = NodeCreate(
            name="开始节点",
            type=NodeType.START,
            task_description="工作流开始执行",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=100,
            position_y=100
        )
        
        start_node_response = await node_service.create_node(start_node_data, user_response.user_id)
        print(f"✅ 开始节点创建成功: {start_node_response.name} (ID: {start_node_response.node_base_id})")
        
        # 4. 创建处理节点
        print("\n⚙️ 4. 创建处理节点...")
        process_node_data = NodeCreate(
            name="数据处理节点",
            type=NodeType.PROCESSOR,
            task_description="对输入数据进行处理和分析",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=300,
            position_y=100
        )
        
        process_node_response = await node_service.create_node(process_node_data, user_response.user_id)
        print(f"✅ 处理节点创建成功: {process_node_response.name} (ID: {process_node_response.node_base_id})")
        
        # 5. 创建结束节点
        print("\n🔴 5. 创建结束节点...")
        end_node_data = NodeCreate(
            name="结束节点",
            type=NodeType.END,
            task_description="工作流执行完成",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=500,
            position_y=100
        )
        
        end_node_response = await node_service.create_node(end_node_data, user_response.user_id)
        print(f"✅ 结束节点创建成功: {end_node_response.name} (ID: {end_node_response.node_base_id})")
        
        # 6. 创建节点连接
        print("\n🔗 6. 创建节点连接...")
        
        # 开始节点 -> 处理节点
        connection1_data = NodeConnectionCreate(
            from_node_base_id=start_node_response.node_base_id,
            to_node_base_id=process_node_response.node_base_id,
            workflow_base_id=workflow_response.workflow_base_id
        )
        
        connection1 = await node_service.create_node_connection(connection1_data, user_response.user_id)
        print(f"✅ 连接创建成功: 开始节点 -> 处理节点")
        
        # 处理节点 -> 结束节点
        connection2_data = NodeConnectionCreate(
            from_node_base_id=process_node_response.node_base_id,
            to_node_base_id=end_node_response.node_base_id,
            workflow_base_id=workflow_response.workflow_base_id
        )
        
        connection2 = await node_service.create_node_connection(connection2_data, user_response.user_id)
        print(f"✅ 连接创建成功: 处理节点 -> 结束节点")
        
        # 7. 查询工作流信息
        print("\n📊 7. 查询工作流信息...")
        
        # 查询用户的所有工作流
        user_workflows = await workflow_service.get_user_workflows(user_response.user_id)
        print(f"✅ 用户工作流数量: {len(user_workflows)}")
        
        # 查询工作流的所有节点
        workflow_nodes = await node_service.get_workflow_nodes(
            workflow_response.workflow_base_id, user_response.user_id
        )
        print(f"✅ 工作流节点数量: {len(workflow_nodes)}")
        
        # 查询工作流的所有连接
        workflow_connections = await node_service.get_workflow_connections(
            workflow_response.workflow_base_id, user_response.user_id
        )
        print(f"✅ 工作流连接数量: {len(workflow_connections)}")
        
        # 8. 输出详细信息
        print("\n📋 8. 工作流详细信息:")
        print("=" * 50)
        print(f"工作流名称: {workflow_response.name}")
        print(f"工作流描述: {workflow_response.description}")
        print(f"创建者: {user_response.username}")
        print(f"创建时间: {workflow_response.created_at}")
        
        print("\n节点列表:")
        for i, node in enumerate(workflow_nodes, 1):
            print(f"  {i}. {node.name} ({node.type.value})")
            print(f"     描述: {node.task_description}")
            print(f"     位置: ({node.position_x}, {node.position_y})")
        
        print("\n连接列表:")
        for i, connection in enumerate(workflow_connections, 1):
            print(f"  {i}. {connection['from_node_base_id']} -> {connection['to_node_base_id']}")
            print(f"     类型: {connection['connection_type']}")
        
        print("\n🎉 工作流创建流程测试完成！")
        
        return {
            "user": user_response,
            "workflow": workflow_response,
            "nodes": workflow_nodes,
            "connections": workflow_connections
        }
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        raise
    finally:
        # 关闭数据库连接
        await close_database()


async def main():
    """主函数"""
    try:
        result = await test_complete_workflow()
        print(f"\n✅ 测试成功完成！创建了包含 {len(result['nodes'])} 个节点和 {len(result['connections'])} 个连接的工作流")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("🧪 工作流API功能测试")
    print("=" * 50)
    
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 所有测试通过！")
    else:
        print("\n💥 测试失败！")
        exit(1)