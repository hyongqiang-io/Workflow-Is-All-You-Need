#!/usr/bin/env python3
"""
检查节点表的结构
Check Node Table Schema
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.utils.database import initialize_database, get_db_manager

async def check_node_schema():
    """检查节点表的结构"""
    
    print("检查节点表结构...")
    print("=" * 60)
    
    try:
        # Initialize database connection
        await initialize_database()
        db = get_db_manager()
        
        # 查询 node 表的结构
        print("\n1. 查询 node 表结构:")
        schema_query = '''
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'node'
        ORDER BY ordinal_position
        '''
        columns = await db.fetch_all(schema_query)
        
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            default = f"DEFAULT {col['column_default']}" if col['column_default'] else ""
            print(f"  {col['column_name']}: {col['data_type']} {nullable} {default}")
        
        # 查询几条记录看看实际字段
        print("\n2. 查询 node 表数据示例:")
        sample_query = '''
        SELECT * FROM node LIMIT 3
        '''
        nodes = await db.fetch_all(sample_query)
        
        if nodes:
            print(f"  找到 {len(nodes)} 条记录:")
            for i, node in enumerate(nodes, 1):
                print(f"    记录 {i}:")
                for key, value in node.items():
                    print(f"      {key}: {value}")
                print()
        else:
            print("  表中无数据")
        
        print("\n" + "=" * 60)
        print("检查完成")
        
    except Exception as e:
        print(f"[ERROR] 检查失败: {e}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(check_node_schema())