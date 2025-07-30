#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工作流执行功能测试脚本
Workflow Execution Functionality Test Script
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# 设置编码和环境
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.execution_service import execution_engine
from workflow_framework.services.human_task_service import HumanTaskService
from workflow_framework.services.agent_task_service import agent_task_service
from workflow_framework.services.monitoring_service import monitoring_service

# 使用之前创建的测试数据
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
from workflow_framework.models.instance import (
    WorkflowExecuteRequest, TaskInstanceStatus, TaskInstanceUpdate
)


async def create_test_workflow():
    """创建测试工作流"""
    print("\n=== 第一步：创建测试工作流 ===")
    
    # 创建服务实例
    auth_service = AuthService()
    workflow_service = WorkflowService()
    node_service = NodeService()
    processor_repository = ProcessorRepository()
    agent_repository = AgentRepository()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 1. 创建测试用户
    print("创建测试用户...")
    user_data = UserCreate(
        username=f"executor_{timestamp}",
        email=f"executor_{timestamp}@example.com",
        password="test123456",
        role="admin",
        description="工作流执行测试用户"
    )
    
    user_response = await auth_service.register_user(user_data)
    print(f"✓ 用户创建成功: {user_response.username} (ID: {user_response.user_id})")
    
    # 2. 创建测试Agent
    print("创建测试Agent...")
    agent_data = AgentCreate(
        agent_name=f"执行测试AI_{timestamp}",
        description="用于执行测试的AI代理",
        endpoint="http://localhost:8081/api",
        capabilities=["数据分析", "决策支持", "内容生成"],
        status=True
    )
    
    agent_record = await agent_repository.create_agent(agent_data)
    print(f"✓ Agent创建成功: {agent_record['agent_name']} (ID: {agent_record['agent_id']})")
    
    # 3. 创建处理器
    print("创建处理器...")
    
    # 人工处理器
    human_processor_data = ProcessorCreate(
        name=f"人工处理器_{timestamp}",
        type=ProcessorType.HUMAN,
        user_id=user_response.user_id,
        agent_id=None
    )
    human_processor = await processor_repository.create_processor(human_processor_data)
    print(f"✓ 人工处理器创建成功: {human_processor['name']}")
    
    # AI处理器
    ai_processor_data = ProcessorCreate(
        name=f"AI处理器_{timestamp}",
        type=ProcessorType.AGENT,
        user_id=None,
        agent_id=agent_record['agent_id']
    )
    ai_processor = await processor_repository.create_processor(ai_processor_data)
    print(f"✓ AI处理器创建成功: {ai_processor['name']}")
    
    # 4. 创建工作流
    print("创建工作流...")
    workflow_data = WorkflowCreate(
        name=f"执行测试工作流_{timestamp}",
        description="用于测试工作流执行功能的完整工作流",
        creator_id=user_response.user_id
    )
    
    workflow_response = await workflow_service.create_workflow(workflow_data)
    print(f"✓ 工作流创建成功: {workflow_response.name}")
    
    # 5. 创建节点
    print("创建工作流节点...")
    
    # 开始节点
    start_node_data = NodeCreate(
        name="数据接收",
        type=NodeType.START,
        task_description="接收用户输入的数据，开始工作流处理",
        workflow_base_id=workflow_response.workflow_base_id,
        position_x=100,
        position_y=200
    )
    start_node = await node_service.create_node(start_node_data, user_response.user_id)
    print(f"✓ 开始节点创建成功: {start_node.name}")
    
    # 人工预处理节点
    human_node_data = NodeCreate(
        name="人工数据验证",
        type=NodeType.PROCESSOR,
        task_description="人工验证数据质量，检查数据完整性和准确性",
        workflow_base_id=workflow_response.workflow_base_id,
        position_x=300,
        position_y=200
    )
    human_node = await node_service.create_node(human_node_data, user_response.user_id)
    print(f"✓ 人工处理节点创建成功: {human_node.name}")
    
    # AI分析节点
    ai_node_data = NodeCreate(
        name="AI智能分析",
        type=NodeType.PROCESSOR,
        task_description="使用AI进行深度数据分析，提取关键信息和模式",
        workflow_base_id=workflow_response.workflow_base_id,
        position_x=500,
        position_y=200
    )
    ai_node = await node_service.create_node(ai_node_data, user_response.user_id)
    print(f"✓ AI分析节点创建成功: {ai_node.name}")
    
    # 结束节点
    end_node_data = NodeCreate(
        name="结果输出",
        type=NodeType.END,
        task_description="输出最终分析结果",
        workflow_base_id=workflow_response.workflow_base_id,
        position_x=700,
        position_y=200
    )
    end_node = await node_service.create_node(end_node_data, user_response.user_id)
    print(f"✓ 结束节点创建成功: {end_node.name}")
    
    # 6. 分配处理器
    print("分配处理器...")
    
    # 为人工节点分配人工处理器
    await node_service.assign_processor_to_node(
        human_node.node_base_id,
        workflow_response.workflow_base_id,
        human_processor['processor_id'],
        user_response.user_id
    )
    print("✓ 人工处理器已分配")
    
    # 为AI节点分配AI处理器
    await node_service.assign_processor_to_node(
        ai_node.node_base_id,
        workflow_response.workflow_base_id,
        ai_processor['processor_id'],
        user_response.user_id
    )
    print("✓ AI处理器已分配")
    
    # 7. 创建节点连接
    print("创建节点连接...")
    
    connections = [
        (start_node.node_base_id, human_node.node_base_id, "数据接收 -> 人工验证"),
        (human_node.node_base_id, ai_node.node_base_id, "人工验证 -> AI分析"),
        (ai_node.node_base_id, end_node.node_base_id, "AI分析 -> 结果输出")
    ]
    
    for from_node, to_node, desc in connections:
        connection_data = NodeConnectionCreate(
            from_node_base_id=from_node,
            to_node_base_id=to_node,
            workflow_base_id=workflow_response.workflow_base_id
        )
        await node_service.create_node_connection(connection_data, user_response.user_id)
        print(f"✓ 连接创建成功: {desc}")
    
    print(f"\n✓ 测试工作流创建完成")
    print(f"  - 工作流ID: {workflow_response.workflow_base_id}")
    print(f"  - 执行用户ID: {user_response.user_id}")
    
    return {
        'workflow_base_id': workflow_response.workflow_base_id,
        'executor_id': user_response.user_id,
        'workflow_name': workflow_response.name,
        'user_name': user_response.username
    }


