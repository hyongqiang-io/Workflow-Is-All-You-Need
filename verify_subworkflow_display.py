#!/usr/bin/env python3
"""
验证修复后的子工作流显示功能
Verify fixed sub-workflow display functionality
"""

import asyncio
import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.api.task_subdivision import get_task_subdivisions
from backend.utils.database import initialize_database
from backend.utils.middleware import CurrentUser

class MockUser:
    def __init__(self, user_id: str, username: str):
        self.user_id = uuid.UUID(user_id)
        self.username = username

async def verify_fixed_subworkflow_display():
    """验证修复后的子工作流显示功能"""
    print("🔍 验证修复后的子工作流显示功能...")
    
    try:
        await initialize_database()
        
        # 使用用户报告的任务ID
        test_task_id = uuid.UUID("c97166a9-4099-48bf-9832-eb486e9a685f")
        mock_user = MockUser("e7b70d97-4c98-4989-98df-0ceafa6cb005", "test_user")
        
        print(f"📊 测试任务ID: {test_task_id}")
        print(f"这是用户报告问题的p1任务")
        
        # 调用API获取有实例的细分
        print(f"\n🚀 调用API (with_instances_only=True)...")
        response = await get_task_subdivisions(
            task_id=test_task_id,
            with_instances_only=True,
            current_user=mock_user
        )
        
        if response.success:
            data = response.data
            subdivisions = data.get('subdivisions', [])
            
            print(f"✅ API调用成功:")
            print(f"   - 有实例的细分数量: {data.get('count', 0)}")
            print(f"   - 总细分数量: {data.get('total_subdivisions', 0)}")
            print(f"   - 仅包含有实例的: {data.get('with_instances_only', False)}")
            
            if subdivisions:
                print(f"\n📋 详细的子工作流信息:")
                for i, subdivision in enumerate(subdivisions[:3], 1):  # 显示前3个
                    print(f"\n  子工作流 {i}:")
                    print(f"    名称: {subdivision.get('subdivision_name')}")
                    print(f"    细分ID: {subdivision.get('subdivision_id')}")
                    print(f"    细分状态: {subdivision.get('status')}")
                    
                    workflow_instance = subdivision.get('workflow_instance', {})
                    if workflow_instance:
                        print(f"    工作流实例ID: {workflow_instance.get('workflow_instance_id')}")
                        print(f"    实例名称: {workflow_instance.get('workflow_instance_name')}")
                        print(f"    实例状态: {workflow_instance.get('status')}")
                        print(f"    创建时间: {workflow_instance.get('created_at')}")
                        print(f"    完成时间: {workflow_instance.get('completed_at')}")
                        
                        # 检查是否有输出数据
                        output_data = workflow_instance.get('output_data')
                        if output_data:
                            preview = str(output_data)[:100] + '...' if len(str(output_data)) > 100 else str(output_data)
                            print(f"    输出数据: {preview}")
                        else:
                            print(f"    输出数据: 无")
                
                print(f"\n🎯 UI显示验证:")
                print(f"   - subWorkflowsForSubmit.length = {len(subdivisions)}")
                print(f"   - 显示条件 (length > 0): {len(subdivisions) > 0}")
                
                if len(subdivisions) > 0:
                    print(f"   ✅ 在UI中应该显示相关子工作流区域")
                    print(f"   📝 而不是显示'该任务没有相关的子工作流'")
                else:
                    print(f"   ❌ UI中仍会显示'该任务没有相关的子工作流'")
            else:
                print(f"\n⚠️ 该任务虽然有 {data.get('total_subdivisions', 0)} 个细分，但都没有工作流实例")
                print(f"这可能是因为:")
                print(f"  1. 细分工作流创建失败")
                print(f"  2. 工作流实例被删除")
                print(f"  3. 细分状态仍然是'created'而不是'executing'")
        else:
            print(f"❌ API调用失败: {response.message}")
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_fixed_subworkflow_display())