#!/usr/bin/env python3
"""
调试节点404错误的脚本
"""
import asyncio
import asyncpg
import uuid
from workflow_framework.config import get_settings

async def debug_node_exists():
    """调试节点存在性问题"""
    settings = get_settings()
    conn = await asyncpg.connect(settings.database.database_url)
    
    print("=== 调试节点404错误 ===")
    
    # 错误信息中的节点ID
    problem_nodes = [
        "fe50944c-1388-4cd9-b25f-804d6ae07931",
        "57b7baf4-02b9-4141-8575-84e1e4c8b00e", 
        "22f9346d-c760-4234-a5c0-ae613faead7e"
    ]
    
    workflow_base_id = "7925f55c-9107-4f5b-ad91-9f628659b5c0"
    
    for node_base_id in problem_nodes:
        print(f"\n检查节点: {node_base_id}")
        
        # 1. 检查节点是否存在
        node_exists = await conn.fetchrow("""
            SELECT node_id, node_base_id, workflow_base_id, name, is_current_version, is_deleted
            FROM "node" 
            WHERE node_base_id = $1 AND workflow_base_id = $2
        """, uuid.UUID(node_base_id), uuid.UUID(workflow_base_id))
        
        if node_exists:
            print(f"  [OK] 节点存在于数据库中:")
            print(f"    - name: {node_exists['name']}")
            print(f"    - is_current_version: {node_exists['is_current_version']}")
            print(f"    - is_deleted: {node_exists['is_deleted']}")
        else:
            print(f"  [ERROR] 节点不存在于数据库中")
            continue
            
        # 2. 检查当前版本节点
        current_node = await conn.fetchrow("""
            SELECT * FROM "node" 
            WHERE node_base_id = $1 
            AND workflow_base_id = $2
            AND is_current_version = true 
            AND is_deleted = false
        """, uuid.UUID(node_base_id), uuid.UUID(workflow_base_id))
        
        if current_node:
            print(f"  [OK] 节点符合当前版本查询条件")
        else:
            print(f"  [ERROR] 节点不符合当前版本查询条件")
            
        # 3. 检查工作流是否存在
        workflow_exists = await conn.fetchrow("""
            SELECT workflow_id, workflow_base_id, name, is_current_version, is_deleted
            FROM workflow 
            WHERE workflow_base_id = $1
        """, uuid.UUID(workflow_base_id))
        
        if workflow_exists:
            print(f"  [OK] 工作流存在:")
            print(f"    - name: {workflow_exists['name']}")
            print(f"    - is_current_version: {workflow_exists['is_current_version']}")
            print(f"    - is_deleted: {workflow_exists['is_deleted']}")
        else:
            print(f"  [ERROR] 工作流不存在")
            
        # 4. 测试NodeRepository的查询方法
        try:
            from workflow_framework.repositories.node.node_repository import NodeRepository
            node_repo = NodeRepository()
            
            result = await node_repo.get_node_by_base_id(
                uuid.UUID(node_base_id), uuid.UUID(workflow_base_id)
            )
            
            if result:
                print(f"  [OK] NodeRepository查询成功: {result['name']}")
            else:
                print(f"  [ERROR] NodeRepository查询返回None")
                
        except Exception as e:
            print(f"  [ERROR] NodeRepository查询异常: {e}")
    
    await conn.close()

async def test_node_service():
    """测试NodeService的update_node方法"""
    print(f"\n=== 测试NodeService ===")
    
    try:
        from workflow_framework.services.node_service import NodeService
        from workflow_framework.models.node import NodeUpdate, NodeType
        
        node_service = NodeService()
        
        # 使用第一个有问题的节点
        node_base_id = uuid.UUID("fe50944c-1388-4cd9-b25f-804d6ae07931")
        workflow_base_id = uuid.UUID("7925f55c-9107-4f5b-ad91-9f628659b5c0") 
        user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")  # 假设的用户ID
        
        print(f"测试获取节点...")
        node = await node_service.get_node_by_base_id(node_base_id, workflow_base_id)
        
        if node:
            print(f"  [OK] 节点获取成功: {node.name}")
            
            # 尝试更新节点
            update_data = NodeUpdate(
                name="测试更新",
                task_description="测试描述"
            )
            
            print(f"测试更新节点...")
            try:
                updated_node = await node_service.update_node(
                    node_base_id, workflow_base_id, update_data, user_id
                )
                print(f"  [OK] 节点更新成功: {updated_node.name}")
            except Exception as update_error:
                print(f"  [ERROR] 节点更新失败: {update_error}")
                
        else:
            print(f"  [ERROR] 节点获取失败")
            
    except Exception as e:
        print(f"  [ERROR] NodeService测试异常: {e}")

async def main():
    print("开始调试节点404错误...\n")
    
    await debug_node_exists()
    await test_node_service()
    
    print("\n调试完成!")

if __name__ == "__main__":
    asyncio.run(main())