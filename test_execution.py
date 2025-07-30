#!/usr/bin/env python3
"""
测试工作流执行功能
"""

import asyncio
import uuid
from workflow_framework.models.instance import WorkflowExecuteRequest
from workflow_framework.services.execution_service import execution_engine

async def test_workflow_execution():
    """测试工作流执行"""
    
    # 测试数据 - 使用新创建的工作流
    workflow_base_id = uuid.UUID("d28d4936-3978-4715-a044-2432450734d2")
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
    
    request = WorkflowExecuteRequest(
        workflow_base_id=workflow_base_id,
        instance_name=f"测试执行_{uuid.uuid4().hex[:8]}",
        input_data={},
        context_data={}
    )
    
    print(f"测试工作流执行:")
    print(f"  工作流ID: {workflow_base_id}")
    print(f"  实例名称: {request.instance_name}")
    print(f"  用户ID: {user_id}")
    
    try:
        result = await execution_engine.execute_workflow(request, user_id)
        print(f"SUCCESS: 工作流执行成功")
        print(f"结果: {result}")
        return True
        
    except Exception as e:
        print(f"ERROR: 工作流执行失败 - {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_engine_status():
    """测试执行引擎状态"""
    try:
        print("检查执行引擎状态...")
        # 简单检查引擎是否可用
        if hasattr(execution_engine, 'status'):
            print(f"引擎状态: {execution_engine.status}")
        else:
            print("引擎状态: 可用")
        return True
    except Exception as e:
        print(f"ERROR: 引擎状态检查失败 - {e}")
        return False

if __name__ == "__main__":
    print("=== 工作流执行测试 ===")
    
    print("\n1. 检查执行引擎状态:")
    success1 = asyncio.run(test_engine_status())
    
    print("\n2. 测试工作流执行:")
    success2 = asyncio.run(test_workflow_execution())
    
    print(f"\n测试结果: {'全部通过' if all([success1, success2]) else '部分失败'}")