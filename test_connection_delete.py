#!/usr/bin/env python3
"""
测试连接删除API的脚本
"""

import asyncio
import uuid
from workflow_framework.services.node_service import NodeService

async def test_connection_delete():
    """测试连接删除功能"""
    node_service = NodeService()
    
    # 测试数据 - 使用实际的节点ID
    from_node_base_id = uuid.UUID("c9a7225c-76d1-4ab0-9bf0-9770d76dd921")
    to_node_base_id = uuid.UUID("07aec286-be9b-4fb4-bd87-34e3123723f7")
    workflow_base_id = uuid.UUID("241167d9-7fe4-4e7e-88df-730bffd59380")
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
    
    print(f"测试删除连接:")
    print(f"  从节点: {from_node_base_id}")
    print(f"  到节点: {to_node_base_id}")
    print(f"  工作流: {workflow_base_id}")
    print(f"  用户: {user_id}")
    
    try:
        success = await node_service.delete_node_connection(
            from_node_base_id, to_node_base_id, workflow_base_id, user_id
        )
        
        if success:
            print("SUCCESS: 连接删除成功")
        else:
            print("INFO: 连接删除完成（可能连接不存在）")
        
        return True
        
    except Exception as e:
        print(f"ERROR: 连接删除失败 - {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_connection_get():
    """测试获取工作流连接"""
    node_service = NodeService()
    
    workflow_base_id = uuid.UUID("241167d9-7fe4-4e7e-88df-730bffd59380")
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
    
    try:
        connections = await node_service.get_workflow_connections(workflow_base_id, user_id)
        print(f"当前工作流连接数量: {len(connections)}")
        for i, conn in enumerate(connections):
            print(f"  连接{i+1}: {conn.get('from_node_base_id')} -> {conn.get('to_node_base_id')}")
        return True
    except Exception as e:
        print(f"ERROR: 获取连接失败 - {e}")
        return False

if __name__ == "__main__":
    print("=== 连接功能测试 ===")
    
    print("\n1. 获取当前连接:")
    success1 = asyncio.run(test_connection_get())
    
    print("\n2. 测试删除连接:")
    success2 = asyncio.run(test_connection_delete())
    
    print("\n3. 删除后再次获取连接:")
    success3 = asyncio.run(test_connection_get())
    
    print(f"\n测试结果: {'全部通过' if all([success1, success2, success3]) else '部分失败'}")