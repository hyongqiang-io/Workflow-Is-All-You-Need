"""
工作流业务服务
Workflow Service
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..models.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..utils.helpers import now_utc
from ..utils.exceptions import ValidationError, ConflictError


class WorkflowService:
    """工作流业务服务"""
    
    def __init__(self):
        self.workflow_repository = WorkflowRepository()
    
    def _check_workflow_permission(self, workflow: Dict[str, Any], user_id: uuid.UUID) -> bool:
        """
        检查工作流权限
        
        Args:
            workflow: 工作流记录
            user_id: 用户ID
            
        Returns:
            是否有权限
        """
        workflow_creator_id = workflow['creator_id']
        if isinstance(workflow_creator_id, str):
            workflow_creator_id = uuid.UUID(workflow_creator_id)
        
        return workflow_creator_id == user_id
    
    def _format_workflow_response(self, workflow_record: Dict[str, Any]) -> WorkflowResponse:
        """格式化工作流响应"""
        # 处理version字段 - 转换字符串版本号为整数
        version_value = workflow_record['version']
        if isinstance(version_value, str):
            # 如果是类似"1.0.0"的字符串，提取主版本号
            try:
                version_int = int(version_value.split('.')[0])
            except (ValueError, AttributeError):
                version_int = 1  # 默认版本号
        else:
            version_int = int(version_value) if version_value is not None else 1
        
        return WorkflowResponse(
            workflow_id=workflow_record['workflow_id'],
            workflow_base_id=workflow_record['workflow_base_id'],
            name=workflow_record['name'],
            description=workflow_record.get('description'),
            creator_id=workflow_record['creator_id'],
            version=version_int,
            parent_version_id=workflow_record.get('parent_version_id'),
            is_current_version=workflow_record['is_current_version'],
            change_description=workflow_record.get('change_description'),
            created_at=workflow_record['created_at'].isoformat() if workflow_record['created_at'] else None,
            updated_at=workflow_record['updated_at'].isoformat() if workflow_record['updated_at'] else None,
            creator_name=workflow_record.get('creator_name')
        )
    
    async def create_workflow(self, workflow_data: WorkflowCreate) -> WorkflowResponse:
        """
        创建新工作流
        
        Args:
            workflow_data: 工作流创建数据
            
        Returns:
            工作流响应数据
            
        Raises:
            ConflictError: 工作流名称已存在
            ValidationError: 输入数据无效
        """
        try:
            # 验证输入数据
            if not workflow_data.name or len(workflow_data.name.strip()) < 1:
                raise ValidationError("工作流名称不能为空", "name")

            # 创建工作流（允许同名，因为ID唯一即可保证区分）
            workflow_record = await self.workflow_repository.create_workflow(workflow_data)
            if not workflow_record:
                raise ValueError("创建工作流失败")
            
            logger.info(f"用户 {workflow_data.creator_id} 创建了工作流: {workflow_data.name}")
            
            return self._format_workflow_response(workflow_record)
            
        except (ConflictError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"创建工作流失败: {e}")
            raise ValueError(f"创建工作流失败: {str(e)}")
    
    async def get_workflow_by_base_id(self, workflow_base_id: uuid.UUID) -> Optional[WorkflowResponse]:
        """
        根据基础ID获取当前版本工作流
        
        Args:
            workflow_base_id: 工作流基础ID
            
        Returns:
            工作流响应数据或None
        """
        try:
            workflow_record = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow_record:
                return None
            
            return self._format_workflow_response(workflow_record)
            
        except Exception as e:
            logger.error(f"获取工作流失败: {e}")
            raise ValueError(f"获取工作流失败: {str(e)}")
    
    async def get_user_workflows(self, user_id: uuid.UUID) -> List[WorkflowResponse]:
        """
        获取用户创建的工作流列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            工作流列表
        """
        try:
            workflow_records = await self.workflow_repository.get_workflows_by_creator(user_id)
            
            return [
                self._format_workflow_response(record) 
                for record in workflow_records
            ]
            
        except Exception as e:
            logger.error(f"获取用户工作流列表失败: {e}")
            raise ValueError(f"获取用户工作流列表失败: {str(e)}")
    
    async def update_workflow(self, workflow_base_id: uuid.UUID, 
                             workflow_data: WorkflowUpdate,
                             editor_user_id: uuid.UUID) -> WorkflowResponse:
        """
        更新工作流（创建新版本）
        
        Args:
            workflow_base_id: 工作流基础ID
            workflow_data: 更新数据
            editor_user_id: 编辑用户ID
            
        Returns:
            更新后的工作流响应数据
            
        Raises:
            ValidationError: 输入数据无效
            ConflictError: 工作流名称冲突
        """
        try:
            # 检查工作流是否存在
            existing_workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not existing_workflow:
                raise ValueError("工作流不存在")
            
            # 更新工作流（允许同名，因为ID唯一即可保证区分）
            updated_workflow = await self.workflow_repository.update_workflow(
                workflow_base_id, workflow_data, editor_user_id
            )
            
            if not updated_workflow:
                raise ValueError("更新工作流失败")
            
            logger.info(f"用户 {editor_user_id} 更新了工作流: {workflow_base_id}")
            
            return self._format_workflow_response(updated_workflow)
            
        except (ConflictError, ValidationError):
            raise
        except Exception as e:
            logger.error(f"更新工作流失败: {e}")
            raise ValueError(f"更新工作流失败: {str(e)}")
    
    async def delete_workflow(self, workflow_base_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """
        删除工作流
        
        Args:
            workflow_base_id: 工作流基础ID
            user_id: 操作用户ID
            
        Returns:
            是否删除成功
        """
        try:
            # 检查权限 - 只有创建者可以删除
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow:
                raise ValueError("工作流不存在")
            
            if not self._check_workflow_permission(workflow, user_id):
                raise ValueError("只有工作流创建者可以删除工作流")
            
            # 执行级联删除
            from .cascade_deletion_service import cascade_deletion_service
            deletion_result = await cascade_deletion_service.delete_workflow_base_cascade(
                workflow_base_id, soft_delete=True
            )
            
            success = deletion_result['deleted_workflow_base']
            if success:
                logger.info(f"用户 {user_id} 级联删除了工作流: {workflow_base_id}")
                logger.info(f"删除统计: 实例{deletion_result['deleted_workflow_instances']}个, "
                           f"任务{deletion_result['deleted_tasks']}个, "
                           f"节点{deletion_result['deleted_nodes']}个")
            
            return success
            
        except Exception as e:
            logger.error(f"删除工作流失败: {e}")
            raise ValueError(f"删除工作流失败: {str(e)}")
    
    async def search_workflows(self, keyword: str, limit: int = 50) -> List[WorkflowResponse]:
        """
        搜索工作流
        
        Args:
            keyword: 搜索关键词
            limit: 返回结果限制
            
        Returns:
            工作流列表
        """
        try:
            if not keyword or len(keyword.strip()) < 1:
                return []
            
            workflow_records = await self.workflow_repository.search_workflows(keyword, limit)
            
            return [
                self._format_workflow_response(record) 
                for record in workflow_records
            ]
            
        except Exception as e:
            logger.error(f"搜索工作流失败: {e}")
            raise ValueError(f"搜索工作流失败: {str(e)}")
    
    async def get_workflow_versions(self, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        获取工作流版本历史
        
        Args:
            workflow_base_id: 工作流基础ID
            
        Returns:
            版本历史列表
        """
        try:
            versions = await self.workflow_repository.get_workflow_versions(workflow_base_id)
            
            # 格式化时间戳
            for version in versions:
                if version.get('created_at'):
                    version['created_at'] = version['created_at'].isoformat()
            
            return versions
            
        except Exception as e:
            logger.error(f"获取工作流版本历史失败: {e}")
            raise ValueError(f"获取工作流版本历史失败: {str(e)}")
    
    async def get_workflow_stats(self) -> Dict[str, Any]:
        """
        获取工作流统计信息
        
        Returns:
            统计信息
        """
        try:
            stats = await self.workflow_repository.get_workflow_stats()
            return stats
            
        except Exception as e:
            logger.error(f"获取工作流统计信息失败: {e}")
            raise ValueError(f"获取工作流统计信息失败: {str(e)}")