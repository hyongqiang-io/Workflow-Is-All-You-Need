# 任务细分逻辑重构 - API兼容性迁移脚本

# 这个脚本用于将现有API切换到重构版本，同时保持完全兼容

import os
import sys

def migrate_to_refactored_service():
    """
    将原有的TaskSubdivisionService替换为重构版本
    保持API完全兼容
    """
    print("🔄 开始迁移任务细分服务到重构版本...")
    
    # 1. 备份原文件
    original_service_path = "/home/ubuntu/Workflow-Is-All-You-Need/backend/services/task_subdivision_service.py"
    backup_path = f"{original_service_path}.backup"
    
    if os.path.exists(original_service_path):
        os.rename(original_service_path, backup_path)
        print(f"✅ 原服务已备份到: {backup_path}")
    
    # 2. 将重构版本重命名为原文件名
    refactored_service_path = "/home/ubuntu/Workflow-Is-All-You-Need/backend/services/task_subdivision_service_refactored.py"
    
    if os.path.exists(refactored_service_path):
        # 读取重构版本内容
        with open(refactored_service_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换类名和导入，使其兼容现有API
        content = content.replace(
            'class TaskSubdivisionServiceRefactored:',
            'class TaskSubdivisionService:'
        )
        content = content.replace(
            'task_subdivision_service_refactored = TaskSubdivisionServiceRefactored()',
            'task_subdivision_service = TaskSubdivisionService()'
        )
        
        # 写入到原服务位置
        with open(original_service_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 重构版本已部署到: {original_service_path}")
    
    # 3. 更新前端组件（可选）
    print("\n📋 前端组件更新说明:")
    print("如需使用新的前端组件，请执行以下步骤:")
    print("1. 备份现有组件: mv TaskSubdivisionModal.tsx TaskSubdivisionModal.tsx.backup")
    print("2. 使用新组件: mv TaskSubdivisionModalRefactored.tsx TaskSubdivisionModal.tsx")
    print("3. 更新组件内的导出名称，确保导入路径正确")
    
    print("\n🎉 迁移完成!")
    print("\n📝 重构改进总结:")
    print("1. ✅ 分离工作流模板和实例概念")
    print("2. ✅ 用户可选择现有工作流或创建新工作流")
    print("3. ✅ 避免重复创建工作流模板")
    print("4. ✅ 保持API完全兼容")
    print("5. ✅ 简化前端工作流选择逻辑")
    
    print("\n⚠️ 测试建议:")
    print("1. 测试使用现有工作流模板进行任务细分")
    print("2. 测试创建新工作流模板进行任务细分")
    print("3. 验证执行结果回传功能正常")
    print("4. 检查细分记录和实例的关联关系")
    
if __name__ == "__main__":
    migrate_to_refactored_service()