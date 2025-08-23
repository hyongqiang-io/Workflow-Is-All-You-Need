"""
飞书OAuth2.0认证API - 按照官方文档实现
Feishu OAuth2.0 Authentication API
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import httpx
from loguru import logger
from typing import Optional
import urllib.parse

from backend.config.feishu_config import FeishuConfig
from backend.utils.feishu_exceptions import create_feishu_exception, FeishuErrorCodes
from backend.models.user import UserCreate
from backend.api.dependencies import get_user_repository, get_auth_service

router = APIRouter()

class FeishuTokenRequest(BaseModel):
    """飞书token交换请求"""
    code: str
    state: Optional[str] = None

class FeishuTokenResponse(BaseModel):
    """飞书token交换响应"""
    success: bool
    message: str
    user_info: Optional[dict] = None

# 飞书应用配置 - 从统一配置管理读取
# 配置验证
if not FeishuConfig.validate_oauth_config():
    logger.error("飞书OAuth配置验证失败，请检查环境变量配置")

@router.get("/feishu/login")
async def feishu_login():
    """
    飞书登录入口 - 重定向到飞书授权页面
    按照官方文档构造授权链接
    """
    # 构造授权URL，按照官方文档格式
    auth_params = {
        "client_id": FeishuConfig.CLIENT_ID,
        "redirect_uri": FeishuConfig.REDIRECT_URI,
        "state": "workflow_system_2024",  # 自定义state参数
        "scope": FeishuConfig.SCOPE
    }
    
    # URL编码参数
    encoded_params = urllib.parse.urlencode(auth_params)
    auth_url = f"{FeishuConfig.AUTH_BASE_URL}?{encoded_params}"
    
    logger.info(f"飞书授权URL: {auth_url}")
    
    # 直接重定向到飞书授权页面
    return RedirectResponse(url=auth_url)

@router.post("/feishu/token", response_model=FeishuTokenResponse)
async def exchange_feishu_token(
    request: FeishuTokenRequest,
    user_repo: UserRepository = Depends(),
    auth_service: AuthService = Depends()
):
    """
    第六步：通过授权码获取user_access_token
    按照官方文档调用接口
    """
    try:
        logger.info(f"收到飞书授权码: {request.code[:10]}...")
        
        # 1. 调用飞书官方接口获取access_token
        token_data = {
            "grant_type": "authorization_code",
            "client_id": FeishuConfig.CLIENT_ID,
            "client_secret": FeishuConfig.CLIENT_SECRET,
            "code": request.code,
            "redirect_uri": FeishuConfig.REDIRECT_URI
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                FeishuConfig.TOKEN_URL,
                json=token_data,
                timeout=30.0
            )
            
            if token_response.status_code != 200:
                logger.error(f"飞书token交换失败: {token_response.status_code} - {token_response.text}")
                raise create_feishu_exception(
                    FeishuErrorCodes.OAUTH_TOKEN_EXCHANGE_FAILED,
                    f"飞书token交换失败: {token_response.status_code}",
                    status_code=400
                )
            
            token_result = token_response.json()
            
            if token_result.get("code") != 0:
                logger.error(f"飞书API返回错误: {token_result}")
                raise create_feishu_exception(
                    FeishuErrorCodes.API_RESPONSE_ERROR,
                    f"飞书API错误: {token_result.get('msg', 'Unknown error')}",
                    status_code=400
                )
            
            access_token = token_result["access_token"]
            refresh_token = token_result.get("refresh_token")
            expires_in = token_result.get("expires_in", 7200)
            
            logger.info(f"飞书access_token获取成功，有效期: {expires_in}秒")
        
        # 2. 使用access_token获取用户信息
        user_info = await get_feishu_user_info(access_token)
        
        # 3. 处理用户登录/注册
        user_result = await handle_user_login(user_info, user_repo, auth_service)
        
        logger.info(f"飞书登录成功，用户: {user_info.get('name', 'Unknown')}")
        
        return FeishuTokenResponse(
            success=True,
            message="飞书登录成功",
            user_info=user_result
        )
        
    except Exception as e:
        logger.error(f"飞书登录过程中发生未知错误: {e}")
        raise create_feishu_exception(
            FeishuErrorCodes.API_REQUEST_FAILED,
            "飞书登录过程中发生错误",
            status_code=500
        )

async def get_feishu_user_info(access_token: str) -> dict:
    """获取飞书用户信息"""
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://open.feishu.cn/open-apis/authen/v1/user_info",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        if user_response.status_code != 200:
            raise create_feishu_exception(
                FeishuErrorCodes.OAUTH_USER_INFO_FAILED,
                "获取飞书用户信息失败",
                status_code=400
            )
        
        user_data = user_response.json()
        
        if user_data.get("code") != 0:
            raise create_feishu_exception(
                FeishuErrorCodes.API_RESPONSE_ERROR,
                f"飞书用户信息API错误: {user_data.get('msg', 'Unknown error')}",
                status_code=400
            )
        
        return user_data["data"]

async def handle_user_login(
    feishu_user: dict, 
    user_repo: UserRepository, 
    auth_service: AuthService
) -> dict:
    """处理用户登录/注册逻辑"""
    
    feishu_open_id = feishu_user.get("open_id")
    feishu_email = feishu_user.get("email", f"{feishu_open_id}@feishu.local")
    
    # 检查用户是否已存在
    existing_user = await user_repo.get_user_by_email(feishu_email)
    
    if not existing_user:
        # 创建新用户
        user_create = UserCreate(
            username=feishu_user.get("name", f"feishu_{feishu_open_id}"),
            email=feishu_email,
            password="feishu_oauth_user",
            full_name=feishu_user.get("name"),
            phone=feishu_user.get("mobile", ""),
            department="",
            role="user"
        )
        
        created_user = await user_repo.create_user(user_create)
        if not created_user:
            raise create_feishu_exception(
                FeishuErrorCodes.USER_CREATION_FAILED,
                "创建用户失败",
                status_code=500
            )
        
        user_id = created_user["user_id"]
        logger.info(f"创建新的飞书用户: {created_user['username']}")
    else:
        user_id = existing_user["user_id"]
        logger.info(f"找到已存在的用户: {existing_user['username']}")
    
    # 生成JWT token
    jwt_token = await auth_service.create_access_token(user_id)
    
    return {
        "user_id": str(user_id),
        "username": feishu_user.get("name"),
        "access_token": jwt_token
    }

@router.get("/feishu/config")
async def get_feishu_config():
    """获取飞书OAuth配置信息"""
    return {
        "client_id": FeishuConfig.CLIENT_ID,
        "redirect_uri": FeishuConfig.REDIRECT_URI,
        "scope": FeishuConfig.SCOPE,
        "auth_url": f"/api/feishu/login"
    }
