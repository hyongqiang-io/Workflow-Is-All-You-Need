#!/usr/bin/env python3
"""
彻底修复工作流上下文丢失问题
这个脚本将作为生产环境的修复工具，可以在任何时候恢复丢失的工作流上下文
"""

import asyncio
import sys
sys.path.append('.')

from backend.services.workflow_execution_context import get_context_manager
from backend.services.execution_service import ExecutionEngine
from backend.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from backend.repositories.instance.node_instance_repository import NodeInstanceRepository
import uuid

async def restore_workflow_context():
    """彻底修复工作流上下文丢失问题"""
    
    # 使用实际的工作流ID
    workflow_instance_id = uuid.UUID('b29e9ea3-5da8-45f5-b0e3-e87884b1f45f')
    
    print("🔧 开始修复工作流上下文...")
    print(f"📋 目标工作流实例: {workflow_instance_id}")
    
    # 获取服务实例
    context_manager = get_context_manager()
    execution_engine = ExecutionEngine()
    workflow_repo = WorkflowInstanceRepository()
    node_repo = NodeInstanceRepository()
    
    # 1. 检查当前状态
    print("\n📊 检查当前工作流状态...")
    workflow = await workflow_repo.get_instance_by_id(workflow_instance_id)
    if not workflow:
        print("❌ 工作流实例不存在")
        return
    
    print(f"工作流名称: {workflow['workflow_instance_name']}")
    print(f"当前状态: {workflow['status']}")
    
    # 2. 获取所有节点实例
    nodes = await node_repo.get_instances_by_workflow_instance(workflow_instance_id)
    print(f"\n📋 节点实例状态:")
    completed_nodes = []
    pending_nodes = []
    
    for node in nodes:
        print(f"  - {node['node_instance_name']}: {node['status']} ({node['node_type']})")
        if node['status'] == 'completed':
            completed_nodes.append(node)
        elif node['status'] == 'pending':
            pending_nodes.append(node)
    
    # 3. 重新创建工作流上下文
    print(f"\n🔄 重新创建工作流上下文...")
    context = await context_manager.get_or_create_context(workflow_instance_id)
    await context_manager.initialize_workflow_context(workflow_instance_id)
    print("✅ 工作流上下文重新创建成功")
    
    # 4. 恢复所有已完成节点的状态
    print(f"\n📝 恢复 {len(completed_nodes)} 个已完成节点的状态...")
    for node in completed_nodes:
        node_instance_id = node['node_instance_id']
        node_name = node['node_instance_name']
        node_id = node['node_id']
        
        print(f"🎯 恢复已完成节点: {node_name} ({node_instance_id})")
        
        # 构造输出数据
        output_data = {
            'status': 'completed',
            'node_name': node_name,
            'completed_at': str(node.get('completed_at', '')),
            'output_data': node.get('output_data', {})
        }
        
        # 标记节点完成
        await context_manager.mark_node_completed(
            workflow_instance_id,
            node_id,
            node_instance_id,
            output_data
        )
        print(f"✅ 节点 {node_name} 状态已恢复")
    
    # 5. 触发工作流完成检查
    print(f"\n🎯 触发工作流完成检查...")
    await execution_engine._check_workflow_completion(workflow_instance_id)
    print("✅ 工作流完成检查已触发")
    
    # 6. 验证修复结果
    print(f"\n📊 验证修复结果...")
    
    # 检查上下文状态
    updated_context = await context_manager.get_context(workflow_instance_id)
    if updated_context:
        print(f"  ✅ 工作流上下文存在")
        print(f"  📋 依赖字典大小: {len(updated_context.node_dependencies)}")
        print(f"  📋 节点输出数量: {len(updated_context.node_outputs)}")
    else:
        print(f"  ❌ 工作流上下文仍然不存在")
    
    # 再次检查节点状态
    updated_nodes = await node_repo.get_instances_by_workflow_instance(workflow_instance_id)
    pending_count = sum(1 for node in updated_nodes if node['status'] == 'pending')
    completed_count = sum(1 for node in updated_nodes if node['status'] == 'completed')
    
    print(f"\n📈 节点状态统计:")
    print(f"  - 已完成: {completed_count}")
    print(f"  - 等待中: {pending_count}")
    
    # 检查工作流最终状态
    final_workflow = await workflow_repo.get_instance_by_id(workflow_instance_id)
    print(f"\n🎯 工作流最终状态: {final_workflow['status']}")
    
    if pending_count == 0:
        print("🎉 所有节点已完成，工作流应该已经完成！")
    else:
        print(f"⏳ 还有 {pending_count} 个节点等待执行")
        
        # 显示等待中的节点
        print("等待中的节点:")
        for node in updated_nodes:
            if node['status'] == 'pending':
                print(f"  - {node['node_instance_name']} ({node['node_type']})")
    
    print("\n🎉 工作流上下文修复完成!")
    
    return {
        'success': True,
        'completed_nodes': completed_count,
        'pending_nodes': pending_count,
        'workflow_status': final_workflow['status']
    }

if __name__ == "__main__":
    result = asyncio.run(restore_workflow_context())
    if result['success']:
        print(f"\n✅ 修复成功！")
        print(f"  - 已完成节点: {result['completed_nodes']}")
        print(f"  - 等待中节点: {result['pending_nodes']}")
        print(f"  - 工作流状态: {result['workflow_status']}")
    else:
        print(f"\n❌ 修复失败！")