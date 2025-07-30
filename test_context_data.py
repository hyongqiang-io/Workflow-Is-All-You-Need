#!/usr/bin/env python3
"""
测试任务上下文数据功能
Test Task Context Data Functionality
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.utils.database import initialize_database, get_db_manager

async def test_context_data():
    """测试上下文数据功能"""
    
    print("🧪 测试任务上下文数据功能")
    print("=" * 60)
    
    try:
        # Initialize database connection
        await initialize_database()
        db = get_db_manager()
        
        # 1. 检查最新创建的任务实例
        print("\n1. 检查最新任务实例的上下文数据:")
        task_query = '''
        SELECT 
            task_instance_id,
            task_title,
            task_description,
            context_data,
            created_at
        FROM task_instance 
        WHERE context_data IS NOT NULL 
        AND context_data != '{}'::jsonb
        ORDER BY created_at DESC
        LIMIT 3
        '''
        tasks = await db.fetch_all(task_query)
        
        if tasks:
            for i, task in enumerate(tasks, 1):
                print(f"\n  任务 {i}: {task['task_title']}")
                print(f"  任务ID: {task['task_instance_id']}")
                print(f"  创建时间: {task['created_at']}")
                print(f"  上下文数据结构:")
                
                context_data = task['context_data']
                if isinstance(context_data, dict):
                    for key in context_data.keys():
                        print(f"    - {key}")
                        if key == 'upstream_outputs' and context_data[key]:
                            print(f"      └─ 包含 {len(context_data[key])} 个上游节点输出")
                        elif key == 'workflow' and context_data[key]:
                            workflow_info = context_data[key]
                            print(f"      └─ 工作流: {workflow_info.get('name', 'Unknown')}")
                        elif key == 'current_node' and context_data[key]:
                            node_info = context_data[key]
                            print(f"      └─ 当前节点: {node_info.get('name', 'Unknown')}")
        else:
            print("  ❌ 未找到包含上下文数据的任务实例")
        
        # 2. 统计上下文数据使用情况
        print("\n2. 上下文数据统计:")
        stats_query = '''
        SELECT 
            COUNT(*) as total_tasks,
            COUNT(CASE WHEN context_data IS NOT NULL AND context_data != '{}'::jsonb THEN 1 END) as tasks_with_context,
            COUNT(CASE WHEN context_data IS NULL OR context_data = '{}'::jsonb THEN 1 END) as tasks_without_context
        FROM task_instance
        WHERE created_at > NOW() - INTERVAL '1 day'
        '''
        stats = await db.fetch_one(stats_query)
        
        if stats:
            print(f"  总任务数: {stats['total_tasks']}")
            print(f"  包含上下文数据: {stats['tasks_with_context']}")
            print(f"  无上下文数据: {stats['tasks_without_context']}")
            
            if stats['total_tasks'] > 0:
                context_rate = (stats['tasks_with_context'] / stats['total_tasks']) * 100
                print(f"  上下文覆盖率: {context_rate:.1f}%")
        
        # 3. 检查context_data字段的数据结构
        print("\n3. 上下文数据结构样例:")
        sample_query = '''
        SELECT context_data
        FROM task_instance 
        WHERE context_data IS NOT NULL 
        AND context_data != '{}'::jsonb
        AND jsonb_typeof(context_data) = 'object'
        ORDER BY created_at DESC
        LIMIT 1
        '''
        sample = await db.fetch_one(sample_query)
        
        if sample and sample['context_data']:
            context = sample['context_data']
            print(f"  完整上下文数据结构:")
            
            import json
            formatted_json = json.dumps(context, indent=2, ensure_ascii=False, default=str)
            # 限制输出长度
            lines = formatted_json.split('\n')
            if len(lines) > 30:
                shown_lines = lines[:25] + ['    ...', f'    // 省略了 {len(lines) - 25} 行'] + lines[-5:]
                formatted_json = '\n'.join(shown_lines)
            
            print(formatted_json)
        else:
            print("  ❌ 未找到上下文数据样例")
        
        print("\n" + "=" * 60)
        print("✅ 上下文数据功能测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_context_data())