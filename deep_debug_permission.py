#!/usr/bin/env python3
"""
深度调试权限检查逻辑
Deep debug permission check logic
"""

import asyncio
import sys
import uuid
from pathlib import Path
from loguru import logger

# 添加父目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

async def deep_debug_permission():
    """深度调试权限检查"""
    try:
        logger.info("🔍 深度调试权限检查逻辑...")
        
        from backend.utils.database import initialize_database, db_manager
        from backend.services.workflow_service import WorkflowService
        from backend.repositories.workflow.workflow_repository import WorkflowRepository
        from backend.models.workflow import WorkflowCreate
        
        await initialize_database()
        
        # 获取用户
        user = await db_manager.fetch_one("SELECT user_id FROM user LIMIT 1")
        user_id = user['user_id']
        
        print(f"👤 使用用户ID: {user_id} (类型: {type(user_id)})")
        
        # 创建工作流
        unique_name = f"深度调试_{uuid.uuid4().hex[:6]}"
        workflow_service = WorkflowService()
        workflow_create = WorkflowCreate(
            name=unique_name,
            description="深度调试权限",
            creator_id=user_id
        )
        
        print(f"\n1️⃣ 创建工作流: {unique_name}")
        created_workflow = await workflow_service.create_workflow(workflow_create)
        workflow_base_id = created_workflow.workflow_base_id
        print(f"✅ 工作流创建成功: {workflow_base_id}")
        print(f"  创建者ID: {created_workflow.creator_id} (类型: {type(created_workflow.creator_id)})")
        
        # 立即测试workflow_repository查询
        print(f"\n2️⃣ 测试workflow_repository查询...")
        workflow_repo = WorkflowRepository()
        
        try:
            queried_workflow = await workflow_repo.get_workflow_by_base_id(workflow_base_id)
            
            if queried_workflow:
                print(f"✅ 查询成功:")
                print(f"  名称: {queried_workflow.get('name')}")
                print(f"  Base ID: {queried_workflow.get('workflow_base_id')}")
                print(f"  创建者ID: {queried_workflow.get('creator_id')} (类型: {type(queried_workflow.get('creator_id'))})")
                print(f"  是否当前版本: {queried_workflow.get('is_current_version')}")
                print(f"  是否删除: {queried_workflow.get('is_deleted')}")
                
                # 模拟权限检查逻辑
                print(f"\n3️⃣ 模拟权限检查逻辑...")
                
                workflow_creator_id = queried_workflow['creator_id']
                print(f"  步骤1 - 工作流创建者: {workflow_creator_id} (类型: {type(workflow_creator_id)})")
                print(f"  步骤2 - 当前用户: {user_id} (类型: {type(user_id)})")
                
                # 类型转换逻辑（模拟_check_workflow_permission）
                if isinstance(workflow_creator_id, str):
                    converted_creator_id = uuid.UUID(workflow_creator_id)
                    print(f"  步骤3 - 转换后创建者: {converted_creator_id} (类型: {type(converted_creator_id)})")
                else:
                    converted_creator_id = workflow_creator_id
                    print(f"  步骤3 - 创建者无需转换: {converted_creator_id} (类型: {type(converted_creator_id)})")
                
                if isinstance(user_id, str):
                    converted_user_id = uuid.UUID(user_id)
                    print(f"  步骤4 - 转换后用户: {converted_user_id} (类型: {type(converted_user_id)})")
                else:
                    converted_user_id = user_id
                    print(f"  步骤4 - 用户无需转换: {converted_user_id} (类型: {type(converted_user_id)})")
                
                # 比较结果
                permission_result = converted_creator_id == converted_user_id
                print(f"  步骤5 - 权限检查结果: {permission_result}")
                
                if permission_result:
                    print(f"  ✅ 权限检查应该通过")
                else:
                    print(f"  ❌ 权限检查失败")
                    print(f"    创建者UUID: {converted_creator_id}")
                    print(f"    用户UUID: {converted_user_id}")
                    print(f"    相等性检查: {converted_creator_id == converted_user_id}")
                    print(f"    字符串比较: {str(converted_creator_id) == str(converted_user_id)}")
                
            else:
                print(f"❌ 查询失败 - 返回None")
                print(f"  这解释了为什么权限检查失败!")
                
                # 检查数据库原始数据
                print(f"\n🔍 检查数据库原始数据...")
                raw_data = await db_manager.fetch_one("""
                    SELECT * FROM workflow 
                    WHERE workflow_base_id = %s 
                    ORDER BY created_at DESC
                    LIMIT 1
                """, workflow_base_id)
                
                if raw_data:
                    print(f"✅ 原始数据存在:")
                    for key, value in raw_data.items():
                        print(f"    {key}: {value} (类型: {type(value)})")
                else:
                    print(f"❌ 原始数据也不存在!")
        
        except Exception as e:
            print(f"❌ 查询异常: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        logger.error(f"深度调试失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("=" * 80)
    print("🔍 深度调试权限检查逻辑")
    print("=" * 80)
    
    await deep_debug_permission()

if __name__ == "__main__":
    asyncio.run(main())