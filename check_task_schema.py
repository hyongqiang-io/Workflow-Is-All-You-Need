#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from workflow_framework.utils.database import db_manager

async def check_task_instance_schema():
    await db_manager.initialize()
    
    # 检查task_instance表的结构
    query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'task_instance'
        ORDER BY ordinal_position
    """
    
    result = await db_manager.fetch_all(query)
    print("task_instance表结构:")
    for row in result:
        print(f"  {row['column_name']}: {row['data_type']} {'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'}")
    
    await db_manager.close()

asyncio.run(check_task_instance_schema())