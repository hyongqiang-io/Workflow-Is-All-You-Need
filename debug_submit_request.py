#!/usr/bin/env python3
"""
调试任务提交请求
Debug Task Submit Request
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.api.execution import TaskSubmissionRequest
from pydantic import ValidationError

async def test_task_submission_validation():
    """测试任务提交请求的验证"""
    
    print("Testing TaskSubmissionRequest validation...")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "name": "空请求",
            "data": {}
        },
        {
            "name": "空字符串result_data",
            "data": {"result_data": ""}
        },
        {
            "name": "None result_data",
            "data": {"result_data": None}
        },
        {
            "name": "缺少result_data字段", 
            "data": {"result_summary": "测试摘要"}
        },
        {
            "name": "正确的请求格式",
            "data": {
                "result_data": {"answer": "测试回答", "notes": "测试备注"},
                "result_summary": "任务完成"
            }
        },
        {
            "name": "最小有效请求",
            "data": {"result_data": {}}
        },
        {
            "name": "只有result_data",
            "data": {"result_data": {"key": "value"}}
        }
    ]
    
    for test_case in test_cases:
        print(f"\n测试用例: {test_case['name']}")
        print(f"请求数据: {json.dumps(test_case['data'], ensure_ascii=False)}")
        print(f"JSON长度: {len(json.dumps(test_case['data']))} 字节")
        
        try:
            # 尝试验证请求
            request = TaskSubmissionRequest(**test_case['data'])
            print(f"✅ 验证通过")
            print(f"   result_data: {request.result_data}")
            print(f"   result_summary: {request.result_summary}")
        except ValidationError as e:
            print(f"❌ 验证失败:")
            for error in e.errors():
                print(f"   - {error['loc']}: {error['msg']} (type: {error['type']})")
        except Exception as e:
            print(f"❌ 意外错误: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(test_task_submission_validation())