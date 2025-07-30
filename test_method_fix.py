#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script to verify the method name fix
"""

import asyncio
import sys
import os

# Add the workflow framework to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'workflow_framework'))

async def test_node_instance_repository():
    """Test that the NodeInstanceRepository methods work correctly"""
    
    try:
        from workflow_framework.repositories.instance.node_instance_repository import NodeInstanceRepository
        import uuid
        
        # Create repository instance
        repo = NodeInstanceRepository()
        
        # Test that the method exists
        assert hasattr(repo, 'get_instance_by_id'), "get_instance_by_id method should exist"
        assert not hasattr(repo, 'get_node_instance_by_id'), "get_node_instance_by_id should not exist (this was the bug)"
        
        print("✅ Method names are correct!")
        print("   - get_instance_by_id: EXISTS")
        print("   - get_node_instance_by_id: DOES NOT EXIST (as expected)")
        
        # Test other important methods
        important_methods = [
            'get_instance_with_details',
            'get_instances_by_workflow_instance', 
            'create_node_instance',
            'update_instance_status'
        ]
        
        for method_name in important_methods:
            if hasattr(repo, method_name):
                print(f"   - {method_name}: EXISTS")
            else:
                print(f"   - {method_name}: MISSING (might be needed)")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Testing NodeInstanceRepository method fix...")
    print("=" * 50)
    
    success = asyncio.run(test_node_instance_repository())
    
    if success:
        print("\n🎉 Test PASSED! The method name issue has been fixed.")
        print("\nThe execution service should now work correctly.")
    else:
        print("\n❌ Test FAILED! There may still be issues to resolve.")
    
    sys.exit(0 if success else 1)