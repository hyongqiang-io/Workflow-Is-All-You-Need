"""
节点依赖管理器
管理节点间的一阶依赖关系检查和数据流
"""

import uuid
from typing import Dict, List, Any, Optional, Tuple
import logging
from ..repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class NodeDependencyManager(BaseRepository):
    """节点依赖管理器"""
    
    def __init__(self, db_connection):
        super().__init__(db_connection)
        # 缓存依赖关系以提高性能
        self._dependency_cache: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
        self._downstream_cache: Dict[uuid.UUID, List[Dict[str, Any]]] = {}
    
    async def get_immediate_upstream_nodes(self, 
                                         workflow_base_id: uuid.UUID,
                                         node_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的一阶上游节点"""
        cache_key = node_base_id
        
        # 检查缓存
        if cache_key in self._dependency_cache:
            return self._dependency_cache[cache_key]
        
        query = """
        SELECT DISTINCT 
            e.from_node_id as upstream_node_id, 
            n.name as upstream_node_name, 
            n.type as upstream_node_type,
            n.task_description as upstream_description
        FROM edge e
        JOIN node n ON e.from_node_id = n.node_base_id
        WHERE e.to_node_id = %s 
        AND e.workflow_base_id = %s
        ORDER BY n.name
        """
        
        try:
            result = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            
            # 缓存结果
            self._dependency_cache[cache_key] = result
            
            logger.debug(f"Found {len(result)} immediate upstream nodes for {node_base_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting upstream nodes for {node_base_id}: {e}")
            return []
    
    async def get_immediate_downstream_nodes(self, 
                                           workflow_base_id: uuid.UUID,
                                           node_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的一阶下游节点"""
        cache_key = node_base_id
        
        # 检查缓存
        if cache_key in self._downstream_cache:
            return self._downstream_cache[cache_key]
        
        query = """
        SELECT DISTINCT 
            e.to_node_id as downstream_node_id, 
            n.name as downstream_node_name, 
            n.type as downstream_node_type,
            n.task_description as downstream_description
        FROM edge e
        JOIN node n ON e.to_node_id = n.node_base_id
        WHERE e.from_node_id = %s 
        AND e.workflow_base_id = %s
        ORDER BY n.name
        """
        
        try:
            result = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            
            # 缓存结果
            self._downstream_cache[cache_key] = result
            
            logger.debug(f"Found {len(result)} immediate downstream nodes for {node_base_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting downstream nodes for {node_base_id}: {e}")
            return []
    
    async def get_workflow_node_instances_with_dependencies(self, 
                                                          workflow_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流中所有节点实例及其依赖信息"""
        query = """
        SELECT 
            ni.node_instance_id,
            n.node_base_id,
            ni.workflow_instance_id,
            n.name as node_name,
            n.type as node_type,
            n.task_description as description,
            ni.status as node_status,
            ni.input_data,
            ni.output_data,
            ni.created_at,
            ni.updated_at
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = %s
        ORDER BY ni.created_at
        """
        
        try:
            result = await self.db.fetch_all(query, workflow_instance_id)
            logger.debug(f"Found {len(result)} node instances for workflow {workflow_instance_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting node instances for workflow {workflow_instance_id}: {e}")
            return []
    
    async def check_upstream_completion_status(self, 
                                             workflow_instance_id: uuid.UUID,
                                             upstream_node_ids: List[uuid.UUID]) -> Dict[str, Any]:
        """检查一阶上游节点的完成状态"""
        if not upstream_node_ids:
            return {
                'all_completed': True,
                'completed_count': 0,  
                'total_count': 0,
                'completed_nodes': [],
                'pending_nodes': []
            }
        
        # 将UUID列表转换为字符串格式用于查询
        upstream_ids_str = [str(node_id) for node_id in upstream_node_ids]
        
        query = """
        SELECT 
            n.node_base_id,
            ni.node_instance_id,
            ni.status,
            n.name as node_name,
            ni.output_data,
            ni.completed_at
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = %s
        AND n.node_base_id::text = ANY(%s)
        ORDER BY ni.completed_at NULLS LAST
        """
        
        try:
            result = await self.db.fetch_all(query, workflow_instance_id, upstream_ids_str)
            
            completed_nodes = []
            pending_nodes = []
            
            for node in result:
                if node['status'] == 'COMPLETED':
                    completed_nodes.append(node)
                else:
                    pending_nodes.append(node)
            
            all_completed = len(completed_nodes) == len(upstream_node_ids)
            
            status_info = {
                'all_completed': all_completed,
                'completed_count': len(completed_nodes),
                'total_count': len(upstream_node_ids),
                'completed_nodes': completed_nodes,
                'pending_nodes': pending_nodes
            }
            
            logger.debug(f"Upstream completion check: {len(completed_nodes)}/{len(upstream_node_ids)} completed")
            return status_info
            
        except Exception as e:
            logger.error(f"Error checking upstream completion: {e}")
            return {
                'all_completed': False,
                'completed_count': 0,
                'total_count': len(upstream_node_ids),
                'completed_nodes': [],
                'pending_nodes': [],
                'error': str(e)
            }
    
    async def get_upstream_output_data(self, 
                                     workflow_instance_id: uuid.UUID,
                                     upstream_node_ids: List[uuid.UUID]) -> Dict[str, Any]:
        """获取一阶上游节点的输出数据"""
        if not upstream_node_ids:
            return {}
        
        upstream_ids_str = [str(node_id) for node_id in upstream_node_ids]
        
        query = """
        SELECT 
            n.node_base_id,
            ni.node_instance_id,
            ni.output_data,
            n.name as node_name,
            ni.completed_at
        FROM node_instance ni
        JOIN node n ON ni.node_id = n.node_id
        WHERE ni.workflow_instance_id = %s
        AND n.node_base_id::text = ANY(%s)
        AND ni.status = 'COMPLETED'
        AND ni.output_data IS NOT NULL
        ORDER BY ni.completed_at
        """
        
        try:
            result = await (query, [workflow_instance_id, upstream_ids_str])
            
            upstream_data = {}
            
            for node in result:
                node_key = str(node['node_base_id'])
                upstream_data[node_key] = {
                    'node_name': node['node_name'],
                    'node_instance_id': str(node['node_instance_id']),
                    'output_data': node['output_data'],
                    'completed_at': node['completed_at']
                }
            
            logger.debug(f"Collected output data from {len(upstream_data)} upstream nodes")
            return upstream_data
            
        except Exception as e:
            logger.error(f"Error getting upstream output data: {e}")
            return {}
    
    async def get_nodes_ready_for_execution(self, 
                                          workflow_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取准备执行的节点（所有上游节点都已完成）"""
        query = """
        WITH node_upstream_status AS (
            SELECT 
                ni.node_instance_id,
                n.node_base_id,
                ni.status as current_status,
                COALESCE(upstream_counts.required_upstream, 0) as required_upstream,
                COALESCE(upstream_counts.completed_upstream, 0) as completed_upstream
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            LEFT JOIN (
                SELECT 
                    e.to_node_id,
                    COUNT(e.from_node_id) as required_upstream,
                    COUNT(CASE WHEN ni_upstream.status = 'COMPLETED' THEN 1 END) as completed_upstream
                FROM edge e
                LEFT JOIN node_instance ni_upstream 
                    JOIN node n_upstream ON ni_upstream.node_id = n_upstream.node_id
                    ON (e.from_node_id = n_upstream.node_base_id AND ni_upstream.workflow_instance_id = %s)
                WHERE e.workflow_base_id = (
                    SELECT workflow_base_id 
                    FROM workflow_instance 
                    WHERE workflow_instance_id = %s
                )
                GROUP BY e.to_node_id
            ) upstream_counts ON n.node_base_id = upstream_counts.to_node_id
            WHERE ni.workflow_instance_id = %s
        )
        SELECT 
            nus.*,
            n.name as node_name,
            n.type as node_type,
            n.task_description as description
        FROM node_upstream_status nus
        JOIN node n ON nus.node_base_id = n.node_base_id
        WHERE nus.current_status = 'PENDING'
        AND (nus.required_upstream = 0 OR nus.required_upstream = nus.completed_upstream)
        ORDER BY nus.required_upstream, n.name
        """
        
        try:
            result = await self.db.fetch_all(query, 
                workflow_instance_id, 
                workflow_instance_id, 
                workflow_instance_id
            )
            
            logger.debug(f"Found {len(result)} nodes ready for execution")
            return result
            
        except Exception as e:
            logger.error(f"Error getting nodes ready for execution: {e}")
            return []
    
    async def validate_workflow_dependencies(self, 
                                           workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """验证工作流的依赖关系是否有效（检查循环依赖等）"""
        query = """
        WITH RECURSIVE dependency_path AS (
            -- 初始节点（起始节点）
            SELECT 
                e.from_node_id as node_id,
                e.to_node_id as depends_on,
                ARRAY[e.from_node_id] as path,
                1 as depth
            FROM edge e
            WHERE e.workflow_base_id = %s
            
            UNION ALL
            
            -- 递归查找依赖路径
            SELECT 
                e.from_node_id,
                e.to_node_id,
                dp.path || e.from_node_id,
                dp.depth + 1
            FROM edge e
            JOIN dependency_path dp ON e.from_node_id = dp.depends_on
            WHERE e.workflow_base_id = %s
            AND e.from_node_id != ALL(dp.path)  -- 检测循环
            AND dp.depth < 50  -- 防止无限递归
        )
        SELECT 
            node_id,
            depends_on,
            path,
            depth,
            CASE WHEN node_id = ANY(path[1:array_length(path,1)-1]) THEN true ELSE false END as has_cycle
        FROM dependency_path
        WHERE has_cycle = true
        """
        
        try:
            result = await self.db.fetch_all(query, workflow_base_id, workflow_base_id)
            
            cycles_found = len(result)
            
            validation_result = {
                'is_valid': cycles_found == 0,
                'cycles_count': cycles_found,
                'cycles': result if result else [],
                'workflow_base_id': str(workflow_base_id)
            }
            
            if cycles_found > 0:
                logger.warning(f"Found {cycles_found} dependency cycles in workflow {workflow_base_id}")
            else:
                logger.debug(f"Workflow {workflow_base_id} has valid dependencies (no cycles)")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating workflow dependencies: {e}")
            return {
                'is_valid': False,
                'cycles_count': 0,
                'cycles': [],
                'error': str(e)
            }
    
    async def get_workflow_execution_order(self, 
                                         workflow_base_id: uuid.UUID) -> List[List[uuid.UUID]]:
        """获取工作流的执行顺序（按层级分组）"""
        query = """
        WITH RECURSIVE node_levels AS (
            -- 起始节点（无上游依赖）
            SELECT 
                n.node_base_id,
                0 as level
            FROM node n
            WHERE n.workflow_base_id = %s
            AND NOT EXISTS (
                SELECT 1 FROM edge e 
                WHERE e.to_node_id = n.node_base_id 
                AND e.workflow_base_id = %s
            )
            
            UNION ALL
            
            -- 递归计算依赖层级
            SELECT 
                e.to_node_id,
                nl.level + 1
            FROM edge e
            JOIN node_levels nl ON e.from_node_id = nl.node_base_id
            WHERE e.workflow_base_id = %s
        )
        SELECT 
            node_base_id,
            MAX(level) as execution_level
        FROM node_levels
        GROUP BY node_base_id
        ORDER BY execution_level, node_base_id
        """
        
        try:
            result = await self.db.fetch_all(query, 
                workflow_base_id, 
                workflow_base_id, 
                workflow_base_id
            )
            
            # 按层级分组
            execution_levels = {}
            for row in result:
                level = row['execution_level']
                if level not in execution_levels:
                    execution_levels[level] = []
                execution_levels[level].append(row['node_base_id'])
            
            # 转换为列表格式
            execution_order = []
            for level in sorted(execution_levels.keys()):
                execution_order.append(execution_levels[level])
            
            logger.debug(f"Workflow execution order: {len(execution_order)} levels")
            return execution_order
            
        except Exception as e:
            logger.error(f"Error getting workflow execution order: {e}")
            return []
    
    def clear_cache(self):
        """清理依赖关系缓存"""
        self._dependency_cache.clear()
        self._downstream_cache.clear()
        logger.debug("Dependency cache cleared")
    
    def clear_node_cache(self, node_base_id: uuid.UUID):
        """清理特定节点的缓存"""
        if node_base_id in self._dependency_cache:
            del self._dependency_cache[node_base_id]
        if node_base_id in self._downstream_cache:
            del self._downstream_cache[node_base_id]