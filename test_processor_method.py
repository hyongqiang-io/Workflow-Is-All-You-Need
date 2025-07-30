#!/usr/bin/env python3

# 测试ProcessorRepository方法添加
import sys
sys.path.insert(0, '.')

# 读取原文件内容
with open('workflow_framework/repositories/processor/processor_repository.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 确保方法被正确添加
if 'get_processors_by_node' not in content:
    print("方法不在文件中！")
else:
    print("方法在文件中")

# 检查文件的最后几行
lines = content.split('\n')
print("文件最后10行:")
for i, line in enumerate(lines[-10:]):
    print(f"{len(lines) - 10 + i + 1}: {repr(line)}")

# 尝试动态导入并测试
try:
    from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
    repo = ProcessorRepository()
    print("导入成功")
    print("方法存在:", hasattr(repo, 'get_processors_by_node'))
    
    # 检查类的所有方法
    import inspect
    methods = [name for name, method in inspect.getmembers(repo) if not name.startswith('_')]
    print("所有方法:", methods)
    
except Exception as e:
    print(f"导入失败: {e}")