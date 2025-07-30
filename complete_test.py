#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys
import os
from datetime import datetime

# 设置编码
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.auth_service import AuthService
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService
from workflow_framework.models.user import UserCreate
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType, NodeConnectionCreate


async def test_complete_workflow():
    """测试完整的工作流创建功能"""
    
    try:
        # 初始化数据库
        print("==== 初始化数据库连接 ====")
        await initialize_database()
        
        # 创建服务实例
        auth_service = AuthService()
        workflow_service = WorkflowService()
        node_service = NodeService()
        
        print("==== 开始测试工作流完整创建流程 ====")
        
        # 1. 创建测试用户
        print("\\n[步骤1] 创建测试用户")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        user_data = UserCreate(
            username=f"test_user_{timestamp}",
            email=f"test_{timestamp}@example.com",
            password="test123456",
            role="admin",
            description="测试用户账户"
        )
        
        user_response = await auth_service.register_user(user_data)
        print(f"SUCCESS: 用户创建成功")
        print(f"  - 用户名: {user_response.username}")
        print(f"  - 用户ID: {user_response.user_id}")
        
        # 2. 创建工作流
        print("\\n[步骤2] 创建工作流")
        workflow_data = WorkflowCreate(
            name=f"人机协作工作流_{timestamp}",
            description="这是一个包含多个节点和连接的测试工作流",
            creator_id=user_response.user_id
        )
        
        workflow_response = await workflow_service.create_workflow(workflow_data)
        print(f"SUCCESS: 工作流创建成功")
        print(f"  - 工作流名称: {workflow_response.name}")
        print(f"  - 工作流ID: {workflow_response.workflow_base_id}")
        
        # 3. 创建开始节点
        print("\\n[步骤3] 创建开始节点")
        start_node_data = NodeCreate(
            name="开始节点",
            type=NodeType.START,
            task_description="工作流开始执行点",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=100,
            position_y=200
        )
        
        start_node_response = await node_service.create_node(start_node_data, user_response.user_id)
        print(f"SUCCESS: 开始节点创建成功")
        print(f"  - 节点名称: {start_node_response.name}")
        print(f"  - 节点ID: {start_node_response.node_base_id}")
        
        # 4. 创建处理节点
        print("\\n[步骤4] 创建处理节点")
        process_node_data = NodeCreate(
            name="数据处理节点",
            type=NodeType.PROCESSOR,
            task_description="对输入数据进行处理、分析和转换",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=350,
            position_y=200
        )
        
        process_node_response = await node_service.create_node(process_node_data, user_response.user_id)
        print(f"SUCCESS: 处理节点创建成功")
        print(f"  - 节点名称: {process_node_response.name}")
        print(f"  - 节点ID: {process_node_response.node_base_id}")
        
        # 5. 创建结束节点
        print("\\n[步骤5] 创建结束节点")
        end_node_data = NodeCreate(
            name="结束节点",
            type=NodeType.END,
            task_description="工作流执行完成点",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=600,
            position_y=200
        )
        
        end_node_response = await node_service.create_node(end_node_data, user_response.user_id)
        print(f"SUCCESS: 结束节点创建成功")
        print(f"  - 节点名称: {end_node_response.name}")
        print(f"  - 节点ID: {end_node_response.node_base_id}")
        
        # 6. 创建节点连接
        print("\\n[步骤6] 创建节点连接")
        
        # 开始节点 -> 处理节点
        connection1_data = NodeConnectionCreate(
            from_node_base_id=start_node_response.node_base_id,
            to_node_base_id=process_node_response.node_base_id,
            workflow_base_id=workflow_response.workflow_base_id
        )
        
        connection1 = await node_service.create_node_connection(connection1_data, user_response.user_id)
        print(f"SUCCESS: 第一个连接创建成功")
        print(f"  - 连接: 开始节点 -> 处理节点")
        
        # 处理节点 -> 结束节点
        connection2_data = NodeConnectionCreate(
            from_node_base_id=process_node_response.node_base_id,
            to_node_base_id=end_node_response.node_base_id,
            workflow_base_id=workflow_response.workflow_base_id
        )
        
        connection2 = await node_service.create_node_connection(connection2_data, user_response.user_id)
        print(f"SUCCESS: 第二个连接创建成功")
        print(f"  - 连接: 处理节点 -> 结束节点")
        
        # 7. 验证创建结果
        print("\\n[步骤7] 验证创建结果")
        
        # 查询用户的所有工作流
        user_workflows = await workflow_service.get_user_workflows(user_response.user_id)
        print(f"用户工作流总数: {len(user_workflows)}")
        
        # 查询工作流的所有节点
        workflow_nodes = await node_service.get_workflow_nodes(
            workflow_response.workflow_base_id, user_response.user_id
        )
        print(f"工作流节点总数: {len(workflow_nodes)}")
        
        # 查询工作流的所有连接
        workflow_connections = await node_service.get_workflow_connections(
            workflow_response.workflow_base_id, user_response.user_id
        )
        print(f"工作流连接总数: {len(workflow_connections)}")
        
        # 8. 输出详细信息
        print("\\n" + "="*60)
        print("工作流创建完成 - 详细信息")
        print("="*60)
        print(f"创建者: {user_response.username}")
        print(f"工作流: {workflow_response.name}")
        print(f"描述: {workflow_response.description}")
        print(f"创建时间: {workflow_response.created_at}")
        
        print("\\n节点列表:")
        for i, node in enumerate(workflow_nodes, 1):
            print(f"  {i}. {node.name} ({node.type.value})")
            print(f"     任务描述: {node.task_description}")
            print(f"     位置坐标: ({node.position_x}, {node.position_y})")
            print(f"     节点ID: {node.node_base_id}")
        
        print("\\n连接列表:")
        for i, connection in enumerate(workflow_connections, 1):
            print(f"  {i}. 连接类型: {connection['connection_type']}")
            print(f"     从节点: {connection['from_node_base_id']}")
            print(f"     到节点: {connection['to_node_base_id']}")
        
        print("="*60)
        print("SUCCESS: 完整的工作流创建测试通过!")
        
        return {
            'user': user_response,
            'workflow': workflow_response,
            'nodes': workflow_nodes,
            'connections': workflow_connections
        }
        
    except Exception as e:
        print(f"\\nERROR: 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 关闭数据库连接
        await close_database()
        print("\\n==== 数据库连接已关闭 ====")


async def main():
    """主函数"""
    print("人机协作工作流构建框架 - API功能测试")
    print("="*60)
    
    result = await test_complete_workflow()
    
    if result:
        print(f"\\n🎉 测试全部通过!")
        print(f"   - 创建了1个用户")
        print(f"   - 创建了1个工作流")
        print(f"   - 创建了{len(result['nodes'])}个节点")
        print(f"   - 创建了{len(result['connections'])}个连接")
        return 0
    else:
        print("\\n❌ 测试失败!")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\\n程序执行出错: {e}")
        sys.exit(1)