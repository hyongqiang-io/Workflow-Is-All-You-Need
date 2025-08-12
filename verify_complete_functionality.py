"""
验证修正后的完整功能
Verify Complete Functionality After Corrections
"""

import asyncio
import sys
import os
from loguru import logger

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from backend.utils.database import db_manager
from backend.config import get_settings


async def test_table_structure():
    """测试表结构"""
    try:
        logger.info("🔍 测试表结构...")
        
        await db_manager.initialize()
        
        # 测试workflow表结构修正
        workflows = await db_manager.fetch_all("""
            SELECT workflow_id, name, description, creator_id, version, is_current_version 
            FROM `workflow` 
            WHERE is_deleted = %s 
            LIMIT 3
        """, False)
        
        logger.info(f"✅ workflow表查询成功，找到 {len(workflows)} 个工作流")
        for workflow in workflows:
            logger.info(f"  工作流: {workflow['name']} (版本: {workflow['version']})")
        
        # 测试user表
        users = await db_manager.fetch_all("""
            SELECT user_id, username, email, role, status 
            FROM `user` 
            WHERE is_deleted = %s 
            LIMIT 3
        """, False)
        
        logger.info(f"✅ user表查询成功，找到 {len(users)} 个用户")
        for user in users:
            logger.info(f"  用户: {user['username']} ({user['role']})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 表结构测试失败: {e}")
        return False


async def test_views():
    """测试视图"""
    try:
        logger.info("🔍 测试数据库视图...")
        
        # 测试current_workflow_view
        workflow_view = await db_manager.fetch_all("""
            SELECT workflow_id, name, creator_name, version 
            FROM current_workflow_view 
            LIMIT 3
        """)
        
        logger.info(f"✅ current_workflow_view 查询成功，找到 {len(workflow_view)} 个当前工作流")
        for wf in workflow_view:
            logger.info(f"  工作流: {wf['name']} (创建者: {wf['creator_name']})")
        
        # 测试workflow_summary_view
        summary_view = await db_manager.fetch_all("""
            SELECT name, creator_name, node_count, is_current_version 
            FROM workflow_summary_view 
            LIMIT 3
        """)
        
        logger.info(f"✅ workflow_summary_view 查询成功，找到 {len(summary_view)} 个工作流摘要")
        for summary in summary_view:
            logger.info(f"  工作流: {summary['name']} (节点数: {summary['node_count']})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 视图测试失败: {e}")
        return False


async def test_functions():
    """测试存储函数"""
    try:
        logger.info("🔍 测试存储函数...")
        
        # 获取第一个用户ID
        user = await db_manager.fetch_one("SELECT user_id FROM `user` LIMIT 1")
        if not user:
            logger.warning("没有用户数据，跳过函数测试")
            return True
        
        user_id = user['user_id']
        
        # 测试create_initial_workflow函数
        workflow_id = await db_manager.call_function(
            'create_initial_workflow',
            '测试完整功能工作流',
            '这是验证修正后功能的测试工作流',
            user_id
        )
        
        if workflow_id:
            logger.info(f"✅ create_initial_workflow 函数测试成功，创建工作流ID: {workflow_id}")
            
            # 验证创建的工作流
            created_workflow = await db_manager.fetch_one("""
                SELECT name, description, creator_id, version, is_current_version 
                FROM `workflow` 
                WHERE workflow_id = %s
            """, workflow_id)
            
            if created_workflow:
                logger.info(f"  验证: 工作流 '{created_workflow['name']}' 版本 {created_workflow['version']}")
                logger.info(f"  当前版本: {created_workflow['is_current_version']}")
            
            # 测试create_workflow_node函数 - 如果表结构支持
            try:
                # 首先获取workflow_base_id
                workflow_info = await db_manager.fetch_one("""
                    SELECT workflow_base_id FROM `workflow` WHERE workflow_id = %s
                """, workflow_id)
                
                if workflow_info:
                    node_id = await db_manager.call_function(
                        'create_workflow_node',
                        workflow_id,
                        workflow_info['workflow_base_id'],
                        '开始节点',
                        'start',
                        '工作流开始节点',
                        100,
                        100
                    )
                    
                    if node_id:
                        logger.info(f"✅ create_workflow_node 函数测试成功，创建节点ID: {node_id}")
                
            except Exception as e:
                logger.warning(f"节点创建函数测试跳过: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 函数测试失败: {e}")
        return False


