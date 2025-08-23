"""
飞书机器人API
Feishu Bot API for Task Notifications
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from loguru import logger

from ..services.feishu_bot_service import feishu_bot_service
from ..utils.auth import get_current_user
from ..models.user import User
from ..utils.feishu_exceptions import create_feishu_exception, FeishuErrorCodes

router = APIRouter()

class TaskNotificationRequest(BaseModel):
    """任务通知请求模型"""
    user_id: str
    task_info: Dict[str, Any]

class BatchNotificationRequest(BaseModel):
    """批量通知请求模型"""
    notifications: List[TaskNotificationRequest]

class NotificationResponse(BaseModel):
    """通知响应模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

@router.post("/feishu-bot/send-notification", response_model=NotificationResponse)
async def send_task_notification(
    request: TaskNotificationRequest,
    current_user: User = Depends(get_current_user)
):
    """发送单个任务通知"""
    try:
        logger.info(f"收到任务通知请求: 用户 {request.user_id}, 任务 {request.task_info.get('task_title')}")
        
        success = await feishu_bot_service.send_task_notification(
            request.user_id, 
            request.task_info
        )
        
        if success:
            return NotificationResponse(
                success=True,
                message="通知发送成功",
                data={"user_id": request.user_id, "task_title": request.task_info.get("task_title")}
            )
        else:
            return NotificationResponse(
                success=False,
                message="通知发送失败"
            )
            
    except Exception as e:
        logger.error(f"发送任务通知失败: {e}")
        raise create_feishu_exception(
            FeishuErrorCodes.BOT_MESSAGE_FAILED,
            f"发送通知失败: {str(e)}",
            status_code=500
        )

@router.post("/feishu-bot/send-batch-notifications", response_model=NotificationResponse)
async def send_batch_notifications(
    request: BatchNotificationRequest,
    current_user: User = Depends(get_current_user)
):
    """批量发送任务通知"""
    try:
        logger.info(f"收到批量通知请求: {len(request.notifications)} 个通知")
        
        # 转换为批量通知格式
        batch_data = []
        for notification in request.notifications:
            batch_data.append({
                "user_id": notification.user_id,
                "task_info": notification.task_info
            })
        
        results = await feishu_bot_service.send_batch_task_notifications(batch_data)
        
        return NotificationResponse(
            success=True,
            message=f"批量通知完成: 成功 {results['success']}, 失败 {results['failed']}",
            data=results
        )
        
    except Exception as e:
        logger.error(f"批量发送通知失败: {e}")
        raise create_feishu_exception(
            FeishuErrorCodes.BOT_MESSAGE_FAILED,
            f"批量发送通知失败: {str(e)}",
            status_code=500
        )

@router.get("/feishu-bot/status")
async def get_bot_status(current_user: User = Depends(get_current_user)):
    """获取机器人状态"""
    try:
        # 检查机器人配置
        bot_app_id = feishu_bot_service.bot_app_id
        bot_app_secret = feishu_bot_service.bot_app_secret
        
        if not bot_app_id or not bot_app_secret:
            return {
                "status": "not_configured",
                "message": "飞书机器人未配置",
                "config": {
                    "bot_app_id": bool(bot_app_id),
                    "bot_app_secret": bool(bot_app_secret)
                }
            }
        
        # 测试获取访问令牌
        try:
            access_token = await feishu_bot_service.get_bot_access_token()
            return {
                "status": "active",
                "message": "飞书机器人运行正常",
                "config": {
                    "bot_app_id": bool(bot_app_id),
                    "bot_app_secret": bool(bot_app_secret),
                    "access_token": bool(access_token)
                }
            }
        except Exception as token_error:
            return {
                "status": "error",
                "message": f"飞书机器人访问令牌获取失败: {str(token_error)}",
                "config": {
                    "bot_app_id": bool(bot_app_id),
                    "bot_app_secret": bool(bot_app_secret),
                    "access_token": False
                }
            }
            
    except Exception as e:
        logger.error(f"获取机器人状态失败: {e}")
        raise create_feishu_exception(
            FeishuErrorCodes.BOT_CONFIG_MISSING,
            f"获取机器人状态失败: {str(e)}",
            status_code=500
        )

@router.post("/feishu-bot/test-message")
async def test_bot_message(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """测试机器人消息发送"""
    try:
        # 发送测试消息
        test_task_info = {
            "task_title": "测试任务",
            "workflow_name": "测试工作流",
            "priority": "高",
            "deadline": "2024-12-31",
            "status": "pending"
        }
        
        success = await feishu_bot_service.send_task_notification(user_id, test_task_info)
        
        if success:
            return {"success": True, "message": "测试消息发送成功"}
        else:
            return {"success": True, "message": "测试消息发送失败"}
            
    except Exception as e:
        logger.error(f"测试机器人消息失败: {e}")
        raise create_feishu_exception(
            FeishuErrorCodes.BOT_MESSAGE_FAILED,
            f"测试消息失败: {str(e)}",
            status_code=500
        )
