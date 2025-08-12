"""
Agent工具绑定服务
Agent Tool Binding Service
"""

import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from ..utils.database import db_manager


class AgentToolService:
    """Agent工具绑定管理服务"""
    
    def __init__(self):
        pass
    
    # ===============================
    # Agent工具绑定管理
    # ===============================
    
    async def get_agent_tools(self, agent_id: uuid.UUID, 
                             user_id: Optional[uuid.UUID] = None,
                             is_enabled: Optional[bool] = None) -> List[Dict[str, Any]]:
        """获取Agent绑定的工具列表"""
        try:
            # 验证Agent存在（不需要验证user_id，Agent表没有user_id字段）
            agent = await db_manager.fetch_one(
                "SELECT agent_id FROM agent WHERE agent_id = $1 AND is_deleted = FALSE",
                agent_id
            )
            if not agent:
                logger.warning(f"Agent {agent_id} 不存在或已删除")
                return []
            
            query = """
                SELECT 
                    atb.binding_id,
                    atb.agent_id,
                    atb.tool_id,
                    atb.user_id as binding_user_id,
                    atb.is_active,
                    atb.binding_config,
                    atb.created_at as binding_created_at,
                    atb.updated_at as binding_updated_at,
                    -- 工具信息
                    mtr.server_name,
                    mtr.server_url,
                    mtr.tool_name,
                    mtr.tool_description,
                    mtr.tool_parameters,
                    mtr.is_server_active,
                    mtr.is_tool_active,
                    mtr.server_status,
                    mtr.tool_usage_count,
                    mtr.success_rate
                FROM agent_tool_binding atb
                JOIN mcp_tool_registry mtr ON atb.tool_id = mtr.tool_id
                WHERE atb.agent_id = $1 AND mtr.is_deleted = FALSE
            """
            params = [agent_id]
            param_count = 1
            
            # 不再按绑定的user_id过滤，因为Agent所有者应该能看到所有绑定到该Agent的工具
            
            if is_enabled is not None:
                param_count += 1
                query += f" AND atb.is_active = ${param_count}"
                params.append(is_enabled)
            
            query += " ORDER BY atb.created_at ASC"
            
            result = await db_manager.fetch_all(query, *params)
            
            # 转换为字典格式
            tools = []
            for row in result:
                tool = dict(row)
                # 解析JSON字段
                if tool.get('tool_parameters'):
                    if isinstance(tool['tool_parameters'], str):
                        tool['tool_parameters'] = json.loads(tool['tool_parameters'])
                if tool.get('binding_config'):
                    if isinstance(tool['binding_config'], str):
                        tool['binding_config'] = json.loads(tool['binding_config'])
                
                # 映射字段名以保持兼容性
                tool['is_enabled'] = tool.get('is_active', True)
                tool['priority'] = tool.get('binding_config', {}).get('priority', 0) if tool.get('binding_config') else 0
                tool['max_calls_per_task'] = tool.get('binding_config', {}).get('max_calls_per_task', 5) if tool.get('binding_config') else 5
                tool['timeout_override'] = tool.get('binding_config', {}).get('timeout_override') if tool.get('binding_config') else None
                tool['custom_config'] = tool.get('binding_config', {}) or {}
                
                tools.append(tool)
            
            logger.debug(f"获取Agent {agent_id} 的工具数量: {len(tools)}")
            return tools
            
        except Exception as e:
            logger.error(f"获取Agent工具失败: {e}")
            raise
    
    async def bind_tool_to_agent(self, agent_id: uuid.UUID, tool_id: uuid.UUID,
                                user_id: uuid.UUID, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """为Agent绑定工具"""
        try:
            # 验证工具存在且属于用户
            tool = await db_manager.fetch_one(
                "SELECT * FROM mcp_tool_registry WHERE tool_id = $1 AND user_id = $2 AND is_deleted = FALSE",
                tool_id, user_id
            )
            
            if not tool:
                raise ValueError("工具不存在或无权限访问")
            
            # 验证Agent存在
            agent = await db_manager.fetch_one(
                "SELECT agent_id FROM agent WHERE agent_id = $1 AND is_deleted = FALSE",
                agent_id
            )
            
            if not agent:
                raise ValueError("Agent不存在")
            
            # 检查是否已绑定
            existing = await db_manager.fetch_one(
                "SELECT binding_id FROM agent_tool_binding WHERE agent_id = $1 AND tool_id = $2",
                agent_id, tool_id
            )
            
            if existing:
                raise ValueError("工具已绑定到此Agent")
            
            # 处理配置参数
            binding_config = config or {}
            is_enabled = binding_config.get('is_enabled', True)
            priority = binding_config.get('priority', 0)
            max_calls_per_task = binding_config.get('max_calls_per_task', 5)
            timeout_override = binding_config.get('timeout_override')
            custom_config = binding_config.get('custom_config', {})
            
            # 插入绑定记录
            binding_id = uuid.uuid4()
            
            await db_manager.execute(
                """
                INSERT INTO agent_tool_binding (
                    binding_id, agent_id, tool_id, user_id, is_active,
                    binding_config
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                binding_id, agent_id, tool_id, user_id, is_enabled,
                json.dumps({
                    'priority': priority,
                    'max_calls_per_task': max_calls_per_task,
                    'timeout_override': timeout_override,
                    'custom_config': custom_config
                })
            )
            
            logger.info(f"工具绑定成功: Agent {agent_id} <-> Tool {tool_id}")
            
            # 返回绑定信息
            return {
                'binding_id': str(binding_id),
                'agent_id': str(agent_id),
                'tool_id': str(tool_id),
                'tool_name': tool['tool_name'],
                'server_name': tool['server_name'],
                'is_enabled': is_enabled,
                'priority': priority,
                'max_calls_per_task': max_calls_per_task
            }
            
        except Exception as e:
            logger.error(f"绑定工具到Agent失败: {e}")
            raise
    
    async def update_tool_binding(self, binding_id: uuid.UUID, user_id: uuid.UUID,
                                 updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新工具绑定配置"""
        try:
            # 验证绑定存在且用户有权限
            binding = await db_manager.fetch_one(
                """
                SELECT atb.*, mtr.tool_name, mtr.server_name
                FROM agent_tool_binding atb
                JOIN mcp_tool_registry mtr ON atb.tool_id = mtr.tool_id
                WHERE atb.binding_id = $1 AND atb.user_id = $2 AND mtr.is_deleted = FALSE
                """,
                binding_id, user_id
            )
            
            if not binding:
                raise ValueError("工具绑定不存在或无权限访问")
            
            # 构建更新SQL
            update_fields = []
            params = []
            param_count = 0
            
            # Handle updates to the simplified schema
            if 'is_enabled' in updates:
                param_count += 1
                update_fields.append(f"is_active = ${param_count}")
                params.append(updates['is_enabled'])
            
            if 'binding_config' in updates:
                param_count += 1
                update_fields.append(f"binding_config = ${param_count}")
                params.append(json.dumps(updates['binding_config']))
            
            # Handle legacy field mappings
            if any(field in updates for field in ['priority', 'max_calls_per_task', 'timeout_override', 'custom_config']):
                # Get current binding_config
                current_config = binding.get('binding_config', {})
                if isinstance(current_config, str):
                    current_config = json.loads(current_config)
                
                # Update config with new values
                if 'priority' in updates:
                    current_config['priority'] = updates['priority']
                if 'max_calls_per_task' in updates:
                    current_config['max_calls_per_task'] = updates['max_calls_per_task']
                if 'timeout_override' in updates:
                    current_config['timeout_override'] = updates['timeout_override']
                if 'custom_config' in updates:
                    current_config['custom_config'] = updates['custom_config']
                
                param_count += 1
                update_fields.append(f"binding_config = ${param_count}")
                params.append(json.dumps(current_config))
            
            if not update_fields:
                raise ValueError("没有有效的更新字段")
            
            param_count += 1
            update_fields.append("updated_at = NOW()")
            params.extend([binding_id, user_id])
            
            query = f"""
                UPDATE agent_tool_binding 
                SET {', '.join(update_fields)}
                WHERE binding_id = ${param_count} AND user_id = ${param_count + 1}
                RETURNING *
            """
            
            updated_binding = await db_manager.fetch_one(query, *params)
            
            logger.info(f"工具绑定更新成功: {binding_id}")
            
            result = dict(updated_binding)
            if result.get('custom_config'):
                if isinstance(result['custom_config'], str):
                    result['custom_config'] = json.loads(result['custom_config'])
            
            return result
            
        except Exception as e:
            logger.error(f"更新工具绑定失败: {e}")
            raise
    
    async def unbind_tool_from_agent(self, binding_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """解除Agent工具绑定"""
        try:
            result = await db_manager.execute(
                "DELETE FROM agent_tool_binding WHERE binding_id = $1 AND user_id = $2",
                binding_id, user_id
            )
            
            if result == "DELETE 1":
                logger.info(f"工具绑定解除成功: {binding_id}")
                return True
            else:
                logger.warning(f"工具绑定不存在或无权限: {binding_id}")
                return False
                
        except Exception as e:
            logger.error(f"解除工具绑定失败: {e}")
            raise
    
    async def batch_bind_tools(self, agent_id: uuid.UUID, user_id: uuid.UUID,
                              tool_bindings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量绑定工具到Agent"""
        try:
            # 验证Agent存在
            agent = await db_manager.fetch_one(
                "SELECT agent_id FROM agent WHERE agent_id = $1 AND is_deleted = FALSE",
                agent_id
            )
            
            if not agent:
                raise ValueError("Agent不存在")
            
            success_bindings = []
            failed_bindings = []
            
            for binding_config in tool_bindings:
                try:
                    tool_id = uuid.UUID(binding_config['tool_id'])
                    
                    result = await self.bind_tool_to_agent(
                        agent_id=agent_id,
                        tool_id=tool_id,
                        user_id=user_id,
                        config=binding_config.get('config', {})
                    )
                    
                    success_bindings.append(result)
                    
                except Exception as bind_error:
                    failed_bindings.append({
                        'tool_id': binding_config.get('tool_id'),
                        'error': str(bind_error)
                    })
                    continue
            
            logger.info(f"批量绑定完成: 成功 {len(success_bindings)}, 失败 {len(failed_bindings)}")
            
            return {
                'agent_id': str(agent_id),
                'total_requested': len(tool_bindings),
                'successful_bindings': len(success_bindings),
                'failed_bindings': len(failed_bindings),
                'success_details': success_bindings,
                'failure_details': failed_bindings
            }
            
        except Exception as e:
            logger.error(f"批量绑定工具失败: {e}")
            raise
    
    # ===============================
    # Agent工具配置生成 (替代tool_config)
    # ===============================
    
    async def get_agent_tool_config(self, agent_id: uuid.UUID) -> Dict[str, Any]:
        """获取Agent的工具配置 (用于替代tool_config字段)"""
        try:
            # 使用视图获取配置
            config_data = await db_manager.fetch_one(
                "SELECT * FROM agent_tool_config_view WHERE agent_id = $1",
                agent_id
            )
            
            if not config_data:
                # Agent存在但没有绑定工具
                return {
                    'tool_selection': 'auto',
                    'max_tool_calls': 5,
                    'timeout': 30,
                    'enabled_tools': [],
                    'tool_count': 0
                }
            
            result = dict(config_data)
            
            # 解析JSON配置
            computed_config = result.get('computed_tool_config', {})
            if isinstance(computed_config, str):
                computed_config = json.loads(computed_config)
            
            # 添加统计信息
            computed_config['tool_count'] = result.get('active_tool_count', 0)
            computed_config['total_bound_tools'] = result.get('total_bound_tools', 0)
            
            return computed_config
            
        except Exception as e:
            logger.error(f"获取Agent工具配置失败: {e}")
            raise
    
    async def get_agent_tools_for_execution(self, agent_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取Agent可用的工具列表 (用于任务执行)"""
        try:
            # 获取启用的工具，按优先级排序
            tools = await self.get_agent_tools(agent_id, is_enabled=True)
            
            # 筛选活跃且健康的工具
            execution_tools = []
            for tool in tools:
                if (tool.get('is_server_active') and 
                    tool.get('is_tool_active') and 
                    tool.get('server_status') == 'healthy'):
                    
                    execution_tool = {
                        'tool_id': tool['tool_id'],
                        'tool_name': tool['tool_name'],
                        'server_name': tool['server_name'],
                        'server_url': tool['server_url'],
                        'description': tool['tool_description'],
                        'parameters': tool['tool_parameters'],
                        'max_calls': tool['max_calls_per_task'],
                        'timeout': tool.get('timeout_override') or 30,
                        'priority': tool['priority'],
                        'binding_config': tool.get('custom_config', {})
                    }
                    execution_tools.append(execution_tool)
            
            logger.debug(f"Agent {agent_id} 可用工具数量: {len(execution_tools)}")
            return execution_tools
            
        except Exception as e:
            logger.error(f"获取Agent执行工具失败: {e}")
            raise
    
    # ===============================
    # 工具调用统计更新
    # ===============================
    
    async def record_tool_call(self, binding_id: uuid.UUID, success: bool,
                              execution_time_ms: Optional[int] = None) -> None:
        """记录工具调用统计"""
        try:
            if success:
                await db_manager.execute(
                    """
                    UPDATE agent_tool_binding 
                    SET total_calls = total_calls + 1,
                        successful_calls = successful_calls + 1,
                        last_called = NOW(),
                        avg_execution_time = CASE 
                            WHEN total_calls > 0 THEN 
                                (avg_execution_time * total_calls + COALESCE($2, 0)) / (total_calls + 1)
                            ELSE COALESCE($2, 0)
                        END
                    WHERE binding_id = $1
                    """,
                    binding_id, execution_time_ms / 1000.0 if execution_time_ms else None
                )
            else:
                await db_manager.execute(
                    """
                    UPDATE agent_tool_binding 
                    SET total_calls = total_calls + 1,
                        last_called = NOW()
                    WHERE binding_id = $1
                    """,
                    binding_id
                )
            
            logger.debug(f"工具调用统计更新: {binding_id}, 成功: {success}")
            
        except Exception as e:
            logger.error(f"记录工具调用统计失败: {e}")
            # 不抛出异常，统计失败不应影响主流程
    
    # ===============================
    # 工具管理辅助方法
    # ===============================
    
    async def get_popular_tools(self, user_id: Optional[uuid.UUID] = None,
                               limit: int = 10) -> List[Dict[str, Any]]:
        """获取热门工具列表"""
        try:
            query = """
                SELECT 
                    mtr.tool_name,
                    mtr.server_name,
                    mtr.tool_description,
                    mtr.tool_usage_count,
                    mtr.success_rate,
                    COUNT(atb.binding_id) as bound_agents_count
                FROM mcp_tool_registry mtr
                LEFT JOIN agent_tool_binding atb ON mtr.tool_id = atb.tool_id AND atb.is_enabled = TRUE
                WHERE mtr.is_deleted = FALSE AND mtr.is_tool_active = TRUE
            """
            params = []
            
            if user_id:
                query += " AND mtr.user_id = $1"
                params.append(user_id)
            
            query += f"""
                GROUP BY mtr.tool_id, mtr.tool_name, mtr.server_name, 
                         mtr.tool_description, mtr.tool_usage_count, mtr.success_rate
                ORDER BY mtr.tool_usage_count DESC, bound_agents_count DESC
                LIMIT {limit}
            """
            
            result = await db_manager.fetch_all(query, *params)
            return [dict(row) for row in result]
            
        except Exception as e:
            logger.error(f"获取热门工具失败: {e}")
            raise
    
    async def get_agent_tool_usage_stats(self, agent_id: uuid.UUID) -> Dict[str, Any]:
        """获取Agent工具使用统计"""
        try:
            stats = await db_manager.fetch_one(
                """
                SELECT 
                    COUNT(*) as total_bound_tools,
                    SUM(CASE WHEN is_enabled = TRUE THEN 1 ELSE 0 END) as enabled_tools,
                    SUM(total_calls) as total_tool_calls,
                    SUM(successful_calls) as successful_tool_calls,
                    AVG(CASE WHEN total_calls > 0 THEN successful_calls::float / total_calls ELSE 0 END) * 100 as avg_success_rate,
                    MAX(last_called) as last_tool_call
                FROM agent_tool_binding
                WHERE agent_id = $1
                """,
                agent_id
            )
            
            if not stats:
                return {
                    'total_bound_tools': 0,
                    'enabled_tools': 0,
                    'total_tool_calls': 0,
                    'successful_tool_calls': 0,
                    'avg_success_rate': 0.0,
                    'last_tool_call': None
                }
            
            return dict(stats)
            
        except Exception as e:
            logger.error(f"获取Agent工具统计失败: {e}")
            raise


# 创建全局实例
agent_tool_service = AgentToolService()