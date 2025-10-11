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
                WHERE workflow_base_id = %s AND is_current_version = 1 AND is_deleted = 0
            """
            workflow_result = await self.db.fetch_one(workflow_query, node_data.workflow_base_id)
            if not workflow_result:
                raise ValueError(f"工作流 {node_data.workflow_base_id} 不存在或没有当前版本")
            
            workflow_id = workflow_result['workflow_id']
            
            # 准备数据
            node_base_id = uuid.uuid4()  # 预生成node_base_id确保唯一性
            data = {
                "node_id": uuid.uuid4(),
                "node_base_id": node_base_id,
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
            
            # 创建记录并处理时序问题
            result = await self.create(data)
            
            # 如果fetch_one返回了错误的记录（由于时序问题），用精确查询替代
            if result and result.get('node_base_id') != node_base_id:
                logger.warning(f"检测到时序问题，使用精确查询获取节点: {node_base_id}")
                accurate_query = """
                    SELECT * FROM node 
                    WHERE node_base_id = %s AND workflow_base_id = %s
                """
                accurate_result = await self.db.fetch_one(accurate_query, node_base_id, node_data.workflow_base_id)
                if accurate_result:
                    return accurate_result
                else:
                    # 如果精确查询也失败，返回我们知道应该插入的数据
                    logger.warning(f"精确查询失败，返回预期数据: {node_base_id}")
                    return data
            
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
                WHERE node_base_id = %s 
                AND workflow_base_id = %s
                AND is_current_version = 1
                AND is_deleted = 0
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
            logger.info(f"[DEBUG] 开始更新节点，node_base_id={node_base_id}, workflow_base_id={workflow_base_id}")
            
            # 先查询当前节点信息
            existing_node = await self.get_node_by_base_id(node_base_id, workflow_base_id)
            if not existing_node:
                logger.error(f"[DEBUG] 节点不存在: node_base_id={node_base_id}")
                return None
            
            logger.info(f"[DEBUG] 找到现有节点: node_id={existing_node.get('node_id')}, node_base_id={existing_node.get('node_base_id')}")
            logger.info(f"[DEBUG] 节点当前版本: {existing_node.get('is_current_version')}, 已删除: {existing_node.get('is_deleted')}")
            
            # 构建更新字段 - 检查是否真的需要更新
            update_fields = []
            params = []
            param_index = 1
            has_changes = False
            
            logger.info(f"[DEBUG] 更新数据: name={node_data.name}, type={node_data.type}, position=({node_data.position_x}, {node_data.position_y})")
            logger.info(f"[DEBUG] 当前数据: name={existing_node.get('name')}, type={existing_node.get('type')}, position=({existing_node.get('position_x')}, {existing_node.get('position_y')})")
            
            if node_data.name is not None and node_data.name != existing_node.get('name'):
                update_fields.append(f"name = ${param_index}")
                params.append(node_data.name)
                param_index += 1
                has_changes = True
            
            if node_data.type is not None and node_data.type.value != existing_node.get('type'):
                update_fields.append(f"type = ${param_index}")
                params.append(node_data.type.value)
                param_index += 1
                has_changes = True
            
            if node_data.task_description is not None and node_data.task_description != existing_node.get('task_description'):
                update_fields.append(f"task_description = ${param_index}")
                params.append(node_data.task_description)
                param_index += 1
                has_changes = True
            
            if node_data.position_x is not None:
                new_x = int(node_data.position_x)
                current_x = int(existing_node.get('position_x', 0))
                if new_x != current_x:
                    update_fields.append(f"position_x = ${param_index}")
                    params.append(new_x)
                    param_index += 1
                    has_changes = True
            
            if node_data.position_y is not None:
                new_y = int(node_data.position_y)
                current_y = int(existing_node.get('position_y', 0))
                if new_y != current_y:
                    update_fields.append(f"position_y = ${param_index}")
                    params.append(new_y)
                    param_index += 1
                    has_changes = True
            
            if not has_changes:
                # 没有实际变化，直接返回现有数据
                logger.info(f"[DEBUG] 节点数据无变化，跳过更新: {node_base_id}")
                return existing_node
            
            # 添加WHERE条件参数
            params.extend([node_base_id, workflow_base_id])
            
            logger.info(f"[DEBUG] 更新字段: {update_fields}")
            logger.info(f"[DEBUG] 更新参数: {params}")
            logger.info(f"[DEBUG] WHERE条件: node_base_id={node_base_id}, workflow_base_id={workflow_base_id}")
            
            # 构建和执行更新查询（MySQL不支持RETURNING）
            query = f"""
                UPDATE node 
                SET {', '.join(update_fields)}
                WHERE node_base_id = %s 
                  AND workflow_base_id = %s
                  AND is_current_version = 1
                  AND is_deleted = 0
            """
            
            logger.info(f"[DEBUG] 执行UPDATE查询: {query}")
            
            # 执行更新
            await self.db.execute(query, *params)
            
            # 查询更新后的结果
            result = await self.get_node_by_base_id(node_base_id, workflow_base_id)
            
            logger.info(f"[DEBUG] UPDATE查询结果类型: {type(result)}")
            logger.info(f"[DEBUG] UPDATE查询结果: {result}")
            
            # 处理DatabaseManager返回的UPDATE成功响应
            if result and result.get("_update_success"):
                logger.warning(f"数据库更新成功但无法获取完整记录，节点: {node_base_id}")
                # 尝试查询刚更新的记录
                try:
                    fallback_result = await self.get_node_by_base_id(node_base_id, workflow_base_id)
                    if fallback_result:
                        logger.info(f"通过fallback查询成功获取更新节点")
                        return fallback_result
                except Exception as fallback_e:
                    logger.error(f"Fallback查询失败: {fallback_e}")
                
                logger.warning(f"Fallback查询失败，返回成功标记")
                return {"_update_success": True, "node_base_id": str(node_base_id)}
            
            if result:
                logger.info(f"更新节点成功: {node_base_id}")
                return result
            else:
                logger.warning(f"未找到要更新的节点: {node_base_id}")
                logger.warning(f"[DEBUG] 可能的原因:")
                logger.warning(f"[DEBUG] 1. node_base_id不存在: {node_base_id}")
                logger.warning(f"[DEBUG] 2. workflow_base_id不匹配: {workflow_base_id}")
                logger.warning(f"[DEBUG] 3. is_current_version != TRUE")
                logger.warning(f"[DEBUG] 4. is_deleted = TRUE")
                
                # 执行诊断查询
                diagnostic_query = """
                    SELECT node_id, node_base_id, workflow_base_id, is_current_version, is_deleted
                    FROM node 
                    WHERE node_base_id = %s AND workflow_base_id = %s
                """
                diagnostic_result = await self.db.fetch_all(diagnostic_query, node_base_id, workflow_base_id)
                logger.warning(f"[DEBUG] 诊断查询结果: {diagnostic_result}")
                
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
                    SET is_deleted = 1 
                    WHERE node_base_id = %s AND workflow_base_id = %s
                """
            else:
                query = """
                    DELETE FROM node 
                    WHERE node_base_id = %s AND workflow_base_id = %s
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
                LEFT JOIN node_processor np ON np.node_id = n.node_id AND np.is_deleted = 0
                WHERE n.workflow_base_id = %s 
                AND n.is_current_version = 1
                AND n.is_deleted = 0
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
                WHERE workflow_base_id = %s AND type = %s 
                AND is_current_version = 1
                AND is_deleted = 0
                ORDER BY created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_base_id, node_type)
            return results
        except Exception as e:
            logger.error(f"根据类型获取节点列表失败: {e}")
            raise
    
    async def get_workflow_connections(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的所有连接"""
        try:
            # 修改查询逻辑：使用node_base_id来查找连接，而不是依赖workflow_id版本
            query = """
                SELECT DISTINCT
                       nc.from_node_id,
                       nc.to_node_id,
                       nc.connection_type,
                       nc.condition_config,
                       nc.created_at,
                       fn.node_base_id as from_node_base_id,
                       tn.node_base_id as to_node_base_id,
                       fn.name as from_node_name,
                       tn.name as to_node_name
                FROM node_connection nc
                JOIN node fn ON fn.node_id = nc.from_node_id
                JOIN node tn ON tn.node_id = nc.to_node_id
                WHERE fn.workflow_base_id = %s
                  AND tn.workflow_base_id = %s
                  AND fn.is_current_version = 1
                  AND tn.is_current_version = 1
                  AND fn.is_deleted = 0
                  AND tn.is_deleted = 0
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_base_id, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取工作流连接列表失败: {e}")
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
                WHERE node_base_id = %s AND workflow_base_id = %s 
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
                WHERE workflow_base_id = %s AND is_current_version = 1 AND is_deleted = 0
            """
            workflow = await self.db.fetch_one(workflow_query, connection_data.workflow_base_id)
            if not workflow:
                raise ValueError("工作流不存在")
            
            # 检查连接是否已存在
            check_query = """
                SELECT * FROM node_connection 
                WHERE from_node_id = %s AND to_node_id = %s AND workflow_id = %s
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
            
            # 创建连接（MySQL不支持RETURNING）
            query = """
                INSERT INTO node_connection 
                (from_node_id, to_node_id, workflow_id, connection_type, condition_config, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            # 处理condition_config的JSON序列化
            condition_config = connection_data.condition_config
            if isinstance(condition_config, dict):
                condition_config = safe_json_dumps(condition_config)
            
            await self.db.execute(
                query,
                from_node['node_id'],
                to_node['node_id'],
                workflow['workflow_id'],
                connection_data.connection_type.value,
                condition_config,
                now_utc()
            )
            
            # 查询刚插入的记录
            result = await self.get_connection(
                from_node['node_id'],
                to_node['node_id'], 
                workflow['workflow_id']
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
                WHERE from_node_id = %s AND to_node_id = %s AND workflow_id = %s
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
            logger.info(f"开始更新连接")

            update_dict = {}
            if update_data.connection_type is not None:
                update_dict["connection_type"] = update_data.connection_type.value
            if update_data.condition_config is not None:
                # 处理condition_config的JSON序列化
                condition_config = update_data.condition_config
                if isinstance(condition_config, dict):
                    condition_config = safe_json_dumps(condition_config)
                update_dict["condition_config"] = condition_config

            logger.info(f"构建的更新字典: {update_dict}")

            if not update_dict:
                return await self.get_connection(from_node_id, to_node_id, workflow_id)

            set_clauses = []
            values = []

            for key, value in update_dict.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)

            query = f"""
                UPDATE node_connection
                SET {', '.join(set_clauses)}
                WHERE from_node_id = %s AND to_node_id = %s
                      AND workflow_id = %s
            """

            # MySQL不支持RETURNING，需要先执行UPDATE，再查询结果
            values.extend([from_node_id, to_node_id, workflow_id])

            logger.info(f"执行SQL: {query}")
            logger.info(f"参数值: {values}")

            await self.db.execute(query, *values)

            # 查询更新后的结果
            result = await self.get_connection(from_node_id, to_node_id, workflow_id)

            logger.info(f"更新后查询结果: {result}")

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
                SELECT node_id FROM node 
                WHERE node_base_id = %s AND workflow_base_id = %s
                AND is_current_version = 1
                AND is_deleted = 0
            """
            from_node = await self.db.fetch_one(node_query, from_node_base_id, workflow_base_id)
            to_node = await self.db.fetch_one(node_query, to_node_base_id, workflow_base_id)
            
            if not from_node or not to_node:
                raise ValueError("源节点或目标节点不存在")
            
            # 获取工作流ID
            workflow_query = """
                SELECT workflow_id FROM workflow 
                WHERE workflow_base_id = %s AND is_current_version = 1
            """
            workflow = await self.db.fetch_one(workflow_query, workflow_base_id)
            if not workflow:
                raise ValueError("工作流不存在")
            
            query = """
                DELETE FROM node_connection 
                WHERE from_node_id = %s AND to_node_id = %s AND workflow_id = %s
            """
            result = await self.db.execute(query, from_node['node_id'], to_node['node_id'], workflow['workflow_id'])
            success = "1" in result
            if success:
                logger.info(f"删除了节点连接: {from_node_base_id} -> {to_node_base_id}")
            return success
        except Exception as e:
            logger.error(f"删除节点连接失败: {e}")
            raise

    async def update_node_connection(self, from_node_id: uuid.UUID, to_node_id: uuid.UUID,
                                   workflow_id: uuid.UUID,
                                   update_data: 'NodeConnectionUpdate') -> Optional[Dict[str, Any]]:
        """更新节点连接 - service层调用的接口"""
        return await self.update_connection(from_node_id, to_node_id, workflow_id, update_data)

    async def get_workflow_connections(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的所有连接"""
        try:
            # 修改查询逻辑：使用node_base_id来查找连接，而不是依赖workflow_id版本
            query = """
                SELECT DISTINCT
                       nc.from_node_id,
                       nc.to_node_id,
                       nc.connection_type,
                       nc.condition_config,
                       nc.created_at,
                       fn.node_base_id as from_node_base_id,
                       tn.node_base_id as to_node_base_id,
                       fn.name as from_node_name,
                       tn.name as to_node_name
                FROM node_connection nc
                JOIN node fn ON fn.node_id = nc.from_node_id
                JOIN node tn ON tn.node_id = nc.to_node_id
                WHERE fn.workflow_base_id = %s
                  AND tn.workflow_base_id = %s
                  AND fn.is_current_version = 1
                  AND tn.is_current_version = 1
                  AND fn.is_deleted = 0
                  AND tn.is_deleted = 0
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_base_id, workflow_base_id)
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
                WHERE fn.node_base_id = %s AND w.workflow_base_id = %s 
                      AND w.is_current_version = 1
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
                WHERE tn.node_base_id = %s AND w.workflow_base_id = %s 
                      AND w.is_current_version = 1
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取节点入向连接失败: {e}")
            raise
    
    
    async def get_nodes_by_type(self, workflow_base_id: uuid.UUID, 
                               node_type: str) -> List[Dict[str, Any]]:
        """根据类型获取节点列表"""
        try:
            query = """
                SELECT * FROM node 
                WHERE workflow_base_id = %s AND type = %s 
                AND is_current_version = 1
                AND is_deleted = 0
                ORDER BY created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_base_id, node_type)
            return results
        except Exception as e:
            logger.error(f"根据类型获取节点列表失败: {e}")
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
                JOIN node fn ON fn.node_id = nc.from_node_id AND fn.is_current_version = 1
                JOIN node tn ON tn.node_id = nc.to_node_id AND tn.is_current_version = 1
                JOIN workflow w ON w.workflow_id = nc.workflow_id AND w.is_current_version = 1
                WHERE fn.node_base_id = %s AND w.workflow_base_id = %s
                ORDER BY nc.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return [result['to_node_base_id'] for result in results]
        except Exception as e:
            logger.error(f"获取节点下游节点失败: {e}")
            raise