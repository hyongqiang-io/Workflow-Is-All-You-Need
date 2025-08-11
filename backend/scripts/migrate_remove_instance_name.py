"""
数据库迁移脚本：删除workflow_instance表中的instance_name字段
Migration Script: Remove instance_name field from workflow_instance table
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from loguru import logger

# 添加父目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, parent_dir)

from backend.config import get_settings


class InstanceNameFieldMigration:
    """instance_name字段迁移器"""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def connect_database(self):
        """连接到数据库"""
        try:
            self.conn = await asyncpg.connect(
                host=self.settings.database.host,
                port=self.settings.database.port,
                user=self.settings.database.username,
                password=self.settings.database.password,
                database=self.settings.database.database
            )
            logger.info(f"✅ 成功连接到数据库: {self.settings.database.database}")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False
    
    async def close_connection(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn') and self.conn:
            await self.conn.close()
            logger.info("🔒 数据库连接已关闭")
    
    async def check_table_structure(self):
        """检查当前表结构"""
        logger.info("🔍 检查workflow_instance表当前结构...")
        
        query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'workflow_instance' 
        AND table_schema = 'public'
        AND column_name IN ('workflow_instance_name', 'instance_name')
        ORDER BY column_name
        """
        
        columns = await self.conn.fetch(query)
        
        if not columns:
            logger.error("❌ 未找到workflow_instance表或相关字段")
            return False
        
        logger.info("📋 当前字段状态:")
        for col in columns:
            nullable = "可空" if col['is_nullable'] == 'YES' else "非空"
            default = f" 默认值:{col['column_default']}" if col['column_default'] else ""
            logger.info(f"  • {col['column_name']}: {col['data_type']} [{nullable}]{default}")
        
        return columns
    
    async def backup_and_migrate_data(self):
        """备份instance_name数据到workflow_instance_name"""
        logger.info("💾 开始备份instance_name数据到workflow_instance_name...")
        
        # 检查有多少条记录需要迁移
        count_query = """
        SELECT COUNT(*) as total_count,
               COUNT(CASE WHEN workflow_instance_name IS NULL OR workflow_instance_name = '' THEN 1 END) as null_workflow_name,
               COUNT(CASE WHEN instance_name IS NOT NULL AND instance_name != '' THEN 1 END) as has_instance_name
        FROM workflow_instance
        """
        
        stats = await self.conn.fetchrow(count_query)
        logger.info(f"📊 数据统计:")
        logger.info(f"  • 总记录数: {stats['total_count']}")
        logger.info(f"  • workflow_instance_name为空的记录: {stats['null_workflow_name']}")
        logger.info(f"  • 有instance_name值的记录: {stats['has_instance_name']}")
        
        if stats['null_workflow_name'] > 0:
            # 将instance_name的值复制到workflow_instance_name
            migration_query = """
            UPDATE workflow_instance 
            SET workflow_instance_name = instance_name,
                updated_at = NOW()
            WHERE (workflow_instance_name IS NULL OR workflow_instance_name = '') 
            AND instance_name IS NOT NULL 
            AND instance_name != ''
            """
            
            result = await self.conn.execute(migration_query)
            affected_rows = int(result.split()[-1]) if "UPDATE" in result else 0
            logger.info(f"✅ 成功迁移 {affected_rows} 条记录的数据")
        else:
            logger.info("ℹ️ 所有workflow_instance_name字段都已有值，无需迁移数据")
        
        return True
    
    async def verify_data_integrity(self):
        """验证数据完整性"""
        logger.info("🔍 验证数据完整性...")
        
        # 检查是否还有workflow_instance_name为空但instance_name有值的记录
        integrity_query = """
        SELECT workflow_instance_id, workflow_instance_name, instance_name
        FROM workflow_instance
        WHERE (workflow_instance_name IS NULL OR workflow_instance_name = '')
        AND (instance_name IS NOT NULL AND instance_name != '')
        LIMIT 5
        """
        
        problem_records = await self.conn.fetch(integrity_query)
        
        if problem_records:
            logger.error(f"❌ 发现 {len(problem_records)} 条数据完整性问题:")
            for record in problem_records:
                logger.error(f"  • ID: {record['workflow_instance_id']}, workflow_instance_name: '{record['workflow_instance_name']}', instance_name: '{record['instance_name']}'")
            return False
        
        logger.info("✅ 数据完整性检查通过")
        return True
    
    async def update_workflow_instance_name_constraint(self):
        """更新workflow_instance_name字段为非空约束"""
        logger.info("🔧 更新workflow_instance_name字段为非空约束...")
        
        try:
            # 首先检查是否还有NULL值
            null_check_query = "SELECT COUNT(*) FROM workflow_instance WHERE workflow_instance_name IS NULL"
            null_count = await self.conn.fetchval(null_check_query)
            
            if null_count > 0:
                logger.error(f"❌ 仍有 {null_count} 条记录的workflow_instance_name为空，无法设置非空约束")
                return False
            
            # 设置非空约束
            alter_query = "ALTER TABLE workflow_instance ALTER COLUMN workflow_instance_name SET NOT NULL"
            await self.conn.execute(alter_query)
            logger.info("✅ 成功将workflow_instance_name字段设置为非空约束")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 设置非空约束失败: {e}")
            return False
    
    async def check_field_dependencies(self):
        """检查instance_name字段的依赖关系"""
        logger.info("🔍 检查instance_name字段的依赖关系...")
        
        # 查找依赖的视图
        dependency_query = """
        SELECT DISTINCT dependent_ns.nspname as dependent_schema,
               dependent_view.relname as dependent_table,
               source_ns.nspname as source_schema,
               source_table.relname as source_table
        FROM pg_depend 
        JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid
        JOIN pg_class as dependent_view ON pg_rewrite.ev_class = dependent_view.oid
        JOIN pg_class as source_table ON pg_depend.refobjid = source_table.oid
        JOIN pg_attribute ON pg_depend.refobjid = pg_attribute.attrelid 
            AND pg_depend.refobjsubid = pg_attribute.attnum
        JOIN pg_namespace dependent_ns ON dependent_view.relnamespace = dependent_ns.oid
        JOIN pg_namespace source_ns ON source_table.relnamespace = source_ns.oid
        WHERE source_table.relname = 'workflow_instance'
        AND pg_attribute.attname = 'instance_name'
        AND dependent_view.relkind = 'v'
        """
        
        dependencies = await self.conn.fetch(dependency_query)
        
        if dependencies:
            logger.info("📋 发现以下视图依赖instance_name字段:")
            for dep in dependencies:
                logger.info(f"  • {dep['dependent_schema']}.{dep['dependent_table']}")
            return dependencies
        else:
            logger.info("ℹ️ 没有发现视图依赖instance_name字段")
            return []
    
    async def drop_dependent_views(self, dependencies):
        """删除依赖的视图"""
        if not dependencies:
            return True
        
        logger.info("🗑️ 删除依赖的视图...")
        
        try:
            for dep in dependencies:
                view_name = f"{dep['dependent_schema']}.{dep['dependent_table']}"
                drop_view_query = f"DROP VIEW IF EXISTS {view_name} CASCADE"
                await self.conn.execute(drop_view_query)
                logger.info(f"  ✅ 删除视图: {view_name}")
            
            logger.info("✅ 所有依赖视图删除完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 删除依赖视图失败: {e}")
            return False
    
    async def recreate_views_without_instance_name(self):
        """重新创建视图(不包含instance_name字段)"""
        logger.info("🔧 重新创建视图(去除instance_name字段)...")
        
        # 重新创建workflow_instance_detail_view视图
        recreate_view_query = """
        CREATE OR REPLACE VIEW workflow_instance_detail_view AS
        SELECT 
            wi.workflow_instance_id,
            wi.workflow_id,
            wi.workflow_base_id,
            wi.workflow_instance_name,
            wi.status,
            wi.input_data,
            wi.context_data,
            wi.output_data,
            wi.started_at,
            wi.completed_at,
            wi.error_message,
            wi.current_node_id,
            wi.retry_count,
            wi.execution_summary,
            wi.quality_metrics,
            wi.data_lineage,
            wi.output_summary,
            wi.created_at,
            wi.updated_at,
            w.name as workflow_name,
            w.description as workflow_description,
            u.username as executor_name,
            COALESCE(node_stats.total_nodes, 0) as total_nodes,
            COALESCE(node_stats.completed_nodes, 0) as completed_nodes,
            COALESCE(node_stats.failed_nodes, 0) as failed_nodes,
            COALESCE(node_stats.running_nodes, 0) as running_nodes
        FROM workflow_instance wi
        LEFT JOIN workflow w ON wi.workflow_id = w.workflow_id
        LEFT JOIN "user" u ON wi.executor_id = u.user_id
        LEFT JOIN (
            SELECT 
                ni.workflow_instance_id,
                COUNT(*) as total_nodes,
                COUNT(CASE WHEN ni.status = 'completed' THEN 1 END) as completed_nodes,
                COUNT(CASE WHEN ni.status = 'failed' THEN 1 END) as failed_nodes,
                COUNT(CASE WHEN ni.status IN ('running', 'pending') THEN 1 END) as running_nodes
            FROM node_instance ni
            WHERE ni.is_deleted = FALSE
            GROUP BY ni.workflow_instance_id
        ) node_stats ON wi.workflow_instance_id = node_stats.workflow_instance_id
        WHERE wi.is_deleted = FALSE
        """
        
        try:
            await self.conn.execute(recreate_view_query)
            logger.info("✅ 成功重新创建workflow_instance_detail_view视图")
            return True
            
        except Exception as e:
            logger.error(f"❌ 重新创建视图失败: {e}")
            return False
    
    async def remove_instance_name_field(self):
        """删除instance_name字段"""
        logger.info("🗑️ 删除instance_name字段...")
        
        try:
            # 1. 检查字段依赖关系
            dependencies = await self.check_field_dependencies()
            
            # 2. 删除依赖的视图
            if not await self.drop_dependent_views(dependencies):
                return False
            
            # 3. 删除字段
            drop_query = "ALTER TABLE workflow_instance DROP COLUMN IF EXISTS instance_name"
            await self.conn.execute(drop_query)
            logger.info("✅ 成功删除instance_name字段")
            
            # 4. 重新创建视图(不包含instance_name字段)
            if not await self.recreate_views_without_instance_name():
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 删除instance_name字段失败: {e}")
            return False
    
    async def verify_final_structure(self):
        """验证最终表结构"""
        logger.info("🔍 验证最终表结构...")
        
        query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'workflow_instance' 
        AND table_schema = 'public'
        AND column_name IN ('workflow_instance_name', 'instance_name')
        ORDER BY column_name
        """
        
        columns = await self.conn.fetch(query)
        
        logger.info("📋 最终字段结构:")
        for col in columns:
            nullable = "可空" if col['is_nullable'] == 'YES' else "非空"
            default = f" 默认值:{col['column_default']}" if col['column_default'] else ""
            logger.info(f"  • {col['column_name']}: {col['data_type']} [{nullable}]{default}")
        
        # 验证只有workflow_instance_name字段存在且为非空
        has_workflow_instance_name = any(col['column_name'] == 'workflow_instance_name' for col in columns)
        has_instance_name = any(col['column_name'] == 'instance_name' for col in columns)
        workflow_name_not_null = any(col['column_name'] == 'workflow_instance_name' and col['is_nullable'] == 'NO' for col in columns)
        
        if has_workflow_instance_name and not has_instance_name and workflow_name_not_null:
            logger.info("✅ 表结构迁移成功！")
            logger.info("  • workflow_instance_name字段存在且为非空")
            logger.info("  • instance_name字段已被删除")
            return True
        else:
            logger.error("❌ 表结构迁移未完成")
            if not has_workflow_instance_name:
                logger.error("  • workflow_instance_name字段不存在")
            if has_instance_name:
                logger.error("  • instance_name字段仍然存在")
            if not workflow_name_not_null:
                logger.error("  • workflow_instance_name字段仍然可空")
            return False
    
    async def run_migration(self):
        """执行完整的迁移过程"""
        logger.info("🚀 开始执行instance_name字段迁移...")
        logger.info("="*60)
        
        try:
            # 1. 连接数据库
            if not await self.connect_database():
                return False
            
            # 2. 检查当前表结构
            current_structure = await self.check_table_structure()
            if not current_structure:
                return False
            
            # 3. 备份和迁移数据
            if not await self.backup_and_migrate_data():
                return False
            
            # 4. 验证数据完整性
            if not await self.verify_data_integrity():
                return False
            
            # 5. 更新workflow_instance_name为非空约束
            if not await self.update_workflow_instance_name_constraint():
                return False
            
            # 6. 删除instance_name字段
            if not await self.remove_instance_name_field():
                return False
            
            # 7. 验证最终结构
            if not await self.verify_final_structure():
                return False
            
            logger.info("="*60)
            logger.info("🎉 迁移完成！instance_name字段已成功删除")
            logger.info("📝 迁移摘要:")
            logger.info("  • 数据已从instance_name迁移到workflow_instance_name")
            logger.info("  • workflow_instance_name字段已设置为非空约束")
            logger.info("  • instance_name字段已被删除")
            logger.info("  • 数据库结构现在与代码保持一致")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 迁移过程中发生异常: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False
        
        finally:
            await self.close_connection()


async def main():
    """主函数"""
    logger.info("🔄 workflow_instance表instance_name字段迁移工具")
    logger.info("版本: 1.0")
    logger.info("作用: 删除instance_name字段，统一使用workflow_instance_name")
    
    migrator = InstanceNameFieldMigration()
    success = await migrator.run_migration()
    
    if success:
        logger.info("✅ 迁移成功完成")
        return 0
    else:
        logger.error("❌ 迁移失败")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)