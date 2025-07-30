"""
节点依赖跟踪器
线程安全的节点依赖关系管理，支持依赖检查和数据流管理
"""

import uuid
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from threading import Lock, RLock
from datetime import datetime
from loguru import logger

from ..repositories.base import BaseRepository


class NodeDependencyTracker:
    """线程安全的节点依赖跟踪器"""
    
    def __init__(self, db_connection=None):
        self.db_connection = db_connection
        
        # 依赖关系缓存（线程安全）
        self._dependency_cache: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
        self._downstream_cache: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
        
        # 工作流级别的依赖图缓存
        self._workflow_dependency_graph: Dict[uuid.UUID, Dict[str, Any]] = {}
        
        # 线程安全锁
        self._cache_lock = RLock()
        self._graph_lock = RLock()
        
        # 缓存统计
        self._cache_stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'cache_invalidations': 0,
            'created_at': datetime.utcnow()
        }
        
        logger.info("Initialized NodeDependencyTracker")
    
    async def get_immediate_upstream_nodes(self, 
                                         workflow_base_id: uuid.UUID,
                                         node_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的一阶上游节点（线程安全）"""
        cache_key = (workflow_base_id, node_base_id)
        
        with self._cache_lock:
            # 检查缓存
            if cache_key in self._dependency_cache:
                self._cache_stats['cache_hits'] += 1
                logger.debug(f"Cache hit for upstream nodes of {node_base_id}")
                return self._dependency_cache[cache_key].copy()
            
            self._cache_stats['cache_misses'] += 1
        
        # 缓存未命中，查询数据库
        query = """
        SELECT DISTINCT 
            e.from_node_id as upstream_node_id, 
            n.name as upstream_node_name, 
            n.type as upstream_node_type,
            n.task_description as upstream_description,
            n.node_id as upstream_node_db_id
        FROM edge e
        JOIN node n ON e.from_node_id = n.node_base_id
        WHERE e.to_node_id = %s 
        AND e.workflow_base_id = %s
        ORDER BY n.name
        """
        
        try:
            # 执行查询（这里需要数据库连接）
            result = await self._execute_query(query, [node_base_id, workflow_base_id])
            
            # 缓存结果
            with self._cache_lock:
                self._dependency_cache[cache_key] = result
            
            logger.debug(f"Found {len(result)} immediate upstream nodes for {node_base_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting upstream nodes for {node_base_id}: {e}")
            return []
    
    async def get_immediate_downstream_nodes(self, 
                                           workflow_base_id: uuid.UUID,
                                           node_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的一阶下游节点（线程安全）"""
        cache_key = (workflow_base_id, node_base_id)
        
        with self._cache_lock:
            # 检查缓存
            if cache_key in self._downstream_cache:
                self._cache_stats['cache_hits'] += 1
                logger.debug(f"Cache hit for downstream nodes of {node_base_id}")
                return self._downstream_cache[cache_key].copy()
            
            self._cache_stats['cache_misses'] += 1
        
        # 缓存未命中，查询数据库
        query = """
        SELECT DISTINCT 
            e.to_node_id as downstream_node_id, 
            n.name as downstream_node_name, 
            n.type as downstream_node_type,
            n.task_description as downstream_description,
            n.node_id as downstream_node_db_id
        FROM edge e
        JOIN node n ON e.to_node_id = n.node_base_id
        WHERE e.from_node_id = %s 
        AND e.workflow_base_id = %s
        ORDER BY n.name
        """
        
        try:
            result = await self._execute_query(query, [node_base_id, workflow_base_id])
            
            # 缓存结果
            with self._cache_lock:
                self._downstream_cache[cache_key] = result
            
            logger.debug(f"Found {len(result)} immediate downstream nodes for {node_base_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting downstream nodes for {node_base_id}: {e}")
            return []
    
    async def build_workflow_dependency_graph(self, 
                                            workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """构建完整的工作流依赖图（线程安全）"""
        with self._graph_lock:
            # 检查缓存
            if workflow_base_id in self._workflow_dependency_graph:
                logger.debug(f"Using cached dependency graph for workflow {workflow_base_id}")
                return self._workflow_dependency_graph[workflow_base_id].copy()
        
        try:
            # 获取工作流的所有节点
            nodes_query = """
            SELECT 
                node_base_id, 
                name, 
                type, 
                task_description,
                node_id
            FROM node 
            WHERE workflow_base_id = %s
            ORDER BY name
            """
            
            nodes = await self._execute_query(nodes_query, [workflow_base_id])
            
            # 获取所有边
            edges_query = """
            SELECT 
                from_node_id, 
                to_node_id,
                edge_type,
                edge_data
            FROM edge 
            WHERE workflow_base_id = %s
            """
            
            edges = await self._execute_query(edges_query, [workflow_base_id])
            
            # 构建依赖图
            dependency_graph = {
                'workflow_base_id': str(workflow_base_id),
                'nodes': {str(node['node_base_id']): node for node in nodes},
                'edges': edges,
                'adjacency_list': {},  # node_id -> [downstream_node_ids]
                'reverse_adjacency_list': {},  # node_id -> [upstream_node_ids]
                'start_nodes': [],  # 无上游依赖的节点
                'end_nodes': [],  # 无下游依赖的节点
                'execution_levels': {},  # node_id -> execution_level
                'created_at': datetime.utcnow()
            }
            
            # 构建邻接表
            for node in nodes:
                node_id = str(node['node_base_id'])
                dependency_graph['adjacency_list'][node_id] = []
                dependency_graph['reverse_adjacency_list'][node_id] = []
            
            for edge in edges:
                from_id = str(edge['from_node_id'])
                to_id = str(edge['to_node_id'])
                
                if from_id in dependency_graph['adjacency_list']:
                    dependency_graph['adjacency_list'][from_id].append(to_id)
                
                if to_id in dependency_graph['reverse_adjacency_list']:
                    dependency_graph['reverse_adjacency_list'][to_id].append(from_id)
            
            # 识别起始和结束节点
            for node_id in dependency_graph['nodes'].keys():
                if not dependency_graph['reverse_adjacency_list'][node_id]:
                    dependency_graph['start_nodes'].append(node_id)
                
                if not dependency_graph['adjacency_list'][node_id]:
                    dependency_graph['end_nodes'].append(node_id)
            
            # 计算执行层级
            await self._calculate_execution_levels(dependency_graph)
            
            # 缓存结果
            with self._graph_lock:
                self._workflow_dependency_graph[workflow_base_id] = dependency_graph
            
            logger.info(f"Built dependency graph for workflow {workflow_base_id}: "
                       f"{len(nodes)} nodes, {len(edges)} edges")
            
            return dependency_graph.copy()
            
        except Exception as e:
            logger.error(f"Error building dependency graph for workflow {workflow_base_id}: {e}")
            return {}
    
    async def _calculate_execution_levels(self, dependency_graph: Dict[str, Any]):
        """计算节点的执行层级（拓扑排序）"""
        try:
            # 使用拓扑排序计算执行层级
            in_degree = {}
            
            # 初始化入度
            for node_id in dependency_graph['nodes'].keys():
                in_degree[node_id] = len(dependency_graph['reverse_adjacency_list'][node_id])
            
            # BFS拓扑排序
            queue = []
            level = 0
            
            # 将入度为0的节点加入队列
            for node_id, degree in in_degree.items():
                if degree == 0:
                    queue.append(node_id)
                    dependency_graph['execution_levels'][node_id] = level
            
            while queue:
                next_queue = []
                
                for node_id in queue:
                    # 减少下游节点的入度
                    for downstream_id in dependency_graph['adjacency_list'][node_id]:
                        in_degree[downstream_id] -= 1
                        
                        if in_degree[downstream_id] == 0:
                            next_queue.append(downstream_id)
                            dependency_graph['execution_levels'][downstream_id] = level + 1
                
                queue = next_queue
                level += 1
            
            logger.debug(f"Calculated execution levels: {len(dependency_graph['execution_levels'])} nodes, "
                        f"{level} levels")
            
        except Exception as e:
            logger.error(f"Error calculating execution levels: {e}")
    
    async def validate_workflow_dependencies(self, 
                                           workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """验证工作流的依赖关系是否有效（检查循环依赖等）"""
        try:
            dependency_graph = await self.build_workflow_dependency_graph(workflow_base_id)
            
            if not dependency_graph:
                return {
                    'is_valid': False,
                    'error': 'Failed to build dependency graph'
                }
            
            # 检查是否有环
            cycles = await self._detect_cycles(dependency_graph)
            
            validation_result = {
                'is_valid': len(cycles) == 0,
                'cycles_count': len(cycles),
                'cycles': cycles,
                'workflow_base_id': str(workflow_base_id),
                'total_nodes': len(dependency_graph['nodes']),
                'total_edges': len(dependency_graph['edges']),
                'start_nodes_count': len(dependency_graph['start_nodes']),
                'end_nodes_count': len(dependency_graph['end_nodes']),
                'max_execution_level': max(dependency_graph['execution_levels'].values()) 
                                     if dependency_graph['execution_levels'] else 0
            }
            
            if cycles:
                logger.warning(f"Found {len(cycles)} dependency cycles in workflow {workflow_base_id}")
            else:
                logger.debug(f"Workflow {workflow_base_id} has valid dependencies (no cycles)")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating workflow dependencies: {e}")
            return {
                'is_valid': False,
                'error': str(e),
                'workflow_base_id': str(workflow_base_id)
            }
    
    async def _detect_cycles(self, dependency_graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        """使用DFS检测依赖图中的环"""
        try:
            cycles = []
            visited = set()
            rec_stack = set()
            path = []
            
            def dfs(node_id: str) -> bool:
                visited.add(node_id)
                rec_stack.add(node_id)
                path.append(node_id)
                
                for neighbor in dependency_graph['adjacency_list'].get(node_id, []):
                    if neighbor not in visited:
                        if dfs(neighbor):
                            return True
                    elif neighbor in rec_stack:
                        # 找到环
                        cycle_start = path.index(neighbor)
                        cycle_nodes = path[cycle_start:] + [neighbor]
                        cycles.append({
                            'cycle_nodes': cycle_nodes,
                            'cycle_length': len(cycle_nodes) - 1
                        })
                        return True
                
                path.pop()
                rec_stack.remove(node_id)
                return False
            
            # 对所有未访问的节点执行DFS
            for node_id in dependency_graph['nodes'].keys():
                if node_id not in visited:
                    dfs(node_id)
            
            return cycles
            
        except Exception as e:
            logger.error(f"Error detecting cycles: {e}")
            return []
    
    async def get_workflow_execution_order(self, 
                                         workflow_base_id: uuid.UUID) -> List[List[str]]:
        """获取工作流的执行顺序（按层级分组）"""
        try:
            dependency_graph = await self.build_workflow_dependency_graph(workflow_base_id)
            
            if not dependency_graph or not dependency_graph['execution_levels']:
                return []
            
            # 按层级分组节点
            levels = {}
            for node_id, level in dependency_graph['execution_levels'].items():
                if level not in levels:
                    levels[level] = []
                levels[level].append(node_id)
            
            # 转换为有序列表
            execution_order = []
            for level in sorted(levels.keys()):
                execution_order.append(levels[level])
            
            logger.debug(f"Workflow execution order: {len(execution_order)} levels")
            return execution_order
            
        except Exception as e:
            logger.error(f"Error getting workflow execution order: {e}")
            return []
    
    async def get_nodes_ready_for_execution(self, 
                                          workflow_instance_id: uuid.UUID,
                                          completed_nodes: Set[uuid.UUID]) -> List[Dict[str, Any]]:
        """获取准备执行的节点（所有上游节点都已完成）"""
        try:
            # 获取工作流实例对应的workflow_base_id
            workflow_base_id = await self._get_workflow_base_id(workflow_instance_id)
            if not workflow_base_id:
                return []
            
            dependency_graph = await self.build_workflow_dependency_graph(workflow_base_id)
            if not dependency_graph:
                return []
            
            ready_nodes = []
            
            for node_id, node_info in dependency_graph['nodes'].items():
                node_uuid = uuid.UUID(node_id)
                
                # 跳过已完成的节点
                if node_uuid in completed_nodes:
                    continue
                
                # 检查上游依赖
                upstream_nodes = dependency_graph['reverse_adjacency_list'][node_id]
                
                if not upstream_nodes:
                    # 无上游依赖，可以执行
                    ready_nodes.append({
                        'node_base_id': node_uuid,
                        'node_name': node_info['name'],
                        'node_type': node_info['type'],
                        'required_upstream': 0,
                        'completed_upstream': 0
                    })
                else:
                    # 检查上游节点是否都已完成
                    upstream_completed = sum(1 for up_id in upstream_nodes 
                                           if uuid.UUID(up_id) in completed_nodes)
                    
                    if upstream_completed == len(upstream_nodes):
                        ready_nodes.append({
                            'node_base_id': node_uuid,
                            'node_name': node_info['name'],
                            'node_type': node_info['type'],
                            'required_upstream': len(upstream_nodes),
                            'completed_upstream': upstream_completed
                        })
            
            logger.debug(f"Found {len(ready_nodes)} nodes ready for execution")
            return ready_nodes
            
        except Exception as e:
            logger.error(f"Error getting nodes ready for execution: {e}")
            return []
    
    async def clear_cache(self, workflow_base_id: Optional[uuid.UUID] = None):
        """清理缓存（线程安全）"""
        with self._cache_lock:
            with self._graph_lock:
                if workflow_base_id:
                    # 清理特定工作流的缓存
                    keys_to_remove = [key for key in self._dependency_cache.keys() 
                                    if key[0] == workflow_base_id]
                    
                    for key in keys_to_remove:
                        del self._dependency_cache[key]
                    
                    downstream_keys_to_remove = [key for key in self._downstream_cache.keys() 
                                               if key[0] == workflow_base_id]
                    
                    for key in downstream_keys_to_remove:
                        del self._downstream_cache[key]
                    
                    if workflow_base_id in self._workflow_dependency_graph:
                        del self._workflow_dependency_graph[workflow_base_id]
                    
                    self._cache_stats['cache_invalidations'] += len(keys_to_remove) + len(downstream_keys_to_remove) + 1
                    
                    logger.debug(f"Cleared cache for workflow {workflow_base_id}")
                else:
                    # 清理所有缓存
                    invalidated_count = (len(self._dependency_cache) + 
                                       len(self._downstream_cache) + 
                                       len(self._workflow_dependency_graph))
                    
                    self._dependency_cache.clear()
                    self._downstream_cache.clear()
                    self._workflow_dependency_graph.clear()
                    
                    self._cache_stats['cache_invalidations'] += invalidated_count
                    
                    logger.debug("Cleared all dependency caches")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._cache_lock:
            return {
                **self._cache_stats,
                'dependency_cache_size': len(self._dependency_cache),
                'downstream_cache_size': len(self._downstream_cache),
                'workflow_graph_cache_size': len(self._workflow_dependency_graph),
                'cache_hit_rate': (self._cache_stats['cache_hits'] / 
                                 max(1, self._cache_stats['cache_hits'] + self._cache_stats['cache_misses'])) * 100
            }
    
    async def _execute_query(self, query: str, params: List[Any]) -> List[Dict[str, Any]]:
        """执行数据库查询（抽象方法，需要具体实现）"""
        # 这里需要根据实际的数据库连接实现
        # 暂时返回空结果
        logger.warning("Database query execution not implemented")
        return []
    
    async def _get_workflow_base_id(self, workflow_instance_id: uuid.UUID) -> Optional[uuid.UUID]:
        """根据工作流实例ID获取workflow_base_id（需要具体实现）"""
        # 这里需要根据实际的数据库连接实现
        logger.warning("Workflow base ID lookup not implemented")
        return None
    
    def __repr__(self) -> str:
        cache_size = len(self._dependency_cache) + len(self._downstream_cache)
        return f"NodeDependencyTracker(cache_size={cache_size}, graphs={len(self._workflow_dependency_graph)})"