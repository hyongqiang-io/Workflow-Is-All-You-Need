"""
用户认证API路由
Authentication API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger

from ..models.base import BaseResponse
from ..models.user import UserCreate, UserLogin, UserResponse
from ..services.auth_service import AuthService, RegistrationError, AuthenticationError
from ..utils.security import Token
from ..utils.middleware import get_current_active_user, CurrentUser, get_current_user_context
from ..utils.exceptions import (
    handle_registration_error, handle_authentication_error,
    ValidationError, ConflictError
)

# 创建路由器
router = APIRouter(prefix="/auth", tags=["认证"])

# 认证服务实例
auth_service = AuthService()


@router.post("/register", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """
    用户注册
    
    Args:
        user_data: 用户注册数据
        
    Returns:
        注册成功响应
        
    Raises:
        HTTPException: 注册失败时抛出
    """
    try:
        # 基本输入验证
        if not user_data.username or len(user_data.username.strip()) < 3:
            raise ValidationError("用户名至少需要3个字符", "username")
        
        if not user_data.password or len(user_data.password) < 6:
            raise ValidationError("密码至少需要6个字符", "password")
        
        if not user_data.email or "@" not in user_data.email:
            raise ValidationError("请提供有效的邮箱地址", "email")
        
        # 执行注册
        user_response = await auth_service.register_user(user_data)
        
        logger.info(f"用户注册成功: {user_response.username}")
        
        return BaseResponse(
            success=True,
            message="注册成功",
            data={
                "user": user_response.model_dump(),
                "message": "账户创建成功，请使用用户名和密码登录"
            }
        )
        
    except (RegistrationError, ValidationError, ConflictError) as e:
        logger.warning(f"用户注册失败: {e}")
        raise handle_registration_error(e)
    except Exception as e:
        logger.error(f"用户注册异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后再试"
        )


@router.post("/login", response_model=BaseResponse)
async def login_user(login_data: UserLogin):
    """
    用户登录
    
    Args:
        login_data: 登录数据
        
    Returns:
        登录成功响应（包含访问令牌）
        
    Raises:
        HTTPException: 登录失败时抛出
    """
    try:
        # 基本输入验证
        if not login_data.username_or_email or not login_data.username_or_email.strip():
            raise ValidationError("请提供用户名或邮箱", "username_or_email")
        
        if not login_data.password or not login_data.password.strip():
            raise ValidationError("请提供密码", "password")
        
        # 执行登录认证
        token = await auth_service.authenticate_user(login_data)
        
        logger.info(f"用户登录成功: {login_data.username_or_email}")
        
        return BaseResponse(
            success=True,
            message="登录成功",
            data={
                "token": token.model_dump(),
                "message": "欢迎回来！"
            }
        )
        
    except AuthenticationError as e:
        logger.warning(f"用户登录失败: {e}")
        raise handle_authentication_error(e)
    except ValidationError as e:
        logger.warning(f"登录输入验证失败: {e}")
        raise e
    except Exception as e:
        logger.error(f"用户登录异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后再试"
        )


@router.get("/me", response_model=BaseResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_active_user)):
    """
    获取当前用户信息
    
    Args:
        current_user: 当前用户（通过认证中间件获取）
        
    Returns:
        当前用户信息
    """
    try:
        return BaseResponse(
            success=True,
            message="获取用户信息成功",
            data={"user": current_user.model_dump()}
        )
        
    except Exception as e:
        logger.error(f"获取用户信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户信息失败"
        )


@router.post("/change-password", response_model=BaseResponse)
async def change_password(
    old_password: str,
    new_password: str,
    current_user_context: CurrentUser = Depends(get_current_user_context)
):
    """
    修改密码
    
    Args:
        old_password: 旧密码
        new_password: 新密码
        current_user_context: 当前用户上下文
        
    Returns:
        密码修改结果
        
    Raises:
        HTTPException: 修改失败时抛出
    """
    try:
        # 输入验证
        if not old_password or not old_password.strip():
            raise ValidationError("请提供当前密码", "old_password")
        
        if not new_password or len(new_password) < 6:
            raise ValidationError("新密码至少需要6个字符", "new_password")
        
        if old_password == new_password:
            raise ValidationError("新密码不能与当前密码相同", "new_password")
        
        # 修改密码
        success = await auth_service.change_password(
            current_user_context.user_id,
            old_password,
            new_password
        )
        
        if success:
            logger.info(f"用户 {current_user_context.username} 密码修改成功")
            return BaseResponse(
                success=True,
                message="密码修改成功",
                data={"message": "密码已更新，请使用新密码登录"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="密码修改失败"
            )
            
    except AuthenticationError as e:
        logger.warning(f"密码修改失败: {e}")
        raise handle_authentication_error(e)
    except ValidationError as e:
        logger.warning(f"密码修改输入验证失败: {e}")
        raise e
    except Exception as e:
        logger.error(f"密码修改异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败，请稍后再试"
        )


@router.post("/logout", response_model=BaseResponse)
async def logout_user(current_user: UserResponse = Depends(get_current_active_user)):
    """
    用户登出
    
    Args:
        current_user: 当前用户
        
    Returns:
        登出成功响应
        
    Note:
        由于使用JWT，服务端无状态，实际的令牌失效需要客户端处理
    """
    try:
        logger.info(f"用户登出: {current_user.username}")
        
        return BaseResponse(
            success=True,
            message="登出成功",
            data={
                "message": "您已成功登出，请删除本地存储的访问令牌"
            }
        )
        
    except Exception as e:
        logger.error(f"用户登出异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失败"
        )


@router.get("/check", response_model=BaseResponse)
async def check_authentication(current_user: UserResponse = Depends(get_current_active_user)):
    """
    检查认证状态
    
    Args:
        current_user: 当前用户
        
    Returns:
        认证状态信息
    """
    try:
        return BaseResponse(
            success=True,
            message="认证有效",
            data={
                "authenticated": True,
                "user": {
                    "user_id": str(current_user.user_id),
                    "username": current_user.username,
                    "role": current_user.role,
                    "status": current_user.status
                }
            }
        )
        
    except Exception as e:
        logger.error(f"认证检查异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="认证检查失败"
        )