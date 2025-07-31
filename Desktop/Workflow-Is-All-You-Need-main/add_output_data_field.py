#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from workflow_framework.utils.database import db_manager

async def add_output_data_field():
    await db_manager.initialize()
    
    try:
        # 添加 output_data 字段到 workflow_instance 表
        query = """
            ALTER TABLE workflow_instance 
            ADD COLUMN IF NOT EXISTS output_data JSONB
        """
        
        await db_manager.execute(query)
        print("Successfully added output_data field to workflow_instance table")
        
    except Exception as e:
        print(f"Error adding field: {e}")
    
    await db_manager.close()

asyncio.run(add_output_data_field())