#!/usr/bin/env python3
"""
查找有细分结果标记的任务
"""

import asyncio
import uuid
import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import initialize_database
from backend.repositories.instance.task_instance_repository import TaskInstanceRepository

async def find_subdivision_marked_tasks():
    """查找有细分结果标记的任务"""
    print("🔍 查找有细分结果标记的任务...")
    
    await initialize_database()
    task_repo = TaskInstanceRepository()
    
    # 查找有context_data的任务
    query = """
    SELECT ti.*, ni.status as node_status
    FROM task_instance ti
    JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
    WHERE ti.context_data IS NOT NULL 
    AND ti.context_data != '{}'
    AND ti.task_type = 'human'
    AND ti.is_deleted = FALSE
    AND ni.is_deleted = FALSE
    ORDER BY ti.updated_at DESC
    LIMIT 10
    """
    
    tasks = await task_repo.db.fetch_all(query)
    
    print(f"📋 找到 {len(tasks)} 个有context_data的任务:")
    
    for i, task in enumerate(tasks, 1):
        print(f"\n=== 任务 {i} ===")
        print(f"任务ID: {task['task_instance_id']}")
        print(f"任务标题: {task['task_title']}")
        print(f"任务状态: {task['status']}")
        print(f"节点状态: {task['node_status']}")
        
        context_data = task.get('context_data')
        if context_data:
            try:
                if isinstance(context_data, str):
                    parsed_context = json.loads(context_data)
                else:
                    parsed_context = context_data
                
                # 检查细分标记
                is_reference_data = parsed_context.get('is_reference_data', False)
                auto_submitted = parsed_context.get('auto_submitted', True)
                subdivision_id = parsed_context.get('subdivision_id')
                
                print(f"细分标记检查:")
                print(f"  - is_reference_data: {is_reference_data}")
                print(f"  - auto_submitted: {auto_submitted}")
                print(f"  - subdivision_id: {subdivision_id}")
                
                if is_reference_data and not auto_submitted:
                    print(f"✅ 这是有细分结果的任务！")
                    
                    # 检查是否需要修复
                    if task['status'] != 'completed' or task['node_status'] == 'pending':
                        print(f"⚠️ 可能需要修复:")
                        print(f"   任务状态: {task['status']} (期望: completed)")
                        print(f"   节点状态: {task['node_status']} (期望: completed)")
                
                # 显示context_data的部分内容
                context_keys = list(parsed_context.keys())
                print(f"context_data包含字段: {context_keys}")
                
            except Exception as e:
                print(f"❌ 解析context_data失败: {e}")
                print(f"原始context_data: {str(context_data)[:200]}...")

if __name__ == "__main__":
    asyncio.run(find_subdivision_marked_tasks())