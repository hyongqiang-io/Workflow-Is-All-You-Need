#!/usr/bin/env python3
"""
检查服务器路由和修复状态
"""

import asyncio
import requests
from workflow_framework.api.execution import router

def check_routes():
    """检查API路由"""
    print("=== 检查API路由 ===")
    
    routes = []
    for route in router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append(f"{list(route.methods)[0]} {route.path}")
    
    print("execution.py 中定义的路由:")
    for route in routes:
        print(f"  {route}")
    
    # 检查关键路由
    execute_route = any('/workflows/execute' in route for route in routes)
    instances_route = any('/workflows/{workflow_base_id}/instances' in route for route in routes)
    
    print(f"\n关键路由检查:")
    print(f"  执行路由: {'✓ 存在' if execute_route else '✗ 缺失'}")
    print(f"  实例路由: {'✓ 存在' if instances_route else '✗ 缺失'}")
    
    return execute_route and instances_route

def test_server_connection():
    """测试服务器连接"""
    print("\n=== 测试服务器连接 ===")
    
    try:
        # 测试健康检查
        response = requests.get("http://localhost:8001/health", timeout=5)
        print(f"健康检查: HTTP {response.status_code}")
        if response.status_code == 200:
            print("✓ 服务器运行正常")
            return True
        else:
            print("✗ 服务器响应异常")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务器 - 服务可能没有在8001端口运行")
        return False
    except Exception as e:
        print(f"✗ 连接测试失败: {e}")
        return False

def check_main_app():
    """检查main.py应用配置"""
    print("\n=== 检查main.py配置 ===")
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查端口配置
        if 'port=8001' in content:
            print("✓ 端口配置正确 (8001)")
        else:
            print("✗ 端口配置错误")
            
        # 检查execution router导入
        if 'from workflow_framework.api.execution import router as execution_router' in content:
            print("✓ execution router 已导入")
        else:
            print("✗ execution router 未导入")
            
        # 检查router注册
        if 'app.include_router(execution_router)' in content:
            print("✓ execution router 已注册")
            return True
        else:
            print("✗ execution router 未注册")
            return False
            
    except Exception as e:
        print(f"✗ 检查main.py失败: {e}")
        return False

if __name__ == "__main__":
    print("检查服务器状态和配置...\n")
    
    routes_ok = check_routes()
    server_ok = test_server_connection()  
    main_ok = check_main_app()
    
    print("\n" + "="*50)
    print("检查结果:")
    print(f"  API路由: {'✓ 正常' if routes_ok else '✗ 异常'}")
    print(f"  服务连接: {'✓ 正常' if server_ok else '✗ 异常'}")
    print(f"  main.py配置: {'✓ 正常' if main_ok else '✗ 异常'}")
    
    if not server_ok:
        print("\n[ERROR] 服务器无法访问!")
        print("请确保:")
        print("1. 运行了 python main.py")
        print("2. 服务启动在8001端口")
        print("3. 没有防火墙阻挡")
        
    elif not (routes_ok and main_ok):
        print("\n[ERROR] 配置有问题!")
        print("请检查main.py是否正确导入和注册了execution_router")
        
    else:
        print("\n[SUCCESS] 配置正常!")
        print("如果前端仍然失败，可能是缓存问题。")
        print("尝试完全重启服务器进程。")