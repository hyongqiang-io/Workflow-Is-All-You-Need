"""
任务细分数据访问层
Task Subdivision Repository
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ..base import BaseRepository
from ...models.task_subdivision import (
    TaskSubdivision, TaskSubdivisionCreate, TaskSubdivisionUpdate,
    WorkflowAdoption, WorkflowAdoptionCreate,
    TaskSubdivisionStatus, SubWorkflowStatus
)
from ...utils.helpers import now_utc


class TaskSubdivisionRepository(BaseRepository[TaskSubdivision]):
    """任务细分数据访问层"""
    
    def __init__(self):
        super().__init__("task_subdivision")
    
    async def create_subdivision(self, subdivision_data: TaskSubdivisionCreate) -> Optional[Dict[str, Any]]:
        """创建任务细分"""
        try:
            subdivision_id = uuid.uuid4()
            
            logger.info(f"🔄 创建任务细分")
            logger.info(f"   细分名称: {subdivision_data.subdivision_name}")
            logger.info(f"   原始任务ID: {subdivision_data.original_task_id}")
            logger.info(f"   细分者ID: {subdivision_data.subdivider_id}")
            
            data = {
                "subdivision_id": subdivision_id,
                "original_task_id": subdivision_data.original_task_id,
                "subdivider_id": subdivision_data.subdivider_id,
                "subdivision_name": subdivision_data.subdivision_name,
                "subdivision_description": subdivision_data.subdivision_description,
                "sub_workflow_base_id": None,  # 将在创建子工作流后更新
                "sub_workflow_instance_id": None,
                "status": TaskSubdivisionStatus.CREATED.value,
                "parent_task_description": "",  # 将在后续更新
                "context_passed": subdivision_data.context_to_pass,
                "parent_subdivision_id": subdivision_data.parent_subdivision_id,  # 链式细分支持
                "is_selected": False,  # 默认未选择
                "selected_at": None,
                "subdivision_created_at": now_utc(),
                "created_at": now_utc(),
                "updated_at": now_utc(),
                "is_deleted": False
            }
            
            result = await self.create(data)
            
            if result:
                logger.info(f"✅ 任务细分创建成功: {subdivision_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"创建任务细分失败: {e}")
            raise
    
    async def update_subdivision_workflow_ids(self, subdivision_id: uuid.UUID, 
                                            sub_workflow_base_id: uuid.UUID,
                                            sub_workflow_instance_id: Optional[uuid.UUID] = None) -> bool:
        """更新细分的工作流ID"""
        try:
            update_data = {
                "sub_workflow_base_id": sub_workflow_base_id,
                "updated_at": now_utc()
            }
            
            if sub_workflow_instance_id:
                update_data["sub_workflow_instance_id"] = sub_workflow_instance_id
                update_data["status"] = TaskSubdivisionStatus.EXECUTING.value
            
            success = await self.update(subdivision_id, update_data, id_column="subdivision_id")
            
            if success:
                logger.info(f"✅ 更新细分工作流ID成功: {subdivision_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"更新细分工作流ID失败: {e}")
            raise
    
    async def update_subdivision_task_context(self, subdivision_id: uuid.UUID,
                                            parent_task_description: str) -> bool:
        """更新细分的任务上下文"""
        try:
            update_data = {
                "parent_task_description": parent_task_description,
                "updated_at": now_utc()
            }
            
            success = await self.update(subdivision_id, update_data, id_column="subdivision_id")
            return success
            
        except Exception as e:
            logger.error(f"更新细分任务上下文失败: {e}")
            raise
    
    async def update_subdivision_status(self, subdivision_id: uuid.UUID,
                                      update_data: Dict[str, Any]) -> bool:
        """更新细分状态"""
        try:
            logger.info(f"🔄 更新细分状态: {subdivision_id}")
            logger.info(f"   - 更新数据: {update_data}")
            
            # 添加更新时间
            update_data["updated_at"] = now_utc()
            
            success = await self.update(subdivision_id, update_data, id_column="subdivision_id")
            
            if success:
                logger.info(f"✅ 更新细分状态成功: {subdivision_id}")
            else:
                logger.error(f"❌ 更新细分状态失败: {subdivision_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"更新细分状态失败: {e}")
            raise
    
    async def get_subdivision_by_id(self, subdivision_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取任务细分"""
        try:
            query = """
            SELECT 
                ts.*,
                ti.task_title as original_task_title,
                u.username as subdivider_name,
                w.name as sub_workflow_name
            FROM task_subdivision ts
            LEFT JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
            LEFT JOIN "user" u ON ts.subdivider_id = u.user_id
            LEFT JOIN workflow w ON ts.sub_workflow_base_id = w.workflow_base_id 
                AND w.is_current_version = TRUE
            WHERE ts.subdivision_id = $1 AND ts.is_deleted = FALSE
            """
            
            result = await self.db.fetch_one(query, subdivision_id)
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"获取任务细分失败: {e}")
            raise
    
    async def get_subdivisions_by_task(self, task_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取任务的所有细分"""
        try:
            query = """
            SELECT 
                ts.*,
                u.username as subdivider_name,
                w.name as sub_workflow_name,
                -- 统计子工作流节点信息
                (SELECT COUNT(*) FROM node n 
                 WHERE n.workflow_base_id = ts.sub_workflow_base_id 
                 AND n.is_deleted = FALSE) as total_sub_nodes,
                -- 统计已完成的节点实例
                (SELECT COUNT(*) FROM node_instance ni 
                 JOIN node n ON ni.node_id = n.node_id
                 WHERE n.workflow_base_id = ts.sub_workflow_base_id 
                 AND ni.workflow_instance_id = ts.sub_workflow_instance_id
                 AND ni.status = 'completed'
                 AND ni.is_deleted = FALSE) as completed_sub_nodes
            FROM task_subdivision ts
            LEFT JOIN "user" u ON ts.subdivider_id = u.user_id
            LEFT JOIN workflow w ON ts.sub_workflow_base_id = w.workflow_base_id 
                AND w.is_current_version = TRUE
            WHERE ts.original_task_id = $1 AND ts.is_deleted = FALSE
            ORDER BY ts.subdivision_created_at DESC
            """
            
            results = await self.db.fetch_all(query, task_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取任务细分列表失败: {e}")
            raise
    
    async def get_subdivisions_by_workflow(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流相关的所有细分（用于预览）"""
        try:
            query = """
            SELECT 
                ts.*,
                ti.task_title as original_task_title,
                u.username as subdivider_name,
                w.name as sub_workflow_name,
                -- 统计子工作流信息
                (SELECT COUNT(*) FROM node n 
                 WHERE n.workflow_base_id = ts.sub_workflow_base_id 
                 AND n.is_deleted = FALSE) as total_sub_nodes,
                (SELECT COUNT(*) FROM node_instance ni 
                 JOIN node n ON ni.node_id = n.node_id
                 WHERE n.workflow_base_id = ts.sub_workflow_base_id 
                 AND ni.workflow_instance_id = ts.sub_workflow_instance_id
                 AND ni.status = 'completed'
                 AND ni.is_deleted = FALSE) as completed_sub_nodes
            FROM task_subdivision ts
            LEFT JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
            LEFT JOIN "user" u ON ts.subdivider_id = u.user_id
            LEFT JOIN workflow w ON ts.sub_workflow_base_id = w.workflow_base_id 
                AND w.is_current_version = TRUE
            WHERE ti.workflow_instance_id IN (
                SELECT workflow_instance_id 
                FROM workflow_instance 
                WHERE workflow_base_id = $1 
                AND is_deleted = FALSE
            )
            AND ts.is_deleted = FALSE
            ORDER BY ts.subdivision_created_at DESC
            """
            
            results = await self.db.fetch_all(query, workflow_base_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取工作流细分列表失败: {e}")
            raise
    
    async def get_subdivisions_by_subdivider(self, subdivider_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取用户创建的所有细分"""
        try:
            query = """
            SELECT 
                ts.*,
                ti.task_title as original_task_title,
                w.name as sub_workflow_name,
                (SELECT COUNT(*) FROM node n 
                 WHERE n.workflow_base_id = ts.sub_workflow_base_id 
                 AND n.is_deleted = FALSE) as total_sub_nodes
            FROM task_subdivision ts
            LEFT JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
            LEFT JOIN workflow w ON ts.sub_workflow_base_id = w.workflow_base_id 
                AND w.is_current_version = TRUE
            WHERE ts.subdivider_id = $1 AND ts.is_deleted = FALSE
            ORDER BY ts.subdivision_created_at DESC
            """
            
            results = await self.db.fetch_all(query, subdivider_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取用户细分列表失败: {e}")
            raise
    
    async def update_subdivision_status(self, subdivision_id: uuid.UUID, 
                                      status: TaskSubdivisionStatus) -> bool:
        """更新细分状态"""
        try:
            update_data = {
                "status": status.value,
                "updated_at": now_utc()
            }
            
            if status == TaskSubdivisionStatus.COMPLETED:
                update_data["completed_at"] = now_utc()
            
            success = await self.update(subdivision_id, update_data, id_column="subdivision_id")
            return success
            
        except Exception as e:
            logger.error(f"更新细分状态失败: {e}")
            raise
    
    async def delete_subdivision(self, subdivision_id: uuid.UUID, soft_delete: bool = True) -> bool:
        """删除任务细分"""
        try:
            if soft_delete:
                success = await self.soft_delete(subdivision_id)
            else:
                success = await self.hard_delete(subdivision_id)
                
            if success:
                logger.info(f"✅ 删除任务细分成功: {subdivision_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"删除任务细分失败: {e}")
            raise

    async def get_subdivision_hierarchy(self, root_subdivision_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取细分的完整层级结构"""
        try:
            query = """
            WITH RECURSIVE subdivision_tree AS (
                -- 基础情况：指定的根节点
                SELECT ts.*, 0 as depth, ARRAY[ts.subdivision_id] as path
                FROM task_subdivision ts
                WHERE ts.subdivision_id = $1 AND ts.is_deleted = FALSE
                
                UNION ALL
                
                -- 递归情况：子级细分
                SELECT ts.*, st.depth + 1, st.path || ts.subdivision_id
                FROM task_subdivision ts
                JOIN subdivision_tree st ON ts.parent_subdivision_id = st.subdivision_id
                WHERE ts.is_deleted = FALSE
            )
            SELECT st.*, 
                   ti.task_title as original_task_title,
                   u.username as subdivider_name
            FROM subdivision_tree st
            LEFT JOIN task_instance ti ON st.original_task_id = ti.task_instance_id
            LEFT JOIN "user" u ON st.subdivider_id = u.user_id
            ORDER BY depth, subdivision_created_at
            """
            
            results = await self.db.fetch_all(query, root_subdivision_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取细分层级结构失败: {e}")
            raise

    async def get_subdivision_children(self, parent_subdivision_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取指定细分的直接子级"""
        try:
            query = """
            SELECT ts.*, 
                   ti.task_title as original_task_title,
                   u.username as subdivider_name,
                   w.name as sub_workflow_name
            FROM task_subdivision ts
            LEFT JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
            LEFT JOIN "user" u ON ts.subdivider_id = u.user_id
            LEFT JOIN workflow w ON ts.sub_workflow_base_id = w.workflow_base_id 
                AND w.is_current_version = TRUE
            WHERE ts.parent_subdivision_id = $1 AND ts.is_deleted = FALSE
            ORDER BY ts.subdivision_created_at ASC
            """
            
            results = await self.db.fetch_all(query, parent_subdivision_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取子级细分失败: {e}")
            raise


class WorkflowAdoptionRepository(BaseRepository[WorkflowAdoption]):
    """工作流采纳数据访问层"""
    
    def __init__(self):
        super().__init__("workflow_adoption")
    
    async def create_adoption(self, adoption_data: WorkflowAdoptionCreate, 
                            new_nodes: List[uuid.UUID]) -> Optional[Dict[str, Any]]:
        """创建工作流采纳记录"""
        try:
            adoption_id = uuid.uuid4()
            
            logger.info(f"🔄 创建工作流采纳记录")
            logger.info(f"   采纳名称: {adoption_data.adoption_name}")
            logger.info(f"   细分ID: {adoption_data.subdivision_id}")
            logger.info(f"   目标节点ID: {adoption_data.target_node_id}")
            logger.info(f"   新增节点数: {len(new_nodes)}")
            
            data = {
                "adoption_id": adoption_id,
                "subdivision_id": adoption_data.subdivision_id,
                "original_workflow_base_id": adoption_data.original_workflow_base_id,
                "adopter_id": adoption_data.adopter_id,
                "adoption_name": adoption_data.adoption_name,
                "target_node_id": adoption_data.target_node_id,
                "new_nodes_added": new_nodes,
                "adopted_at": now_utc(),
                "created_at": now_utc(),
                "updated_at": now_utc(),
                "is_deleted": False
            }
            
            result = await self.create(data)
            
            if result:
                logger.info(f"✅ 工作流采纳记录创建成功: {adoption_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"创建工作流采纳记录失败: {e}")
            raise
    
    async def get_adoptions_by_workflow(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的所有采纳记录"""
        try:
            query = """
            SELECT 
                wa.*,
                ts.subdivision_name,
                u.username as adopter_name
            FROM workflow_adoption wa
            LEFT JOIN task_subdivision ts ON wa.subdivision_id = ts.subdivision_id
            LEFT JOIN "user" u ON wa.adopter_id = u.user_id
            WHERE wa.original_workflow_base_id = $1 AND wa.is_deleted = FALSE
            ORDER BY wa.adopted_at DESC
            """
            
            results = await self.db.fetch_all(query, workflow_base_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取工作流采纳记录失败: {e}")
            raise