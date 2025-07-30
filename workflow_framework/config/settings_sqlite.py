"""
SQLite配置 - 用于测试和开发
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class DatabaseSettings(BaseSettings):
    """SQLite数据库配置"""
    database_path: str = "workflow.db"
    
    class Config:
        env_prefix = "DB_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    @property
    def database_url(self) -> str:
        """获取SQLite连接URL"""
        return f"sqlite:///{self.database_path}"

class ApplicationSettings(BaseSettings):
    """应用程序配置"""
    app_name: str = "Workflow Framework"
    debug: bool = True
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