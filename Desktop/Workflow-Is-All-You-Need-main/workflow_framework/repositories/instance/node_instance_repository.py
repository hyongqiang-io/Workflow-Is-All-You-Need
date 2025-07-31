"""
节点实例数据访问层
Node Instance Repository
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ..base import BaseRepository
from ...models.instance import (
    NodeInstance, NodeInstanceCreate, NodeInstanceUpdate, NodeInstanceStatus
)
from ...utils.helpers import now_utc


class NodeInstanceRepository(BaseRepository[NodeInstance]):
    """节点实例数据访问层"""
    
    def __init__(self):
        super().__init__("node_instance")
    
    async def create_node_instance(self, instance_data: NodeInstanceCreate) -> Optional[Dict[str, Any]]:
        """创建节点实例"""
        node_instance_id = uuid.uuid4()
        logger.info(f"🚀 开始创建节点实例: {instance_data.node_instance_name or '无名称'}")
        logger.info(f"   - 节点实例ID: {node_instance_id}")
        logger.info(f"   - 工作流实例ID: {instance_data.workflow_instance_id}")
        logger.info(f"   - 节点ID: {instance_data.node_id}")
        logger.info(f"   - 初始状态: {instance_data.status.value}")
        
        try:
            # 验证工作流实例是否存在
            logger.info(f"🔍 验证工作流实例: {instance_data.workflow_instance_id}")
            workflow_instance_query = """
                SELECT workflow_instance_id FROM workflow_instance 
                WHERE workflow_instance_id = $1 AND is_deleted = FALSE
            """
            workflow_instance_result = await self.db.fetch_one(
                workflow_instance_query, instance_data.workflow_instance_id
            )
            if not workflow_instance_result:
                logger.error(f"❌ 工作流实例不存在: {instance_data.workflow_instance_id}")
                raise ValueError(f"工作流实例 {instance_data.workflow_instance_id} 不存在")
            logger.info(f"✅ 工作流实例验证成功")
            
            # 验证节点是否存在
            logger.info(f"🔍 验证节点: {instance_data.node_id}")
            node_query = "SELECT node_id, name, type FROM node WHERE node_id = $1 AND is_deleted = FALSE"
            node_result = await self.db.fetch_one(node_query, instance_data.node_id)
            if not node_result:
                logger.error(f"❌ 节点不存在: {instance_data.node_id}")
                raise ValueError(f"节点 {instance_data.node_id} 不存在")
            logger.info(f"✅ 节点验证成功: {node_result['name']} (类型: {node_result['type']})")
            
            # 准备数据
            logger.info(f"📝 准备节点实例数据")
            data = {
                "node_instance_id": node_instance_id,
                "workflow_instance_id": instance_data.workflow_instance_id,
                "node_id": instance_data.node_id,
                "node_instance_name": instance_data.node_instance_name or node_result['name'],
                "task_description": instance_data.task_description,
                "status": instance_data.status.value,
                "input_data": instance_data.input_data,
                "output_data": instance_data.output_data,
                "error_message": instance_data.error_message,
                "retry_count": instance_data.retry_count or 0,
                "created_at": now_utc(),
            }
            logger.info(f"   - 节点实例名称: {data['node_instance_name']}")
            logger.info(f"   - 任务描述: {data['task_description'] or '无'}")
            logger.info(f"   - 重试次数: {data['retry_count']}")
            
            logger.info(f"💾 写入数据库: 节点实例 {node_instance_id}")
            result = await self.create(data)
            if result:
                logger.info(f"✅ 节点实例创建成功!")
                logger.info(f"   - 实例ID: {result['node_instance_id']}")
                logger.info(f"   - 实例名称: {result.get('node_instance_name', '无名称')}")
                logger.info(f"   - 状态: {result.get('status', 'unknown')}")
                logger.info(f"   - 创建时间: {result.get('created_at', 'unknown')}")
            else:
                logger.error(f"❌ 节点实例创建失败: 数据库返回空结果")
            return result
        except Exception as e:
            logger.error(f"❌ 创建节点实例失败: {e}")
            logger.error(f"   - 节点实例ID: {node_instance_id}")
            logger.error(f"   - 工作流实例ID: {instance_data.workflow_instance_id}")
            logger.error(f"   - 节点ID: {instance_data.node_id}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            raise
    
    async def get_instance_by_id(self, instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取节点实例"""
        return await self.get_by_id(instance_id, "node_instance_id")
    
    async def get_instance_with_details(self, instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取节点实例详细信息"""
        try:
            query = """
                SELECT ni.*,
                       n.name as node_name,
                       n.type as node_type,
                       wi.workflow_instance_name
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                JOIN workflow_instance wi ON wi.workflow_instance_id = ni.workflow_instance_id
                WHERE ni.node_instance_id = $1
            """
            result = await self.db.fetch_one(query, instance_id)
            return result
        except Exception as e:
            logger.error(f"获取节点实例详细信息失败: {e}")
            raise
    
    async def update_node_instance(self, instance_id: uuid.UUID, update_data: NodeInstanceUpdate) -> Optional[Dict[str, Any]]:
        """更新节点实例"""
        try:
            # 构建更新字段
            update_fields = {}
            
            if update_data.status is not None:
                update_fields["status"] = update_data.status.value
            
            if update_data.input_data is not None:
                update_fields["input_data"] = update_data.input_data
            if update_data.output_data is not None:
                update_fields["output_data"] = update_data.output_data  
            if update_data.error_message is not None:
                update_fields["error_message"] = update_data.error_message
            if update_data.retry_count is not None:
                update_fields["retry_count"] = update_data.retry_count
            
            # 添加更新时间
            update_fields["updated_at"] = now_utc()
            
            logger.info(f"💾 更新节点实例数据库: {instance_id}")
            logger.info(f"   - 更新字段: {list(update_fields.keys())}")
            result = await self.update(instance_id, update_fields, "node_instance_id")
            if result:
                logger.info(f"✅ 节点实例更新成功!")
                logger.info(f"   - 实例ID: {instance_id}")
                if update_data.status:
                    logger.info(f"   - 新状态: {update_data.status.value}")
            else:
                logger.error(f"❌ 节点实例更新失败: 数据库返回空结果")
            return result
        except Exception as e:
            logger.error(f"更新节点实例失败: {e}")
            raise
    
    async def update_instance_status(self, instance_id: uuid.UUID,
                                   status: NodeInstanceStatus,
                                   input_data: Optional[Dict[str, Any]] = None,
                                   output_data: Optional[Dict[str, Any]] = None,
                                   error_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """更新节点实例状态"""
        try:
            update_data = {"status": status.value}
            
            # 根据状态设置时间字段
            if status == NodeInstanceStatus.RUNNING:
                update_data["start_at"] = now_utc()
            elif status in [NodeInstanceStatus.COMPLETED, NodeInstanceStatus.FAILED, NodeInstanceStatus.CANCELLED]:
                update_data["completed_at"] = now_utc()
            
            if input_data is not None:
                update_data["input_data"] = input_data
            if output_data is not None:
                update_data["output_data"] = output_data
            if error_message:
                update_data["error_message"] = error_message
            
            result = await self.update(instance_id, update_data, "node_instance_id")
            if result:
                logger.info(f"更新节点实例 {instance_id} 状态为 {status.value}")
            return result
        except Exception as e:
            logger.error(f"更新节点实例状态失败: {e}")
            raise
    
    async def increment_retry_count(self, instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """增加重试次数"""
        try:
            query = """
                UPDATE node_instance 
                SET retry_count = retry_count + 1 
                WHERE node_instance_id = $1
                RETURNING *
            """
            result = await self.db.fetch_one(query, instance_id)
            if result:
                logger.info(f"节点实例 {instance_id} 重试次数增加到 {result['retry_count']}")
            return result
        except Exception as e:
            logger.error(f"增加重试次数失败: {e}")
            raise
    
    async def get_instances_by_workflow_instance(self, workflow_instance_id: uuid.UUID,
                                               status: Optional[NodeInstanceStatus] = None) -> List[Dict[str, Any]]:
        """获取工作流实例的节点实例列表"""
        try:
            query = """
                SELECT ni.*,
                       n.name as node_name,
                       n.type as node_type
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                WHERE ni.workflow_instance_id = $1
            """
            params = [workflow_instance_id]
            
            if status:
                query += " AND ni.status = $2"
                params.append(status.value)
            
            query += " ORDER BY ni.created_at ASC"
            
            results = await self.db.fetch_all(query, *params)
            return results
        except Exception as e:
            logger.error(f"获取工作流实例的节点实例列表失败: {e}")
            raise
    
    async def get_instances_by_node(self, node_id: uuid.UUID,
                                  status: Optional[NodeInstanceStatus] = None,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """获取节点的实例列表"""
        try:
            query = """
                SELECT ni.*,
                       n.name as node_name,
                       wi.workflow_instance_name
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                JOIN workflow_instance wi ON wi.workflow_instance_id = ni.workflow_instance_id
                WHERE ni.node_id = $1
            """
            params = [node_id]
            
            if status:
                query += " AND ni.status = $2"
                params.append(status.value)
            
            query += " ORDER BY ni.created_at DESC LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            results = await self.db.fetch_all(query, *params)
            return results
        except Exception as e:
            logger.error(f"获取节点实例列表失败: {e}")
            raise
    
    async def get_pending_instances(self) -> List[Dict[str, Any]]:
        """获取所有等待执行的节点实例"""
        try:
            query = """
                SELECT ni.*,
                       n.name as node_name,
                       n.type as node_type,
                       wi.workflow_instance_name
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                JOIN workflow_instance wi ON wi.workflow_instance_id = ni.workflow_instance_id
                WHERE ni.status = $1
                ORDER BY ni.created_at ASC
            """
            results = await self.db.fetch_all(query, NodeInstanceStatus.PENDING.value)
            return results
        except Exception as e:
            logger.error(f"获取等待执行的节点实例失败: {e}")
            raise
    
    async def get_running_instances(self) -> List[Dict[str, Any]]:
        """获取所有运行中的节点实例"""
        try:
            query = """
                SELECT ni.*,
                       n.name as node_name,
                       n.type as node_type,
                       wi.workflow_instance_name
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                JOIN workflow_instance wi ON wi.workflow_instance_id = ni.workflow_instance_id
                WHERE ni.status = $1
                ORDER BY ni.start_at ASC
            """
            results = await self.db.fetch_all(query, NodeInstanceStatus.RUNNING.value)
            return results
        except Exception as e:
            logger.error(f"获取运行中的节点实例失败: {e}")
            raise
    
    async def get_next_executable_instances(self, workflow_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取下一个可执行的节点实例（基于节点连接关系）"""
        try:
            # 这个查询需要根据节点连接关系来确定哪些节点可以执行
            # 可执行的节点是：1）没有入向连接的节点，或 2）所有前置节点都已完成的节点
            query = """
                WITH executable_nodes AS (
                    -- 获取没有入向连接的节点（起始节点）
                    SELECT n.node_id
                    FROM node n
                    JOIN workflow_node wn ON wn.node_id = n.node_id
                    JOIN workflow_instance wi ON wi.workflow_id = wn.workflow_id
                    WHERE wi.workflow_instance_id = $1
                      AND n.node_id NOT IN (
                          SELECT DISTINCT nc.to_node_id 
                          FROM node_connection nc
                      )
                    
                    UNION
                    
                    -- 获取所有前置节点都已完成的节点
                    SELECT nc.to_node_id as node_id
                    FROM node_connection nc
                    JOIN node n ON n.node_id = nc.to_node_id
                    JOIN workflow_node wn ON wn.node_id = n.node_id
                    JOIN workflow_instance wi ON wi.workflow_id = wn.workflow_id
                    WHERE wi.workflow_instance_id = $1
                      AND NOT EXISTS (
                          SELECT 1 
                          FROM node_connection nc2
                          JOIN node_instance ni ON ni.node_id = nc2.from_node_id
                          WHERE nc2.to_node_id = nc.to_node_id
                            AND ni.workflow_instance_id = $1
                            AND ni.status != 'completed'
                      )
                )
                SELECT ni.*,
                       n.name as node_name,
                       n.type as node_type
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                JOIN executable_nodes en ON en.node_id = ni.node_id
                WHERE ni.workflow_instance_id = $1
                  AND ni.status = 'pending'
                ORDER BY ni.created_at ASC
            """
            results = await self.db.fetch_all(query, workflow_instance_id)
            return results
        except Exception as e:
            logger.error(f"获取下一个可执行的节点实例失败: {e}")
            raise
    
    async def cancel_pending_instances(self, workflow_instance_id: uuid.UUID) -> int:
        """取消工作流实例中所有等待执行的节点实例"""
        try:
            query = """
                UPDATE node_instance 
                SET status = 'cancelled', completed_at = NOW()
                WHERE workflow_instance_id = $1 AND status = 'pending'
            """
            result = await self.db.execute(query, workflow_instance_id)
            
            # 解析更新的记录数
            updated_count = int(result.split()[1]) if result.split()[1].isdigit() else 0
            logger.info(f"取消了 {updated_count} 个等待执行的节点实例")
            return updated_count
        except Exception as e:
            logger.error(f"取消等待执行的节点实例失败: {e}")
            raise
    
    async def get_instance_execution_path(self, workflow_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流实例的执行路径"""
        try:
            query = """
                SELECT ni.*,
                       n.name as node_name,
                       n.type as node_type,
                       CASE 
                           WHEN ni.completed_at IS NOT NULL AND ni.start_at IS NOT NULL 
                           THEN EXTRACT(EPOCH FROM (ni.completed_at - ni.start_at))::INTEGER
                           ELSE NULL
                       END as duration_seconds
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                WHERE ni.workflow_instance_id = $1
                ORDER BY 
                    CASE WHEN ni.start_at IS NOT NULL THEN ni.start_at ELSE ni.created_at END ASC
            """
            results = await self.db.fetch_all(query, workflow_instance_id)
            return results
        except Exception as e:
            logger.error(f"获取工作流实例执行路径失败: {e}")
            raise
    
    async def get_failed_instances_with_retries(self, max_retry_count: int = 3) -> List[Dict[str, Any]]:
        """获取失败但可重试的节点实例"""
        try:
            query = """
                SELECT ni.*,
                       n.name as node_name,
                       n.type as node_type,
                       wi.workflow_instance_name
                FROM node_instance ni
                JOIN node n ON n.node_id = ni.node_id
                JOIN workflow_instance wi ON wi.workflow_instance_id = ni.workflow_instance_id
                WHERE ni.status = 'failed' 
                  AND ni.retry_count < $1
                  AND wi.status != 'cancelled'
                ORDER BY ni.completed_at ASC
            """
            results = await self.db.fetch_all(query, max_retry_count)
            return results
        except Exception as e:
            logger.error(f"获取可重试的失败节点实例失败: {e}")
            raise