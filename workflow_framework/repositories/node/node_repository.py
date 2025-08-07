"""
节点数据访问层
Node Repository
"""

import uuid
import json
from typing import Optional, Dict, Any, List
from loguru import logger

from ..base import BaseRepository
from ...models.node import (
    Node, NodeCreate, NodeUpdate, NodeConnection, 
    NodeConnectionCreate, NodeConnectionUpdate, NodeVersionCreate
)
from ...utils.helpers import now_utc, safe_json_dumps


class NodeRepository(BaseRepository[Node]):
    """节点数据访问层"""
    
    def __init__(self):
        super().__init__("node")
    
    async def create_node(self, node_data: NodeCreate) -> Optional[Dict[str, Any]]:
        """创建节点"""
        try:
            # 获取当前工作流版本
            workflow_query = """
                SELECT workflow_id FROM workflow 
                WHERE workflow_base_id = $1 AND is_current_version = TRUE AND is_deleted = FALSE
            """
            workflow_result = await self.db.fetch_one(workflow_query, node_data.workflow_base_id)
            if not workflow_result:
                raise ValueError(f"工作流 {node_data.workflow_base_id} 不存在或没有当前版本")
            
            workflow_id = workflow_result['workflow_id']
            
            # 准备数据
            data = {
                "node_id": uuid.uuid4(),
                "node_base_id": uuid.uuid4(),
                "workflow_id": workflow_id,
                "workflow_base_id": node_data.workflow_base_id,
                "name": node_data.name,
                "type": node_data.type.value,
                "task_description": node_data.task_description,
                "version": 1,
                "parent_version_id": None,
                "is_current_version": True,
                "position_x": node_data.position_x,
                "position_y": node_data.position_y,
                "created_at": now_utc(),
                "is_deleted": False
            }
            
            result = await self.create(data)
            return result
        except Exception as e:
            logger.error(f"创建节点失败: {e}")
            raise
    
    async def get_node_by_id(self, node_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取节点"""
        return await self.get_by_id(node_id, "node_id")
    
    async def get_node_by_base_id(self, node_base_id: uuid.UUID, 
                                 workflow_base_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据基础ID获取当前版本的节点"""
        try:
            query = """
                SELECT * FROM "node" 
                WHERE node_base_id = $1 
                AND workflow_base_id = $2
                AND is_current_version = true 
                AND is_deleted = false
            """
            result = await self.db.fetch_one(query, node_base_id, workflow_base_id)
            return result
        except Exception as e:
            logger.error(f"根据基础ID获取节点失败: {e}")
            raise
    
    async def update_node(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID,
                         node_data: NodeUpdate) -> Optional[Dict[str, Any]]:
        """更新节点（直接更新当前版本）"""
        try:
            # 构建更新字段
            update_fields = []
            params = []
            param_index = 1
            
            if node_data.name is not None:
                update_fields.append(f"name = ${param_index}")
                params.append(node_data.name)
                param_index += 1
            
            if node_data.type is not None:
                update_fields.append(f"type = ${param_index}")
                params.append(node_data.type.value)
                param_index += 1
            
            if node_data.task_description is not None:
                update_fields.append(f"task_description = ${param_index}")
                params.append(node_data.task_description)
                param_index += 1
            
            if node_data.position_x is not None:
                update_fields.append(f"position_x = ${param_index}")
                params.append(int(node_data.position_x))  # 转换为整数存储
                param_index += 1
            
            if node_data.position_y is not None:
                update_fields.append(f"position_y = ${param_index}")
                params.append(int(node_data.position_y))  # 转换为整数存储
                param_index += 1
            
            if not update_fields:
                # 没有字段需要更新
                return await self.get_node_by_base_id(node_base_id, workflow_base_id)
            
            # 添加更新时间
            update_fields.append(f"updated_at = ${param_index}")
            params.append(now_utc())
            param_index += 1
            
            # 添加WHERE条件参数
            params.extend([node_base_id, workflow_base_id])
            
            # 构建和执行更新查询
            query = f"""
                UPDATE node 
                SET {', '.join(update_fields)}
                WHERE node_base_id = ${param_index} 
                  AND workflow_base_id = ${param_index + 1}
                  AND is_current_version = TRUE 
                  AND is_deleted = FALSE
                RETURNING *
            """
            
            result = await self.db.fetch_one(query, *params)
            
            if result:
                logger.info(f"更新节点成功: {node_base_id}")
                return result
            else:
                logger.warning(f"未找到要更新的节点: {node_base_id}")
                return None
                
        except Exception as e:
            logger.error(f"更新节点失败: {e}")
            raise
    
    async def delete_node(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID,
                         soft_delete: bool = True) -> bool:
        """删除节点（删除所有版本）"""
        try:
            if soft_delete:
                query = """
                    UPDATE node 
                    SET is_deleted = TRUE 
                    WHERE node_base_id = $1 AND workflow_base_id = $2
                """
            else:
                query = """
                    DELETE FROM node 
                    WHERE node_base_id = $1 AND workflow_base_id = $2
                """
            
            result = await self.db.execute(query, node_base_id, workflow_base_id)
            success = "1" in result or result.split()[1] != "0"
            if success:
                action = "软删除" if soft_delete else "硬删除"
                logger.info(f"{action}了节点 {node_base_id} 的所有版本")
            return success
        except Exception as e:
            logger.error(f"删除节点失败: {e}")
            raise
    
    async def get_workflow_nodes(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的所有当前版本节点，包含处理器信息"""
        try:
            query = """
                SELECT 
                    n.*,
                    np.processor_id
                FROM "node" n
                LEFT JOIN node_processor np ON np.node_id = n.node_id
                WHERE n.workflow_base_id = $1 
                AND n.is_current_version = true 
                AND n.is_deleted = false
                ORDER BY n.created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取工作流节点列表失败: {e}")
            raise
    
    async def get_nodes_by_type(self, workflow_base_id: uuid.UUID, 
                               node_type: str) -> List[Dict[str, Any]]:
        """根据类型获取节点列表"""
        try:
            query = """
                SELECT * FROM "node" 
                WHERE workflow_base_id = $1 AND type = $2 
                AND is_current_version = true 
                AND is_deleted = false
                ORDER BY created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_base_id, node_type)
            return results
        except Exception as e:
            logger.error(f"根据类型获取节点列表失败: {e}")
            raise


class NodeConnectionRepository:
    """节点连接数据访问层"""
    
    def __init__(self):
        self.db = BaseRepository("node_connection").db
    
    async def create_connection(self, connection_data: NodeConnectionCreate) -> Optional[Dict[str, Any]]:
        """创建节点连接"""
        try:
            # 获取当前版本的节点ID
            from_node_query = """
                SELECT node_id FROM node 
                WHERE node_base_id = $1 AND workflow_base_id = $2 
                AND is_current_version = TRUE AND is_deleted = FALSE
            """
            from_node = await self.db.fetch_one(from_node_query, 
                                              connection_data.from_node_base_id,
                                              connection_data.workflow_base_id)
            if not from_node:
                raise ValueError("源节点不存在")
            
            to_node = await self.db.fetch_one(from_node_query,
                                            connection_data.to_node_base_id,
                                            connection_data.workflow_base_id)
            if not to_node:
                raise ValueError("目标节点不存在")
            
            # 获取工作流ID
            workflow_query = """
                SELECT workflow_id FROM workflow 
                WHERE workflow_base_id = $1 AND is_current_version = TRUE AND is_deleted = FALSE
            """
            workflow = await self.db.fetch_one(workflow_query, connection_data.workflow_base_id)
            if not workflow:
                raise ValueError("工作流不存在")
            
            # 检查连接是否已存在
            check_query = """
                SELECT * FROM node_connection 
                WHERE from_node_id = $1 AND to_node_id = $2 AND workflow_id = $3
            """
            existing_connection = await self.db.fetch_one(
                check_query,
                from_node['node_id'],
                to_node['node_id'],
                workflow['workflow_id']
            )
            
            if existing_connection:
                logger.info(f"连接已存在，返回现有连接: {from_node['node_id']} -> {to_node['node_id']}")
                return existing_connection
            
            # 创建连接
            query = """
                INSERT INTO node_connection 
                (from_node_id, to_node_id, workflow_id, connection_type, condition_config, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
            """
            
            # 处理condition_config的JSON序列化
            condition_config = connection_data.condition_config
            if isinstance(condition_config, dict):
                condition_config = safe_json_dumps(condition_config)
            
            result = await self.db.fetch_one(
                query,
                from_node['node_id'],
                to_node['node_id'],
                workflow['workflow_id'],
                connection_data.connection_type.value,
                condition_config,
                now_utc()
            )
            
            if result:
                logger.info(f"创建了节点连接: {from_node['node_id']} -> {to_node['node_id']}")
            return result
        except Exception as e:
            logger.error(f"创建节点连接失败: {e}")
            raise
    
    async def get_connection(self, from_node_id: uuid.UUID, to_node_id: uuid.UUID, 
                           workflow_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点连接"""
        try:
            query = """
                SELECT * FROM node_connection 
                WHERE from_node_id = $1 AND to_node_id = $2 AND workflow_id = $3
            """
            result = await self.db.fetch_one(query, from_node_id, to_node_id, workflow_id)
            return result
        except Exception as e:
            logger.error(f"获取节点连接失败: {e}")
            raise
    
    async def update_connection(self, from_node_id: uuid.UUID, to_node_id: uuid.UUID,
                               workflow_id: uuid.UUID, 
                               update_data: NodeConnectionUpdate) -> Optional[Dict[str, Any]]:
        """更新节点连接"""
        try:
            update_dict = {}
            if update_data.connection_type is not None:
                update_dict["connection_type"] = update_data.connection_type.value
            if update_data.condition_config is not None:
                update_dict["condition_config"] = update_data.condition_config
            
            if not update_dict:
                return await self.get_connection(from_node_id, to_node_id, workflow_id)
            
            set_clauses = []
            values = []
            param_index = 1
            
            for key, value in update_dict.items():
                set_clauses.append(f"{key} = ${param_index}")
                values.append(value)
                param_index += 1
            
            query = f"""
                UPDATE node_connection 
                SET {', '.join(set_clauses)} 
                WHERE from_node_id = ${param_index} AND to_node_id = ${param_index + 1} 
                      AND workflow_id = ${param_index + 2}
                RETURNING *
            """
            
            values.extend([from_node_id, to_node_id, workflow_id])
            result = await self.db.fetch_one(query, *values)
            
            if result:
                logger.info(f"更新了节点连接: {from_node_id} -> {to_node_id}")
            return result
        except Exception as e:
            logger.error(f"更新节点连接失败: {e}")
            raise
    
    async def delete_connection(self, from_node_base_id: uuid.UUID, to_node_base_id: uuid.UUID,
                               workflow_base_id: uuid.UUID) -> bool:
        """删除节点连接"""
        try:
            # 获取当前版本的节点ID
            node_query = """
                SELECT node_id FROM "node" 
                WHERE node_base_id = $1 AND workflow_base_id = $2
                AND is_current_version = true 
                AND is_deleted = false
            """
            from_node = await self.db.fetch_one(node_query, from_node_base_id, workflow_base_id)
            to_node = await self.db.fetch_one(node_query, to_node_base_id, workflow_base_id)
            
            if not from_node or not to_node:
                raise ValueError("源节点或目标节点不存在")
            
            # 获取工作流ID
            workflow_query = """
                SELECT workflow_id FROM workflow 
                WHERE workflow_base_id = $1 AND is_current_version = TRUE
            """
            workflow = await self.db.fetch_one(workflow_query, workflow_base_id)
            if not workflow:
                raise ValueError("工作流不存在")
            
            query = """
                DELETE FROM node_connection 
                WHERE from_node_id = $1 AND to_node_id = $2 AND workflow_id = $3
            """
            result = await self.db.execute(query, from_node['node_id'], to_node['node_id'], workflow['workflow_id'])
            success = "1" in result
            if success:
                logger.info(f"删除了节点连接: {from_node_base_id} -> {to_node_base_id}")
            return success
        except Exception as e:
            logger.error(f"删除节点连接失败: {e}")
            raise
    
    async def get_workflow_connections(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的所有连接"""
        try:
            query = """
                SELECT nc.*, 
                       fn.node_base_id as from_node_base_id,
                       tn.node_base_id as to_node_base_id,
                       fn.name as from_node_name,
                       tn.name as to_node_name
                FROM node_connection nc
                JOIN node fn ON fn.node_id = nc.from_node_id
                JOIN node tn ON tn.node_id = nc.to_node_id
                JOIN workflow w ON w.workflow_id = nc.workflow_id
                WHERE w.workflow_base_id = $1 AND w.is_current_version = TRUE
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取工作流连接列表失败: {e}")
            raise
    
    async def get_node_outgoing_connections(self, node_base_id: uuid.UUID, 
                                          workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的出向连接"""
        try:
            query = """
                SELECT nc.*, tn.node_base_id as to_node_base_id, tn.name as to_node_name
                FROM node_connection nc
                JOIN node fn ON fn.node_id = nc.from_node_id
                JOIN node tn ON tn.node_id = nc.to_node_id
                JOIN workflow w ON w.workflow_id = nc.workflow_id
                WHERE fn.node_base_id = $1 AND w.workflow_base_id = $2 
                      AND w.is_current_version = TRUE
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取节点出向连接失败: {e}")
            raise
    
    async def get_node_incoming_connections(self, node_base_id: uuid.UUID, 
                                          workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的入向连接"""
        try:
            query = """
                SELECT nc.*, fn.node_base_id as from_node_base_id, fn.name as from_node_name
                FROM node_connection nc
                JOIN node fn ON fn.node_id = nc.from_node_id
                JOIN node tn ON tn.node_id = nc.to_node_id
                JOIN workflow w ON w.workflow_id = nc.workflow_id
                WHERE tn.node_base_id = $1 AND w.workflow_base_id = $2 
                      AND w.is_current_version = TRUE
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取节点入向连接失败: {e}")
            raise
    
    async def get_start_nodes(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的开始节点"""
        return await self.get_nodes_by_type(workflow_base_id, "start")
    
    async def get_end_nodes(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的结束节点"""
        return await self.get_nodes_by_type(workflow_base_id, "end")
    
    async def get_next_nodes(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID) -> List[uuid.UUID]:
        """获取节点的下游节点ID列表"""
        try:
            query = """
                SELECT tn.node_base_id as to_node_base_id
                FROM node_connection nc
                JOIN node fn ON fn.node_id = nc.from_node_id AND fn.is_current_version = TRUE
                JOIN node tn ON tn.node_id = nc.to_node_id AND tn.is_current_version = TRUE
                JOIN workflow w ON w.workflow_id = nc.workflow_id AND w.is_current_version = TRUE
                WHERE fn.node_base_id = $1 AND w.workflow_base_id = $2
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return [result['to_node_base_id'] for result in results]
        except Exception as e:
            logger.error(f"获取节点下游节点失败: {e}")
            raise