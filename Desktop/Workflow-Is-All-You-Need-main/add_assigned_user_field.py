#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from workflow_framework.utils.database import db_manager

async def add_assigned_user_field():
    await db_manager.initialize()
    
    try:
        # 添加 assigned_user_id 字段到 task_instance 表
        query = """
            ALTER TABLE task_instance 
            ADD COLUMN IF NOT EXISTS assigned_user_id UUID
        """
        
        await db_manager.execute(query)
        print("Successfully added assigned_user_id field to task_instance table")
        
    except Exception as e:
        print(f"Error adding field: {e}")
    
    await db_manager.close()

asyncio.run(add_assigned_user_field())