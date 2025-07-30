#!/usr/bin/env python3
"""
数据库连接测试脚本
"""

import asyncio
import asyncpg
from workflow_framework.config import get_settings

async def test_db_connection():
    """测试数据库连接"""
    import os
    print("环境变量检查:")
    print(f"  DB_USER: {os.getenv('DB_USER', 'Not set')}")
    print(f"  DB_PASSWORD: {os.getenv('DB_PASSWORD', 'Not set')}")
    print(f"  DB_HOST: {os.getenv('DB_HOST', 'Not set')}")
    print(f"  DB_PORT: {os.getenv('DB_PORT', 'Not set')}")
    print(f"  DB_NAME: {os.getenv('DB_NAME', 'Not set')}")
    
    settings = get_settings()
    
    print(f"\n数据库配置:")
    print(f"  Host: {settings.database.host}")
    print(f"  Port: {settings.database.port}")
    print(f"  Database: {settings.database.database}")
    print(f"  Username: {settings.database.username}")
    print(f"  Password: {'*' * len(settings.database.password) if settings.database.password else '(empty)'}")
    
    connection_params = {
        'host': settings.database.host,
        'port': settings.database.port,
        'user': settings.database.username,
        'password': settings.database.password,
        'database': settings.database.database,
    }
    
    try:
        print("\n尝试连接数据库...")
        conn = await asyncpg.connect(**connection_params, timeout=10)
        print("✅ 数据库连接成功!")
        
        # 测试查询
        result = await conn.fetchval("SELECT version()")
        print(f"PostgreSQL版本: {result}")
        
        await conn.close()
        print("✅ 连接已关闭")
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(test_db_connection()) 