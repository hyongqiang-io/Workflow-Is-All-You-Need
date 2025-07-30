"""
测试节点创建功能
"""

import asyncio
import httpx
import json
from datetime import datetime

# API配置
API_BASE = "http://localhost:8000"

async def test_node_creation():
    """测试节点创建功能"""
    print("=== 测试节点创建功能 ===")
    
    try:
        # 1. 先注册用户
        print("\n1. 注册测试用户...")
        register_data = {
            "username": f"testuser_{datetime.now().strftime('%H%M%S')}",
            "email": f"test_{datetime.now().strftime('%H%M%S')}@example.com",
            "password": "testpass123"
        }
        
        async with httpx.AsyncClient() as client:
            # 注册
            register_response = await client.post(
                f"{API_BASE}/api/auth/register",
                json=register_data,
                headers={"Content-Type": "application/json"}
            )
            
            if register_response.status_code != 201:
                print(f"❌ 注册失败: {register_response.status_code}")
                print(f"响应: {register_response.text}")
                return
            
            register_result = register_response.json()
            if not register_result.get("success"):
                print(f"❌ 注册失败: {register_result.get('message')}")
                return
            
            print("✅ 用户注册成功")
            
            # 2. 用户登录
            print("\n2. 用户登录...")
            login_data = {
                "username_or_email": register_data["username"],
                "password": register_data["password"]
            }
            
            login_response = await client.post(
                f"{API_BASE}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            if login_response.status_code != 200:
                print(f"❌ 登录失败: {login_response.status_code}")
                print(f"响应: {login_response.text}")
                return
            
            login_result = login_response.json()
            if not login_result.get("success"):
                print(f"❌ 登录失败: {login_result.get('message')}")
                return
            
            token = login_result["data"]["token"]["access_token"]
            print("✅ 登录成功")
            
            # 3. 创建工作流
            print("\n3. 创建工作流...")
            workflow_data = {
                "name": f"测试工作流_{datetime.now().strftime('%H%M%S')}",
                "description": "用于测试节点创建的工作流"
            }
            
            workflow_response = await client.post(
                f"{API_BASE}/api/workflows",
                json=workflow_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                follow_redirects=False
            )
            
            print(f"工作流创建响应状态码: {workflow_response.status_code}")
            print(f"工作流创建响应头: {dict(workflow_response.headers)}")
            print(f"工作流创建响应: {workflow_response.text}")
            
            if workflow_response.status_code != 201:
                print(f"❌ 创建工作流失败: {workflow_response.status_code}")
                return
            
            workflow_result = workflow_response.json()
            if not workflow_result.get("success"):
                print(f"❌ 创建工作流失败: {workflow_result.get('message')}")
                return
            
            workflow_id = workflow_result["data"]["workflow"]["workflow_base_id"]
            print(f"✅ 工作流创建成功: {workflow_id}")
            
            # 4. 创建节点
            print("\n4. 创建节点...")
            node_data = {
                "name": "测试节点",
                "type": "processor",
                "task_description": "这是一个测试节点",
                "position_x": 100,
                "position_y": 200
            }
            
            node_response = await client.post(
                f"{API_BASE}/api/workflows/{workflow_id}/nodes",
                json=node_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
            )
            
            print(f"节点创建响应状态码: {node_response.status_code}")
            print(f"节点创建响应: {json.dumps(node_response.json(), indent=2, ensure_ascii=False)}")
            
            if node_response.status_code == 201:
                node_result = node_response.json()
                if node_result.get("success"):
                    print("✅ 节点创建成功")
                    print(f"节点ID: {node_result['data']['node']['node_id']}")
                else:
                    print(f"❌ 节点创建失败: {node_result.get('message')}")
            else:
                print(f"❌ 节点创建失败: {node_response.status_code}")
                print(f"错误响应: {node_response.text}")
                
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_node_creation()) 