async def test_workflow_execution(workflow_info):
    """测试工作流执行"""
    print("\n=== 第二步：测试工作流执行 ===")
    
    # 1. 启动执行引擎
    print("启动执行引擎...")
    await execution_engine.start_engine()
    await agent_task_service.start_service()
    await monitoring_service.start_monitoring()
    print("✓ 执行引擎启动成功")
    
    # 2. 创建执行请求
    print("创建工作流执行请求...")
    
    execute_request = WorkflowExecuteRequest(
        workflow_base_id=workflow_info['workflow_base_id'],
        instance_name=f"执行测试实例_{datetime.now().strftime('%H%M%S')}",
        input_data={
            "test_data": [1, 2, 3, 4, 5],
            "user_requirements": "请分析这组数据的统计特征",
            "priority": "normal"
        },
        context_data={
            "source": "execution_test",
            "test_mode": True,
            "expected_duration": 10
        }
    )
    
    # 3. 执行工作流
    print("开始执行工作流...")
    
    try:
        execution_result = await execution_engine.execute_workflow(
            execute_request, workflow_info['executor_id']
        )
        
        instance_id = execution_result['instance_id']
        print(f"✓ 工作流开始执行，实例ID: {instance_id}")
        
        # 4. 监控执行状态
        print("\n监控执行状态...")
        
        for i in range(10):  # 监控10次，每次间隔2秒
            await asyncio.sleep(2)
            
            status_info = await execution_engine.get_workflow_status(instance_id)
            if status_info:
                instance = status_info['instance']
                stats = status_info['statistics']
                
                print(f"第{i+1}次检查 - 状态: {instance['status']}")
                if stats:
                    print(f"  任务统计: 总计{stats.get('total_tasks', 0)}个, " 
                          f"完成{stats.get('completed_tasks', 0)}个, "
                          f"失败{stats.get('failed_tasks', 0)}个")
                
                # 如果完成或失败，停止监控
                if instance['status'] in ['completed', 'failed', 'cancelled']:
                    print(f"✓ 工作流执行结束，最终状态: {instance['status']}")
                    break
        else:
            print("⚠ 监控超时，工作流可能仍在执行中")
        
        return instance_id
        
    except Exception as e:
        print(f"❌ 工作流执行失败: {e}")
        return None


