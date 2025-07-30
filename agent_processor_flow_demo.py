#!/usr/bin/env python3
"""
Agent Processor 运行流程演示
Agent Processor Flow Demonstration
"""

import asyncio
import uuid
from datetime import datetime

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.agent_task_service import agent_task_service
from workflow_framework.utils.openai_client import openai_client
from workflow_framework.repositories.instance.task_instance_repository import TaskInstanceRepository
from workflow_framework.models.instance import TaskInstanceCreate, TaskInstanceType, TaskInstanceStatus


async def demonstrate_agent_processor_flow():
    """演示Agent Processor的完整运行流程"""
    
    await initialize_database()
    
    try:
        print("=== Agent Processor 运行流程演示 ===")
        print()
        
        # 1. 模拟创建一个Agent任务
        print("1. 创建Agent任务实例...")
        task_repo = TaskInstanceRepository()
        
        # 创建任务数据
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=uuid.uuid4(),
            task_type=TaskInstanceType.AGENT,
            task_title="AI数据分析任务",
            task_description="分析用户行为数据，识别关键模式和趋势",
            input_data={
                "user_data": [
                    {"user_id": 1, "action": "login", "timestamp": "2024-01-15 09:00:00"},
                    {"user_id": 1, "action": "view_product", "timestamp": "2024-01-15 09:05:00"},
                    {"user_id": 1, "action": "add_to_cart", "timestamp": "2024-01-15 09:10:00"},
                    {"user_id": 2, "action": "login", "timestamp": "2024-01-15 10:00:00"},
                    {"user_id": 2, "action": "search", "timestamp": "2024-01-15 10:05:00"}
                ],
                "analysis_type": "behavior_pattern",
                "time_range": "last_30_days"
            },
            instructions="请识别用户行为模式，分析转化率，并提供优化建议",
            priority=1,
            assigned_agent_id=uuid.uuid4(),
            estimated_duration=10
        )
        
        # 创建任务实例
        task_instance = await task_repo.create_task(task_data)
        task_id = task_instance['task_instance_id']
        print(f"✅ 任务实例创建成功: {task_id}")
        print(f"   任务标题: {task_instance['task_title']}")
        print(f"   任务类型: {task_instance['task_type']}")
        print()
        
        # 2. 演示AgentTaskService处理流程
        print("2. AgentTaskService处理流程...")
        print("   步骤2.1: 启动Agent任务服务")
        await agent_task_service.start_service()
        print("   ✅ Agent任务服务已启动")
        
        print("   步骤2.2: 提交任务到处理队列")
        submit_result = await agent_task_service.submit_task_to_agent(task_id, priority=1)
        print(f"   ✅ 任务提交结果: {submit_result['status']}")
        print(f"   消息: {submit_result['message']}")
        print()
        
        # 3. 等待并观察任务处理
        print("3. 观察任务处理过程...")
        
        # 等待一段时间让服务处理任务
        print("   等待Agent服务处理任务...")
        await asyncio.sleep(5)
        
        # 检查任务状态
        final_task = await task_repo.get_task_by_id(task_id)
        print(f"   最终任务状态: {final_task['status']}")
        
        if final_task['status'] == TaskInstanceStatus.COMPLETED.value:
            print("   ✅ 任务处理完成!")
            print("   处理结果:")
            output_data = final_task.get('output_data', {})
            if output_data:
                print(f"     - 分析结果: {output_data.get('analysis', 'N/A')}")
                print(f"     - 置信度: {output_data.get('confidence_score', 'N/A')}")
                print(f"     - 建议数量: {len(output_data.get('recommendations', []))}")
                print(f"     - 使用的模型: {output_data.get('model_used', 'N/A')}")
        else:
            print(f"   ⚠️ 任务状态: {final_task['status']}")
            if final_task.get('error_message'):
                print(f"   错误信息: {final_task['error_message']}")
        
        print()
        
        # 4. 演示直接的OpenAI客户端调用
        print("4. 直接演示OpenAI客户端调用...")
        
        # 构建任务数据
        openai_task_data = {
            'task_id': str(task_id),
            'task_title': '用户行为分析',
            'task_description': '分析电商用户的购买行为模式',
            'input_data': {
                'sessions': 150,
                'conversions': 23,
                'bounce_rate': 0.65,
                'avg_session_duration': 245
            },
            'instructions': '请分析这些指标并提供优化建议',
            'context': {
                'business_type': 'e-commerce',
                'analysis_period': '30_days'
            }
        }
        
        print("   调用OpenAI客户端处理任务...")
        ai_result = await openai_client.process_task(openai_task_data)
        
        if ai_result['success']:
            print("   ✅ OpenAI处理成功!")
            print(f"   使用模型: {ai_result['model']}")
            result_data = ai_result['result']
            print(f"   分析摘要: {result_data['analysis']}")
            print(f"   置信度: {result_data['confidence']}")
            print(f"   建议数量: {len(result_data['recommendations'])}")
            print("   主要建议:")
            for i, rec in enumerate(result_data['recommendations'][:3], 1):
                print(f"     {i}. {rec}")
            
            # 显示token使用情况
            usage = ai_result.get('usage', {})
            print(f"   Token使用: {usage.get('total_tokens', 0)} (提示: {usage.get('prompt_tokens', 0)}, 完成: {usage.get('completion_tokens', 0)})")
        else:
            print(f"   ❌ OpenAI处理失败: {ai_result['error']}")
        
        print()
        
        # 5. 演示不同类型的AI处理能力
        print("5. 演示其他AI处理能力...")
        
        # 情感分析
        print("   5.1 情感分析:")
        sentiment_text = "这个产品非常好用，界面设计很棒，功能也很完善，我很满意这次购买体验！"
        sentiment_result = await openai_client.analyze_sentiment(sentiment_text)
        print(f"   ✅ 情感: {sentiment_result['sentiment']}, 置信度: {sentiment_result['confidence']}")
        
        # 文本摘要
        print("   5.2 文本摘要:")
        long_text = """
        在现代数字化业务环境中，数据分析已成为企业决策的重要依据。通过对用户行为数据的深入分析，
        企业可以更好地理解客户需求，优化产品设计，提升用户体验。机器学习和人工智能技术的发展，
        为数据分析提供了更强大的工具和方法。企业应该建立完善的数据收集、处理和分析体系，
        以支持数据驱动的决策制定过程。
        """
        summary_result = await openai_client.summarize_text(long_text.strip())
        print(f"   ✅ 摘要: {summary_result['summary']}")
        print(f"   压缩比: {summary_result['compression_ratio']:.2f}")
        
        # 代码生成
        print("   5.3 代码生成:")
        code_desc = "创建一个函数来计算数组的平均值"
        code_result = await openai_client.generate_code(code_desc, 'python')
        print(f"   ✅ 生成了 {code_result['lines_of_code']} 行 {code_result['language']} 代码")
        print("   生成的代码示例:")
        print("   " + "\n   ".join(code_result['code'].split('\n')[:5]))  # 显示前5行
        print("   ...")
        
        print()
        print("=== Agent Processor 流程演示完成 ===")
        
        return True
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await agent_task_service.stop_service()
        await close_database()


