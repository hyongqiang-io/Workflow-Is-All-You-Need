#!/usr/bin/env python3
"""
测试延迟任务创建机制
Test Delayed Task Creation Mechanism
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.utils.database import initialize_database, get_db_manager

async def test_delayed_task_creation():
    """测试延迟任务创建机制"""
    
    print("测试延迟任务创建机制...")
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
        LIMIT 3
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
        
        print(f"\n分析工作流: {latest_workflow['instance_name']} ({workflow_instance_id})")
        print(f"   当前状态: {latest_workflow['status']}")
        
        # 2. 查询节点实例状态和任务创建情况
        print("\n2. 节点实例状态分析:")
        nodes_query = '''
        SELECT ni.node_instance_id, ni.status, n.name as node_name, n.type as node_type,
               (SELECT COUNT(*) FROM task_instance ti 
                WHERE ti.node_instance_id = ni.node_instance_id AND ti.is_deleted = FALSE) as task_count
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
        ORDER BY ni.created_at
        '''
        nodes = await db.fetch_all(nodes_query, workflow_instance_id)
        
        print(f"  工作流包含 {len(nodes)} 个节点:")
        for node in nodes:
            status_emoji = {
                'pending': '[PENDING]', 'waiting': '[WAIT]', 'ready': '[READY]', 'running': '[RUN]', 
                'completed': '[DONE]', 'failed': '[FAIL]', 'cancelled': '[CANCEL]'
            }.get(node['status'], '[UNK]')
            
            print(f"    {status_emoji} {node['node_name']} ({node['node_type']})")
            print(f"        状态: {node['status']}")
            print(f"        任务数量: {node['task_count']}")
        
        # 3. 检查任务创建的延迟情况
        print("\n3. 任务创建时机分析:")
        
        # 统计不同状态节点的任务情况
        waiting_nodes = [n for n in nodes if n['status'] == 'waiting']
        ready_nodes = [n for n in nodes if n['status'] == 'ready']
        completed_nodes = [n for n in nodes if n['status'] == 'completed']
        
        print(f"  等待中节点 (waiting): {len(waiting_nodes)} 个")
        for node in waiting_nodes:
            print(f"    - {node['node_name']}: {node['task_count']} 个任务")
            if node['task_count'] > 0:
                print(f"      [WARNING] 等待状态的节点不应该有任务!")
        
        print(f"  就绪节点 (ready): {len(ready_nodes)} 个")
        for node in ready_nodes:
            print(f"    - {node['node_name']}: {node['task_count']} 个任务")
            if node['task_count'] == 0 and node['node_type'] == 'processor':
                print(f"      [WARNING] 就绪状态的PROCESSOR节点应该有任务!")
        
        print(f"  已完成节点 (completed): {len(completed_nodes)} 个")
        for node in completed_nodes:
            print(f"    - {node['node_name']}: {node['task_count']} 个任务")
        
        # 4. 检查依赖关系和执行顺序
        print("\n4. 执行顺序验证:")
        connections_query = '''
        SELECT c.connection_id, 
               source_n.name as source_name, source_n.type as source_type,
               target_n.name as target_name, target_n.type as target_type,
               source_ni.status as source_status, target_ni.status as target_status
        FROM node_connection c
        JOIN node source_n ON c.source_node_id = source_n.node_id
        JOIN node target_n ON c.target_node_id = target_n.node_id
        JOIN node_instance source_ni ON source_n.node_id = source_ni.node_id
        JOIN node_instance target_ni ON target_n.node_id = target_ni.node_id
        WHERE source_ni.workflow_instance_id = $1 AND target_ni.workflow_instance_id = $1
        ORDER BY c.created_at
        '''
        connections = await db.fetch_all(connections_query, workflow_instance_id)
        
        print(f"  找到 {len(connections)} 个连接关系:")
        for conn in connections:
            source_emoji = {
                'pending': '[PENDING]', 'waiting': '[WAIT]', 'ready': '[READY]', 'running': '[RUN]', 
                'completed': '[DONE]', 'failed': '[FAIL]'
            }.get(conn['source_status'], '[UNK]')
            
            target_emoji = {
                'pending': '[PENDING]', 'waiting': '[WAIT]', 'ready': '[READY]', 'running': '[RUN]', 
                'completed': '[DONE]', 'failed': '[FAIL]'
            }.get(conn['target_status'], '[UNK]')
            
            print(f"    -> {source_emoji} {conn['source_name']} -> {target_emoji} {conn['target_name']}")
            
            # 检查顺序是否正确
            if conn['source_status'] != 'completed' and conn['target_status'] in ['ready', 'running', 'completed']:
                print(f"      [WARNING] 执行顺序异常: 前置节点未完成但后续节点已激活")
            elif conn['source_status'] == 'completed' and conn['target_status'] == 'waiting':
                print(f"      [OK] 可以激活: 前置节点已完成，目标节点等待中")
        
        # 5. 延迟任务创建效果评估
        print("\n5. 延迟任务创建效果评估:")
        
        # 计算任务创建统计
        total_processor_nodes = len([n for n in nodes if n['node_type'] == 'processor'])
        nodes_with_tasks = len([n for n in nodes if n['task_count'] > 0])
        waiting_processors = len([n for n in nodes if n['node_type'] == 'processor' and n['status'] == 'waiting'])
        
        print(f"  PROCESSOR节点总数: {total_processor_nodes}")
        print(f"  已创建任务的节点: {nodes_with_tasks}")
        print(f"  等待中的PROCESSOR节点: {waiting_processors}")
        
        if waiting_processors > 0:
            print(f"  [SUCCESS] 延迟创建生效: {waiting_processors} 个节点暂未创建任务")
        else:
            print(f"  [INFO] 可能所有任务都已创建")
        
        # 6. 建议和总结
        print("\n6. 测试总结:")
        
        issues_found = []
        successes = []
        
        # 检查各种情况
        if any(n['task_count'] > 0 and n['status'] == 'waiting' for n in nodes):
            issues_found.append("等待状态节点有任务（不符合延迟创建）")
        else:
            successes.append("等待状态节点正确无任务")
        
        if any(n['node_type'] == 'processor' and n['status'] == 'ready' and n['task_count'] == 0 for n in nodes):
            issues_found.append("就绪PROCESSOR节点缺少任务")
        else:
            successes.append("就绪PROCESSOR节点正确有任务")
        
        print(f"  成功项目 ({len(successes)}):")
        for success in successes:
            print(f"    [OK] {success}")
        
        if issues_found:
            print(f"  发现问题 ({len(issues_found)}):")
            for issue in issues_found:
                print(f"    [ERROR] {issue}")
        else:
            print(f"  [SUCCESS] 延迟任务创建机制运行正常!")
        
        print("\n" + "=" * 60)
        print("测试完成")
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_delayed_task_creation())