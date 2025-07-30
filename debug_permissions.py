#!/usr/bin/env python3
"""
调试权限问题的脚本
"""
import asyncio
import asyncpg
import uuid
from workflow_framework.config import get_settings

async def debug_permissions():
    """调试权限问题"""
    settings = get_settings()
    conn = await asyncpg.connect(settings.database.database_url)
    
    print("=== 调试权限问题 ===")
    
    workflow_base_id = "7925f55c-9107-4f5b-ad91-9f628659b5c0"
    
    # 1. 查看工作流的创建者
    workflow_info = await conn.fetchrow("""
        SELECT w.workflow_id, w.workflow_base_id, w.name, w.creator_id, u.username as creator_name
        FROM workflow w
        LEFT JOIN "user" u ON u.user_id = w.creator_id
        WHERE w.workflow_base_id = $1 AND w.is_current_version = true
    """, uuid.UUID(workflow_base_id))
    
    if workflow_info:
        print(f"工作流信息:")
        print(f"  - name: {workflow_info['name']}")
        print(f"  - creator_id: {workflow_info['creator_id']}")
        print(f"  - creator_name: {workflow_info['creator_name']}")
    else:
        print("工作流不存在")
        await conn.close()
        return
    
    # 2. 查看所有用户
    users = await conn.fetch("SELECT user_id, username FROM \"user\" WHERE is_deleted = false")
    print(f"\n系统中的用户:")
    for user in users:
        print(f"  - {user['username']} (ID: {user['user_id']})")
    
    # 3. 查看节点的创建情况
    problem_nodes = [
        "fe50944c-1388-4cd9-b25f-804d6ae07931",
        "57b7baf4-02b9-4141-8575-84e1e4c8b00e", 
        "22f9346d-c760-4234-a5c0-ae613faead7e"
    ]
    
    print(f"\n节点详细信息:")
    for node_base_id in problem_nodes:
        node_info = await conn.fetchrow("""
            SELECT n.node_id, n.node_base_id, n.name, n.created_at,
                   w.creator_id as workflow_creator_id
            FROM "node" n
            JOIN workflow w ON w.workflow_id = n.workflow_id
            WHERE n.node_base_id = $1 AND n.workflow_base_id = $2
            AND n.is_current_version = true
        """, uuid.UUID(node_base_id), uuid.UUID(workflow_base_id))
        
        if node_info:
            print(f"  节点 '{node_info['name']}':")
            print(f"    - node_base_id: {node_info['node_base_id']}")
            print(f"    - workflow_creator_id: {node_info['workflow_creator_id']}")
            print(f"    - created_at: {node_info['created_at']}")
    
    await conn.close()

async def test_with_correct_user():
    """使用正确的用户测试节点更新"""
    print(f"\n=== 使用正确用户测试 ===")
    
    try:
        from workflow_framework.services.node_service import NodeService
        from workflow_framework.models.node import NodeUpdate
        
        # 从数据库获取工作流创建者ID
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
        
        node_service = NodeService()
        
        # 使用第一个有问题的节点
        node_base_id = uuid.UUID("fe50944c-1388-4cd9-b25f-804d6ae07931")
        
        print(f"测试获取节点...")
        node = await node_service.get_node_by_base_id(node_base_id, workflow_base_id)
        
        if node:
            print(f"  [OK] 节点获取成功: {node.name}")
            
            # 尝试更新节点
            update_data = NodeUpdate(
                name="权限测试更新",
                task_description="使用正确用户ID测试"
            )
            
            print(f"测试更新节点...")
            try:
                updated_node = await node_service.update_node(
                    node_base_id, workflow_base_id, update_data, creator_id
                )
                print(f"  [OK] 节点更新成功: {updated_node.name}")
            except Exception as update_error:
                print(f"  [ERROR] 节点更新失败: {update_error}")
                
        else:
            print(f"  [ERROR] 节点获取失败")
            
    except Exception as e:
        print(f"  [ERROR] 测试异常: {e}")

async def main():
    print("开始调试权限问题...\n")
    
    await debug_permissions()
    await test_with_correct_user()
    
    print("\n调试完成!")

if __name__ == "__main__":
    asyncio.run(main())