"""
处理器数据访问层
Processor Repository
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..base import BaseRepository
from ...models.processor import (
    Processor, ProcessorCreate, ProcessorUpdate, ProcessorType,
    NodeProcessor, NodeProcessorCreate
)
from ...utils.helpers import now_utc


class ProcessorRepository(BaseRepository[Processor]):
    """处理器数据访问层"""
    
    def __init__(self):
        super().__init__("processor")
    
    async def create_processor(self, processor_data: ProcessorCreate) -> Optional[Dict[str, Any]]:
        """创建处理器"""
        try:
            # 验证处理器类型和关联的用户/Agent
            self._validate_processor_type(processor_data.type, 
                                        processor_data.user_id, 
                                        processor_data.agent_id)
            
            # 验证用户和Agent是否存在
            await self._validate_referenced_entities(processor_data.user_id, processor_data.agent_id)
            
            # 准备数据
            data = {
                "processor_id": uuid.uuid4(),
                "user_id": processor_data.user_id,
                "agent_id": processor_data.agent_id,
                "name": processor_data.name,
                "type": processor_data.type.value,
                "version": 1,
                "created_at": now_utc(),
                "is_deleted": False
            }
            
            result = await self.create(data)
            return result
        except Exception as e:
            logger.error(f"创建处理器失败: {e}")
            raise
    
    def _validate_processor_type(self, processor_type: ProcessorType, 
                                user_id: Optional[uuid.UUID], 
                                agent_id: Optional[uuid.UUID]):
        """验证处理器类型"""
        if processor_type == ProcessorType.HUMAN:
            if not user_id or agent_id:
                raise ValueError("human类型处理器必须指定user_id且不能指定agent_id")
        elif processor_type == ProcessorType.AGENT:
            if not agent_id or user_id:
                raise ValueError("agent类型处理器必须指定agent_id且不能指定user_id")
        elif processor_type == ProcessorType.MIX:
            if not user_id or not agent_id:
                raise ValueError("mix类型处理器必须同时指定user_id和agent_id")
    
    async def _validate_referenced_entities(self, user_id: Optional[uuid.UUID], agent_id: Optional[uuid.UUID]):
        """验证引用的用户和Agent是否存在"""
        if user_id:
            # 检查用户是否存在
            user_query = "SELECT user_id FROM \"user\" WHERE user_id = $1 AND is_deleted = FALSE"
            user_exists = await self.db.fetch_one(user_query, user_id)
            if not user_exists:
                raise ValueError(f"用户 {user_id} 不存在或已被删除")
        
        if agent_id:
            # 检查Agent是否存在
            agent_query = "SELECT agent_id FROM agent WHERE agent_id = $1 AND is_deleted = FALSE"
            agent_exists = await self.db.fetch_one(agent_query, agent_id)
            if not agent_exists:
                raise ValueError(f"Agent {agent_id} 不存在或已被删除")
    
    async def get_processor_by_id(self, processor_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取处理器"""
        return await self.get_by_id(processor_id, "processor_id")
    
    async def get_processor_with_details(self, processor_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取处理器详细信息（包含用户和Agent信息）"""
        try:
            query = """
                SELECT p.*,
                       u.username, u.email as user_email,
                       a.agent_name, a.description as agent_description
                FROM processor p
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                WHERE p.processor_id = $1 AND p.is_deleted = FALSE
            """
            result = await self.db.fetch_one(query, processor_id)
            return result
        except Exception as e:
            logger.error(f"获取处理器详细信息失败: {e}")
            raise
    
    async def update_processor(self, processor_id: uuid.UUID, 
                              processor_data: ProcessorUpdate) -> Optional[Dict[str, Any]]:
        """更新处理器"""
        try:
            # 检查处理器是否存在
            existing_processor = await self.get_by_id(processor_id, "processor_id")
            if not existing_processor:
                raise ValueError(f"处理器 {processor_id} 不存在")
            
            # 准备更新数据
            update_data = {}
            
            if processor_data.name is not None:
                update_data["name"] = processor_data.name
            
            if processor_data.user_id is not None:
                update_data["user_id"] = processor_data.user_id
            
            if processor_data.agent_id is not None:
                update_data["agent_id"] = processor_data.agent_id
            
            # 如果更新了用户或Agent，需要重新验证类型
            current_type = ProcessorType(existing_processor['type'])
            user_id = processor_data.user_id if processor_data.user_id is not None else existing_processor['user_id']
            agent_id = processor_data.agent_id if processor_data.agent_id is not None else existing_processor['agent_id']
            
            self._validate_processor_type(current_type, user_id, agent_id)
            
            if not update_data:
                return existing_processor
            
            # 增加版本号
            update_data["version"] = existing_processor['version'] + 1
            
            result = await self.update(processor_id, update_data, "processor_id")
            return result
        except Exception as e:
            logger.error(f"更新处理器失败: {e}")
            raise
    
    async def delete_processor(self, processor_id: uuid.UUID, soft_delete: bool = True) -> bool:
        """删除处理器"""
        return await self.delete(processor_id, "processor_id", soft_delete)
    
    async def get_processors_by_type(self, processor_type: ProcessorType) -> List[Dict[str, Any]]:
        """根据类型获取处理器列表"""
        try:
            query = """
                SELECT p.*,
                       u.username, u.email as user_email,
                       a.agent_name, a.description as agent_description
                FROM processor p
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                WHERE p.type = $1 AND p.is_deleted = FALSE
                ORDER BY p.created_at DESC
            """
            results = await self.db.fetch_all(query, processor_type.value)
            return results
        except Exception as e:
            logger.error(f"根据类型获取处理器列表失败: {e}")
            raise
    
    async def get_processors_by_user(self, user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取用户的处理器列表"""
        try:
            query = """
                SELECT p.*,
                       u.username, u.email as user_email,
                       a.agent_name, a.description as agent_description
                FROM processor p
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                WHERE p.user_id = $1 AND p.is_deleted = FALSE
                ORDER BY p.created_at DESC
            """
            results = await self.db.fetch_all(query, user_id)
            return results
        except Exception as e:
            logger.error(f"获取用户处理器列表失败: {e}")
            raise
    
    async def get_processors_by_agent(self, agent_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取Agent的处理器列表"""
        try:
            query = """
                SELECT p.*,
                       u.username, u.email as user_email,
                       a.agent_name, a.description as agent_description
                FROM processor p
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                WHERE p.agent_id = $1 AND p.is_deleted = FALSE
                ORDER BY p.created_at DESC
            """
            results = await self.db.fetch_all(query, agent_id)
            return results
        except Exception as e:
            logger.error(f"获取Agent处理器列表失败: {e}")
            raise
    
    async def search_processors(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索处理器"""
        try:
            query = """
                SELECT p.*,
                       u.username, u.email as user_email,
                       a.agent_name, a.description as agent_description
                FROM processor p
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                WHERE (p.name ILIKE $1 OR u.username ILIKE $1 OR a.agent_name ILIKE $1)
                      AND p.is_deleted = FALSE
                ORDER BY p.created_at DESC
                LIMIT $2
            """
            keyword_pattern = f"%{keyword}%"
            results = await self.db.fetch_all(query, keyword_pattern, limit)
            return results
        except Exception as e:
            logger.error(f"搜索处理器失败: {e}")
            raise


class NodeProcessorRepository:
    """节点处理器关联数据访问层"""
    
    def __init__(self):
        self.db = BaseRepository("node_processor").db
    
    async def create_node_processor(self, data: NodeProcessorCreate) -> Optional[Dict[str, Any]]:
        """创建节点处理器关联"""
        try:
            # 获取当前版本的节点ID和workflow_id
            node_query = """
                SELECT node_id, workflow_id FROM "node" 
                WHERE node_base_id = $1 AND workflow_base_id = $2
                AND is_current_version = true 
                AND is_deleted = false
            """
            node_result = await self.db.fetch_one(node_query, 
                                                data.node_base_id, 
                                                data.workflow_base_id)
            if not node_result:
                raise ValueError("节点不存在")
            
            # 检查处理器是否存在
            processor_query = "SELECT processor_id FROM processor WHERE processor_id = $1 AND is_deleted = FALSE"
            processor_result = await self.db.fetch_one(processor_query, data.processor_id)
            if not processor_result:
                raise ValueError("处理器不存在")
            
            # 创建关联 - MySQL兼容版本
            # 先检查是否已存在
            check_query = """
                SELECT * FROM node_processor 
                WHERE node_id = $1 AND processor_id = $2
            """
            existing = await self.db.fetch_one(check_query, node_result['node_id'], data.processor_id)
            
            if existing:
                logger.info(f"节点处理器关联已存在: {node_result['node_id']} -> {data.processor_id}")
                return existing
            
            # 不存在则创建 - 包含所有必需字段
            node_processor_id = uuid.uuid4()
            query = """
                INSERT INTO node_processor (
                    node_processor_id, node_id, node_base_id, workflow_id, 
                    workflow_base_id, processor_id, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
            
            await self.db.execute(
                query,
                node_processor_id,
                node_result['node_id'],
                data.node_base_id,
                node_result['workflow_id'],
                data.workflow_base_id,
                data.processor_id,
                now_utc()
            )
            
            # 查询创建的记录
            result = await self.db.fetch_one(check_query, node_result['node_id'], data.processor_id)
            
            if result:
                logger.info(f"创建了节点处理器关联: {node_result['node_id']} -> {data.processor_id}")
            return result
        except Exception as e:
            logger.error(f"创建节点处理器关联失败: {e}")
            raise
    
    async def delete_node_processor(self, node_base_id: uuid.UUID, 
                                   workflow_base_id: uuid.UUID,
                                   processor_id: uuid.UUID) -> bool:
        """删除节点处理器关联"""
        try:
            # 获取当前版本的节点ID
            node_query = """
                SELECT node_id FROM "node" 
                WHERE node_base_id = $1 AND workflow_base_id = $2
                AND is_current_version = true 
                AND is_deleted = false
            """
            node_result = await self.db.fetch_one(node_query, node_base_id, workflow_base_id)
            if not node_result:
                raise ValueError("节点不存在")
            
            query = "DELETE FROM node_processor WHERE node_id = $1 AND processor_id = $2"
            result = await self.db.execute(query, node_result['node_id'], processor_id)
            success = "1" in result
            if success:
                logger.info(f"删除了节点处理器关联: {node_result['node_id']} -> {processor_id}")
            return success
        except Exception as e:
            logger.error(f"删除节点处理器关联失败: {e}")
            raise
    
    async def get_node_processors(self, node_base_id: uuid.UUID, 
                                 workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的处理器列表"""
        try:
            query = """
                SELECT np.*, p.name as processor_name, p.type as processor_type,
                       u.username, a.agent_name
                FROM node_processor np
                JOIN processor p ON p.processor_id = np.processor_id AND p.is_deleted = FALSE
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                JOIN node n ON n.node_id = np.node_id AND n.is_current_version = TRUE
                WHERE n.node_base_id = $1 AND n.workflow_base_id = $2
                ORDER BY np.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取节点处理器列表失败: {e}")
            raise
    
    async def get_processor_nodes(self, processor_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取处理器关联的节点列表"""
        try:
            query = """
                SELECT np.*, n.node_base_id, n.name as node_name, n.type as node_type,
                       w.workflow_base_id, w.name as workflow_name
                FROM node_processor np
                JOIN node n ON n.node_id = np.node_id AND n.is_current_version = TRUE
                JOIN workflow w ON w.workflow_id = n.workflow_id AND w.is_current_version = TRUE
                WHERE np.processor_id = $1
                ORDER BY np.created_at DESC
            """
            results = await self.db.fetch_all(query, processor_id)
            return results
        except Exception as e:
            logger.error(f"获取处理器节点列表失败: {e}")
            raise
    
    async def get_processors_by_node(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的处理器列表"""
        try:
            query = """
                SELECT np.*, p.name as processor_name, p.type as processor_type,
                       u.username, a.agent_name, p.user_id, p.agent_id
                FROM node_processor np
                JOIN processor p ON p.processor_id = np.processor_id AND p.is_deleted = FALSE
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                JOIN node n ON n.node_id = np.node_id AND n.is_current_version = TRUE
                WHERE n.node_base_id = $1 AND n.workflow_base_id = $2
                ORDER BY np.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取节点处理器列表失败: {e}")
            raise