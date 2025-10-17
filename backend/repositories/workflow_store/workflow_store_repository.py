"""
工作流商店数据访问层
Workflow Store Repository
"""

import uuid
import json
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

from ..base import BaseRepository
from ...models.workflow_store import (
    WorkflowStore, WorkflowStoreCreate, WorkflowStoreUpdate,
    WorkflowStoreQuery, WorkflowStoreResponse, WorkflowStoreDetail,
    WorkflowStoreRating, WorkflowStoreRatingCreate, StoreCategory, StoreStatus
)
from ...models.workflow_import_export import WorkflowExport
from ...utils.helpers import now_utc, QueryBuilder


class WorkflowStoreRepository(BaseRepository[WorkflowStore]):
    """工作流商店数据访问层"""

    def __init__(self):
        super().__init__("workflow_store")
        # 覆盖table_name，移除引号以兼容MySQL
        self.table_name = "workflow_store"

    async def create_store_item(self, store_data: WorkflowStoreCreate, workflow_export: WorkflowExport, author_id: str, author_name: str) -> Optional[str]:
        """创建商店条目"""
        try:
            store_id = str(uuid.uuid4())

            data = {
                "store_id": store_id,
                "title": store_data.title,
                "description": store_data.description,
                "category": store_data.category.value,
                "tags": json.dumps(store_data.tags) if store_data.tags else "[]",
                "is_featured": store_data.is_featured,
                "is_free": store_data.is_free,
                "price": store_data.price,
                "author_id": author_id,
                "author_name": author_name,
                "workflow_export_data": workflow_export.model_dump_json(),
                "status": StoreStatus.PUBLISHED.value,
                "published_at": now_utc(),
                "version": "1.0.0"
                # created_at 和 updated_at 由数据库自动处理
            }

            result = await self.create(data)
            return store_id if result else None

        except Exception as e:
            logger.error(f"创建商店条目失败: {e}")
            return None

    async def get_store_item(self, store_id: str) -> Optional[WorkflowStoreDetail]:
        """获取商店条目详情"""
        try:
            query = f"""
            SELECT * FROM {self.table_name}
            WHERE store_id = %s AND is_deleted = FALSE
            """

            result = await self.db.fetch_one(query, store_id)
            if not result:
                return None

            return self._format_store_detail(result)

        except Exception as e:
            logger.error(f"获取商店条目失败: {e}")
            return None

    async def update_store_item(self, store_id: str, update_data: WorkflowStoreUpdate) -> bool:
        """更新商店条目"""
        try:
            data = {}

            if update_data.title is not None:
                data["title"] = update_data.title
            if update_data.description is not None:
                data["description"] = update_data.description
            if update_data.category is not None:
                data["category"] = update_data.category.value
            if update_data.tags is not None:
                data["tags"] = json.dumps(update_data.tags)
            if update_data.is_featured is not None:
                data["is_featured"] = update_data.is_featured
            if update_data.is_free is not None:
                data["is_free"] = update_data.is_free
            if update_data.price is not None:
                data["price"] = update_data.price
            if update_data.status is not None:
                data["status"] = update_data.status.value
                if update_data.status == StoreStatus.PUBLISHED:
                    data["published_at"] = now_utc()
            if update_data.changelog is not None:
                data["changelog"] = update_data.changelog

            if not data:
                return True

            data["updated_at"] = now_utc()

            query = f"""
            UPDATE {self.table_name}
            SET {', '.join(f'{k} = %s' for k in data.keys())}
            WHERE store_id = %s AND is_deleted = FALSE
            """

            values = list(data.values()) + [store_id]
            result = await self.db.execute(query, values)
            return result > 0

        except Exception as e:
            logger.error(f"更新商店条目失败: {e}")
            return False

    async def delete_store_item(self, store_id: str) -> bool:
        """删除商店条目（软删除）"""
        try:
            query = f"""
            UPDATE {self.table_name}
            SET is_deleted = TRUE, updated_at = %s
            WHERE store_id = %s
            """

            result = await self.db.execute(query, now_utc(), store_id)
            return result > 0

        except Exception as e:
            logger.error(f"删除商店条目失败: {e}")
            return False

    async def search_store_items(self, search_params: WorkflowStoreQuery) -> Tuple[List[WorkflowStoreResponse], int]:
        """搜索商店条目"""
        try:
            # 构建基础查询
            base_conditions = ["is_deleted = FALSE", "status = 'published'"]
            params = []

            # 关键词搜索
            if search_params.keyword:
                base_conditions.append("(title LIKE %s OR description LIKE %s)")
                params.extend([f"%{search_params.keyword}%", f"%{search_params.keyword}%"])

            # 分类筛选
            if search_params.category:
                base_conditions.append("category = %s")
                params.append(search_params.category.value)

            # 标签筛选
            if search_params.tags:
                for tag in search_params.tags:
                    base_conditions.append("JSON_CONTAINS(tags, %s)")
                    params.append(json.dumps(tag))

            # 作者筛选
            if search_params.author_id:
                base_conditions.append("author_id = %s")
                params.append(str(search_params.author_id))

            # 推荐筛选
            if search_params.is_featured is not None:
                base_conditions.append("is_featured = %s")
                params.append(search_params.is_featured)

            # 免费筛选
            if search_params.is_free is not None:
                base_conditions.append("is_free = %s")
                params.append(search_params.is_free)

            # 评分筛选
            if search_params.min_rating is not None:
                base_conditions.append("rating >= %s")
                params.append(search_params.min_rating)

            where_clause = " AND ".join(base_conditions)

            # 获取总数
            count_query = f"""
            SELECT COUNT(*) FROM {self.table_name}
            WHERE {where_clause}
            """
            total = await self.db.fetch_val(count_query, *params) or 0

            # 排序
            order_clause = ""
            if search_params.sort_by:
                direction = "DESC" if search_params.sort_order == "desc" else "ASC"
                order_clause = f"ORDER BY {search_params.sort_by} {direction}"

            # 分页
            offset = (search_params.page - 1) * search_params.page_size
            limit_clause = f"LIMIT %s OFFSET %s"
            params.extend([search_params.page_size, offset])

            # 执行查询
            query = f"""
            SELECT * FROM {self.table_name}
            WHERE {where_clause}
            {order_clause}
            {limit_clause}
            """

            results = await self.db.fetch_all(query, *params)
            items = [self._format_store_response(row) for row in results]

            return items, total

        except Exception as e:
            logger.error(f"搜索商店条目失败: {e}")
            return [], 0

    async def get_featured_items(self, limit: int = 10) -> List[WorkflowStoreResponse]:
        """获取推荐条目"""
        try:
            query = f"""
            SELECT * FROM {self.table_name}
            WHERE is_featured = TRUE AND status = 'published' AND is_deleted = FALSE
            ORDER BY featured_at DESC, created_at DESC
            LIMIT %s
            """

            results = await self.db.fetch_all(query, limit)
            return [self._format_store_response(row) for row in results]

        except Exception as e:
            logger.error(f"获取推荐条目失败: {e}")
            return []

    async def get_popular_items(self, limit: int = 10) -> List[WorkflowStoreResponse]:
        """获取热门条目（按下载量排序）"""
        try:
            query = f"""
            SELECT * FROM {self.table_name}
            WHERE status = 'published' AND is_deleted = FALSE
            ORDER BY downloads DESC, rating DESC
            LIMIT %s
            """

            results = await self.db.fetch_all(query, limit)
            return [self._format_store_response(row) for row in results]

        except Exception as e:
            logger.error(f"获取热门条目失败: {e}")
            return []

    async def get_user_items(self, author_id: str) -> List[WorkflowStoreResponse]:
        """获取用户发布的条目"""
        try:
            query = f"""
            SELECT * FROM {self.table_name}
            WHERE author_id = %s AND is_deleted = FALSE
            ORDER BY created_at DESC
            """

            results = await self.db.fetch_all(query, author_id)
            return [self._format_store_response(row) for row in results]

        except Exception as e:
            logger.error(f"获取用户条目失败: {e}")
            return []

    async def increment_view_count(self, store_id: str) -> bool:
        """增加浏览次数"""
        try:
            query = f"""
            UPDATE {self.table_name}
            SET views = views + 1
            WHERE store_id = %s AND is_deleted = FALSE
            """

            result = await self.db.execute(query, store_id)
            # result 可能是字符串格式，需要提取数字
            if isinstance(result, str) and "UPDATE" in result:
                # 从 "UPDATE 1" 格式中提取数字
                affected_rows = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                return affected_rows > 0
            return int(result) > 0 if result else False

        except Exception as e:
            logger.error(f"增加浏览次数失败: {e}")
            return False

    def _format_store_response(self, row: Dict[str, Any]) -> WorkflowStoreResponse:
        """格式化商店响应"""
        # 解析标签
        tags = []
        if row.get('tags'):
            try:
                tags = json.loads(row['tags'])
            except:
                pass

        # 解析工作流基本信息
        workflow_info = None
        if row.get('workflow_export_data'):
            try:
                export_data = json.loads(row['workflow_export_data'])
                workflow_info = {
                    "name": export_data.get("name"),
                    "description": export_data.get("description"),
                    "nodes_count": len(export_data.get("nodes", [])),
                    "connections_count": len(export_data.get("connections", []))
                }
            except:
                pass

        # 时间字段转换函数
        def format_datetime(dt):
            if dt is None:
                return None
            if isinstance(dt, str):
                return dt
            return dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)

        return WorkflowStoreResponse(
            store_id=uuid.UUID(row['store_id']),
            title=row['title'],
            description=row.get('description'),
            category=StoreCategory(row['category']),
            tags=tags,
            is_featured=bool(row.get('is_featured', False)),
            is_free=bool(row.get('is_free', True)),
            price=row.get('price'),
            author_id=uuid.UUID(row['author_id']),
            author_name=row['author_name'],
            downloads=row.get('downloads', 0),
            views=row.get('views', 0),
            rating=float(row.get('rating', 0.0)),
            rating_count=row.get('rating_count', 0),
            status=StoreStatus(row['status']),
            published_at=format_datetime(row.get('published_at')),
            featured_at=format_datetime(row.get('featured_at')),
            version=row.get('version', '1.0.0'),
            changelog=row.get('changelog'),
            created_at=format_datetime(row.get('created_at')),
            updated_at=format_datetime(row.get('updated_at')),
            workflow_info=workflow_info
        )

    def _format_store_detail(self, row: Dict[str, Any]) -> WorkflowStoreDetail:
        """格式化商店详情"""
        # 先获取基础响应格式
        base_response = self._format_store_response(row)

        # 解析完整的工作流导出数据
        workflow_export_data = None
        if row.get('workflow_export_data'):
            try:
                export_json = json.loads(row['workflow_export_data'])
                workflow_export_data = WorkflowExport(**export_json)
            except Exception as e:
                logger.error(f"解析工作流导出数据失败: {e}")
                # 如果解析失败，创建一个基本的WorkflowExport对象
                workflow_export_data = WorkflowExport(
                    name="数据解析失败",
                    export_timestamp=now_utc(),
                    nodes=[],
                    connections=[]
                )

        return WorkflowStoreDetail(
            **base_response.model_dump(),
            workflow_export_data=workflow_export_data
        )