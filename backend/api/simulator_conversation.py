"""
Simulator对话API接口
Simulator Conversation API
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import uuid

from backend.models.simulator import (
    CreateSimulatorSessionRequest, SendSimulatorMessageRequest,
    SimulatorDecisionRequest, SimulatorSessionResponse,
    SimulatorConversationSession, SimulatorConversationMessage,
    SimulatorExecutionResult
)
from backend.services.simulator_conversation_service import SimulatorConversationService


router = APIRouter(prefix="/api/simulator/conversation", tags=["Simulator对话"])


def get_simulator_conversation_service() -> SimulatorConversationService:
    """获取simulator对话服务实例"""
    return SimulatorConversationService()


@router.post("/sessions", response_model=SimulatorConversationSession)
async def create_session(
    request: CreateSimulatorSessionRequest,
    service: SimulatorConversationService = Depends(get_simulator_conversation_service)
):
    """创建新的Simulator对话会话"""
    try:
        session = await service.create_session(request)
        return session
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建会话失败: {str(e)}")


@router.get("/sessions/{session_id}", response_model=SimulatorSessionResponse)
async def get_session(
    session_id: str,
    service: SimulatorConversationService = Depends(get_simulator_conversation_service)
):
    """获取会话及其消息"""
    try:
        session_response = await service.get_session_with_messages(session_id)
        if not session_response:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session_response
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"获取会话失败: {str(e)}")


@router.post("/sessions/{session_id}/messages", response_model=SimulatorConversationMessage)
async def send_message(
    session_id: str,
    request: SendSimulatorMessageRequest,
    service: SimulatorConversationService = Depends(get_simulator_conversation_service)
):
    """发送消息到会话"""
    try:
        # 确保请求中的session_id与路径中的一致
        request.session_id = session_id
        message = await service.send_message(request)
        return message
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@router.post("/sessions/{session_id}/decision", response_model=SimulatorExecutionResult)
async def make_decision(
    session_id: str,
    request: SimulatorDecisionRequest,
    service: SimulatorConversationService = Depends(get_simulator_conversation_service)
):
    """做出最终决策"""
    try:
        # 确保请求中的session_id与路径中的一致
        request.session_id = session_id
        result = await service.make_decision(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"决策失败: {str(e)}")


@router.post("/sessions/{session_id}/interrupt")
async def interrupt_session(
    session_id: str,
    reason: str = "用户中断",
    service: SimulatorConversationService = Depends(get_simulator_conversation_service)
):
    """中断会话"""
    try:
        await service.interrupt_session(session_id, reason)
        return {"message": "会话已中断", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"中断会话失败: {str(e)}")


@router.get("/sessions/{session_id}/statistics")
async def get_session_statistics(
    session_id: str,
    service: SimulatorConversationService = Depends(get_simulator_conversation_service)
) -> Dict[str, Any]:
    """获取会话统计信息"""
    try:
        stats = await service.get_session_statistics(session_id)
        if not stats:
            raise HTTPException(status_code=404, detail="会话不存在")
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/sessions/task/{task_instance_id}")
async def get_sessions_by_task(
    task_instance_id: str,
    service: SimulatorConversationService = Depends(get_simulator_conversation_service)
):
    """根据任务实例ID获取所有相关会话"""
    try:
        # 这个功能需要在Repository中添加相应方法
        # 暂时返回空列表，后续可以扩展
        return {"task_instance_id": task_instance_id, "sessions": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


# 健康检查端点
@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "simulator_conversation"}