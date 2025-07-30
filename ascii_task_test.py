"""
ASCII test for TaskInstanceCreate validation fix
"""

import uuid
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.models.instance import TaskInstanceCreate, TaskInstanceType

def main():
    print("Testing TaskInstanceCreate validation fix...")
    
    # Test 1: Empty string task_description
    try:
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=uuid.uuid4(),
            task_type=TaskInstanceType.HUMAN,
            task_title="Test Task",
            task_description="",  # Empty string
            input_data={},
            instructions="Test instructions",
            priority=1,
            assigned_user_id=uuid.uuid4(),
            estimated_duration=30
        )
        print("PASS: Empty string task_description validation passed")
    except Exception as e:
        print(f"FAIL: Empty string task_description validation failed: {e}")
    
    # Test 2: Default task_description (no value provided)
    try:
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=uuid.uuid4(),
            task_type=TaskInstanceType.HUMAN,
            task_title="Test Task",
            # task_description not provided, should use default
            input_data={},
            instructions="Test instructions",
            priority=1,
            assigned_user_id=uuid.uuid4(),
            estimated_duration=30
        )
        print(f"PASS: Default task_description validation passed: '{task_data.task_description}'")
    except Exception as e:
        print(f"FAIL: Default task_description validation failed: {e}")
    
    # Test 3: Normal task_description
    try:
        task_data = TaskInstanceCreate(
            node_instance_id=uuid.uuid4(),
            workflow_instance_id=uuid.uuid4(),
            processor_id=uuid.uuid4(),
            task_type=TaskInstanceType.HUMAN,
            task_title="Test Task",
            task_description="This is a normal task description",
            input_data={},
            instructions="Test instructions",
            priority=1,
            assigned_user_id=uuid.uuid4(),
            estimated_duration=30
        )
        print(f"PASS: Normal task_description validation passed: '{task_data.task_description}'")
    except Exception as e:
        print(f"FAIL: Normal task_description validation failed: {e}")
    
    print("\nTest completed!")
    print("The TaskInstanceCreate validation issue should now be fixed.")

if __name__ == "__main__":
    main()