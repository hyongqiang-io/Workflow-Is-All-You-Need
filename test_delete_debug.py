#!/usr/bin/env python3
"""
删除功能调试测试脚本
"""

import asyncio
import uuid
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_delete_functionality():
    print("开始测试删除功能...")
    
    try:
        # 导入必要的模块
        from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
        from workflow_framework.utils.database import get_db_manager, initialize_database
        
        # 初始化数据库连接
        await initialize_database()
        db_manager = get_db_manager()
        processor_repo = ProcessorRepository()
        
        print("数据库连接成功")
        
        # 测试处理器的存在
        test_processor_id = uuid.UUID("04939706-3a8d-46f1-a4f5-79ca6a6f2511")
        print(f"测试处理器ID: {test_processor_id}")
        
        # 1. 检查处理器是否存在
        print("\n1. 检查处理器是否存在...")
        processor_details = await processor_repo.get_processor_with_details(test_processor_id)
        
        if processor_details:
            print(f"找到处理器: {processor_details.get('name', 'Unknown')}")
            print(f"处理器类型: {processor_details.get('type', 'Unknown')}")
            print(f"是否已删除: {processor_details.get('is_deleted', 'Unknown')}")
        else:
            print("处理器不存在")
            
            # 让我们查看所有处理器
            print("\n查看所有处理器...")
            query = "SELECT processor_id, name, type, is_deleted FROM processor LIMIT 5"
            result = await db_manager.fetch_all(query)
            
            if result:
                print("现有处理器:")
                for row in result:
                    print(f"  ID: {row['processor_id']}, Name: {row['name']}, Type: {row['type']}, Deleted: {row['is_deleted']}")
                    
                # 使用第一个存在的处理器进行测试
                test_processor_id = result[0]['processor_id']
                print(f"\n使用第一个处理器进行测试: {test_processor_id}")
                processor_details = await processor_repo.get_processor_with_details(test_processor_id)
            else:
                print("数据库中没有处理器数据")
                return
        
        # 2. 检查数据库表结构
        print("\n2. 检查processor表结构...")
        table_info_query = """
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = 'processor' 
        ORDER BY ordinal_position
        """
        columns = await db_manager.fetch_all(table_info_query)
        
        print("processor表字段:")
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        # 检查关键字段
        has_is_deleted = any(col['column_name'] == 'is_deleted' for col in columns)
        has_updated_at = any(col['column_name'] == 'updated_at' for col in columns)
        
        print(f"\nis_deleted字段存在: {has_is_deleted}")
        print(f"updated_at字段存在: {has_updated_at}")
        
        if not has_is_deleted or not has_updated_at:
            print("关键字段缺失，这可能是删除失败的原因!")
            return
        
        # 3. 测试删除操作
        print(f"\n3. 测试删除操作...")
        print(f"删除前处理器状态: is_deleted = {processor_details.get('is_deleted', 'Unknown')}")
        
        try:
            # 执行删除操作
            delete_result = await processor_repo.delete_processor(test_processor_id, soft_delete=True)
            print(f"删除操作结果: {delete_result}")
            
            # 验证删除结果
            updated_processor = await processor_repo.get_processor_with_details(test_processor_id)
            if updated_processor:
                print(f"删除后处理器状态: is_deleted = {updated_processor.get('is_deleted', 'Unknown')}")
            else:
                print("删除后无法找到处理器(可能被过滤掉了)")
                
                # 直接查询数据库确认
                direct_query = "SELECT processor_id, name, is_deleted, updated_at FROM processor WHERE processor_id = $1"
                direct_result = await db_manager.fetch_all(direct_query, test_processor_id)
                
                if direct_result:
                    row = direct_result[0]
                    print(f"直接查询结果: is_deleted = {row['is_deleted']}, updated_at = {row['updated_at']}")
                
        except Exception as e:
            print(f"删除操作失败: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_delete_functionality())