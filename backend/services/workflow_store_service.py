"""
工作流商店业务服务
Workflow Store Service
"""

import uuid
import json
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from ..models.workflow_store import (
    WorkflowStoreCreate, WorkflowStoreUpdate, WorkflowStoreResponse,
    WorkflowStoreDetail, WorkflowStoreQuery, WorkflowStoreList,
    WorkflowStoreRatingCreate, WorkflowStoreRating,
    WorkflowStoreImportRequest, WorkflowStoreImportResult,
    WorkflowStoreStats, StoreStatus
)
from ..models.workflow_import_export import WorkflowExport, WorkflowImport, ImportResult
from ..repositories.workflow_store.workflow_store_repository import WorkflowStoreRepository
from ..repositories.workflow_store.workflow_store_rating_repository import WorkflowStoreRatingRepository
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..repositories.user.user_repository import UserRepository
from ..services.workflow_import_export_service import WorkflowImportExportService
from ..utils.helpers import now_utc
from ..utils.exceptions import ValidationError, ConflictError, NotFoundError, AuthorizationError


class WorkflowStoreService:
    """工作流商店业务服务"""

    def __init__(self):
        self.store_repository = WorkflowStoreRepository()
        self.rating_repository = WorkflowStoreRatingRepository()
        self.workflow_repository = WorkflowRepository()
        self.user_repository = UserRepository()
        self.import_export_service = WorkflowImportExportService()

    async def publish_workflow(self, workflow_base_id: uuid.UUID, store_data: WorkflowStoreCreate, user_id: uuid.UUID) -> str:
        """发布工作流到商店"""
        try:
            # 1. 验证工作流是否存在
            workflow = await self.workflow_repository.get_workflow_by_base_id(str(workflow_base_id))
            if not workflow:
                raise NotFoundError("工作流不存在")

            # 2. 导出工作流数据
            workflow_export = await self._export_workflow_data(str(workflow_base_id), str(user_id))
            if not workflow_export:
                raise ValidationError("导出工作流数据失败")

            # 3. 检查是否已发布过该工作流（基于workflow_base_id）
            existing_items = await self.store_repository.get_user_items(str(user_id))
            for item in existing_items:
                # 检查工作流导出数据中的metadata是否包含相同的workflow_base_id
                if (item.workflow_export_data and
                    hasattr(item.workflow_export_data, 'metadata') and
                    item.workflow_export_data.metadata and
                    item.workflow_export_data.metadata.get("original_workflow_id") == str(workflow_base_id)):
                    raise ConflictError("该工作流已发布到商店")

            # 4. 创建商店条目（使用简化的用户名）
            store_id = await self.store_repository.create_store_item(
                store_data, workflow_export, str(user_id), "System User"
            )

            if not store_id:
                raise ValidationError("创建商店条目失败")

            return store_id

        except Exception as e:
            logger.error(f"发布工作流失败: {e}")
            raise

    async def get_store_item(self, store_id: str, user_id: Optional[str] = None) -> Optional[WorkflowStoreDetail]:
        """获取商店条目详情（不增加浏览数）"""
        try:
            item = await self.store_repository.get_store_item(store_id)
            if not item:
                return None

            return item

        except Exception as e:
            logger.error(f"获取商店条目失败: {e}")
            return None

    async def increment_store_view(self, store_id: str, user_id: Optional[str] = None) -> bool:
        """单独增加浏览次数"""
        try:
            return await self.store_repository.increment_view_count(store_id)
        except Exception as e:
            logger.error(f"增加浏览次数失败: {e}")
            return False

    async def update_store_item(self, store_id: str, update_data: WorkflowStoreUpdate, user_id: uuid.UUID) -> bool:
        """更新商店条目"""
        try:
            # 验证权限
            item = await self.store_repository.get_store_item(store_id)
            if not item:
                raise NotFoundError("商店条目不存在")

            if item.author_id != user_id:
                raise AuthorizationError("无权限修改此条目")

            return await self.store_repository.update_store_item(store_id, update_data)

        except Exception as e:
            logger.error(f"更新商店条目失败: {e}")
            raise

    async def delete_store_item(self, store_id: str, user_id: uuid.UUID) -> bool:
        """删除商店条目"""
        try:
            # 验证权限
            item = await self.store_repository.get_store_item(store_id)
            if not item:
                raise NotFoundError("商店条目不存在")

            if item.author_id != user_id:
                raise AuthorizationError("无权限删除此条目")

            return await self.store_repository.delete_store_item(store_id)

        except Exception as e:
            logger.error(f"删除商店条目失败: {e}")
            raise

    async def search_store_items(self, search_params: WorkflowStoreQuery) -> WorkflowStoreList:
        """搜索商店条目"""
        try:
            items, total = await self.store_repository.search_store_items(search_params)

            total_pages = (total + search_params.page_size - 1) // search_params.page_size

            return WorkflowStoreList(
                items=items,
                total=total,
                page=search_params.page,
                page_size=search_params.page_size,
                total_pages=total_pages
            )

        except Exception as e:
            logger.error(f"搜索商店条目失败: {e}")
            return WorkflowStoreList(
                items=[],
                total=0,
                page=search_params.page,
                page_size=search_params.page_size,
                total_pages=0
            )

    async def get_featured_items(self, limit: int = 10) -> List[WorkflowStoreResponse]:
        """获取推荐工作流"""
        return await self.store_repository.get_featured_items(limit)

    async def get_popular_items(self, limit: int = 10) -> List[WorkflowStoreResponse]:
        """获取热门工作流"""
        return await self.store_repository.get_popular_items(limit)

    async def get_user_items(self, user_id: uuid.UUID) -> List[WorkflowStoreResponse]:
        """获取用户发布的工作流"""
        return await self.store_repository.get_user_items(str(user_id))

    async def import_workflow_from_store(self, import_request: WorkflowStoreImportRequest, user_id: uuid.UUID) -> WorkflowStoreImportResult:
        """从商店导入工作流"""
        try:
            # 1. 获取商店条目
            item = await self.store_repository.get_store_item(str(import_request.store_id))
            if not item:
                raise NotFoundError("商店条目不存在")

            if item.status != StoreStatus.PUBLISHED:
                raise ValidationError("该工作流尚未发布")

            # 2. 准备导入数据
            # 确保 nodes 和 connections 是正确的格式
            nodes_data = item.workflow_export_data.nodes
            connections_data = item.workflow_export_data.connections

            # 如果数据是对象，转换为字典
            if nodes_data and len(nodes_data) > 0 and hasattr(nodes_data[0], 'model_dump'):
                nodes_data = [node.model_dump() if hasattr(node, 'model_dump') else node for node in nodes_data]

            if connections_data and len(connections_data) > 0 and hasattr(connections_data[0], 'model_dump'):
                connections_data = [conn.model_dump() if hasattr(conn, 'model_dump') else conn for conn in connections_data]

            workflow_import = WorkflowImport(
                name=import_request.import_name or item.workflow_export_data.name,
                description=import_request.import_description or item.workflow_export_data.description,
                nodes=nodes_data,
                connections=connections_data
            )

            # 3. 验证导入数据
            validation_result = workflow_import.validate_import_data()
            logger.info(f"🔍 工作流导入验证结果: {validation_result}")
            logger.info(f"🔍 导入数据: name='{workflow_import.name}', nodes_count={len(workflow_import.nodes)}, connections_count={len(workflow_import.connections)}")

            if not validation_result["valid"]:
                logger.error(f"❌ 工作流验证失败: errors={validation_result['errors']}, warnings={validation_result['warnings']}")
                return WorkflowStoreImportResult(
                    success=False,
                    message="工作流数据验证失败",
                    errors=validation_result["errors"],
                    warnings=validation_result["warnings"]
                )

            # 4. 清理并导入工作流
            cleaned_import = workflow_import.clean_import_data()

            # 使用导入服务创建新的工作流（不覆盖，总是创建新的）
            import_result = await self.import_export_service.import_workflow(
                cleaned_import, user_id, overwrite=False
            )

            if import_result.success:
                # 5. 记录下载
                await self._record_download(str(import_request.store_id), str(user_id))

                return WorkflowStoreImportResult(
                    success=True,
                    workflow_id=uuid.UUID(import_result.workflow_id) if import_result.workflow_id else None,
                    workflow_base_id=uuid.UUID(import_result.workflow_id) if import_result.workflow_id else None,
                    message="工作流导入成功",
                    warnings=import_result.warnings or []
                )
            else:
                return WorkflowStoreImportResult(
                    success=False,
                    message=import_result.message,
                    errors=import_result.errors or [],
                    warnings=import_result.warnings or []
                )

        except Exception as e:
            logger.error(f"从商店导入工作流失败: {e}")
            return WorkflowStoreImportResult(
                success=False,
                message=f"导入失败: {str(e)}",
                errors=[str(e)]
            )

    async def create_rating(self, rating_data: WorkflowStoreRatingCreate, user_id: uuid.UUID) -> Optional[str]:
        """创建评分"""
        try:
            # 验证商店条目是否存在
            item = await self.store_repository.get_store_item(str(rating_data.store_id))
            if not item:
                raise NotFoundError("商店条目不存在")

            # 验证用户是否已评分
            existing_rating = await self.rating_repository.get_user_rating(
                str(rating_data.store_id), str(user_id)
            )
            if existing_rating:
                raise ConflictError("您已对此工作流评分")

            # 获取用户信息
            user = await self.user_repository.get_user_by_id(str(user_id))
            if not user:
                raise NotFoundError("用户不存在")

            return await self.rating_repository.create_rating(
                rating_data, str(user_id), user['username']
            )

        except Exception as e:
            logger.error(f"创建评分失败: {e}")
            raise

    async def update_rating(self, rating_id: str, rating: int, comment: Optional[str], user_id: uuid.UUID) -> bool:
        """更新评分"""
        try:
            # 验证评分是否存在且属于该用户
            existing_rating = await self.rating_repository.get_user_rating("", str(user_id))
            # 这里需要优化，通过rating_id获取评分并验证用户权限

            return await self.rating_repository.update_rating(rating_id, rating, comment)

        except Exception as e:
            logger.error(f"更新评分失败: {e}")
            raise

    async def get_store_ratings(self, store_id: str, limit: int = 50, offset: int = 0) -> List[WorkflowStoreRating]:
        """获取商店条目评分"""
        return await self.rating_repository.get_store_ratings(store_id, limit, offset)

    async def get_store_stats(self) -> WorkflowStoreStats:
        """获取商店统计信息"""
        try:
            # 这里需要实现具体的统计查询
            # 为了演示，返回模拟数据
            return WorkflowStoreStats(
                total_workflows=0,
                total_downloads=0,
                featured_count=0,
                categories_stats={},
                top_authors=[],
                recent_uploads=[]
            )

        except Exception as e:
            logger.error(f"获取商店统计失败: {e}")
            raise

    async def _export_workflow_data(self, workflow_base_id: str, user_id: str) -> Optional[WorkflowExport]:
        """导出工作流数据"""
        try:
            # 使用现有的完整导出服务
            workflow_export = await self.import_export_service.export_workflow(
                uuid.UUID(workflow_base_id), uuid.UUID(user_id)
            )
            return workflow_export

        except Exception as e:
            logger.error(f"导出工作流数据失败: {e}")
            return None

    async def _record_download(self, store_id: str, user_id: str) -> None:
        """记录下载"""
        try:
            # 这里可以添加到下载记录表
            # 当前只是简单记录，可以扩展为详细的下载历史
            pass

        except Exception as e:
            logger.error(f"记录下载失败: {e}")