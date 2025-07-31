#!/usr/bin/env python3
"""
强制重启服务脚本 - 确保修复代码生效
"""

import os
import sys
import subprocess
import time

def clear_python_cache():
    """清除Python缓存文件"""
    print("清除Python缓存文件...")
    
    # 删除.pyc文件
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pyc'):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"删除: {file_path}")
                except:
                    pass
    
    # 删除__pycache__目录
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            if dir_name == '__pycache__':
                dir_path = os.path.join(root, dir_name)
                try:
                    import shutil
                    shutil.rmtree(dir_path)
                    print(f"删除目录: {dir_path}")
                except:
                    pass

def verify_code_changes():
    """验证关键代码修复是否存在"""
    print("验证代码修复...")
    
    try:
        # 检查execution_service.py中的修复
        with open('workflow_framework/services/execution_service.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'node_instance_repo.db.fetch_all(query, workflow_instance_id)' in content:
            print("✓ execution_service.py 修复存在")
        else:
            print("✗ execution_service.py 修复缺失")
            return False
            
        # 检查execution.py中的修复
        with open('workflow_framework/api/execution.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'get_current_user_context' in content and 'CurrentUser' in content:
            print("✓ execution.py 修复存在")
        else:
            print("✗ execution.py 修复缺失")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ 验证代码失败: {e}")
        return False

def test_execution_engine():
    """测试执行引擎"""
    print("测试执行引擎...")
    
    test_script = '''
import asyncio
import uuid
from workflow_framework.models.instance import WorkflowExecuteRequest
from workflow_framework.services.execution_service import execution_engine

async def test():
    workflow_base_id = uuid.UUID("b4add00e-3593-42ef-8d26-6aeb3ce544e8")
    user_id = uuid.UUID("e92d6bc0-3187-430d-96e0-450b6267949a")
    
    request = WorkflowExecuteRequest(
        workflow_base_id=workflow_base_id,
        instance_name=f"重启测试_{uuid.uuid4().hex[:8]}",
        input_data={},
        context_data={}
    )
    
    try:
        await execution_engine.start_engine()
        result = await execution_engine.execute_workflow(request, user_id)
        print(f"SUCCESS: {result}")
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

success = asyncio.run(test())
exit(0 if success else 1)
'''
    
    try:
        result = subprocess.run([sys.executable, '-c', test_script], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✓ 执行引擎测试通过")
            return True
        else:
            print("✗ 执行引擎测试失败")
            print(f"错误输出: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ 执行引擎测试异常: {e}")
        return False

def main():
    print("=" * 60)
    print("强制重启服务 - 确保修复生效")
    print("=" * 60)
    
    # 1. 验证代码修复
    if not verify_code_changes():
        print("\n❌ 代码修复缺失，请先确保所有修复已应用")
        return
        
    print("\n✅ 代码修复验证通过")
    
    # 2. 清除缓存
    clear_python_cache()
    print("\n✅ Python缓存已清除")
    
    # 3. 测试执行引擎
    if test_execution_engine():
        print("\n✅ 执行引擎工作正常")
    else:
        print("\n❌ 执行引擎测试失败")
        return
    
    print("\n" + "=" * 60)
    print("✅ 所有检查通过！")
    print("\n现在请:")
    print("1. 在后端服务终端按 Ctrl+C 停止服务")
    print("2. 运行: python main.py")  
    print("3. 确认看到: INFO: Uvicorn running on http://127.0.0.1:8001")
    print("4. 前端执行工作流应该成功")
    print("=" * 60)

if __name__ == "__main__":
    main()