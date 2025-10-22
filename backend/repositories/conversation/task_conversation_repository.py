"""
任务对话数据访问层
Task Conversation Repository
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from ...utils.database import DatabaseManager
from ...utils.timestamp_utils import safe_format_timestamp


class TaskConversationRepository:
    """任务对话数据访问层"""

    def __init__(self):
        self.db = DatabaseManager()

    async def create_or_get_session(self, task_instance_id: uuid.UUID,
                                   user_id: uuid.UUID) -> Dict[str, Any]:
        """创建或获取对话会话"""
        try:
            logger.info(f"🔗 开始创建或获取对话会话: task_id={task_instance_id}, user_id={user_id}")

            # 先尝试获取现有会话
            existing_session = await self.get_active_session(task_instance_id, user_id)
            if existing_session:
                logger.info(f"✅ 找到现有会话: {existing_session.get('session_id')}")
                return existing_session

            # 创建新会话
            logger.info(f"🆕 创建新对话会话...")

            # MySQL不支持RETURNING，分两步操作
            session_id = str(uuid.uuid4())  # 生成新的session_id

            insert_query = """
            INSERT INTO task_conversation_session (session_id, task_instance_id, user_id)
            VALUES (%s, %s, %s)
            """
            await self.db.execute(insert_query, session_id, str(task_instance_id), str(user_id))

            # 查询刚插入的记录
            select_query = """
            SELECT session_id, task_instance_id, user_id, created_at, updated_at, is_active
            FROM task_conversation_session
            WHERE session_id = %s
            """
            result = await self.db.fetch_one(select_query, session_id)
            logger.info(f"📝 新会话数据库插入结果: {dict(result) if result else None}")

            if result:
                session = dict(result)
                logger.info(f"🕐 处理新会话的时间戳字段...")

                # 安全处理时间戳字段
                for timestamp_field in ['created_at', 'updated_at']:
                    if session.get(timestamp_field):
                        logger.info(f"处理{timestamp_field}: {session[timestamp_field]} (类型: {type(session[timestamp_field])})")
                        try:
                            session[timestamp_field] = safe_format_timestamp(session[timestamp_field])
                            logger.info(f"{timestamp_field}格式化成功: {session[timestamp_field]}")
                        except Exception as ts_error:
                            logger.error(f"❌ {timestamp_field}格式化失败: {ts_error}")
                            logger.error(f"原始时间戳: {repr(session[timestamp_field])}")
                            session[timestamp_field] = None

                logger.info(f"✅ 新对话会话创建成功: session_id={session.get('session_id')}")
                return session
            else:
                raise RuntimeError("创建对话会话失败")

        except Exception as e:
            logger.error(f"❌ 创建或获取对话会话失败: {e}")
            logger.error(f"task_id: {task_instance_id} (类型: {type(task_instance_id)})")
            logger.error(f"user_id: {user_id} (类型: {type(user_id)})")
            logger.error(f"错误类型: {type(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise

    async def get_active_session(self, task_instance_id: uuid.UUID,
                                user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取活跃的对话会话"""
        try:
            logger.info(f"🔍 查找活跃对话会话: task_id={task_instance_id}, user_id={user_id}")
            query = """
            SELECT session_id, task_instance_id, user_id, created_at, updated_at, is_active
            FROM task_conversation_session
            WHERE task_instance_id = %s AND user_id = %s AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """
            result = await self.db.fetch_one(query, str(task_instance_id), str(user_id))

            if result:
                session = dict(result)
                logger.info(f"📊 找到活跃会话，处理时间戳...")

                # 安全处理时间戳字段
                for timestamp_field in ['created_at', 'updated_at']:
                    if session.get(timestamp_field):
                        logger.info(f"处理{timestamp_field}: {session[timestamp_field]} (类型: {type(session[timestamp_field])})")
                        try:
                            session[timestamp_field] = safe_format_timestamp(session[timestamp_field])
                            logger.info(f"{timestamp_field}格式化成功: {session[timestamp_field]}")
                        except Exception as ts_error:
                            logger.error(f"❌ {timestamp_field}格式化失败: {ts_error}")
                            logger.error(f"原始时间戳: {repr(session[timestamp_field])}")
                            session[timestamp_field] = None

                logger.info(f"✅ 活跃会话获取成功: session_id={session.get('session_id')}")
                return session
            else:
                logger.info(f"🚫 未找到活跃会话")
                return None

        except Exception as e:
            logger.error(f"❌ 获取活跃对话会话失败: {e}")
            logger.error(f"task_id: {task_instance_id} (类型: {type(task_instance_id)})")
            logger.error(f"user_id: {user_id} (类型: {type(user_id)})")
            logger.error(f"错误类型: {type(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return None

    async def add_message(self, session_id: uuid.UUID, role: str, content: str,
                         context_data: Optional[Dict[str, Any]] = None,
                         attachments: Optional[List[str]] = None) -> Dict[str, Any]:
        """添加对话消息"""
        try:
            logger.info(f"💬 开始添加对话消息: session_id={session_id}, role={role}")

            # MySQL不支持RETURNING，分两步操作
            message_id = str(uuid.uuid4())  # 生成新的message_id

            import json
            context_json = json.dumps(context_data) if context_data else None
            attachments_json = json.dumps(attachments) if attachments else None

            insert_query = """
            INSERT INTO task_conversation_message (message_id, session_id, role, content, context_data, attachments)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            await self.db.execute(
                insert_query, message_id, str(session_id), role, content, context_json, attachments_json
            )

            # 查询刚插入的记录
            select_query = """
            SELECT message_id, session_id, role, content, context_data, attachments, created_at
            FROM task_conversation_message
            WHERE message_id = %s
            """
            result = await self.db.fetch_one(select_query, message_id)
            logger.info(f"📝 数据库插入结果: {dict(result) if result else None}")

            if result:
                message = dict(result)
                logger.info(f"🕐 处理返回消息的时间戳字段...")

                # 安全处理时间戳字段
                if message.get('created_at'):
                    logger.info(f"原始created_at: {message['created_at']} (类型: {type(message['created_at'])})")
                    try:
                        message['created_at'] = safe_format_timestamp(message['created_at'])
                        logger.info(f"时间戳格式化成功: {message['created_at']}")
                    except Exception as ts_error:
                        logger.error(f"❌ 时间戳格式化失败: {ts_error}")
                        logger.error(f"原始时间戳: {repr(message['created_at'])}")
                        message['created_at'] = None

                # 更新会话的updated_at
                logger.info(f"🔄 更新会话时间戳...")
                await self.update_session_timestamp(session_id)

                logger.info(f"✅ 对话消息添加成功: message_id={message.get('message_id')}")
                return message
            else:
                raise RuntimeError("添加对话消息失败")

        except Exception as e:
            logger.error(f"❌ 添加对话消息失败: {e}")
            logger.error(f"session_id: {session_id} (类型: {type(session_id)})")
            logger.error(f"错误类型: {type(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise

    async def get_session_messages(self, session_id: uuid.UUID,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """获取会话的所有消息"""
        try:
            logger.info(f"📜 开始获取会话消息: {session_id}, 限制: {limit}")
            query = """
            SELECT message_id, session_id, role, content, context_data, attachments, created_at
            FROM task_conversation_message
            WHERE session_id = %s
            ORDER BY created_at ASC
            LIMIT %s
            """
            results = await self.db.fetch_all(query, str(session_id), limit)
            logger.info(f"📊 查询到 {len(results)} 条原始消息")

            messages = []
            for i, result in enumerate(results):
                logger.info(f"🔄 处理消息 {i+1}/{len(results)}")
                message = dict(result)

                logger.info(f"原始消息数据: {list(message.keys())}")

                # 处理时间戳字段
                if message.get('created_at'):
                    logger.info(f"处理时间戳: {message['created_at']} (类型: {type(message['created_at'])})")
                    try:
                        message['created_at'] = safe_format_timestamp(message['created_at'])
                        logger.info(f"时间戳格式化成功: {message['created_at']}")
                    except Exception as ts_error:
                        logger.error(f"❌ 时间戳格式化失败: {ts_error}")
                        logger.error(f"原始时间戳: {repr(message['created_at'])}")
                        message['created_at'] = None

                # 解析JSON字段
                if message['context_data']:
                    try:
                        import json
                        message['context_data'] = json.loads(message['context_data'])
                    except:
                        message['context_data'] = None

                if message['attachments']:
                    try:
                        import json
                        message['attachments'] = json.loads(message['attachments'])
                    except:
                        message['attachments'] = []

                messages.append(message)
                logger.info(f"✅ 消息 {i+1} 处理完成")

            logger.info(f"✅ 会话消息获取完成: {len(messages)} 条")
            return messages

        except Exception as e:
            logger.error(f"❌ 获取会话消息失败: {e}")
            logger.error(f"会话ID: {session_id} (类型: {type(session_id)})")
            logger.error(f"错误类型: {type(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return []

    async def get_conversation_history(self, task_instance_id: uuid.UUID,
                                     user_id: uuid.UUID) -> Dict[str, Any]:
        """获取完整的对话历史"""
        try:
            # 获取会话信息
            session = await self.get_active_session(task_instance_id, user_id)
            if not session:
                return {
                    'task_instance_id': str(task_instance_id),
                    'messages': [],
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    'is_active': True
                }

            # 获取消息列表
            messages = await self.get_session_messages(session['session_id'])

            return {
                'task_instance_id': str(task_instance_id),
                'session_id': str(session['session_id']),
                'messages': messages,
                'created_at': safe_format_timestamp(session['created_at']),
                'updated_at': safe_format_timestamp(session['updated_at']),
                'is_active': session['is_active']
            }

        except Exception as e:
            logger.error(f"获取对话历史失败: {e}")
            raise

    async def clear_conversation(self, task_instance_id: uuid.UUID,
                               user_id: uuid.UUID) -> bool:
        """清空对话历史"""
        try:
            # 获取会话
            session = await self.get_active_session(task_instance_id, user_id)
            if not session:
                return True

            # 删除所有消息
            delete_messages_query = """
            DELETE FROM task_conversation_message
            WHERE session_id = $1
            """
            await self.db.execute(delete_messages_query, session['session_id'])

            # 删除会话
            delete_session_query = """
            DELETE FROM task_conversation_session
            WHERE session_id = $1
            """
            await self.db.execute(delete_session_query, session['session_id'])

            logger.info(f"已清空任务 {task_instance_id} 的对话历史")
            return True

        except Exception as e:
            logger.error(f"清空对话历史失败: {e}")
            return False

    async def update_session_timestamp(self, session_id: uuid.UUID):
        """更新会话时间戳"""
        try:
            logger.info(f"🕒 开始更新会话时间戳: {session_id}")
            query = """
            UPDATE task_conversation_session
            SET updated_at = CURRENT_TIMESTAMP
            WHERE session_id = %s
            """
            result = await self.db.execute(query, str(session_id))
            logger.info(f"✅ 会话时间戳更新成功: {session_id}")

        except Exception as e:
            logger.error(f"❌ 更新会话时间戳失败: {e}")
            logger.error(f"会话ID: {session_id} (类型: {type(session_id)})")
            logger.error(f"错误类型: {type(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise

    async def get_conversation_stats(self, task_instance_id: uuid.UUID) -> Dict[str, Any]:
        """获取对话统计信息"""
        try:
            logger.info(f"📊 开始获取对话统计: {task_instance_id}")
            query = """
            SELECT
                COUNT(m.message_id) as message_count,
                MIN(m.created_at) as first_message_at,
                MAX(m.created_at) as last_message_at,
                COUNT(CASE WHEN m.role = 'user' THEN m.message_id END) as user_message_count,
                COUNT(CASE WHEN m.role = 'assistant' THEN m.message_id END) as ai_message_count
            FROM task_conversation_session s
            LEFT JOIN task_conversation_message m ON s.session_id = m.session_id
            WHERE s.task_instance_id = %s
            """
            result = await self.db.fetch_one(query, str(task_instance_id))
            logger.info(f"📊 统计查询完成，结果: {dict(result) if result else None}")

            if result:
                stats = dict(result)
                logger.info(f"🕐 处理统计时间戳...")

                # 转换时间格式 - 使用安全函数
                if stats.get('first_message_at'):
                    logger.info(f"处理first_message_at: {stats['first_message_at']} (类型: {type(stats['first_message_at'])})")
                    try:
                        stats['first_message_at'] = safe_format_timestamp(stats['first_message_at'])
                        logger.info(f"first_message_at格式化成功: {stats['first_message_at']}")
                    except Exception as ts_error:
                        logger.error(f"❌ first_message_at格式化失败: {ts_error}")
                        logger.error(f"原始时间戳: {repr(stats['first_message_at'])}")
                        stats['first_message_at'] = None

                if stats.get('last_message_at'):
                    logger.info(f"处理last_message_at: {stats['last_message_at']} (类型: {type(stats['last_message_at'])})")
                    try:
                        stats['last_message_at'] = safe_format_timestamp(stats['last_message_at'])
                        logger.info(f"last_message_at格式化成功: {stats['last_message_at']}")
                    except Exception as ts_error:
                        logger.error(f"❌ last_message_at格式化失败: {ts_error}")
                        logger.error(f"原始时间戳: {repr(stats['last_message_at'])}")
                        stats['last_message_at'] = None

                logger.info(f"✅ 对话统计获取成功: {stats}")
                return stats
            else:
                logger.info(f"📊 没有找到对话数据，返回默认统计")
                return {
                    'message_count': 0,
                    'user_message_count': 0,
                    'ai_message_count': 0,
                    'first_message_at': None,
                    'last_message_at': None
                }

        except Exception as e:
            logger.error(f"❌ 获取对话统计失败: {e}")
            logger.error(f"任务ID: {task_instance_id} (类型: {type(task_instance_id)})")
            logger.error(f"错误类型: {type(e)}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            return {}