async def show_agent_api_integration():
    """展示Agent与API集成的详细信息"""
    
    print("\n=== Agent API集成详细说明 ===")
    print()
    
    print("📍 1. Agent任务处理流程:")
    print("   ExecutionService._process_agent_task()")
    print("   ↓")
    print("   AgentTaskService.submit_task_to_agent()")
    print("   ↓")
    print("   AgentTaskService.process_agent_task()")
    print("   ↓")
    print("   AgentTaskService._call_agent_api()")
    print("   ↓")
    print("   根据Agent类型选择处理方式:")
    print("   • OpenAI: _process_with_openai()")
    print("   • Claude: _process_with_claude()")
    print("   • HTTP API: _process_with_http_api()")
    print()
    
    print("📍 2. OpenAI API调用流程:")
    print("   OpenAIClient.process_task()")
    print("   ↓")
    print("   _build_prompt() - 构建提示词")
    print("   ↓")
    print("   _simulate_openai_request() - 发送API请求")
    print("   ↓")
    print("   返回结构化结果")
    print()
    
    print("📍 3. 任务状态管理:")
    print("   PENDING → IN_PROGRESS → COMPLETED/FAILED")
    print("   ↓")
    print("   回调通知ExecutionService")
    print("   ↓")
    print("   继续工作流执行")
    print()
    
    print("📍 4. API响应结构:")
    print("""
   {
     "success": true,
     "model": "gpt-4",
     "result": {
       "analysis": "任务分析结果",
       "result": { ... },
       "recommendations": [...],
       "confidence": 0.85,
       "next_steps": [...]
     },
     "usage": {
       "prompt_tokens": 150,
       "completion_tokens": 200,
       "total_tokens": 350
     }
   }
   """)
    
    print("📍 5. 错误处理机制:")
    print("   • API调用超时 → 任务标记为失败")
    print("   • 网络错误 → 自动重试机制")
    print("   • 解析错误 → 降级到简单处理")
    print("   • 所有错误都会通过回调通知执行引擎")


async def main():
    """主演示函数"""
    try:
        print("Agent Processor 运行机制详解")
        print("=" * 50)
        
        # 1. 展示理论说明
        await show_agent_api_integration()
        
        # 2. 运行实际演示
        success = await demonstrate_agent_processor_flow()
        
        if success:
            print("\n🎉 Agent Processor演示成功完成!")
            print("\n📚 关键要点总结:")
            print("• Agent任务通过队列异步处理")
            print("• 支持多种AI服务(OpenAI, Claude等)")
            print("• 完整的状态跟踪和回调机制")
            print("• 结构化的API响应和错误处理")
            print("• 与工作流执行引擎完全集成")
        else:
            print("\n💥 Agent Processor演示失败!")
        
    except Exception as e:
        print(f"\n错误: {e}")
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(main())