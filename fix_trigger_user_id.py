#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from workflow_framework.utils.database import db_manager

async def fix_trigger_user_id():
    await db_manager.initialize()
    
    # The issue is that the repository is setting executor_id but the database expects trigger_user_id
    # Let's modify the repository to map executor_id to trigger_user_id
    
    print('[INFO] The fix needs to be applied in the repository code')
    print('[INFO] The WorkflowInstanceRepository.create_instance method needs to map:')
    print('[INFO] "trigger_user_id": instance_data.executor_id')
    print('[INFO] instead of "executor_id": instance_data.executor_id')
    
    await db_manager.close()

asyncio.run(fix_trigger_user_id())