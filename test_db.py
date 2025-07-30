"""
数据库测试脚本
"""

import asyncio
import asyncpg

async def test_db():
    try:
        # 连接数据库
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            database="workflow_db",
            user="postgres",
            password="postgresql"
        )
        
        print("连接数据库成功")
        
        # 查看表结构
        result = await conn.fetch('SELECT column_name, data_type FROM information_schema.columns WHERE table_name = $1', 'user')
        print("User表字段:")
        for row in result:
            print(f"  {row['column_name']}: {row['data_type']}")
        
        # 查看所有用户
        users = await conn.fetch('SELECT user_id, username, email FROM "user" WHERE is_deleted = FALSE')
        print(f"\n已有用户 ({len(users)} 个):")
        for user in users:
            print(f"  ID: {user['user_id']}, Username: {user['username']}, Email: {user['email']}")
        
        # 测试查询用户
        test_user = await conn.fetchrow('SELECT * FROM "user" WHERE username = $1 AND is_deleted = FALSE', 'testuser')
        if test_user:
            print(f"\n找到测试用户: {dict(test_user)}")
        else:
            print("\n未找到测试用户")
        
        await conn.close()
        
    except Exception as e:
        print(f"数据库测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())