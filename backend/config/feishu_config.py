"""
飞书配置管理
Feishu Configuration Management
"""

import os
from typing import Optional
from loguru import logger


class FeishuConfig:
    """飞书配置管理类"""
    
    # OAuth2.0 认证配置
    CLIENT_ID: Optional[str] = None
    CLIENT_SECRET: Optional[str] = None
    REDIRECT_URI: Optional[str] = None
    SCOPE: str = "component:user_profile contact:user.id:readonly offline_access"
    
    # 机器人配置
    BOT_APP_ID: Optional[str] = None
    BOT_APP_SECRET: Optional[str] = None
    BOT_WEBHOOK_URL: Optional[str] = None
    
    # 授权页面配置
    AUTH_BASE_URL: str = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
    TOKEN_URL: str = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"
    USER_INFO_URL: str = "https://open.feishu.cn/open-apis/authen/v1/user_info"
    
    # 机器人API配置
    BOT_TOKEN_URL: str = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    BOT_USER_INFO_URL: str = "https://open.feishu.cn/open-apis/contact/v3/users"
    BOT_MESSAGE_URL: str = "https://open.feishu.cn/open-apis/im/v1/messages"
    
    @classmethod
    def load_from_env(cls):
        """从环境变量加载配置"""
        cls.CLIENT_ID = os.getenv("FEISHU_CLIENT_ID")
        cls.CLIENT_SECRET = os.getenv("FEISHU_CLIENT_SECRET")
        cls.REDIRECT_URI = os.getenv("FEISHU_REDIRECT_URI")
        cls.BOT_APP_ID = os.getenv("FEISHU_BOT_APP_ID")
        cls.BOT_APP_SECRET = os.getenv("FEISHU_BOT_APP_SECRET")
        cls.BOT_WEBHOOK_URL = os.getenv("FEISHU_BOT_WEBHOOK_URL")
        
        # 加载自定义配置
        custom_scope = os.getenv("FEISHU_SCOPE")
        if custom_scope:
            cls.SCOPE = custom_scope
    
    @classmethod
    def validate_oauth_config(cls) -> bool:
        """验证OAuth配置"""
        required_fields = ['CLIENT_ID', 'CLIENT_SECRET', 'REDIRECT_URI']
        missing = [field for field in required_fields if not getattr(cls, field)]
        
        if missing:
            logger.error(f"飞书OAuth配置缺失: {missing}")
            return False
        
        logger.info("飞书OAuth配置验证通过")
        return True
    
    @classmethod
    def validate_bot_config(cls) -> bool:
        """验证机器人配置"""
        required_fields = ['BOT_APP_ID', 'BOT_APP_SECRET']
        missing = [field for field in required_fields if not getattr(cls, field)]
        
        if missing:
            logger.warning(f"飞书机器人配置缺失: {missing}")
            return False
        
        logger.info("飞书机器人配置验证通过")
        return True
    
    @classmethod
    def validate_all(cls) -> bool:
        """验证所有配置"""
        oauth_valid = cls.validate_oauth_config()
        bot_valid = cls.validate_bot_config()
        
        if not oauth_valid:
            logger.error("飞书OAuth配置验证失败，飞书登录功能将不可用")
        
        if not bot_valid:
            logger.warning("飞书机器人配置验证失败，机器人通知功能将不可用")
        
        return oauth_valid
    
    @classmethod
    def get_oauth_config(cls) -> dict:
        """获取OAuth配置"""
        return {
            "client_id": cls.CLIENT_ID,
            "redirect_uri": cls.REDIRECT_URI,
            "scope": cls.SCOPE,
            "auth_url": cls.AUTH_BASE_URL
        }
    
    @classmethod
    def get_bot_config(cls) -> dict:
        """获取机器人配置"""
        return {
            "bot_app_id": cls.BOT_APP_ID,
            "bot_app_secret": cls.BOT_APP_SECRET,
            "bot_webhook_url": cls.BOT_WEBHOOK_URL
        }


# 初始化配置
FeishuConfig.load_from_env()
