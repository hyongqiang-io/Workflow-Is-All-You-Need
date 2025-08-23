"""
飞书机器人服务
Feishu Bot Service for Task Notifications
"""

import httpx
import json
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime

from backend.config.feishu_config import FeishuConfig
from backend.utils.feishu_exceptions import create_feishu_exception, FeishuErrorCodes

class FeishuBotService:
    """飞书机器人服务"""
    
    def __init__(self):
        # 从统一配置管理获取飞书机器人配置
        self.bot_app_id = FeishuConfig.BOT_APP_ID
        self.bot_app_secret = FeishuConfig.BOT_APP_SECRET
        self.bot_webhook_url = FeishuConfig.BOT_WEBHOOK_URL
        
        # 机器人访问令牌
        self.bot_access_token = None
        self.token_expires_at = None
        
        # 用户ID映射缓存
        self.user_id_cache = {}
        
        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证机器人配置"""
        if not self.bot_app_id or not self.bot_app_secret:
            logger.warning("飞书机器人配置不完整，机器人功能将不可用")
            logger.warning(f"BOT_APP_ID: {'已配置' if self.bot_app_id else '未配置'}")
            logger.warning(f"BOT_APP_SECRET: {'已配置' if self.bot_app_secret else '未配置'}")
    
    async def get_bot_access_token(self) -> str:
        """获取机器人访问令牌"""
        try:
            # 检查令牌是否过期
            if (self.bot_access_token and self.token_expires_at and 
                datetime.now() < self.token_expires_at):
                return self.bot_access_token
            
            # 获取新的访问令牌
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    FeishuConfig.BOT_TOKEN_URL,
                    json={
                        "app_id": self.bot_app_id,
                        "app_secret": self.bot_app_secret
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    raise create_feishu_exception(
                        FeishuErrorCodes.BOT_TOKEN_FAILED,
                        f"获取机器人访问令牌失败: {response.status_code}",
                        status_code=400
                    )
                
                result = response.json()
                if result.get("code") != 0:
                    raise create_feishu_exception(
                        FeishuErrorCodes.API_RESPONSE_ERROR,
                        f"飞书API错误: {result.get('msg')}",
                        status_code=400
                    )
                
                self.bot_access_token = result["tenant_access_token"]
                # 令牌有效期通常是2小时，提前5分钟刷新
                expires_in = result.get("expire", 7200)
                self.token_expires_at = datetime.now().timestamp() + expires_in - 300
                
                logger.info("飞书机器人访问令牌获取成功")
                return self.bot_access_token
                
        except Exception as e:
            logger.error(f"获取飞书机器人访问令牌失败: {e}")
            raise
    
    async def get_user_open_id(self, user_id: str) -> Optional[str]:
        """根据用户ID获取飞书open_id"""
        try:
            # 先从缓存获取
            if user_id in self.user_id_cache:
                return self.user_id_cache[user_id]
            
            # 调用飞书API获取用户信息
            access_token = await self.get_bot_access_token()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{FeishuConfig.BOT_USER_INFO_URL}/{user_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"获取用户飞书信息失败: {response.status_code}")
                    return None
                
                result = response.json()
                if result.get("code") != 0:
                    logger.warning(f"飞书API错误: {result.get('msg')}")
                    return None
                
                user_info = result.get("data", {}).get("user", {})
                open_id = user_id  # 简化处理，直接使用user_id作为open_id
                
                if open_id:
                    # 缓存结果
                    self.user_id_cache[user_id] = open_id
                    return open_id
                
                return None
                
        except Exception as e:
            logger.error(f"获取用户飞书open_id失败: {e}")
            return None
    
    async def send_task_notification(self, user_id: str, task_info: Dict[str, Any]) -> bool:
        """发送代办任务通知到飞书"""
        try:
            # 获取用户的飞书open_id
            open_id = await self.get_user_open_id(user_id)
            if not open_id:
                logger.warning(f"用户 {user_id} 未找到飞书open_id，无法发送通知")
                return False
            
            # 构建消息内容
            message_content = self._build_task_message(task_info)
            
            # 发送消息
            success = await self._send_message_to_user(open_id, message_content)
            
            if success:
                logger.info(f"成功发送代办任务通知给用户 {user_id}")
            else:
                logger.error(f"发送代办任务通知给用户 {user_id} 失败")
            
            return success
            
        except Exception as e:
            logger.error(f"发送代办任务通知失败: {e}")
            return False
    
    def _build_task_message(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        """构建代办任务消息内容"""
        task_title = task_info.get("task_title", "未命名任务")
        workflow_name = task_info.get("workflow_name", "未知工作流")
        priority = task_info.get("priority", "普通")
        deadline = task_info.get("deadline")
        
        # 构建消息卡片
        message = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "📋 您有新的代办任务"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**任务名称**: {task_title}\n**所属工作流**: {workflow_name}\n**优先级**: {priority}"
                        }
                    }
                ]
            }
        }
        
        # 添加截止时间信息
        if deadline:
            message["card"]["elements"].append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**截止时间**: {deadline}"
                }
            })
        
        # 添加操作按钮
        message["card"]["elements"].extend([
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "查看详情"
                        },
                        "type": "primary",
                        "url": f"http://106.54.12.39/todo"  # 跳转到代办页面
                    }
                ]
            }
        ])
        
        return message
    
    async def _send_message_to_user(self, open_id: str, message_content: Dict[str, Any]) -> bool:
        """发送消息给指定用户"""
        try:
            access_token = await self.get_bot_access_token()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    FeishuConfig.BOT_MESSAGE_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "receive_id": open_id,
                        "msg_type": message_content["msg_type"],
                        "content": json.dumps(message_content["card"])
                    },
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.error(f"发送飞书消息失败: {response.status_code}")
                    return False
                
                result = response.json()
                if result.get("code") != 0:
                    logger.error(f"飞书消息API错误: {result.get('msg')}")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"发送飞书消息异常: {e}")
            return False
    
    async def send_batch_task_notifications(self, task_notifications: List[Dict[str, Any]]) -> Dict[str, int]:
        """批量发送代办任务通知"""
        results = {
            "success": 0,
            "failed": 0,
            "total": len(task_notifications)
        }
        
        for notification in task_notifications:
            user_id = notification["user_id"]
            task_info = notification["task_info"]
            
            success = await self.send_task_notification(user_id, task_info)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"批量发送代办任务通知完成: 成功 {results['success']}, 失败 {results['failed']}")
        return results

# 创建全局实例
feishu_bot_service = FeishuBotService()
