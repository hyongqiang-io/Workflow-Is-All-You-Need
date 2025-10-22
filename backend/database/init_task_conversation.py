"""
初始化任务对话数据库表
Initialize Task Conversation Database Tables
"""

from loguru import logger
from ..utils.database import DatabaseManager


async def init_task_conversation_tables():
    """初始化任务对话相关的数据库表"""
    try:
        db = DatabaseManager()

        logger.info("🗃️ 开始创建任务对话数据库表...")

        # 任务对话会话表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_conversation_session (
                session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                task_instance_id UUID NOT NULL REFERENCES task_instance(task_instance_id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                is_active BOOLEAN DEFAULT TRUE
            )
        """)

        # 对话消息表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_conversation_message (
                message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID NOT NULL REFERENCES task_conversation_session(session_id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                context_data JSONB,
                attachments JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)

        # 创建索引
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_task_conversation_session_task_id ON task_conversation_session(task_instance_id)",
            "CREATE INDEX IF NOT EXISTS idx_task_conversation_session_user_id ON task_conversation_session(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_task_conversation_session_created_at ON task_conversation_session(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_task_conversation_message_session_id ON task_conversation_message(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_task_conversation_message_role ON task_conversation_message(role)",
            "CREATE INDEX IF NOT EXISTS idx_task_conversation_message_created_at ON task_conversation_message(created_at)"
        ]

        for index_sql in indexes:
            await db.execute(index_sql)

        logger.info("✅ 任务对话数据库表创建完成")

    except Exception as e:
        logger.error(f"❌ 创建任务对话数据库表失败: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(init_task_conversation_tables())