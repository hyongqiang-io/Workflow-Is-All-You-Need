#!/usr/bin/env python3
"""
测试节点更新API的脚本
"""

import asyncio
import uuid
from workflow_framework.models.node import NodeUpdate
from workflow_framework.services.node_service import NodeService

async def test_node_updates():
    """测试不同类型节点的更新"""
    node_service = NodeService()
    
    # 测试数据
    test_cases = [
        {
            "name": "start节点更新测试",
            "node_base_id": "c9a7225c-76d1-4ab0-9bf0-9770d76dd921",
            "workflow_base_id": "241167d9-7fe4-4e7e-88df-730bffd59380",
            "update_data": NodeUpdate(
                name="1",
                task_description="",
                position_x=100,
                position_y=100
            )
        },
        {
            "name": "end节点更新测试",
            "node_base_id": "c9a7225c-76d1-4ab0-9bf0-9770d76dd921",  # 替换为实际的end节点ID
            "workflow_base_id": "241167d9-7fe4-4e7e-88df-730bffd59380",
            "update_data": NodeUpdate(
                name="end",
                task_description=None,
                position_x=200,
                position_y=200
            )
        },
        {
            "name": "processor节点更新测试",
            "node_base_id": "c9a7225c-76d1-4ab0-9bf0-9770d76dd921",  # 替换为实际的processor节点ID
            "workflow_base_id": "241167d9-7fe4-4e7e-88df-730bffd59380", 
            "update_data": NodeUpdate(
                name="hhh",
                task_description="处理器节点描述",
                position_x=300,
                position_y=300
            )
        }
    ]
    
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")  # 正确的工作流创建者ID
    
    for test_case in test_cases:
        print(f"\n=== {test_case['name']} ===")
        try:
            node_base_id = uuid.UUID(test_case['node_base_id'])
            workflow_base_id = uuid.UUID(test_case['workflow_base_id'])
            
            result = await node_service.update_node(
                node_base_id,
                workflow_base_id,
                test_case['update_data'],
                user_id
            )
            
            print(f"✅ 更新成功: {result.name}")
            print(f"   位置: ({result.position_x}, {result.position_y})")
            print(f"   描述: {result.task_description}")
            print(f"   版本: {result.version}")
            
        except Exception as e:
            print(f"❌ 更新失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("开始测试节点更新功能...")
    asyncio.run(test_node_updates())
    print("\n测试完成！")