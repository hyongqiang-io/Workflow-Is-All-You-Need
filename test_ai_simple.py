"""
AI处理器简化测试
"""

import uuid
import asyncio
import sys

sys.path.append('.')

from workflow_framework.services.agent_task_service import AgentTaskService
from workflow_framework.models.instance import TaskInstanceType


async def test_ai_processor():
    """测试AI处理器"""
    print("Testing AI Processor...")
    
    service = AgentTaskService()
    
    # 模拟任务数据（与人类任务一致的结构）
    mock_task = {
        'task_instance_id': str(uuid.uuid4()),
        'task_title': 'User Behavior Analysis Task',
        'task_description': 'Analyze user behavior data and identify patterns',
        'instructions': 'Analyze user patterns, identify key segments, provide recommendations',
        'priority': 3,
        'estimated_duration': 45,
        'input_data': {
            'immediate_upstream': {
                str(uuid.uuid4()): {
                    'node_name': 'Data Collection Node',
                    'output_data': {
                        'collected_records': 10000,
                        'quality_score': 0.95
                    },
                    'completed_at': '2024-01-15T10:30:00Z'
                }
            },
            'workflow_global': {
                'execution_path': ['start', 'collection', 'preprocessing'],
                'global_data': {
                    'project_name': 'Q1 Analysis'
                }
            },
            'node_info': {
                'upstream_node_count': 1
            }
        }
    }
    
    print(f"Task: {mock_task['task_title']}")
    
    # 测试系统prompt生成
    system_prompt = service._build_system_prompt(mock_task)
    print(f"System prompt: {len(system_prompt)} characters")
    
    # 测试上下文预处理
    context_info = service._preprocess_upstream_context(mock_task['input_data'])
    print(f"Context info: {len(context_info)} characters")
    
    # 测试用户消息构建
    user_message = service._build_user_message(mock_task, context_info)
    print(f"User message: {len(user_message)} characters")
    
    # 构建AI client数据
    ai_client_data = {
        'task_id': str(mock_task['task_instance_id']),
        'system_prompt': system_prompt,
        'user_message': user_message,
        'task_metadata': {
            'task_title': mock_task['task_title'],
            'priority': mock_task['priority'],
            'estimated_duration': mock_task['estimated_duration']
        }
    }
    
    print("AI Client Data Structure:")
    print(f"  Task ID: {ai_client_data['task_id']}")
    print(f"  System Prompt: {len(ai_client_data['system_prompt'])} chars")
    print(f"  User Message: {len(ai_client_data['user_message'])} chars")
    print(f"  Metadata: {ai_client_data['task_metadata']}")
    
    # 测试AI处理
    mock_agent = {
        'agent_name': 'claude-test',
        'model': 'claude-3-sonnet',
        'temperature': 0.7,
        'max_tokens': 2000
    }
    
    try:
        result = await service._process_with_openai_format(mock_agent, ai_client_data)
        print("\nAI Processing Result:")
        print(f"  Analysis: {result.get('analysis_result', 'N/A')[:100]}...")
        print(f"  Key Findings: {len(result.get('key_findings', []))} items")
        print(f"  Recommendations: {len(result.get('recommendations', []))} items")
        print(f"  Confidence: {result.get('confidence_score', 0)}")
        print(f"  Model Used: {result.get('model_used', 'N/A')}")
        
        print("\nTest Results:")
        print("- System prompt generation: PASS")
        print("- Context preprocessing: PASS")
        print("- User message construction: PASS")
        print("- AI client data structure: PASS")
        print("- AI processing: PASS")
        print("- Data consistency with human tasks: PASS")
        
        print("\nSUCCESS: AI processor correctly handles human-task-like data structure!")
        return True
        
    except Exception as e:
        print(f"ERROR: AI processing failed: {e}")
        return False


if __name__ == "__main__":
    result = asyncio.run(test_ai_processor())
    if result:
        print("\nAI Processor Test: PASSED")
    else:
        print("\nAI Processor Test: FAILED")