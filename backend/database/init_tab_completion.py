"""
Tab补全数据库初始化脚本
Initialize Tab Completion Database Tables
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from database.tab_completion_schema import get_create_table_sql, get_table_descriptions
from utils.database import get_database


async def create_tab_completion_tables():
    """创建Tab补全相关的数据库表"""
    db = get_database()

    try:
        logger.info("🔍 [DB-INIT] 开始创建Tab补全数据库表")

        table_sqls = get_create_table_sql()
        table_descriptions = get_table_descriptions()

        async with db.transaction() as conn:
            for i, table_sql in enumerate(table_sqls, 1):
                try:
                    # 执行表创建SQL
                    await conn.execute(table_sql)

                    # 提取表名
                    table_name = extract_table_name(table_sql)

                    logger.info(f"🔍 [DB-INIT] ✅ 表 {i}/{len(table_sqls)} 创建成功: {table_name}")

                    # 输出表描述
                    if table_name in table_descriptions:
                        logger.info(f"🔍 [DB-INIT] 📝 {table_name}: {table_descriptions[table_name].strip()}")

                except Exception as table_error:
                    logger.error(f"🔍 [DB-INIT] ❌ 表创建失败: {str(table_error)}")
                    # 提取出错的表名
                    table_name = extract_table_name(table_sql)
                    logger.error(f"🔍 [DB-INIT] 失败的表: {table_name}")

                    # 如果是已存在的表，继续执行
                    if "already exists" in str(table_error).lower() or "table" in str(table_error).lower():
                        logger.warning(f"🔍 [DB-INIT] ⚠️  表 {table_name} 已存在，跳过创建")
                        continue
                    else:
                        raise table_error

        logger.info("🔍 [DB-INIT] ✅ 所有Tab补全表创建完成")

        # 验证表是否创建成功
        await verify_tables()

    except Exception as e:
        logger.error(f"🔍 [DB-INIT] ❌ Tab补全表创建失败: {str(e)}")
        raise


async def verify_tables():
    """验证表是否创建成功"""
    db = get_database()

    expected_tables = [
        'user_interaction_logs',
        'user_behavior_patterns',
        'suggestion_effectiveness',
        'global_tab_completion_stats',
        'user_tab_completion_sessions'
    ]

    try:
        logger.info("🔍 [DB-VERIFY] 开始验证Tab补全表结构")

        async with db.transaction() as conn:
            # 查询现有表
            result = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name IN %s
            """, (expected_tables,))

            existing_tables = [row['table_name'] for row in result]

            # 检查哪些表存在/缺失
            missing_tables = set(expected_tables) - set(existing_tables)

            if missing_tables:
                logger.error(f"🔍 [DB-VERIFY] ❌ 缺失表: {', '.join(missing_tables)}")
                return False
            else:
                logger.info(f"🔍 [DB-VERIFY] ✅ 所有表验证通过: {', '.join(existing_tables)}")

                # 检查每个表的基本结构
                for table_name in existing_tables:
                    column_count = await conn.fetchval(f"""
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_schema = DATABASE()
                        AND table_name = %s
                    """, table_name)

                    logger.info(f"🔍 [DB-VERIFY] 📊 表 {table_name}: {column_count} 个字段")

                return True

    except Exception as e:
        logger.error(f"🔍 [DB-VERIFY] ❌ 表验证失败: {str(e)}")
        return False


def extract_table_name(sql: str) -> str:
    """从CREATE TABLE SQL中提取表名"""
    try:
        # 查找 "CREATE TABLE IF NOT EXISTS" 或 "CREATE TABLE" 后的表名
        import re

        # 匹配模式：CREATE TABLE [IF NOT EXISTS] `table_name` 或 table_name
        pattern = r'CREATE TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+`?(\w+)`?'
        match = re.search(pattern, sql, re.IGNORECASE)

        if match:
            return match.group(1)
        else:
            return "unknown_table"
    except:
        return "unknown_table"


async def drop_tab_completion_tables():
    """删除Tab补全相关的数据库表（谨慎使用）"""
    db = get_database()

    tables_to_drop = [
        'user_tab_completion_sessions',
        'global_tab_completion_stats',
        'suggestion_effectiveness',
        'user_behavior_patterns',
        'user_interaction_logs'  # 最后删除，因为其他表可能有外键引用
    ]

    try:
        logger.warning("🔍 [DB-DROP] ⚠️  开始删除Tab补全数据库表")

        async with db.transaction() as conn:
            for table_name in tables_to_drop:
                try:
                    await conn.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                    logger.warning(f"🔍 [DB-DROP] ✅ 表已删除: {table_name}")
                except Exception as e:
                    logger.error(f"🔍 [DB-DROP] ❌ 表删除失败: {table_name} - {str(e)}")

        logger.warning("🔍 [DB-DROP] ✅ Tab补全表删除完成")

    except Exception as e:
        logger.error(f"🔍 [DB-DROP] ❌ 表删除操作失败: {str(e)}")
        raise


async def reset_tab_completion_tables():
    """重置Tab补全表（删除后重新创建）"""
    try:
        logger.info("🔍 [DB-RESET] 开始重置Tab补全数据库表")

        # 先删除
        await drop_tab_completion_tables()

        # 等待一下确保删除完成
        await asyncio.sleep(1)

        # 重新创建
        await create_tab_completion_tables()

        logger.info("🔍 [DB-RESET] ✅ Tab补全表重置完成")

    except Exception as e:
        logger.error(f"🔍 [DB-RESET] ❌ 表重置失败: {str(e)}")
        raise


# 主执行函数
async def main():
    """主函数：创建Tab补全相关表"""
    try:
        await create_tab_completion_tables()
        print("✅ Tab补全数据库表初始化成功")
    except Exception as e:
        print(f"❌ Tab补全数据库表初始化失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())