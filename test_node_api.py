#!/usr/bin/env python3
"""
测试节点API的脚本
"""
import asyncio
import asyncpg
import requests
import json
import uuid
from workflow_framework.config import get_settings

async def test_database_direct():
    """直接测试数据库查询"""
    settings = get_settings()
    conn = await asyncpg.connect(settings.database.database_url)
    
    print("=== 直接数据库查询测试 ===")
    
    # 查找所有节点
    nodes = await conn.fetch("""
        SELECT node_base_id, workflow_base_id, name, is_current_version, is_deleted
        FROM node 
        WHERE is_current_version = true AND is_deleted = false
        ORDER BY created_at DESC
        LIMIT 5
    """)
    
    print(f"找到 {len(nodes)} 个当前版本节点:")
    for node in nodes:
        print(f"  - {node['name']} (node_base_id: {node['node_base_id']}, workflow_base_id: {node['workflow_base_id']})")
    
    # 测试get_node_by_base_id查询
    if nodes:
        test_node = nodes[0]
        node_base_id = test_node['node_base_id']
        workflow_base_id = test_node['workflow_base_id']
        
        print(f"\n测试查询节点 {node_base_id} 在工作流 {workflow_base_id} 中:")
        
        result = await conn.fetchrow("""
            SELECT * FROM "node" 
            WHERE node_base_id = $1 
            AND workflow_base_id = $2
            AND is_current_version = true 
            AND is_deleted = false
        """, node_base_id, workflow_base_id)
        
        if result:
            print(f"  ✅ 数据库查询成功: {result['name']}")
            return str(node_base_id), str(workflow_base_id)
        else:
            print(f"  ❌ 数据库查询失败")
    
    await conn.close()
    return None, None

def test_api_endpoint(node_base_id, workflow_base_id):
    """测试API端点"""
    print(f"\n=== API端点测试 ===")
    
    # 首先测试健康检查
    try:
        response = requests.get("http://localhost:8001/health")
        print(f"健康检查: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ 后端服务无法连接: {e}")
        return
    
    # 测试节点更新API
    if node_base_id and workflow_base_id:
        url = f"http://localhost:8001/api/nodes/{node_base_id}/workflow/{workflow_base_id}"
        
        # 准备测试数据
        test_data = {
            "name": "测试更新节点",
            "task_description": "API测试描述",
            "position_x": 100,
            "position_y": 200
        }
        
        headers = {
            "Content-Type": "application/json",
            # 注意：这里可能需要JWT token，先不加看看
        }
        
        print(f"测试URL: {url}")
        print(f"测试数据: {json.dumps(test_data, ensure_ascii=False)}")
        
        try:
            response = requests.put(url, json=test_data, headers=headers)
            print(f"API响应: {response.status_code}")
            print(f"响应内容: {response.text}")
            
            if response.status_code == 401:
                print("❌ 需要认证，401错误")
            elif response.status_code == 404:
                print("❌ 节点不存在，404错误")
            elif response.status_code == 200:
                print("✅ API调用成功")
            else:
                print(f"❌ 其他错误: {response.status_code}")
                
        except Exception as e:
            print(f"❌ API调用异常: {e}")

async def main():
    print("开始节点API测试...\n")
    
    # 测试数据库直接查询
    node_base_id, workflow_base_id = await test_database_direct()
    
    # 测试API端点
    test_api_endpoint(node_base_id, workflow_base_id)
    
    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())