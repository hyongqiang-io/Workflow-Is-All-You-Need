#!/usr/bin/env python3
"""
模拟前端快速点击测试防护机制
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.services.task_subdivision_service import TaskSubdivisionService
from backend.models.task_subdivision import TaskSubdivisionCreate
from backend.utils.database import initialize_database
import uuid

async def simulate_rapid_clicks():
    """模拟用户快速点击导致的重复请求"""
    print("🚀 模拟用户快速点击导致的重复请求...")
    
    try:
        await initialize_database()
        
        subdivision_service = TaskSubdivisionService()
        
        # 使用一个真实的任务ID
        real_task_id = uuid.UUID("c97166a9-4099-48bf-9832-eb486e9a685f")  # 从上面的测试中获取
        
        # 创建测试数据
        test_subdivision_data = TaskSubdivisionCreate(
            original_task_id=real_task_id,
            subdivider_id=uuid.UUID("e7b70d97-4c98-4989-98df-0ceafa6cb005"),
            subdivision_name="快速点击测试",  # 唯一的名称
            subdivision_description="测试快速点击防护机制",
            sub_workflow_base_id=None,  # 新工作流
            sub_workflow_data={
                "nodes": [
                    {
                        "id": "start_1",
                        "name": "开始",
                        "type": "start",
                        "task_description": "测试开始",
                        "position_x": 100,
                        "position_y": 100
                    },
                    {
                        "id": "end_1",
                        "name": "结束", 
                        "type": "end",
                        "task_description": "测试结束",
                        "position_x": 300,
                        "position_y": 100
                    }
                ],
                "connections": [
                    {
                        "from": "start_1",
                        "to": "end_1",
                        "connection_type": "normal"
                    }
                ]
            },
            context_to_pass="测试上下文"
        )
        
        print(f"📋 测试任务ID: {real_task_id}")
        print(f"📋 细分名称: {test_subdivision_data.subdivision_name}")
        
        # 模拟快速点击 - 并发发送3个相同的请求
        print("\n🔥 开始模拟3个并发的相同请求（模拟快速点击）...")
        
        tasks = []
        for i in range(3):
            task = subdivision_service.create_task_subdivision(test_subdivision_data, False)
            tasks.append(task)
        
        # 并发执行所有请求
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"\n📊 并发请求结果:")
        successful_results = []
        
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                print(f"   请求{i}: ❌ 异常 - {result}")
            else:
                successful_results.append(result)
                print(f"   请求{i}: ✅ 成功 - 细分ID: {result.subdivision_id}")
                print(f"           工作流ID: {result.sub_workflow_base_id}")
        
        # 分析结果
        if len(successful_results) > 1:
            # 检查是否返回了相同的细分ID（防护机制的期望行为）
            subdivision_ids = [r.subdivision_id for r in successful_results]
            unique_subdivision_ids = set(subdivision_ids)
            
            if len(unique_subdivision_ids) == 1:
                print(f"\n✅ 防护机制工作正常！")
                print(f"   所有请求都返回了相同的细分ID: {list(unique_subdivision_ids)[0]}")
            else:
                print(f"\n⚠️ 防护机制可能有问题！")
                print(f"   返回了不同的细分ID: {unique_subdivision_ids}")
                
            # 检查工作流ID
            workflow_ids = [r.sub_workflow_base_id for r in successful_results if r.sub_workflow_base_id]
            unique_workflow_ids = set(workflow_ids)
            
            if len(unique_workflow_ids) <= 1:
                print(f"   工作流ID一致性: ✅ 正常")
            else:
                print(f"   工作流ID一致性: ⚠️ 异常 - {unique_workflow_ids}")
        
        elif len(successful_results) == 1:
            print(f"\n✅ 只有1个请求成功，其他被防护机制拦截")
        else:
            print(f"\n❌ 所有请求都失败了")
        
        print("\n🎯 测试总结:")
        print(f"   发送请求数: 3")
        print(f"   成功请求数: {len(successful_results)}")
        print(f"   异常请求数: {3 - len(successful_results)}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simulate_rapid_clicks())