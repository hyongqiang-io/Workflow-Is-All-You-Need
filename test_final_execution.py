#!/usr/bin/env python3
"""
最终执行测试 - 验证用户工作流执行是否正常工作
"""

import asyncio
import uuid
import json
from workflow_framework.models.instance import WorkflowExecuteRequest
from workflow_framework.services.execution_service import execution_engine
from workflow_framework.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository

async def test_user_workflow_execution():
    """测试用户的工作流执行"""
    
    # 使用用户实际的工作流ID
    workflow_base_id = uuid.UUID("298e0b74-fca7-465f-860d-d3144b5d78fc")
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
    
    print("=== 最终执行测试 ===")
    print(f"工作流ID: {workflow_base_id}")
    print(f"用户ID: {user_id}")
    
    try:
        # 启动执行引擎
        print("\n1. 启动执行引擎...")
        await execution_engine.start_engine()
        print("[OK] 执行引擎启动成功")
        
        # 创建执行请求
        request = WorkflowExecuteRequest(
            workflow_base_id=workflow_base_id,
            instance_name=f"前端测试执行_{uuid.uuid4().hex[:8]}",
            input_data={},
            context_data={}
        )
        
        print(f"\n2. 执行工作流...")
        print(f"   实例名称: {request.instance_name}")
        
        # 执行工作流
        result = await execution_engine.execute_workflow(request, user_id)
        
        print(f"\n[SUCCESS] 执行成功!")
        print(f"   实例ID: {result['instance_id']}")
        print(f"   状态: {result['status']}")
        print(f"   消息: {result['message']}")
        
        # 检查执行实例列表
        print(f"\n3. 检查执行实例...")
        workflow_instance_repo = WorkflowInstanceRepository()
        
        query = """
        SELECT wi.*, w.name as workflow_name
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id
        WHERE wi.workflow_base_id = $1
        AND wi.is_deleted = FALSE
        ORDER BY wi.created_at DESC
        LIMIT 5
        """
        
        instances = await workflow_instance_repo.db.fetch_all(query, workflow_base_id)
        print(f"   找到 {len(instances)} 个执行实例:")
        
        for instance in instances:
            print(f"   - {instance.get('instance_name')} (状态: {instance.get('status')}) - {instance.get('created_at')}")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_response_format():
    """测试API返回格式"""
    try:
        from workflow_framework.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        workflow_base_id = uuid.UUID("298e0b74-fca7-465f-860d-d3144b5d78fc")
        workflow_instance_repo = WorkflowInstanceRepository()
        
        print("\n=== 测试API响应格式 ===")
        
        # 模拟API查询
        query = """
        SELECT wi.*, w.name as workflow_name
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id
        WHERE wi.workflow_base_id = $1
        AND wi.is_deleted = FALSE
        ORDER BY wi.created_at DESC
        LIMIT 3
        """
        
        instances = await workflow_instance_repo.db.fetch_all(query, workflow_base_id)
        
        # 格式化返回数据（模拟API处理）
        formatted_instances = []
        for instance in instances:
            formatted_instances.append({
                "instance_id": str(instance["workflow_instance_id"]),
                "instance_name": instance.get("instance_name"),
                "workflow_name": instance.get("workflow_name"),
                "status": instance.get("status"),
                "executor_id": str(instance.get("executor_id")) if instance.get("executor_id") else None,
                "created_at": instance["created_at"].isoformat() if instance.get("created_at") else None,
                "updated_at": instance["updated_at"].isoformat() if instance.get("updated_at") else None,
                "input_data": instance.get("input_data", {}),
                "output_data": instance.get("output_data", {}),
                "error_message": instance.get("error_message")
            })
        
        print(f"格式化的API响应示例:")
        print(json.dumps({
            "success": True,
            "data": formatted_instances,
            "message": f"获取到 {len(formatted_instances)} 个执行实例"
        }, indent=2, ensure_ascii=False, default=str))
        
        return True
        
    except Exception as e:
        print(f"API格式测试失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("工作流执行功能最终测试")
    print("=" * 60)
    
    # Test 1: 执行工作流
    success1 = asyncio.run(test_user_workflow_execution())
    
    print("\n" + "=" * 60)
    
    # Test 2: API响应格式
    success2 = asyncio.run(test_api_response_format())
    
    print("\n" + "=" * 60)
    print("测试总结:")
    print(f"  工作流执行: {'[PASS] 通过' if success1 else '[FAIL] 失败'}")
    print(f"  API响应格式: {'[PASS] 通过' if success2 else '[FAIL] 失败'}")
    
    if success1 and success2:
        print("\n[SUCCESS] 所有测试通过！")
        print("现在可以:")
        print("  1. 重启后端服务以加载修复")
        print("  2. 在前端点击'执行工作流'应该成功")
        print("  3. 点击'执行记录'可以查看执行实例列表")
    else:
        print("\n[FAIL] 测试失败，需要进一步调试")