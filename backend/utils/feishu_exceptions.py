"""
飞书异常处理
Feishu Exception Handling
"""

from typing import Optional, Dict, Any
from backend.utils.exceptions import BusinessException


class FeishuException(BusinessException):
    """飞书基础异常类"""
    
    def __init__(
        self, 
        error_code: str, 
        message: str, 
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(error_code, message, status_code)
        self.details = details or {}


class FeishuOAuthException(FeishuException):
    """飞书OAuth认证异常"""
    pass


class FeishuBotException(FeishuException):
    """飞书机器人异常"""
    pass


class FeishuConfigException(FeishuException):
    """飞书配置异常"""
    pass


class FeishuAPIException(FeishuException):
    """飞书API调用异常"""
    
    def __init__(
        self, 
        error_code: str, 
        message: str, 
        api_response: Optional[Dict[str, Any]] = None,
        status_code: int = 400
    ):
        super().__init__(error_code, message, status_code)
        self.api_response = api_response or {}


# 预定义的飞书错误码
class FeishuErrorCodes:
    """飞书错误码定义"""
    
    # OAuth相关错误
    OAUTH_CONFIG_MISSING = "FEISHU_OAUTH_CONFIG_MISSING"
    OAUTH_AUTHORIZATION_FAILED = "FEISHU_OAUTH_AUTHORIZATION_FAILED"
    OAUTH_TOKEN_EXCHANGE_FAILED = "FEISHU_OAUTH_TOKEN_EXCHANGE_FAILED"
    OAUTH_USER_INFO_FAILED = "FEISHU_OAUTH_USER_INFO_FAILED"
    OAUTH_INVALID_CODE = "FEISHU_OAUTH_INVALID_CODE"
    
    # 机器人相关错误
    BOT_CONFIG_MISSING = "FEISHU_BOT_CONFIG_MISSING"
    BOT_TOKEN_FAILED = "FEISHU_BOT_TOKEN_FAILED"
    BOT_MESSAGE_FAILED = "FEISHU_BOT_MESSAGE_FAILED"
    BOT_USER_NOT_FOUND = "FEISHU_BOT_USER_NOT_FOUND"
    
    # API相关错误
    API_REQUEST_FAILED = "FEISHU_API_REQUEST_FAILED"
    API_RESPONSE_ERROR = "FEISHU_API_RESPONSE_ERROR"
    API_TIMEOUT = "FEISHU_API_TIMEOUT"
    
    # 用户相关错误
    USER_CREATION_FAILED = "FEISHU_USER_CREATION_FAILED"
    USER_NOT_FOUND = "FEISHU_USER_NOT_FOUND"
    USER_LOGIN_FAILED = "FEISHU_USER_LOGIN_FAILED"


# 错误消息映射
FEISHU_ERROR_MESSAGES = {
    FeishuErrorCodes.OAUTH_CONFIG_MISSING: "飞书OAuth配置缺失",
    FeishuErrorCodes.OAUTH_AUTHORIZATION_FAILED: "飞书授权失败",
    FeishuErrorCodes.OAUTH_TOKEN_EXCHANGE_FAILED: "飞书token交换失败",
    FeishuErrorCodes.OAUTH_USER_INFO_FAILED: "获取飞书用户信息失败",
    FeishuErrorCodes.OAUTH_INVALID_CODE: "无效的授权码",
    FeishuErrorCodes.BOT_CONFIG_MISSING: "飞书机器人配置缺失",
    FeishuErrorCodes.BOT_TOKEN_FAILED: "获取机器人访问令牌失败",
    FeishuErrorCodes.BOT_MESSAGE_FAILED: "发送机器人消息失败",
    FeishuErrorCodes.BOT_USER_NOT_FOUND: "未找到用户飞书信息",
    FeishuErrorCodes.API_REQUEST_FAILED: "飞书API请求失败",
    FeishuErrorCodes.API_RESPONSE_ERROR: "飞书API响应错误",
    FeishuErrorCodes.API_TIMEOUT: "飞书API请求超时",
    FeishuErrorCodes.USER_CREATION_FAILED: "创建用户失败",
    FeishuErrorCodes.USER_NOT_FOUND: "用户不存在",
    FeishuErrorCodes.USER_LOGIN_FAILED: "用户登录失败"
}


def create_feishu_exception(
    error_code: str, 
    message: Optional[str] = None, 
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None
) -> FeishuException:
    """创建飞书异常实例"""
    if message is None:
        message = FEISHU_ERROR_MESSAGES.get(error_code, "飞书操作失败")
    
    if error_code.startswith("FEISHU_OAUTH"):
        return FeishuOAuthException(error_code, message, status_code, details)
    elif error_code.startswith("FEISHU_BOT"):
        return FeishuBotException(error_code, message, status_code, details)
    elif error_code.startswith("FEISHU_API"):
        return FeishuAPIException(error_code, message, status_code, details)
    else:
        return FeishuException(error_code, message, status_code, details)
