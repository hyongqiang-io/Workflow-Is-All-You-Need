"""
工作流数据访问层
Workflow Repository
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..base import BaseRepository
from ...models.workflow import (
    Workflow, WorkflowCreate, WorkflowUpdate, WorkflowVersion, 
    WorkflowVersionCreate, WorkflowUser, WorkflowUserAdd
)
from ...utils.helpers import now_utc


class WorkflowRepository(BaseRepository[Workflow]):
    """工作流数据访问层"""
    
    def __init__(self):
        super().__init__("workflow")
    
    async def create_workflow(self, workflow_data: WorkflowCreate) -> Optional[Dict[str, Any]]:
        """创建工作流（使用初始化函数）"""
        try:
            # 调用数据库函数创建初始工作流
            workflow_id = await self.db.call_function(
                "create_initial_workflow",
                workflow_data.name,
                workflow_data.description,
                workflow_data.creator_id
            )
            
            if workflow_id:
                return await self.get_workflow_by_id(workflow_id)
            return None
        except Exception as e:
            logger.error(f"创建工作流失败: {e}")
            raise
    
    async def get_workflow_by_id(self, workflow_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取工作流"""
        return await self.get_by_id(workflow_id, "workflow_id")
    
    async def get_workflow_by_base_id(self, workflow_base_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据基础ID获取当前版本的工作流"""
        try:
            query = """
                SELECT w.*, u.username as creator_name
                FROM workflow w
                LEFT JOIN `user` u ON u.user_id = w.creator_id
                WHERE w.workflow_base_id = %s AND w.is_current_version = TRUE AND w.is_deleted = FALSE
            """
            result = await self.db.fetch_one(query, workflow_base_id)
            return result
        except Exception as e:
            logger.error(f"根据基础ID获取工作流失败: {e}")
            raise
    
    async def update_workflow(self, workflow_base_id: uuid.UUID, 
                             workflow_data: WorkflowUpdate,
                             editor_user_id: Optional[uuid.UUID] = None) -> Optional[Dict[str, Any]]:
        """更新工作流（创建新版本）"""
        try:
            # 获取当前版本的工作流信息
            current_workflow = await self.get_workflow_by_base_id(workflow_base_id)
            if not current_workflow:
                raise ValueError("工作流不存在")
            
            # 生成新的workflow_id和版本号
            new_workflow_id = uuid.uuid4()
            current_version = current_workflow.get('version', 1)
            # 🔧 确保版本号是整数类型
            if isinstance(current_version, str):
                current_version = int(current_version)
            new_version = current_version + 1
            
            # 准备新版本数据
            new_name = workflow_data.name if workflow_data.name is not None else current_workflow.get('name')
            new_description = workflow_data.description if workflow_data.description is not None else current_workflow.get('description')
            
            logger.info(f"开始创建工作流新版本: {workflow_base_id} v{new_version}")
            
            # 开始事务处理
            try:
                # 1. 将当前版本标记为非当前版本
                update_current_query = """
                    UPDATE `workflow` 
                    SET is_current_version = 0 
                    WHERE workflow_base_id = %s AND is_current_version = 1
                """
                await self.db.execute(update_current_query, str(workflow_base_id))
                
                # 2. 创建新版本的工作流记录
                insert_query = """
                    INSERT INTO `workflow` (
                        workflow_id, workflow_base_id, name, description, 
                        version, is_current_version, creator_id, change_description,
                        created_at, updated_at, is_deleted
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0
                    )
                """
                
                await self.db.execute(
                    insert_query,
                    str(new_workflow_id),
                    str(workflow_base_id),
                    new_name,
                    new_description,
                    str(new_version),  # 🔧 确保版本号转换为字符串
                    "1",  # 🔧 确保布尔值转换为字符串
                    str(current_workflow.get('creator_id')),
                    workflow_data.change_description or 'Workflow updated'
                )
                
                logger.info(f"工作流版本创建成功: {workflow_base_id} -> v{new_version} (ID: {new_workflow_id})")
                
                # 返回新创建的工作流
                return await self.get_workflow_by_id(new_workflow_id)
                
            except Exception as e:
                logger.error(f"创建工作流版本时发生错误: {e}")
                raise
                
        except Exception as e:
            logger.error(f"更新工作流失败: {e}")
            raise
    
    async def delete_workflow(self, workflow_base_id: uuid.UUID, soft_delete: bool = True) -> bool:
        """删除工作流（删除所有版本）"""
        try:
            if soft_delete:
                query = """
                    UPDATE workflow 
                    SET is_deleted = TRUE, updated_at = NOW() 
                    WHERE workflow_base_id = %s
                """
            else:
                query = "DELETE FROM workflow WHERE workflow_base_id = %s"
            
            result = await self.db.execute(query, workflow_base_id)
            success = "1" in result or result.split()[1] != "0"
            if success:
                action = "软删除" if soft_delete else "硬删除"
                logger.info(f"{action}了工作流 {workflow_base_id} 的所有版本")
            return success
        except Exception as e:
            logger.error(f"删除工作流失败: {e}")
            raise
    
    async def get_workflow_versions(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的所有版本"""
        try:
            query = """
                SELECT * FROM workflow_version_history 
                WHERE workflow_base_id = %s 
                ORDER BY version DESC
            """
            results = await self.db.fetch_all(query, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取工作流版本列表失败: {e}")
            raise
    
    async def get_workflows_by_creator(self, creator_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取用户创建的工作流列表"""
        try:
            query = """
                SELECT w.*, u.username as creator_name
                FROM workflow w
                LEFT JOIN `user` u ON u.user_id = w.creator_id
                WHERE w.creator_id = %s AND w.is_current_version = TRUE AND w.is_deleted = FALSE
                ORDER BY w.created_at DESC
            """
            results = await self.db.fetch_all(query, creator_id)
            return results
        except Exception as e:
            logger.error(f"获取用户工作流列表失败: {e}")
            raise
    
    async def search_workflows(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索工作流"""
        try:
            query = """
                SELECT * FROM current_workflow_view 
                WHERE (name LIKE %s OR description LIKE %s) 
                ORDER BY created_at DESC 
                LIMIT %s
            """
            keyword_pattern = f"%{keyword}%"
            results = await self.db.fetch_all(query, keyword_pattern, keyword_pattern, limit)
            return results
        except Exception as e:
            logger.error(f"搜索工作流失败: {e}")
            raise
    
    # 工作流用户关联管理
    async def add_workflow_users(self, workflow_base_id: uuid.UUID, user_ids: List[uuid.UUID]) -> bool:
        """添加工作流用户"""
        try:
            queries = []
            for user_id in user_ids:
                queries.append((
                    "INSERT INTO workflow_user (workflow_base_id, user_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE workflow_base_id=workflow_base_id",
                    (workflow_base_id, user_id)
                ))
            
            await self.db.execute_transaction(queries)
            logger.info(f"为工作流 {workflow_base_id} 添加了 {len(user_ids)} 个用户")
            return True
        except Exception as e:
            logger.error(f"添加工作流用户失败: {e}")
            raise
    
    async def remove_workflow_user(self, workflow_base_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """移除工作流用户"""
        try:
            query = "DELETE FROM workflow_user WHERE workflow_base_id = %s AND user_id = %s"
            result = await self.db.execute(query, workflow_base_id, user_id)
            success = "1" in result
            if success:
                logger.info(f"从工作流 {workflow_base_id} 中移除了用户 {user_id}")
            return success
        except Exception as e:
            logger.error(f"移除工作流用户失败: {e}")
            raise
    
    async def get_workflow_users(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流用户列表"""
        try:
            query = """
                SELECT wu.workflow_base_id, wu.user_id, wu.created_at,
                       u.username, u.email, u.role
                FROM workflow_user wu
                JOIN `user` u ON u.user_id = wu.user_id
                WHERE wu.workflow_base_id = %s AND u.is_deleted = FALSE
                ORDER BY wu.created_at DESC
            """
            results = await self.db.fetch_all(query, workflow_base_id)
            return results
        except Exception as e:
            logger.error(f"获取工作流用户列表失败: {e}")
            raise
    
    async def get_user_workflows(self, user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取用户参与的工作流列表"""
        try:
            query = """
                SELECT w.*, u.username as creator_name
                FROM workflow_user wu
                JOIN current_workflow_view w ON w.workflow_base_id = wu.workflow_base_id
                JOIN `user` u ON u.user_id = w.creator_id
                WHERE wu.user_id = %s
                ORDER BY w.created_at DESC
            """
            results = await self.db.fetch_all(query, user_id)
            return results
        except Exception as e:
            logger.error(f"获取用户参与的工作流列表失败: {e}")
            raise
    
    async def workflow_name_exists(self, name: str, creator_id: uuid.UUID) -> bool:
        """检查工作流名称是否已存在（同一创建者）"""
        try:
            query = """
                SELECT EXISTS(
                    SELECT 1 FROM current_workflow_view 
                    WHERE name = %s AND creator_id = %s
                )
            """
            result = await self.db.fetch_val(query, name, creator_id)
            return result
        except Exception as e:
            logger.error(f"检查工作流名称存在性失败: {e}")
            raise
    
    async def get_workflow_stats(self) -> Dict[str, Any]:
        """获取工作流统计信息"""
        try:
            query = """
                SELECT 
                    COUNT(DISTINCT workflow_base_id) as total_workflows,
                    COUNT(DISTINCT creator_id) as total_creators,
                    AVG(CAST(version AS UNSIGNED)) as avg_version,
                    COUNT(*) as total_versions
                FROM workflow 
                WHERE is_deleted = FALSE
            """
            result = await self.db.fetch_one(query)
            return result
        except Exception as e:
            logger.error(f"获取工作流统计信息失败: {e}")
            raise