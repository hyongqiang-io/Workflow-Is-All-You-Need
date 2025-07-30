#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from workflow_framework.utils.database import db_manager

async def check_foreign_keys():
    await db_manager.initialize()
    
    # 检查node_instance表的外键约束
    query = """
        SELECT 
            tc.constraint_name, 
            kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
        WHERE constraint_type = 'FOREIGN KEY' AND tc.table_name='node_instance';
    """
    
    result = await db_manager.fetch_all(query)
    print("node_instance表的外键约束:")
    for row in result:
        print(f"  约束名: {row['constraint_name']}")
        print(f"  本表字段: {row['column_name']}")
        print(f"  引用表: {row['foreign_table_name']}")
        print(f"  引用字段: {row['foreign_column_name']}")
        print()
    
    await db_manager.close()

asyncio.run(check_foreign_keys())