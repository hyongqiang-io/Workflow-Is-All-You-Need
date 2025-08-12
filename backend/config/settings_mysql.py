"""
MySQL数据库配置管理模块 - 与PostgreSQL版本完全兼容
MySQL Database Configuration Management Module - Fully Compatible with PostgreSQL Version
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class DatabaseSettings(BaseSettings):
    """MySQL数据库配置 - 保持与PostgreSQL相同的接口"""
    host: str = "localhost"
    port: int = 3306  # MySQL默认端口
    database: str = "workflow_db"
    username: str = "root"  # MySQL默认用户
    password: str = "mysql123"
    charset: str = "utf8mb4"  # MySQL字符集，支持完整的UTF-8
    
    class Config:
        env_prefix = "DB_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    # 连接池配置
    min_connections: int = 5
    max_connections: int = 20
    
    @property
    def database_url(self) -> str:
        """获取数据库连接URL - 保持与PostgreSQL相同的接口"""
        # 为了兼容性，返回MySQL URL但格式类似PostgreSQL
        return f"mysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?charset={self.charset}"


class ApplicationSettings(BaseSettings):
    """应用程序配置 - 与PostgreSQL版本完全相同"""
    app_name: str = "Workflow Framework"
    debug: bool = False
    log_level: str = "INFO"
    
    # 安全配置
    secret_key: str = "default-secret-key"
    access_token_expire_minutes: int = 30
    
    class Config:
        extra = "ignore"


class Settings:
    """全局配置类 - 与PostgreSQL版本完全相同"""
    def __init__(self):
        self.database = DatabaseSettings()
        self.app = ApplicationSettings()


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取全局配置实例 - 与PostgreSQL版本完全相同"""
    return settings