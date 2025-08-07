"""
数据迁移脚本：将Agent的tool_config迁移到新的工具绑定系统
Data Migration Script: Migrate Agent tool_config to new tool binding system
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List
from loguru import logger
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.utils.database import db_manager, initialize_database
from backend.services.mcp_tool_service import mcp_tool_service
from backend.services.agent_tool_service import agent_tool_service


class MCPDataMigration:
    """MCP工具数据迁移器"""
    
    def __init__(self):
        self.migrated_agents = 0
        self.migrated_tools = 0
        self.failed_migrations = 0
        self.migration_log = []
    
    async def migrate_agent_tool_configs(self):
        """迁移Agent的tool_config到新的工具绑定系统"""
        logger.info("开始迁移Agent工具配置...")
        
        try:
            # 查询所有有tool_config的Agent
            agents_query = """
                SELECT agent_id, agent_name, tool_config, user_id
                FROM agent 
                WHERE tool_config IS NOT NULL 
                AND tool_config != '{}'::jsonb
                AND tool_config != 'null'::jsonb
                AND is_deleted = FALSE
            """
            
            agents = await db_manager.fetch_all(agents_query)
            logger.info(f"找到 {len(agents)} 个需要迁移的Agent")
            
            for agent in agents:
                await self._migrate_single_agent(agent)
                
            logger.info(f"Agent工具配置迁移完成: 成功 {self.migrated_agents} 个, 失败 {self.failed_migrations} 个")
            
        except Exception as e:
            logger.error(f"迁移Agent工具配置失败: {e}")
            raise
    
    async def _migrate_single_agent(self, agent: Dict[str, Any]):
        """迁移单个Agent的工具配置"""
        agent_id = agent['agent_id']
        agent_name = agent['agent_name']
        tool_config = agent['tool_config']
        user_id = agent['user_id']
        
        try:
            logger.info(f"迁移Agent: {agent_name} ({agent_id})")
            
            # 解析tool_config
            if isinstance(tool_config, str):
                config = json.loads(tool_config)
            else:
                config = tool_config
            
            # 检查是否是有效的工具配置
            if not isinstance(config, dict):
                logger.warning(f"Agent {agent_name} 的tool_config不是有效的字典格式，跳过")
                return
            
            # 尝试从配置中提取工具信息
            tools_to_bind = []
            
            # 处理不同格式的tool_config
            if 'tools' in config and isinstance(config['tools'], list):
                # 格式1: {"tools": ["tool1", "tool2"]}
                for tool_name in config['tools']:
                    if isinstance(tool_name, str):
                        tools_to_bind.append({
                            'tool_name': tool_name,
                            'priority': 5,
                            'max_calls_per_task': 5
                        })
            
            elif 'mcp_servers' in config:
                # 格式2: {"mcp_servers": {...}}
                mcp_servers = config['mcp_servers']
                if isinstance(mcp_servers, dict):
                    for server_name, server_config in mcp_servers.items():
                        if isinstance(server_config, dict) and 'tools' in server_config:
                            for tool_config in server_config['tools']:
                                if isinstance(tool_config, dict) and 'name' in tool_config:
                                    tools_to_bind.append({
                                        'tool_name': tool_config['name'],
                                        'server_name': server_name,
                                        'priority': tool_config.get('priority', 5),
                                        'max_calls_per_task': tool_config.get('max_calls', 5)
                                    })
            
            # 如果没有找到工具配置，记录并跳过
            if not tools_to_bind:
                logger.info(f"Agent {agent_name} 的tool_config中没有找到可迁移的工具，跳过")
                self.migration_log.append({
                    'agent_id': str(agent_id),
                    'agent_name': agent_name,
                    'status': 'skipped',
                    'reason': 'no_tools_found',
                    'original_config': config
                })
                return
            
            # 查找和绑定工具
            bound_tools = 0
            for tool_info in tools_to_bind:
                try:
                    # 查找用户的MCP工具
                    tool = await self._find_user_tool(user_id, tool_info)
                    
                    if tool:
                        # 创建工具绑定
                        binding_config = {
                            'is_enabled': True,
                            'priority': tool_info.get('priority', 5),
                            'max_calls_per_task': tool_info.get('max_calls_per_task', 5),
                            'custom_config': {}
                        }
                        
                        result = await agent_tool_service.bind_tool_to_agent(
                            agent_id=agent_id,
                            tool_id=uuid.UUID(tool['tool_id']),
                            user_id=user_id,
                            config=binding_config
                        )
                        
                        if result:
                            bound_tools += 1
                            logger.info(f"成功绑定工具 {tool_info['tool_name']} 到Agent {agent_name}")
                    else:
                        logger.warning(f"未找到工具 {tool_info['tool_name']} 在用户 {user_id} 的MCP工具中")
                        
                except Exception as e:
                    logger.error(f"绑定工具 {tool_info['tool_name']} 到Agent {agent_name} 失败: {e}")
            
            if bound_tools > 0:
                self.migrated_agents += 1
                self.migrated_tools += bound_tools
                
                # 备份原始配置然后清空tool_config
                await self._backup_and_clear_tool_config(agent_id, config)
                
                logger.info(f"Agent {agent_name} 迁移完成: 绑定了 {bound_tools} 个工具")
                
                self.migration_log.append({
                    'agent_id': str(agent_id),
                    'agent_name': agent_name,
                    'status': 'success',
                    'bound_tools': bound_tools,
                    'original_config': config
                })
            else:
                logger.warning(f"Agent {agent_name} 没有成功绑定任何工具")
                self.migration_log.append({
                    'agent_id': str(agent_id),
                    'agent_name': agent_name,
                    'status': 'no_tools_bound',
                    'original_config': config
                })
                
        except Exception as e:
            self.failed_migrations += 1
            logger.error(f"迁移Agent {agent_name} 失败: {e}")
            self.migration_log.append({
                'agent_id': str(agent_id),
                'agent_name': agent_name,
                'status': 'failed',
                'error': str(e),
                'original_config': tool_config
            })
    
    async def _find_user_tool(self, user_id: uuid.UUID, tool_info: Dict[str, Any]) -> Dict[str, Any]:
        """在用户的MCP工具中查找指定工具"""
        try:
            # 查询用户的MCP工具
            query = """
                SELECT tool_id, tool_name, server_name
                FROM mcp_tool_registry
                WHERE user_id = $1 
                AND is_tool_active = TRUE
                AND (tool_name = $2 OR tool_name ILIKE $3)
            """
            
            tool_name = tool_info['tool_name']
            # 使用模糊匹配来处理工具名称的变化
            pattern = f"%{tool_name}%"
            
            tools = await db_manager.fetch_all(query, user_id, tool_name, pattern)
            
            if tools:
                # 优先选择精确匹配的工具
                exact_match = None
                partial_match = None
                
                for tool in tools:
                    if tool['tool_name'] == tool_name:
                        exact_match = tool
                        break
                    elif not partial_match:
                        partial_match = tool
                
                return exact_match or partial_match
            
            return None
            
        except Exception as e:
            logger.error(f"查找用户工具失败: {e}")
            return None
    
    async def _backup_and_clear_tool_config(self, agent_id: uuid.UUID, original_config: Dict[str, Any]):
        """备份原始配置并清空tool_config字段"""
        try:
            # 创建备份记录
            backup_query = """
                INSERT INTO agent_tool_config_backup (
                    agent_id, original_tool_config, migrated_at
                ) VALUES ($1, $2, NOW())
                ON CONFLICT (agent_id) DO UPDATE SET
                    original_tool_config = EXCLUDED.original_tool_config,
                    migrated_at = EXCLUDED.migrated_at
            """
            
            await db_manager.execute(backup_query, agent_id, json.dumps(original_config))
            
            # 清空tool_config字段
            clear_query = """
                UPDATE agent 
                SET tool_config = NULL,
                    updated_at = NOW()
                WHERE agent_id = $1
            """
            
            await db_manager.execute(clear_query, agent_id)
            
            logger.info(f"Agent {agent_id} 的tool_config已备份并清空")
            
        except Exception as e:
            logger.error(f"备份和清空Agent {agent_id} 的tool_config失败: {e}")
    
    async def create_backup_table(self):
        """创建备份表存储原始的tool_config"""
        try:
            create_backup_table_sql = """
                CREATE TABLE IF NOT EXISTS agent_tool_config_backup (
                    agent_id UUID PRIMARY KEY,
                    original_tool_config JSONB NOT NULL,
                    migrated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_agent_tool_config_backup_migrated_at 
                ON agent_tool_config_backup(migrated_at);
            """
            
            await db_manager.execute(create_backup_table_sql)
            logger.info("备份表创建成功")
            
        except Exception as e:
            logger.error(f"创建备份表失败: {e}")
            raise
    
    async def generate_migration_report(self):
        """生成迁移报告"""
        report = {
            'summary': {
                'migrated_agents': self.migrated_agents,
                'migrated_tools': self.migrated_tools,
                'failed_migrations': self.failed_migrations,
                'total_processed': len(self.migration_log)
            },
            'details': self.migration_log
        }
        
        # 保存报告到文件
        import json
        from datetime import datetime
        
        report_filename = f"mcp_migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"迁移报告已保存到: {report_filename}")
            
        except Exception as e:
            logger.error(f"保存迁移报告失败: {e}")
        
        return report


async def main():
    """主函数"""
    try:
        logger.info("开始MCP工具数据迁移...")
        
        # 初始化数据库连接
        await initialize_database()
        logger.info("数据库连接初始化成功")
        
        # 创建迁移器
        migrator = MCPDataMigration()
        
        # 创建备份表
        await migrator.create_backup_table()
        
        # 执行迁移
        await migrator.migrate_agent_tool_configs()
        
        # 生成报告
        report = await migrator.generate_migration_report()
        
        logger.info("=== 迁移完成 ===")
        logger.info(f"成功迁移的Agent: {report['summary']['migrated_agents']}")
        logger.info(f"成功迁移的工具绑定: {report['summary']['migrated_tools']}")
        logger.info(f"失败的迁移: {report['summary']['failed_migrations']}")
        
        if report['summary']['failed_migrations'] > 0:
            logger.warning("存在失败的迁移，请检查迁移报告文件")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"数据迁移失败: {e}")
        return False
    
    finally:
        try:
            await db_manager.close()
        except:
            pass


if __name__ == "__main__":
    import asyncio
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)