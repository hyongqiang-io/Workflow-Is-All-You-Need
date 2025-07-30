"""
检查和修复任务状态约束
Check and Fix Task Status Constraints
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.utils.database import initialize_database, get_db_manager

async def check_task_constraints():
    """检查任务状态约束"""
    try:
        print("Checking task_instance table constraints...")
        
        # Initialize database connection
        await initialize_database()
        db = get_db_manager()
        
        # 查询当前的约束
        constraint_query = """
        SELECT 
            conname as constraint_name,
            pg_get_constraintdef(c.oid) as constraint_definition
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'task_instance' 
        AND contype = 'c'
        ORDER BY conname;
        """
        
        constraints = await db.fetch_all(constraint_query)
        
        print("Current check constraints on task_instance table:")
        print("=" * 70)
        
        for constraint in constraints:
            print(f"Name: {constraint['constraint_name']}")
            print(f"Definition: {constraint['constraint_definition']}")
            print("-" * 50)
        
        # 检查状态约束
        status_constraint = None
        for constraint in constraints:
            if 'status' in constraint['constraint_name'].lower():
                status_constraint = constraint
                break
        
        if status_constraint:
            print(f"\nFound status constraint: {status_constraint['constraint_name']}")
            print(f"Current definition: {status_constraint['constraint_definition']}")
            
            # 检查约束是否包含所需的状态值
            definition = status_constraint['constraint_definition'].lower()
            required_statuses = ['pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled']
            
            print(f"\nChecking required statuses:")
            missing_statuses = []
            for status in required_statuses:
                if status in definition or status.replace('_', '') in definition:
                    print(f"  PASS: {status}")
                else:
                    print(f"  MISSING: {status}")
                    missing_statuses.append(status)
            
            if missing_statuses:
                print(f"\nERROR: Missing statuses in constraint: {missing_statuses}")
                return False, status_constraint['constraint_name'], missing_statuses
            else:
                print(f"\nSUCCESS: All required statuses are in the constraint")
                return True, None, []
        else:
            print(f"\nWARNING: No status constraint found")
            return False, None, required_statuses
        
    except Exception as e:
        print(f"ERROR: Failed to check constraints: {e}")
        import traceback
        print(f"Error details:\n{traceback.format_exc()}")
        return False, None, []

async def fix_status_constraint(constraint_name=None):
    """修复状态约束"""
    try:
        print("Fixing task status constraint...")
        
        await initialize_database()
        db = get_db_manager()
        
        # 如果有旧约束，先删除
        if constraint_name:
            print(f"Dropping old constraint: {constraint_name}")
            drop_sql = f"ALTER TABLE task_instance DROP CONSTRAINT IF EXISTS {constraint_name};"
            await db.execute(drop_sql)
        
        # 创建新的状态约束
        print("Creating new status constraint...")
        new_constraint_sql = """
        ALTER TABLE task_instance 
        ADD CONSTRAINT task_instance_status_check 
        CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled', 'paused'));
        """
        
        await db.execute(new_constraint_sql)
        print("SUCCESS: New status constraint created")
        
        # 验证新约束
        verification_query = """
        SELECT pg_get_constraintdef(c.oid) as constraint_definition
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'task_instance' 
        AND c.conname = 'task_instance_status_check';
        """
        
        result = await db.fetch_one(verification_query)
        if result:
            print(f"New constraint definition: {result['constraint_definition']}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to fix constraint: {e}")
        import traceback
        print(f"Error details:\n{traceback.format_exc()}")
        return False

async def main():
    """Main function"""
    print("Task Status Constraint Check and Fix Tool")
    print("=" * 50)
    
    # First check current constraints
    is_valid, constraint_name, missing = await check_task_constraints()
    
    if not is_valid:
        print(f"\nConstraint needs to be fixed...")
        success = await fix_status_constraint(constraint_name)
        
        if success:
            print(f"\nRe-checking constraints after fix...")
            is_valid_after, _, _ = await check_task_constraints()
            
            if is_valid_after:
                print(f"\nSUCCESS: Task status constraint has been fixed!")
                print("You can now use all task statuses: pending, assigned, in_progress, completed, failed, cancelled")
            else:
                print(f"\nERROR: Constraint fix verification failed")
        else:
            print(f"\nERROR: Failed to fix constraint")
    else:
        print(f"\nConstraint is already correct - no fix needed")

if __name__ == "__main__":
    asyncio.run(main())