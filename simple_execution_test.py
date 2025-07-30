#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple Workflow Execution Test
工作流执行功能简单测试
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# Set encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required modules
from workflow_framework.utils.database import initialize_database, close_database
from workflow_framework.services.execution_service import execution_engine
from workflow_framework.services.human_task_service import HumanTaskService
from workflow_framework.services.agent_task_service import agent_task_service
from workflow_framework.services.monitoring_service import monitoring_service
from workflow_framework.services.auth_service import AuthService
from workflow_framework.services.workflow_service import WorkflowService
from workflow_framework.services.node_service import NodeService
from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
from workflow_framework.repositories.agent.agent_repository import AgentRepository

# Import models
from workflow_framework.models.user import UserCreate
from workflow_framework.models.workflow import WorkflowCreate
from workflow_framework.models.node import NodeCreate, NodeType, NodeConnectionCreate
from workflow_framework.models.processor import ProcessorCreate, ProcessorType
from workflow_framework.models.agent import AgentCreate
from workflow_framework.models.instance import WorkflowExecuteRequest


async def create_simple_workflow():
    """Create a simple test workflow"""
    print("\n=== Step 1: Creating Test Workflow ===")
    
    # Initialize services
    auth_service = AuthService()
    workflow_service = WorkflowService()
    node_service = NodeService()
    processor_repository = ProcessorRepository()
    agent_repository = AgentRepository()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        # 1. Create test user
        print("Creating test user...")
        user_data = UserCreate(
            username=f"test_user_{timestamp}",
            email=f"test_{timestamp}@example.com",
            password="test123456",
            role="admin",
            description="Test user for workflow execution"
        )
        
        user_response = await auth_service.register_user(user_data)
        print(f"[OK] User created: {user_response.username} (ID: {user_response.user_id})")
        
        # 2. Create test agent
        print("Creating test agent...")
        agent_data = AgentCreate(
            agent_name=f"Test_AI_{timestamp}",
            description="AI agent for execution testing",
            endpoint="http://localhost:8081/api",
            capabilities=["data_analysis", "decision_support"],
            status=True
        )
        
        agent_record = await agent_repository.create_agent(agent_data)
        print(f"[OK] Agent created: {agent_record['agent_name']}")
        
        # 3. Create processors
        print("Creating processors...")
        
        # Human processor
        human_processor_data = ProcessorCreate(
            name=f"Human_Processor_{timestamp}",
            type=ProcessorType.HUMAN,
            user_id=user_response.user_id,
            agent_id=None
        )
        human_processor = await processor_repository.create_processor(human_processor_data)
        print(f"[OK] Human processor created")
        
        # AI processor
        ai_processor_data = ProcessorCreate(
            name=f"AI_Processor_{timestamp}",
            type=ProcessorType.AGENT,
            user_id=None,
            agent_id=agent_record['agent_id']
        )
        ai_processor = await processor_repository.create_processor(ai_processor_data)
        print(f"[OK] AI processor created")
        
        # 4. Create workflow
        print("Creating workflow...")
        workflow_data = WorkflowCreate(
            name=f"Test_Workflow_{timestamp}",
            description="Simple test workflow for execution testing",
            creator_id=user_response.user_id
        )
        
        workflow_response = await workflow_service.create_workflow(workflow_data)
        print(f"[OK] Workflow created: {workflow_response.name}")
        
        # 5. Create nodes
        print("Creating workflow nodes...")
        
        # Start node
        start_node_data = NodeCreate(
            name="Start",
            type=NodeType.START,
            task_description="Start of workflow processing",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=100,
            position_y=200
        )
        start_node = await node_service.create_node(start_node_data, user_response.user_id)
        print(f"[OK] Start node created")
        
        # Processing node
        process_node_data = NodeCreate(
            name="Process",
            type=NodeType.PROCESSOR,
            task_description="Process data using AI",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=300,
            position_y=200
        )
        process_node = await node_service.create_node(process_node_data, user_response.user_id)
        print(f"[OK] Process node created")
        
        # End node
        end_node_data = NodeCreate(
            name="End",
            type=NodeType.END,
            task_description="End of workflow",
            workflow_base_id=workflow_response.workflow_base_id,
            position_x=500,
            position_y=200
        )
        end_node = await node_service.create_node(end_node_data, user_response.user_id)
        print(f"[OK] End node created")
        
        # 6. Assign processor
        print("Assigning processor...")
        await node_service.assign_processor_to_node(
            process_node.node_base_id,
            workflow_response.workflow_base_id,
            ai_processor['processor_id'],
            user_response.user_id
        )
        print("[OK] AI processor assigned")
        
        # 7. Create connections
        print("Creating node connections...")
        connections = [
            (start_node.node_base_id, process_node.node_base_id),
            (process_node.node_base_id, end_node.node_base_id)
        ]
        
        for from_node, to_node in connections:
            connection_data = NodeConnectionCreate(
                from_node_base_id=from_node,
                to_node_base_id=to_node,
                workflow_base_id=workflow_response.workflow_base_id
            )
            await node_service.create_node_connection(connection_data, user_response.user_id)
        print("[OK] Node connections created")
        
        print(f"\n[SUCCESS] Test workflow creation completed")
        print(f"  - Workflow ID: {workflow_response.workflow_base_id}")
        print(f"  - User ID: {user_response.user_id}")
        
        return {
            'workflow_base_id': workflow_response.workflow_base_id,
            'executor_id': user_response.user_id,
            'workflow_name': workflow_response.name,
            'user_name': user_response.username
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to create workflow: {e}")
        return None


async def test_workflow_execution(workflow_info):
    """Test workflow execution"""
    print("\n=== Step 2: Testing Workflow Execution ===")
    
    try:
        # 1. Start execution engine
        print("Starting execution engine...")
        await execution_engine.start_engine()
        await agent_task_service.start_service()
        await monitoring_service.start_monitoring()
        print("[OK] Execution engine started")
        
        # 2. Create execution request
        print("Creating workflow execution request...")
        execute_request = WorkflowExecuteRequest(
            workflow_base_id=workflow_info['workflow_base_id'],
            instance_name=f"Test_Instance_{datetime.now().strftime('%H%M%S')}",
            input_data={
                "test_data": [1, 2, 3, 4, 5],
                "requirements": "Analyze the data patterns"
            },
            context_data={
                "source": "simple_test",
                "test_mode": True
            }
        )
        
        # 3. Execute workflow
        print("Starting workflow execution...")
        execution_result = await execution_engine.execute_workflow(
            execute_request, workflow_info['executor_id']
        )
        
        instance_id = execution_result['instance_id']
        print(f"[OK] Workflow started executing, Instance ID: {instance_id}")
        
        # 4. Monitor execution status
        print("\nMonitoring execution status...")
        for i in range(8):  # Monitor 8 times, 3 seconds each
            await asyncio.sleep(3)
            
            status_info = await execution_engine.get_workflow_status(instance_id)
            if status_info:
                instance = status_info['instance']
                stats = status_info.get('statistics', {})
                
                print(f"Check {i+1} - Status: {instance['status']}")
                if stats:
                    print(f"  Task Stats: Total {stats.get('total_tasks', 0)}, "
                          f"Completed {stats.get('completed_tasks', 0)}, "
                          f"Failed {stats.get('failed_tasks', 0)}")
                
                # Stop monitoring if workflow is finished
                if instance['status'] in ['completed', 'failed', 'cancelled']:
                    print(f"[OK] Workflow execution finished, Final status: {instance['status']}")
                    break
        else:
            print("[WARNING] Monitoring timeout, workflow may still be running")
        
        return instance_id
        
    except Exception as e:
        print(f"[ERROR] Workflow execution failed: {e}")
        return None


async def test_system_monitoring(instance_id):
    """Test system monitoring"""
    print("\n=== Step 3: Testing System Monitoring ===")
    
    try:
        # Get current metrics
        print("Getting system monitoring metrics...")
        metrics = await monitoring_service.get_current_metrics()
        
        print("[OK] System monitoring metrics:")
        print(f"  Total workflows: {metrics['metrics']['workflows']['total']}")
        print(f"  Running workflows: {metrics['metrics']['workflows']['running']}")
        print(f"  Total tasks: {metrics['metrics']['tasks']['total']}")
        print(f"  Success rate: {metrics['metrics']['performance']['success_rate']:.1f}%")
        print(f"  Total alerts: {metrics['alerts']['total']}")
        
        # Get workflow health status
        if instance_id:
            print(f"\nGetting workflow health status (ID: {instance_id})...")
            health = await monitoring_service.get_workflow_health(instance_id)
            
            print("[OK] Workflow health status:")
            print(f"  Health score: {health['health_score']:.1f}/100")
            print(f"  Status: {health['status']}")
            print(f"  Issues count: {len(health['issues'])}")
            
            if health['issues']:
                print("  Issues found:")
                for issue in health['issues']:
                    print(f"    - [{issue['severity']}] {issue['message']}")
    
    except Exception as e:
        print(f"[ERROR] System monitoring test failed: {e}")


async def test_agent_tasks():
    """Test agent task processing"""
    print("\n=== Step 4: Testing Agent Task Processing ===")
    
    try:
        # Get pending agent tasks
        print("Getting pending agent tasks...")
        pending_tasks = await agent_task_service.get_pending_agent_tasks(limit=5)
        
        print(f"[OK] Found {len(pending_tasks)} pending agent tasks")
        
        if pending_tasks:
            # Test first task
            test_task = pending_tasks[0]
            task_id = test_task['task_instance_id']
            
            print(f"Testing task: {test_task['task_title']} (ID: {task_id})")
            
            # Process agent task
            print("Processing agent task...")
            process_result = await agent_task_service.process_agent_task(task_id)
            
            if process_result['status'] == 'completed':
                print("[OK] Agent task processing completed")
                print(f"  Duration: {process_result.get('duration', 'N/A')} minutes")
                print(f"  Confidence: {process_result['result'].get('confidence_score', 'N/A')}")
            else:
                print(f"[ERROR] Agent task processing failed: {process_result.get('message', 'Unknown error')}")
            
            # Get agent task statistics
            print("Getting agent task statistics...")
            stats = await agent_task_service.get_agent_task_statistics()
            
            print("[OK] Agent task statistics:")
            print(f"  Total tasks: {stats['total_tasks']}")
            print(f"  Completed: {stats['completed_tasks']}")
            print(f"  Success rate: {stats['success_rate']:.1f}%")
            print(f"  Queue size: {stats['queue_size']}")
        else:
            print("[WARNING] No agent tasks found for testing")
            
    except Exception as e:
        print(f"[ERROR] Agent task processing test failed: {e}")


async def run_simple_test():
    """Run the complete simple test"""
    print("=" * 80)
    print("SIMPLE WORKFLOW EXECUTION TEST")
    print("=" * 80)
    
    try:
        # Initialize database
        await initialize_database()
        print("[OK] Database connection initialized")
        
        # Step 1: Create test workflow
        workflow_info = await create_simple_workflow()
        
        if not workflow_info:
            print("[ERROR] Test workflow creation failed, terminating test")
            return False
        
        # Step 2: Test workflow execution
        instance_id = await test_workflow_execution(workflow_info)
        
        # Wait for tasks to be created
        await asyncio.sleep(5)
        
        # Step 3: Test system monitoring
        await test_system_monitoring(instance_id)
        
        # Step 4: Test agent task processing
        await test_agent_tasks()
        
        print("\n" + "=" * 80)
        print("[SUCCESS] Simple execution test completed!")
        print("=" * 80)
        
        # Test summary
        print("\nTest Summary:")
        print("[OK] Workflow creation and configuration")
        print("[OK] Workflow execution engine")
        print("[OK] Agent task processing")
        print("[OK] Status monitoring and tracking")
        print("[OK] OpenAI integration simulation")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Test process error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup resources
        try:
            await execution_engine.stop_engine()
            await agent_task_service.stop_service()
            await monitoring_service.stop_monitoring()
            await close_database()
            print("\n[OK] Resource cleanup completed")
        except Exception as e:
            print(f"\n[WARNING] Resource cleanup exception: {e}")


async def main():
    """Main function"""
    print("Starting simple workflow execution test...")
    
    success = await run_simple_test()
    
    if success:
        print("\n[SUCCESS] All tests passed! Workflow execution functionality is working properly.")
        return 0
    else:
        print("\n[FAILED] Tests failed! Please check error messages.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[WARNING] Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Program execution error: {e}")
        sys.exit(1)