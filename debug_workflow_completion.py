#!/usr/bin/env python3
"""
调试工作流完成问题
Debug Workflow Completion Issue
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.utils.database import initialize_database, get_db_manager

async def debug_workflow_completion():
    """调试工作流完成问题"""
    
    print("🔍 调试工作流完成问题...")
    print("=" * 60)
    
    try:
        # Initialize database connection
        await initialize_database()
        db = get_db_manager()
        
        # 1. 查询最新的工作流实例
        print("\n1. 查询最新的工作流实例:")
        workflow_query = '''
        SELECT wi.workflow_instance_id, wi.instance_name, wi.status, wi.created_at
        FROM workflow_instance wi
        WHERE wi.is_deleted = FALSE
        ORDER BY wi.created_at DESC
        LIMIT 5
        '''
        workflows = await db.fetch_all(workflow_query)
        
        for workflow in workflows:
            print(f"  - {workflow['instance_name']}: {workflow['status']} ({workflow['workflow_instance_id']})")
        
        if not workflows:
            print("  ❌ 没有找到工作流实例")
            return
        
        # 选择最新的工作流实例进行分析
        latest_workflow = workflows[0]
        workflow_instance_id = latest_workflow['workflow_instance_id']
        
        print(f"\n🔍 分析工作流: {latest_workflow['instance_name']} ({workflow_instance_id})")
        print(f"   当前状态: {latest_workflow['status']}")
        
        # 2. 查询该工作流的所有节点实例
        print("\n2. 节点实例状态:")
        nodes_query = '''
        SELECT ni.node_instance_id, ni.status, n.name as node_name, n.node_type
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
        ORDER BY ni.created_at
        '''
        nodes = await db.fetch_all(nodes_query, workflow_instance_id)
        
        for node in nodes:
            status_emoji = {
                'pending': '⏳', 'waiting': '⏳', 'running': '🔄', 
                'completed': '✅', 'failed': '❌', 'cancelled': '🚫'
            }.get(node['status'], '❓')
            print(f"  {status_emoji} {node['node_name']} ({node['node_type']}): {node['status']}")
        
        # 3. 查询该工作流的所有任务实例
        print("\n3. 任务实例状态:")
        tasks_query = '''
        SELECT ti.task_instance_id, ti.status, ti.task_title, ni.node_name
        FROM task_instance ti
        JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
        WHERE ni.workflow_instance_id = $1 AND ti.is_deleted = FALSE
        ORDER BY ti.created_at
        '''
        tasks = await db.fetch_all(tasks_query, workflow_instance_id)
        
        for task in tasks:
            status_emoji = {
                'pending': '⏳', 'assigned': '📋', 'in_progress': '🔄',
                'completed': '✅', 'failed': '❌', 'cancelled': '🚫'
            }.get(task['status'], '❓')
            print(f"  {status_emoji} {task['task_title']} ({task['node_name']}): {task['status']}")
        
        # 4. 检查连接关系
        print("\n4. 节点连接关系:")
        connections_query = '''
        SELECT c.connection_id, 
               source_n.name as source_name, source_n.node_type as source_type,
               target_n.name as target_name, target_n.node_type as target_type
        FROM connection c
        JOIN node source_n ON c.source_node_id = source_n.node_id
        JOIN node target_n ON c.target_node_id = target_n.node_id
        WHERE source_n.workflow_base_id = (
            SELECT workflow_base_id FROM workflow_instance WHERE workflow_instance_id = $1
        )
        ORDER BY c.created_at
        '''
        connections = await db.fetch_all(connections_query, workflow_instance_id)
        
        for conn in connections:
            print(f"  📎 {conn['source_name']} ({conn['source_type']}) → {conn['target_name']} ({conn['target_type']})")
        
        # 5. 分析问题
        print("\n5. 问题分析:")
        
        # 检查是否有结束节点
        end_nodes = [n for n in nodes if n['node_type'] == 'end']
        if not end_nodes:
            print("  ❌ 没有找到结束节点")
        else:
            print(f"  ✅ 找到 {len(end_nodes)} 个结束节点")
            for end_node in end_nodes:
                print(f"    - {end_node['node_name']}: {end_node['status']}")
        
        # 检查任务是否都已完成
        completed_tasks = [t for t in tasks if t['status'] == 'completed']
        if len(completed_tasks) == len(tasks) and len(tasks) > 0:
            print(f"  ✅ 所有任务已完成 ({len(completed_tasks)}/{len(tasks)})")
        else:
            print(f"  ❌ 任务未全部完成 ({len(completed_tasks)}/{len(tasks)})")
        
        # 检查节点是否都已完成
        completed_nodes = [n for n in nodes if n['status'] == 'completed']
        if len(completed_nodes) == len(nodes) and len(nodes) > 0:
            print(f"  ✅ 所有节点已完成 ({len(completed_nodes)}/{len(nodes)})")
        else:
            print(f"  ❌ 节点未全部完成 ({len(completed_nodes)}/{len(nodes)})")
            for node in nodes:
                if node['status'] != 'completed':
                    print(f"    - 未完成节点: {node['node_name']} ({node['status']})")
        
        # 检查连接关系是否正确
        if not connections:
            print("  ❌ 没有找到节点连接关系")
        else:
            print(f"  ✅ 找到 {len(connections)} 个连接关系")
        
        print("\n" + "=" * 60)
        print("调试完成")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(debug_workflow_completion())