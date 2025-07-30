"""
测试改进后的工作流执行流程
Test Improved Workflow Execution Flow
"""

import asyncio
import uuid
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from workflow_framework.services.execution_service import execution_engine
from workflow_framework.models.instance import WorkflowExecuteRequest
from workflow_framework.utils.database import initialize_database
from loguru import logger

async def test_workflow_execution():
    """测试工作流执行流程"""
    try:
        print("🚀 开始测试改进后的工作流执行流程")
        print("=" * 60)
        
        # 1. 初始化数据库连接
        print("📚 1. 初始化数据库连接...")
        await initialize_database()
        print("   ✅ 数据库连接初始化完成")
        
        # 2. 启动执行引擎
        print("\n🔧 2. 启动执行引擎...")
        await execution_engine.start_engine()
        print("   ✅ 执行引擎启动完成")
        
        # 3. 准备测试数据
        print("\n📋 3. 准备测试数据...")
        
        # 这些ID需要根据您的实际数据库中的数据来调整
        test_workflow_base_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")  # 请替换为实际的工作流ID
        test_executor_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174111")      # 请替换为实际的用户ID
        
        # 创建执行请求
        execute_request = WorkflowExecuteRequest(
            workflow_base_id=test_workflow_base_id,
            instance_name="测试工作流实例_" + str(uuid.uuid4())[:8],
            input_data={
                "test_input": "这是测试输入数据",
                "priority": "high",
                "created_by": "test_system"
            },
            context_data={
                "test_context": "测试上下文数据",
                "environment": "development"
            }
        )
        
        print(f"   - 工作流Base ID: {test_workflow_base_id}")
        print(f"   - 执行者ID: {test_executor_id}")
        print(f"   - 实例名称: {execute_request.instance_name}")
        print("   ✅ 测试数据准备完成")
        
        # 4. 执行工作流
        print(f"\n🎯 4. 开始执行工作流...")
        print("-" * 40)
        
        try:
            result = await execution_engine.execute_workflow(execute_request, test_executor_id)
            
            print(f"\n✅ 工作流执行启动成功!")
            print(f"   - 实例ID: {result['instance_id']}")
            print(f"   - 状态: {result['status']}")
            print(f"   - 消息: {result['message']}")
            
            instance_id = uuid.UUID(result['instance_id'])
            
            # 5. 等待一段时间让任务分配完成
            print(f"\n⏳ 5. 等待任务分配和处理...")
            await asyncio.sleep(5)
            
            # 6. 查询工作流状态
            print(f"\n📊 6. 查询工作流状态...")
            status_info = await execution_engine.get_workflow_status(instance_id)
            
            if status_info:
                instance = status_info['instance']
                stats = status_info['statistics']
                
                print(f"   - 工作流实例: {instance.get('workflow_instance_name', 'Unknown')}")
                print(f"   - 状态: {instance.get('status', 'Unknown')}")
                print(f"   - 创建时间: {instance.get('created_at', 'Unknown')}")
                print(f"   - 总节点数: {stats.total_nodes if stats else 'Unknown'}")
                print(f"   - 完成节点数: {stats.completed_nodes if stats else 'Unknown'}")
                print(f"   - 总任务数: {stats.total_tasks if stats else 'Unknown'}")
                print(f"   - 人工任务数: {stats.human_tasks if stats else 'Unknown'}")
                
            # 7. 检查生成的日志文件
            print(f"\n📄 7. 检查生成的日志文件...")
            
            # 检查用户通知日志
            notification_log_path = "user_notifications.log"
            if os.path.exists(notification_log_path):
                print(f"   ✅ 用户通知日志文件存在: {notification_log_path}")
                with open(notification_log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[-5:]  # 读取最后5行
                    if lines:
                        print("   最近的通知记录:")
                        for line in lines:
                            print(f"     {line.strip()}")
            else:
                print(f"   ⚠️  用户通知日志文件不存在: {notification_log_path}")
            
            # 检查任务事件日志
            event_log_path = "task_events.log"
            if os.path.exists(event_log_path):
                print(f"   ✅ 任务事件日志文件存在: {event_log_path}")
                with open(event_log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[-5:]  # 读取最后5行
                    if lines:
                        print("   最近的事件记录:")
                        for line in lines:
                            print(f"     {line.strip()}")
            else:
                print(f"   ⚠️  任务事件日志文件不存在: {event_log_path}")
            
        except Exception as e:
            print(f"\n❌ 工作流执行失败: {e}")
            import traceback
            print(f"   错误详情:\n{traceback.format_exc()}")
            
            # 如果是因为测试数据不存在，提供指导
            if "不存在" in str(e) or "does not exist" in str(e).lower():
                print(f"\n💡 提示: 请确保数据库中存在以下测试数据:")
                print(f"   - 工作流 (workflow_base_id): {test_workflow_base_id}")
                print(f"   - 用户 (user_id): {test_executor_id}")
                print(f"   - 或者修改 test_workflow_base_id 和 test_executor_id 为实际存在的ID")
        
        print(f"\n🏁 测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试过程出现错误: {e}")
        import traceback
        print(f"   错误详情:\n{traceback.format_exc()}")
    
    finally:
        # 清理：停止执行引擎
        try:
            await execution_engine.stop_engine()
            print(f"\n🛑 执行引擎已停止")
        except Exception as e:
            print(f"\n⚠️  停止执行引擎时出现错误: {e}")


async def query_existing_workflows():
    """查询现有的工作流，用于测试"""
    try:
        print("🔍 查询现有的工作流和用户数据...")
        
        from workflow_framework.repositories.workflow.workflow_repository import WorkflowRepository
        from workflow_framework.repositories.user.user_repository import UserRepository
        
        workflow_repo = WorkflowRepository()
        user_repo = UserRepository()
        
        # 查询工作流
        print("\n📋 现有工作流:")
        workflows = await workflow_repo.list_all({"is_current_version": True, "is_deleted": False})
        if workflows:
            for i, wf in enumerate(workflows[:5], 1):  # 只显示前5个
                print(f"   {i}. {wf.get('name', 'Unknown')} (Base ID: {wf.get('workflow_base_id')})")
        else:
            print("   没有找到工作流")
        
        # 查询用户
        print("\n👥 现有用户:")
        users = await user_repo.list_all({"is_deleted": False})
        if users:
            for i, user in enumerate(users[:5], 1):  # 只显示前5个
                print(f"   {i}. {user.get('username', 'Unknown')} (ID: {user.get('user_id')})")
        else:
            print("   没有找到用户")
            
        return workflows, users
        
    except Exception as e:
        print(f"❌ 查询数据失败: {e}")
        return [], []


async def main():
    """主函数"""
    print("🧪 工作流执行流程测试程序")
    print("=" * 60)
    
    # 首先查询现有数据
    try:
        await initialize_database()
        workflows, users = await query_existing_workflows()
        
        if not workflows or not users:
            print(f"\n⚠️  数据库中缺少测试数据，无法进行完整测试")
            print(f"   建议: 先创建工作流和用户数据")
            return
        
        # 使用第一个找到的工作流和用户进行测试
        test_workflow_base_id = workflows[0]['workflow_base_id']
        test_executor_id = users[0]['user_id']
        
        print(f"\n✅ 将使用以下数据进行测试:")
        print(f"   工作流: {workflows[0].get('name', 'Unknown')} ({test_workflow_base_id})")
        print(f"   用户: {users[0].get('username', 'Unknown')} ({test_executor_id})")
        
        # 继续执行测试
        await test_workflow_execution()
        
    except Exception as e:
        print(f"❌ 程序执行出现错误: {e}")
        import traceback
        print(f"错误详情:\n{traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())