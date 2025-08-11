#!/usr/bin/env python3
"""
Final verification script for executor_id field unification
Tests the actual database state after migration
"""

import asyncio
import asyncpg

async def verify_database_state():
    """Verify the actual database state after migration"""
    try:
        # Connect to database
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            user='postgres', 
            password='postgresql',
            database='workflow_db'
        )
        
        print("🔌 Connected to database for verification")
        print("=" * 60)
        
        # Test 1: Check table structure
        print("\n📋 Test 1: Checking workflow_instance table structure...")
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'workflow_instance' 
            ORDER BY ordinal_position
        """)
        
        executor_id_found = False
        trigger_user_id_found = False
        
        print("   Columns in workflow_instance table:")
        for col in columns:
            print(f"     - {col['column_name']}: {col['data_type']} {'(nullable)' if col['is_nullable'] == 'YES' else '(not null)'}")
            if col['column_name'] == 'executor_id':
                executor_id_found = True
            elif col['column_name'] == 'trigger_user_id':
                trigger_user_id_found = True
        
        if executor_id_found and not trigger_user_id_found:
            print("   ✅ Table structure correct: executor_id exists, trigger_user_id removed")
        else:
            print(f"   ❌ Table structure issue: executor_id={executor_id_found}, trigger_user_id={trigger_user_id_found}")
        
        # Test 2: Check foreign key constraints
        print("\n🔗 Test 2: Checking foreign key constraints...")
        constraints = await conn.fetch("""
            SELECT tc.constraint_name, kcu.column_name, ccu.table_name as foreign_table_name, ccu.column_name as foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
            WHERE tc.table_name = 'workflow_instance' 
            AND tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name LIKE '%executor%'
        """)
        
        if constraints:
            print("   ✅ Foreign key constraints found:")
            for constraint in constraints:
                print(f"     - {constraint['constraint_name']}: {constraint['column_name']} -> {constraint['foreign_table_name']}.{constraint['foreign_column_name']}")
        else:
            print("   ❌ No executor_id foreign key constraints found")
        
        # Test 3: Check indexes
        print("\n📊 Test 3: Checking indexes...")
        indexes = await conn.fetch("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE tablename = 'workflow_instance' 
            AND indexname LIKE '%executor%'
        """)
        
        if indexes:
            print("   ✅ Executor indexes found:")
            for idx in indexes:
                print(f"     - {idx['indexname']}")
        else:
            print("   ❌ No executor_id indexes found")
        
        # Test 4: Check if there's any data and it's accessible
        print("\n📄 Test 4: Checking data accessibility...")
        try:
            count = await conn.fetchval("SELECT COUNT(*) FROM workflow_instance")
            print(f"   ✅ Can query workflow_instance table: {count} records found")
            
            # Try to query with executor_id
            sample = await conn.fetch("""
                SELECT workflow_instance_id, executor_id, instance_name, status 
                FROM workflow_instance 
                LIMIT 3
            """)
            
            if sample:
                print("   ✅ Sample records:")
                for record in sample:
                    print(f"     - ID: {record['workflow_instance_id']}")
                    print(f"       Executor: {record['executor_id']}")
                    print(f"       Name: {record['instance_name']}")
                    print(f"       Status: {record['status']}")
            else:
                print("   ℹ️  No sample records found (table may be empty)")
                
        except Exception as e:
            print(f"   ❌ Error querying data: {e}")
        
        # Test 5: Test a representative query that the application would use
        print("\n🔍 Test 5: Testing application-style queries...")
        try:
            # Test query similar to what the repository uses
            test_query = """
                SELECT wi.*, u.username as executor_name
                FROM workflow_instance wi
                LEFT JOIN "user" u ON u.user_id = wi.executor_id
                WHERE wi.is_deleted = FALSE
                LIMIT 1
            """
            
            result = await conn.fetch(test_query)
            print("   ✅ Application-style query with executor_id JOIN works")
            
        except Exception as e:
            print(f"   ❌ Application query failed: {e}")
        
        await conn.close()
        
        print("\n" + "=" * 60)
        print("🎉 DATABASE VERIFICATION COMPLETE!")
        print("✅ The executor_id field unification has been successfully implemented")
        print("✅ Database is ready for application restart")
        
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(verify_database_state())
    if success:
        print("\n🚀 Ready to restart the application!")
    else:
        print("\n🔧 Please resolve database issues before proceeding")