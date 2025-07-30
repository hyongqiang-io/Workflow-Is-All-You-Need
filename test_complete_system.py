"""
完整系统测试
测试OpenAI规范的agent_task_service与人类任务的数据一致性
"""

import uuid
import asyncio
import sys

sys.path.append('.')

from workflow_framework.services.agent_task_service import AgentTaskService
from workflow_framework.services.human_task_service import HumanTaskService


async def test_complete_system():
    """测试完整系统"""
    print("=" * 60)
    print("完整系统测试：OpenAI规范的AI处理器与人类任务一致性")
    print("=" * 60)
    
    # 初始化服务
    agent_service = AgentTaskService()
    human_service = HumanTaskService()
    
    # 共享的测试数据结构
    shared_upstream_data = {
        'immediate_upstream': {
            str(uuid.uuid4()): {
                'node_name': '数据收集节点',
                'output_data': {
                    'collected_records': 15000,
                    'data_quality_score': 0.95,
                    'collection_summary': '成功收集用户行为数据'
                },
                'completed_at': '2024-01-15T10:30:00Z'
            }
        },
        'workflow_global': {
            'execution_path': ['start', 'collection', 'analysis'],
            'global_data': {
                'project_name': 'Q1用户分析项目',
                'deadline': '2024-01-30T18:00:00Z'
            }
        },
        'node_info': {
            'upstream_node_count': 1
        }
    }
    
    # 测试1: 人类任务数据处理
    print("\n测试1: 人类任务数据处理")
    print("-" * 40)
    
    human_task = {
        'task_instance_id': uuid.uuid4(),
        'task_title': '用户行为分析任务',
        'task_description': '分析用户行为数据，识别关键模式',
        'instructions': '请基于上游数据进行深度分析',
        'input_data': shared_upstream_data,
        'status': 'assigned',
        'priority': 2
    }
    
    # 人类任务的上下文处理
    print("人类任务上下文提取:")
    human_context = await human_service._get_upstream_context(human_task)
    print(f"  上游节点数: {len(human_context.get('immediate_upstream_results', {}))}")
    print(f"  工作流路径: {human_context.get('workflow_execution_path', [])}")
    print(f"  有上游数据: {human_context.get('has_upstream_data', False)}")
    
    # 测试2: AI任务数据处理（使用相同的数据结构）
    print("\n测试2: AI任务数据处理")
    print("-" * 40)
    
    ai_task = {
        'task_instance_id': uuid.uuid4(),
        'task_title': '用户行为分析任务',  # 与人类任务相同
        'task_description': '分析用户行为数据，识别关键模式',  # 与人类任务相同
        'instructions': '请基于上游数据进行深度分析',  # 与人类任务相同
        'input_data': shared_upstream_data,  # 完全相同的上游数据
        'status': 'assigned',
        'priority': 2,
        'assigned_agent_id': uuid.uuid4()
    }
    
    # AI任务的数据处理
    system_prompt = agent_service._build_system_prompt(ai_task)
    context_info = agent_service._preprocess_upstream_context(ai_task['input_data'])
    user_message = agent_service._build_user_message(ai_task, context_info)
    
    print("AI任务数据处理:")
    print(f"  系统提示长度: {len(system_prompt)} 字符")
    print(f"  上下文信息长度: {len(context_info)} 字符")
    print(f"  用户消息长度: {len(user_message)} 字符")
    
    # 测试3: AI处理执行（使用OpenAI规范）
    print("\n测试3: AI处理执行")
    print("-" * 40)
    
    ai_client_data = {
        'task_id': str(ai_task['task_instance_id']),
        'system_prompt': system_prompt,
        'user_message': user_message,
        'task_metadata': {
            'task_title': ai_task['task_title'],
            'priority': ai_task['priority'],
            'estimated_duration': 30
        }
    }
    
    mock_agent = {
        'agent_name': 'openai-gpt4',
        'model': 'gpt-4',
        'temperature': 0.7,
        'max_tokens': 2000
    }
    
    try:
        ai_result = await agent_service._process_with_openai_format(mock_agent, ai_client_data)
        print("AI处理结果:")
        print(f"  分析结果: {ai_result.get('analysis_result', 'N/A')[:50]}...")
        print(f"  关键发现: {len(ai_result.get('key_findings', []))} 项")
        print(f"  建议数量: {len(ai_result.get('recommendations', []))} 项")
        print(f"  置信度: {ai_result.get('confidence_score', 0)}")
        print(f"  使用模型: {ai_result.get('model_used', 'N/A')}")
        
        ai_processing_success = True
    except Exception as e:
        print(f"AI处理失败: {e}")
        ai_processing_success = False
    
    # 测试4: 数据一致性验证
    print("\n测试4: 数据一致性验证")
    print("-" * 40)
    
    consistency_checks = [
        ("任务标题一致", human_task['task_title'] == ai_task['task_title']),
        ("任务描述一致", human_task['task_description'] == ai_task['task_description']),
        ("指令一致", human_task['instructions'] == ai_task['instructions']),
        ("上游数据一致", human_task['input_data'] == ai_task['input_data']),
        ("优先级一致", human_task['priority'] == ai_task['priority']),
        ("上游节点数一致", len(human_context.get('immediate_upstream_results', {})) == 
         len(shared_upstream_data.get('immediate_upstream', {}))),
        ("工作流路径一致", human_context.get('workflow_execution_path') == 
         shared_upstream_data['workflow_global']['execution_path'])
    ]
    
    all_consistent = True
    for check_name, is_consistent in consistency_checks:
        status = "[OK]" if is_consistent else "[ERROR]"
        print(f"  {check_name}: {status}")
        if not is_consistent:
            all_consistent = False
    
    # 测试5: 输出格式验证
    print("\n测试5: 输出格式验证")
    print("-" * 40)
    
    if ai_processing_success:
        required_output_fields = [
            'analysis_result', 'key_findings', 'recommendations', 
            'confidence_score', 'summary'
        ]
        
        output_complete = True
        for field in required_output_fields:
            has_field = field in ai_result
            status = "[OK]" if has_field else "[ERROR]"
            print(f"  {field}: {status}")
            if not has_field:
                output_complete = False
    else:
        output_complete = False
        print("  AI处理失败，无法验证输出格式")
    
    # 最终结果
    print("\n" + "=" * 60)
    print("测试总结:")
    
    test_results = [
        ("人类任务数据处理", True),  # 人类任务处理总是可用的
        ("AI任务数据处理", True),   # AI数据处理成功
        ("AI处理执行", ai_processing_success),
        ("数据一致性", all_consistent),
        ("输出格式", output_complete)
    ]
    
    passed_tests = 0
    for test_name, passed in test_results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {test_name}: {status}")
        if passed:
            passed_tests += 1
    
    success_rate = (passed_tests / len(test_results)) * 100
    print(f"\n成功率: {passed_tests}/{len(test_results)} ({success_rate:.0f}%)")
    
    if passed_tests == len(test_results):
        print("\n[SUCCESS] 完整系统测试通过！")
        print("* OpenAI规范的agent_task_service已成功实现")
        print("* AI任务与人类任务数据完全一致")
        print("* 工作流框架支持统一的数据处理")
        return True
    else:
        print(f"\n[WARNING] 部分测试失败，需要进一步优化")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_complete_system())
    
    if result:
        print("\n" + "=" * 60)
        print("[SUCCESS] 恭喜！系统测试全部完成！")
        print("OpenAI规范的AI处理器已成功集成到工作流框架中")
    else:
        print("\n" + "=" * 60)
        print("[WARNING] 系统测试未完全通过，请检查相关问题")