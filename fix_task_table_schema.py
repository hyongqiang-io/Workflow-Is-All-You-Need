"""
修复任务表结构 - 添加缺失字段
Fix Task Table Schema - Add Missing Fields
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.utils.database import initialize_database, get_db_manager

async def fix_task_table_schema():
    """修复任务表结构"""
    try:
        print("🔧 开始修复任务表结构...")
        
        # 初始化数据库连接
        await initialize_database()
        db = get_db_manager()
        
        # 读取SQL文件
        sql_file = Path(__file__).parent / "add_missing_task_fields.sql"
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print("📄 执行数据库结构修复SQL...")
        
        # 执行SQL（分段执行，因为包含多个DO块）
        sql_statements = sql_content.split('-- 显示当前task_instance表结构')[0]
        
        # 执行结构修复
        await db.execute(sql_statements)
        print("✅ 数据库结构修复完成")
        
        # 查询表结构
        print("\n📋 查询当前task_instance表结构:")
        structure_query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns 
        WHERE table_name = 'task_instance' 
        ORDER BY ordinal_position;
        """
        
        columns = await db.fetch_all(structure_query)
        
        print("=" * 80)
        print(f"{'字段名':<20} {'数据类型':<25} {'可空':<8} {'默认值'}")
        print("=" * 80)
        
        for col in columns:
            column_name = col['column_name']
            data_type = col['data_type']
            is_nullable = '是' if col['is_nullable'] == 'YES' else '否'
            default_val = col['column_default'] or ''
            
            print(f"{column_name:<20} {data_type:<25} {is_nullable:<8} {default_val}")
        
        print("=" * 80)
        print(f"✅ task_instance表共有 {len(columns)} 个字段")
        
        # 检查关键字段是否存在
        field_names = [col['column_name'] for col in columns]
        required_fields = ['started_at', 'assigned_at', 'context_data', 'actual_duration', 'result_summary']
        
        print(f"\n🔍 检查关键字段:")
        for field in required_fields:
            if field in field_names:
                print(f"  ✅ {field} - 存在")
            else:
                print(f"  ❌ {field} - 缺失")
        
        print(f"\n🎉 任务表结构修复完成！")
        
    except Exception as e:
        print(f"❌ 修复任务表结构失败: {e}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")

async def main():
    """主函数"""
    print("🏥 任务表结构修复工具")
    print("=" * 50)
    
    await fix_task_table_schema()

if __name__ == "__main__":
    asyncio.run(main())