#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from workflow_framework.utils.database import db_manager

async def comprehensive_schema_fix():
    await db_manager.initialize()
    
    # Add all remaining missing fields
    commands = [
        'ALTER TABLE workflow_instance ADD COLUMN IF NOT EXISTS input_data JSONB',
        'ALTER TABLE workflow_instance ADD COLUMN IF NOT EXISTS context_data JSONB',
        'UPDATE workflow_instance SET input_data = \'{"source": "legacy"}\' WHERE input_data IS NULL',
        'UPDATE workflow_instance SET context_data = \'{"created_from": "legacy"}\' WHERE context_data IS NULL',
        'CREATE INDEX IF NOT EXISTS idx_workflow_instance_input_data ON workflow_instance USING gin(input_data)',
        'CREATE INDEX IF NOT EXISTS idx_workflow_instance_context_data ON workflow_instance USING gin(context_data)',
    ]
    
    for i, cmd in enumerate(commands):
        try:
            await db_manager.execute(cmd)
            print(f'[OK] Command {i+1}: {cmd[:50]}...')
        except Exception as e:
            print(f'[WARNING] Command {i+1} failed: {e}')
    
    print('[SUCCESS] Comprehensive schema fix completed!')
    await db_manager.close()

asyncio.run(comprehensive_schema_fix())