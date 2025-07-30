#!/usr/bin/env python3
"""
测试运行脚本
Test Runner Script
"""

import sys
import os
import asyncio
import subprocess
from pathlib import Path


def run_command(cmd, description=""):
    """运行命令并打印输出"""
    print(f"\n{'='*60}")
    print(f"运行: {description}")
    print(f"命令: {cmd}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print("输出:")
        print(result.stdout)
    
    if result.stderr:
        print("错误:")
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"命令失败，返回码: {result.returncode}")
        return False
    
    print("命令成功完成")
    return True


def main():
    """主函数"""
    print("Workflow Framework 测试套件运行器")
    print("=" * 60)
    
    # 确保在正确的目录中
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        print("\n可用的测试选项:")
        print("1. all      - 运行所有测试")
        print("2. crud     - 运行CRUD操作测试")
        print("3. instance - 运行实例管理测试")
        print("4. version  - 运行版本管理测试")
        print("5. integration - 运行集成测试")
        print("6. quick    - 运行快速测试（不包含慢速测试）")
        print("7. coverage - 运行测试并生成覆盖率报告")
        
        test_type = input("\n请选择测试类型 (默认: all): ").lower() or "all"
    
    success = True
    
    if test_type == "all":
        success &= run_command(
            "python -m pytest tests/ -v", 
            "运行所有测试"
        )
    
    elif test_type == "crud":
        success &= run_command(
            "python -m pytest tests/test_crud_operations.py -v", 
            "运行CRUD操作测试"
        )
    
    elif test_type == "instance":
        success &= run_command(
            "python -m pytest tests/test_instance_management.py -v", 
            "运行实例管理测试"
        )
    
    elif test_type == "version":
        success &= run_command(
            "python -m pytest tests/test_version_management.py -v", 
            "运行版本管理测试"
        )
    
    elif test_type == "integration":
        success &= run_command(
            "python -m pytest tests/test_integration.py -v", 
            "运行集成测试"
        )
    
    elif test_type == "quick":
        success &= run_command(
            "python -m pytest tests/ -v -m 'not slow'", 
            "运行快速测试"
        )
    
    elif test_type == "coverage":
        success &= run_command(
            "python -m pytest tests/ --cov=workflow_framework --cov-report=html --cov-report=term", 
            "运行测试并生成覆盖率报告"
        )
        if success:
            print("\n覆盖率报告已生成在 htmlcov/ 目录中")
    
    elif test_type == "help":
        print("\n使用方法:")
        print("python run_tests.py [test_type]")
        print("\n测试类型:")
        print("  all        - 运行所有测试")
        print("  crud       - 运行CRUD操作测试")
        print("  instance   - 运行实例管理测试")
        print("  version    - 运行版本管理测试")
        print("  integration- 运行集成测试")
        print("  quick      - 运行快速测试")
        print("  coverage   - 运行测试并生成覆盖率")
        print("  help       - 显示此帮助信息")
        return
    
    else:
        print(f"未知的测试类型: {test_type}")
        print("使用 'python run_tests.py help' 查看可用选项")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    if success:
        print("所有测试执行完成！")
        print("测试结果: 成功 ✅")
    else:
        print("测试执行完成，但有错误")
        print("测试结果: 失败 ❌")
        sys.exit(1)


if __name__ == "__main__":
    main()