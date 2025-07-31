#!/usr/bin/env python3
"""
实时诊断脚本 - 监控API调用
"""

import asyncio
import uuid
from workflow_framework.models.instance import WorkflowExecuteRequest
from workflow_framework.services.execution_service import execution_engine
from workflow_framework.repositories.node.node_repository import NodeRepository

async def detailed_diagnosis():
    """详细诊断当前状态"""
    
    workflow_base_id = uuid.UUID('b4add00e-3593-42ef-8d26-6aeb3ce544e8')
    user_id = uuid.UUID('e92d6bc0-3187-430d-96e0-450b6267949a')
    
    print("=== 详细诊断 ===")
    print(f"工作流ID: {workflow_base_id}")
    print(f"用户ID: {user_id}")
    
    # 1. 检查节点数据
    print("\n1. 检查工作流节点:")
    try:
        node_repo = NodeRepository()
        nodes = await node_repo.get_workflow_nodes(workflow_base_id)
        print(f"   找到 {len(nodes)} 个节点:")
        
        start_nodes = []
        for node in nodes:
            node_type = node.get('type', 'unknown')
            print(f"   - {node.get('name', 'N/A')} (类型: {node_type}) ID: {node.get('node_base_id', 'N/A')}")
            if node_type == 'start':
                start_nodes.append(node)
        
        print(f"   START节点数量: {len(start_nodes)}")
        
        if not start_nodes:
            print("   [ERROR] 没有START节点!")
            return False
            
    except Exception as e:
        print(f"   [ERROR] 获取节点失败: {e}")
        return False
    
    # 2. 测试执行引擎
    print("\n2. 测试执行引擎:")
    try:
        await execution_engine.start_engine()
        print("   引擎启动成功")
        
        request = WorkflowExecuteRequest(
            workflow_base_id=workflow_base_id,
            instance_name=f"诊断测试_{uuid.uuid4().hex[:8]}",
            input_data={},
            context_data={}
        )
        
        result = await execution_engine.execute_workflow(request, user_id)
        print(f"   执行成功: {result}")
        
        return True
        
    except Exception as e:
        print(f"   [ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_api_path():
    """测试API路径"""
    print("\n3. 测试API组件:")
    
    try:
        # 测试认证
        from workflow_framework.utils.middleware import get_current_user_context
        print("   get_current_user_context 导入成功")
        
        # 测试执行API
        from workflow_framework.api.execution import router
        print("   execution router 导入成功")
        
        # 检查路由
        routes = [route.path for route in router.routes if hasattr(route, 'path')]
        if '/workflows/execute' in str(routes):
            print("   执行路由存在")
        else:
            print("   [ERROR] 执行路由缺失")
            
        return True
        
    except Exception as e:
        print(f"   [ERROR] API组件问题: {e}")
        return False

async def main():
    print("开始实时诊断...")
    
    # 运行诊断
    diagnosis_ok = await detailed_diagnosis()
    api_ok = await test_api_path()
    
    print(f"\n=== 诊断结果 ===")
    print(f"执行引擎: {'正常' if diagnosis_ok else '异常'}")
    print(f"API组件: {'正常' if api_ok else '异常'}")
    
    if diagnosis_ok and api_ok:
        print("\n[SUCCESS] 后端完全正常!")
        print("\n问题可能在于:")
        print("1. 前端缓存 - 请硬刷新页面 (Ctrl+Shift+R)")
        print("2. 网络问题 - 检查浏览器Network标签")
        print("3. Token过期 - 重新设置token")
        
        print(f"\n请在浏览器Console中重新执行:")
        print(f"localStorage.setItem('token', '[您的token]')")
        print(f"然后硬刷新页面")
        
    else:
        print("\n[ERROR] 后端有问题，需要进一步调试")
    
    print(f"\n=== 下一步调试 ===")
    print("请在前端点击执行工作流时，观察后端终端输出。")
    print("如果没有看到相关日志，说明请求没有到达后端。")

if __name__ == "__main__":
    asyncio.run(main())