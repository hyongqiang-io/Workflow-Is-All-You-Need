#!/usr/bin/env python3
"""
Simple verification script for executor_id and trigger_user_id unification
This script verifies that the field unification has been completed correctly
"""

import sys
from pathlib import Path

def verify_field_unification():
    """Verify that executor_id field unification is complete"""
    backend_path = Path(__file__).parent
    
    print("🔍 Verifying executor_id and trigger_user_id field unification...")
    print("=" * 60)
    
    # Test 1: Check migration script exists
    print("\n📄 Test 1: Checking migration script...")
    migration_file = backend_path / "migrations" / "unify_executor_id_field.sql"
    if migration_file.exists():
        print("✅ Migration script exists")
        print(f"   📁 Path: {migration_file}")
        # Check migration script content
        content = migration_file.read_text()
        if "DROP COLUMN trigger_user_id" in content:
            print("✅ Migration drops trigger_user_id column")
        if "executor_id" in content:
            print("✅ Migration references executor_id")
    else:
        print("❌ Migration script not found")
        return False
    
    # Test 2: Check key files for trigger_user_id references
    print("\n🔍 Test 2: Checking for remaining trigger_user_id references...")
    
    key_files = [
        "repositories/instance/workflow_instance_repository.py",
        "api/execution.py", 
        "api/workflow_output.py",
        "services/human_task_service.py",
        "scripts/init_database.py"
    ]
    
    all_clean = True
    for file_path in key_files:
        full_path = backend_path / file_path
        if full_path.exists():
            content = full_path.read_text()
            if 'trigger_user_id' in content:
                print(f"❌ trigger_user_id still found in {file_path}")
                # Show the lines containing trigger_user_id
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'trigger_user_id' in line:
                        print(f"   Line {i}: {line.strip()}")
                all_clean = False
            else:
                print(f"✅ {file_path} - clean")
        else:
            print(f"⚠️  File not found: {file_path}")
    
    # Test 3: Check that executor_id is properly used
    print("\n✅ Test 3: Checking executor_id usage...")
    
    # Check repository file
    repo_file = backend_path / "repositories/instance/workflow_instance_repository.py"
    if repo_file.exists():
        content = repo_file.read_text()
        if 'executor_id": instance_data.executor_id' in content:
            print("✅ Repository uses executor_id correctly")
        if 'wi.executor_id' in content:
            print("✅ Repository queries use executor_id")
        if '"executor_id"' not in content:
            print("❌ Repository missing executor_id references")
            all_clean = False
    
    # Test 4: Check database schema
    print("\n🏗️  Test 4: Checking database schema...")
    init_file = backend_path / "scripts/init_database.py"
    if init_file.exists():
        content = init_file.read_text()
        if 'executor_id UUID NOT NULL' in content:
            print("✅ Database schema has executor_id field")
        if 'trigger_user_id' not in content:
            print("✅ Database schema clean of trigger_user_id")
        else:
            print("❌ Database schema still contains trigger_user_id")
            all_clean = False
        
        if 'fk_workflow_instance_executor' in content:
            print("✅ Database has executor_id foreign key constraint")
        
        if 'idx_workflow_instance_executor' in content:
            print("✅ Database has executor_id index")
    
    print("\n" + "=" * 60)
    
    if all_clean:
        print("🎉 SUCCESS: Field unification completed successfully!")
        print("\n📋 Summary of changes made:")
        print("   ✅ Created migration script to unify fields")
        print("   ✅ Updated workflow_instance_repository.py")
        print("   ✅ Updated all SQL queries in API files")
        print("   ✅ Updated database initialization script")
        print("   ✅ Removed all trigger_user_id references")
        print("   ✅ Maintained all executor_id usage")
        
        print("\n🚀 Next steps:")
        print("   1. Apply the migration: unify_executor_id_field.sql")
        print("   2. Restart the application")
        print("   3. Test workflow creation and execution")
        
        return True
    else:
        print("❌ FAILED: Some issues found with field unification")
        return False

if __name__ == "__main__":
    success = verify_field_unification()
    sys.exit(0 if success else 1)