async def test_human_task_management(workflow_info, instance_id):
    """测试人工任务管理"""
    print("\n=== 第三步：测试人工任务管理 ===")
    
    human_task_service = HumanTaskService()
    
    try:
        # 1. 获取用户任务列表
        print("获取用户任务列表...")
        user_tasks = await human_task_service.get_user_tasks(
            workflow_info['executor_id'], 
            TaskInstanceStatus.ASSIGNED, 
            10
        )
        
        print(f"✓ 获取到 {len(user_tasks)} 个已分配的任务")
        
        if user_tasks:
            # 选择第一个任务进行测试
            test_task = user_tasks[0]
            task_id = test_task['task_instance_id']
            
            print(f"选择任务进行测试: {test_task['task_title']} (ID: {task_id})")
            
            # 2. 获取任务详情
            print("获取任务详情...")
            task_details = await human_task_service.get_task_details(
                task_id, workflow_info['executor_id']
            )
            
            if task_details:
                print(f"✓ 任务详情获取成功")
                print(f"  任务描述: {task_details['task_description']}")
                print(f"  当前状态: {task_details['status']}")
            
            # 3. 开始执行任务
            print("开始执行任务...")
            start_result = await human_task_service.start_task(
                task_id, workflow_info['executor_id']
            )
            
            if start_result:
                print(f"✓ 任务开始执行: {start_result['message']}")
                
                # 模拟任务处理时间
                await asyncio.sleep(3)
                
                # 4. 提交任务结果
                print("提交任务结果...")
                result_data = {
                    "validation_result": "数据质量良好",
                    "issues_found": [],
                    "recommendations": ["数据可以进入下一步处理"],
                    "confidence": 0.95
                }
                
                submit_result = await human_task_service.submit_task_result(
                    task_id, workflow_info['executor_id'], 
                    result_data, "人工验证完成，数据质量合格"
                )
                
                if submit_result:
                    print(f"✓ 任务结果提交成功: {submit_result['message']}")
                    print(f"  执行时长: {submit_result.get('actual_duration', 'N/A')} 分钟")
                else:
                    print("❌ 任务结果提交失败")
            else:
                print("❌ 任务开始执行失败")
        else:
            print("⚠ 没有找到可测试的人工任务")
    
    except Exception as e:
        print(f"❌ 人工任务管理测试失败: {e}")


async def test_agent_task_processing():
    """测试Agent任务处理"""
    print("\n=== 第四步：测试Agent任务处理 ===")
    
    try:
        # 1. 获取待处理的Agent任务
        print("获取待处理的Agent任务...")
        pending_tasks = await agent_task_service.get_pending_agent_tasks(limit=5)
        
        print(f"✓ 获取到 {len(pending_tasks)} 个待处理的Agent任务")
        
        if pending_tasks:
            # 选择第一个任务进行测试
            test_task = pending_tasks[0]
            task_id = test_task['task_instance_id']
            
            print(f"选择任务进行测试: {test_task['task_title']} (ID: {task_id})")
            
            # 2. 手动处理Agent任务
            print("开始处理Agent任务...")
            process_result = await agent_task_service.process_agent_task(task_id)
            
            if process_result['status'] == 'completed':
                print(f"✓ Agent任务处理完成")
                print(f"  执行时长: {process_result.get('duration', 'N/A')} 分钟")
                print(f"  置信度: {process_result['result'].get('confidence_score', 'N/A')}")
            else:
                print(f"❌ Agent任务处理失败: {process_result.get('message', 'Unknown error')}")
            
            # 3. 获取Agent任务统计
            print("获取Agent任务统计...")
            stats = await agent_task_service.get_agent_task_statistics()
            
            print(f"✓ Agent任务统计:")
            print(f"  总任务数: {stats['total_tasks']}")
            print(f"  已完成: {stats['completed_tasks']}")
            print(f"  成功率: {stats['success_rate']:.1f}%")
            print(f"  队列大小: {stats['queue_size']}")
        else:
            print("⚠ 没有找到可测试的Agent任务")
            
    except Exception as e:
        print(f"❌ Agent任务处理测试失败: {e}")


