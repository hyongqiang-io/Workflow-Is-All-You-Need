#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from workflow_framework.utils.database import db_manager

async def add_instance_name():
    await db_manager.initialize()
    await db_manager.execute('ALTER TABLE workflow_instance ADD COLUMN IF NOT EXISTS instance_name VARCHAR(255)')
    await db_manager.execute('UPDATE workflow_instance SET instance_name = workflow_instance_name WHERE instance_name IS NULL')
    print('[OK] Added instance_name field')
    await db_manager.close()

asyncio.run(add_instance_name())