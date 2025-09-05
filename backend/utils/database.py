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

from ..config.settings import get_settings


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
            'autocommit': True,   # 🔧 修复：恢复自动提交，避免单个操作不提交
            'connect_timeout': 10,
            # 改用init_command设置锁等待时间
            'init_command': (
                'SET SESSION innodb_lock_wait_timeout=5; '  # 减少锁等待时间为5秒
                'SET SESSION lock_wait_timeout=5'           # 设置表级锁等待时间
            )
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
        
        # 处理布尔值比较 - MySQL中TRUE/FALSE需要转换为1/0
        converted_query = re.sub(r'=\s*TRUE\b', '= 1', converted_query, flags=re.IGNORECASE)
        converted_query = re.sub(r'=\s*FALSE\b', '= 0', converted_query, flags=re.IGNORECASE)
        converted_query = re.sub(r'\bIS\s+TRUE\b', '= 1', converted_query, flags=re.IGNORECASE)
        converted_query = re.sub(r'\bIS\s+FALSE\b', '= 0', converted_query, flags=re.IGNORECASE)
        
        # 处理RETURNING子句（MySQL不支持，需要特殊处理）
        if 'RETURNING *' in converted_query.upper():
            converted_query = converted_query.replace('RETURNING *', '')
            # 移除可能的尾随空白和换行
            converted_query = converted_query.rstrip()
            # 标记需要获取受影响的记录
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
            async with conn.connection.cursor() as cursor:
                affected_rows = await cursor.execute(converted_query, args)
                return f"UPDATE {affected_rows}" if affected_rows > 0 else "UPDATE 0"
    
    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """查询单条记录 - 兼容PostgreSQL接口"""
        converted_query = self._convert_postgresql_query(query)
        needs_last_insert = '-- NEEDS_LAST_INSERT' in converted_query
        converted_query = converted_query.replace(' -- NEEDS_LAST_INSERT', '')
        
        async with self.get_connection() as conn:
            async with conn.connection.cursor(aiomysql.DictCursor) as cursor:
                if needs_last_insert:
                    # 检查是INSERT还是UPDATE查询
                    original_query = query.strip().upper()
                    if original_query.startswith('INSERT'):
                        # 处理INSERT ... RETURNING的情况
                        await cursor.execute(converted_query, args)
                        
                        # 获取刚插入的记录
                        table_name = self._extract_table_name_from_insert(query)
                        if table_name:
                            # 尝试多种主键字段查询策略
                            primary_key_queries = [
                                # 方案1: 使用UUID主键字段（常见于工作流系统）
                                f"SELECT * FROM `{table_name}` ORDER BY created_at DESC LIMIT 1",
                                # 方案2: 使用AUTO_INCREMENT主键
                                f"SELECT * FROM `{table_name}` WHERE id = LAST_INSERT_ID()",
                                # 方案3: 通用查询最新记录
                                f"SELECT * FROM `{table_name}` ORDER BY COALESCE(created_at, NOW()) DESC LIMIT 1"
                            ]
                            
                            for pk_query in primary_key_queries:
                                try:
                                    await cursor.execute(pk_query)
                                    result = await cursor.fetchone()
                                    if result:
                                        logger.debug(f"成功获取插入记录 from {table_name}: {pk_query[:50]}...")
                                        return result
                                except Exception as e:
                                    logger.debug(f"主键查询失败 {pk_query[:50]}...: {e}")
                                    continue
                            
                            # 如果所有查询都失败，记录警告但返回空字典表示成功插入
                            logger.warning(f"无法查询刚插入的记录，表名: {table_name}")
                            return {"_insert_success": True, "table": table_name}
                        else:
                            logger.error(f"无法提取表名from INSERT查询: {query[:100]}")
                            return {"_insert_success": True, "_error": "table_name_extraction_failed"}
                    
                    elif original_query.startswith('UPDATE'):
                        # 处理UPDATE ... RETURNING的情况
                        logger.debug(f"[DEBUG] 原始UPDATE查询完整内容: {query}")
                        logger.debug(f"[DEBUG] 转换UPDATE查询完整内容: {converted_query}")
                        logger.debug(f"[DEBUG] UPDATE参数: {args}")
                        
                        await cursor.execute(converted_query, args)
                        affected_rows = cursor.rowcount
                        
                        logger.debug(f"[DEBUG] UPDATE影响行数: {affected_rows}")
                        
                        if affected_rows > 0:
                            # 尝试从WHERE子句中提取主键信息来查询更新后的记录
                            table_name = self._extract_table_name_from_update(query)
                            where_conditions = self._extract_where_conditions_from_update(query, args)
                            
                            logger.debug(f"[DEBUG] 提取的表名: {table_name}")
                            logger.debug(f"[DEBUG] 提取的WHERE条件: {where_conditions}")
                            
                            if table_name and where_conditions:
                                try:
                                    # 构建查询语句来获取更新后的记录
                                    where_clause = " AND ".join([f"`{key}` = %s" for key in where_conditions.keys()])
                                    query_values = list(where_conditions.values())
                                    
                                    select_query = f"SELECT * FROM `{table_name}` WHERE {where_clause} LIMIT 1"
                                    logger.debug(f"[DEBUG] 查询更新后记录SQL: {select_query}")
                                    logger.debug(f"[DEBUG] 查询参数: {query_values}")
                                    
                                    await cursor.execute(select_query, query_values)
                                    result = await cursor.fetchone()
                                    
                                    if result:
                                        logger.debug(f"[DEBUG] 成功获取更新记录: {list(result.keys())[:5]}...")
                                        return result
                                    else:
                                        logger.warning(f"[DEBUG] 查询更新后记录返回空")
                                except Exception as e:
                                    logger.error(f"[DEBUG] UPDATE后查询失败: {e}")
                            
                            # 如果无法查询更新后的记录，返回成功标记
                            logger.info(f"[DEBUG] UPDATE成功，影响行数: {affected_rows}")
                            return {"_update_success": True, "affected_rows": affected_rows}
                        else:
                            # 没有记录被更新 - 简化日志，避免垃圾信息
                            logger.debug(f"[DEBUG] UPDATE操作未影响任何记录 (可能记录不存在或WHERE条件不匹配)")
                            return None
                    
                    else:
                        # 对于其他查询，正常执行
                        await cursor.execute(converted_query, args)
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
            async with conn.connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(converted_query, args)
                results = await cursor.fetchall()
                return results or []
    
    async def fetch_val(self, query: str, *args) -> Any:
        """查询单个值 - 兼容PostgreSQL接口"""
        converted_query = self._convert_postgresql_query(query)
        
        async with self.get_connection() as conn:
            async with conn.connection.cursor() as cursor:
                await cursor.execute(converted_query, args)
                result = await cursor.fetchone()
                return result[0] if result else None
    
    async def call_function(self, function_name: str, *args) -> Any:
        """调用数据库函数 - 兼容PostgreSQL接口"""
        # MySQL函数调用语法
        placeholders = ', '.join(['%s' for _ in args])
        query = f"SELECT {function_name}({placeholders})"
        return await self.fetch_val(query, *args)
    
    async def execute_transaction(self, queries: List[Tuple[str, tuple]]) -> None:
        """执行事务 - 兼容PostgreSQL接口"""
        async with self.get_connection() as conn:
            async with conn.connection.cursor() as cursor:
                try:
                    await conn.connection.begin()
                    for query, args in queries:
                        converted_query = self._convert_postgresql_query(query)
                        await cursor.execute(converted_query, args)
                    await conn.connection.commit()
                except Exception as e:
                    await conn.connection.rollback()
                    raise
    
    @asynccontextmanager
    async def transaction(self):
        """数据库事务上下文管理器"""
        async with self.get_connection() as conn:
            try:
                # 开始事务
                await conn.connection.begin()
                logger.debug("🔄 事务开始")
                yield conn
                # 提交事务
                await conn.connection.commit()
                logger.debug("✅ 事务提交成功")
            except Exception as e:
                # 回滚事务
                await conn.connection.rollback()
                logger.error(f"❌ 事务回滚: {e}")
                raise
    
    def _extract_table_name_from_insert(self, query: str) -> Optional[str]:
        """从INSERT语句中提取表名"""
        import re
        # 支持各种表名格式: "table", `table`, table, "schema"."table"
        patterns = [
            r'INSERT\s+INTO\s+["`]?(\w+)["`]?',  # 简单表名
            r'INSERT\s+INTO\s+"([^"]+)"',  # 带双引号的表名
            r'INSERT\s+INTO\s+`([^`]+)`',  # 带反引号的表名
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                # 移除可能的模式引号
                table_name = table_name.strip('"').strip('`')
                logger.debug(f"从INSERT语句中提取表名: {table_name}")
                return table_name
        
        logger.warning(f"无法从INSERT语句中提取表名: {query[:100]}...")
        return None
    
    def _extract_table_name_from_update(self, query: str) -> Optional[str]:
        """从UPDATE语句中提取表名"""
        import re
        # 支持各种表名格式: "table", `table`, table
        patterns = [
            r'UPDATE\s+["`]?(\w+)["`]?\s+SET',  # 简单表名
            r'UPDATE\s+"([^"]+)"\s+SET',  # 带双引号的表名
            r'UPDATE\s+`([^`]+)`\s+SET',  # 带反引号的表名
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                # 移除可能的引号
                table_name = table_name.strip('"').strip('`')
                logger.debug(f"从UPDATE语句中提取表名: {table_name}")
                return table_name
        
        logger.warning(f"无法从UPDATE语句中提取表名: {query[:100]}...")
        return None
    
    def _extract_where_conditions_from_update(self, query: str, args: tuple) -> Optional[Dict[str, Any]]:
        """从UPDATE语句的WHERE子句中提取条件"""
        import re
        try:
            # 查找WHERE子句，排除RETURNING
            where_match = re.search(r'WHERE\s+(.+?)(?:\s+RETURNING|\s+ORDER\s+BY|\s+LIMIT|\s*$)', query, re.IGNORECASE | re.DOTALL)
            if not where_match:
                return None
            
            where_clause = where_match.group(1).strip()
            
            # 提取字段名（简单匹配 field = $n 的模式）
            field_patterns = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\$(\d+)', where_clause, re.IGNORECASE)
            
            conditions = {}
            for field_name, param_num in field_patterns:
                param_index = int(param_num) - 1  # $1 对应 args[0]
                # 确保参数索引在范围内
                if param_index < len(args):
                    # 移除字段名的引号
                    clean_field_name = field_name.strip('"`')
                    conditions[clean_field_name] = args[param_index]
                else:
                    logger.warning(f"[DEBUG] 参数索引超出范围: ${param_num} (索引{param_index}) >= args长度{len(args)}")
                    logger.warning(f"[DEBUG] 完整args: {args}")
                    # 尝试从args末尾获取可能的UUID参数
                    if clean_field_name in ['node_base_id', 'workflow_base_id'] and len(args) >= 2:
                        if clean_field_name == 'node_base_id':
                            conditions[clean_field_name] = args[-2]  # 倒数第二个参数
                        elif clean_field_name == 'workflow_base_id':
                            conditions[clean_field_name] = args[-1]  # 最后一个参数
            
            # 处理布尔值字段的特殊情况 (PostgreSQL TRUE/FALSE -> MySQL 1/0)
            logger.debug(f"[DEBUG] 检查布尔字段前的conditions: {conditions}")
            logger.debug(f"[DEBUG] WHERE子句内容: '{where_clause}'")
            
            for field_name in ['is_current_version', 'is_deleted']:
                if field_name not in conditions:
                    # 从WHERE子句中查找布尔值条件
                    bool_pattern = re.search(rf'{field_name}\s*=\s*(TRUE|FALSE)', where_clause, re.IGNORECASE)
                    logger.debug(f"[DEBUG] 查找{field_name}布尔模式: {bool_pattern}")
                    if bool_pattern:
                        bool_value = bool_pattern.group(1).upper()
                        mysql_bool_value = 1 if bool_value == 'TRUE' else 0
                        conditions[field_name] = mysql_bool_value
                        logger.debug(f"[DEBUG] 添加布尔条件: {field_name} = {mysql_bool_value} (原值: {bool_value})")
            
            logger.debug(f"[DEBUG] 最终提取的WHERE条件: {conditions}")
            return conditions if conditions else None
            
        except Exception as e:
            logger.debug(f"提取WHERE条件失败: {e}")
            return None


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
    
    @asynccontextmanager
    async def transaction(self):
        """事务上下文管理器 - 提供真正的事务支持"""
        async with self.connection.cursor() as cursor:
            try:
                await cursor.execute("START TRANSACTION")
                logger.debug("事务开始")
                yield self
                await cursor.execute("COMMIT")
                logger.debug("事务提交成功")
            except Exception as e:
                await cursor.execute("ROLLBACK")
                logger.error(f"事务回滚: {e}")
                raise
    
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