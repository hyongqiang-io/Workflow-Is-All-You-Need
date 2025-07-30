#!/usr/bin/env python3
"""
测试所有问题节点的更新功能
"""
import asyncio
import asyncpg
import uuid
from workflow_framework.config import get_settings
from workflow_framework.services.node_service import NodeService
from workflow_framework.models.node import NodeUpdate

async def test_all_problem_nodes():
    """测试所有问题节点"""
    print("=== 测试所有问题节点更新 ===")
    
    # 获取正确的用户ID
    settings = get_settings()
    conn = await asyncpg.connect(settings.database.database_url)
    
    workflow_base_id = uuid.UUID("7925f55c-9107-4f5b-ad91-9f628659b5c0")
    
    workflow_info = await conn.fetchrow("""
        SELECT creator_id FROM workflow 
        WHERE workflow_base_id = $1 AND is_current_version = true
    """, workflow_base_id)
    
    await conn.close()
    
    if not workflow_info:
        print("  [ERROR] 找不到工作流")
        return
        
    creator_id = workflow_info['creator_id']
    print(f"使用工作流创建者ID: {creator_id}")
    
    # 问题节点列表
    problem_nodes = [
        ("fe50944c-1388-4cd9-b25f-804d6ae07931", "节点1更新测试"),
        ("57b7baf4-02b9-4141-8575-84e1e4c8b00e", "节点2更新测试"), 
        ("22f9346d-c760-4234-a5c0-ae613faead7e", "节点3更新测试")
    ]
    
    node_service = NodeService()
    
    for node_base_id_str, new_name in problem_nodes:
        node_base_id = uuid.UUID(node_base_id_str)
        
        print(f"\n测试节点: {node_base_id}")
        
        try:
            # 获取节点
            node = await node_service.get_node_by_base_id(node_base_id, workflow_base_id)
            
            if not node:
                print(f"  [ERROR] 节点获取失败")
                continue
                
            print(f"  [OK] 获取节点成功: {node.name}")
            
            # 更新节点
            update_data = NodeUpdate(
                name=new_name,
                task_description=f"修复404错误后的测试更新 - {node_base_id}",
                position_x=150,
                position_y=250
            )
            
            updated_node = await node_service.update_node(
                node_base_id, workflow_base_id, update_data, creator_id
            )
            
            print(f"  [OK] 节点更新成功: {updated_node.name}")
            print(f"       描述: {updated_node.task_description}")
            print(f"       位置: ({updated_node.position_x}, {updated_node.position_y})")
            
        except Exception as e:
            print(f"  [ERROR] 节点操作失败: {e}")

async def test_api_simulation():
    """模拟API调用测试"""
    print(f"\n=== 模拟API调用测试 ===")
    
    try:
        from workflow_framework.api.node import update_node
        from workflow_framework.models.node import NodeUpdate
        from workflow_framework.utils.middleware import CurrentUser
        
        # 模拟用户对象
        mock_user = CurrentUser(
            user_id=uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a"),
            username="hhhh"
        )
        
        # 测试第一个节点
        node_base_id = uuid.UUID("fe50944c-1388-4cd9-b25f-804d6ae07931")
        workflow_base_id = uuid.UUID("7925f55c-9107-4f5b-ad91-9f628659b5c0")
        
        update_data = NodeUpdate(
            name="API模拟测试",
            task_description="通过模拟API调用进行的测试"
        )
        
        # 调用API函数
        response = await update_node(
            node_base_id=node_base_id,
            workflow_base_id=workflow_base_id, 
            node_data=update_data,
            current_user=mock_user
        )
        
        if response.success:
            print(f"  [OK] API调用成功: {response.message}")
            print(f"       返回数据: {response.data['node']['name']}")
        else:
            print(f"  [ERROR] API调用失败: {response.message}")
            
    except Exception as e:
        print(f"  [ERROR] API调用异常: {e}")

async def main():
    print("开始测试所有问题节点...\n")
    
    await test_all_problem_nodes()
    await test_api_simulation()
    
    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())