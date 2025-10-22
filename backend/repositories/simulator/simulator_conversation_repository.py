"""
Simulator对话Repository
Simulator Conversation Repository
"""

import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiomysql
from backend.models.simulator import (
    SimulatorConversationSession, SimulatorConversationMessage,
    SimulatorExecutionResult, SimulatorSessionStatus,
    SimulatorDecision, ConversationRole, SimulatorExecutionType
)


class SimulatorConversationRepository:
    """Simulator对话数据库操作类"""

    def __init__(self, connection: aiomysql.Connection):
        self.connection = connection

    async def create_session(
        self,
        task_instance_id: str,
        node_instance_id: str,
        processor_id: str,
        weak_model: str,
        strong_model: str,
        max_rounds: int = 20
    ) -> SimulatorConversationSession:
        """创建新的Simulator对话会话"""
        session_id = str(uuid.uuid4())
        now = datetime.now()

        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO simulator_conversation_session
                (session_id, task_instance_id, node_instance_id, processor_id,
                 weak_model, strong_model, max_rounds, current_round, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session_id, task_instance_id, node_instance_id, processor_id,
                weak_model, strong_model, max_rounds, 0, SimulatorSessionStatus.ACTIVE.value,
                now, now
            ))
            await self.connection.commit()

        return SimulatorConversationSession(
            session_id=session_id,
            task_instance_id=task_instance_id,
            node_instance_id=node_instance_id,
            processor_id=processor_id,
            weak_model=weak_model,
            strong_model=strong_model,
            max_rounds=max_rounds,
            current_round=0,
            status=SimulatorSessionStatus.ACTIVE,
            created_at=now,
            updated_at=now
        )

    async def get_session(self, session_id: str) -> Optional[SimulatorConversationSession]:
        """根据ID获取会话"""
        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT * FROM simulator_conversation_session WHERE session_id = %s
            """, (session_id,))
            row = await cursor.fetchone()

            if not row:
                return None

            return SimulatorConversationSession(
                session_id=row['session_id'],
                task_instance_id=row['task_instance_id'],
                node_instance_id=row['node_instance_id'],
                processor_id=row['processor_id'],
                weak_model=row['weak_model'],
                strong_model=row['strong_model'],
                max_rounds=row['max_rounds'],
                current_round=row['current_round'],
                status=SimulatorSessionStatus(row['status']),
                final_decision=SimulatorDecision(row['final_decision']) if row['final_decision'] else None,
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                completed_at=row['completed_at']
            )

    async def add_message(
        self,
        session_id: str,
        role: ConversationRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SimulatorConversationMessage:
        """添加消息到会话"""
        message_id = str(uuid.uuid4())
        now = datetime.now()

        # 获取当前轮次
        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                SELECT current_round FROM simulator_conversation_session WHERE session_id = %s
            """, (session_id,))
            result = await cursor.fetchone()
            current_round = result[0] if result else 0

        # 插入消息
        async with self.connection.cursor() as cursor:
            # 序列化metadata为JSON字符串
            metadata_json = json.dumps(metadata) if metadata is not None else None

            await cursor.execute("""
                INSERT INTO simulator_conversation_message
                (message_id, session_id, round_number, role, content, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                message_id, session_id, current_round, role.value, content,
                metadata_json, now
            ))
            await self.connection.commit()

        return SimulatorConversationMessage(
            message_id=message_id,
            session_id=session_id,
            round_number=current_round,
            role=role,
            content=content,
            metadata=metadata,
            created_at=now
        )

    async def get_messages(self, session_id: str) -> List[SimulatorConversationMessage]:
        """获取会话的所有消息"""
        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT * FROM simulator_conversation_message
                WHERE session_id = %s
                ORDER BY round_number ASC, created_at ASC
            """, (session_id,))
            rows = await cursor.fetchall()

            return [
                SimulatorConversationMessage(
                    message_id=row['message_id'],
                    session_id=row['session_id'],
                    round_number=row['round_number'],
                    role=ConversationRole(row['role']),
                    content=row['content'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else None,
                    created_at=row['created_at']
                )
                for row in rows
            ]

    async def update_session_round(self, session_id: str) -> None:
        """更新会话轮次"""
        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                UPDATE simulator_conversation_session
                SET current_round = current_round + 1, updated_at = %s
                WHERE session_id = %s
            """, (datetime.now(), session_id))
            await self.connection.commit()

    async def complete_session(
        self,
        session_id: str,
        final_decision: SimulatorDecision,
        status: SimulatorSessionStatus = SimulatorSessionStatus.COMPLETED
    ) -> None:
        """完成会话"""
        now = datetime.now()
        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                UPDATE simulator_conversation_session
                SET status = %s, final_decision = %s, completed_at = %s, updated_at = %s
                WHERE session_id = %s
            """, (status.value, final_decision.value, now, now, session_id))
            await self.connection.commit()

    async def save_execution_result(
        self,
        session_id: str,
        task_instance_id: str,
        execution_type: SimulatorExecutionType,
        result_data: Dict[str, Any],
        final_decision: SimulatorDecision,
        confidence_score: Optional[float] = None,
        total_rounds: int = 0,
        decision_reasoning: Optional[str] = None
    ) -> SimulatorExecutionResult:
        """保存执行结果"""
        result_id = str(uuid.uuid4())
        now = datetime.now()

        async with self.connection.cursor() as cursor:
            # 序列化result_data为JSON字符串
            result_data_json = json.dumps(result_data) if result_data is not None else None

            await cursor.execute("""
                INSERT INTO simulator_execution_result
                (result_id, session_id, task_instance_id, execution_type,
                 result_data, confidence_score, total_rounds, decision_reasoning, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                result_id, session_id, task_instance_id, execution_type.value,
                result_data_json, confidence_score, total_rounds, decision_reasoning, now
            ))
            await self.connection.commit()

        return SimulatorExecutionResult(
            success=True,
            execution_type=execution_type,
            final_decision=final_decision,
            result_data=result_data,
            session_id=session_id,
            total_rounds=total_rounds,
            confidence_score=confidence_score,
            decision_reasoning=decision_reasoning
        )

    async def record_decision(
        self,
        session_id: str,
        decision_type: SimulatorDecision,
        result_data: Dict[str, Any],
        confidence_score: Optional[float] = None,
        reasoning: Optional[str] = None
    ) -> SimulatorExecutionResult:
        """记录Simulator决策并完成会话"""
        # 获取会话信息
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        # 完成会话
        await self.complete_session(session_id, decision_type)

        # 保存执行结果
        execution_result = await self.save_execution_result(
            session_id=session_id,
            task_instance_id=session.task_instance_id,
            execution_type=SimulatorExecutionType.DIRECT_SUBMIT,
            result_data=result_data,
            final_decision=decision_type,
            confidence_score=confidence_score,
            total_rounds=session.current_round,
            decision_reasoning=reasoning
        )

        return execution_result

    async def interrupt_session(self, session_id: str, reason: str) -> bool:
        """中断对话会话"""
        try:
            now = datetime.now()
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    UPDATE simulator_conversation_session
                    SET status = %s, completed_at = %s, updated_at = %s
                    WHERE session_id = %s
                """, (SimulatorSessionStatus.INTERRUPTED.value, now, now, session_id))
                await self.connection.commit()

            return True
        except Exception:
            return False