"""
项目设置和管理脚本
Project Setup and Management Script
"""

import asyncio
import argparse
from loguru import logger

from .init_database import DatabaseInitializer
from ..utils.database import initialize_database, close_database


class ProjectSetup:
    """项目设置管理器"""
    
    def __init__(self):
        self.db_initializer = DatabaseInitializer()
    
    async def setup_database(self, include_sample_data: bool = False):
        """设置数据库"""
        try:
            logger.info("开始设置数据库...")
            await self.db_initializer.initialize_all(include_sample_data)
            logger.info("数据库设置完成")
        except Exception as e:
            logger.error(f"数据库设置失败: {e}")
            raise
    
    async def test_connection(self):
        """测试数据库连接"""
        try:
            logger.info("测试数据库连接...")
            await initialize_database()
            logger.info("数据库连接测试成功")
            await close_database()
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            raise
    
    async def reset_database(self):
        """重置数据库（危险操作）"""
        try:
            logger.warning("正在重置数据库，这将删除所有数据！")
            
            # 重新创建架构
            await self.db_initializer.initialize_schema()
            await self.db_initializer.create_functions()
            await self.db_initializer.create_views()
            
            logger.info("数据库重置完成")
        except Exception as e:
            logger.error(f"数据库重置失败: {e}")
            raise
    
    def create_env_file(self):
        """创建环境配置文件"""
        try:
            import os
            from pathlib import Path
            
            env_path = Path.cwd() / '.env'
            
            if env_path.exists():
                logger.info(f".env 文件已存在: {env_path}")
                return
            
            env_content = """# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=workflow_db
DB_USER=postgres
DB_PASSWORD=postgresql
DB_MIN_CONNECTIONS=5
DB_MAX_CONNECTIONS=20

# 应用配置
DEBUG=true
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
"""
            
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            logger.info(f"创建 .env 文件: {env_path}")
            logger.info("请根据实际情况修改配置")
        except Exception as e:
            logger.error(f"创建 .env 文件失败: {e}")
            raise


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Workflow Framework Setup")
    parser.add_argument('command', choices=['setup', 'test', 'reset', 'env'], 
                       help='Command to execute')
    parser.add_argument('--with-sample-data', action='store_true',
                       help='Include sample data when setting up database')
    parser.add_argument('--force', action='store_true',
                       help='Force execution without confirmation')
    
    args = parser.parse_args()
    
    setup = ProjectSetup()
    
    try:
        if args.command == 'env':
            setup.create_env_file()
            
        elif args.command == 'setup':
            await setup.setup_database(args.with_sample_data)
            
        elif args.command == 'test':
            await setup.test_connection()
            
        elif args.command == 'reset':
            if not args.force:
                confirm = input("这将删除所有数据，确定要继续吗？(y/N): ")
                if confirm.lower() != 'y':
                    logger.info("操作已取消")
                    return
            
            await setup.reset_database()
            
    except KeyboardInterrupt:
        logger.info("操作被用户中断")
    except Exception as e:
        logger.error(f"操作失败: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())