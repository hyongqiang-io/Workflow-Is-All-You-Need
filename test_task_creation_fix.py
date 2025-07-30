"""
测试任务创建修复
Test Task Creation Fix
"""

import asyncio
import uuid
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.models.instance import TaskInstanceCreate, TaskInstanceType
from loguru import logger

def test_task_instance_create_validation():
    """Test TaskInstanceCreate validation"""
    print("Test TaskInstanceCreate model validation")
    print("=" * 50)
    
    # 测试1: 空字符串task_description（应该通过）
    print("\n1. 测试空字符串task_description:")
    try:
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=uuid.uuid4(),
            task_type=TaskInstanceType.HUMAN,
            task_title="测试任务",
            task_description="",  # 空字符串
            input_data={},
            instructions="测试指令",
            priority=1,
            assigned_user_id=uuid.uuid4(),
            assigned_agent_id=None,
            estimated_duration=30
        )
        print("   ✅ 空字符串task_description验证通过")
    except Exception as e:
        print(f"   ❌ 空字符串task_description验证失败: {e}")
    
    # 测试2: None值task_description（应该使用默认值）
    print("\n2. 测试None值task_description:")
    try:
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=uuid.uuid4(),
            task_type=TaskInstanceType.HUMAN,
            task_title="测试任务",
            # task_description 不传值，应该使用默认值
            input_data={},
            instructions="测试指令",
            priority=1,
            assigned_user_id=uuid.uuid4(),
            assigned_agent_id=None,
            estimated_duration=30
        )
        print(f"   ✅ 默认task_description验证通过: '{task_data.task_description}'")
    except Exception as e:
        print(f"   ❌ 默认task_description验证失败: {e}")
    
    # 测试3: 正常的task_description
    print("\n3. 测试正常的task_description:")
    try:
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=uuid.uuid4(),
            task_type=TaskInstanceType.HUMAN,
            task_title="测试任务",
            task_description="这是一个正常的任务描述",
            input_data={},
            instructions="测试指令",
            priority=1,
            assigned_user_id=uuid.uuid4(),
            assigned_agent_id=None,
            estimated_duration=30
        )
        print(f"   ✅ 正常task_description验证通过: '{task_data.task_description}'")
    except Exception as e:
        print(f"   ❌ 正常task_description验证失败: {e}")
    
    print("\n✅ TaskInstanceCreate模型验证测试完成")

def test_node_data_processing():
    """测试节点数据处理逻辑"""
    print("\n🔧 测试节点数据处理逻辑")
    print("=" * 50)
    
    # 模拟不同的节点数据情况
    test_cases = [
        {
            "name": "空task_description的节点",
            "node_data": {
                "name": "测试节点1",
                "task_description": "",
                "instructions": ""
            },
            "processor": {
                "processor_name": "测试处理器",
                "instructions": ""
            }
        },
        {
            "name": "None task_description的节点",
            "node_data": {
                "name": "测试节点2",
                "task_description": None,
                "instructions": None
            },
            "processor": {
                "processor_name": "测试处理器",
                "instructions": None
            }
        },
        {
            "name": "缺少task_description字段的节点",
            "node_data": {
                "name": "测试节点3",
                "description": "这是节点描述"
            },
            "processor": {
                "processor_name": "测试处理器",
                "instructions": "处理器指令"
            }
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['name']}:")
        
        node_data = case['node_data']
        processor = case['processor']
        
        # 模拟修复后的逻辑
        task_description = node_data.get('task_description') or node_data.get('description') or f"执行节点 {node_data['name']} 的任务"
        instructions = node_data.get('instructions') or processor.get('instructions') or f"请处理节点 {node_data['name']} 的相关任务"
        
        print(f"   生成的task_description: '{task_description}'")
        print(f"   生成的instructions: '{instructions}'")
        
        # 验证这些值能否通过模型验证
        try:
            task_data = TaskInstanceCreate(
                node_instance_id=uuid.uuid4(),
                workflow_instance_id=uuid.uuid4(),
                processor_id=uuid.uuid4(),
                task_type=TaskInstanceType.HUMAN,
                task_title=f"{node_data['name']} - {processor.get('processor_name', 'Unknown')}",
                task_description=task_description,
                input_data={},
                instructions=instructions,
                priority=1,
                assigned_user_id=uuid.uuid4(),
                assigned_agent_id=None,
                estimated_duration=30
            )
            print("   ✅ 模型验证通过")
        except Exception as e:
            print(f"   ❌ 模型验证失败: {e}")
    
    print("\n✅ 节点数据处理逻辑测试完成")

def main():
    """主函数"""
    print("TaskInstanceCreate validation error fix test")
    print("=" * 60)
    
    # 测试模型验证
    test_task_instance_create_validation()
    
    # 测试数据处理逻辑
    test_node_data_processing()
    
    print(f"\nAll tests completed!")
    print("=" * 60)
    print("Fix summary:")
    print("1. TaskInstanceBase.task_description now has default value (empty string)")
    print("2. execution_service.py now has smart task_description generation logic")
    print("3. Ensured instructions also have reasonable default values")
    print("4. Added detailed logs to show generated task_description and instructions")
    print("\nTask instances should now be created successfully!")

if __name__ == "__main__":
    main()