"""
Simulator对话数据库初始化
Initialize Simulator Conversation Tables
"""

import asyncio
import aiomysql
import os
import sys
from pathlib import Path

# 添加父目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, parent_dir)

from backend.config.settings import get_settings
from backend.database.simulator_conversation_schema import create_simulator_conversation_tables


async def init_simulator_conversation_tables():
    """初始化simulator对话相关数据表"""
    settings = get_settings()

    try:
        # 连接数据库
        connection = await aiomysql.connect(
            host=settings.database.host,
            port=settings.database.port,
            user=settings.database.username,
            password=settings.database.password,
            db=settings.database.database,
            charset='utf8mb4'
        )

        print("🔗 数据库连接成功")

        # 创建simulator对话表
        await create_simulator_conversation_tables(connection)
        print("✅ Simulator对话表创建完成")

        connection.close()
        print("🔚 数据库连接已关闭")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(init_simulator_conversation_tables())