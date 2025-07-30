"""
新工作流上下文管理架构使用示例
展示如何使用新架构的各个组件
"""

import uuid
import asyncio
from typing import Dict, Any, List
import logging

# 导入新架构组件
from .workflow_context_manager_v2 import (
    WorkflowContextManagerV2, 
    ManagerMode,
    get_context_manager_v2
)
from .workflow_instance_context import WorkflowExecutionStatus
from .node_dependency_tracker import DependencyType

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowExample:
    """工作流使用示例"""
    
    def __init__(self):
        # 获取上下文管理器实例（增强模式）
        self.context_manager = get_context_manager_v2(ManagerMode.ENHANCED)
        
        # 注册回调函数
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """设置回调函数"""
        self.context_manager.register_workflow_created_callback(self._on_workflow_created)
        self.context_manager.register_workflow_completed_callback(self._on_workflow_completed)
        self.context_manager.register_workflow_failed_callback(self._on_workflow_failed)
        self.context_manager.register_node_completed_callback(self._on_node_completed)
    
    async def run_simple_workflow_example(self):
        """运行简单工作流示例"""
        logger.info("=== 开始简单工作流示例 ===")
        
        # 创建工作流实例
        workflow_instance_id = uuid.uuid4()
        workflow_base_id = uuid.uuid4()
        
        context = await self.context_manager.create_workflow_instance(
            workflow_instance_id=workflow_instance_id,
            workflow_base_id=workflow_base_id,
            config={
                'workflow_name': 'Simple Example Workflow',
                'timeout_seconds': 300,
                'retry_enabled': True
            }
        )
        
        # 定义节点
        start_node_id = uuid.uuid4()
        process_node_id = uuid.uuid4()
        end_node_id = uuid.uuid4()
        
        # 注册开始节点（无依赖）
        await self.context_manager.register_node_with_dependencies(
            workflow_instance_id=workflow_instance_id,
            node_instance_id=start_node_id,
            node_base_id=start_node_id,
            dependencies=[]  # 无依赖
        )
        
        # 注册处理节点（依赖开始节点）
        await self.context_manager.register_node_with_dependencies(
            workflow_instance_id=workflow_instance_id,
            node_instance_id=process_node_id,
            node_base_id=process_node_id,
            dependencies=[{
                'upstream_node_id': start_node_id,
                'type': 'SEQUENCE'
            }]
        )
        
        # 注册结束节点（依赖处理节点）
        await self.context_manager.register_node_with_dependencies(
            workflow_instance_id=workflow_instance_id,
            node_instance_id=end_node_id,
            node_base_id=end_node_id,
            dependencies=[{
                'upstream_node_id': process_node_id,
                'type': 'SEQUENCE'
            }]
        )
        
        # 执行工作流
        await self._execute_workflow_nodes(workflow_instance_id)
        
        # 获取最终状态
        final_status = await self.context_manager.get_workflow_status(workflow_instance_id)
        logger.info(f"工作流最终状态: {final_status['status']}")
        
        # 清理资源
        await self.context_manager.cleanup_workflow(workflow_instance_id)
        
        logger.info("=== 简单工作流示例完成 ===")
    
    async def run_complex_workflow_example(self):
        """运行复杂工作流示例"""
        logger.info("=== 开始复杂工作流示例 ===")
        
        # 创建工作流实例
        workflow_instance_id = uuid.uuid4()
        workflow_base_id = uuid.uuid4()
        
        context = await self.context_manager.create_workflow_instance(
            workflow_instance_id=workflow_instance_id,
            workflow_base_id=workflow_base_id,
            config={
                'workflow_name': 'Complex Example Workflow',
                'max_parallel_nodes': 3,
                'enable_monitoring': True
            }
        )
        
        # 创建复杂的依赖图结构
        #     A (start)
        #    / \\
        #   B   C (parallel)
        #   |   |
        #   D   E
        #    \\ /
        #     F (end)
        
        nodes = {
            'A': uuid.uuid4(),  # 开始节点
            'B': uuid.uuid4(),  # 左分支
            'C': uuid.uuid4(),  # 右分支  
            'D': uuid.uuid4(),  # 左处理
            'E': uuid.uuid4(),  # 右处理
            'F': uuid.uuid4()   # 汇聚节点
        }
        
        # 注册所有节点及其依赖关系
        node_dependencies = {
            'A': [],
            'B': [{'upstream_node_id': nodes['A'], 'type': 'SEQUENCE'}],
            'C': [{'upstream_node_id': nodes['A'], 'type': 'SEQUENCE'}],
            'D': [{'upstream_node_id': nodes['B'], 'type': 'SEQUENCE'}],
            'E': [{'upstream_node_id': nodes['C'], 'type': 'SEQUENCE'}],
            'F': [
                {'upstream_node_id': nodes['D'], 'type': 'PARALLEL'},
                {'upstream_node_id': nodes['E'], 'type': 'PARALLEL'}
            ]
        }
        
        for node_name, node_id in nodes.items():
            dependencies = node_dependencies[node_name]
            await self.context_manager.register_node_with_dependencies(
                workflow_instance_id=workflow_instance_id,
                node_instance_id=node_id,
                node_base_id=node_id,
                dependencies=dependencies,
                node_config={'node_name': node_name}
            )
        
        # 执行复杂工作流
        await self._execute_complex_workflow(workflow_instance_id, nodes)
        
        # 获取详细状态和统计信息
        final_status = await self.context_manager.get_workflow_status(workflow_instance_id)
        global_stats = self.context_manager.get_global_statistics()
        
        logger.info(f"复杂工作流状态: {final_status['status']}")
        logger.info(f"全局统计信息: {global_stats['global_stats']}")
        
        # 清理资源
        await self.context_manager.cleanup_workflow(workflow_instance_id)
        
        logger.info("=== 复杂工作流示例完成 ===")
    
    async def run_compatibility_example(self):
        """运行兼容性接口示例"""
        logger.info("=== 开始兼容性接口示例 ===")
        
        # 使用兼容模式创建管理器
        from .workflow_context_manager_v2 import WorkflowContextManagerV2
        compat_manager = WorkflowContextManagerV2(mode=ManagerMode.COMPATIBLE)
        
        # 获取兼容性接口
        compat_interface = compat_manager.get_compatibility_interface()
        if not compat_interface:
            logger.error("兼容性接口未启用")
            return
        
        # 使用旧的接口风格
        workflow_instance_id = uuid.uuid4()
        
        # 初始化工作流上下文（旧接口）
        await compat_interface.initialize_workflow_context(workflow_instance_id)
        
        # 注册节点依赖（旧接口）
        node_instance_id = uuid.uuid4()
        node_base_id = uuid.uuid4()
        await compat_interface.register_node_dependencies(
            node_instance_id=node_instance_id,
            node_base_id=node_base_id,
            workflow_instance_id=workflow_instance_id,
            upstream_nodes=[]  # 开始节点
        )
        
        # 标记节点完成（旧接口）
        await compat_interface.mark_node_completed(
            workflow_instance_id=workflow_instance_id,
            node_base_id=node_base_id,
            node_instance_id=node_instance_id,
            output_data={'result': 'success', 'data': 'test_output'}
        )
        
        # 获取状态（旧接口）
        status = await compat_interface.get_workflow_status(workflow_instance_id)
        logger.info(f"兼容接口工作流状态: {status}")
        
        # 清理（旧接口）
        await compat_interface.cleanup_workflow_context(workflow_instance_id)
        
        logger.info("=== 兼容性接口示例完成 ===")
    
    async def _execute_workflow_nodes(self, workflow_instance_id: uuid.UUID):
        """执行简单工作流的节点"""
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            # 获取就绪节点
            ready_nodes = self.context_manager.get_ready_nodes(workflow_instance_id)
            
            if not ready_nodes:
                # 检查工作流是否完成
                status = await self.context_manager.get_workflow_status(workflow_instance_id)
                if status['status'] in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    break
                
                # 等待一下再检查
                await asyncio.sleep(0.1)
                iteration += 1
                continue
            
            # 并行执行所有就绪节点
            tasks = []
            for node_id in ready_nodes:
                task = self.context_manager.execute_node(
                    workflow_instance_id=workflow_instance_id,
                    node_instance_id=node_id,
                    execution_func=self._simple_node_execution,
                    input_data={'iteration': iteration}
                )
                tasks.append(task)
            
            # 等待所有节点完成
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            iteration += 1
    
    async def _execute_complex_workflow(self, workflow_instance_id: uuid.UUID, nodes: Dict[str, uuid.UUID]):
        """执行复杂工作流"""
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            ready_nodes = self.context_manager.get_ready_nodes(workflow_instance_id)
            
            if not ready_nodes:
                status = await self.context_manager.get_workflow_status(workflow_instance_id)
                if status['status'] in ['COMPLETED', 'FAILED', 'CANCELLED']:
                    break
                await asyncio.sleep(0.1)
                iteration += 1
                continue
            
            # 为每种类型的节点定义不同的执行函数
            tasks = []
            for node_id in ready_nodes:
                # 根据节点类型选择执行函数
                node_name = self._get_node_name_by_id(nodes, node_id)
                execution_func = self._get_execution_func_for_node(node_name)
                
                task = self.context_manager.execute_node(
                    workflow_instance_id=workflow_instance_id,
                    node_instance_id=node_id,
                    execution_func=execution_func,
                    input_data={'node_name': node_name, 'iteration': iteration}
                )
                tasks.append(task)
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                # 检查是否有异常
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"节点执行异常: {result}")
            
            iteration += 1
    
    def _get_node_name_by_id(self, nodes: Dict[str, uuid.UUID], node_id: uuid.UUID) -> str:
        """根据节点ID获取节点名称"""
        for name, nid in nodes.items():
            if nid == node_id:
                return name
        return "Unknown"
    
    def _get_execution_func_for_node(self, node_name: str):
        """根据节点名称获取执行函数"""
        execution_funcs = {
            'A': self._start_node_execution,
            'B': self._branch_node_execution,
            'C': self._branch_node_execution,
            'D': self._process_node_execution,
            'E': self._process_node_execution,
            'F': self._merge_node_execution
        }
        return execution_funcs.get(node_name, self._simple_node_execution)
    
    async def _simple_node_execution(self, **kwargs) -> Dict[str, Any]:
        """简单节点执行函数"""
        node_instance_id = kwargs.get('node_instance_id')
        input_data = kwargs.get('input_data', {})
        upstream_context = kwargs.get('upstream_context', {})
        
        logger.info(f"执行简单节点: {node_instance_id}")
        
        # 模拟一些处理时间
        await asyncio.sleep(0.1)
        
        return {
            'status': 'success',
            'processed_data': f"processed_{input_data.get('iteration', 0)}",
            'timestamp': str(uuid.uuid4())
        }
    
    async def _start_node_execution(self, **kwargs) -> Dict[str, Any]:
        """开始节点执行函数"""
        logger.info("执行开始节点")
        await asyncio.sleep(0.05)
        return {
            'status': 'started',
            'start_time': str(uuid.uuid4()),
            'initial_data': 'workflow_started'
        }
    
    async def _branch_node_execution(self, **kwargs) -> Dict[str, Any]:
        """分支节点执行函数"""
        node_name = kwargs.get('input_data', {}).get('node_name', 'Unknown')
        logger.info(f"执行分支节点: {node_name}")
        await asyncio.sleep(0.1)
        return {
            'status': 'branch_processed',
            'branch_name': node_name,
            'branch_data': f"data_from_{node_name}"
        }
    
    async def _process_node_execution(self, **kwargs) -> Dict[str, Any]:
        """处理节点执行函数"""
        node_name = kwargs.get('input_data', {}).get('node_name', 'Unknown')
        upstream_context = kwargs.get('upstream_context', {})
        
        logger.info(f"执行处理节点: {node_name}")
        
        # 处理上游数据
        upstream_results = upstream_context.get('immediate_upstream_results', {})
        processed_count = len(upstream_results)
        
        await asyncio.sleep(0.15)  # 模拟较长处理时间
        
        return {
            'status': 'processed',
            'node_name': node_name,
            'upstream_count': processed_count,
            'processed_result': f"result_from_{node_name}"
        }
    
    async def _merge_node_execution(self, **kwargs) -> Dict[str, Any]:
        """汇聚节点执行函数"""
        upstream_context = kwargs.get('upstream_context', {})
        upstream_results = upstream_context.get('immediate_upstream_results', {})
        
        logger.info(f"执行汇聚节点，合并 {len(upstream_results)} 个上游结果")
        
        # 合并所有上游结果
        merged_data = {}
        for upstream_id, result in upstream_results.items():
            if isinstance(result, dict):
                merged_data.update(result)
        
        await asyncio.sleep(0.1)
        
        return {
            'status': 'merged',
            'merged_count': len(upstream_results),
            'final_result': merged_data,
            'workflow_completed': True
        }
    
    # 回调函数
    async def _on_workflow_created(self, context):
        """工作流创建回调"""
        logger.info(f"✅ 工作流已创建: {context.workflow_instance_id}")
    
    async def _on_workflow_completed(self, workflow_instance_id):
        """工作流完成回调"""
        logger.info(f"🎉 工作流已完成: {workflow_instance_id}")
    
    async def _on_workflow_failed(self, workflow_instance_id):
        """工作流失败回调"""
        logger.error(f"❌ 工作流失败: {workflow_instance_id}")
    
    async def _on_node_completed(self, node_instance_id):
        """节点完成回调"""
        logger.info(f"✓ 节点已完成: {node_instance_id}")


async def main():
    """主函数，运行所有示例"""
    example = WorkflowExample()
    
    try:
        # 运行简单工作流示例
        await example.run_simple_workflow_example()
        
        # 等待一下
        await asyncio.sleep(1)
        
        # 运行复杂工作流示例
        await example.run_complex_workflow_example()
        
        # 等待一下
        await asyncio.sleep(1)
        
        # 运行兼容性示例
        await example.run_compatibility_example()
        
        # 显示全局统计
        stats = example.context_manager.get_global_statistics()
        logger.info("=== 最终统计信息 ===")
        logger.info(f"总共创建工作流: {stats['global_stats']['total_workflows_created']}")
        logger.info(f"总共完成工作流: {stats['global_stats']['total_workflows_completed']}")
        logger.info(f"总共执行节点: {stats['global_stats']['total_nodes_executed']}")
        
        # 执行性能优化
        await example.context_manager.optimize_performance()
        
    except Exception as e:
        logger.error(f"示例执行失败: {e}")
        raise
    
    finally:
        # 关闭管理器
        await example.context_manager.shutdown()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())