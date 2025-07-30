"""
Fix Task Table Schema - Add Missing Fields (ASCII version)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.utils.database import initialize_database, get_db_manager

async def fix_task_table_schema():
    """Fix task table schema"""
    try:
        print("Starting task table schema fix...")
        
        # Initialize database connection
        await initialize_database()
        db = get_db_manager()
        
        # Define the SQL commands to add missing fields
        sql_commands = [
            # Add started_at field
            """
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_instance' AND column_name = 'started_at'
                ) THEN
                    ALTER TABLE task_instance ADD COLUMN started_at TIMESTAMP WITH TIME ZONE;
                    RAISE NOTICE 'Added started_at field to task_instance table';
                ELSE
                    RAISE NOTICE 'started_at field already exists in task_instance table';
                END IF;
            END $$;
            """,
            
            # Add assigned_at field
            """
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_instance' AND column_name = 'assigned_at'
                ) THEN
                    ALTER TABLE task_instance ADD COLUMN assigned_at TIMESTAMP WITH TIME ZONE;
                    RAISE NOTICE 'Added assigned_at field to task_instance table';
                ELSE
                    RAISE NOTICE 'assigned_at field already exists in task_instance table';
                END IF;
            END $$;
            """,
            
            # Add context_data field
            """
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_instance' AND column_name = 'context_data'
                ) THEN
                    ALTER TABLE task_instance ADD COLUMN context_data JSONB DEFAULT '{}';
                    RAISE NOTICE 'Added context_data field to task_instance table';
                ELSE
                    RAISE NOTICE 'context_data field already exists in task_instance table';
                END IF;
            END $$;
            """,
            
            # Add actual_duration field
            """
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_instance' AND column_name = 'actual_duration'
                ) THEN
                    ALTER TABLE task_instance ADD COLUMN actual_duration INTEGER;
                    RAISE NOTICE 'Added actual_duration field to task_instance table';
                ELSE
                    RAISE NOTICE 'actual_duration field already exists in task_instance table';
                END IF;
            END $$;
            """,
            
            # Add result_summary field
            """
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'task_instance' AND column_name = 'result_summary'
                ) THEN
                    ALTER TABLE task_instance ADD COLUMN result_summary TEXT;
                    RAISE NOTICE 'Added result_summary field to task_instance table';
                ELSE
                    RAISE NOTICE 'result_summary field already exists in task_instance table';
                END IF;
            END $$;
            """
        ]
        
        print("Executing schema fix SQL commands...")
        
        # Execute each SQL command
        for i, sql in enumerate(sql_commands, 1):
            try:
                await db.execute(sql)
                print(f"  Command {i}/5 executed successfully")
            except Exception as e:
                print(f"  Command {i}/5 failed: {e}")
        
        print("Database schema fix completed")
        
        # Query table structure
        print("\nQuerying current task_instance table structure:")
        structure_query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_name = 'task_instance' 
        ORDER BY ordinal_position;
        """
        
        columns = await db.fetch_all(structure_query)
        
        print("=" * 80)
        print(f"{'Field Name':<20} {'Data Type':<25} {'Nullable':<8} {'Default'}")
        print("=" * 80)
        
        for col in columns:
            column_name = col['column_name']
            data_type = col['data_type']
            is_nullable = 'Yes' if col['is_nullable'] == 'YES' else 'No'
            default_val = col['column_default'] or ''
            
            print(f"{column_name:<20} {data_type:<25} {is_nullable:<8} {default_val[:20]}")
        
        print("=" * 80)
        print(f"task_instance table has {len(columns)} fields in total")
        
        # Check if required fields exist
        field_names = [col['column_name'] for col in columns]
        required_fields = ['started_at', 'assigned_at', 'context_data', 'actual_duration', 'result_summary']
        
        print(f"\nChecking required fields:")
        all_present = True
        for field in required_fields:
            if field in field_names:
                print(f"  PASS: {field} - exists")
            else:
                print(f"  FAIL: {field} - missing")
                all_present = False
        
        if all_present:
            print(f"\nSUCCESS: All required fields are present!")
        else:
            print(f"\nWARNING: Some required fields are still missing")
        
        print(f"\nTask table schema fix completed!")
        
    except Exception as e:
        print(f"ERROR: Failed to fix task table schema: {e}")
        import traceback
        print(f"Error details:\n{traceback.format_exc()}")

async def main():
    """Main function"""
    print("Task Table Schema Fix Tool")
    print("=" * 50)
    
    await fix_task_table_schema()

if __name__ == "__main__":
    asyncio.run(main())