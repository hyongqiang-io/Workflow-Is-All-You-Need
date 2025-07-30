#!/usr/bin/env python3
"""
后端启动测试脚本
"""

import sys
import os
import asyncio
from loguru import logger

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_imports():
    """测试导入"""
    try:
        logger.info("测试导入模块...")
        
        # 测试基础模块
        from workflow_framework.config.settings import settings
        logger.info("✓ 配置模块导入成功")
        
        from workflow_framework.utils.database import initialize_database
        logger.info("✓ 数据库模块导入成功")
        
        from workflow_framework.api.auth import router as auth_router
        logger.info("✓ 认证模块导入成功")
        
        from workflow_framework.services.execution_service import execution_engine
        logger.info("✓ 执行引擎模块导入成功")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 模块导入失败: {e}")
        return False

async def test_database():
    """测试数据库连接"""
    try:
        logger.info("测试数据库连接...")
        
        from workflow_framework.utils.database import initialize_database
        await initialize_database()
        logger.info("✓ 数据库连接成功")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 数据库连接失败: {e}")
        return False

def test_dependencies():
    """测试依赖包"""
    try:
        logger.info("测试依赖包...")
        
        import fastapi
        logger.info(f"✓ FastAPI {fastapi.__version__}")
        
        import uvicorn
        logger.info(f"✓ Uvicorn {uvicorn.__version__}")
        
        import asyncpg
        logger.info(f"✓ AsyncPG {asyncpg.__version__}")
        
        import pydantic
        logger.info(f"✓ Pydantic {pydantic.__version__}")
        
        return True
        
    except ImportError as e:
        logger.error(f"✗ 依赖包缺失: {e}")
        return False

async def main():
    """主函数"""
    logger.info("开始后端启动测试...")
    
    # 测试依赖
    if not test_dependencies():
        logger.error("依赖包测试失败，请安装所需依赖")
        return
    
    # 测试导入
    if not await test_imports():
        logger.error("模块导入测试失败")
        return
    
    # 测试数据库
    if not await test_database():
        logger.error("数据库连接测试失败")
        return
    
    logger.info("✓ 所有测试通过，后端可以正常启动")

if __name__ == "__main__":
    asyncio.run(main()) 