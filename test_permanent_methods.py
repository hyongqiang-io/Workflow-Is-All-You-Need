#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())

from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
from workflow_framework.repositories.node.node_repository import NodeRepository

async def test_permanent_methods():
    print("测试永久方法实现...")
    
    # 测试ProcessorRepository的方法
    print("\n1. 测试ProcessorRepository.get_processors_by_node方法:")
    processor_repo = ProcessorRepository()
    methods = [method for method in dir(processor_repo) if 'get_processors_by_node' in method]
    print(f"   方法存在: {bool(methods)}")
    if methods:
        print(f"   方法名: {methods}")
    
    # 测试NodeRepository的方法
    print("\n2. 测试NodeRepository.get_next_nodes方法:")
    node_repo = NodeRepository()
    methods = [method for method in dir(node_repo) if 'get_next_nodes' in method]
    print(f"   方法存在: {bool(methods)}")
    if methods:
        print(f"   方法名: {methods}")
    
    print("\n永久方法测试完成!")

if __name__ == "__main__":
    asyncio.run(test_permanent_methods())