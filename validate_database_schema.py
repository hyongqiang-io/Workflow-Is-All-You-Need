#!/usr/bin/env python3
"""
数据库架构验证脚本
Database Schema Validation Script
"""

import asyncio
import asyncpg
from loguru import logger

async def validate_database_schema():
    """验证数据库架构是否正确"""
    try:
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            database='workflow_db',
            user='postgres',
            password='postgresql'
        )
        
        logger.info("数据库连接成功")
        
        # 检查所有预期的表是否存在
        expected_tables = [
            'user', 'agent', 'workflow', 'node', 'processor',
            'workflow_user', 'node_processor', 'node_connection',
            'workflow_instance', 'node_instance', 'task_instance',
            'workflow_execution', 'node_execution'
        ]
        
        existing_tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        existing_table_names = [row['table_name'] for row in existing_tables]
        
        print("=== 表结构验证 ===")
        print(f"数据库中现有表数量: {len(existing_table_names)}")
        
        # 检查缺失的核心表
        missing_tables = []
        for table in expected_tables:
            if table not in existing_table_names:
                missing_tables.append(table)
        
        if missing_tables:
            print(f"缺失的核心表: {missing_tables}")
        else:
            print("✅ 所有核心表都存在")
        
        # 检查视图
        existing_views = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        view_names = [row['table_name'] for row in existing_views]
        print(f"现有视图数量: {len(view_names)}")
        if view_names:
            for view in view_names:
                print(f"  - {view}")
        
        # 验证关键表的字段结构
        print("\n=== 关键表字段验证 ===")
        
        # 检查workflow_instance表
        if 'workflow_instance' in existing_table_names:
            wi_columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'workflow_instance' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            
            required_wi_fields = ['workflow_instance_id', 'workflow_id', 'status', 'trigger_user_id']
            existing_wi_fields = [col['column_name'] for col in wi_columns]
            
            missing_wi_fields = [field for field in required_wi_fields if field not in existing_wi_fields]
            if missing_wi_fields:
                print(f"❌ workflow_instance表缺失字段: {missing_wi_fields}")
            else:
                print("✅ workflow_instance表字段完整")
        
        # 检查task_instance表
        if 'task_instance' in existing_table_names:
            ti_columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'task_instance' AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            
            required_ti_fields = ['task_instance_id', 'node_instance_id', 'workflow_instance_id', 'processor_id', 'status']
            existing_ti_fields = [col['column_name'] for col in ti_columns]
            
            missing_ti_fields = [field for field in required_ti_fields if field not in existing_ti_fields]
            if missing_ti_fields:
                print(f"❌ task_instance表缺失字段: {missing_ti_fields}")
            else:
                print("✅ task_instance表字段完整")
        
        # 检查外键约束
        print("\n=== 外键约束验证 ===")
        foreign_keys = await conn.fetch("""
            SELECT 
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_name
        """)
        
        print(f"现有外键约束数量: {len(foreign_keys)}")
        for fk in foreign_keys[:5]:  # 只显示前5个
            print(f"  {fk['table_name']}.{fk['column_name']} -> {fk['foreign_table_name']}.{fk['foreign_column_name']}")
        if len(foreign_keys) > 5:
            print(f"  ... 还有 {len(foreign_keys) - 5} 个约束")
        
        # 检查索引
        print("\n=== 索引验证 ===")
        indexes = await conn.fetch("""
            SELECT 
                schemaname, tablename, indexname, indexdef
            FROM pg_indexes 
            WHERE schemaname = 'public' 
                AND indexname NOT LIKE '%_pkey'  -- 排除主键索引
            ORDER BY tablename, indexname
        """)
        
        print(f"现有自定义索引数量: {len(indexes)}")
        for idx in indexes[:5]:  # 只显示前5个
            print(f"  {idx['tablename']}: {idx['indexname']}")
        if len(indexes) > 5:
            print(f"  ... 还有 {len(indexes) - 5} 个索引")
        
        await conn.close()
        
        print("\n=== 验证总结 ===")
        if not missing_tables:
            print("✅ 数据库架构验证通过！")
            return True
        else:
            print("❌ 数据库架构存在问题，需要修复")
            return False
            
    except Exception as e:
        logger.error(f"验证失败: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(validate_database_schema())
    exit(0 if result else 1)