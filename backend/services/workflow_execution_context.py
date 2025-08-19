"""
工作流执行上下文管理器
统一管理单个工作流实例的执行上下文、状态和依赖关系
一个工作流实例对应一个上下文管理器实例
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Set, Optional
import asyncio
import json
from loguru import logger

# 延迟导入避免循环依赖
from ..models.instance import WorkflowInstanceStatus, WorkflowInstanceUpdate


def _serialize_for_json(obj):
    """将对象序列化为JSON兼容格式"""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            serialized_key = str(key) if isinstance(key, uuid.UUID) else key
            serialized_value = _serialize_for_json(value)
            result[serialized_key] = serialized_value
        return result
    elif isinstance(obj, (list, tuple, set)):
        return [_serialize_for_json(item) for item in obj]
    else:
        return obj


class WorkflowExecutionContext:
    """工作流执行上下文管理器
    
    统一管理一个工作流实例的：
    - 执行上下文数据
    - 节点状态管理 
    - 依赖关系管理
    - 数据流管理
    """
    
    def __init__(self, workflow_instance_id: uuid.UUID):
        self.workflow_instance_id = workflow_instance_id
        
        # 执行上下文数据
        self.execution_context = {
            'global_data': {},
            'node_outputs': {},  # node_instance_id -> output_data
            'execution_path': [],  # 已执行的节点路径 (node_instance_id)
            'execution_start_time': datetime.utcnow().isoformat(),
            'current_executing_nodes': set(),  # 当前执行中的节点实例ID (node_instance_id)
            'completed_nodes': set(),  # 已完成的节点实例ID (node_instance_id)
            'failed_nodes': set(),  # 失败的节点实例ID (node_instance_id)
            'auto_save_counter': 0,
            'last_snapshot_time': datetime.utcnow().isoformat(),
            'persistence_enabled': True
        }
        
        # 节点依赖关系管理 - 使用node_instance_id作为key
        self.node_dependencies: Dict[uuid.UUID, Dict[str, Any]] = {}
        
        # 节点状态管理
        self.node_states: Dict[uuid.UUID, str] = {}  # node_instance_id -> state
        
        # 待触发的节点队列
        self.pending_triggers: Set[uuid.UUID] = set()
        
        # 异步锁管理
        self._context_lock = asyncio.Lock()
        
        # 回调函数注册
        self.completion_callbacks: List[callable] = []
        
        logger.debug(f"🏠 初始化工作流执行上下文: {workflow_instance_id}")
    
    async def initialize_context(self, restore_from_snapshot: bool = False):
        """初始化工作流上下文"""
        async with self._context_lock:
            if restore_from_snapshot:
                # TODO: 实现快照恢复
                pass
            
            # 获取开始节点信息
            start_node_info = await self._get_start_node_task_descriptions()
            self.execution_context['global_data']['start_node_descriptions'] = start_node_info
            
            logger.info(f"✅ 工作流上下文初始化完成: {self.workflow_instance_id}")
    
    async def register_node_dependencies(self, 
                                       node_instance_id: uuid.UUID,
                                       node_id: uuid.UUID,
                                       upstream_nodes: List[uuid.UUID]):
        """注册节点的依赖关系（修复版：使用node_states检查实例状态）"""
        async with self._context_lock:
            # 检查已完成的上游节点实例（使用node_states）
            completed_upstream = set()
            
            for upstream_node_instance_id in upstream_nodes:
                if self.node_states.get(upstream_node_instance_id) == 'COMPLETED':
                    completed_upstream.add(upstream_node_instance_id)
                    logger.debug(f"  上游节点实例 {upstream_node_instance_id} 已完成")
            
            # 计算是否准备执行
            ready_to_execute = len(completed_upstream) == len(upstream_nodes)
            
            self.node_dependencies[node_instance_id] = {
                'node_id': node_id,
                'workflow_instance_id': self.workflow_instance_id,
                'upstream_nodes': upstream_nodes,
                'completed_upstream': completed_upstream,
                'ready_to_execute': ready_to_execute,
                'dependency_count': len(upstream_nodes)
            }
            
            # 初始化节点状态
            self.node_states[node_instance_id] = 'PENDING'
            
            logger.info(f"📋 [依赖注册] 节点实例 {node_instance_id}")
            logger.info(f"  - 上游节点实例总数: {len(upstream_nodes)}")
            logger.info(f"  - 已完成上游实例: {len(completed_upstream)}")
            logger.info(f"  - 准备执行: {ready_to_execute}")
            logger.info(f"  - 当前依赖字典大小: {len(self.node_dependencies)}")
            if upstream_nodes:
                logger.info(f"  - 上游节点实例列表: {upstream_nodes}")
            if completed_upstream:
                logger.info(f"  - 已完成上游实例列表: {list(completed_upstream)}")
    
    async def mark_node_executing(self, node_id: uuid.UUID, node_instance_id: uuid.UUID):
        """标记节点开始执行"""
        async with self._context_lock:
            # 🔧 防护：确保关键集合字段是set类型
            if not isinstance(self.execution_context.get('current_executing_nodes'), set):
                logger.warning("🔧 修复current_executing_nodes类型从list到set")
                self.execution_context['current_executing_nodes'] = set(self.execution_context.get('current_executing_nodes', []))
            
            self.node_states[node_instance_id] = 'EXECUTING'
            # 🔧 修复：统一使用node_instance_id管理执行状态
            self.execution_context['current_executing_nodes'].add(node_instance_id)
            
            logger.trace(f"⚡ 标记节点实例执行: {node_instance_id} (节点ID: {node_id})")
    
    async def mark_node_completed(self, node_id: uuid.UUID, node_instance_id: uuid.UUID, output_data: Dict[str, Any]):
        """标记节点完成"""
        async with self._context_lock:
            # 🔧 防护：确保关键集合字段是set类型（修复JSON恢复后的类型问题）
            if not isinstance(self.execution_context.get('completed_nodes'), set):
                logger.warning("🔧 修复completed_nodes类型从list到set")
                self.execution_context['completed_nodes'] = set(self.execution_context.get('completed_nodes', []))
            if not isinstance(self.execution_context.get('current_executing_nodes'), set):
                logger.warning("🔧 修复current_executing_nodes类型从list到set")
                self.execution_context['current_executing_nodes'] = set(self.execution_context.get('current_executing_nodes', []))
            if not isinstance(self.execution_context.get('failed_nodes'), set):
                logger.warning("🔧 修复failed_nodes类型从list到set")
                self.execution_context['failed_nodes'] = set(self.execution_context.get('failed_nodes', []))
            
            # 防重复处理 - 检查内存状态
            # 🔧 修复：使用node_instance_id检查完成状态，因为我们管理的是实例状态
            if node_instance_id in self.execution_context['completed_nodes']:
                logger.warning(f"🔄 节点实例 {node_instance_id} 已经在内存中标记为完成，跳过重复处理")
                return
            
            # 防重复处理 - 检查数据库状态
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            try:
                existing_node = await node_repo.get_instance_by_id(node_instance_id)
                if existing_node and existing_node.get('status') == 'completed':
                    logger.warning(f"🔄 节点实例 {node_instance_id} 在数据库中已经完成，同步内存状态")
                    # 同步内存状态
                    self.node_states[node_instance_id] = 'COMPLETED'
                    # 🔧 修复：统一使用node_instance_id管理完成状态
                    self.execution_context['completed_nodes'].add(node_instance_id)
                    # 🔧 修复：使用node_instance_id存储输出数据
                    self.execution_context['node_outputs'][node_instance_id] = output_data
                    self.execution_context['current_executing_nodes'].discard(node_instance_id)
                    return
            except Exception as e:
                logger.warning(f"⚠️ 检查节点数据库状态时出错: {e}")
            
            # 更新状态
            self.node_states[node_instance_id] = 'COMPLETED'
            # 🔧 修复：统一使用node_instance_id管理完成状态，保持一致性
            self.execution_context['completed_nodes'].add(node_instance_id)
            # 🔧 修复：使用node_instance_id作为键存储输出数据，这样获取上下文时能正确匹配
            self.execution_context['node_outputs'][node_instance_id] = output_data
            logger.debug(f"🔧 [上下文修复] 节点输出存储: {node_instance_id} -> {len(str(output_data))}字符")
            logger.debug(f"🔧 [上下文修复] 当前所有输出键: {list(self.execution_context['node_outputs'].keys())}")
            self.execution_context['execution_path'].append(str(node_instance_id))
            
            # 从执行中移除
            # 🔧 修复：统一使用node_instance_id管理执行状态
            self.execution_context['current_executing_nodes'].discard(node_instance_id)
            
            logger.info(f"🎉 节点完成: {node_id}")
            
            # 更新数据库状态
            await self._update_database_node_state(node_instance_id, 'COMPLETED', output_data)
        
        # 检查并触发下游节点（在锁外执行避免死锁）
        triggered_nodes = await self._check_and_trigger_downstream_nodes(node_instance_id)
        
        # 通知回调
        if triggered_nodes:
            await self._notify_completion_callbacks(triggered_nodes)
        
        # 检查工作流完成
        await self._check_workflow_completion()
    
    async def mark_node_failed(self, node_id: uuid.UUID, node_instance_id: uuid.UUID, error_info: Dict[str, Any]):
        """标记节点失败"""
        async with self._context_lock:
            # 🔧 防护：确保关键集合字段是set类型
            if not isinstance(self.execution_context.get('failed_nodes'), set):
                logger.warning("🔧 修复failed_nodes类型从list到set")
                self.execution_context['failed_nodes'] = set(self.execution_context.get('failed_nodes', []))
            if not isinstance(self.execution_context.get('current_executing_nodes'), set):
                logger.warning("🔧 修复current_executing_nodes类型从list到set")
                self.execution_context['current_executing_nodes'] = set(self.execution_context.get('current_executing_nodes', []))
            
            self.node_states[node_instance_id] = 'FAILED'
            # 🔧 修复：统一使用node_instance_id管理失败状态，保持一致性
            self.execution_context['failed_nodes'].add(node_instance_id)
            self.execution_context['current_executing_nodes'].discard(node_instance_id)
            
            logger.error(f"❌ 节点实例失败: {node_instance_id} (节点ID: {node_id}) - {error_info}")
            
            # 更新数据库状态
            await self._update_database_node_state(node_instance_id, 'FAILED', None, error_info)
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行"""
        deps = self.node_dependencies.get(node_instance_id)
        if not deps:
            return False
        
        return deps.get('ready_to_execute', False)
    
    def get_node_state(self, node_instance_id: uuid.UUID) -> str:
        """获取节点状态"""
        return self.node_states.get(node_instance_id, 'UNKNOWN')
    
    async def get_node_execution_context(self, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取节点的执行上下文数据"""
        async with self._context_lock:
            # 获取节点依赖信息
            deps = self.node_dependencies.get(node_instance_id)
            if not deps:
                logger.warning(f"⚠️ 节点实例 {node_instance_id} 没有依赖信息")
                return {
                    'immediate_upstream_results': {},
                    'workflow_global': {
                        'global_data': self.execution_context.get('global_data', {}),
                        'workflow_instance_id': str(self.workflow_instance_id),
                        'execution_start_time': self.execution_context.get('execution_start_time'),
                        'execution_path': self.execution_context.get('execution_path', [])
                    },
                    'upstream_node_count': 0,
                    'current_node': {}
                }
            
            upstream_nodes = deps.get('upstream_nodes', [])
            logger.debug(f"🔍 [上下文构建] 节点实例 {node_instance_id} 有 {len(upstream_nodes)} 个上游节点实例")
            
            # 收集上游节点实例的输出数据
            immediate_upstream_results = {}
            logger.debug(f"🔧 [上下文获取] 开始收集上游输出，上游节点数: {len(upstream_nodes)}")
            logger.debug(f"🔧 [上下文获取] 上游节点实例IDs: {upstream_nodes}")
            logger.debug(f"🔧 [上下文获取] 可用输出数据键: {list(self.execution_context['node_outputs'].keys())}")
            
            for upstream_node_instance_id in upstream_nodes:
                logger.debug(f"🔧 [上下文获取] 检查上游节点: {upstream_node_instance_id}")
                if upstream_node_instance_id in self.execution_context['node_outputs']:
                    output_data = self.execution_context['node_outputs'][upstream_node_instance_id]
                    logger.debug(f"🔧 [上下文获取] ✅ 找到输出数据: {len(str(output_data))}字符")
                    # 通过upstream_node_instance_id获取对应的node_id来查询节点名称
                    upstream_deps = self.node_dependencies.get(upstream_node_instance_id)
                    if upstream_deps:
                        upstream_node_id = upstream_deps.get('node_id')
                        node_name = await self._get_node_name_by_id(upstream_node_id) if upstream_node_id else None
                    else:
                        node_name = None
                    
                    upstream_key = node_name or f'节点实例_{str(upstream_node_instance_id)[:8]}'
                    immediate_upstream_results[upstream_key] = {
                        'node_instance_id': str(upstream_node_instance_id),
                        'node_name': node_name or f'节点实例_{str(upstream_node_instance_id)[:8]}',
                        'output_data': output_data,
                        'status': 'completed'
                    }
                    logger.debug(f"  ✅ 添加上游输出: {upstream_key} -> {len(str(output_data))}字符")
                else:
                    logger.warning(f"  ⚠️ 上游节点实例 {upstream_node_instance_id} 的输出数据不存在")
                    logger.debug(f"🔧 [上下文获取] ❌ 未找到 {upstream_node_instance_id} 的输出数据")
            
            # 当前节点信息
            current_node_name = await self._get_node_name_by_id(deps.get('node_id'))
            
            context_data = {
                'immediate_upstream_results': immediate_upstream_results,
                'workflow_global': {
                    'global_data': self.execution_context.get('global_data', {}),
                    'workflow_instance_id': str(self.workflow_instance_id),
                    'execution_start_time': self.execution_context.get('execution_start_time'),
                    'execution_path': self.execution_context.get('execution_path', [])
                },
                'upstream_node_count': len(upstream_nodes),
                'current_node': {
                    'node_instance_id': str(node_instance_id),
                    'node_id': str(deps.get('node_id')),
                    'node_name': current_node_name,
                    'status': self.get_node_state(node_instance_id)
                }
            }
            
            logger.debug(f"✅ [上下文构建] 为节点实例 {node_instance_id} 构建了包含 {len(immediate_upstream_results)} 个上游结果的上下文")
            return context_data
    
    async def _check_and_trigger_downstream_nodes(self, completed_node_instance_id: uuid.UUID) -> List[uuid.UUID]:
        """检查并触发下游节点（修复版：防止竞态和重复触发，统一使用node_instance_id）"""
        triggered_nodes = []
        
        # 🔒 使用锁保护整个检查和触发过程，防止竞态条件
        async with self._context_lock:
            logger.info(f"🔍 [下游触发] 检查完成节点实例 {completed_node_instance_id} 的下游依赖...")
            logger.info(f"   - 当前注册的节点依赖数量: {len(self.node_dependencies)}")
            logger.info(f"   - 依赖字典的key列表: {list(self.node_dependencies.keys())}")
            
            for node_instance_id, deps in self.node_dependencies.items():
                logger.info(f"   - 检查节点实例 {node_instance_id}，上游依赖: {deps['upstream_nodes']}")
                logger.info(f"     - 节点状态: {self.node_states.get(node_instance_id, 'UNKNOWN')}")
                logger.info(f"     - 已完成上游: {len(deps.get('completed_upstream', set()))}/{len(deps['upstream_nodes'])}")
                
                if completed_node_instance_id in deps['upstream_nodes']:
                    logger.info(f"✅ [下游触发] 找到下游节点实例: {node_instance_id}")
                    logger.info(f"   - 当前状态: {self.node_states.get(node_instance_id, 'UNKNOWN')}")
                    logger.info(f"   - 依赖状态: {len(deps.get('completed_upstream', set()))}/{len(deps['upstream_nodes'])}")
                    
                    # 🔒 先检查节点是否已经被触发或正在执行
                    if deps.get('ready_to_execute', False):
                        logger.trace(f"  ⚠️ 节点实例 {node_instance_id} 已经被标记为准备执行，跳过")
                        continue
                        
                    # 检查节点实例是否正在执行（使用node_states检查）
                    if self.node_states.get(node_instance_id) == 'EXECUTING':
                        logger.trace(f"  ⚠️ 节点实例 {node_instance_id} 正在执行中，跳过")
                        continue
                        
                    # 检查节点实例是否已完成（使用node_states检查实例级别状态）
                    if self.node_states.get(node_instance_id) == 'COMPLETED':
                        logger.trace(f"  ⚠️ 节点实例 {node_instance_id} 已完成，跳过")
                        continue
                    
                    # 标记上游节点实例完成
                    if completed_node_instance_id not in deps['completed_upstream']:
                        deps['completed_upstream'].add(completed_node_instance_id)
                        logger.info(f"  ✅ 标记上游节点实例 {completed_node_instance_id} 为已完成")
                    else:
                        logger.debug(f"  ℹ️ 上游节点实例 {completed_node_instance_id} 已经标记为完成")
                    
                    # 严格检查所有上游是否都完成
                    total_upstream = len(deps['upstream_nodes'])
                    completed_upstream = len(deps['completed_upstream'])
                    
                    logger.info(f"  📊 节点实例 {node_instance_id} 依赖状态: {completed_upstream}/{total_upstream}")
                    
                    # 只有当所有上游都完成时才触发
                    if completed_upstream == total_upstream and total_upstream > 0:
                        # 双重检查：确保所有上游节点实例都已完成（使用node_states检查）
                        all_upstream_completed_verified = True
                        for upstream_instance_id in deps['upstream_nodes']:
                            if self.node_states.get(upstream_instance_id) != 'COMPLETED':
                                logger.trace(f"  ❌ 上游节点实例 {upstream_instance_id} 状态为 {self.node_states.get(upstream_instance_id, 'UNKNOWN')}，等待")
                                all_upstream_completed_verified = False
                                break
                        
                        if all_upstream_completed_verified:
                            # 防止重复触发的最终检查
                            if node_instance_id not in self.pending_triggers:
                                deps['ready_to_execute'] = True
                                self.pending_triggers.add(node_instance_id)
                                triggered_nodes.append(node_instance_id)
                                
                                logger.debug(f"🚀 触发下游节点实例: {node_instance_id} (依赖已全部满足: {deps['upstream_nodes']})")
                            else:
                                logger.trace(f"  ⚠️ 节点实例 {node_instance_id} 已在pending_triggers中，避免重复触发")
                    else:
                        logger.trace(f"  ⏳ 节点实例 {node_instance_id} 依赖未满足，等待更多上游完成")
            
            logger.info(f"🎯 [下游触发] 触发检查完成，共触发 {len(triggered_nodes)} 个下游节点实例")
            if triggered_nodes:
                logger.info(f"   - 触发的节点实例: {triggered_nodes}")
            else:
                logger.info(f"   - 原因分析: 可能是依赖未完全满足，或节点已处理，或没有下游节点")
        
        return triggered_nodes
    
    async def get_ready_nodes(self) -> List[uuid.UUID]:
        """获取准备执行的节点"""
        ready_nodes = list(self.pending_triggers)
        self.pending_triggers.clear()
        return ready_nodes
    
    async def build_node_context(self, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """构建节点执行上下文"""
        deps = self.node_dependencies.get(node_instance_id, {})
        upstream_nodes = deps.get('upstream_nodes', [])
        
        # 收集上游输出
        upstream_context = {}
        for upstream_node_instance_id in upstream_nodes:
            if upstream_node_instance_id in self.execution_context['node_outputs']:
                # 通过upstream_node_instance_id获取对应的node_id来查询节点名称
                upstream_deps = self.node_dependencies.get(upstream_node_instance_id)
                if upstream_deps:
                    upstream_node_id = upstream_deps.get('node_id')
                    node_name = await self._get_node_name_by_id(upstream_node_id) if upstream_node_id else None
                else:
                    node_name = None
                    
                key = node_name or str(upstream_node_instance_id)
                upstream_context[key] = {
                    'node_instance_id': str(upstream_node_instance_id),
                    'output_data': self.execution_context['node_outputs'][upstream_node_instance_id],
                    'status': 'completed'
                }
        
        return {
            'node_instance_id': str(node_instance_id),
            'upstream_outputs': upstream_context,
            'workflow_context': {
                'workflow_instance_id': str(self.workflow_instance_id),
                'execution_start_time': self.execution_context['execution_start_time'],
                'execution_path': self.execution_context['execution_path'],
                'global_data': self.execution_context['global_data']
            },
            'context_built_at': datetime.utcnow().isoformat()
        }
    
    async def get_workflow_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        total_nodes = len(self.node_dependencies)  # 基于node_instance_id的总数
        
        # 统计已完成的节点实例数量（通过node_states检查）
        completed_node_instances = len([nid for nid, state in self.node_states.items() if state == 'COMPLETED'])
        failed_node_instances = len([nid for nid, state in self.node_states.items() if state == 'FAILED'])
        executing_node_instances = len([nid for nid, state in self.node_states.items() if state == 'EXECUTING'])
        
        # 也保留原有的node_id级别的统计（用于兼容性）
        completed_nodes = len(self.execution_context['completed_nodes'])
        failed_nodes = len(self.execution_context['failed_nodes'])
        executing_nodes = len(self.execution_context['current_executing_nodes'])
        
        logger.debug(f"📊 [状态计算] 工作流状态统计:")
        logger.debug(f"   - 总节点实例: {total_nodes}")
        logger.debug(f"   - 已完成节点实例: {completed_node_instances}")
        logger.debug(f"   - 执行中节点实例: {executing_node_instances}")
        logger.debug(f"   - 失败节点实例: {failed_node_instances}")
        logger.debug(f"   - 已完成节点(node_id): {completed_nodes}")
        
        if failed_node_instances > 0:
            status = 'FAILED'
        elif completed_node_instances == total_nodes and total_nodes > 0:
            status = 'COMPLETED'
        elif executing_node_instances > 0 or (total_nodes - completed_node_instances - failed_node_instances) > 0:
            status = 'RUNNING'
        else:
            status = 'UNKNOWN'
        
        logger.debug(f"📊 [状态计算] 最终状态: {status}")
        
        return {
            'status': status,
            'total_nodes': total_nodes,
            'completed_nodes': completed_node_instances,  # 使用节点实例级别的统计
            'failed_nodes': failed_node_instances,
            'executing_nodes': executing_node_instances,
            'pending_nodes': total_nodes - completed_node_instances - failed_node_instances - executing_node_instances,
            # 保留原有字段用于兼容性
            'completed_nodes_by_id': completed_nodes,
            'failed_nodes_by_id': failed_nodes,
            'executing_nodes_by_id': executing_nodes
        }
    
    def register_completion_callback(self, callback: callable):
        """注册完成回调"""
        self.completion_callbacks.append(callback)
    
    async def _notify_completion_callbacks(self, triggered_nodes: List[uuid.UUID]):
        """通知回调函数"""
        for callback in self.completion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self.workflow_instance_id, triggered_nodes)
                else:
                    callback(self.workflow_instance_id, triggered_nodes)
            except Exception as e:
                logger.error(f"回调函数执行失败: {e}")
    
    async def _check_workflow_completion(self):
        """检查工作流是否完成"""
        status_info = await self.get_workflow_status()
        if status_info['status'] in ['COMPLETED', 'FAILED']:
            logger.info(f"🏁 工作流 {self.workflow_instance_id} 执行完成: {status_info['status']}")
            
            # 更新数据库中的工作流状态
            try:
                from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
                from ..models.instance import WorkflowInstanceUpdate, WorkflowInstanceStatus
                from ..utils.helpers import now_utc
                
                workflow_repo = WorkflowInstanceRepository()
                
                # 确定最终状态
                final_status = WorkflowInstanceStatus.COMPLETED if status_info['status'] == 'COMPLETED' else WorkflowInstanceStatus.FAILED
                
                # 更新工作流实例状态
                update_data = WorkflowInstanceUpdate(
                    status=final_status,
                    completed_at=now_utc() if final_status == WorkflowInstanceStatus.COMPLETED else None,
                    error_message=status_info.get('error_message') if final_status == WorkflowInstanceStatus.FAILED else None
                )
                
                result = await workflow_repo.update_instance(self.workflow_instance_id, update_data)
                if result:
                    logger.info(f"✅ 工作流状态已更新到数据库: {self.workflow_instance_id} -> {final_status.value}")
                else:
                    logger.error(f"❌ 工作流状态更新失败: {self.workflow_instance_id}")
                    
            except Exception as e:
                logger.error(f"❌ 更新工作流状态到数据库时出错: {e}")
                import traceback
                logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _update_database_node_state(self, node_instance_id: uuid.UUID, 
                                        state: str, output_data: Optional[Dict[str, Any]] = None,
                                        error_info: Optional[Dict[str, Any]] = None):
        """更新数据库中的节点状态"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus
            
            node_repo = NodeInstanceRepository()
            
            # 先检查节点实例是否存在
            existing_node = await node_repo.get_instance_by_id(node_instance_id)
            if not existing_node:
                logger.warning(f"⚠️ 节点实例不存在，跳过状态更新: {node_instance_id}")
                return
            
            status_mapping = {
                'COMPLETED': NodeInstanceStatus.COMPLETED,
                'FAILED': NodeInstanceStatus.FAILED,
                'EXECUTING': NodeInstanceStatus.RUNNING,
                'PENDING': NodeInstanceStatus.PENDING
            }
            
            db_status = status_mapping.get(state, NodeInstanceStatus.PENDING)
            
            # 准备输出数据 - 直接使用字典格式，不转换为JSON字符串
            output_data_dict = output_data if output_data else None
            
            update_data = NodeInstanceUpdate(
                status=db_status,
                output_data=output_data_dict,
                error_message=error_info.get('message') if error_info else None
            )
            
            result = await node_repo.update_node_instance(node_instance_id, update_data)
            if result:
                logger.debug(f"✅ 数据库状态更新成功: {node_instance_id} -> {state}")
            else:
                logger.warning(f"⚠️ 数据库状态更新返回空结果: {node_instance_id} -> {state}")
            
        except Exception as e:
            logger.error(f"❌ 数据库状态更新失败: {node_instance_id} -> {state}: {e}")
            # 不抛出异常，让流程继续
    
    async def _get_start_node_task_descriptions(self) -> Dict[str, Any]:
        """获取开始节点任务描述"""
        try:
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            
            node_instance_repo = NodeInstanceRepository()
            
            query = """
                SELECT ni.node_instance_id, ni.node_id, n.name as node_name,
                       n.task_description, ni.task_description as instance_task_description
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = $1
                AND LOWER(n.type) = 'start'
                AND ni.is_deleted = FALSE
                AND n.is_deleted = FALSE
                ORDER BY ni.created_at ASC
            """
            
            start_nodes = await node_instance_repo.db.fetch_all(query, self.workflow_instance_id)
            
            start_node_info = {}
            for node in start_nodes:
                node_id = str(node['node_id'])
                task_description = (
                    node.get('instance_task_description') or 
                    node.get('task_description') or 
                    f"开始节点 {node.get('node_name', '未命名')} 的任务"
                )
                
                start_node_info[node_id] = {
                    'node_instance_id': str(node['node_instance_id']),
                    'node_name': node.get('node_name', '未命名'),
                    'task_description': task_description
                }
            
            return start_node_info
            
        except Exception as e:
            logger.error(f"获取开始节点任务描述失败: {e}")
            return {}
    
    async def _get_node_name_by_id(self, node_id: uuid.UUID) -> str:
        """根据node_id获取节点名称"""
        try:
            from ..repositories.node.node_repository import NodeRepository
            node_repo = NodeRepository()
            
            query = "SELECT name FROM node WHERE node_id = $1"
            result = await node_repo.db.fetch_one(query, node_id)
            return result['name'] if result else None
        except Exception as e:
            logger.error(f"获取节点名称失败: {e}")
            return None
    
    def cleanup(self):
        """清理上下文资源"""
        logger.info(f"🧹 清理工作流上下文: {self.workflow_instance_id}")
        self.execution_context.clear()
        self.node_dependencies.clear()
        self.node_states.clear()
        self.pending_triggers.clear()
        self.completion_callbacks.clear()


# 工作流执行上下文管理器工厂
class WorkflowExecutionContextManager:
    """工作流执行上下文管理器工厂
    
    管理多个工作流实例的上下文管理器
    一个工作流实例对应一个WorkflowExecutionContext
    支持持久化和自动恢复
    """
    
    def __init__(self):
        self.contexts: Dict[uuid.UUID, WorkflowExecutionContext] = {}
        self._contexts_lock = asyncio.Lock()
        self._persistence_enabled = True
        self._auto_recovery_enabled = True
    
    
    async def get_context(self, workflow_instance_id: uuid.UUID) -> Optional[WorkflowExecutionContext]:
        """获取工作流执行上下文（支持自动恢复）"""
        context = self.contexts.get(workflow_instance_id)
        
        # 如果上下文不存在且启用了自动恢复，尝试从数据库恢复
        if context is None and self._auto_recovery_enabled:
            logger.info(f"🔧 上下文不存在，尝试从数据库自动恢复: {workflow_instance_id}")
            context = await self._restore_context_from_database(workflow_instance_id)
            
        return context
    
    async def remove_context(self, workflow_instance_id: uuid.UUID):
        """移除工作流执行上下文"""
        async with self._contexts_lock:
            if workflow_instance_id in self.contexts:
                context = self.contexts[workflow_instance_id]
                context.cleanup()
                del self.contexts[workflow_instance_id]
                logger.info(f"🗑️ 移除工作流执行上下文: {workflow_instance_id}")
    
    def get_all_contexts(self) -> List[WorkflowExecutionContext]:
        """获取所有上下文"""
        return list(self.contexts.values())
    
    def register_completion_callback(self, callback):
        """注册完成回调函数到所有现有和未来的上下文"""
        # 将回调添加到所有现有上下文
        for context in self.contexts.values():
            if callback not in context.completion_callbacks:
                context.completion_callbacks.append(callback)
        
        # 保存回调函数，以便为新创建的上下文自动注册
        if not hasattr(self, '_global_callbacks'):
            self._global_callbacks = []
        if callback not in self._global_callbacks:
            self._global_callbacks.append(callback)
            logger.debug(f"📝 注册全局完成回调函数: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    async def get_or_create_context(self, workflow_instance_id: uuid.UUID) -> WorkflowExecutionContext:
        """获取或创建工作流执行上下文（改进版本，自动注册全局回调）"""
        async with self._contexts_lock:
            if workflow_instance_id not in self.contexts:
                context = WorkflowExecutionContext(workflow_instance_id)
                
                # 为新上下文注册所有全局回调
                if hasattr(self, '_global_callbacks'):
                    for callback in self._global_callbacks:
                        if callback not in context.completion_callbacks:
                            context.completion_callbacks.append(callback)
                
                self.contexts[workflow_instance_id] = context
                logger.info(f"🆕 创建新的工作流执行上下文: {workflow_instance_id}")
            
            return self.contexts[workflow_instance_id]
    
    async def initialize_workflow_context(self, workflow_instance_id: uuid.UUID):
        """初始化工作流上下文"""
        context = await self.get_or_create_context(workflow_instance_id)
        await context.initialize_context()
    
    async def get_task_context_data(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取任务的上下文数据"""
        context = await self.get_context(workflow_instance_id)
        if context:
            return await context.get_node_execution_context(node_instance_id)
        return {}
    
    async def mark_node_completed(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID, 
                                node_instance_id: uuid.UUID, output_data: Dict[str, Any]):
        """标记节点完成"""
        context = await self.get_context(workflow_instance_id)
        if context:
            await context.mark_node_completed(node_id, node_instance_id, output_data)
    
    async def mark_node_failed(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID, 
                             node_instance_id: uuid.UUID, error_info: Dict[str, Any]):
        """标记节点失败"""
        context = await self.get_context(workflow_instance_id)
        if context:
            await context.mark_node_failed(node_id, node_instance_id, error_info)
    
    @property
    def node_completion_status(self) -> Dict[uuid.UUID, str]:
        """获取所有节点的完成状态（兼容性属性）"""
        if not hasattr(self, '_node_completion_status'):
            self._node_completion_status = {}
        return self._node_completion_status
    
    async def register_node_dependencies(self, workflow_instance_id: uuid.UUID, 
                                       node_instance_id: uuid.UUID, node_id: uuid.UUID, 
                                       upstream_nodes: List[uuid.UUID]):
        """注册节点依赖关系"""
        context = await self.get_or_create_context(workflow_instance_id)
        await context.register_node_dependencies(node_instance_id, node_id, upstream_nodes)
    
    def print_dependency_summary(self, workflow_instance_id: uuid.UUID):
        """打印依赖关系摘要"""
        context = self.contexts.get(workflow_instance_id)
        if context:
            logger.info(f"📊 工作流 {workflow_instance_id} 依赖关系摘要:")
            logger.info(f"   - 节点总数: {len(context.node_dependencies)}")
            logger.info(f"   - 已完成节点: {len(context.execution_context.get('completed_nodes', set()))}")
            logger.info(f"   - 执行中节点: {len(context.execution_context.get('current_executing_nodes', set()))}")
            logger.info(f"   - 失败节点: {len(context.execution_context.get('failed_nodes', set()))}")
        else:
            logger.warning(f"⚠️ 未找到工作流 {workflow_instance_id} 的上下文信息")
    
    def get_node_dependency_info(self, node_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点依赖信息"""
        for workflow_context in self.contexts.values():
            if node_instance_id in workflow_context.node_dependencies:
                return workflow_context.node_dependencies[node_instance_id]
        return None
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行"""
        for workflow_context in self.contexts.values():
            if node_instance_id in workflow_context.node_dependencies:
                return workflow_context.is_node_ready_to_execute(node_instance_id)
        return False
    
    async def mark_node_executing(self, workflow_instance_id: uuid.UUID, node_id: uuid.UUID, 
                                 node_instance_id: uuid.UUID):
        """标记节点开始执行"""
        context = await self.get_context(workflow_instance_id)
        if context:
            await context.mark_node_executing(node_id, node_instance_id)
    
    async def cleanup_workflow_context(self, workflow_instance_id: uuid.UUID):
        """清理工作流上下文"""
        await self.remove_context(workflow_instance_id)
    
    async def get_node_upstream_context(self, workflow_instance_id: uuid.UUID, 
                                       node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取节点上游上下文数据"""
        context = await self.get_context(workflow_instance_id)
        if context:
            return await context.get_node_execution_context(node_instance_id)
        return {}
    
    async def ensure_context_lifecycle_consistency(self, workflow_instance_id: uuid.UUID):
        """确保上下文生命周期一致性"""
        # 确保工作流上下文存在
        await self.get_or_create_context(workflow_instance_id)
    
    async def _restore_context_from_database(self, workflow_instance_id: uuid.UUID) -> Optional[WorkflowExecutionContext]:
        """从数据库恢复工作流上下文（核心恢复逻辑）"""
        try:
            logger.info(f"🔄 开始从数据库恢复工作流上下文: {workflow_instance_id}")
            
            # 1. 检查工作流实例是否存在
            from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
            workflow_repo = WorkflowInstanceRepository()
            workflow = await workflow_repo.get_instance_by_id(workflow_instance_id)
            
            if not workflow:
                logger.warning(f"❌ 工作流实例不存在，无法恢复上下文: {workflow_instance_id}")
                return None
            
            # 2. 创建新的上下文实例
            async with self._contexts_lock:
                context = WorkflowExecutionContext(workflow_instance_id)
                await context.initialize_context()
                self.contexts[workflow_instance_id] = context
                logger.info(f"✅ 创建空白上下文成功: {workflow_instance_id}")
            
            # 3. 恢复节点实例状态
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            nodes = await node_repo.get_instances_by_workflow_instance(workflow_instance_id)
            
            logger.info(f"📋 发现 {len(nodes)} 个节点实例，开始恢复状态...")
            
            completed_count = 0
            for node in nodes:
                node_instance_id = node['node_instance_id']
                node_id = node['node_id'] 
                node_name = node.get('node_instance_name', '未知')
                status = node.get('status', 'pending')
                
                # 恢复节点状态到内存
                context.node_states[node_instance_id] = status
                
                # 如果节点已完成，恢复其输出数据
                if status == 'completed':
                    output_data = {
                        'status': 'completed',
                        'node_name': node_name,
                        'completed_at': str(node.get('completed_at', '')),
                        'output_data': node.get('output_data', {})
                    }
                    
                    # 标记节点完成
                    await context.mark_node_completed(node_id, node_instance_id, output_data)
                    completed_count += 1
                    logger.debug(f"✅ 恢复已完成节点: {node_name}")
                
                elif status == 'running':
                    # 标记节点正在执行
                    await context.mark_node_executing(node_id, node_instance_id)
                    logger.debug(f"🔄 恢复执行中节点: {node_name}")
            
            logger.info(f"🎯 上下文恢复完成: {completed_count} 个已完成节点已恢复")
            
            # 4. 持久化上下文状态
            if self._persistence_enabled:
                await self._persist_context_snapshot(workflow_instance_id, context)
            
            return context
            
        except Exception as e:
            logger.error(f"❌ 从数据库恢复上下文失败: {workflow_instance_id}, 错误: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None
    
    async def _persist_context_snapshot(self, workflow_instance_id: uuid.UUID, context: WorkflowExecutionContext):
        """持久化上下文快照到数据库"""
        try:
            if not self._persistence_enabled:
                return
                
            logger.debug(f"💾 持久化上下文快照: {workflow_instance_id}")
            
            # 构造快照数据
            snapshot_data = {
                'workflow_instance_id': str(workflow_instance_id),
                'execution_context': _serialize_for_json(context.execution_context),
                'node_states': {str(k): v for k, v in context.node_states.items()},
                'completed_nodes_count': len(context.execution_context.get('completed_nodes', set())),
                'snapshot_time': datetime.utcnow().isoformat(),
                'context_version': '2.0'  # 版本标识
            }
            
            # 这里可以存储到Redis或数据库表中
            # 暂时使用日志记录（生产环境中可替换为实际存储）
            logger.debug(f"📊 上下文快照数据: {len(str(snapshot_data))} 字符")
            
        except Exception as e:
            logger.error(f"持久化上下文快照失败: {e}")
    
    async def create_context_snapshot(self, workflow_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """创建上下文快照（用于细分工作流隔离）"""
        context = await self.get_context(workflow_instance_id)
        if not context:
            return None
            
        return {
            'workflow_instance_id': str(workflow_instance_id),
            'execution_context': _serialize_for_json(context.execution_context),
            'node_states': {str(k): v for k, v in context.node_states.items()},
            'node_dependencies': {str(k): v for k, v in context.node_dependencies.items()},
            'snapshot_time': datetime.utcnow().isoformat()
        }
    
    async def restore_from_snapshot(self, workflow_instance_id: uuid.UUID, snapshot: Dict[str, Any]):
        """从快照恢复上下文（用于细分工作流隔离）"""
        try:
            logger.info(f"🔄 从快照恢复上下文: {workflow_instance_id}")
            
            async with self._contexts_lock:
                if workflow_instance_id not in self.contexts:
                    context = WorkflowExecutionContext(workflow_instance_id)
                    self.contexts[workflow_instance_id] = context
                else:
                    context = self.contexts[workflow_instance_id]
                
                # 恢复执行上下文，确保集合类型字段正确恢复
                execution_context = snapshot.get('execution_context', {})
                context.execution_context.update(execution_context)
                
                # 修复：确保关键的集合字段被正确恢复为set类型（JSON序列化会将set转为list）
                if 'completed_nodes' in execution_context:
                    context.execution_context['completed_nodes'] = set(execution_context['completed_nodes'])
                if 'current_executing_nodes' in execution_context:
                    context.execution_context['current_executing_nodes'] = set(execution_context['current_executing_nodes'])
                if 'failed_nodes' in execution_context:
                    context.execution_context['failed_nodes'] = set(execution_context['failed_nodes'])
                
                # 恢复节点状态
                node_states = snapshot.get('node_states', {})
                for node_id_str, state in node_states.items():
                    context.node_states[uuid.UUID(node_id_str)] = state
                
                logger.info(f"✅ 从快照恢复上下文成功: {workflow_instance_id}")
                
        except Exception as e:
            logger.error(f"❌ 从快照恢复上下文失败: {e}")
    
    async def check_context_health(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """检查上下文健康状态"""
        try:
            context = self.contexts.get(workflow_instance_id)
            
            if not context:
                return {
                    'healthy': False,
                    'status': 'context_missing',
                    'message': '上下文不存在于内存中',
                    'auto_recovery_available': self._auto_recovery_enabled
                }
            
            # 检查内存状态与数据库状态一致性
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            db_nodes = await node_repo.get_instances_by_workflow_instance(workflow_instance_id)
            
            db_completed_count = sum(1 for node in db_nodes if node.get('status') == 'completed')
            memory_completed_count = len(context.execution_context.get('completed_nodes', set()))
            
            consistent = db_completed_count == memory_completed_count
            
            return {
                'healthy': consistent,
                'status': 'consistent' if consistent else 'inconsistent',
                'memory_completed_nodes': memory_completed_count,
                'db_completed_nodes': db_completed_count,
                'total_nodes': len(db_nodes),
                'context_size': len(context.node_dependencies),
                'last_activity': context.execution_context.get('last_snapshot_time')
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'status': 'check_failed',
                'error': str(e)
            }


# 全局上下文管理器实例
_global_context_manager: Optional[WorkflowExecutionContextManager] = None

def get_context_manager() -> WorkflowExecutionContextManager:
    """获取全局上下文管理器"""
    global _global_context_manager
    if _global_context_manager is None:
        _global_context_manager = WorkflowExecutionContextManager()
        logger.debug("🌍 初始化全局工作流执行上下文管理器")
    return _global_context_manager