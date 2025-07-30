#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from workflow_framework.utils.database import db_manager

async def check_workflow_instance_schema():
    await db_manager.initialize()
    
    # 检查workflow_instance表的结构
    query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'workflow_instance'
        ORDER BY ordinal_position
    """
    
    result = await db_manager.fetch_all(query)
    print("workflow_instance表结构:")
    for row in result:
        print(f"  {row['column_name']}: {row['data_type']} {'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'}")
    
    # 也检查node_instance表的结构
    query2 = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'node_instance'
        ORDER BY ordinal_position
    """
    
    result2 = await db_manager.fetch_all(query2)
    print("\nnode_instance表结构:")
    for row in result2:
        print(f"  {row['column_name']}: {row['data_type']} {'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'}")
    
    await db_manager.close()

asyncio.run(check_workflow_instance_schema())