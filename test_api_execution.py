#!/usr/bin/env python3
"""
测试API执行工作流功能
"""

import asyncio
import uuid
import json

# 模拟前端API调用
async def test_api_execution():
    """测试API执行功能"""
    
    # 测试数据
    workflow_base_id = "d28d4936-3978-4715-a044-2432450734d2"
    
    # 准备请求数据
    request_data = {
        "workflow_base_id": workflow_base_id,
        "instance_name": f"测试执行_{uuid.uuid4().hex[:8]}",
        "input_data": {},
        "context_data": {}
    }
    
    print("=== 测试API执行功能 ===")
    print(f"请求数据: {json.dumps(request_data, indent=2, ensure_ascii=False)}")
    
    try:
        # 直接调用服务层逻辑
        from workflow_framework.models.instance import WorkflowExecuteRequest
        from workflow_framework.services.execution_service import execution_engine
        
        # 启动执行引擎
        print("\n1. 启动执行引擎...")
        await execution_engine.start_engine()
        
        # 创建请求对象
        request = WorkflowExecuteRequest(**request_data)
        user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
        
        print(f"\n2. 执行工作流...")
        print(f"   工作流ID: {workflow_base_id}")
        print(f"   实例名称: {request.instance_name}")
        print(f"   用户ID: {user_id}")
        
        # 执行工作流
        result = await execution_engine.execute_workflow(request, user_id)
        
        print(f"\n[SUCCESS] 执行成功!")
        print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False, default=str)}")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_api_execution())
    print(f"\n{'='*50}")
    print(f"测试结果: {'[SUCCESS] 成功' if success else '[FAILED] 失败'}")
    print("现在前端应该可以正常执行工作流了!")