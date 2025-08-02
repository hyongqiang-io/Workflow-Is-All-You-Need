"""
版本控制服务
Version Control Service
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..utils.database import get_db_manager
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..repositories.node.node_repository import NodeRepository, NodeConnectionRepository
from ..repositories.processor.processor_repository import NodeProcessorRepository


class VersionService:
    """版本控制服务"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.workflow_repo = WorkflowRepository()
        self.node_repo = NodeRepository()
        self.connection_repo = NodeConnectionRepository()
        self.node_processor_repo = NodeProcessorRepository()
    
    async def create_workflow_version(self, workflow_base_id: uuid.UUID, 
                                     editor_user_id: Optional[uuid.UUID] = None,
                                     change_description: Optional[str] = None) -> Dict[str, Any]:
        """创建工作流新版本"""
        try:
            # 调用数据库函数创建工作流版本
            new_workflow_id = await self.db.call_function(
                "create_workflow_version",
                workflow_base_id,
                editor_user_id,
                change_description
            )
            
            if not new_workflow_id:
                raise ValueError("创建工作流版本失败")
            
            # 获取新版本信息
            new_workflow = await self.workflow_repo.get_workflow_by_id(new_workflow_id)
            
            logger.info(f"成功创建工作流版本: {workflow_base_id} -> 版本 {new_workflow['version']}")
            
            return {
                "workflow_id": new_workflow_id,
                "workflow_base_id": workflow_base_id,
                "version": new_workflow['version'],
                "change_description": change_description,
                "success": True,
                "message": f"成功创建版本 {new_workflow['version']}"
            }
        except Exception as e:
            logger.error(f"创建工作流版本失败: {e}")
            raise
    
    async def create_node_version(self, node_base_id: uuid.UUID, 
                                 workflow_base_id: uuid.UUID,
                                 new_name: Optional[str] = None,
                                 new_description: Optional[str] = None,
                                 new_position_x: Optional[int] = None,
                                 new_position_y: Optional[int] = None) -> Dict[str, Any]:
        """创建节点新版本"""
        try:
            # 调用数据库函数创建节点版本
            new_node_id = await self.db.call_function(
                "create_node_version",
                node_base_id,
                workflow_base_id,
                new_name,
                new_description,
                new_position_x,
                new_position_y
            )
            
            if not new_node_id:
                raise ValueError("创建节点版本失败")
            
            # 获取新版本信息
            new_node = await self.node_repo.get_node_by_id(new_node_id)
            
            logger.info(f"成功创建节点版本: {node_base_id} -> 版本 {new_node['version']}")
            
            # 验证连接关系完整性
            new_workflow_id = new_node['workflow_id']
            await self._validate_connection_integrity(new_workflow_id)
            
            return {
                "node_id": new_node_id,
                "node_base_id": node_base_id,
                "workflow_id": new_workflow_id,
                "workflow_base_id": workflow_base_id,
                "version": new_node['version'],
                "success": True,
                "message": f"成功创建节点版本 {new_node['version']}"
            }
        except Exception as e:
            logger.error(f"创建节点版本失败: {e}")
            raise
    
    async def get_workflow_version_history(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流版本历史"""
        try:
            versions = await self.workflow_repo.get_workflow_versions(workflow_base_id)
            
            # 为每个版本添加详细信息
            for version in versions:
                # 获取该版本的节点数量
                node_count_query = """
                    SELECT COUNT(*) FROM node 
                    WHERE workflow_id = $1 AND is_deleted = FALSE
                """
                node_count = await self.db.fetch_val(node_count_query, version['workflow_id'])
                version['node_count'] = node_count
                
                # 获取连接数量
                connection_count_query = """
                    SELECT COUNT(*) FROM node_connection 
                    WHERE workflow_id = $1
                """
                connection_count = await self.db.fetch_val(connection_count_query, version['workflow_id'])
                version['connection_count'] = connection_count
            
            return versions
        except Exception as e:
            logger.error(f"获取工作流版本历史失败: {e}")
            raise
    
    async def get_node_version_history(self, node_base_id: uuid.UUID, 
                                      workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点版本历史"""
        try:
            query = """
                SELECT n.*, w.version as workflow_version, w.name as workflow_name
                FROM node n
                JOIN workflow w ON w.workflow_id = n.workflow_id
                WHERE n.node_base_id = $1 AND n.workflow_base_id = $2 AND n.is_deleted = FALSE
                ORDER BY n.version DESC
            """
            versions = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return versions
        except Exception as e:
            logger.error(f"获取节点版本历史失败: {e}")
            raise
    
    async def rollback_workflow_version(self, workflow_base_id: uuid.UUID, 
                                       target_version: int,
                                       editor_user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """回滚工作流到指定版本"""
        try:
            # 获取目标版本的工作流
            target_workflow_query = """
                SELECT * FROM workflow 
                WHERE workflow_base_id = $1 AND version = $2 AND is_deleted = FALSE
            """
            target_workflow = await self.db.fetch_one(target_workflow_query, 
                                                     workflow_base_id, target_version)
            if not target_workflow:
                raise ValueError(f"目标版本 {target_version} 不存在")
            
            # 创建新版本（基于目标版本）
            change_description = f"回滚到版本 {target_version}"
            result = await self.create_workflow_version(
                workflow_base_id, editor_user_id, change_description
            )
            
            # 复制目标版本的所有节点和连接
            new_workflow_id = result['workflow_id']
            await self._copy_workflow_content(target_workflow['workflow_id'], new_workflow_id)
            
            logger.info(f"成功回滚工作流 {workflow_base_id} 到版本 {target_version}")
            
            result.update({
                "rollback_to_version": target_version,
                "message": f"成功回滚到版本 {target_version}"
            })
            return result
        except Exception as e:
            logger.error(f"回滚工作流版本失败: {e}")
            raise
    
    async def _copy_workflow_content(self, source_workflow_id: uuid.UUID, 
                                    target_workflow_id: uuid.UUID):
        """复制工作流内容（内部方法）"""
        try:
            # 获取源工作流的所有节点
            source_nodes_query = "SELECT * FROM node WHERE workflow_id = $1 AND is_deleted = FALSE"
            source_nodes = await self.db.fetch_all(source_nodes_query, source_workflow_id)
            
            # 获取目标工作流信息
            target_workflow_query = "SELECT * FROM workflow WHERE workflow_id = $1"
            target_workflow = await self.db.fetch_one(target_workflow_query, target_workflow_id)
            
            node_id_mapping = {}
            
            # 复制节点
            for source_node in source_nodes:
                new_node_id = uuid.uuid4()
                node_id_mapping[source_node['node_id']] = new_node_id
                
                insert_node_query = """
                    INSERT INTO node (
                        node_id, node_base_id, workflow_id, workflow_base_id,
                        name, type, task_description, version, parent_version_id,
                        is_current_version, position_x, position_y, created_at, is_deleted
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """
                
                await self.db.execute(
                    insert_node_query,
                    new_node_id,
                    source_node['node_base_id'],
                    target_workflow_id,
                    target_workflow['workflow_base_id'],
                    source_node['name'],
                    source_node['type'],
                    source_node['task_description'],
                    target_workflow['version'],
                    source_node['node_id'],  # 父版本ID指向源节点
                    True,
                    source_node['position_x'],
                    source_node['position_y'],
                    source_node['created_at'],
                    False
                )
            
            # 复制连接
            source_connections_query = "SELECT * FROM node_connection WHERE workflow_id = $1"
            source_connections = await self.db.fetch_all(source_connections_query, source_workflow_id)
            
            for connection in source_connections:
                insert_connection_query = """
                    INSERT INTO node_connection (
                        from_node_id, to_node_id, workflow_id, 
                        connection_type, condition_config, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """
                
                await self.db.execute(
                    insert_connection_query,
                    node_id_mapping[connection['from_node_id']],
                    node_id_mapping[connection['to_node_id']],
                    target_workflow_id,
                    connection['connection_type'],
                    connection['condition_config'],
                    connection['created_at']
                )
            
            # 复制节点处理器关联
            for source_node_id, new_node_id in node_id_mapping.items():
                processor_query = "SELECT * FROM node_processor WHERE node_id = $1"
                processors = await self.db.fetch_all(processor_query, source_node_id)
                
                for processor in processors:
                    insert_processor_query = """
                        INSERT INTO node_processor (node_id, processor_id, created_at)
                        VALUES ($1, $2, $3)
                    """
                    await self.db.execute(
                        insert_processor_query,
                        new_node_id,
                        processor['processor_id'],
                        processor['created_at']
                    )
                    
        except Exception as e:
            logger.error(f"复制工作流内容失败: {e}")
            raise
    
    async def compare_workflow_versions(self, workflow_base_id: uuid.UUID,
                                       version1: int, version2: int) -> Dict[str, Any]:
        """比较工作流版本差异"""
        try:
            # 获取两个版本的工作流
            version_query = """
                SELECT * FROM workflow 
                WHERE workflow_base_id = $1 AND version = $2 AND is_deleted = FALSE
            """
            
            workflow1 = await self.db.fetch_one(version_query, workflow_base_id, version1)
            workflow2 = await self.db.fetch_one(version_query, workflow_base_id, version2)
            
            if not workflow1 or not workflow2:
                raise ValueError("指定的版本不存在")
            
            # 获取两个版本的节点
            nodes_query = "SELECT * FROM node WHERE workflow_id = $1 AND is_deleted = FALSE"
            nodes1 = await self.db.fetch_all(nodes_query, workflow1['workflow_id'])
            nodes2 = await self.db.fetch_all(nodes_query, workflow2['workflow_id'])
            
            # 获取两个版本的连接
            connections_query = "SELECT * FROM node_connection WHERE workflow_id = $1"
            connections1 = await self.db.fetch_all(connections_query, workflow1['workflow_id'])
            connections2 = await self.db.fetch_all(connections_query, workflow2['workflow_id'])
            
            # 比较差异
            comparison = {
                "workflow_base_id": workflow_base_id,
                "version1": version1,
                "version2": version2,
                "workflow_changes": self._compare_workflows(workflow1, workflow2),
                "node_changes": self._compare_nodes(nodes1, nodes2),
                "connection_changes": self._compare_connections(connections1, connections2)
            }
            
            return comparison
        except Exception as e:
            logger.error(f"比较工作流版本失败: {e}")
            raise
    
    def _compare_workflows(self, workflow1: Dict[str, Any], 
                          workflow2: Dict[str, Any]) -> Dict[str, Any]:
        """比较工作流基本信息差异"""
        changes = {}
        
        if workflow1['name'] != workflow2['name']:
            changes['name'] = {
                'old': workflow1['name'],
                'new': workflow2['name']
            }
        
        if workflow1['description'] != workflow2['description']:
            changes['description'] = {
                'old': workflow1['description'],
                'new': workflow2['description']
            }
        
        return changes
    
    def _compare_nodes(self, nodes1: List[Dict[str, Any]], 
                      nodes2: List[Dict[str, Any]]) -> Dict[str, Any]:
        """比较节点差异"""
        nodes1_map = {node['node_base_id']: node for node in nodes1}
        nodes2_map = {node['node_base_id']: node for node in nodes2}
        
        added = []
        removed = []
        modified = []
        
        # 检查添加和修改的节点
        for base_id, node2 in nodes2_map.items():
            if base_id not in nodes1_map:
                added.append(node2)
            else:
                node1 = nodes1_map[base_id]
                if self._nodes_different(node1, node2):
                    modified.append({
                        'node_base_id': base_id,
                        'old': node1,
                        'new': node2
                    })
        
        # 检查删除的节点
        for base_id, node1 in nodes1_map.items():
            if base_id not in nodes2_map:
                removed.append(node1)
        
        return {
            'added': added,
            'removed': removed,
            'modified': modified
        }
    
    def _compare_connections(self, connections1: List[Dict[str, Any]], 
                           connections2: List[Dict[str, Any]]) -> Dict[str, Any]:
        """比较连接差异"""
        # 简化比较（实际实现需要通过node_base_id来对应）
        return {
            'added': [],
            'removed': [],
            'modified': []
        }
    
    def _nodes_different(self, node1: Dict[str, Any], node2: Dict[str, Any]) -> bool:
        """检查两个节点是否不同"""
        compare_fields = ['name', 'task_description', 'position_x', 'position_y']
        for field in compare_fields:
            if node1.get(field) != node2.get(field):
                return True
        return False
    
    async def get_version_statistics(self, workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """获取版本统计信息"""
        try:
            stats_query = """
                SELECT 
                    COUNT(*) as total_versions,
                    MAX(version) as latest_version,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_modified,
                    COUNT(DISTINCT creator_id) as contributors
                FROM workflow 
                WHERE workflow_base_id = $1 AND is_deleted = FALSE
            """
            
            stats = await self.db.fetch_one(stats_query, workflow_base_id)
            
            # 获取每个版本的节点和连接数量
            version_details_query = """
                SELECT w.version, w.created_at, w.change_description,
                       COUNT(DISTINCT n.node_id) as node_count,
                       COUNT(DISTINCT nc.from_node_id) as connection_count
                FROM workflow w
                LEFT JOIN node n ON n.workflow_id = w.workflow_id AND n.is_deleted = FALSE
                LEFT JOIN node_connection nc ON nc.workflow_id = w.workflow_id
                WHERE w.workflow_base_id = $1 AND w.is_deleted = FALSE
                GROUP BY w.version, w.created_at, w.change_description
                ORDER BY w.version DESC
            """
            
            version_details = await self.db.fetch_all(version_details_query, workflow_base_id)
            
            return {
                "workflow_base_id": workflow_base_id,
                "summary": stats,
                "version_details": version_details
            }
        except Exception as e:
            logger.error(f"获取版本统计信息失败: {e}")
            raise
    
    async def _validate_connection_integrity(self, workflow_id: uuid.UUID):
        """验证工作流中连接关系的完整性"""
        try:
            logger.info(f"🔍 [连接验证] 开始验证工作流 {workflow_id} 的连接关系完整性")
            
            # 获取所有节点
            nodes_query = """
                SELECT node_id, name, type 
                FROM node 
                WHERE workflow_id = $1 AND is_current_version = TRUE AND is_deleted = FALSE
            """
            nodes = await self.db.fetch_all(nodes_query, workflow_id)
            node_ids = {node['node_id'] for node in nodes}
            
            logger.info(f"  - 工作流节点数: {len(nodes)}")
            
            # 获取所有连接
            connections_query = """
                SELECT from_node_id, to_node_id, connection_type 
                FROM node_connection 
                WHERE workflow_id = $1
            """
            connections = await self.db.fetch_all(connections_query, workflow_id)
            
            logger.info(f"  - 连接关系数: {len(connections)}")
            
            # 验证连接的完整性
            invalid_connections = []
            for conn in connections:
                from_id = conn['from_node_id']
                to_id = conn['to_node_id']
                
                if from_id not in node_ids:
                    invalid_connections.append(f"源节点 {from_id} 不存在")
                
                if to_id not in node_ids:
                    invalid_connections.append(f"目标节点 {to_id} 不存在")
            
            if invalid_connections:
                error_msg = f"发现 {len(invalid_connections)} 个无效连接: {', '.join(invalid_connections)}"
                logger.error(f"❌ [连接验证] {error_msg}")
                raise ValueError(error_msg)
            
            logger.info(f"✅ [连接验证] 连接关系完整性验证通过")
            
            # 记录连接关系详情
            logger.info(f"📊 [连接验证] 连接关系详情:")
            for conn in connections:
                from_node = next((n for n in nodes if n['node_id'] == conn['from_node_id']), None)
                to_node = next((n for n in nodes if n['node_id'] == conn['to_node_id']), None)
                
                if from_node and to_node:
                    logger.info(f"  - {from_node['name']} -> {to_node['name']} ({conn['connection_type']})")
            
        except Exception as e:
            logger.error(f"❌ [连接验证] 验证连接关系完整性失败: {e}")
            raise
    
    async def validate_workflow_consistency(self, workflow_id: uuid.UUID) -> Dict[str, Any]:
        """全面验证工作流的一致性"""
        try:
            logger.info(f"🔍 开始验证工作流 {workflow_id} 的一致性")
            
            result = {
                "workflow_id": workflow_id,
                "is_valid": True,
                "issues": [],
                "warnings": [],
                "statistics": {}
            }
            
            # 1. 验证连接关系完整性
            try:
                await self._validate_connection_integrity(workflow_id)
            except ValueError as e:
                result["is_valid"] = False
                result["issues"].append(f"连接关系完整性问题: {str(e)}")
            
            # 2. 检查孤立节点
            orphaned_nodes_query = """
                SELECT n.node_id, n.name, n.type 
                FROM node n
                WHERE n.workflow_id = $1 AND n.is_current_version = TRUE AND n.is_deleted = FALSE
                AND n.node_id NOT IN (
                    SELECT DISTINCT from_node_id FROM node_connection WHERE workflow_id = $1
                    UNION
                    SELECT DISTINCT to_node_id FROM node_connection WHERE workflow_id = $1
                )
                AND n.type NOT IN ('start', 'end')
            """
            
            orphaned_nodes = await self.db.fetch_all(orphaned_nodes_query, workflow_id)
            if orphaned_nodes:
                result["warnings"].append(f"发现 {len(orphaned_nodes)} 个孤立节点")
                for node in orphaned_nodes:
                    result["warnings"].append(f"  - 孤立节点: {node['name']} ({node['type']})")
            
            # 3. 统计信息
            stats_query = """
                SELECT 
                    COUNT(DISTINCT n.node_id) as total_nodes,
                    COUNT(DISTINCT nc.from_node_id) as total_connections,
                    COUNT(DISTINCT CASE WHEN n.type = 'start' THEN n.node_id END) as start_nodes,
                    COUNT(DISTINCT CASE WHEN n.type = 'end' THEN n.node_id END) as end_nodes,
                    COUNT(DISTINCT CASE WHEN n.type = 'processor' THEN n.node_id END) as processor_nodes
                FROM node n
                LEFT JOIN node_connection nc ON nc.workflow_id = n.workflow_id
                WHERE n.workflow_id = $1 AND n.is_current_version = TRUE AND n.is_deleted = FALSE
                GROUP BY n.workflow_id
            """
            
            stats = await self.db.fetch_one(stats_query, workflow_id)
            if stats:
                result["statistics"] = dict(stats)
            
            logger.info(f"✅ 工作流一致性验证完成: {'通过' if result['is_valid'] else '失败'}")
            return result
            
        except Exception as e:
            logger.error(f"验证工作流一致性失败: {e}")
            raise