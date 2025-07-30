#!/usr/bin/env python3
import requests
import json

# Test node info from the database
node_base_id = "eaab4463-8480-490f-8f1a-04ec0e17ef8c"
workflow_base_id = "744d7673-6d0a-4e2c-817a-be791c40b049"

print("Testing API connection...")

# First test health check
try:
    response = requests.get("http://localhost:8001/health")
    print(f"Health check: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Backend connection failed: {e}")
    exit(1)

# Test node update API
url = f"http://localhost:8001/api/nodes/{node_base_id}/workflow/{workflow_base_id}"
test_data = {
    "name": "Test Update Node",
    "task_description": "API Test Description", 
    "position_x": 100,
    "position_y": 200
}

headers = {"Content-Type": "application/json"}

print(f"Testing URL: {url}")
print(f"Test data: {json.dumps(test_data)}")

try:
    response = requests.put(url, json=test_data, headers=headers)
    print(f"API Response: {response.status_code}")
    print(f"Response content: {response.text}")
    
    if response.status_code == 401:
        print("Need authentication - 401 error")
    elif response.status_code == 404:
        print("Node not found - 404 error")  
    elif response.status_code == 200:
        print("API call successful")
    else:
        print(f"Other error: {response.status_code}")
        
except Exception as e:
    print(f"API call exception: {e}")