"""
配置管理模块
Configuration Management Module
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class DatabaseSettings(BaseSettings):
    """数据库配置"""
    host: str = "localhost"
    port: int = 5432
    database: str = "workflow_db"
    username: str = "postgres"
    password: str = "postgresql"
    
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
        """获取数据库连接URL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class ApplicationSettings(BaseSettings):
    """应用程序配置"""
    app_name: str = "Workflow Framework"
    debug: bool = False
    log_level: str = "INFO"
    
    # 安全配置
    secret_key: str = "default-secret-key"
    access_token_expire_minutes: int = 30
    
    class Config:
        extra = "ignore"


class Settings:
    """全局配置类"""
    def __init__(self):
        self.database = DatabaseSettings()
        self.app = ApplicationSettings()


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取全局配置实例"""
    return settings