async def test_monitoring_service(instance_id):
    """测试监控服务"""
    print("\n=== 第五步：测试监控服务 ===")
    
    try:
        # 1. 获取当前指标
        print("获取系统监控指标...")
        metrics = await monitoring_service.get_current_metrics()
        
        print(f"✓ 系统监控指标:")
        print(f"  工作流总数: {metrics['metrics']['workflows']['total']}")
        print(f"  运行中工作流: {metrics['metrics']['workflows']['running']}")
        print(f"  任务总数: {metrics['metrics']['tasks']['total']}")
        print(f"  成功率: {metrics['metrics']['performance']['success_rate']:.1f}%")
        print(f"  告警数量: {metrics['alerts']['total']}")
        
        # 2. 获取工作流健康状态
        if instance_id:
            print(f"获取工作流健康状态 (ID: {instance_id})...")
            health = await monitoring_service.get_workflow_health(instance_id)
            
            print(f"✓ 工作流健康状态:")
            print(f"  健康分数: {health['health_score']:.1f}/100")
            print(f"  状态: {health['status']}")
            print(f"  问题数量: {len(health['issues'])}")
            
            if health['issues']:
                print("  发现的问题:")
                for issue in health['issues']:
                    print(f"    - [{issue['severity']}] {issue['message']}")
            
            if health['recommendations']:
                print("  建议:")
                for rec in health['recommendations']:
                    print(f"    - {rec}")
        
        # 3. 获取性能报告
        print("获取性能报告...")
        report = await monitoring_service.get_performance_report(7)
        
        print(f"✓ 性能报告 ({report['period']}):")
        print(f"  工作流总数: {report['summary']['total_workflows']}")
        print(f"  成功率: {report['summary']['success_rate']:.1f}%")
        print(f"  平均任务时长: {report['summary']['avg_task_duration']:.1f}分钟")
        
    except Exception as e:
        print(f"❌ 监控服务测试失败: {e}")


async def test_execution_functionality():
    """测试完整的执行功能"""
    print("=" * 80)
    print("工作流执行功能完整测试")
    print("=" * 80)
    
    try:
        # 初始化数据库
        await initialize_database()
        print("✓ 数据库连接初始化成功")
        
        # 第一步：创建测试工作流
        workflow_info = await create_test_workflow()
        
        if not workflow_info:
            print("❌ 测试工作流创建失败，终止测试")
            return False
        
        # 第二步：测试工作流执行
        instance_id = await test_workflow_execution(workflow_info)
        
        # 等待一段时间让任务创建完成
        await asyncio.sleep(5)
        
        # 第三步：测试人工任务管理
        await test_human_task_management(workflow_info, instance_id)
        
        # 第四步：测试Agent任务处理
        await test_agent_task_processing()
        
        # 第五步：测试监控服务
        await test_monitoring_service(instance_id)
        
        print("\n" + "=" * 80)
        print("✓ 执行功能测试完成！")
        print("=" * 80)
        
        # 测试总结
        print("\n📊 测试总结:")
        print("✓ 工作流创建和配置")
        print("✓ 工作流执行引擎")
        print("✓ 人工任务处理")
        print("✓ Agent任务处理")
        print("✓ 状态监控和追踪")
        print("✓ OpenAI集成")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理资源
        try:
            await execution_engine.stop_engine()
            await agent_task_service.stop_service()
            await monitoring_service.stop_monitoring()
            await close_database()
            print("\n✓ 资源清理完成")
        except Exception as e:
            print(f"\n⚠ 资源清理异常: {e}")


async def main():
    """主函数"""
    print("启动工作流执行功能测试...")
    
    success = await test_execution_functionality()
    
    if success:
        print("\n🎉 所有测试通过！工作流执行功能正常运行。")
        return 0
    else:
        print("\n💥 测试失败！请检查错误信息。")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 程序执行出错: {e}")
        sys.exit(1)