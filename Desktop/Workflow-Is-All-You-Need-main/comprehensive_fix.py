#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Comprehensive fix for the node_instance status constraint issue
This script will:
1. Update the database constraints to include 'waiting' status
2. Verify the constraints are updated correctly
3. Provide instructions for testing
"""

import sys
import subprocess

def run_sql_command(sql_command):
    """Run a SQL command using psql"""
    try:
        cmd = [
            'psql', 
            '-h', 'localhost',
            '-p', '5432', 
            '-U', 'workflow_user',
            '-d', 'workflow_db',
            '-c', sql_command
        ]
        
        # Set password via environment variable
        env = {'PGPASSWORD': 'workflow_pass'}
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            env=env
        )
        
        if result.returncode == 0:
            print(f"✅ SQL executed successfully: {sql_command[:50]}...")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ SQL failed: {sql_command[:50]}...")
            print(f"   Error: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ Exception running SQL: {e}")
        return False

def main():
    print("🔧 Starting comprehensive fix for node_instance constraint issue")
    print("=" * 60)
    
    # Step 1: Drop existing constraints
    print("\n1. Dropping existing constraints...")
    
    constraints_to_drop = [
        "ALTER TABLE node_instance DROP CONSTRAINT IF EXISTS node_instance_status_check;",
        "ALTER TABLE task_instance DROP CONSTRAINT IF EXISTS task_instance_status_check;",
        "ALTER TABLE workflow_instance DROP CONSTRAINT IF EXISTS workflow_instance_status_check;"
    ]
    
    for sql in constraints_to_drop:
        run_sql_command(sql)
    
    # Step 2: Add new constraints with 'waiting' status
    print("\n2. Adding new constraints with 'waiting' status...")
    
    new_constraints = [
        """ALTER TABLE node_instance 
           ADD CONSTRAINT node_instance_status_check 
           CHECK (status IN ('pending', 'waiting', 'running', 'completed', 'failed', 'cancelled'));""",
        
        """ALTER TABLE task_instance 
           ADD CONSTRAINT task_instance_status_check 
           CHECK (status IN ('pending', 'assigned', 'waiting', 'in_progress', 'running', 'completed', 'failed', 'cancelled'));""",
        
        """ALTER TABLE workflow_instance 
           ADD CONSTRAINT workflow_instance_status_check 
           CHECK (status IN ('pending', 'waiting', 'running', 'paused', 'completed', 'failed', 'cancelled'));"""
    ]
    
    for sql in new_constraints:
        success = run_sql_command(sql)
        if not success:
            print(f"❌ Failed to add constraint. Please check the error above.")
            return False
    
    # Step 3: Verify constraints
    print("\n3. Verifying constraints...")
    
    verify_sql = """
    SELECT conname, pg_get_constraintdef(oid) as definition
    FROM pg_constraint 
    WHERE conname LIKE '%status_check%' 
    ORDER BY conname;
    """
    
    run_sql_command(verify_sql)
    
    print("\n" + "=" * 60)
    print("🎉 Fix completed!")
    print("\nSUMMARY:")
    print("- Updated database constraints to include 'waiting' status")
    print("- Updated Python enums in models/instance.py")
    print("\nNEXT STEPS:")
    print("1. Restart your backend server if it's running")
    print("2. Try executing the workflow again from the frontend")
    print("3. The error should now be resolved")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)