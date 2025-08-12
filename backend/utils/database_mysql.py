"""
MySQL数据库连接管理器 - 与PostgreSQL版本完全兼容
MySQL Database Connection Manager - Fully Compatible with PostgreSQL Version
"""

import asyncio
import aiomysql
import re
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from contextlib import asynccontextmanager

from ..config import get_settings


class DatabaseManager:
    """MySQL数据库连接管理器 - 与PostgreSQL API兼容"""
    
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self.settings = get_settings()
        self._connection_params = {
            'host': self.settings.database.host,
            'port': self.settings.database.port,
            'user': self.settings.database.username,
            'password': self.settings.database.password,
            'db': self.settings.database.database,
            'charset': getattr(self.settings.database, 'charset', 'utf8mb4'),
            'autocommit': True,
            'connect_timeout': 60,
        }
    
    def _convert_postgresql_query(self, query: str) -> str:
        """将PostgreSQL查询转换为MySQL查询"""
        # 替换占位符 $1, $2, $3... 为 %s, %s, %s...
        def replace_placeholder(match):
            return '%s'
        
        # 使用正则表达式替换 $1, $2 等占位符
        converted_query = re.sub(r'\$\d+', replace_placeholder, query)
        
        # 替换双引号标识符为反引号
        converted_query = re.sub(r'"([^"]+)"', r'`\1`', converted_query)
        
        # 替换PostgreSQL特定函数
        converted_query = converted_query.replace('gen_random_uuid()', 'UUID()')
        converted_query = converted_query.replace('NOW()', 'CURRENT_TIMESTAMP')
        
        # 处理RETURNING子句（MySQL不支持，需要特殊处理）
        if 'RETURNING *' in converted_query.upper():
            converted_query = converted_query.replace('RETURNING *', '')
            # 标记需要获取最后插入的记录
            converted_query += ' -- NEEDS_LAST_INSERT'
        
        return converted_query
    
    async def initialize(self) -> None:
        """初始化数据库连接池"""
        try:
            # 创建连接池
            self.pool = await aiomysql.create_pool(
                minsize=self.settings.database.min_connections,
                maxsize=self.settings.database.max_connections,
                **self._connection_params
            )
            logger.info("MySQL数据库连接池初始化成功")
            
        except Exception as e:
            logger.error(f"MySQL数据库连接初始化失败: {e}")
            raise
    
    async def close(self) -> None:
        """关闭数据库连接池"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("MySQL数据库连接池已关闭")
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接上下文管理器 - 兼容PostgreSQL接口"""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            # 创建兼容PostgreSQL的连接wrapper
            wrapper = MySQLConnectionWrapper(connection)
            try:
                yield wrapper
            finally:
                pass
    
    async def execute(self, query: str, *args) -> str:
        """执行SQL命令（INSERT, UPDATE, DELETE）- 兼容PostgreSQL接口"""
        converted_query = self._convert_postgresql_query(query)
        
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                affected_rows = await cursor.execute(converted_query, args)
                return f"UPDATE {affected_rows}" if affected_rows > 0 else "UPDATE 0"
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """查询单条记录 - 兼容PostgreSQL接口"""
        converted_query = self._convert_postgresql_query(query)
        needs_last_insert = '-- NEEDS_LAST_INSERT' in converted_query
        converted_query = converted_query.replace(' -- NEEDS_LAST_INSERT', '')
        
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                if needs_last_insert:
                    # 处理INSERT ... RETURNING的情况
                    await cursor.execute(converted_query, args)
                    last_id = cursor.lastrowid
                    if last_id:
                        # 获取刚插入的记录
                        table_name = self._extract_table_name_from_insert(query)
                        if table_name:
                            await cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s OR uuid = %s", (last_id, last_id))
                            result = await cursor.fetchone()
                            return result
                else:
                    await cursor.execute(converted_query, args)
                    result = await cursor.fetchone()
                    return result
        
        return None
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """查询多条记录 - 兼容PostgreSQL接口"""
        converted_query = self._convert_postgresql_query(query)
        
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(converted_query, args)
                results = await cursor.fetchall()
                return results or []
    
    async def fetch_val(self, query: str, *args) -> Any:
        """查询单个值 - 兼容PostgreSQL接口"""
        converted_query = self._convert_postgresql_query(query)
        
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(converted_query, args)
                result = await cursor.fetchone()
                return result[0] if result else None
    
    async def execute_transaction(self, queries: List[Tuple[str, tuple]]) -> None:
        """执行事务 - 兼容PostgreSQL接口"""
        async with self.get_connection() as conn:
            async with conn.cursor() as cursor:
                try:
                    await conn.begin()
                    for query, args in queries:
                        converted_query = self._convert_postgresql_query(query)
                        await cursor.execute(converted_query, args)
                    await conn.commit()
                except Exception as e:
                    await conn.rollback()
                    raise
    
    async def call_function(self, function_name: str, *args) -> Any:
        """调用数据库函数 - 兼容PostgreSQL接口"""
        # MySQL函数调用语法
        placeholders = ', '.join(['%s' for _ in args])
        query = f"SELECT {function_name}({placeholders})"
        return await self.fetch_val(query, *args)
    
    def _extract_table_name_from_insert(self, query: str) -> Optional[str]:
        """从INSERT语句中提取表名"""
        import re
        match = re.search(r'INSERT\s+INTO\s+["`]?(\w+)["`]?', query, re.IGNORECASE)
        return match.group(1) if match else None


class MySQLConnectionWrapper:
    """MySQL连接包装器，提供PostgreSQL兼容的接口"""
    
    def __init__(self, mysql_connection):
        self.connection = mysql_connection
    
    async def execute(self, query: str, *args) -> str:
        """执行SQL - PostgreSQL兼容接口"""
        db_manager = DatabaseManager()
        converted_query = db_manager._convert_postgresql_query(query)
        
        async with self.connection.cursor() as cursor:
            affected_rows = await cursor.execute(converted_query, args)
            return f"UPDATE {affected_rows}" if affected_rows > 0 else "UPDATE 0"
    
    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """获取单行 - PostgreSQL兼容接口"""
        db_manager = DatabaseManager()
        converted_query = db_manager._convert_postgresql_query(query)
        
        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(converted_query, args)
            result = await cursor.fetchone()
            return result
    
    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """获取多行 - PostgreSQL兼容接口"""
        db_manager = DatabaseManager()
        converted_query = db_manager._convert_postgresql_query(query)
        
        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(converted_query, args)
            results = await cursor.fetchall()
            return results or []
    
    async def fetchval(self, query: str, *args) -> Any:
        """获取单个值 - PostgreSQL兼容接口"""
        db_manager = DatabaseManager()
        converted_query = db_manager._convert_postgresql_query(query)
        
        async with self.connection.cursor() as cursor:
            await cursor.execute(converted_query, args)
            result = await cursor.fetchone()
            return result[0] if result else None
    
    async def transaction(self):
        """事务上下文管理器"""
        return self.connection
    
    async def close(self):
        """关闭连接"""
        pass  # 连接由连接池管理，无需手动关闭


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def initialize_database() -> None:
    """初始化数据库连接"""
    await db_manager.initialize()


async def close_database() -> None:
    """关闭数据库连接"""
    await db_manager.close()


def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例"""
    return db_manager