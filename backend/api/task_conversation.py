"""
人类任务AI对话API路由
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid

from ..utils.middleware import get_current_user
from ..models.user import UserResponse
from ..services.task_conversation_service import TaskConversationService


router = APIRouter(prefix="/api/tasks", tags=["task-conversation"])


class ConversationMessageRequest(BaseModel):
    message: str
    include_context: bool = True
    context_type: str = "summary"  # full, summary, minimal


class ConversationMessageResponse(BaseModel):
    message_id: str
    content: str
    suggestions: List[str] = []
    context_used: Optional[dict] = None
    conversation_length: int


@router.post("/{task_id}/conversation/send")
async def send_conversation_message(
    task_id: str,
    request: ConversationMessageRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """发送对话消息并获取AI回复"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔥 API接收到对话发送请求: task_id={task_id}, user={current_user.user_id}")
        logger.info(f"请求内容: message_length={len(request.message)}, include_context={request.include_context}")

        # 安全转换UUID
        task_uuid = uuid.UUID(task_id)

        # current_user.user_id可能已经是UUID对象，需要安全处理
        if isinstance(current_user.user_id, uuid.UUID):
            user_uuid = current_user.user_id
            logger.info(f"✅ user_id已经是UUID对象: {user_uuid}")
        else:
            user_uuid = uuid.UUID(current_user.user_id)
            logger.info(f"✅ user_id转换为UUID: {user_uuid}")

        logger.info(f"✅ UUID处理完成: task_uuid={task_uuid}, user_uuid={user_uuid}")

        logger.info(f"🔧 创建TaskConversationService...")
        service = TaskConversationService()

        logger.info(f"📞 调用service.send_message...")
        result = await service.send_message(
            task_id=task_uuid,
            user_id=user_uuid,
            message=request.message,
            include_context=request.include_context,
            context_type=request.context_type
        )
        logger.info(f"✅ service.send_message调用成功")

        return {
            "success": True,
            "data": result
        }

    except ValueError as e:
        logger.error(f"❌ API ValueError: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.error(f"❌ API PermissionError: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API Exception: {e}")
        logger.error(f"错误类型: {type(e)}")
        import traceback
        logger.error(f"API错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"发送消息失败: {str(e)}")


@router.get("/{task_id}/conversation/history")
async def get_conversation_history(
    task_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """获取任务的对话历史"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📜 API接收到对话历史请求: task_id={task_id}, user={current_user.user_id}")

        # 安全转换UUID
        task_uuid = uuid.UUID(task_id)

        # current_user.user_id可能已经是UUID对象，需要安全处理
        if isinstance(current_user.user_id, uuid.UUID):
            user_uuid = current_user.user_id
            logger.info(f"✅ user_id已经是UUID对象: {user_uuid}")
        else:
            user_uuid = uuid.UUID(current_user.user_id)
            logger.info(f"✅ user_id转换为UUID: {user_uuid}")

        logger.info(f"✅ UUID处理完成: task_uuid={task_uuid}, user_uuid={user_uuid}")

        logger.info(f"🔧 创建TaskConversationService...")
        service = TaskConversationService()

        logger.info(f"📞 调用service.get_conversation_history...")
        conversation = await service.get_conversation_history(
            task_id=task_uuid,
            user_id=user_uuid
        )
        logger.info(f"✅ service.get_conversation_history调用成功")

        return {
            "success": True,
            "data": conversation
        }

    except ValueError as e:
        logger.error(f"❌ API ValueError: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.error(f"❌ API PermissionError: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API Exception: {e}")
        logger.error(f"错误类型: {type(e)}")
        import traceback
        logger.error(f"API错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取对话历史失败: {str(e)}")


@router.delete("/{task_id}/conversation/clear")
async def clear_conversation_history(
    task_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """清空任务的对话历史"""
    try:
        task_uuid = uuid.UUID(task_id)
        user_uuid = uuid.UUID(current_user.user_id)

        service = TaskConversationService()
        result = await service.clear_conversation(
            task_id=task_uuid,
            user_id=user_uuid
        )

        return {
            "success": True,
            "data": {"cleared": result}
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空对话历史失败: {str(e)}")


@router.get("/{task_id}/conversation/stats")
async def get_conversation_stats(
    task_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """获取任务对话统计信息"""
    try:
        task_uuid = uuid.UUID(task_id)

        # 验证权限（任务所有者或管理员）
        service = TaskConversationService()
        stats = await service.get_conversation_stats(
            task_id=task_uuid,
            user_id=uuid.UUID(current_user.user_id)
        )

        return {
            "success": True,
            "data": stats
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话统计失败: {str(e)}")


# 管理员接口
@router.get("/admin/conversations/search")
async def admin_search_conversations(
    task_title: Optional[str] = None,
    user_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """管理员搜索对话记录（审计功能）"""
    try:
        # 验证管理员权限
        if current_user.role not in ['admin', 'manager']:
            raise HTTPException(status_code=403, detail="需要管理员权限")

        service = TaskConversationService()
        conversations = await service.admin_search_conversations(
            task_title=task_title,
            user_name=user_name,
            start_date=start_date,
            end_date=end_date
        )

        return {
            "success": True,
            "data": conversations
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索对话记录失败: {str(e)}")


@router.get("/workflow/{workflow_instance_id}/conversation-nodes")
async def get_workflow_conversation_nodes(
    workflow_instance_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """获取工作流实例中包含对话的节点列表"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 获取工作流实例对话节点: workflow_instance_id={workflow_instance_id}")

        workflow_uuid = uuid.UUID(workflow_instance_id)

        service = TaskConversationService()
        conversation_nodes = await service.get_workflow_conversation_nodes(
            workflow_instance_id=workflow_uuid,
            user_id=uuid.UUID(current_user.user_id)
        )

        return {
            "success": True,
            "data": conversation_nodes
        }

    except ValueError as e:
        logger.error(f"❌ API ValueError: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        logger.error(f"❌ API PermissionError: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"❌ API Exception: {e}")
        import traceback
        logger.error(f"API错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取对话节点失败: {str(e)}")