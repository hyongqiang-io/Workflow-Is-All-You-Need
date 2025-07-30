#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Database Schema Update Script
数据库架构更新脚本
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_framework.utils.database import db_manager

async def update_database_schema():
    """Update database schema with missing fields"""
    print("Starting database schema update...")
    
    # SQL commands to add missing fields
    sql_commands = [
        # Add missing fields to workflow_instance table
        "ALTER TABLE workflow_instance ADD COLUMN IF NOT EXISTS instance_id UUID",
        "ALTER TABLE workflow_instance ADD COLUMN IF NOT EXISTS executor_id UUID",
        
        # Add missing fields to task_instance table
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS task_instance_id UUID",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS task_type VARCHAR(20) DEFAULT 'human'",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS assigned_agent_id UUID",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS task_title VARCHAR(255)",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS instructions TEXT",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS workflow_context JSONB",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS result_summary TEXT",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS actual_duration INTEGER",
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 1",
        
        # Update existing records
        "UPDATE workflow_instance SET instance_id = workflow_instance_id WHERE instance_id IS NULL",
        "UPDATE workflow_instance SET executor_id = trigger_user_id WHERE executor_id IS NULL",
        "UPDATE task_instance SET task_instance_id = task_id WHERE task_instance_id IS NULL",
        "UPDATE task_instance SET task_title = COALESCE(task_description, 'Task') WHERE task_title IS NULL",
        
        # Add indexes for new fields
        "CREATE INDEX IF NOT EXISTS idx_workflow_instance_instance_id ON workflow_instance(instance_id)",
        "CREATE INDEX IF NOT EXISTS idx_workflow_instance_executor_id ON workflow_instance(executor_id)",
        "CREATE INDEX IF NOT EXISTS idx_task_instance_task_instance_id ON task_instance(task_instance_id)",
        "CREATE INDEX IF NOT EXISTS idx_task_instance_task_type ON task_instance(task_type)",
        "CREATE INDEX IF NOT EXISTS idx_task_instance_assigned_agent ON task_instance(assigned_agent_id)",
    ]
    
    try:
        for i, sql in enumerate(sql_commands):
            try:
                await db_manager.execute(sql)
                print(f"[OK] Command {i+1}/{len(sql_commands)}: {sql[:60]}...")
            except Exception as e:
                print(f"[WARNING] Command {i+1} failed: {e}")
                continue
        
        print("[SUCCESS] Database schema update completed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Schema update failed: {e}")
        return False

async def main():
    """Main function"""
    try:
        await db_manager.initialize()
        success = await update_database_schema()
        await db_manager.close()
        
        if success:
            print("\n[SUCCESS] Schema update completed successfully!")
            return 0
        else:
            print("\n[FAILED] Schema update failed!")
            return 1
            
    except Exception as e:
        print(f"[ERROR] Update process failed: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"[ERROR] Script execution failed: {e}")
        sys.exit(1)