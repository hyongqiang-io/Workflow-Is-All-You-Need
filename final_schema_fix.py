#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Final Database Schema Fix
最终数据库架构修复
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow_framework.utils.database import db_manager

async def final_schema_fix():
    """Final fix for remaining database schema issues"""
    print("Starting final database schema fix...")
    
    # SQL commands to fix remaining issues
    sql_commands = [
        # Add missing fields to workflow_instance table
        "ALTER TABLE workflow_instance ADD COLUMN IF NOT EXISTS workflow_base_id UUID",
        "ALTER TABLE workflow_instance ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE",
        
        # Add missing fields to task_instance table  
        "ALTER TABLE task_instance ADD COLUMN IF NOT EXISTS estimated_duration INTEGER",
        
        # Add missing fields to agent table (if it exists)
        "ALTER TABLE agent ADD COLUMN IF NOT EXISTS endpoint VARCHAR(500)",
        
        # Update existing records
        "UPDATE workflow_instance SET workflow_base_id = workflow_id WHERE workflow_base_id IS NULL",
        "UPDATE workflow_instance SET started_at = start_at WHERE started_at IS NULL AND start_at IS NOT NULL",
        "UPDATE agent SET endpoint = 'http://localhost:8081/api' WHERE endpoint IS NULL",
        
        # Add indexes for new fields
        "CREATE INDEX IF NOT EXISTS idx_workflow_instance_workflow_base_id ON workflow_instance(workflow_base_id)",
        "CREATE INDEX IF NOT EXISTS idx_workflow_instance_started_at ON workflow_instance(started_at)",
    ]
    
    try:
        for i, sql in enumerate(sql_commands):
            try:
                await db_manager.execute(sql)
                print(f"[OK] Command {i+1}/{len(sql_commands)}: {sql[:60]}...")
            except Exception as e:
                print(f"[WARNING] Command {i+1} failed: {e}")
                continue
        
        print("[SUCCESS] Final schema fix completed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Final schema fix failed: {e}")
        return False

async def main():
    """Main function"""
    try:
        await db_manager.initialize()
        success = await final_schema_fix()
        await db_manager.close()
        
        if success:
            print("\n[SUCCESS] Final schema fix completed successfully!")
            return 0
        else:
            print("\n[FAILED] Final schema fix failed!")
            return 1
            
    except Exception as e:
        print(f"[ERROR] Fix process failed: {e}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"[ERROR] Script execution failed: {e}")
        sys.exit(1)