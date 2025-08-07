#!/usr/bin/env python3
"""
一键重命名 workflow_framework -> backend
自动更新所有相关路径和导入语句
"""

import os
import shutil
import re
from pathlib import Path


def main():
    base_dir = Path(__file__).parent
    old_name = "workflow_framework"
    new_name = "backend"
    
    print(f"[START] 开始重命名 {old_name} -> {new_name}")
    
    # 1. 检查目标目录是否存在
    old_path = base_dir / old_name
    new_path = base_dir / new_name
    
    if not old_path.exists():
        print(f"[ERROR] 源目录不存在: {old_path}")
        return
    
    if new_path.exists():
        print(f"[ERROR] 目标目录已存在: {new_path}")
        return
    
    # 2. 重命名文件夹
    print(f"[RENAME] 重命名文件夹: {old_path} -> {new_path}")
    shutil.move(str(old_path), str(new_path))
    
    # 3. 需要更新的文件列表
    files_to_update = [
        "main.py",
        "main_no_openai.py", 
        "main_no_db.py",
        "migrate_mcp_data.py",
        "inspect_context_data.py",
        "verify_deployment_config.sh",
        "Dockerfile.backend",
        "deployment/scripts/test-local.sh",
        "deployment/scripts/test-deployment.sh", 
        "deployment/scripts/deploy.sh",
        "deployment/scripts/upgrade.sh",
        "config_backup/deployment_scripts_test-local.sh"
    ]
    
    # 4. 更新backend目录内的文件
    backend_files = []
    for root, dirs, files in os.walk(new_path):
        for file in files:
            if file.endswith('.py'):
                backend_files.append(Path(root) / file)
    
    # 5. 更新所有文件中的引用
    all_files = []
    
    # 添加根目录文件
    for file_path in files_to_update:
        full_path = base_dir / file_path
        if full_path.exists():
            all_files.append(full_path)
    
    # 添加backend目录内的Python文件
    all_files.extend(backend_files)
    
    print(f"[UPDATE] 需要更新的文件数量: {len(all_files)}")
    
    # 6. 执行替换
    patterns = [
        (rf'\bfrom {old_name}\.', f'from {new_name}.'),
        (rf'\bimport {old_name}\.', f'import {new_name}.'),
        (rf'\b{old_name}/', f'{new_name}/'),
        (rf'"{old_name}/"', f'"{new_name}/"'),
        (rf"'{old_name}/'", f"'{new_name}/'"),
        (rf'\b{old_name}\b(?=\.)', new_name),  # workflow_framework.xxx -> backend.xxx
    ]
    
    updated_files = 0
    total_replacements = 0
    
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            file_replacements = 0
            
            # 应用所有替换规则
            for pattern, replacement in patterns:
                new_content, count = re.subn(pattern, replacement, content)
                content = new_content
                file_replacements += count
            
            # 如果文件有变化，写回文件
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                updated_files += 1
                total_replacements += file_replacements
                print(f"   [OK] {file_path.relative_to(base_dir)}: {file_replacements} 处替换")
        
        except Exception as e:
            print(f"   [ERROR] 更新失败 {file_path}: {e}")
    
    # 7. 显示总结
    print(f"\n[SUCCESS] 重命名完成!")
    print(f"   [FOLDER] 文件夹已重命名: {old_name} -> {new_name}")
    print(f"   [FILES] 更新的文件数: {updated_files}")
    print(f"   [CHANGES] 总替换次数: {total_replacements}")
    
    print(f"\n[TODO] 建议检查:")
    print(f"   1. 运行 python main.py 检查是否正常启动")
    print(f"   2. 检查 IDE 中是否还有红色导入错误")
    print(f"   3. 运行测试确保功能正常")
    
    # 8. 创建 .gitignore 条目（如果需要）
    gitignore_path = base_dir / ".gitignore"
    if gitignore_path.exists():
        try:
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()
            
            if f"{old_name}/" in gitignore_content:
                new_gitignore = gitignore_content.replace(f"{old_name}/", f"{new_name}/")
                with open(gitignore_path, 'w') as f:
                    f.write(new_gitignore)
                print(f"   [GITIGNORE] 已更新 .gitignore")
        except Exception as e:
            print(f"   [WARNING] .gitignore 更新失败: {e}")


if __name__ == "__main__":
    main()