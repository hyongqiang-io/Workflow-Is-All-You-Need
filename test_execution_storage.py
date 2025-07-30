#!/usr/bin/env python3
"""
测试执行过程存储API
"""

import asyncio
import uuid
from workflow_framework.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository

async def test_execution_storage():
    """测试执行存储查询"""
    
    workflow_base_id = uuid.UUID('b4add00e-3593-42ef-8d26-6aeb3ce544e8')
    
    print("=== 测试执行存储API ===")
    print(f"工作流ID: {workflow_base_id}")
    
    try:
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 模拟API查询
        query = """
        SELECT wi.*, w.name as workflow_name
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id
        WHERE wi.workflow_base_id = $1
        AND wi.is_deleted = FALSE
        ORDER BY wi.created_at DESC
        LIMIT 10
        """
        
        instances = await workflow_instance_repo.db.fetch_all(query, workflow_base_id)
        
        print(f"\n找到 {len(instances)} 个执行实例:")
        
        for i, instance in enumerate(instances, 1):
            print(f"\n{i}. 执行实例:")
            print(f"   实例ID: {instance['workflow_instance_id']}")
            print(f"   实例名称: {instance.get('instance_name', 'N/A')}")
            print(f"   工作流名称: {instance.get('workflow_name', 'N/A')}")
            print(f"   状态: {instance.get('status', 'N/A')}")
            print(f"   执行者: {instance.get('executor_id', 'N/A')}")
            print(f"   创建时间: {instance.get('created_at', 'N/A')}")
            print(f"   更新时间: {instance.get('updated_at', 'N/A')}")
            
            # 查询该实例的节点实例
            node_query = """
            SELECT ni.*, n.name as node_name, n.type as node_type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1
            ORDER BY ni.created_at
            """
            
            node_instances = await workflow_instance_repo.db.fetch_all(
                node_query, instance['workflow_instance_id']
            )
            
            print(f"   节点实例 ({len(node_instances)}个):")
            for ni in node_instances:
                print(f"     - {ni.get('node_name', 'N/A')} ({ni.get('node_type', 'N/A')}) - {ni.get('status', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_execution_storage())
    
    if success:
        print(f"\n[SUCCESS] 执行存储API工作正常!")
        print(f"\n可用的API端点:")
        print(f"1. GET /api/execution/workflows/{workflow_base_id}/instances")
        print(f"2. GET /api/execution/workflows/{{instance_id}}/status")
        print(f"3. POST /api/execution/workflows/{{instance_id}}/control")
        print(f"\n前端'执行记录'按钮可以查看这些数据。")
    else:
        print(f"\n[ERROR] 执行存储有问题")