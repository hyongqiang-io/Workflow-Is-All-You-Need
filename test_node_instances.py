#!/usr/bin/env python3
"""
测试节点实例创建和查找
"""

import asyncio
import uuid
from workflow_framework.models.instance import WorkflowExecuteRequest
from workflow_framework.services.execution_service import execution_engine
from workflow_framework.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository

async def test_node_instance_creation():
    """测试节点实例创建和START节点查找"""
    
    # 测试数据
    workflow_base_id = uuid.UUID("d28d4936-3978-4715-a044-2432450734d2")
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
    
    request = WorkflowExecuteRequest(
        workflow_base_id=workflow_base_id,
        instance_name=f"测试实例_{uuid.uuid4().hex[:8]}",
        input_data={},
        context_data={}
    )
    
    print(f"=== 测试节点实例创建 ===")
    print(f"工作流ID: {workflow_base_id}")
    print(f"实例名称: {request.instance_name}")
    
    try:
        # 初始化执行引擎
        print("\n1. 启动执行引擎...")
        await execution_engine.start_engine()
        
        # 尝试执行工作流
        print("\n2. 执行工作流...")
        result = await execution_engine.execute_workflow(request, user_id)
        print(f"执行结果: {result}")
        
        # 检查工作流实例是否创建成功
        workflow_instance_repo = WorkflowInstanceRepository()
        instance_id = result.get('instance_id')
        if instance_id:
            print(f"\n3. 检查工作流实例: {instance_id}")
            instance = await workflow_instance_repo.get_instance_by_id(uuid.UUID(instance_id))
            if instance:
                print(f"工作流实例状态: {instance.get('status')}")
                
                # 手动测试_get_start_nodes方法
                print(f"\n4. 测试START节点查找...")
                start_nodes = await execution_engine._get_start_nodes(uuid.UUID(instance_id))
                print(f"找到START节点数量: {len(start_nodes)}")
                for node in start_nodes:
                    print(f"  - 节点: {node.get('node_instance_name')} (类型: {node.get('node_type')}) (状态: {node.get('status')})")
            else:
                print("错误: 工作流实例未找到")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_existing_instances():
    """检查现有的工作流实例"""
    try:
        print("\n=== 检查现有工作流实例 ===")
        workflow_instance_repo = WorkflowInstanceRepository()
        
        # 获取最近的实例
        query = """
        SELECT wi.*, w.name as workflow_name
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id
        ORDER BY wi.created_at DESC
        LIMIT 5
        """
        
        instances = await workflow_instance_repo.db.fetch_all(query)
        print(f"找到 {len(instances)} 个工作流实例:")
        
        for instance in instances:
            print(f"  - 实例: {instance.get('instance_name')} (ID: {instance.get('workflow_instance_id')})")
            print(f"    工作流: {instance.get('workflow_name')} (状态: {instance.get('status')})")
            
            # 检查这个实例的节点实例
            instance_id = instance.get('workflow_instance_id')
            if instance_id:
                node_query = """
                SELECT ni.*, n.name as node_name, n.type as node_type
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = $1
                """
                
                node_instances = await workflow_instance_repo.db.fetch_all(node_query, instance_id)
                print(f"    节点实例数量: {len(node_instances)}")
                for ni in node_instances:
                    print(f"      - {ni.get('node_name')} (类型: {ni.get('node_type')}) (状态: {ni.get('status')})")
                    
    except Exception as e:
        print(f"检查实例时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== 节点实例测试 ===")
    
    # 检查现有实例
    asyncio.run(check_existing_instances())
    
    # 创建新实例并测试
    print("\n" + "="*50)
    success = asyncio.run(test_node_instance_creation())
    
    print(f"\n测试结果: {'成功' if success else '失败'}")