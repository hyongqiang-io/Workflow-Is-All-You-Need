"""
用户认证服务
Authentication Service
"""

import uuid
from typing import Optional, Dict, Any
from loguru import logger

from ..models.user import UserCreate, UserLogin, UserResponse
from ..repositories.user.user_repository import UserRepository
from ..utils.security import hash_password, verify_password, create_token_response, Token
from ..utils.helpers import now_utc
import json


class AuthenticationError(Exception):
    """认证错误"""
    pass


class RegistrationError(Exception):
    """注册错误"""
    pass


class AuthService:
    """用户认证服务"""
    
    def __init__(self):
        self.user_repository = UserRepository()
    
    def _parse_profile(self, profile_data):
        """解析profile数据"""
        if isinstance(profile_data, str):
            try:
                return json.loads(profile_data)
            except:
                return {}
        elif profile_data is None:
            return {}
        return profile_data
    
    async def register_user(self, user_data: UserCreate) -> UserResponse:
        """
        用户注册
        
        Args:
            user_data: 用户创建数据
            
        Returns:
            用户响应数据
            
        Raises:
            RegistrationError: 注册失败时抛出
        """
        try:
            # 检查用户名是否已存在
            if await self.user_repository.username_exists(user_data.username):
                raise RegistrationError(f"用户名 '{user_data.username}' 已存在")
            
            # 检查邮箱是否已存在
            if await self.user_repository.email_exists(user_data.email):
                raise RegistrationError(f"邮箱 '{user_data.email}' 已被注册")
            
            # 加密密码
            hashed_password = hash_password(user_data.password)
            
            # 准备用户数据
            create_data = {
                "user_id": uuid.uuid4(),
                "username": user_data.username,
                "password_hash": hashed_password,
                "email": user_data.email,
                "terminal_endpoint": user_data.terminal_endpoint,
                "profile": user_data.profile or {},
                "description": user_data.description,
                "role": user_data.role or "user",  # 默认角色为普通用户
                "status": True,  # 新用户默认为激活状态
                "created_at": now_utc(),
                "updated_at": now_utc(),
                "is_deleted": False
            }
            
            # 创建用户
            user_record = await self.user_repository.create(create_data)
            if not user_record:
                raise RegistrationError("创建用户失败")
            
            logger.info(f"用户注册成功: {user_data.username} ({user_record['user_id']})")
            
            # 返回用户信息（不包含密码）
            return UserResponse(
                user_id=user_record['user_id'],
                username=user_record['username'],
                email=user_record['email'],
                terminal_endpoint=user_record.get('terminal_endpoint'),
                profile=self._parse_profile(user_record.get('profile')),
                description=user_record.get('description'),
                role=user_record['role'],
                status=user_record['status'],
                created_at=user_record['created_at'].isoformat() if user_record['created_at'] else None,
                updated_at=user_record['updated_at'].isoformat() if user_record['updated_at'] else None
            )
            
        except RegistrationError:
            raise
        except Exception as e:
            logger.error(f"用户注册失败: {e}")
            raise RegistrationError(f"注册失败: {str(e)}")
    
    async def authenticate_user(self, login_data: UserLogin) -> Token:
        """
        用户登录认证
        
        Args:
            login_data: 登录数据
            
        Returns:
            访问令牌
            
        Raises:
            AuthenticationError: 认证失败时抛出
        """
        try:
            # 根据用户名或邮箱查找用户
            user_record = None
            if "@" in login_data.username_or_email:
                # 邮箱登录
                user_record = await self.user_repository.get_user_by_email(login_data.username_or_email)
            else:
                # 用户名登录
                user_record = await self.user_repository.get_user_by_username(login_data.username_or_email)
            
            # 检查用户是否存在
            if not user_record:
                logger.warning(f"登录失败: 用户不存在 - {login_data.username_or_email}")
                raise AuthenticationError("用户名或密码错误")
            
            # 检查用户状态
            if not user_record.get('status', False):
                logger.warning(f"登录失败: 用户已被禁用 - {login_data.username_or_email}")
                raise AuthenticationError("账户已被禁用")
            
            # 验证密码
            if not verify_password(login_data.password, user_record['password_hash']):
                logger.warning(f"登录失败: 密码错误 - {login_data.username_or_email}")
                raise AuthenticationError("用户名或密码错误")
            
            logger.info(f"用户登录成功: {user_record['username']} ({user_record['user_id']})")
            
            # 生成访问令牌
            return create_token_response(
                str(user_record['user_id']),
                user_record['username']
            )
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"用户认证失败: {e}")
            raise AuthenticationError(f"认证失败: {str(e)}")
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[UserResponse]:
        """
        根据ID获取用户信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户响应数据或None
        """
        try:
            user_record = await self.user_repository.get_user_by_id(user_id)
            if not user_record:
                return None
            
            return UserResponse(
                user_id=user_record['user_id'],
                username=user_record['username'],
                email=user_record['email'],
                terminal_endpoint=user_record.get('terminal_endpoint'),
                profile=self._parse_profile(user_record.get('profile')),
                description=user_record.get('description'),
                role=user_record['role'],
                status=user_record['status'],
                created_at=user_record['created_at'].isoformat() if user_record['created_at'] else None,
                updated_at=user_record['updated_at'].isoformat() if user_record['updated_at'] else None
            )
            
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[UserResponse]:
        """
        根据用户名获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            用户响应数据或None
        """
        try:
            user_record = await self.user_repository.get_user_by_username(username)
            if not user_record:
                return None
            
            return UserResponse(
                user_id=user_record['user_id'],
                username=user_record['username'],
                email=user_record['email'],
                terminal_endpoint=user_record.get('terminal_endpoint'),
                profile=self._parse_profile(user_record.get('profile')),
                description=user_record.get('description'),
                role=user_record['role'],
                status=user_record['status'],
                created_at=user_record['created_at'].isoformat() if user_record['created_at'] else None,
                updated_at=user_record['updated_at'].isoformat() if user_record['updated_at'] else None
            )
            
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None
    
    async def change_password(self, user_id: uuid.UUID, old_password: str, new_password: str) -> bool:
        """
        修改用户密码
        
        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            是否修改成功
        """
        try:
            # 获取用户信息
            user_record = await self.user_repository.get_user_by_id(user_id)
            if not user_record:
                raise AuthenticationError("用户不存在")
            
            # 验证旧密码
            if not verify_password(old_password, user_record['password_hash']):
                raise AuthenticationError("原密码错误")
            
            # 加密新密码
            new_password_hash = hash_password(new_password)
            
            # 更新密码
            result = await self.user_repository.update(
                user_id,
                {"password_hash": new_password_hash, "updated_at": now_utc()},
                "user_id"
            )
            
            if result:
                logger.info(f"用户 {user_record['username']} 密码修改成功")
                return True
            
            return False
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            raise AuthenticationError(f"修改密码失败: {str(e)}")
    
    async def update_user_status(self, user_id: uuid.UUID, status: bool) -> bool:
        """
        更新用户状态
        
        Args:
            user_id: 用户ID
            status: 新状态
            
        Returns:
            是否更新成功
        """
        try:
            result = await self.user_repository.update_user_status(user_id, status)
            if result:
                action = "激活" if status else "禁用"
                logger.info(f"用户 {user_id} 状态已{action}")
            return result
            
        except Exception as e:
            logger.error(f"更新用户状态失败: {e}")
            return False