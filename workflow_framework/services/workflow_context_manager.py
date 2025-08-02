"""
工作流上下文管理器
统一管理整个工作流的执行上下文和数据流
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Set, Optional
import asyncio
import logging
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
        # 处理字典时，确保键和值都被序列化
        result = {}
        for key, value in obj.items():
            # 序列化键（如果键是UUID）
            serialized_key = str(key) if isinstance(key, uuid.UUID) else key
            # 序列化值
            serialized_value = _serialize_for_json(value)
            result[serialized_key] = serialized_value
        return result
    elif isinstance(obj, (list, tuple, set)):
        return [_serialize_for_json(item) for item in obj]
    else:
        return obj


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
        
        # 🔒 异步锁管理：为每个工作流实例维护独立的锁
        self._workflow_locks: Dict[uuid.UUID, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()  # 保护锁字典本身的锁
    
    async def _get_workflow_lock(self, workflow_instance_id: uuid.UUID) -> asyncio.Lock:
        """获取或创建工作流实例的异步锁"""
        async with self._locks_lock:
            if workflow_instance_id not in self._workflow_locks:
                self._workflow_locks[workflow_instance_id] = asyncio.Lock()
            return self._workflow_locks[workflow_instance_id]
    
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
                                       node_id: uuid.UUID,  # 改为node_id参数
                                       workflow_instance_id: uuid.UUID, 
                                       upstream_nodes: List[uuid.UUID]):
        """注册节点的一阶依赖关系"""
        self.node_dependencies[node_instance_id] = {
            'node_id': node_id,  # 存储node_id而不是node_base_id
            'workflow_instance_id': workflow_instance_id,
            'upstream_nodes': upstream_nodes,
            'completed_upstream': set(),
            'ready_to_execute': len(upstream_nodes) == 0,  # START节点无依赖
            'dependency_count': len(upstream_nodes)
        }
        
        # 初始化节点状态
        self.node_completion_status[node_instance_id] = 'PENDING'
        
        logger.info(f"📋 [依赖注册] 节点实例 {node_instance_id}:")
        logger.info(f"  - node_id: {node_id}")
        logger.info(f"  - 上游依赖数量: {len(upstream_nodes)}")
        logger.info(f"  - 上游节点列表: {upstream_nodes}")
        logger.info(f"  - 初始状态: {'Ready' if len(upstream_nodes) == 0 else 'Waiting'}")
        
        # 如果是START节点（无依赖），立即标记为ready
        if len(upstream_nodes) == 0:
            logger.info(f"🚀 [依赖注册] START节点 {node_instance_id} 无依赖，可立即执行")
    
    def print_dependency_summary(self, workflow_instance_id: uuid.UUID):
        """打印依赖关系总结"""
        logger.info(f"📊 [依赖总结] 工作流 {workflow_instance_id} 的依赖关系:")
        
        workflow_nodes = [(nid, deps) for nid, deps in self.node_dependencies.items() 
                         if deps['workflow_instance_id'] == workflow_instance_id]
        
        logger.info(f"  - 节点总数: {len(workflow_nodes)}")
        
        for i, (node_instance_id, deps) in enumerate(workflow_nodes, 1):
            node_id = deps.get('node_id', 'Unknown')
            upstream_count = len(deps['upstream_nodes'])
            completed_count = len(deps['completed_upstream'])
            status = 'Ready' if deps['ready_to_execute'] else 'Waiting'
            
            logger.info(f"  节点 {i}: {node_instance_id}")
            logger.info(f"    - node_id: {node_id}")
            logger.info(f"    - 依赖状态: {status} ({completed_count}/{upstream_count})")
            logger.info(f"    - 上游节点: {deps['upstream_nodes']}")
            logger.info(f"    - 已完成上游: {list(deps['completed_upstream'])}")
        
        logger.info(f"📊 [依赖总结] 完成")
    
    async def mark_node_completed(self, 
                                workflow_instance_id: uuid.UUID,
                                node_id: uuid.UUID,  # 改为node_id参数
                                node_instance_id: uuid.UUID,
                                output_data: Dict[str, Any]):
        """标记节点完成并更新上下文（线程安全）"""
        # 🔒 获取工作流锁，确保原子性操作
        workflow_lock = await self._get_workflow_lock(workflow_instance_id)
        
        async with workflow_lock:
            if workflow_instance_id not in self.workflow_contexts:
                logger.warning(f"⚠️ [节点完成] 工作流上下文不存在 {workflow_instance_id}，可能已被清理。节点 {node_id} 仍然标记为完成。")
                # 即使上下文不存在，也更新节点完成状态
                self.node_completion_status[node_instance_id] = 'COMPLETED'
                return
            
            # 检查节点是否已经完成，避免重复处理
            context = self.workflow_contexts[workflow_instance_id]
            already_completed = node_id in context['completed_nodes']
            if already_completed:
                logger.info(f"⚠️ [节点完成] 节点 {node_id} 已经标记为完成，但仍检查工作流完成状态")
                # 即使节点已完成，也要检查工作流是否全部完成
                should_check_completion = True
            else:
                logger.info(f"🎉 [节点完成] 节点 {node_id} 在工作流 {workflow_instance_id} 中完成")
                
                # 更新工作流上下文
                context['node_outputs'][node_id] = output_data
                context['execution_path'].append(str(node_id))  # 转换为字符串避免UUID序列化问题
                context['completed_nodes'].add(node_id)
                
                # 从正在执行的节点中移除
                if node_id in context['current_executing_nodes']:
                    context['current_executing_nodes'].remove(node_id)
                
                # 更新完成状态
                self.node_completion_status[node_instance_id] = 'COMPLETED'
                
                logger.info(f"📊 [节点完成] 上下文更新完成:")
                logger.info(f"  - 已完成节点数: {len(context['completed_nodes'])}")
                logger.info(f"  - 执行路径: {context['execution_path']}")
                
                # 检查并触发下游节点
                logger.info(f"🔍 [节点完成] 开始检查下游节点触发...")
                should_check_completion = False
            
            # 打印当前依赖关系状态
            self.print_dependency_summary(workflow_instance_id)
        
        # 🔓 在锁外执行下游检查和工作流完成检查，避免死锁
        try:
            if not already_completed:
                # 只有新完成的节点才检查并触发下游节点
                await self._check_and_trigger_downstream_nodes(
                    workflow_instance_id, node_id
                )
                
                # 延迟检查工作流完成状态，给下游节点一些时间启动
                await asyncio.sleep(0.1)
            else:
                logger.info(f"🔍 [节点完成] 节点已完成，跳过下游检查，直接检查工作流完成状态")
            
            # 无论如何都要检查工作流是否全部完成
            await self._check_workflow_completion(workflow_instance_id)
        except Exception as e:
            logger.error(f"❌ [节点完成] 下游检查失败: {e}")
            # 即使下游检查失败，节点完成状态也已经正确更新
    
    async def mark_node_failed(self,
                             workflow_instance_id: uuid.UUID,
                             node_id: uuid.UUID,  # 改为node_id参数
                             node_instance_id: uuid.UUID,
                             error_info: Dict[str, Any]):
        """标记节点失败（线程安全）"""
        # 🔒 获取工作流锁，确保原子性操作
        workflow_lock = await self._get_workflow_lock(workflow_instance_id)
        
        async with workflow_lock:
            if workflow_instance_id not in self.workflow_contexts:
                logger.warning(f"⚠️ [节点失败] 工作流上下文不存在 {workflow_instance_id}，节点 {node_id} 仍标记为失败")
                self.node_completion_status[node_instance_id] = 'FAILED'
                return
            
            logger.error(f"❌ [节点失败] 节点 {node_id} 在工作流 {workflow_instance_id} 中失败: {error_info}")
            
            context = self.workflow_contexts[workflow_instance_id]
            context['failed_nodes'].add(node_id)
            
            # 从正在执行的节点中移除
            if node_id in context['current_executing_nodes']:
                context['current_executing_nodes'].remove(node_id)
            
            # 更新失败状态
            self.node_completion_status[node_instance_id] = 'FAILED'
    
    async def mark_node_executing(self,
                                workflow_instance_id: uuid.UUID,
                                node_id: uuid.UUID,  # 改为node_id参数
                                node_instance_id: uuid.UUID):
        """标记节点开始执行（线程安全）"""
        # 🔒 获取工作流锁，确保原子性操作
        workflow_lock = await self._get_workflow_lock(workflow_instance_id)
        
        async with workflow_lock:
            if workflow_instance_id not in self.workflow_contexts:
                logger.warning(f"⚠️ [节点执行] 工作流上下文不存在 {workflow_instance_id}，节点 {node_id} 仍标记为执行中")
                self.node_completion_status[node_instance_id] = 'EXECUTING'
                return
            
            logger.info(f"⚡ [节点执行] 节点 {node_id} 在工作流 {workflow_instance_id} 中开始执行")
            
            context = self.workflow_contexts[workflow_instance_id]
            context['current_executing_nodes'].add(node_id)
            
            self.node_completion_status[node_instance_id] = 'EXECUTING'
    
    async def _check_and_trigger_downstream_nodes(self, 
                                                workflow_instance_id: uuid.UUID,
                                                completed_node_id: uuid.UUID):
        """检查并触发下游节点"""
        logger.info(f"🔍 [下游检查] 检查节点 {completed_node_id} 的下游依赖...")
        logger.info(f"  - 工作流实例: {workflow_instance_id}")
        logger.info(f"  - 已完成的节点ID: {completed_node_id}")
        logger.info(f"  - 已完成节点ID类型: {type(completed_node_id)}")
        
        triggered_nodes = []
        checked_nodes = 0
        
        # 遍历所有节点依赖，找到以当前节点为上游的节点
        logger.info(f"🔍 [下游检查] 遍历所有已注册的节点依赖 (总数: {len(self.node_dependencies)}):")
        for node_instance_id, deps in self.node_dependencies.items():
            checked_nodes += 1
            logger.info(f"  检查节点 {checked_nodes}/{len(self.node_dependencies)}: {node_instance_id}")
            logger.info(f"    - 工作流匹配: {deps['workflow_instance_id'] == workflow_instance_id}")
            logger.info(f"    - 上游节点列表: {deps['upstream_nodes']}")
            logger.info(f"    - 上游节点类型: {[type(x) for x in deps['upstream_nodes']]}")
            logger.info(f"    - 完成节点在上游中: {completed_node_id in deps['upstream_nodes']}")
            
            # 详细检查每个上游节点
            for i, upstream_node in enumerate(deps['upstream_nodes']):
                is_match = upstream_node == completed_node_id
                logger.info(f"      上游节点{i+1}: {upstream_node} == {completed_node_id} ? {is_match}")
            
            if (deps['workflow_instance_id'] == workflow_instance_id and 
                completed_node_id in deps['upstream_nodes']):
                
                logger.info(f"  ✅ [下游检查] 找到下游节点: {node_instance_id}")
                
                # 标记该上游节点已完成
                deps['completed_upstream'].add(completed_node_id)
                logger.info(f"    - 已完成上游: {deps['completed_upstream']}")
                logger.info(f"    - 需要上游: {deps['upstream_nodes']}")
                logger.info(f"    - 完成进度: {len(deps['completed_upstream'])}/{len(deps['upstream_nodes'])}")
                
                # 检查是否所有上游节点都已完成
                if len(deps['completed_upstream']) == len(deps['upstream_nodes']):
                    logger.info(f"  ✅ [下游检查] 所有上游节点已完成，设置ready_to_execute=True")
                    deps['ready_to_execute'] = True
                    
                    # 添加到待触发队列
                    self.pending_triggers[workflow_instance_id].add(node_instance_id)
                    triggered_nodes.append(node_instance_id)
                    
                    logger.info(f"🚀 [下游检查] 节点 {deps['node_id']} 准备执行 - 所有上游依赖已完成")
                    logger.info(f"    - ready_to_execute标志已设置为: {deps['ready_to_execute']}")
                else:
                    logger.info(f"⏳ [下游检查] 节点 {deps['node_id']} 仍需等待更多上游节点完成")
                    logger.info(f"    - 需要: {len(deps['upstream_nodes'])} 个上游节点")
                    logger.info(f"    - 已完成: {len(deps['completed_upstream'])} 个上游节点")
        
        logger.info(f"📊 [下游检查] 检查完成:")
        logger.info(f"  - 检查的节点数: {checked_nodes}")
        logger.info(f"  - 触发的节点数: {len(triggered_nodes)}")
        logger.info(f"  - 触发的节点列表: {triggered_nodes}")
        
        # 通知回调函数有新的节点准备执行
        if triggered_nodes:
            logger.info(f"🔔 [下游检查] 通知回调函数有 {len(triggered_nodes)} 个节点准备执行")
            await self._notify_completion_callbacks(workflow_instance_id, triggered_nodes)
        else:
            logger.info(f"❌ [下游检查] 没有找到可触发的下游节点")
    
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
    
    async def get_task_context_data(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取任务执行所需的完整上下文数据（兼容ExecutionService格式）"""
        try:
            context_data = {}
            
            # 1. 获取工作流信息
            if workflow_instance_id in self.workflow_contexts:
                workflow_context = self.workflow_contexts[workflow_instance_id]
                
                # 延迟导入避免循环依赖
                from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
                workflow_repo = WorkflowInstanceRepository()
                workflow_instance = await workflow_repo.get_instance_by_id(workflow_instance_id)
                
                if workflow_instance:
                    created_at = workflow_instance.get('created_at')
                    context_data['workflow'] = {
                        'name': workflow_instance.get('workflow_name'),
                        'instance_name': workflow_instance.get('instance_name'), 
                        'status': workflow_instance.get('status'),
                        'input_data': workflow_instance.get('input_data', {}),
                        'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)
                    }
            
            # 2. 获取上游节点输出数据
            if node_instance_id in self.node_dependencies:
                deps = self.node_dependencies[node_instance_id] 
                upstream_nodes = deps['upstream_nodes']
                workflow_context = self.workflow_contexts.get(workflow_instance_id, {})
                node_outputs = workflow_context.get('node_outputs', {})
                
                logger.info(f"🔍 [上下文收集] 节点 {node_instance_id} 的上游依赖分析:")
                logger.info(f"  - 上游节点数量: {len(upstream_nodes)}")
                logger.info(f"  - 上游节点ID列表: {upstream_nodes}")
                logger.info(f"  - 工作流已有输出的节点: {list(node_outputs.keys())}")
                
                # 从内存中的节点输出构建上游输出列表
                upstream_outputs = []
                for upstream_node_id in upstream_nodes:
                    if upstream_node_id in node_outputs:
                        # 获取节点名称（需要查询数据库获取节点信息）
                        node_name = await self._get_node_name_by_id(upstream_node_id)
                        output_data = node_outputs[upstream_node_id]
                        
                        logger.info(f"  ✅ 找到上游节点输出: {node_name} ({upstream_node_id})")
                        logger.info(f"     输出数据: {str(output_data)[:200]}...")
                        
                        upstream_outputs.append({
                            'node_name': node_name or f'Node_{str(upstream_node_id)[:8]}',
                            'node_instance_id': str(upstream_node_id),
                            'output_data': output_data,
                            'completed_at': None,  # 暂时不提供完成时间
                            'task_count': 1  # 简化处理
                        })
                    else:
                        logger.warning(f"  ⚠️ 上游节点 {upstream_node_id} 的输出数据未找到")
                
                context_data['upstream_outputs'] = upstream_outputs
                logger.info(f"  📋 最终上游输出数量: {len(upstream_outputs)}")
            else:
                logger.warning(f"⚠️ [上下文收集] 节点 {node_instance_id} 不在依赖字典中")
                context_data['upstream_outputs'] = []
            
            # 3. 获取当前节点信息
            if node_instance_id in self.node_dependencies:
                current_node_name = await self._get_node_name_by_instance_id(node_instance_id)
                current_node_type = await self._get_node_type_by_instance_id(node_instance_id)
                
                context_data['current_node'] = {
                    'name': current_node_name or 'Unknown',
                    'type': current_node_type or 'unknown',
                    'description': None,
                    'input_data': {},
                    'status': 'pending'
                }
            
            # 4. 添加时间戳
            from datetime import datetime
            context_data['context_generated_at'] = datetime.utcnow().isoformat()
            
            logger.info(f"WorkflowContextManager为节点 {node_instance_id} 收集上下文数据: {len(context_data)} 个顶级字段")
            return context_data
            
        except Exception as e:
            logger.error(f"WorkflowContextManager收集任务上下文数据失败: {e}")
            return {}
    
    async def _get_node_name_by_id(self, node_id: uuid.UUID) -> str:
        """根据node_id获取节点名称"""
        try:
            # 延迟导入避免循环依赖
            from ..repositories.node.node_repository import NodeRepository
            node_repo = NodeRepository()
            
            # 查询节点信息
            query = "SELECT name FROM node WHERE node_id = $1"
            result = await node_repo.db.fetch_one(query, node_id)
            return result['name'] if result else None
        except Exception as e:
            logger.error(f"获取节点名称失败: {e}")
            return None
    
    async def _get_node_name_by_instance_id(self, node_instance_id: uuid.UUID) -> str:
        """根据node_instance_id获取节点名称"""
        try:
            # 延迟导入避免循环依赖
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            
            query = """
            SELECT n.name
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id  
            WHERE ni.node_instance_id = $1
            """
            result = await node_repo.db.fetch_one(query, node_instance_id)
            return result['name'] if result else None
        except Exception as e:
            logger.error(f"获取节点实例名称失败: {e}")
            return None
    
    async def _get_node_type_by_instance_id(self, node_instance_id: uuid.UUID) -> str:
        """根据node_instance_id获取节点类型"""
        try:
            # 延迟导入避免循环依赖
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            
            query = """
            SELECT n.type
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.node_instance_id = $1
            """
            result = await node_repo.db.fetch_one(query, node_instance_id)
            return result['type'] if result else None
        except Exception as e:
            logger.error(f"获取节点实例类型失败: {e}")
            return None
    
    async def get_workflow_status(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取工作流整体状态"""
        if workflow_instance_id not in self.workflow_contexts:
            return {'status': 'NOT_FOUND'}
        
        context = self.workflow_contexts[workflow_instance_id]
        
        # 统计节点状态 - 只统计当前工作流的节点
        workflow_nodes = [nid for nid, deps in self.node_dependencies.items() 
                         if deps['workflow_instance_id'] == workflow_instance_id]
        total_nodes = len(workflow_nodes)
        completed_nodes = len(context['completed_nodes'])
        failed_nodes = len(context['failed_nodes'])
        executing_nodes = len(context['current_executing_nodes'])
        pending_nodes = total_nodes - completed_nodes - failed_nodes - executing_nodes
        
        # 🔍 调试：打印详细的节点信息
        logger.info(f"🔍 [状态调试] 工作流 {workflow_instance_id} 节点统计:")
        logger.info(f"   - 注册的依赖节点数: {len(self.node_dependencies)}")
        logger.info(f"   - 当前工作流节点数: {total_nodes}")
        logger.info(f"   - 工作流节点IDs: {workflow_nodes}")
        logger.info(f"   - 已完成节点: {list(context['completed_nodes'])}")
        logger.info(f"   - 执行中节点: {list(context['current_executing_nodes'])}")
        logger.info(f"   - 失败节点: {list(context['failed_nodes'])}")
        
        # 判断工作流整体状态
        if failed_nodes > 0:
            overall_status = 'FAILED'
        elif completed_nodes == total_nodes and total_nodes > 0:
            # 额外验证：检查数据库中的实际节点状态，防止误判
            overall_status = await self._verify_workflow_completion(workflow_instance_id, total_nodes, completed_nodes)
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
    
    async def _verify_workflow_completion(self, workflow_instance_id: uuid.UUID, 
                                        expected_total: int, context_completed: int) -> str:
        """验证工作流完成状态，通过数据库核实"""
        try:
            logger.info(f"🔍 [完成验证] 验证工作流 {workflow_instance_id} 完成状态:")
            logger.info(f"   - 预期总节点数: {expected_total}")
            logger.info(f"   - 上下文已完成: {context_completed}")
            
            # 从数据库查询实际的节点状态
            from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            
            # 查询工作流的所有节点实例
            query = """
            SELECT ni.node_instance_id, ni.status, ni.node_instance_name as node_name
            FROM node_instance ni
            WHERE ni.workflow_instance_id = $1 AND ni.is_deleted = FALSE
            ORDER BY ni.created_at
            """
            
            db_nodes = await node_repo.db.fetch_all(query, workflow_instance_id)
            
            logger.info(f"   - 数据库实际节点数: {len(db_nodes)}")
            
            # 统计数据库中的节点状态
            db_completed = 0
            db_pending = 0
            db_running = 0
            
            for node in db_nodes:
                status = node['status']
                logger.info(f"     - {node.get('node_name', 'Unknown')}: {status}")
                
                if status == 'completed':
                    db_completed += 1
                elif status in ['pending', 'assigned']:
                    db_pending += 1
                elif status in ['running', 'in_progress']:
                    db_running += 1
            
            logger.info(f"   - 数据库统计: 完成={db_completed}, 待处理={db_pending}, 执行中={db_running}")
            
            # 判断是否真正完成
            if len(db_nodes) != expected_total:
                logger.warning(f"⚠️ [完成验证] 节点数量不匹配: 预期{expected_total}, 实际{len(db_nodes)}")
                return 'RUNNING'  # 节点数量不匹配，继续运行
            
            if db_completed == len(db_nodes) and len(db_nodes) > 0:
                logger.info(f"✅ [完成验证] 工作流确实已完成: {db_completed}/{len(db_nodes)} 节点完成")
                return 'COMPLETED'
            else:
                logger.info(f"⏳ [完成验证] 工作流仍在运行: {db_completed}/{len(db_nodes)} 节点完成, {db_pending} 待处理, {db_running} 执行中")
                return 'RUNNING'
                
        except Exception as e:
            logger.error(f"❌ [完成验证] 验证失败: {e}")
            # 验证失败时保守处理，继续运行
            return 'RUNNING'
    
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
    
    
    def get_node_dependency_info(self, node_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点的依赖信息"""
        return self.node_dependencies.get(node_instance_id)
    
    def is_node_ready_to_execute(self, node_instance_id: uuid.UUID) -> bool:
        """检查节点是否准备好执行"""
        deps = self.node_dependencies.get(node_instance_id)
        
        logger.info(f"🔍 [就绪检查] 检查节点 {node_instance_id} 是否准备执行:")
        if deps is None:
            logger.info(f"  ❌ 节点依赖信息不存在")
            return False
        
        ready_flag = deps.get('ready_to_execute', False)
        upstream_nodes = deps.get('upstream_nodes', [])
        completed_upstream = deps.get('completed_upstream', set())
        
        logger.info(f"  - 上游节点数: {len(upstream_nodes)}")
        logger.info(f"  - 已完成上游: {len(completed_upstream)}")
        logger.info(f"  - ready_to_execute标志: {ready_flag}")
        logger.info(f"  - 上游节点列表: {upstream_nodes}")
        logger.info(f"  - 已完成列表: {list(completed_upstream)}")
        
        result = deps is not None and ready_flag
        logger.info(f"  ➡️ 最终结果: {result}")
        return result
    
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
            logger.info(f"   - 待处理节点: {status_info.get('pending_nodes', 0)}")
            
            # 显示详细的节点状态
            if workflow_instance_id in self.workflow_contexts:
                context = self.workflow_contexts[workflow_instance_id]
                logger.info(f"   - 已完成节点列表: {list(context['completed_nodes'])}")
                logger.info(f"   - 执行中节点列表: {list(context['current_executing_nodes'])}")
                logger.info(f"   - 失败节点列表: {list(context['failed_nodes'])}")
            
            # 如果工作流已完成或失败，更新数据库状态
            if current_status in ['COMPLETED', 'FAILED']:
                logger.info(f"🎯 [工作流状态检查] 工作流 {workflow_instance_id} 需要更新状态为: {current_status}")
                
                # 延迟导入工作流实例仓库避免循环依赖
                from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
                workflow_repo = WorkflowInstanceRepository()
                
                # 准备输出数据（序列化UUID等对象）
                context = self.workflow_contexts[workflow_instance_id]
                raw_output_data = {
                    'completion_time': datetime.utcnow().isoformat(),
                    'node_outputs': context.get('node_outputs', {}),
                    'execution_path': context.get('execution_path', []),
                    'total_nodes': status_info.get('total_nodes', 0),
                    'completed_nodes': status_info.get('completed_nodes', 0),
                    'failed_nodes': status_info.get('failed_nodes', 0)
                }
                
                # 序列化UUID对象为字符串
                output_data = _serialize_for_json(raw_output_data)
                
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
                
                # 🕒 延迟清理工作流上下文，等待异步任务完成
                # 对于COMPLETED状态，可以立即清理；对于FAILED状态，需要延迟清理等待异步任务完成
                if current_status == 'COMPLETED':
                    await self.cleanup_workflow_context(workflow_instance_id)
                else:
                    await self._delayed_cleanup_workflow_context(workflow_instance_id)
                
            else:
                logger.info(f"⏳ [工作流状态检查] 工作流 {workflow_instance_id} 仍在运行中")
                
        except Exception as e:
            logger.error(f"❌ 检查工作流完成状态失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    async def _delayed_cleanup_workflow_context(self, workflow_instance_id: uuid.UUID, delay_seconds: int = 3):
        """延迟清理工作流上下文，等待异步任务完成"""
        logger.info(f"🕒 [延迟清理] 将在 {delay_seconds} 秒后清理工作流上下文 {workflow_instance_id}")
        
        # 较短的延迟，避免阻塞正常操作
        await asyncio.sleep(delay_seconds)
        
        # 智能检查：如果还有未完成的节点监听器，再等待一次
        max_retries = 2
        for attempt in range(max_retries):
            if workflow_instance_id in self.workflow_contexts:
                context = self.workflow_contexts[workflow_instance_id]
                executing_nodes = context.get('current_executing_nodes', set())
                
                if executing_nodes and attempt < max_retries - 1:
                    logger.warning(f"⚠️ [延迟清理] 仍有节点在执行: {executing_nodes}，再等待 {delay_seconds} 秒 (尝试 {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay_seconds)
                    continue
                elif executing_nodes:
                    logger.warning(f"⚠️ [延迟清理] 强制清理，忽略仍在执行的节点: {executing_nodes}")
                break
            else:
                logger.info(f"📋 [延迟清理] 工作流上下文已被清理")
                return
        
        # 执行清理
        await self.cleanup_workflow_context(workflow_instance_id)
        logger.info(f"✅ [延迟清理] 工作流上下文 {workflow_instance_id} 清理完成")
    
    async def cleanup_workflow_context(self, workflow_instance_id: uuid.UUID):
        """清理工作流上下文（线程安全）"""
        try:
            # 🔒 使用锁确保清理过程的原子性
            workflow_lock = await self._get_workflow_lock(workflow_instance_id)
            
            async with workflow_lock:
                # 删除工作流上下文
                if workflow_instance_id in self.workflow_contexts:
                    del self.workflow_contexts[workflow_instance_id]
                
                # 删除待触发节点队列
                if workflow_instance_id in self.pending_triggers:
                    del self.pending_triggers[workflow_instance_id]
                
                # 删除相关的节点依赖信息
                to_remove = []
                for node_instance_id, deps in self.node_dependencies.items():
                    if deps['workflow_instance_id'] == workflow_instance_id:
                        to_remove.append(node_instance_id)
                
                for node_instance_id in to_remove:
                    del self.node_dependencies[node_instance_id]
                    if node_instance_id in self.node_completion_status:
                        del self.node_completion_status[node_instance_id]
            
            # 🔓 在锁外清理锁本身，避免死锁
            async with self._locks_lock:
                if workflow_instance_id in self._workflow_locks:
                    del self._workflow_locks[workflow_instance_id]
            
            logger.info(f"Cleaned up workflow context for {workflow_instance_id}")
            
        except Exception as e:
            logger.error(f"❌ 清理工作流上下文失败: {e}")
            # 即使清理失败，也尝试强制清理关键数据
            try:
                if workflow_instance_id in self.workflow_contexts:
                    del self.workflow_contexts[workflow_instance_id]
                logger.warning(f"⚠️ 强制清理工作流上下文: {workflow_instance_id}")
            except:
                pass