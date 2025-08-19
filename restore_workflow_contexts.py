#!/usr/bin/env python3
"""
修复工作流上下文缺失问题 - 实现上下文恢复机制
"""

import asyncio
import uuid
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import initialize_database
from backend.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from backend.repositories.instance.node_instance_repository import NodeInstanceRepository
from backend.services.execution_service import execution_engine

async def restore_workflow_contexts():
    """恢复缺失的工作流上下文"""
    print("🔧 修复工作流上下文缺失问题...")
    
    await initialize_database()
    workflow_repo = WorkflowInstanceRepository()
    node_repo = NodeInstanceRepository()
    
    # 查找需要恢复上下文的工作流实例（有已完成节点但状态为pending/running的）
    query = """
    SELECT wi.*, 
           COUNT(ni.node_instance_id) as total_nodes,
           SUM(CASE WHEN ni.status = 'completed' THEN 1 ELSE 0 END) as completed_nodes,
           SUM(CASE WHEN ni.status = 'pending' THEN 1 ELSE 0 END) as pending_nodes,
           SUM(CASE WHEN ni.status = 'running' THEN 1 ELSE 0 END) as running_nodes
    FROM workflow_instance wi
    JOIN node_instance ni ON wi.workflow_instance_id = ni.workflow_instance_id
    WHERE wi.status IN ('pending', 'running')
    AND ni.is_deleted = FALSE
    AND wi.created_at > DATE_SUB(NOW(), INTERVAL 48 HOUR)
    GROUP BY wi.workflow_instance_id
    HAVING completed_nodes > 0 AND (pending_nodes > 0 OR running_nodes > 0)
    ORDER BY wi.created_at DESC
    """
    
    workflows = await workflow_repo.db.fetch_all(query)
    
    if not workflows:
        print("✅ 没有需要恢复上下文的工作流实例")
        return
    
    print(f"🔍 找到 {len(workflows)} 个需要恢复上下文的工作流实例:")
    
    restored_count = 0
    triggered_count = 0
    
    for workflow in workflows:
        workflow_instance_id = workflow['workflow_instance_id']
        print(f"\n=== 恢复工作流 {workflow['workflow_instance_name']} ===")
        print(f"实例ID: {workflow_instance_id}")
        print(f"状态: {workflow['status']}")
        print(f"节点统计: 总计 {workflow['total_nodes']}, 完成 {workflow['completed_nodes']}, 等待 {workflow['pending_nodes']}, 运行中 {workflow['running_nodes']}")
        
        try:
            # 1. 创建新的工作流上下文
            print(f"🏗️ 创建工作流上下文...")
            context = await execution_engine.context_manager.get_or_create_context(workflow_instance_id)
            await context.initialize_context()
            print(f"✅ 上下文创建成功")
            
            # 2. 查询该工作流的所有节点实例
            node_query = """
            SELECT ni.node_instance_id, ni.node_id, ni.status, ni.output_data,
                   n.name, n.type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
            ORDER BY ni.created_at
            """
            
            nodes = await node_repo.db.fetch_all(node_query, workflow_instance_id)
            print(f"📋 加载 {len(nodes)} 个节点实例")
            
            # 3. 重建每个节点的依赖关系和状态
            for node in nodes:
                node_instance_id = node['node_instance_id']
                node_id = node['node_id']
                node_status = node['status']
                node_name = node['name']
                output_data = node['output_data']
                
                print(f"  🔗 处理节点 {node_name} ({node_status})")
                
                # 获取上游节点实例
                upstream_nodes = await execution_engine._get_upstream_node_instances(
                    node_id, workflow_instance_id
                )
                
                # 注册依赖关系
                await context.register_node_dependencies(
                    node_instance_id, node_id, upstream_nodes
                )
                
                # 同步节点状态到上下文
                if node_status == 'completed':
                    context.node_states[node_instance_id] = 'COMPLETED'
                    context.execution_context['completed_nodes'].add(node_instance_id)
                    
                    # 处理输出数据
                    if output_data:
                        try:
                            if isinstance(output_data, str):
                                import json
                                parsed_output = json.loads(output_data)
                            else:
                                parsed_output = output_data
                            context.execution_context['node_outputs'][node_instance_id] = parsed_output
                        except:
                            # 如果解析失败，使用原始数据
                            context.execution_context['node_outputs'][node_instance_id] = output_data
                    
                    print(f"    ✅ 已完成节点状态已同步")
                    
                elif node_status == 'running':
                    context.node_states[node_instance_id] = 'EXECUTING'
                    context.execution_context['current_executing_nodes'].add(node_instance_id)
                    print(f"    ⚡ 运行中节点状态已同步")
                else:
                    context.node_states[node_instance_id] = 'PENDING'
                    print(f"    ⏳ 等待节点状态已同步")
            
            print(f"✅ 工作流上下文恢复完成")
            restored_count += 1
            
            # 4. 检查并触发准备就绪的节点
            print(f"🚀 检查并触发准备就绪的节点...")
            pending_nodes = [n for n in nodes if n['status'] == 'pending']
            
            if pending_nodes:
                # 检查哪些节点准备就绪
                ready_nodes = []
                for node in pending_nodes:
                    node_instance_id = node['node_instance_id']
                    if execution_engine.context_manager.is_node_ready_to_execute(node_instance_id):
                        ready_nodes.append(node_instance_id)
                        print(f"    ✅ 节点 {node['name']} 准备就绪")
                
                if ready_nodes:
                    # 触发准备就绪的节点
                    await execution_engine._on_nodes_ready_to_execute(workflow_instance_id, ready_nodes)
                    print(f"🎉 成功触发了 {len(ready_nodes)} 个下游节点！")
                    triggered_count += len(ready_nodes)
                else:
                    print(f"ℹ️ 没有节点准备就绪，依赖尚未完全满足")
            else:
                print(f"ℹ️ 没有等待中的节点需要触发")
            
        except Exception as e:
            print(f"❌ 恢复工作流 {workflow_instance_id} 上下文失败: {e}")
            import traceback
            print(f"错误详情: {traceback.format_exc()}")
    
    print(f"\n🎉 上下文恢复完成统计:")
    print(f"  - 恢复的工作流数: {restored_count}/{len(workflows)}")
    print(f"  - 触发的节点数: {triggered_count}")
    
    # 5. 验证恢复结果
    print(f"\n🔍 验证恢复结果...")
    for workflow in workflows[:3]:  # 只验证前3个工作流
        workflow_instance_id = workflow['workflow_instance_id']
        context_exists = workflow_instance_id in execution_engine.context_manager.contexts
        
        if context_exists:
            context = execution_engine.context_manager.contexts[workflow_instance_id]
            print(f"✅ 工作流 {workflow['workflow_instance_name'][:20]}... 上下文已恢复")
            print(f"    - 依赖信息数量: {len(context.node_dependencies)}")
            print(f"    - 已完成节点: {len(context.execution_context.get('completed_nodes', set()))}")
            print(f"    - 执行中节点: {len(context.execution_context.get('current_executing_nodes', set()))}")
        else:
            print(f"❌ 工作流 {workflow['workflow_instance_name'][:20]}... 上下文恢复失败")

if __name__ == "__main__":
    asyncio.run(restore_workflow_contexts())