"""
基础数据访问层
Base Repository
"""

import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generic, TypeVar, Tuple
from loguru import logger

from ..utils.database import get_db_manager
from ..utils.helpers import dict_to_sql_insert, dict_to_sql_update, build_where_clause, QueryBuilder
from ..models.base import PaginationParams, PaginationResponse

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """基础数据访问层"""
    
    def __init__(self, table_name: str):
        # 自动添加引号处理PostgreSQL保留关键字
        self.table_name = f'"{table_name}"' if not table_name.startswith('"') else table_name
        self.db = get_db_manager()
    
    async def create(self, data: Dict[str, Any]) -> Optional[T]:
        """创建记录"""
        try:
            columns, placeholders, values = dict_to_sql_insert(data)
            if not columns:
                raise ValueError("没有有效的数据用于插入")
            
            query = f"""
                INSERT INTO {self.table_name} ({columns}) 
                VALUES ({placeholders}) 
                RETURNING *
            """
            
            result = await self.db.fetch_one(query, *values)
            logger.info(f"在表 {self.table_name} 中创建了新记录")
            return result
        except Exception as e:
            logger.error(f"创建记录失败: {e}")
            raise
    
    async def get_by_id(self, record_id: uuid.UUID, id_column: str = "id") -> Optional[T]:
        """根据ID获取记录"""
        try:
            query = f"SELECT * FROM {self.table_name} WHERE {id_column} = $1 AND is_deleted = FALSE"
            result = await self.db.fetch_one(query, record_id)
            return result
        except Exception as e:
            logger.error(f"根据ID获取记录失败: {e}")
            raise
    
    async def update(self, record_id: uuid.UUID, data: Dict[str, Any], id_column: str = "id") -> Optional[T]:
        """更新记录"""
        try:
            set_clause, values = dict_to_sql_update(data, exclude=[id_column, 'created_at', 'updated_at'])
            if not set_clause:
                raise ValueError("没有有效的数据用于更新")
            
            query = f"""
                UPDATE {self.table_name} 
                SET {set_clause}, updated_at = NOW() 
                WHERE {id_column} = ${len(values) + 1} AND is_deleted = FALSE
                RETURNING *
            """
            
            result = await self.db.fetch_one(query, *values, record_id)
            if result:
                logger.info(f"更新了表 {self.table_name} 中的记录 {record_id}")
            return result
        except Exception as e:
            logger.error(f"更新记录失败: {e}")
            raise
    
    async def delete(self, record_id: uuid.UUID, id_column: str = "id", soft_delete: bool = True) -> bool:
        """删除记录"""
        try:
            if soft_delete:
                query = f"""
                    UPDATE {self.table_name} 
                    SET is_deleted = TRUE, updated_at = NOW() 
                    WHERE {id_column} = $1 AND is_deleted = FALSE
                """
            else:
                query = f"DELETE FROM {self.table_name} WHERE {id_column} = $1"
            
            result = await self.db.execute(query, record_id)
            success = "1" in result
            if success:
                action = "软删除" if soft_delete else "硬删除"
                logger.info(f"{action}了表 {self.table_name} 中的记录 {record_id}")
            return success
        except Exception as e:
            logger.error(f"删除记录失败: {e}")
            raise
    
    async def list_all(self, conditions: Optional[Dict[str, Any]] = None, 
                       order_by: str = "created_at DESC") -> List[T]:
        """获取所有记录"""
        try:
            base_query = f"SELECT * FROM {self.table_name}"
            
            if conditions is None:
                conditions = {}
            conditions["is_deleted"] = False
            
            where_clause, values, _ = build_where_clause(conditions)
            if where_clause:
                base_query += f" WHERE {where_clause}"
            
            if order_by:
                base_query += f" ORDER BY {order_by}"
            
            results = await self.db.fetch_all(base_query, *values)
            return results
        except Exception as e:
            logger.error(f"获取记录列表失败: {e}")
            raise
    
    async def paginate(self, params: PaginationParams, 
                       conditions: Optional[Dict[str, Any]] = None,
                       order_by: str = "created_at DESC") -> PaginationResponse:
        """分页查询"""
        try:
            if conditions is None:
                conditions = {}
            conditions["is_deleted"] = False
            
            # 构建WHERE子句
            where_clause, values, _ = build_where_clause(conditions)
            base_where = f"WHERE {where_clause}" if where_clause else "WHERE is_deleted = FALSE"
            
            # 获取总数
            count_query = f"SELECT COUNT(*) FROM {self.table_name} {base_where}"
            total = await self.db.fetch_val(count_query, *values)
            
            # 获取数据
            data_query = f"""
                SELECT * FROM {self.table_name} {base_where} 
                ORDER BY {order_by} 
                LIMIT {params.page_size} OFFSET {params.offset}
            """
            items = await self.db.fetch_all(data_query, *values)
            
            return PaginationResponse(
                items=items,
                total=total,
                page=params.page,
                page_size=params.page_size
            )
        except Exception as e:
            logger.error(f"分页查询失败: {e}")
            raise
    
    async def exists(self, conditions: Dict[str, Any]) -> bool:
        """检查记录是否存在"""
        try:
            conditions["is_deleted"] = False
            where_clause, values, _ = build_where_clause(conditions)
            
            query = f"SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE {where_clause})"
            result = await self.db.fetch_val(query, *values)
            return result
        except Exception as e:
            logger.error(f"检查记录存在性失败: {e}")
            raise
    
    async def count(self, conditions: Optional[Dict[str, Any]] = None) -> int:
        """统计记录数量"""
        try:
            if conditions is None:
                conditions = {}
            conditions["is_deleted"] = False
            
            where_clause, values, _ = build_where_clause(conditions)
            base_where = f"WHERE {where_clause}" if where_clause else "WHERE is_deleted = FALSE"
            
            query = f"SELECT COUNT(*) FROM {self.table_name} {base_where}"
            result = await self.db.fetch_val(query, *values)
            return result
        except Exception as e:
            logger.error(f"统计记录数量失败: {e}")
            raise
    
    def query_builder(self) -> QueryBuilder:
        """获取查询构建器"""
        return QueryBuilder(self.table_name)