#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import requests
from loguru import logger

async def test_workflow_execution():
    """Test workflow execution after the fix"""
    
    # Test data for workflow execution
    test_data = {
        "workflow_base_id": "c49c3885-47b9-48f5-99d4-16f9ff3e7d38",  # From the error message
        "instance_name": "test_execution_" + str(asyncio.get_event_loop().time()),
        "input_data": {},
        "context_data": {}
    }
    
    try:
        logger.info("Testing workflow execution API...")
        
        # Make POST request to the execution endpoint
        response = requests.post(
            "http://localhost:8001/api/execution/workflows/execute",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info("SUCCESS: Workflow execution started!")
            logger.info(f"Result: {result}")
            return True
        else:
            logger.error(f"FAILED: Status {response.status_code}")
            logger.error(f"Response text: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"EXCEPTION: {e}")
        return False

if __name__ == "__main__":
    # Remove any unicode characters that might cause issues
    logger.remove()
    logger.add(lambda msg: print(msg.strip()), level="INFO")
    
    success = asyncio.run(test_workflow_execution())
    
    if success:
        print("Test PASSED - The constraint fix worked!")
    else:
        print("Test FAILED - Need to investigate further")