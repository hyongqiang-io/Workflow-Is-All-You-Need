#!/usr/bin/env python3
"""
为工作流输出数据字段添加数据库索引
Add Database Indexes for Workflow Output Data Fields
"""

import asyncio
import sys
import os
from loguru import logger

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import get_database


class OutputDataIndexManager:
    """工作流输出数据索引管理器"""
    
    def __init__(self):
        self.db = None
    
    async def initialize(self):
        """初始化数据库连接"""
        try:
            self.db = get_database()
            logger.info("✅ 数据库连接初始化成功")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库连接初始化失败: {e}")
            return False
    
    async def add_workflow_output_columns(self):
        """为workflow_instance表添加新的输出数据列"""
        try:
            logger.info("📋 开始添加新的输出数据字段...")
            
            # 检查字段是否已存在
            check_columns_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'workflow_instance' 
            AND column_name IN ('execution_summary', 'quality_metrics', 'data_lineage', 'output_summary')
            """
            
            existing_columns = await self.db.fetch_all(check_columns_query)
            existing_column_names = [row['column_name'] for row in existing_columns]
            
            logger.info(f"📊 现有字段: {existing_column_names}")
            
            # 需要添加的字段
            columns_to_add = [
                ('execution_summary', 'JSONB', '执行摘要数据'),
                ('quality_metrics', 'JSONB', '质量评估指标'),
                ('data_lineage', 'JSONB', '数据血缘信息'),
                ('output_summary', 'JSONB', '结构化输出摘要')
            ]
            
            # 添加缺失的字段
            for column_name, column_type, description in columns_to_add:
                if column_name not in existing_column_names:
                    alter_query = f"""
                    ALTER TABLE workflow_instance 
                    ADD COLUMN {column_name} {column_type}
                    """
                    
                    comment_query = f"""
                    COMMENT ON COLUMN workflow_instance.{column_name} IS '{description}'
                    """
                    
                    try:
                        await self.db.execute(alter_query)
                        await self.db.execute(comment_query)
                        logger.info(f"✅ 添加字段成功: {column_name}")
                    except Exception as e:
                        logger.error(f"❌ 添加字段失败 {column_name}: {e}")
                        # 继续添加其他字段
                        continue
                else:
                    logger.info(f"⏭️ 字段已存在，跳过: {column_name}")
            
            logger.info("✅ 输出数据字段添加完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加输出数据字段异常: {e}")
            return False
    
    async def create_output_data_indexes(self):
        """创建输出数据相关的索引"""
        try:
            logger.info("📊 开始创建输出数据索引...")
            
            # 定义需要创建的索引
            indexes = [
                # 1. 执行结果类型索引 - 用于按结果类型筛选
                {
                    'name': 'idx_workflow_instance_result_type',
                    'table': 'workflow_instance', 
                    'definition': "USING GIN ((execution_summary->>'execution_result'->>'result_type'))",
                    'description': '执行结果类型索引'
                },
                
                # 2. 工作流状态和结果类型复合索引
                {
                    'name': 'idx_workflow_instance_status_result',
                    'table': 'workflow_instance',
                    'definition': "USING GIN (status, (execution_summary->>'execution_result'->>'result_type'))",
                    'description': '状态和结果类型复合索引'
                },
                
                # 3. 质量评估指标索引 - 用于按质量分数筛选
                {
                    'name': 'idx_workflow_instance_quality_score',
                    'table': 'workflow_instance',
                    'definition': "USING GIN ((quality_metrics->>'overall_quality_score'))",
                    'description': '整体质量评分索引'
                },
                
                # 4. 质量门禁状态索引
                {
                    'name': 'idx_workflow_instance_quality_gates',
                    'table': 'workflow_instance',
                    'definition': "USING GIN ((quality_metrics->>'quality_gates_passed'))",
                    'description': '质量门禁状态索引'
                },
                
                # 5. 数据来源索引 - 用于按输入来源筛选
                {
                    'name': 'idx_workflow_instance_input_sources',
                    'table': 'workflow_instance',
                    'definition': "USING GIN ((data_lineage->>'input_sources'))",
                    'description': '数据输入来源索引'
                },
                
                # 6. 执行统计索引 - 用于按节点数量筛选
                {
                    'name': 'idx_workflow_instance_execution_stats',
                    'table': 'workflow_instance',
                    'definition': "USING GIN (execution_summary->>'execution_stats')",
                    'description': '执行统计信息索引'
                },
                
                # 7. 创建时间和状态复合索引 - 优化时间范围查询
                {
                    'name': 'idx_workflow_instance_created_status',
                    'table': 'workflow_instance',
                    'definition': "USING BTREE (created_at DESC, status)",
                    'description': '创建时间和状态复合索引'
                },
                
                # 8. 完成时间和结果类型复合索引
                {
                    'name': 'idx_workflow_instance_completed_result',
                    'table': 'workflow_instance',
                    'definition': "USING BTREE (completed_at DESC) WHERE completed_at IS NOT NULL",
                    'description': '完成时间索引（部分索引）'
                },
                
                # 9. 工作流基础ID和状态复合索引 - 优化按工作流筛选
                {
                    'name': 'idx_workflow_instance_workflow_base_status',
                    'table': 'workflow_instance',
                    'definition': "USING BTREE (workflow_base_id, status, created_at DESC)",
                    'description': '工作流基础ID和状态复合索引'
                },
                
                # 10. 执行者和状态复合索引 - 优化按执行者筛选
                {
                    'name': 'idx_workflow_instance_executor_status',
                    'table': 'workflow_instance',
                    'definition': "USING BTREE (executor_id, status, created_at DESC)",
                    'description': '执行者和状态复合索引'
                }
            ]
            
            # 创建索引
            for index_info in indexes:
                try:
                    # 检查索引是否已存在
                    check_index_query = """
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = $1 AND indexname = $2
                    """
                    
                    existing_index = await self.db.fetch_one(
                        check_index_query, 
                        index_info['table'], 
                        index_info['name']
                    )
                    
                    if existing_index:
                        logger.info(f"⏭️ 索引已存在，跳过: {index_info['name']}")
                        continue
                    
                    # 创建索引
                    create_index_query = f"""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_info['name']} 
                    ON {index_info['table']} {index_info['definition']}
                    """
                    
                    logger.info(f"🔨 创建索引: {index_info['name']}")
                    logger.info(f"   - 表: {index_info['table']}")
                    logger.info(f"   - 定义: {index_info['definition']}")
                    logger.info(f"   - 描述: {index_info['description']}")
                    
                    await self.db.execute(create_index_query)
                    logger.info(f"✅ 索引创建成功: {index_info['name']}")
                    
                    # 添加索引注释
                    try:
                        comment_query = f"""
                        COMMENT ON INDEX {index_info['name']} IS '{index_info['description']}'
                        """
                        await self.db.execute(comment_query)
                    except Exception as comment_error:
                        logger.warning(f"⚠️ 添加索引注释失败 {index_info['name']}: {comment_error}")
                    
                except Exception as e:
                    logger.error(f"❌ 创建索引失败 {index_info['name']}: {e}")
                    # 继续创建其他索引
                    continue
            
            logger.info("✅ 输出数据索引创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建输出数据索引异常: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return False
    
    async def analyze_table_statistics(self):
        """分析表统计信息，优化查询计划"""
        try:
            logger.info("📈 开始分析表统计信息...")
            
            tables_to_analyze = [
                'workflow_instance',
                'node_instance', 
                'task_instance'
            ]
            
            for table_name in tables_to_analyze:
                try:
                    analyze_query = f"ANALYZE {table_name}"
                    await self.db.execute(analyze_query)
                    logger.info(f"✅ 表统计分析完成: {table_name}")
                except Exception as e:
                    logger.error(f"❌ 表统计分析失败 {table_name}: {e}")
            
            logger.info("✅ 表统计信息分析完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 分析表统计信息异常: {e}")
            return False
    
    async def show_index_summary(self):
        """显示索引创建摘要"""
        try:
            logger.info("📋 输出数据索引创建摘要:")
            logger.info("=" * 60)
            
            # 查询workflow_instance表的所有索引
            index_query = """
            SELECT 
                indexname,
                indexdef,
                pg_size_pretty(pg_relation_size(indexname::regclass)) as size
            FROM pg_indexes 
            WHERE tablename = 'workflow_instance'
            AND indexname LIKE 'idx_workflow_instance_%'
            ORDER BY indexname
            """
            
            indexes = await self.db.fetch_all(index_query)
            
            logger.info(f"📊 workflow_instance表相关索引 ({len(indexes)} 个):")
            for index in indexes:
                logger.info(f"  - {index['indexname']} ({index['size']})")
            
            # 查询表大小
            table_size_query = """
            SELECT 
                pg_size_pretty(pg_total_relation_size('workflow_instance')) as total_size,
                pg_size_pretty(pg_relation_size('workflow_instance')) as table_size
            """
            
            size_info = await self.db.fetch_one(table_size_query)
            if size_info:
                logger.info(f"📏 表大小信息:")
                logger.info(f"  - 表大小: {size_info['table_size']}")
                logger.info(f"  - 总大小(含索引): {size_info['total_size']}")
            
            logger.info("=" * 60)
            return True
            
        except Exception as e:
            logger.error(f"❌ 显示索引摘要异常: {e}")
            return False
    
    async def run_complete_setup(self):
        """运行完整的输出数据索引设置"""
        try:
            logger.info("🚀 开始工作流输出数据索引完整设置")
            logger.info("=" * 60)
            
            # 1. 初始化数据库连接
            if not await self.initialize():
                return False
            
            # 2. 添加新的输出数据字段
            if not await self.add_workflow_output_columns():
                logger.error("❌ 添加输出数据字段失败")
                return False
            
            # 3. 创建索引
            if not await self.create_output_data_indexes():
                logger.error("❌ 创建输出数据索引失败")
                return False
            
            # 4. 分析表统计信息
            if not await self.analyze_table_statistics():
                logger.warning("⚠️ 表统计分析失败，但不影响主要功能")
            
            # 5. 显示摘要
            await self.show_index_summary()
            
            logger.info("=" * 60)
            logger.info("🎉 工作流输出数据索引设置完成!")
            logger.info("✨ 新功能:")
            logger.info("  - 支持按执行结果类型筛选工作流")
            logger.info("  - 支持按质量评分筛选工作流") 
            logger.info("  - 支持按数据来源筛选工作流")
            logger.info("  - 优化了时间范围查询性能")
            logger.info("  - 优化了复合条件查询性能")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 完整设置过程异常: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return False


async def main():
    """主函数"""
    manager = OutputDataIndexManager()
    success = await manager.run_complete_setup()
    
    if success:
        logger.info("✅ 脚本执行成功")
        return 0
    else:
        logger.error("❌ 脚本执行失败")
        return 1


if __name__ == "__main__":
    import sys
    
    logger.info("开始执行工作流输出数据索引设置脚本...")
    exit_code = asyncio.run(main())
    sys.exit(exit_code)