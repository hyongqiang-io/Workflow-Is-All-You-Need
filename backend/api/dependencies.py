"""
API依赖注入
API Dependencies
"""

from backend.repositories.user.user_repository import UserRepository
from backend.services.auth_service import AuthService


def get_user_repository() -> UserRepository:
    """获取用户仓库实例"""
    return UserRepository()


def get_auth_service() -> AuthService:
    """获取认证服务实例"""
    return AuthService()
