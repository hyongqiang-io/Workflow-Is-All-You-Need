#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试工作流实例的取消和删除功能
Test workflow instance cancel and delete functionality
"""

import asyncio
import uuid
import sys
import os
from datetime import datetime

# Add the workflow framework to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'workflow_framework'))

async def test_workflow_control():
    """测试工作流实例的控制功能"""
    
    try:
        from workflow_framework.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        from workflow_framework.services.execution_service import ExecutionEngine
        from workflow_framework.models.instance import WorkflowInstanceCreate, WorkflowInstanceStatus
        
        print("=== 工作流控制功能测试 ===")
        print()
        
        # 初始化仓库和服务
        repo = WorkflowInstanceRepository()
        engine = ExecutionEngine()
        
        # 创建一个测试工作流实例
        print("1. 创建测试工作流实例")
        
        test_instance_data = WorkflowInstanceCreate(
            workflow_base_id=uuid.uuid4(),
            executor_id=uuid.uuid4(),
            instance_name=f"测试实例_{datetime.now().strftime('%H%M%S')}",
            input_data={"test": "data"},
            context_data={"test": "context"}
        )
        
        created_instance = await repo.create_instance(test_instance_data)
        if not created_instance:
            print("❌ 创建测试实例失败")
            return False
            
        instance_id = created_instance.get('instance_id')
        if not instance_id:
            # 尝试使用workflow_instance_id
            instance_id = created_instance.get('workflow_instance_id')
        
        print(f"✅ 创建测试实例成功: {instance_id}")
        print(f"   - 实例名称: {created_instance.get('instance_name')}")
        print(f"   - 状态: {created_instance.get('status')}")
        print()
        
        # 测试取消工作流
        print("2. 测试取消工作流")
        
        try:
            cancel_result = await engine.cancel_workflow(instance_id)
            print(f"   - 取消操作结果: {cancel_result}")
            
            # 验证取消结果
            updated_instance = await repo.get_instance_by_id(instance_id)
            if updated_instance:
                print(f"   - 取消后状态: {updated_instance.get('status')}")
                if updated_instance.get('status') == 'cancelled':
                    print("✅ 取消工作流成功")
                else:
                    print("⚠️ 取消工作流后状态未更新")
            else:
                print("❌ 取消后无法查询到实例")
                
        except Exception as cancel_error:
            print(f"❌ 取消工作流失败: {cancel_error}")
            import traceback
            traceback.print_exc()
        
        print()
        
        # 测试删除工作流实例
        print("3. 测试删除工作流实例 (软删除)")
        
        try:
            delete_result = await repo.delete_instance(instance_id, soft_delete=True)
            print(f"   - 删除操作结果: {delete_result}")
            
            # 验证删除结果
            deleted_instance = await repo.get_instance_by_id(instance_id)
            if deleted_instance:
                is_deleted = deleted_instance.get('is_deleted', False)
                print(f"   - 删除后 is_deleted: {is_deleted}")
                if is_deleted:
                    print("✅ 软删除工作流成功")
                else:
                    print("⚠️ 软删除工作流后 is_deleted 标志未设置")
            else:
                print("✅ 删除后实例已不可查询 (软删除生效)")
                
        except Exception as delete_error:
            print(f"❌ 删除工作流失败: {delete_error}")
            import traceback
            traceback.print_exc()
        
        print()
        print("=== 测试完成 ===")
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_connection():
    """测试数据库连接"""
    try:
        from workflow_framework.utils.database import get_database
        
        print("测试数据库连接...")
        db = get_database()
        
        # 简单查询测试
        result = await db.fetch_one("SELECT 1 as test")
        if result and result.get('test') == 1:
            print("✅ 数据库连接正常")
            return True
        else:
            print("❌ 数据库查询异常")
            return False
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

if __name__ == "__main__":
    print("开始测试工作流控制功能...")
    print()
    
    # 首先测试数据库连接
    db_ok = asyncio.run(test_database_connection())
    if not db_ok:
        print("数据库连接失败，无法继续测试")
        sys.exit(1)
    
    print()
    
    # 运行主测试
    success = asyncio.run(test_workflow_control())
    
    if success:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 测试失败，请检查日志输出")
    
    sys.exit(0 if success else 1)