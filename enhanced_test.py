#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sys
import os
from datetime import datetime

# 设置编码和环境
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.auth_service import AuthService
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService
from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
from workflow_framework.repositories.agent.agent_repository import AgentRepository
from workflow_framework.models.user import UserCreate
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType, NodeConnectionCreate
from workflow_framework.models.processor import ProcessorCreate, ProcessorType
from workflow_framework.models.agent import AgentCreate


async def test_enhanced_workflow():
    """测试增强的工作流创建功能，包含processor测试"""
    
    try:
        # 初始化数据库
        print("=" * 60)
        print("人机协作工作流构建框架 - 增强测试")
        print("=" * 60)
        print("正在初始化数据库连接...")
        await initialize_database()
        
        # 创建服务实例
        auth_service = AuthService()
        workflow_service = WorkflowService()
        node_service = NodeService()
        processor_repository = ProcessorRepository()
        agent_repository = AgentRepository()
        
        print("开始测试完整的工作流创建流程...")
        
        # 1. 创建测试用户
        print("\n[步骤1] 创建测试用户")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        user_data = UserCreate(
            username=f"test_user_{timestamp}",
            email=f"test_{timestamp}@example.com",
            password="test123456",
            role="admin",
            description="工作流测试用户"
        )
        
        user_response = await auth_service.register_user(user_data)
        print(f"SUCCESS: 用户创建成功")
        print(f"  - 用户名: {user_response.username}")
        print(f"  - 用户ID: {user_response.user_id}")
        
        # 2. 创建测试Agent
        print("\n[步骤2] 创建测试Agent")
        agent_data = AgentCreate(
            agent_name=f"AI助手_{timestamp}",
            description="智能数据处理助手",
            endpoint="http://localhost:8081/api",
            capabilities=["数据分析", "文本处理", "决策支持"],
            status=True
        )
        
        agent_record = await agent_repository.create_agent(agent_data)
        print(f"SUCCESS: Agent创建成功")
        print(f"  - Agent名称: {agent_record['agent_name']}")
        print(f"  - Agent ID: {agent_record['agent_id']}")
        
        # 3. 创建处理器
        print("\n[步骤3] 创建处理器")
        
        # 创建人工处理器
        human_processor_data = ProcessorCreate(
            name=f"人工处理器_{timestamp}",
            type=ProcessorType.HUMAN,
            user_id=user_response.user_id,
            agent_id=None
        )
        
        human_processor = await processor_repository.create_processor(human_processor_data)
        print(f"SUCCESS: 人工处理器创建成功")
        print(f"  - 处理器名称: {human_processor['name']}")
        print(f"  - 处理器ID: {human_processor['processor_id']}")
        print(f"  - 处理器类型: {human_processor['type']}")
        
        # 创建AI处理器
        ai_processor_data = ProcessorCreate(
            name=f"AI处理器_{timestamp}",
            type=ProcessorType.AGENT,
            user_id=None,
            agent_id=agent_record['agent_id']
        )
        
        ai_processor = await processor_repository.create_processor(ai_processor_data)
        print(f"SUCCESS: AI处理器创建成功")
        print(f"  - 处理器名称: {ai_processor['name']}")
        print(f"  - 处理器ID: {ai_processor['processor_id']}")
        print(f"  - 处理器类型: {ai_processor['type']}")
        
        # 创建混合处理器
        mix_processor_data = ProcessorCreate(
            name=f"混合处理器_{timestamp}",
            type=ProcessorType.MIX,
            user_id=user_response.user_id,
            agent_id=agent_record['agent_id']
        )
        
        mix_processor = await processor_repository.create_processor(mix_processor_data)
        print(f"SUCCESS: 混合处理器创建成功")
        print(f"  - 处理器名称: {mix_processor['name']}")
        print(f"  - 处理器ID: {mix_processor['processor_id']}")
        print(f"  - 处理器类型: {mix_processor['type']}")
        
        # 4. 创建工作流
        print("\n[步骤4] 创建工作流")
        workflow_data = WorkflowCreate(
            name=f"智能协作工作流_{timestamp}",
            description="包含人工智能协作的完整工作流，展示人机协作能力",
            creator_id=user_response.user_id
        )
        
        workflow_response = await workflow_service.create_workflow(workflow_data)
        print(f"SUCCESS: 工作流创建成功")
        print(f"  - 工作流名称: {workflow_response.name}")
        print(f"  - 工作流ID: {workflow_response.workflow_base_id}")
        
        # 5. 创建节点
        print("\n[步骤5] 创建工作流节点")
        
        # 开始节点
        start_node_data = NodeCreate(
            name="工作流开始",
            type=NodeType.START,
            task_description="工作流启动，接收初始数据",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=50,
            position_y=200
        )
        
        start_node = await node_service.create_node(start_node_data, user_response.user_id)
        print(f"SUCCESS: 开始节点创建成功 - {start_node.name}")
        
        # 人工预处理节点
        human_process_node_data = NodeCreate(
            name="人工数据预处理",
            type=NodeType.PROCESSOR,
            task_description="人工进行数据清洗、验证和初步分析",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=250,
            position_y=150
        )
        
        human_process_node = await node_service.create_node(human_process_node_data, user_response.user_id)
        print(f"SUCCESS: 人工处理节点创建成功 - {human_process_node.name}")
        
        # AI分析节点
        ai_analysis_node_data = NodeCreate(
            name="AI智能分析",
            type=NodeType.PROCESSOR,
            task_description="使用AI进行深度数据分析和模式识别",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=450,
            position_y=150
        )
        
        ai_analysis_node = await node_service.create_node(ai_analysis_node_data, user_response.user_id)
        print(f"SUCCESS: AI分析节点创建成功 - {ai_analysis_node.name}")
        
        # 人机协作决策节点
        collaborative_node_data = NodeCreate(
            name="人机协作决策",
            type=NodeType.PROCESSOR,
            task_description="结合人工经验和AI建议做出最终决策",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=650,
            position_y=200
        )
        
        collaborative_node = await node_service.create_node(collaborative_node_data, user_response.user_id)
        print(f"SUCCESS: 协作决策节点创建成功 - {collaborative_node.name}")
        
        # 结束节点
        end_node_data = NodeCreate(
            name="工作流完成",
            type=NodeType.END,
            task_description="输出最终结果，工作流结束",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=850,
            position_y=200
        )
        
        end_node = await node_service.create_node(end_node_data, user_response.user_id)
        print(f"SUCCESS: 结束节点创建成功 - {end_node.name}")
        
        # 6. 为节点分配处理器
        print("\n[步骤6] 为节点分配处理器")
        
        # 为人工处理节点分配人工处理器
        human_assignment = await node_service.assign_processor_to_node(
            human_process_node.node_base_id,
            workflow_response.workflow_base_id,
            human_processor['processor_id'],
            user_response.user_id
        )
        print(f"SUCCESS: 人工处理器已分配给人工预处理节点")
        
        # 为AI分析节点分配AI处理器
        ai_assignment = await node_service.assign_processor_to_node(
            ai_analysis_node.node_base_id,
            workflow_response.workflow_base_id,
            ai_processor['processor_id'],
            user_response.user_id
        )
        print(f"SUCCESS: AI处理器已分配给AI分析节点")
        
        # 为协作决策节点分配混合处理器
        mix_assignment = await node_service.assign_processor_to_node(
            collaborative_node.node_base_id,
            workflow_response.workflow_base_id,
            mix_processor['processor_id'],
            user_response.user_id
        )
        print(f"SUCCESS: 混合处理器已分配给协作决策节点")
        
        # 7. 创建节点连接
        print("\n[步骤7] 创建节点连接")
        
        connections = [
            (start_node.node_base_id, human_process_node.node_base_id, "开始 -> 人工预处理"),
            (human_process_node.node_base_id, ai_analysis_node.node_base_id, "人工预处理 -> AI分析"),
            (ai_analysis_node.node_base_id, collaborative_node.node_base_id, "AI分析 -> 协作决策"),
            (collaborative_node.node_base_id, end_node.node_base_id, "协作决策 -> 结束")
        ]
        
        for from_node, to_node, desc in connections:
            connection_data = NodeConnectionCreate(
                from_node_base_id=from_node,
                to_node_base_id=to_node,
                workflow_base_id=workflow_response.workflow_base_id
            )
            
            await node_service.create_node_connection(connection_data, user_response.user_id)
            print(f"SUCCESS: 连接创建成功 - {desc}")
        
        # 8. 验证和统计
        print("\n[步骤8] 验证创建结果")
        
        # 获取工作流统计
        user_workflows = await workflow_service.get_user_workflows(user_response.user_id)
        workflow_nodes = await node_service.get_workflow_nodes(
            workflow_response.workflow_base_id, user_response.user_id
        )
        workflow_connections = await node_service.get_workflow_connections(
            workflow_response.workflow_base_id, user_response.user_id
        )
        
        # 获取节点处理器分配情况
        processor_assignments = {}
        for node in workflow_nodes:
            if node.type == NodeType.PROCESSOR:
                processors = await node_service.get_node_processors(
                    node.node_base_id, workflow_response.workflow_base_id, user_response.user_id
                )
                processor_assignments[node.name] = processors
        
        print(f"工作流总数: {len(user_workflows)}")
        print(f"节点总数: {len(workflow_nodes)}")
        print(f"连接总数: {len(workflow_connections)}")
        print(f"处理器分配总数: {sum(len(procs) for procs in processor_assignments.values())}")
        
        # 9. 输出详细报告
        print("\n" + "=" * 80)
        print("工作流创建完成 - 详细报告")
        print("=" * 80)
        print(f"创建者: {user_response.username}")
        print(f"工作流: {workflow_response.name}")
        print(f"描述: {workflow_response.description}")
        print(f"创建时间: {workflow_response.created_at}")
        
        print(f"\n创建的Agent:")
        print(f"  - {agent_record['agent_name']} (ID: {agent_record['agent_id']})")
        
        print(f"\n创建的处理器:")
        processors = [human_processor, ai_processor, mix_processor]
        for i, proc in enumerate(processors, 1):
            print(f"  {i}. {proc['name']} ({proc['type']})")
            print(f"     ID: {proc['processor_id']}")
        
        print(f"\n工作流节点:")
        for i, node in enumerate(workflow_nodes, 1):
            print(f"  {i}. {node.name} ({node.type.value})")
            print(f"     任务: {node.task_description}")
            print(f"     位置: ({node.position_x}, {node.position_y})")
            if node.name in processor_assignments:
                procs = processor_assignments[node.name]
                if procs:
                    print(f"     处理器: {procs[0]['processor_name']} ({procs[0]['processor_type']})")
        
        print(f"\n节点连接:")
        for i, connection in enumerate(workflow_connections, 1):
            print(f"  {i}. {connection['from_node_base_id']} -> {connection['to_node_base_id']}")
            print(f"     类型: {connection['connection_type']}")
        
        print("=" * 80)
        print("SUCCESS: 完整的人机协作工作流创建测试成功!")
        print("=" * 80)
        
        return {
            'user': user_response,
            'agent': agent_record,
            'processors': processors,
            'workflow': workflow_response,
            'nodes': workflow_nodes,
            'connections': workflow_connections,
            'assignments': processor_assignments
        }
        
    except Exception as e:
        print(f"\nERROR: 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await close_database()
        print("\n数据库连接已关闭")


async def main():
    """主函数"""
    result = await test_enhanced_workflow()
    
    if result:
        print(f"\n[测试总结]")
        print(f"- 创建用户: 1个")
        print(f"- 创建Agent: 1个") 
        print(f"- 创建处理器: 3个 (人工/AI/混合)")
        print(f"- 创建工作流: 1个")
        print(f"- 创建节点: {len(result['nodes'])}个")
        print(f"- 创建连接: {len(result['connections'])}个")
        print(f"- 处理器分配: {sum(len(procs) for procs in result['assignments'].values())}个")
        print(f"\n全部测试通过!")
        return 0
    else:
        print(f"\n测试失败!")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序执行出错: {e}")
        sys.exit(1)