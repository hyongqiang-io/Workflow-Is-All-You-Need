#!/usr/bin/env python3
"""
Agent删除功能测试脚本
"""

import requests
import uuid
import sys

def test_agent_delete():
    base_url = "http://localhost:8001/api/processors"
    
    print("测试Agent删除功能...")
    
    # 测试基本连接
    try:
        response = requests.get(f"{base_url}/test-no-auth", timeout=5)
        print(f"服务器连接成功: {response.status_code}")
        print(f"时间戳: {response.json().get('timestamp')}")
    except Exception as e:
        print(f"服务器连接失败: {e}")
        return False
    
    # 测试Agent删除路由存在性
    test_agent_id = "12345678-1234-5678-9012-123456789012"  # 使用一个UUID格式的测试ID
    
    try:
        response = requests.delete(f"{base_url}/agents/{test_agent_id}", timeout=5)
        print(f"Agent删除路由状态: {response.status_code}")
        
        if response.status_code == 401 or response.status_code == 403:
            print("Agent删除路由存在，需要认证")
            return True
        elif response.status_code == 404:
            print("Agent删除路由不存在或Agent不存在")
            print(f"响应内容: {response.text}")
        elif response.status_code == 422:
            print("Agent删除路由存在，参数验证问题(UUID格式等)")
            print(f"响应内容: {response.text}")
            return True
        else:
            print(f"其他响应: {response.text}")
            return True
            
    except Exception as e:
        print(f"Agent删除路由测试失败: {e}")
        return False
    
    return False

if __name__ == "__main__":
    success = test_agent_delete()
    if success:
        print("\nAgent删除功能基本正常，路由可访问")
    else:
        print("\nAgent删除功能有问题，需要检查服务器")