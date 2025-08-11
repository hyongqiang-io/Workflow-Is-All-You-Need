"""
安全工具
Security Utilities
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
from pydantic import BaseModel
import secrets

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT配置
SECRET_KEY = "your-secret-key-change-in-production"  # 生产环境中应该从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24小时


class Token(BaseModel):
    """访问令牌模型"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    username: str


class TokenData(BaseModel):
    """令牌数据模型"""
    user_id: Optional[str] = None
    username: Optional[str] = None


def hash_password(password: str) -> str:
    """
    加密密码
    
    Args:
        password: 明文密码
        
    Returns:
        加密后的密码哈希
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 已加密的密码哈希
        
    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌
    
    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量
        
    Returns:
        JWT访问令牌
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """
    验证访问令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        令牌数据或None（如果无效）
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        
        if user_id is None or username is None:
            return None
            
        return TokenData(user_id=user_id, username=username)
    except JWTError:
        return None


def generate_reset_token() -> str:
    """
    生成密码重置令牌
    
    Returns:
        32字符的随机令牌
    """
    return secrets.token_urlsafe(32)


def create_token_response(user_id: str, username: str) -> Token:
    """
    创建令牌响应
    
    Args:
        user_id: 用户ID
        username: 用户名
        
    Returns:
        令牌响应对象
    """
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id, "username": username},
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒
        user_id=user_id,
        username=username
    )


def extract_token_from_header(authorization: str) -> Optional[str]:
    """
    从Authorization头提取令牌
    
    Args:
        authorization: Authorization头的值
        
    Returns:
        提取的令牌或None
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    return authorization.split(" ")[1]