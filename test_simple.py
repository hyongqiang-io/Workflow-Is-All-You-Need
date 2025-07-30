#!/usr/bin/env python3
"""
简化版新架构测试
Simple test for new architecture
"""

import sys
import os
import uuid
import asyncio
import time
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

async def test_workflow_instance_context():
    """测试 WorkflowInstanceContext 基本功能"""
    print("\n=== Testing WorkflowInstanceContext ===")
    
    try:
        from workflow_framework.services.workflow_instance_context import WorkflowInstanceContext
        
        # 创建测试实例
        workflow_instance_id = uuid.uuid4()
        workflow_base_id = uuid.uuid4()
        
        print(f"Creating context: {workflow_instance_id}")
        context = WorkflowInstanceContext(workflow_instance_id, workflow_base_id)
        
        # 测试基本属性
        assert context.workflow_instance_id == workflow_instance_id
        assert context.workflow_base_id == workflow_base_id
        print("OK Basic attributes OK")
        
        # 测试节点依赖注册
        node_instance_id = uuid.uuid4()
        node_base_id = uuid.uuid4()
        upstream_nodes = [uuid.uuid4(), uuid.uuid4()]
        
        result = await context.register_node_dependencies(
            node_instance_id, node_base_id, upstream_nodes
        )
        assert result == True
        print("OK Node dependency registration OK")
        
        # 测试依赖信息查询
        dep_info = context.get_node_dependency_info(node_instance_id)
        assert dep_info is not None
        assert dep_info['node_base_id'] == node_base_id
        print("OK Dependency info query OK")
        
        # 测试节点执行状态
        result = await context.mark_node_executing(node_base_id, node_instance_id)
        assert result == True
        print("OK Node execution status OK")
        
        # 测试节点完成
        output_data = {"result": "test_output"}
        triggered_nodes = await context.mark_node_completed(
            node_base_id, node_instance_id, output_data
        )
        assert node_base_id in context.completed_nodes
        print("OK Node completion OK")
        
        # 测试工作流状态
        status = await context.get_workflow_status()
        assert status['workflow_instance_id'] == str(workflow_instance_id)
        print("OK Workflow status query OK")
        
        # 清理
        await context.cleanup()
        print("OK Context cleanup OK")
        
        print("PASS WorkflowInstanceContext tests PASSED")
        return True
        
    except Exception as e:
        print(f"FAIL WorkflowInstanceContext test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_workflow_instance_manager():
    """测试 WorkflowInstanceManager"""
    print("\n=== Testing WorkflowInstanceManager ===")
    
    try:
        from workflow_framework.services.workflow_instance_manager import get_instance_manager
        
        # 获取管理器
        manager = await get_instance_manager()
        print("OK Instance manager obtained")
        
        # 创建实例
        workflow_instance_id = uuid.uuid4()
        workflow_base_id = uuid.uuid4()
        executor_id = uuid.uuid4()
        
        context = await manager.create_instance(
            workflow_instance_id, workflow_base_id, executor_id, "test_instance"
        )
        print("OK Instance created")
        
        # 查询实例
        retrieved = await manager.get_instance(workflow_instance_id)
        assert retrieved is not None
        print("OK Instance retrieval OK")
        
        # 获取统计
        stats = await manager.get_manager_stats()
        assert stats['total_created'] >= 1
        print(f"OK Manager stats OK: {stats['total_created']} instances created")
        
        # 清理
        await manager.update_instance_status(workflow_instance_id, 'COMPLETED')
        result = await manager.remove_instance(workflow_instance_id)
        print(f"OK Instance cleanup: {result}")
        
        print("PASS WorkflowInstanceManager tests PASSED")
        return True
        
    except Exception as e:
        print(f"FAIL WorkflowInstanceManager test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_concurrent_safety():
    """测试并发安全性"""
    print("\n=== Testing Concurrent Safety ===")
    
    try:
        from workflow_framework.services.workflow_instance_context import WorkflowInstanceContext
        
        # 创建上下文
        context = WorkflowInstanceContext(uuid.uuid4(), uuid.uuid4())
        
        # 并发注册节点
        async def register_node():
            node_instance_id = uuid.uuid4()
            node_base_id = uuid.uuid4()
            return await context.register_node_dependencies(
                node_instance_id, node_base_id, []
            )
        
        tasks = [register_node() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        
        print(f"OK Concurrent registration: {success_count}/10 successful")
        
        # 并发状态查询
        tasks = [context.get_workflow_status() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if isinstance(r, dict))
        
        print(f"OK Concurrent queries: {success_count}/20 successful")
        
        await context.cleanup()
        print("PASS Concurrent safety tests PASSED")
        return True
        
    except Exception as e:
        print(f"FAIL Concurrent safety test FAILED: {e}")
        return False

async def test_resource_cleanup():
    """测试资源清理"""
    print("\n=== Testing Resource Cleanup ===")
    
    try:
        from workflow_framework.services.resource_cleanup_manager import ResourceCleanupManager
        
        cleanup_manager = ResourceCleanupManager()
        
        # 测试自定义清理器
        cleanup_count = 0
        def custom_cleaner():
            nonlocal cleanup_count
            cleanup_count += 1
        
        result = cleanup_manager.register_cleaner("test", custom_cleaner, 1)
        assert result == True
        print("OK Custom cleaner registered")
        
        # 启动管理器
        await cleanup_manager.start_manager()
        print("OK Cleanup manager started")
        
        # 运行清理器
        await cleanup_manager.run_custom_cleaners()
        print(f"OK Custom cleaner executed: {cleanup_count} times")
        
        # 获取统计
        stats = cleanup_manager.get_cleanup_stats()
        print(f"OK Cleanup stats: {stats['total_cleanups']} total cleanups")
        
        # 停止管理器
        await cleanup_manager.stop_manager()
        print("OK Cleanup manager stopped")
        
        print("PASS Resource cleanup tests PASSED")
        return True
        
    except Exception as e:
        print(f"FAIL Resource cleanup test FAILED: {e}")
        return False

async def test_performance():
    """性能测试"""
    print("\n=== Testing Performance ===")
    
    try:
        from workflow_framework.services.workflow_instance_context import WorkflowInstanceContext
        
        # 创建多个实例
        start_time = time.time()
        instances = []
        for i in range(50):
            context = WorkflowInstanceContext(uuid.uuid4(), uuid.uuid4())
            instances.append(context)
        create_time = time.time() - start_time
        
        print(f"OK Created 50 instances in {create_time:.3f}s ({create_time/50*1000:.2f}ms each)")
        
        # 节点注册性能
        start_time = time.time()
        for context in instances[:5]:
            for j in range(10):
                await context.register_node_dependencies(
                    uuid.uuid4(), uuid.uuid4(), []
                )
        register_time = time.time() - start_time
        
        print(f"OK Registered 50 nodes in {register_time:.3f}s ({register_time/50*1000:.2f}ms each)")
        
        # 清理
        for context in instances:
            await context.cleanup()
        
        print("PASS Performance tests PASSED")
        return True
        
    except Exception as e:
        print(f"FAIL Performance test FAILED: {e}")
        return False

async def main():
    """主测试函数"""
    print("New Workflow Architecture Test Suite")
    print("=" * 50)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    tests = [
        ("WorkflowInstanceContext", test_workflow_instance_context),
        ("WorkflowInstanceManager", test_workflow_instance_manager),
        ("Concurrent Safety", test_concurrent_safety),
        ("Resource Cleanup", test_resource_cleanup),
        ("Performance", test_performance),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"FAIL Test {test_name} threw exception: {e}")
            results.append((test_name, False))
    
    # 输出结果
    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"[{status}] {test_name}")
    
    print("=" * 50)
    success_rate = (passed / total) * 100
    print(f"Summary: {passed}/{total} tests passed ({success_rate:.1f}%)")
    
    if success_rate == 100:
        print("All tests passed!")
    else:
        print("Some tests failed")
    
    # 清理
    try:
        from workflow_framework.services.workflow_instance_manager import cleanup_instance_manager
        await cleanup_instance_manager()
        print("Global cleanup completed")
    except Exception as e:
        print(f"Warning during cleanup: {e}")
    
    return success_rate == 100

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Test execution error: {e}")
        sys.exit(1)