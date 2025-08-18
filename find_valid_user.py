#!/usr/bin/env python3
"""
查找有效的用户ID并更新任务分配
"""

import asyncio
from backend.utils.database import db_manager

async def find_valid_user_and_update_task():
    """查找有效用户并更新任务分配"""
    print("🔍 查找有效用户...")
    
    try:
        # 初始化数据库连接
        await db_manager.initialize()
        
        # 查找现有用户
        users_query = "SELECT user_id, username, email FROM user LIMIT 5"
        users = await db_manager.fetch_all(users_query)
        
        if users:
            print(f"📋 找到 {len(users)} 个用户:")
            for i, user in enumerate(users, 1):
                print(f"   {i}. ID: {user['user_id']}, 用户名: {user['username']}, 邮箱: {user['email']}")
            
            # 使用第一个用户
            valid_user_id = users[0]['user_id']
            valid_username = users[0]['username']
            
            print(f"\n🎯 使用用户: {valid_username} (ID: {valid_user_id})")
            
            # 更新任务分配
            task_id = "e4f58eae-60de-4ebb-b42f-4d5f5de76642"
            
            update_query = """
            UPDATE task_instance 
            SET assigned_user_id = %s 
            WHERE task_instance_id = %s
            """
            
            result = await db_manager.execute(update_query, valid_user_id, task_id)
            print(f"✅ 任务分配更新成功: {result}")
            
            # 验证更新结果
            verify_query = """
            SELECT ti.task_instance_id, ti.task_title, ti.assigned_user_id, ti.assigned_agent_id, 
                   ti.processor_id, ti.status, u.username
            FROM task_instance ti
            LEFT JOIN user u ON ti.assigned_user_id = u.user_id
            WHERE ti.task_instance_id = %s
            """
            
            task_info = await db_manager.fetch_one(verify_query, task_id)
            
            if task_info:
                print(f"\n✅ 验证任务信息:")
                print(f"   - 任务ID: {task_info['task_instance_id']}")
                print(f"   - 任务标题: {task_info['task_title']}")
                print(f"   - 分配用户ID: {task_info['assigned_user_id']}")
                print(f"   - 分配用户名: {task_info['username']}")
                print(f"   - 分配代理ID: {task_info['assigned_agent_id']}")
                print(f"   - 处理器ID: {task_info['processor_id']}")
                print(f"   - 状态: {task_info['status']}")
                
                return str(valid_user_id), str(task_info['processor_id']) if task_info['processor_id'] else None
            else:
                print(f"❌ 未找到更新后的任务信息")
                return None, None
                
        else:
            print(f"❌ 未找到任何用户")
            return None, None
            
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
        return None, None
    finally:
        await db_manager.close()

if __name__ == "__main__":
    user_id, processor_id = asyncio.run(find_valid_user_and_update_task())
    if user_id:
        print(f"\n🎉 任务分配更新成功!")
        print(f"   - 测试用户ID: {user_id}")
        print(f"   - 处理器ID: {processor_id}")
        print(f"   - 现在可以进行processor保留测试!")
    else:
        print(f"\n❌ 无法完成任务分配更新")