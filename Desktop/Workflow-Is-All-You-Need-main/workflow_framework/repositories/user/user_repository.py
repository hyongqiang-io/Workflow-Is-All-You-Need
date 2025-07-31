"""
用户数据访问层
User Repository
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..base import BaseRepository
from ...models.user import User, UserCreate, UserUpdate
from ...utils.helpers import now_utc
from ...utils.security import hash_password, verify_password


class UserRepository(BaseRepository[User]):
    """用户数据访问层"""
    
    def __init__(self):
        super().__init__("user")
    
    async def create_user(self, user_data: UserCreate) -> Optional[Dict[str, Any]]:
        """创建用户"""
        try:
            # 检查用户名和邮箱是否已存在
            if await self.username_exists(user_data.username):
                raise ValueError(f"用户名 '{user_data.username}' 已存在")
            
            if await self.email_exists(user_data.email):
                raise ValueError(f"邮箱 '{user_data.email}' 已存在")
            
            # 准备数据，使用BCrypt哈希
            data = {
                "user_id": uuid.uuid4(),
                "username": user_data.username,
                "email": user_data.email,
                "password_hash": hash_password(user_data.password),
                "terminal_endpoint": user_data.terminal_endpoint,
                "profile": user_data.profile,
                "description": user_data.description,
                "role": user_data.role,
                "status": user_data.status,
                "created_at": now_utc(),
                "updated_at": now_utc(),
                "is_deleted": False
            }
            
            result = await self.create(data)
            if result:
                # 不返回密码哈希
                result_copy = dict(result)
                result_copy.pop('password_hash', None)
                return result_copy
            return None
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            raise
    
    
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        result = await self.get_by_id(user_id, "user_id")
        if result:
            result_copy = dict(result)
            result_copy.pop('password_hash', None)
            return result_copy
        return None
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        try:
            query = f'SELECT * FROM {self.table_name} WHERE username = $1 AND is_deleted = FALSE'
            result = await self.db.fetch_one(query, username)
            return result
        except Exception as e:
            logger.error(f"根据用户名获取用户失败: {e}")
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取用户"""
        try:
            query = f'SELECT * FROM {self.table_name} WHERE email = $1 AND is_deleted = FALSE'
            result = await self.db.fetch_one(query, email)
            return result
        except Exception as e:
            logger.error(f"根据邮箱获取用户失败: {e}")
            raise
    
    async def update_user(self, user_id: uuid.UUID, user_data: UserUpdate) -> Optional[Dict[str, Any]]:
        """更新用户 - 简化版本"""
        try:
            logger.info(f"开始更新用户: {user_id}")
            logger.info(f"更新数据: {user_data}")
            
            # 准备更新数据 - 只更新有值的字段  
            update_data = {}
            
            # 简单直接的字段更新，不做复杂验证
            if hasattr(user_data, 'username') and user_data.username:
                update_data["username"] = user_data.username
                
            if hasattr(user_data, 'email') and user_data.email:
                update_data["email"] = user_data.email
                
            if hasattr(user_data, 'terminal_endpoint') and user_data.terminal_endpoint:
                update_data["terminal_endpoint"] = user_data.terminal_endpoint
                
            if hasattr(user_data, 'description') and user_data.description is not None:
                update_data["description"] = user_data.description
                
            if hasattr(user_data, 'role') and user_data.role:
                update_data["role"] = user_data.role
            
            logger.info(f"准备更新的数据: {update_data}")
            
            if not update_data:
                logger.info("没有数据需要更新，返回当前用户信息")
                return await self.get_user_by_id(user_id)
            
            # 添加更新时间
            update_data["updated_at"] = now_utc()
            
            result = await self.update(user_id, update_data, "user_id")
            logger.info(f"数据库更新结果: {result}")
            
            if result:
                result_copy = dict(result)
                result_copy.pop('password_hash', None)
                return result_copy
            return None
            
        except Exception as e:
            logger.error(f"更新用户失败: {e}")
            import traceback
            logger.error(f"完整错误: {traceback.format_exc()}")
            raise
    
    async def delete_user(self, user_id: uuid.UUID, soft_delete: bool = True) -> bool:
        """删除用户"""
        return await self.delete(user_id, "user_id", soft_delete)
    
    async def username_exists(self, username: str) -> bool:
        """检查用户名是否存在"""
        return await self.exists({"username": username})
    
    async def email_exists(self, email: str) -> bool:
        """检查邮箱是否存在"""
        return await self.exists({"email": email})
    
    
    
    async def update_user_status(self, user_id: uuid.UUID, status: bool) -> bool:
        """更新用户状态"""
        try:
            result = await self.update(user_id, {"status": status}, "user_id")
            return result is not None
        except Exception as e:
            logger.error(f"更新用户状态失败: {e}")
            raise
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """用户认证"""
        try:
            user = await self.get_user_by_username(username)
            if user and verify_password(password, user['password_hash']):
                if not user['status']:
                    raise ValueError("用户账户已被禁用")
                # 不返回密码哈希
                user_copy = dict(user)
                user_copy.pop('password_hash', None)
                return user_copy
            return None
        except Exception as e:
            logger.error(f"用户认证失败: {e}")
            raise
    
    async def change_password(self, user_id: uuid.UUID, old_password: str, new_password: str) -> bool:
        """修改密码"""
        try:
            user = await self.get_by_id(user_id, "user_id")
            if not user:
                raise ValueError("用户不存在")
            
            if not verify_password(old_password, user['password_hash']):
                raise ValueError("原密码错误")
            
            new_password_hash = hash_password(new_password)
            result = await self.update(user_id, {"password_hash": new_password_hash}, "user_id")
            return result is not None
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            raise
    
    async def get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        """根据角色获取用户列表"""
        try:
            query = f"""
                SELECT user_id, username, email, terminal_endpoint, profile, 
                       description, role, status, created_at, updated_at
                FROM {self.table_name} 
                WHERE role = $1 AND is_deleted = FALSE 
                ORDER BY created_at DESC
            """
            results = await self.db.fetch_all(query, role)
            return results
        except Exception as e:
            logger.error(f"根据角色获取用户列表失败: {e}")
            raise
    
    async def search_users(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索用户"""
        try:
            query = f"""
                SELECT user_id, username, email, terminal_endpoint, profile, 
                       description, role, status, created_at, updated_at
                FROM {self.table_name} 
                WHERE (username ILIKE $1 OR email ILIKE $1 OR description ILIKE $1) 
                      AND is_deleted = FALSE 
                ORDER BY created_at DESC 
                LIMIT $2
            """
            keyword_pattern = f"%{keyword}%"
            results = await self.db.fetch_all(query, keyword_pattern, limit)
            return results
        except Exception as e:
            logger.error(f"搜索用户失败: {e}")
            raise
    
    async def get_all_active_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有激活用户"""
        try:
            query = f"""
                SELECT user_id, username, email, terminal_endpoint, profile, 
                       description, role, status, created_at, updated_at
                FROM {self.table_name} 
                WHERE status = TRUE AND is_deleted = FALSE 
                ORDER BY created_at DESC 
                LIMIT $1
            """
            results = await self.db.fetch_all(query, limit)
            return results
        except Exception as e:
            logger.error(f"获取所有激活用户失败: {e}")
            raise