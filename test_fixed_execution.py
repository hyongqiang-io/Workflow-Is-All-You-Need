#!/usr/bin/env python3
"""
测试修复后的工作流执行
Test Fixed Workflow Execution
"""

import asyncio
import requests
import json
import uuid
from datetime import datetime

# 后端API基础URL
BASE_URL = "http://localhost:8001/api"

async def test_workflow_execution():
    """测试工作流执行"""
    print("=== 测试修复后的工作流执行 ===")
    
    try:
        # 1. 创建用户
        print("\n1. 创建测试用户...")
        user_data = {
            "username": f"test_user_{datetime.now().strftime('%H%M%S')}",
            "email": f"test_{datetime.now().strftime('%H%M%S')}@example.com",
            "password": "testpass123",
            "full_name": "测试用户"
        }
        
        user_response = requests.post(f"{BASE_URL}/auth/register", json=user_data)
        print(f"用户创建响应状态: {user_response.status_code}")
        
        if user_response.status_code != 201:
            print(f"用户创建失败: {user_response.text}")
            return False
            
        user_data_result = user_response.json()
        user_id = user_data_result['data']['user']['user_id']
        print(f"[OK] 用户创建成功: {user_id}")
        
        # 1.5. 用户登录获取token
        print("\n1.5. 用户登录获取认证token...")
        login_data = {
            "username_or_email": user_data["username"],
            "password": user_data["password"]
        }
        
        login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        print(f"登录响应状态: {login_response.status_code}")
        
        if login_response.status_code != 200:
            print(f"登录失败: {login_response.text}")
            return False
            
        login_result = login_response.json()
        access_token = login_result['data']['token']['access_token']
        print(f"[OK] 登录成功，获得token")
        
        # 设置认证headers
        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # 2. 创建工作流
        print("\n2. 创建测试工作流...")
        workflow_data = {
            "name": f"测试工作流_{datetime.now().strftime('%H%M%S')}",
            "description": "用于测试修复后的执行功能",
            "creator_id": user_id
        }
        
        workflow_response = requests.post(f"{BASE_URL}/workflows", json=workflow_data, headers=auth_headers)
        print(f"工作流创建响应状态: {workflow_response.status_code}")
        
        if workflow_response.status_code not in [200, 201]:
            print(f"工作流创建失败: {workflow_response.text}")
            return False
            
        workflow_result = workflow_response.json()
        workflow_base_id = workflow_result['data']['workflow']['workflow_base_id']
        print(f"[OK] 工作流创建成功: {workflow_base_id}")
        
        # 3. 创建节点
        print("\n3. 创建节点...")
        
        # 创建开始节点
        start_node_data = {
            "name": "开始节点",
            "type": "start",  # 使用小写，匹配NodeType.START
            "task_description": "工作流开始",
            "workflow_base_id": workflow_base_id,
            "position_x": 100,
            "position_y": 100
        }
        
        start_response = requests.post(f"{BASE_URL}/nodes", json=start_node_data, headers=auth_headers)
        print(f"开始节点创建响应状态: {start_response.status_code}")
        
        if start_response.status_code not in [200, 201]:
            print(f"开始节点创建失败: {start_response.text}")
            return False
            
        start_result = start_response.json() 
        start_node_base_id = start_result['data']['node']['node_base_id']
        print(f"[OK] 开始节点创建成功: {start_node_base_id}")
        
        # 创建处理节点
        processor_node_data = {
            "name": "处理节点", 
            "type": "processor",  # 使用小写，匹配NodeType.PROCESSOR
            "task_description": "处理任务",
            "workflow_base_id": workflow_base_id,
            "position_x": 300,
            "position_y": 100
        }
        
        processor_response = requests.post(f"{BASE_URL}/nodes", json=processor_node_data, headers=auth_headers)
        print(f"处理节点创建响应状态: {processor_response.status_code}")
        
        if processor_response.status_code not in [200, 201]:
            print(f"处理节点创建失败: {processor_response.text}")
            return False
            
        processor_result = processor_response.json()
        processor_node_base_id = processor_result['data']['node']['node_base_id']
        print(f"[OK] 处理节点创建成功: {processor_node_base_id}")
        
        # 创建结束节点
        end_node_data = {
            "name": "结束节点",
            "type": "end",  # 使用小写，匹配NodeType.END
            "task_description": "工作流结束",
            "workflow_base_id": workflow_base_id,
            "position_x": 500,
            "position_y": 100
        }
        
        end_response = requests.post(f"{BASE_URL}/nodes", json=end_node_data, headers=auth_headers)
        print(f"结束节点创建响应状态: {end_response.status_code}")
        
        if end_response.status_code not in [200, 201]:
            print(f"结束节点创建失败: {end_response.text}")
            return False
            
        end_result = end_response.json()
        end_node_base_id = end_result['data']['node']['node_base_id']
        print(f"[OK] 结束节点创建成功: {end_node_base_id}")
        
        # 4. 创建连接
        print("\n4. 创建节点连接...")
        
        # 开始 -> 处理
        connection1_data = {
            "from_node_base_id": start_node_base_id,
            "to_node_base_id": processor_node_base_id,
            "workflow_base_id": workflow_base_id,
            "connection_type": "normal"
        }
        
        conn1_response = requests.post(f"{BASE_URL}/nodes/connections", json=connection1_data, headers=auth_headers)
        print(f"连接1创建响应状态: {conn1_response.status_code}")
        
        if conn1_response.status_code not in [200, 201]:
            print(f"连接1创建失败: {conn1_response.text}")
            return False
            
        print("[OK] 连接1创建成功: 开始 -> 处理")
        
        # 处理 -> 结束
        connection2_data = {
            "from_node_base_id": processor_node_base_id,
            "to_node_base_id": end_node_base_id,
            "workflow_base_id": workflow_base_id,
            "connection_type": "normal"
        }
        
        conn2_response = requests.post(f"{BASE_URL}/nodes/connections", json=connection2_data, headers=auth_headers)
        print(f"连接2创建响应状态: {conn2_response.status_code}")
        
        if conn2_response.status_code not in [200, 201]:
            print(f"连接2创建失败: {conn2_response.text}")
            return False
            
        print("[OK] 连接2创建成功: 处理 -> 结束")
        
        # 5. 执行工作流
        print("\n5. 执行工作流...")
        execution_data = {
            "workflow_base_id": workflow_base_id,
            "instance_name": f"测试执行_{datetime.now().strftime('%H%M%S')}",
            "input_data": {"message": "测试执行"},
            "context_data": {}
        }
        
        execution_response = requests.post(f"{BASE_URL}/execution/workflows/execute", json=execution_data, headers=auth_headers)
        print(f"工作流执行响应状态: {execution_response.status_code}")
        print(f"响应内容: {execution_response.text}")
        
        if execution_response.status_code == 200:
            execution_result = execution_response.json()
            print(f"[OK] 工作流执行成功!")
            print(f"   实例ID: {execution_result.get('instance_id')}")
            print(f"   状态: {execution_result.get('status')}")
            print(f"   消息: {execution_result.get('message')}")
            return True
        else:
            print(f"[ERROR] 工作流执行失败: {execution_response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_workflow_execution())
    if success:
        print("\n[SUCCESS] 测试通过! 工作流执行修复成功!")
    else:
        print("\n[FAILED] 测试失败，需要进一步调试。")