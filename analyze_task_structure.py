#!/usr/bin/env python3
"""
解析真实Task实例结构
Analyze Real Task Instance Structure
"""

import asyncio
import uuid
import json
from datetime import datetime
from pprint import pprint

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.auth_service import AuthService
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService
from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
from workflow_framework.repositories.instance.task_instance_repository import TaskInstanceRepository
from workflow_framework.models.user import UserCreate
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType, NodeConnectionCreate
from workflow_framework.models.processor import ProcessorCreate, ProcessorType
from workflow_framework.models.instance import TaskInstanceCreate, TaskInstanceType, TaskInstanceStatus


async def create_and_analyze_task():
    """创建并解析真实的task实例"""
    
    await initialize_database()
    
    try:
        print("=== 真实Task实例结构解析 ===")
        print()
        
        # 1. 准备基础数据
        print("1. 创建基础数据...")
        auth_service = AuthService()
        workflow_service = WorkflowService()
        node_service = NodeService()
        processor_repo = ProcessorRepository()
        task_repo = TaskInstanceRepository()
        
        # 创建用户
        user_data = UserCreate(
            username=f"task_analyzer_{datetime.now().strftime('%H%M%S')}",
            email=f"task_{datetime.now().strftime('%H%M%S')}@test.com",
            password="test123456",
            role="admin",
            description="任务分析测试用户"
        )
        user = await auth_service.register_user(user_data)
        print(f"创建用户: {user.username}")
        
        # 创建工作流
        workflow_data = WorkflowCreate(
            name=f"任务分析测试工作流_{datetime.now().strftime('%H%M%S')}",
            description="用于分析Task实例结构的测试工作流",
            creator_id=user.user_id
        )
        workflow = await workflow_service.create_workflow(workflow_data)
        print(f"创建工作流: {workflow.name}")
        
        # 创建处理节点
        node_data = NodeCreate(
            name="数据分析节点",
            type=NodeType.PROCESSOR,
            task_description="执行复杂的数据分析任务，包含输入数据处理、AI模型调用和结果输出",
            workflow_base_id=workflow.workflow_base_id,
            position_x=200,
            position_y=150
        )
        node = await node_service.create_node(node_data, user.user_id)
        print(f"创建节点: {node.name}")
        
        # 先创建Agent
        from workflow_framework.repositories.agent.agent_repository import AgentRepository
        from workflow_framework.models.agent import AgentCreate
        
        agent_repo = AgentRepository()
        agent_data = AgentCreate(
            agent_name="GPT-4数据分析师",
            description="专业的数据分析AI助手",
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            model_name="gpt-4",
            is_autonomous=False
        )
        agent = await agent_repo.create_agent(agent_data)
        print(f"创建Agent: {agent['agent_name']}")
        
        # 创建Agent处理器
        agent_processor_data = ProcessorCreate(
            name="GPT数据分析师",
            type=ProcessorType.AGENT,
            agent_id=agent['agent_id']
        )
        processor = await processor_repo.create_processor(agent_processor_data)
        print(f"创建处理器: {processor['name']}")
        
        # 关联处理器到节点
        await node_service.assign_processor_to_node(
            node.node_base_id,
            workflow.workflow_base_id,
            processor['processor_id'],
            user.user_id
        )
        print("处理器已关联到节点")
        print()
        
        # 2. 创建复杂的Task实例
        print("2. 创建复杂的Task实例...")
        
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=processor['processor_id'],
            task_type=TaskInstanceType.AGENT,
            task_title="电商用户行为数据深度分析",
            task_description="""
            对电商平台的用户行为数据进行深度分析，包括：
            1. 用户访问路径分析
            2. 购买转化率计算
            3. 用户画像构建
            4. 商品推荐优化建议
            5. 季节性趋势识别
            """,
            input_data={
                "raw_data": {
                    "user_sessions": [
                        {
                            "session_id": "sess_001",
                            "user_id": "user_12345",
                            "start_time": "2024-01-15T09:00:00Z",
                            "end_time": "2024-01-15T09:25:00Z",
                            "pages_visited": [
                                {"page": "/home", "duration": 30},
                                {"page": "/category/electronics", "duration": 120},
                                {"page": "/product/laptop-abc", "duration": 180},
                                {"page": "/cart", "duration": 60},
                                {"page": "/checkout", "duration": 90}
                            ],
                            "actions": [
                                {"action": "view_product", "product_id": "laptop-abc", "timestamp": "2024-01-15T09:05:00Z"},
                                {"action": "add_to_cart", "product_id": "laptop-abc", "quantity": 1, "timestamp": "2024-01-15T09:15:00Z"},
                                {"action": "purchase", "order_id": "order_789", "amount": 1299.99, "timestamp": "2024-01-15T09:22:00Z"}
                            ]
                        }
                    ],
                    "products": {
                        "laptop-abc": {
                            "name": "高性能笔记本电脑",
                            "category": "electronics",
                            "price": 1299.99,
                            "tags": ["laptop", "gaming", "high-performance"],
                            "inventory": 50
                        }
                    },
                    "user_profiles": {
                        "user_12345": {
                            "age_range": "25-34",
                            "location": "北京",
                            "purchase_history": 15,
                            "avg_order_value": 850.00,
                            "preferred_categories": ["electronics", "books", "sports"]
                        }
                    }
                },
                "analysis_parameters": {
                    "time_window": "last_30_days",
                    "min_confidence_threshold": 0.8,
                    "include_predictive_modeling": True,
                    "export_format": "json",
                    "generate_visualizations": False
                },
                "business_context": {
                    "company": "TechStore电商平台",
                    "industry": "电子商务",
                    "goals": ["提升转化率", "优化用户体验", "增加客户生命周期价值"],
                    "constraints": ["数据隐私合规", "实时性要求", "成本控制"]
                }
            },
            output_data={},
            instructions="""
            请按照以下步骤进行分析：
            1. 数据清洗和预处理
            2. 用户行为模式识别
            3. 转化漏斗分析
            4. 异常行为检测
            5. 商业价值评估
            6. 可操作的优化建议
            
            输出格式要求：
            - 提供执行摘要
            - 包含关键指标和KPI
            - 给出置信度评估
            - 提供具体的行动建议
            """,
            context_data={
                "execution_context": {
                    "triggered_by": "scheduled_analysis",
                    "execution_environment": "production",
                    "resource_allocation": {
                        "cpu_limit": "2 cores",
                        "memory_limit": "4GB",
                        "timeout": "300 seconds"
                    }
                },
                "workflow_metadata": {
                    "workflow_version": "v1.2.3",
                    "node_position": 2,
                    "total_nodes": 5,
                    "upstream_results": {
                        "data_validation": "passed",
                        "preprocessing": "completed"
                    }
                },
                "ai_configuration": {
                    "model_preferences": ["gpt-4", "claude-3"],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                    "use_system_prompt": True
                }
            },
            priority=2,
            assigned_user_id=None,
            assigned_agent_id=uuid.uuid4(),
            estimated_duration=15,
            dependencies=["task_001", "task_002"],
            tags=["data-analysis", "user-behavior", "e-commerce", "ai-processing"],
            metadata={
                "created_by_system": "workflow_engine_v2",
                "cost_center": "analytics_department",
                "compliance_flags": ["gdpr", "ccpa"],
                "performance_requirements": {
                    "max_processing_time": 900,
                    "accuracy_threshold": 0.95,
                    "resource_efficiency": "high"
                }
            }
        )
        
        # 创建Task实例
        task_instance = await task_repo.create_task(task_data)
        print(f"创建Task实例: {task_instance['task_instance_id']}")
        print()
        
        # 3. 详细解析Task实例结构
        print("3. Task实例结构详细解析...")
        print("=" * 60)
        
        # 获取完整的Task实例数据
        full_task = await task_repo.get_task_by_id(task_instance['task_instance_id'])
        
        print("🔍 基础标识信息:")
        print(f"  Task ID: {full_task['task_instance_id']}")
        print(f"  Node Instance ID: {full_task['node_instance_id']}")
        print(f"  Workflow Instance ID: {full_task['workflow_instance_id']}")
        print(f"  Processor ID: {full_task['processor_id']}")
        print()
        
        print("📋 任务基本信息:")
        print(f"  标题: {full_task['task_title']}")
        print(f"  类型: {full_task['task_type']}")
        print(f"  状态: {full_task['status']}")
        print(f"  优先级: {full_task['priority']}")
        print(f"  预估时长: {full_task['estimated_duration']} 分钟")
        print()
        
        print("📝 任务描述:")
        description_lines = full_task['task_description'].strip().split('\n')
        for line in description_lines[:3]:  # 显示前3行
            print(f"  {line.strip()}")
        if len(description_lines) > 3:
            print(f"  ... (共{len(description_lines)}行)")
        print()
        
        print("📊 输入数据结构:")
        input_data = full_task['input_data']
        if isinstance(input_data, dict):
            print(f"  主要键: {list(input_data.keys())}")
            for key, value in input_data.items():
                if isinstance(value, dict):
                    print(f"  {key}: {{字典, {len(value)} 个字段}}")
                elif isinstance(value, list):
                    print(f"  {key}: [列表, {len(value)} 个元素]")
                else:
                    print(f"  {key}: {type(value).__name__}")
        print()
        
        print("🎯 处理指令:")
        instructions_lines = full_task['instructions'].strip().split('\n')
        for line in instructions_lines[:5]:
            if line.strip():
                print(f"  {line.strip()}")
        print()
        
        print("🔧 上下文数据:")
        context_data = full_task['context_data']
        if isinstance(context_data, dict):
            for key, value in context_data.items():
                if isinstance(value, dict):
                    print(f"  {key}: {{包含 {len(value)} 个配置项}}")
                else:
                    print(f"  {key}: {type(value).__name__}")
        print()
        
        print("🏷️ 元数据和标签:")
        print(f"  标签: {full_task.get('tags', [])}")
        metadata = full_task.get('metadata', {})
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                print(f"  {key}: {value}")
        print()
        
        print("⏰ 时间信息:")
        print(f"  创建时间: {full_task['created_at']}")
        print(f"  更新时间: {full_task.get('updated_at', 'N/A')}")
        print(f"  开始时间: {full_task.get('started_at', 'N/A')}")
        print(f"  完成时间: {full_task.get('completed_at', 'N/A')}")
        print()
        
        print("📈 执行统计:")
        print(f"  重试次数: {full_task.get('retry_count', 0)}")
        print(f"  实际耗时: {full_task.get('actual_duration', 'N/A')} 分钟")
        print(f"  错误信息: {full_task.get('error_message', 'N/A')}")
        print()
        
        # 4. 展示Task在整个系统中的关联关系
        print("4. Task实例的系统关联关系...")
        print("=" * 60)
        
        print("🔗 数据库关联:")
        print(f"  task_instance ←→ node_instance (节点实例)")
        print(f"  task_instance ←→ workflow_instance (工作流实例)")
        print(f"  task_instance ←→ processor (处理器)")
        print(f"  processor ←→ user/agent (执行者)")
        print()
        
        print("🔄 生命周期状态流转:")
        status_flow = [
            "PENDING (待处理)",
            "ASSIGNED (已分配)", 
            "IN_PROGRESS (执行中)",
            "COMPLETED (已完成)",
            "FAILED (失败)",
            "CANCELLED (已取消)"
        ]
        for i, status in enumerate(status_flow):
            if i < len(status_flow) - 1:
                print(f"  {status} → ")
            else:
                print(f"  {status}")
        print()
        
        print("⚡ 处理流程:")
        process_steps = [
            "1. ExecutionService 创建Task实例",
            "2. 根据processor_type路由到对应服务",
            "3. AgentTaskService 接收并排队",
            "4. 工作协程从队列取出任务",
            "5. 调用OpenAI API进行处理",
            "6. 更新Task状态和结果",
            "7. 通过回调通知ExecutionService",
            "8. 继续工作流下一步骤"
        ]
        for step in process_steps:
            print(f"  {step}")
        print()
        
        # 5. JSON格式完整输出
        print("5. 完整Task实例JSON结构 (示例):")
        print("=" * 60)
        
        # 创建一个简化版本用于演示
        sample_task = {
            "task_instance_id": str(full_task['task_instance_id']),
            "task_title": full_task['task_title'][:30] + "...",
            "task_type": full_task['task_type'],
            "status": full_task['status'],
            "input_data": {
                "raw_data": "{ ... 复杂的业务数据 ... }",
                "analysis_parameters": "{ ... 分析配置 ... }",
                "business_context": "{ ... 业务上下文 ... }"
            },
            "context_data": {
                "execution_context": "{ ... 执行环境配置 ... }",
                "workflow_metadata": "{ ... 工作流元数据 ... }",
                "ai_configuration": "{ ... AI模型配置 ... }"
            },
            "metadata": {
                "performance_requirements": "{ ... 性能要求 ... }",
                "compliance_flags": ["gdpr", "ccpa"]
            },
            "created_at": str(full_task['created_at']),
            "relationships": {
                "node_instance_id": str(full_task['node_instance_id']),
                "workflow_instance_id": str(full_task['workflow_instance_id']),
                "processor_id": str(full_task['processor_id'])
            }
        }
        
        print(json.dumps(sample_task, indent=2, ensure_ascii=False))
        print()
        
        print("=== Task实例结构解析完成 ===")
        
        return task_instance
        
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    finally:
        await close_database()


async def main():
    """主函数"""
    print("Task实例结构分析工具")
    print("=" * 40)
    print()
    
    try:
        task = await create_and_analyze_task()
        
        if task:
            print(f"\n✅ 成功创建并解析Task实例: {task['task_instance_id']}")
            print("\n📚 关键要点:")
            print("• Task实例包含完整的业务数据和执行上下文")
            print("• 支持复杂的输入数据结构和处理指令")
            print("• 具备完整的生命周期管理和状态跟踪")
            print("• 与工作流系统的其他组件深度集成")
            print("• 提供灵活的元数据和标签系统")
        else:
            print("\n❌ Task实例创建失败")
        
    except Exception as e:
        print(f"执行异常: {e}")
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(main())