#!/usr/bin/env python3
"""
检查context_data的具体内容
"""

import asyncio
import uuid
import json
import pprint
from workflow_framework.repositories.instance.task_instance_repository import TaskInstanceRepository

async def inspect_context_data():
    """检查context_data的具体内容"""
    print("检查context_data的具体内容...")
    
    task_repo = TaskInstanceRepository()
    
    # 任务ID
    task_id = uuid.UUID("ba41eed4-37ba-476b-8ee1-0964177db71f")
    
    print(f"任务ID: {task_id}")
    
    # 获取任务数据
    raw_task = await task_repo.get_task_by_id(task_id)
    if raw_task:
        print(f"任务标题: {raw_task.get('task_title')}")
        
        # 获取context_data
        context_data = raw_task.get('context_data')
        print(f"context_data类型: {type(context_data)}")
        
        if isinstance(context_data, dict):
            print("\ncontext_data结构:")
            print("=" * 60)
            
            for key, value in context_data.items():
                print(f"Key: {key}")
                print(f"  类型: {type(value)}")
                print(f"  值: {value}")
                print("-" * 40)
                
                # 如果是upstream_outputs，详细检查
                if key == 'upstream_outputs':
                    print(f"  upstream_outputs详细检查:")
                    print(f"    类型: {type(value)}")
                    if isinstance(value, dict):
                        print(f"    keys数量: {len(value)}")
                        for sub_key, sub_value in value.items():
                            print(f"    {sub_key}: {type(sub_value)} = {sub_value}")
                    elif isinstance(value, list):
                        print(f"    列表长度: {len(value)}")
                        for i, item in enumerate(value):
                            print(f"    [{i}]: {type(item)} = {item}")
                    else:
                        print(f"    直接值: {value}")
            
            print("=" * 60)
        else:
            print(f"context_data不是字典: {context_data}")

async def main():
    """主函数"""
    try:
        await inspect_context_data()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())