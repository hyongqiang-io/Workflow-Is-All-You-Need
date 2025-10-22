"""
Simulator对话服务
Simulator Conversation Service
"""

from typing import Optional
from backend.models.simulator import (
    CreateSimulatorSessionRequest, SendSimulatorMessageRequest,
    SimulatorDecisionRequest, SimulatorConversationSession,
    SimulatorConversationMessage, SimulatorExecutionResult,
    SimulatorSessionResponse, SimulatorSessionStatus, ConversationRole
)
from backend.repositories.simulator.simulator_conversation_repository import SimulatorConversationRepository
from backend.utils.database import get_db_connection


class SimulatorConversationService:
    """Simulator对话管理服务"""

    def __init__(self):
        self.db_manager = get_db_connection()

    async def create_session(self, request: CreateSimulatorSessionRequest) -> SimulatorConversationSession:
        """创建新的Simulator对话会话"""
        async with self.db_manager.get_connection() as connection:
            repo = SimulatorConversationRepository(connection.connection)  # 传递实际的aiomysql连接

            return await repo.create_session(
                task_instance_id=request.task_instance_id,
                node_instance_id=request.node_instance_id,
                processor_id=request.processor_id,
                weak_model=request.weak_model,
                strong_model=request.strong_model,
                max_rounds=request.max_rounds
            )

    async def get_session_with_messages(self, session_id: str) -> Optional[SimulatorSessionResponse]:
        """获取会话及其消息"""
        async with self.db_manager.get_connection() as connection:
            repo = SimulatorConversationRepository(connection.connection)

            session = await repo.get_session(session_id)
            if not session:
                return None

            messages = await repo.get_messages(session_id)

            # 判断是否可以继续对话
            can_continue = (
                session.status == SimulatorSessionStatus.ACTIVE and
                session.current_round < session.max_rounds
            )

            # 判断下一步行动
            next_action = self._determine_next_action(session, messages)

            return SimulatorSessionResponse(
                session=session,
                messages=messages,
                can_continue=can_continue,
                next_action=next_action
            )

    async def send_message(self, request: SendSimulatorMessageRequest) -> SimulatorConversationMessage:
        """发送消息"""
        async with self.db_manager.get_connection() as connection:
            repo = SimulatorConversationRepository(connection.connection)

            return await repo.add_message(
                session_id=request.session_id,
                role=request.role,
                content=request.content,
                metadata=request.metadata
            )

    async def make_decision(self, request: SimulatorDecisionRequest) -> SimulatorExecutionResult:
        """记录Simulator决策并结束会话"""
        async with self.db_manager.get_connection() as connection:
            repo = SimulatorConversationRepository(connection.connection)

            return await repo.record_decision(
                session_id=request.session_id,
                decision_type=request.decision_type,
                result_data=request.result_data,
                confidence_score=request.confidence_score,
                reasoning=request.decision_reasoning
            )

    async def interrupt_session(self, session_id: str, reason: str) -> bool:
        """中断对话会话"""
        async with self.db_manager.get_connection() as connection:
            repo = SimulatorConversationRepository(connection.connection)

            return await repo.interrupt_session(session_id, reason)

    def _determine_next_action(self, session, messages) -> str:
        """确定下一步动作"""
        if session.status != SimulatorSessionStatus.ACTIVE:
            return "session_complete"

        if session.current_round >= session.max_rounds:
            return "session_complete"

        if not messages:
            return "wait_for_weak_model"

        last_message = messages[-1]
        if last_message.role == ConversationRole.WEAK_MODEL:
            return "wait_for_strong_model"
        else:
            return "wait_for_weak_model"