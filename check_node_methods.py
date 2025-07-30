#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.getcwd())

from workflow_framework.repositories.node.node_repository import NodeRepository

# Check if the method exists
repo = NodeRepository()
print("NodeRepository methods:")
methods = [method for method in dir(repo) if not method.startswith('_') and 'connection' in method.lower()]
for method in methods:
    print(f"  - {method}")

print(f"\nHas get_node_outgoing_connections: {hasattr(repo, 'get_node_outgoing_connections')}")
print(f"Has get_workflow_connections: {hasattr(repo, 'get_workflow_connections')}")
print(f"Has create_connection: {hasattr(repo, 'create_connection')}")