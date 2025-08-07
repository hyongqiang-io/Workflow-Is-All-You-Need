"""
数据库连接管理器
Database Connection Manager
"""

import asyncio
import asyncpg
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from contextlib import asynccontextmanager

from ..config import get_settings


class DatabaseManager:
    """数据库连接管理器"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.settings = get_settings()
        self._connection_params = {
            'host': self.settings.database.host,
            'port': self.settings.database.port,
            'user': self.settings.database.username,
            'password': self.settings.database.password,
            'database': self.settings.database.database,
            'command_timeout': 60,
            'server_settings': {
                'application_name': 'backend',
                'client_encoding': 'utf8'
            }
        }
    
    async def initialize(self) -> None:
        """初始化数据库连接池"""
        try:
            # 先测试单个连接
            test_conn = await asyncpg.connect(**self._connection_params, timeout=10)
            await test_conn.close()
            logger.info("单个连接测试成功")
            
            # 在Windows上，我们使用单连接模式而不是连接池
            logger.info("使用单连接模式（Windows兼容）")
            
        except Exception as e:
            logger.error(f"数据库连接初始化失败: {e}")
            raise
    
    async def close(self) -> None:
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()
            logger.info("数据库连接池已关闭")
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接上下文管理器"""
        # 每次创建新连接，避免连接池问题
        connection = await asyncpg.connect(**self._connection_params, timeout=10)
        try:
            yield connection
        finally:
            await connection.close()
    
    async def execute(self, query: str, *args) -> str:
        """执行SQL命令（INSERT, UPDATE, DELETE）"""
        async with self.get_connection() as conn:
            return await conn.execute(query, *args)
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """查询单条记录"""
        async with self.get_connection() as conn:
            result = await conn.fetchrow(query, *args)
            return dict(result) if result else None
    
    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """查询多条记录"""
        async with self.get_connection() as conn:
            results = await conn.fetch(query, *args)
            return [dict(row) for row in results]
    
    async def fetch_val(self, query: str, *args) -> Any:
        """查询单个值"""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)
    
    async def execute_transaction(self, queries: List[Tuple[str, tuple]]) -> None:
        """执行事务"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                for query, args in queries:
                    await conn.execute(query, *args)
    
    async def call_function(self, function_name: str, *args) -> Any:
        """调用数据库函数"""
        placeholders = ', '.join([f'${i+1}' for i in range(len(args))])
        query = f"SELECT {function_name}({placeholders})"
        return await self.fetch_val(query, *args)


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