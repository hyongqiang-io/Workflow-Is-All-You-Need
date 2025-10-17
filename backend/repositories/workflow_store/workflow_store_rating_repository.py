"""
工作流商店评分数据访问层
Workflow Store Rating Repository
"""

import uuid
from typing import Dict, Any, List, Optional
from loguru import logger

from ..base import BaseRepository
from ...models.workflow_store import WorkflowStoreRating, WorkflowStoreRatingCreate
from ...utils.helpers import now_utc


class WorkflowStoreRatingRepository(BaseRepository[WorkflowStoreRating]):
    """工作流商店评分数据访问层"""

    def __init__(self):
        super().__init__("workflow_store_rating")
        # 覆盖table_name，移除引号以兼容MySQL
        self.table_name = "workflow_store_rating"

    async def create_rating(self, rating_data: WorkflowStoreRatingCreate, user_id: str, user_name: str) -> Optional[str]:
        """创建评分"""
        try:
            rating_id = str(uuid.uuid4())

            data = {
                "rating_id": rating_id,
                "store_id": str(rating_data.store_id),
                "user_id": user_id,
                "user_name": user_name,
                "rating": rating_data.rating,
                "comment": rating_data.comment,
                "created_at": now_utc()
            }

            result = await self.create(data)
            return rating_id if result else None

        except Exception as e:
            logger.error(f"创建评分失败: {e}")
            return None

    async def update_rating(self, rating_id: str, rating: int, comment: Optional[str] = None) -> bool:
        """更新评分"""
        try:
            data = {
                "rating": rating,
                "updated_at": now_utc()
            }

            if comment is not None:
                data["comment"] = comment

            query = f"""
            UPDATE {self.table_name}
            SET {', '.join(f'{k} = %s' for k in data.keys())}
            WHERE rating_id = %s AND is_deleted = FALSE
            """

            values = list(data.values()) + [rating_id]
            result = await self.db.execute(query, values)
            return result > 0

        except Exception as e:
            logger.error(f"更新评分失败: {e}")
            return False

    async def get_user_rating(self, store_id: str, user_id: str) -> Optional[WorkflowStoreRating]:
        """获取用户对特定工作流的评分"""
        try:
            query = f"""
            SELECT * FROM {self.table_name}
            WHERE store_id = %s AND user_id = %s AND is_deleted = FALSE
            """

            result = await self.db.fetch_one(query, (store_id, user_id))
            if not result:
                return None

            return self._format_rating(result)

        except Exception as e:
            logger.error(f"获取用户评分失败: {e}")
            return None

    async def get_store_ratings(self, store_id: str, limit: int = 50, offset: int = 0) -> List[WorkflowStoreRating]:
        """获取商店条目的所有评分"""
        try:
            query = f"""
            SELECT * FROM {self.table_name}
            WHERE store_id = %s AND is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """

            results = await self.db.fetch_all(query, store_id, limit, offset)
            return [self._format_rating(row) for row in results]

        except Exception as e:
            logger.error(f"获取商店评分失败: {e}")
            return []

    async def delete_rating(self, rating_id: str) -> bool:
        """删除评分（软删除）"""
        try:
            query = f"""
            UPDATE {self.table_name}
            SET is_deleted = TRUE, updated_at = %s
            WHERE rating_id = %s
            """

            result = await self.db.execute(query, (now_utc(), rating_id))
            return result > 0

        except Exception as e:
            logger.error(f"删除评分失败: {e}")
            return False

    def _format_rating(self, row: Dict[str, Any]) -> WorkflowStoreRating:
        """格式化评分数据"""
        return WorkflowStoreRating(
            rating_id=uuid.UUID(row['rating_id']),
            store_id=uuid.UUID(row['store_id']),
            user_id=uuid.UUID(row['user_id']),
            user_name=row['user_name'],
            rating=row['rating'],
            comment=row.get('comment'),
            created_at=row['created_at']
        )