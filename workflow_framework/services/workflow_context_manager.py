"""
工作流上下文管理器
统一管理整个工作流的执行上下文和数据流
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Set, Optional
import asyncio
import logging
from loguru import logger

# 延迟导入避免循环依赖
from ..models.instance import WorkflowInstanceStatus, WorkflowInstanceUpdate


class WorkflowContextManager:
    """宏观工作流上下文管理器"""
    
    def __init__(self):
        # 工作流级别的全局上下文
        self.workflow_contexts: Dict[uuid.UUID, Dict[str, Any]] = {}
        
        # 节点依赖关系管理
        self.node_dependencies: Dict[uuid.UUID, Dict[str, Any]] = {}
        
        # 节点完成状态追踪
        self.node_completion_status: Dict[uuid.UUID, str] = {}
        
        # 待触发的节点队列
        self.pending_triggers: Dict[uuid.UUID, Set[uuid.UUID]] = {}
        
        # 回调函数注册
        self.completion_callbacks: List[callable] = []
    
    async def initialize_workflow_context(self, workflow_instance_id: uuid.UUID):
        """初始化工作流上下文"""
        self.workflow_contexts[workflow_instance_id] = {
            'global_data': {},
            'node_outputs': {},  # node_base_id -> output_data
            'execution_path': [],  # 已执行的节点路径
            'execution_start_time': datetime.utcnow(),
            'current_executing_nodes': set(),
            'completed_nodes': set(),
            'failed_nodes': set()
        }
        
        # 初始化工作流的待触发队列
        self.pending_triggers[workflow_instance_id] = set()
        
        logger.info(f"Initialized workflow context for {workflow_instance_id}")
    
    async def register_node_dependencies(self, 
                                       node_instance_id: uuid.UUID,
                                       node_base_id: uuid.UUID,
                                       workflow_instance_id: uuid.UUID, 
                                       upstream_nodes: List[uuid.UUID]):
        """注册节点的一阶依赖关系"""
        self.node_dependencies[node_instance_id] = {
            'node_base_id': node_base_id,
            'workflow_instance_id': workflow_instance_id,
            'upstream_nodes': upstream_nodes,
            'completed_upstream': set(),
            'ready_to_execute': len(upstream_nodes) == 0,  # START节点无依赖
            'dependency_count': len(upstream_nodes)
        }
        
        # 初始化节点状态
        self.node_completion_status[node_instance_id] = 'PENDING'
        
        logger.debug(f"Registered dependencies for node {node_instance_id}: {len(upstream_nodes)} upstream nodes")
    
    async def mark_node_completed(self, 
                                workflow_instance_id: uuid.UUID,
                                node_base_id: uuid.UUID, 
                                node_instance_id: uuid.UUID,
                                output_data: Dict[str, Any]):
        """标记节点完成并更新上下文"""
        if workflow_instance_id not in self.workflow_contexts:
            logger.error(f"Workflow context not found for {workflow_instance_id}")
            return
        
        # 更新工作流上下文
        context = self.workflow_contexts[workflow_instance_id]
        context['node_outputs'][node_base_id] = output_data
        context['execution_path'].append(node_base_id)
        context['completed_nodes'].add(node_base_id)
        
        # 从正在执行的节点中移除
        if node_base_id in context['current_executing_nodes']:
            context['current_executing_nodes'].remove(node_base_id)
        
        # 更新完成状态
        self.node_completion_status[node_instance_id] = 'COMPLETED'
        
        logger.info(f"Node {node_base_id} completed in workflow {workflow_instance_id}")
        
        # 检查并触发下游节点
        await self._check_and_trigger_downstream_nodes(
            workflow_instance_id, node_base_id
        )
        
        # 检查工作流是否全部完成
        await self._check_workflow_completion(workflow_instance_id)
    
    async def mark_node_failed(self,
                             workflow_instance_id: uuid.UUID,
                             node_base_id: uuid.UUID,
                             node_instance_id: uuid.UUID,
                             error_info: Dict[str, Any]):
        """标记节点失败"""
        if workflow_instance_id not in self.workflow_contexts:
            return
        
        context = self.workflow_contexts[workflow_instance_id]
        context['failed_nodes'].add(node_base_id)
        
        # 从正在执行的节点中移除
        if node_base_id in context['current_executing_nodes']:
            context['current_executing_nodes'].remove(node_base_id)
        
        # 更新失败状态
        self.node_completion_status[node_instance_id] = 'FAILED'
        
        logger.error(f"Node {node_base_id} failed in workflow {workflow_instance_id}: {error_info}")
    
    async def mark_node_executing(self,
                                workflow_instance_id: uuid.UUID,
                                node_base_id: uuid.UUID,
                                node_instance_id: uuid.UUID):
        """标记节点开始执行"""
        if workflow_instance_id not in self.workflow_contexts:
            return
        
        context = self.workflow_contexts[workflow_instance_id]
        context['current_executing_nodes'].add(node_base_id)
        
        self.node_completion_status[node_instance_id] = 'EXECUTING'
        
        logger.info(f"Node {node_base_id} started executing in workflow {workflow_instance_id}")
    
    async def _check_and_trigger_downstream_nodes(self, 
                                                workflow_instance_id: uuid.UUID,
                                                completed_node_id: uuid.UUID):
        """检查并触发下游节点"""
        triggered_nodes = []
        
        # 遍历所有节点依赖，找到以当前节点为上游的节点
        for node_instance_id, deps in self.node_dependencies.items():
            if (deps['workflow_instance_id'] == workflow_instance_id and 
                completed_node_id in deps['upstream_nodes']):
                
                # 标记该上游节点已完成
                deps['completed_upstream'].add(completed_node_id)
                
                # 检查是否所有上游节点都已完成
                if len(deps['completed_upstream']) == len(deps['upstream_nodes']):
                    deps['ready_to_execute'] = True
                    
                    # 添加到待触发队列
                    self.pending_triggers[workflow_instance_id].add(node_instance_id)
                    triggered_nodes.append(node_instance_id)
                    
                    logger.info(f"Node {deps['node_base_id']} ready to execute - all upstream completed")
        
        # 通知回调函数有新的节点准备执行
        if triggered_nodes:
            await self._notify_completion_callbacks(workflow_instance_id, triggered_nodes)
    
    async def get_ready_nodes(self, workflow_instance_id: uuid.UUID) -> List[uuid.UUID]:
        """获取准备执行的节点实例ID列表"""
        if workflow_instance_id not in self.pending_triggers:
            return []
        
        ready_nodes = list(self.pending_triggers[workflow_instance_id])
        # 清空待触发队列
        self.pending_triggers[workflow_instance_id].clear()
        
        return ready_nodes
    
    async def get_node_upstream_context(self, 
                                      workflow_instance_id: uuid.UUID,
                                      node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取节点的一阶上游上下文数据"""
        if node_instance_id not in self.node_dependencies:
            return {'immediate_upstream_results': {}, 'upstream_node_count': 0}
        
        deps = self.node_dependencies[node_instance_id]
        upstream_nodes = deps['upstream_nodes']
        
        # 获取工作流上下文
        workflow_context = self.workflow_contexts.get(workflow_instance_id, {})
        node_outputs = workflow_context.get('node_outputs', {})
        
        # 收集一阶上游节点的输出数据
        upstream_results = {}
        for upstream_node_id in upstream_nodes:
            if upstream_node_id in node_outputs:
                upstream_results[str(upstream_node_id)] = node_outputs[upstream_node_id]
        
        return {
            'immediate_upstream_results': upstream_results,
            'upstream_node_count': len(upstream_nodes),
            'workflow_global': {
                'execution_path': workflow_context.get('execution_path', []),
                'global_data': workflow_context.get('global_data', {}),
                'execution_start_time': workflow_context.get('execution_start_time')
            }
        }
    
    async def get_workflow_status(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取工作流整体状态"""
        if workflow_instance_id not in self.workflow_contexts:
            return {'status': 'NOT_FOUND'}
        
        context = self.workflow_contexts[workflow_instance_id]
        
        # 统计节点状态
        total_nodes = len(self.node_dependencies)
        completed_nodes = len(context['completed_nodes'])
        failed_nodes = len(context['failed_nodes'])
        executing_nodes = len(context['current_executing_nodes'])
        pending_nodes = total_nodes - completed_nodes - failed_nodes - executing_nodes
        
        # 判断工作流整体状态
        if failed_nodes > 0:
            overall_status = 'FAILED'
        elif completed_nodes == total_nodes:
            overall_status = 'COMPLETED'
        elif executing_nodes > 0 or pending_nodes > 0:
            overall_status = 'RUNNING'
        else:
            overall_status = 'UNKNOWN'
        
        return {
            'status': overall_status,
            'total_nodes': total_nodes,
            'completed_nodes': completed_nodes,
            'failed_nodes': failed_nodes,
            'executing_nodes': executing_nodes,
            'pending_nodes': pending_nodes,
            'execution_path': context['execution_path'],
            'execution_start_time': context['execution_start_time']
        }
    
    def register_completion_callback(self, callback: callable):
        """注册节点完成回调函数"""
        self.completion_callbacks.append(callback)
    
    async def _notify_completion_callbacks(self, 
                                         workflow_instance_id: uuid.UUID,
                                         triggered_nodes: List[uuid.UUID]):
        """通知回调函数有新节点准备执行"""
        for callback in self.completion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(workflow_instance_id, triggered_nodes)
                else:
                    callback(workflow_instance_id, triggered_nodes)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")
    
    async def cleanup_workflow_context(self, workflow_instance_id: uuid.UUID):
        """清理工作流上下文（工作流完成后调用）"""
        if workflow_instance_id in self.workflow_contexts:
            del self.workflow_contexts[workflow_instance_id]
        
        if workflow_instance_id in self.pending_triggers:
            del self.pending_triggers[workflow_instance_id]
        
        # 清理相关的节点依赖
        to_remove = []
        for node_instance_id, deps in self.node_dependencies.items():
            if deps['workflow_instance_id'] == workflow_instance_id:
                to_remove.append(node_instance_id)
        
        for node_instance_id in to_remove:
            del self.node_dependencies[node_instance_id]
            if node_instance_id in self.node_completion_status:
                del self.node_completion_status[node_instance_id]
        
        logger.info(f"Cleaned up workflow context for {workflow_instance_id}")
    
    def get_node_dependency_info(self, node_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点的依赖信息"""
        return self.node_dependencies.get(node_instance_id)
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行"""
        deps = self.node_dependencies.get(node_instance_id)
        return deps is not None and deps.get('ready_to_execute', False)
    
    async def _check_workflow_completion(self, workflow_instance_id: uuid.UUID):
        """检查工作流是否完成并更新数据库状态"""
        try:
            if workflow_instance_id not in self.workflow_contexts:
                return
            
            # 获取工作流状态
            status_info = await self.get_workflow_status(workflow_instance_id)
            current_status = status_info.get('status')
            
            logger.info(f"🔍 [工作流状态检查] 工作流 {workflow_instance_id}:")
            logger.info(f"   - 当前状态: {current_status}")
            logger.info(f"   - 总节点数: {status_info.get('total_nodes', 0)}")
            logger.info(f"   - 已完成节点: {status_info.get('completed_nodes', 0)}")
            logger.info(f"   - 失败节点: {status_info.get('failed_nodes', 0)}")
            logger.info(f"   - 执行中节点: {status_info.get('executing_nodes', 0)}")
            
            # 如果工作流已完成或失败，更新数据库状态
            if current_status in ['COMPLETED', 'FAILED']:
                logger.info(f"🎯 [工作流状态检查] 工作流 {workflow_instance_id} 需要更新状态为: {current_status}")
                
                # 延迟导入工作流实例仓库避免循环依赖
                from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
                workflow_repo = WorkflowInstanceRepository()
                
                # 准备输出数据
                context = self.workflow_contexts[workflow_instance_id]
                output_data = {
                    'completion_time': datetime.utcnow().isoformat(),
                    'node_outputs': context.get('node_outputs', {}),
                    'execution_path': context.get('execution_path', []),
                    'total_nodes': status_info.get('total_nodes', 0),
                    'completed_nodes': status_info.get('completed_nodes', 0),
                    'failed_nodes': status_info.get('failed_nodes', 0)
                }
                
                # 更新工作流实例状态
                if current_status == 'COMPLETED':
                    update_data = WorkflowInstanceUpdate(
                        status=WorkflowInstanceStatus.COMPLETED,
                        output_data=output_data
                    )
                    logger.info(f"✅ [工作流状态检查] 标记工作流 {workflow_instance_id} 为已完成")
                else:  # FAILED
                    update_data = WorkflowInstanceUpdate(
                        status=WorkflowInstanceStatus.FAILED,
                        output_data=output_data,
                        error_message="工作流中有节点执行失败"
                    )
                    logger.error(f"❌ [工作流状态检查] 标记工作流 {workflow_instance_id} 为失败")
                
                # 更新数据库
                await workflow_repo.update_instance(workflow_instance_id, update_data)
                
                # 清理工作流上下文
                await self.cleanup_workflow_context(workflow_instance_id)
                
            else:
                logger.info(f"⏳ [工作流状态检查] 工作流 {workflow_instance_id} 仍在运行中")
                
        except Exception as e:
            logger.error(f"❌ 检查工作流完成状态失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")