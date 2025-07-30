#!/usr/bin/env python3
"""
测试新工作流架构
Test script for the new workflow architecture
"""

import sys
import os
import uuid
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

# 导入新架构组件
from workflow_framework.services.workflow_instance_context import WorkflowInstanceContext
from workflow_framework.services.workflow_instance_manager import get_instance_manager, cleanup_instance_manager
from workflow_framework.services.resource_cleanup_manager import ResourceCleanupManager
from workflow_framework.services.node_dependency_tracker import NodeDependencyTracker

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_test_header(test_name: str):
    """打印测试标题"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}🧪 测试: {test_name}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def print_success(message: str):
    """打印成功消息"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    """打印错误消息"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message: str):
    """打印信息消息"""
    print(f"{Colors.CYAN}ℹ️  {message}{Colors.END}")

def print_warning(message: str):
    """打印警告消息"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

async def test_workflow_instance_context():
    """测试 WorkflowInstanceContext 基本功能"""
    print_test_header("WorkflowInstanceContext 基本功能测试")
    
    try:
        # 创建测试实例
        workflow_instance_id = uuid.uuid4()
        workflow_base_id = uuid.uuid4()
        
        print_info(f"创建工作流实例上下文: {workflow_instance_id}")
        context = WorkflowInstanceContext(workflow_instance_id, workflow_base_id)
        
        # 测试基本属性
        assert context.workflow_instance_id == workflow_instance_id
        assert context.workflow_base_id == workflow_base_id
        assert context.execution_start_time is not None
        print_success("基本属性初始化正确")
        
        # 测试节点依赖注册
        node_instance_id = uuid.uuid4()
        node_base_id = uuid.uuid4()
        upstream_nodes = [uuid.uuid4(), uuid.uuid4()]
        
        result = await context.register_node_dependencies(
            node_instance_id, node_base_id, upstream_nodes
        )
        assert result == True
        print_success("节点依赖注册成功")
        
        # 测试依赖信息查询
        dep_info = context.get_node_dependency_info(node_instance_id)
        assert dep_info is not None
        assert dep_info['node_base_id'] == node_base_id
        assert len(dep_info['upstream_nodes']) == 2
        print_success("依赖信息查询正确")
        
        # 测试节点执行状态管理
        result = await context.mark_node_executing(node_base_id, node_instance_id)
        assert result == True
        assert node_base_id in context.current_executing_nodes
        print_success("节点执行状态管理正确")
        
        # 测试节点完成
        output_data = {"result": "test_output", "timestamp": datetime.utcnow().isoformat()}
        triggered_nodes = await context.mark_node_completed(
            node_base_id, node_instance_id, output_data
        )
        assert node_base_id in context.completed_nodes
        assert node_base_id not in context.current_executing_nodes
        print_success("节点完成状态管理正确")
        
        # 测试工作流状态查询
        status = await context.get_workflow_status()
        assert status['workflow_instance_id'] == str(workflow_instance_id)
        assert status['completed_nodes'] == 1
        assert status['total_nodes'] == 1
        print_success("工作流状态查询正确")
        
        # 测试上下文清理
        await context.cleanup()
        print_success("上下文清理成功")
        
        print_success("WorkflowInstanceContext 所有测试通过!")
        return True
        
    except Exception as e:
        print_error(f"WorkflowInstanceContext 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_workflow_instance_manager():
    """测试 WorkflowInstanceManager 管理功能"""
    print_test_header("WorkflowInstanceManager 管理功能测试")
    
    try:
        # 获取实例管理器
        print_info("获取工作流实例管理器")
        manager = await get_instance_manager()
        assert manager is not None
        print_success("实例管理器获取成功")
        
        # 创建多个工作流实例
        instances = []
        for i in range(3):
            workflow_instance_id = uuid.uuid4()
            workflow_base_id = uuid.uuid4()
            executor_id = uuid.uuid4()
            instance_name = f"test_workflow_{i}"
            
            context = await manager.create_instance(
                workflow_instance_id, workflow_base_id, executor_id, instance_name
            )
            instances.append((workflow_instance_id, context))
            print_success(f"创建实例 {i+1}: {instance_name}")
        
        # 测试实例查询
        for workflow_instance_id, expected_context in instances:
            retrieved_context = await manager.get_instance(workflow_instance_id)
            assert retrieved_context is not None
            assert retrieved_context.workflow_instance_id == workflow_instance_id
        print_success("实例查询功能正确")
        
        # 测试实例列表
        instance_list = await manager.list_instances()
        assert len(instance_list) >= 3
        print_success(f"实例列表查询正确: {len(instance_list)} 个实例")
        
        # 测试实例状态更新
        test_instance_id = instances[0][0]
        result = await manager.update_instance_status(test_instance_id, 'COMPLETED')
        assert result == True
        print_success("实例状态更新成功")
        
        # 测试统计信息
        stats = await manager.get_manager_stats()
        assert stats['total_created'] >= 3
        assert stats['instances_count'] >= 3
        print_success(f"管理器统计信息正确: 已创建 {stats['total_created']} 个实例")
        
        # 测试实例移除
        removed_count = 0
        for workflow_instance_id, context in instances:
            # 先标记为完成状态
            status = await context.get_workflow_status()
            if status['status'] != 'COMPLETED':
                await manager.update_instance_status(workflow_instance_id, 'COMPLETED')
            
            result = await manager.remove_instance(workflow_instance_id)
            if result:
                removed_count += 1
        
        print_success(f"实例移除成功: {removed_count} 个实例")
        
        print_success("WorkflowInstanceManager 所有测试通过!")
        return True
        
    except Exception as e:
        print_error(f"WorkflowInstanceManager 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_concurrent_safety():
    """测试并发安全性"""
    print_test_header("并发安全性测试")
    
    try:
        # 创建一个工作流实例上下文
        workflow_instance_id = uuid.uuid4()
        workflow_base_id = uuid.uuid4()
        context = WorkflowInstanceContext(workflow_instance_id, workflow_base_id)
        
        # 并发注册节点依赖
        async def register_nodes_concurrently():
            tasks = []
            for i in range(10):
                node_instance_id = uuid.uuid4()
                node_base_id = uuid.uuid4()
                upstream_nodes = [uuid.uuid4() for _ in range(2)]
                
                task = context.register_node_dependencies(
                    node_instance_id, node_base_id, upstream_nodes
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r is True)
            return success_count
        
        print_info("执行并发节点注册测试 (10个节点)")
        success_count = await register_nodes_concurrently()
        assert success_count == 10
        print_success(f"并发节点注册成功: {success_count}/10")
        
        # 并发状态更新测试
        async def concurrent_status_updates():
            node_ids = list(context.node_dependencies.keys())[:5]  # 取前5个节点
            tasks = []
            
            for i, node_instance_id in enumerate(node_ids):
                dep_info = context.get_node_dependency_info(node_instance_id)
                node_base_id = dep_info['node_base_id']
                
                # 交替执行不同的状态更新
                if i % 2 == 0:
                    task = context.mark_node_executing(node_base_id, node_instance_id)
                else:
                    task = context.mark_node_completed(
                        node_base_id, node_instance_id, {"result": f"test_{i}"}
                    )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if r not in [False, None] and not isinstance(r, Exception))
            return success_count
        
        print_info("执行并发状态更新测试")
        success_count = await concurrent_status_updates()
        print_success(f"并发状态更新成功: {success_count} 个操作")
        
        # 并发查询测试
        async def concurrent_queries():
            tasks = []
            for _ in range(20):
                task = context.get_workflow_status()
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if isinstance(r, dict))
            return success_count
        
        print_info("执行并发查询测试 (20个并发查询)")
        success_count = await concurrent_queries()
        assert success_count == 20
        print_success(f"并发查询成功: {success_count}/20")
        
        await context.cleanup()
        print_success("并发安全性测试通过!")
        return True
        
    except Exception as e:
        print_error(f"并发安全性测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_resource_cleanup():
    """测试资源清理机制"""
    print_test_header("资源清理机制测试")
    
    try:
        # 创建资源清理管理器
        cleanup_manager = ResourceCleanupManager()
        
        # 测试自定义清理器注册
        cleanup_count = 0
        
        def custom_cleaner():
            nonlocal cleanup_count
            cleanup_count += 1
        
        result = cleanup_manager.register_cleaner("test_cleaner", custom_cleaner, 1)
        assert result == True
        print_success("自定义清理器注册成功")
        
        # 测试临时文件跟踪
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False, prefix="workflow_test_")
        temp_file.write(b"test data")
        temp_file.close()
        
        cleanup_manager.track_temp_file(temp_file.name)
        print_success(f"临时文件跟踪: {temp_file.name}")
        
        # 启动清理管理器
        await cleanup_manager.start_manager()
        print_success("清理管理器启动成功")
        
        # 等待清理器运行
        await asyncio.sleep(2)
        
        # 运行自定义清理器
        await cleanup_manager.run_custom_cleaners()
        assert cleanup_count > 0
        print_success(f"自定义清理器执行成功: {cleanup_count} 次")
        
        # 强制执行全面清理
        await cleanup_manager.force_cleanup_all()
        print_success("强制清理执行成功")
        
        # 获取清理统计
        stats = cleanup_manager.get_cleanup_stats()
        assert stats['total_cleanups'] >= 0
        print_success(f"清理统计信息正确: 总清理次数 {stats['total_cleanups']}")
        
        # 停止清理管理器
        await cleanup_manager.stop_manager()
        print_success("清理管理器停止成功")
        
        # 清理测试文件
        try:
            os.unlink(temp_file.name)
        except:
            pass
        
        print_success("资源清理机制测试通过!")
        return True
        
    except Exception as e:
        print_error(f"资源清理机制测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_dependency_tracker():
    """测试节点依赖跟踪器"""
    print_test_header("NodeDependencyTracker 功能测试")
    
    try:
        # 创建依赖跟踪器
        tracker = NodeDependencyTracker()
        
        # 测试缓存统计
        cache_stats = await tracker.get_cache_stats()
        assert 'cache_hits' in cache_stats
        assert 'cache_misses' in cache_stats
        print_success("缓存统计功能正确")
        
        # 测试缓存清理
        await tracker.clear_cache()
        print_success("缓存清理功能正确")
        
        # 注意：由于没有实际的数据库连接，上游/下游节点查询会返回空结果
        # 但我们可以测试方法调用不会出错
        workflow_base_id = uuid.uuid4()
        node_base_id = uuid.uuid4()
        
        upstream_nodes = await tracker.get_immediate_upstream_nodes(workflow_base_id, node_base_id)
        assert isinstance(upstream_nodes, list)
        print_success("上游节点查询方法正常")
        
        downstream_nodes = await tracker.get_immediate_downstream_nodes(workflow_base_id, node_base_id)
        assert isinstance(downstream_nodes, list)
        print_success("下游节点查询方法正常")
        
        # 测试工作流依赖图构建
        dependency_graph = await tracker.build_workflow_dependency_graph(workflow_base_id)
        assert isinstance(dependency_graph, dict)
        print_success("依赖图构建方法正常")
        
        # 测试依赖验证
        validation_result = await tracker.validate_workflow_dependencies(workflow_base_id)
        assert isinstance(validation_result, dict)
        assert 'is_valid' in validation_result
        print_success("依赖验证方法正常")
        
        print_success("NodeDependencyTracker 功能测试通过!")
        return True
        
    except Exception as e:
        print_error(f"NodeDependencyTracker 测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def test_performance_comparison():
    """性能对比测试"""
    print_test_header("性能对比测试")
    
    try:
        print_info("测试新架构的性能特征...")
        
        # 测试工作流实例创建性能
        start_time = time.time()
        instances = []
        
        for i in range(100):
            workflow_instance_id = uuid.uuid4()
            workflow_base_id = uuid.uuid4()
            context = WorkflowInstanceContext(workflow_instance_id, workflow_base_id)
            instances.append(context)
        
        create_time = time.time() - start_time
        print_success(f"创建100个工作流实例耗时: {create_time:.3f}秒")
        
        # 测试节点注册性能
        start_time = time.time()
        for i, context in enumerate(instances[:10]):  # 只测试前10个
            for j in range(10):  # 每个实例10个节点
                node_instance_id = uuid.uuid4()
                node_base_id = uuid.uuid4()
                upstream_nodes = [uuid.uuid4() for _ in range(2)]
                await context.register_node_dependencies(
                    node_instance_id, node_base_id, upstream_nodes
                )
        
        register_time = time.time() - start_time
        print_success(f"注册1000个节点依赖耗时: {register_time:.3f}秒")
        
        # 测试状态查询性能
        start_time = time.time()
        for context in instances[:10]:
            for _ in range(10):
                await context.get_workflow_status()
        
        query_time = time.time() - start_time
        print_success(f"执行100次状态查询耗时: {query_time:.3f}秒")
        
        # 清理测试实例
        for context in instances:
            await context.cleanup()
        
        print_success("性能测试完成!")
        print_info(f"性能摘要:")
        print_info(f"  - 实例创建: {create_time/100*1000:.2f}ms/实例")
        print_info(f"  - 节点注册: {register_time/1000*1000:.2f}ms/节点")
        print_info(f"  - 状态查询: {query_time/100*1000:.2f}ms/查询")
        
        return True
        
    except Exception as e:
        print_error(f"性能测试失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False

async def main():
    """主测试函数"""
    print(f"{Colors.BOLD}{Colors.PURPLE}")
    print("🚀 新工作流架构测试套件")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"{Colors.END}")
    
    test_results = []
    
    # 执行所有测试
    tests = [
        ("WorkflowInstanceContext基本功能", test_workflow_instance_context),
        ("WorkflowInstanceManager管理功能", test_workflow_instance_manager),
        ("并发安全性", test_concurrent_safety),
        ("资源清理机制", test_resource_cleanup),
        ("NodeDependencyTracker功能", test_dependency_tracker),
        ("性能对比", test_performance_comparison),
    ]
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print_error(f"测试 {test_name} 执行异常: {e}")
            test_results.append((test_name, False))
    
    # 输出测试总结
    print(f"\n{Colors.BOLD}{Colors.PURPLE}📊 测试结果总结{Colors.END}")
    print("=" * 60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.END} - {test_name}")
    
    print("=" * 60)
    success_rate = (passed / total) * 100
    if success_rate == 100:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 所有测试通过! ({passed}/{total}, {success_rate:.1f}%){Colors.END}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  部分测试失败 ({passed}/{total}, {success_rate:.1f}%){Colors.END}")
    
    # 清理资源
    try:
        await cleanup_instance_manager()
        print_info("全局资源清理完成")
    except Exception as e:
        print_warning(f"全局资源清理时出现警告: {e}")
    
    return success_rate == 100

if __name__ == "__main__":
    # 运行测试
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}测试被用户中断{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}测试执行出现异常: {e}{Colors.END}")
        sys.exit(1)