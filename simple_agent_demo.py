#!/usr/bin/env python3
"""
Agent Processor 简单演示
Simple Agent Processor Demo
"""

import asyncio
import uuid
from datetime import datetime

from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.agent_task_service import agent_task_service
from workflow_framework.utils.openai_client import openai_client


async def demo_agent_processing():
    """演示Agent处理流程"""
    
    await initialize_database()
    
    try:
        print("=== Agent Processor 运行流程演示 ===")
        print()
        
        # 1. 启动Agent服务
        print("1. 启动Agent任务服务...")
        await agent_task_service.start_service()
        print("Agent服务启动成功")
        print()
        
        # 2. 直接演示OpenAI客户端调用
        print("2. 演示OpenAI API调用...")
        
        # 构建任务数据
        task_data = {
            'task_id': str(uuid.uuid4()),
            'task_title': '数据分析任务',
            'task_description': '分析用户行为数据并提供见解',
            'input_data': {
                'total_users': 1000,
                'active_users': 750,
                'conversion_rate': 0.15,
                'revenue': 50000
            },
            'instructions': '请分析这些业务指标并提供优化建议',
            'context': {
                'business_type': 'e-commerce',
                'time_period': '本月'
            }
        }
        
        print("任务数据准备完成:")
        print(f"  标题: {task_data['task_title']}")
        print(f"  描述: {task_data['task_description']}")
        print(f"  用户数据: {task_data['input_data']}")
        print()
        
        # 3. 调用OpenAI处理
        print("3. 调用OpenAI客户端处理...")
        ai_result = await openai_client.process_task(task_data)
        
        if ai_result['success']:
            print("OpenAI处理成功!")
            print(f"使用模型: {ai_result['model']}")
            
            result_data = ai_result['result']
            print(f"分析结果: {result_data['analysis']}")
            print(f"置信度: {result_data['confidence']}")
            print("主要建议:")
            for i, rec in enumerate(result_data['recommendations'], 1):
                print(f"  {i}. {rec}")
            
            # 显示token使用
            usage = ai_result.get('usage', {})
            print(f"Token使用: 总计{int(usage.get('total_tokens', 0))}")
        else:
            print(f"OpenAI处理失败: {ai_result['error']}")
        
        print()
        
        # 4. 演示其他AI能力
        print("4. 演示其他AI处理能力...")
        
        # 情感分析
        print("4.1 情感分析:")
        text = "这个产品很好用，我很满意！"
        sentiment = await openai_client.analyze_sentiment(text)
        print(f"  文本: {text}")
        print(f"  情感: {sentiment['sentiment']}")
        print(f"  置信度: {sentiment['confidence']}")
        print()
        
        # 文本摘要
        print("4.2 文本摘要:")
        long_text = "在现代数字化时代，数据分析变得越来越重要。企业需要利用数据来做出明智的决策。通过分析用户行为，公司可以改善产品和服务。"
        summary = await openai_client.summarize_text(long_text)
        print(f"  原文长度: {summary['original_length']} 字符")
        print(f"  摘要: {summary['summary']}")
        print(f"  压缩比: {summary['compression_ratio']:.2f}")
        print()
        
        # 代码生成
        print("4.3 代码生成:")
        code_result = await openai_client.generate_code("计算列表平均值", "python")
        print(f"  生成了 {code_result['lines_of_code']} 行代码")
        print("  代码片段:")
        lines = code_result['code'].split('\n')[:8]  # 显示前8行
        for line in lines:
            print(f"    {line}")
        print("    ...")
        print()
        
        print("=== 演示完成 ===")
        print()
        
        # 5. 说明Agent处理流程
        print("Agent处理流程说明:")
        print("1. 工作流执行引擎创建Agent任务")
        print("2. ExecutionService调用AgentTaskService")
        print("3. AgentTaskService将任务加入处理队列")
        print("4. 工作协程从队列取出任务进行处理")
        print("5. 根据Agent类型调用相应的API接口:")
        print("   - OpenAI: 调用GPT模型")
        print("   - Claude: 调用Anthropic模型")
        print("   - HTTP API: 调用自定义API")
        print("6. 处理完成后更新任务状态")
        print("7. 通过回调机制通知执行引擎")
        print("8. 执行引擎继续后续工作流步骤")
        
        return True
        
    except Exception as e:
        print(f"演示失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await agent_task_service.stop_service()
        await close_database()


async def show_api_structure():
    """展示API调用结构"""
    print("\n=== API调用结构详解 ===")
    print()
    
    print("Agent任务处理的关键组件:")
    print("1. AgentTaskService - 任务调度和管理")
    print("2. OpenAIClient - AI服务接口")
    print("3. TaskInstanceRepository - 任务状态存储")
    print("4. ExecutionService - 工作流执行引擎")
    print()
    
    print("API调用流程:")
    print("步骤1: 构建任务提示词")
    print("  - 任务标题和描述")
    print("  - 输入数据和上下文")
    print("  - 处理指令")
    print()
    
    print("步骤2: 发送API请求")
    print("  - 选择合适的AI模型")
    print("  - 设置请求参数")
    print("  - 处理网络请求")
    print()
    
    print("步骤3: 解析响应结果")
    print("  - 提取分析结果")
    print("  - 计算置信度")
    print("  - 生成建议列表")
    print()
    
    print("步骤4: 更新任务状态")
    print("  - 保存处理结果")
    print("  - 记录执行时间")
    print("  - 触发完成回调")


async def main():
    """主函数"""
    try:
        print("Agent Processor 运行机制演示")
        print("=" * 40)
        
        # 显示理论说明
        await show_api_structure()
        
        # 运行实际演示
        success = await demo_agent_processing()
        
        if success:
            print("\n演示成功完成!")
            print("现在你了解了Agent Processor的完整运行流程。")
        else:
            print("\n演示失败!")
        
    except Exception as e:
        print(f"错误: {e}")
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(main())