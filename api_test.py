#!/usr/bin/env python3
"""
API测试脚本 - 直接测试API是否正常工作
"""

import requests
import json
import uuid

def test_execution_api():
    """测试执行API"""
    
    # 测试数据
    workflow_base_id = "b4add00e-3593-42ef-8d26-6aeb3ce544e8"
    
    data = {
        "workflow_base_id": workflow_base_id,
        "instance_name": f"API测试_{uuid.uuid4().hex[:8]}",
        "input_data": {},
        "context_data": {}
    }
    
    # 测试用户的认证头（模拟前端请求）
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test-token",  # 可能需要实际token
        "X-User-ID": "e92d6bc0-3187-430d-96e0-450b6267949a"  # 测试用户ID
    }
    
    print("=== API执行测试 ===")
    print(f"URL: http://localhost:8001/api/execution/workflows/execute")
    print(f"数据: {json.dumps(data, indent=2)}")
    print(f"认证头: {headers}")
    
    try:
        response = requests.post(
            "http://localhost:8001/api/execution/workflows/execute",
            json=data,
            headers=headers,
            timeout=30
        )
        
        print(f"\n响应状态: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            print(f"响应内容: {json.dumps(response_json, indent=2, ensure_ascii=False)}")
        except:
            print(f"响应文本: {response.text}")
        
        if response.status_code == 200:
            print("\n[SUCCESS] API调用成功!")
            return True
        else:
            print(f"\n[ERROR] API调用失败: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] 连接失败 - 服务器可能没有运行在8001端口")
        return False
    except Exception as e:
        print(f"\n[ERROR] 请求异常: {e}")
        return False

def test_health_check():
    """测试健康检查API"""
    try:
        response = requests.get("http://localhost:8001/health", timeout=10)
        print(f"健康检查: HTTP {response.status_code}")
        if response.status_code == 200:
            print("✓ 服务器正在运行")
            return True
        else:
            print("✗ 服务器状态异常")
            return False
    except:
        print("✗ 无法连接到服务器")
        return False

if __name__ == "__main__":
    print("开始API测试...")
    
    # 1. 健康检查
    print("\n1. 健康检查")
    health_ok = test_health_check()
    
    if not health_ok:
        print("\n服务器无法访问，请确保后端服务在8001端口运行")
        exit(1)
    
    # 2. 执行API测试
    print("\n2. 执行API测试")
    execution_ok = test_execution_api()
    
    print(f"\n{'='*50}")
    print("测试总结:")
    print(f"  健康检查: {'✓ 通过' if health_ok else '✗ 失败'}")
    print(f"  执行API: {'✓ 通过' if execution_ok else '✗ 失败'}")
    
    if execution_ok:
        print("\n🎉 API工作正常！前端应该可以正常执行工作流了。")
        print("如果前端仍然失败，可能是认证或CORS问题。")
    else:
        print("\n❌ API有问题，需要检查服务器日志。")
        print("可能的原因:")
        print("  1. 认证中间件问题")
        print("  2. 服务没有完全重启")
        print("  3. 代码没有正确加载")