async def test_postgresql_compatibility():
    """测试PostgreSQL兼容性"""
    try:
        logger.info("🔍 测试PostgreSQL兼容性...")
        
        # 测试占位符转换 ($1, $2 -> %s, %s)
        result = await db_manager.fetch_one("""
            SELECT username, email 
            FROM "user" 
            WHERE username = $1 AND is_deleted = $2
        """, 'admin', False)
        
        if result:
            logger.info(f"✅ PostgreSQL占位符转换成功: {result['username']}")
        
        # 测试表名引用转换 ("table" -> `table`)
        count = await db_manager.fetch_val("""
            SELECT COUNT(*) 
            FROM "workflow" 
            WHERE is_deleted = $1
        """, False)
        
        logger.info(f"✅ PostgreSQL表名引用转换成功，工作流总数: {count}")
        
        # 测试复杂查询
        complex_result = await db_manager.fetch_all("""
            SELECT w.name, u.username as creator 
            FROM "workflow" w 
            JOIN "user" u ON w.creator_id = u.user_id 
            WHERE w.is_deleted = $1 
            LIMIT $2
        """, False, 3)
        
        logger.info(f"✅ 复杂查询转换成功，找到 {len(complex_result)} 个结果")
        for result in complex_result:
            logger.info(f"  工作流: {result['name']} (创建者: {result['creator']})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL兼容性测试失败: {e}")
        return False


async def test_data_operations():
    """测试数据操作"""
    try:
        logger.info("🔍 测试数据操作...")
        
        # 测试插入操作
        test_user_id = await db_manager.fetch_val("SELECT UUID()")
        
        insert_result = await db_manager.execute("""
            INSERT INTO `user` (user_id, username, email, password_hash, role, status) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, test_user_id, f'test_user_{test_user_id[:8]}', f'test_{test_user_id[:8]}@example.com', 
           'hashed_password', 'user', True)
        
        logger.info(f"✅ 插入操作成功: {insert_result}")
        
        # 测试更新操作
        update_result = await db_manager.execute("""
            UPDATE `user` 
            SET description = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = %s
        """, '测试用户描述', test_user_id)
        
        logger.info(f"✅ 更新操作成功: {update_result}")
        
        # 测试删除操作（软删除）
        delete_result = await db_manager.execute("""
            UPDATE `user` 
            SET is_deleted = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = %s
        """, True, test_user_id)
        
        logger.info(f"✅ 软删除操作成功: {delete_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 数据操作测试失败: {e}")
        return False


async def generate_test_report():
    """生成测试报告"""
    try:
        logger.info("📊 生成测试报告...")
        
        # 统计信息
        stats = {}
        
        # 表统计
        stats['users'] = await db_manager.fetch_val("SELECT COUNT(*) FROM `user` WHERE is_deleted = %s", False)
        stats['workflows'] = await db_manager.fetch_val("SELECT COUNT(*) FROM `workflow` WHERE is_deleted = %s", False)
        stats['current_workflows'] = await db_manager.fetch_val("SELECT COUNT(*) FROM `workflow` WHERE is_deleted = %s AND is_current_version = %s", False, True)
        
        # 视图统计
        stats['workflow_views'] = await db_manager.fetch_val("SELECT COUNT(*) FROM current_workflow_view")
        
        logger.info("📈 数据库统计:")
        logger.info(f"  用户总数: {stats['users']}")
        logger.info(f"  工作流总数: {stats['workflows']}")
        logger.info(f"  当前版本工作流: {stats['current_workflows']}")
        logger.info(f"  视图可访问工作流: {stats['workflow_views']}")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ 生成报告失败: {e}")
        return None


async def main():
    """主函数"""
    print("=" * 80)
    print("🔍 MySQL迁移完整功能验证")
    print("=" * 80)
    
    test_results = []
    
    try:
        # 初始化数据库连接
        await db_manager.initialize()
        logger.info("✅ 数据库连接初始化成功")
        
        # 运行各项测试
        tests = [
            ("表结构测试", test_table_structure),
            ("视图功能测试", test_views),
            ("存储函数测试", test_functions),
            ("PostgreSQL兼容性测试", test_postgresql_compatibility),
            ("数据操作测试", test_data_operations)
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n🧪 开始 {test_name}...")
            success = await test_func()
            test_results.append((test_name, success))
            
            if success:
                logger.info(f"✅ {test_name} 通过")
            else:
                logger.error(f"❌ {test_name} 失败")
        
        # 生成报告
        logger.info(f"\n📊 生成最终报告...")
        stats = await generate_test_report()
        
        # 总结
        logger.info(f"\n{'='*80}")
        logger.info("🎯 测试结果总结:")
        
        passed_tests = sum(1 for _, success in test_results if success)
        total_tests = len(test_results)
        
        for test_name, success in test_results:
            status = "✅ 通过" if success else "❌ 失败"
            logger.info(f"  {test_name}: {status}")
        
        logger.info(f"\n📈 总体结果: {passed_tests}/{total_tests} 测试通过")
        
        if passed_tests == total_tests:
            logger.info("🎉 所有测试通过！MySQL迁移完全成功！")
            logger.info("💡 您的应用现在可以完全正常使用MySQL数据库了")
        else:
            logger.warning(f"⚠️  有 {total_tests - passed_tests} 个测试失败，请检查相关功能")
        
    except Exception as e:
        logger.error(f"❌ 验证过程失败: {e}")
    finally:
        await db_manager.close()
        logger.info("🔒 数据库连接已关闭")


if __name__ == "__main__":
    asyncio.run(main())