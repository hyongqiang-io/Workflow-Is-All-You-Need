#!/usr/bin/env python3
"""
数据库配置脚本
Database Configuration Script
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from workflow_framework.scripts.init_database import DatabaseInitializer
from workflow_framework.config import get_settings
from loguru import logger


async def main():
    """主配置函数"""
    logger.info("开始配置PostgreSQL数据库...")
    
    # 检查环境变量
    settings = get_settings()
    logger.info(f"数据库配置:")
    logger.info(f"  主机: {settings.database.host}")
    logger.info(f"  端口: {settings.database.port}")
    logger.info(f"  数据库: {settings.database.database}")
    logger.info(f"  用户: {settings.database.username}")
    
    # 询问用户是否继续
    print("\n请确认数据库配置信息，按回车继续或Ctrl+C退出...")
    try:
        input()
    except KeyboardInterrupt:
        logger.info("用户取消配置")
        return
    
    try:
        # 初始化数据库
        initializer = DatabaseInitializer()
        
        # 询问是否包含示例数据
        include_sample = input("是否包含示例数据? (y/N): ").lower().strip() == 'y'
        logger.info(f"包含示例数据: {include_sample}")
        
        await initializer.initialize_all(include_sample_data=include_sample)
        
        logger.info("✅ 数据库配置完成!")
        logger.info("现在你可以启动应用程序:")
        
        # WSL路径转换
        python_path = "/mnt/d/anaconda3/envs/fornew/python"
        logger.info(f"  {python_path} main.py")
        
    except Exception as e:
        logger.error(f"❌ 数据库配置失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())