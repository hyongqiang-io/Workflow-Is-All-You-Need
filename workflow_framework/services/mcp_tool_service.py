"""
MCP工具服务 - 用户工具管理
MCP Tool Service for User Tool Management
"""

import asyncio
import uuid
import json
import httpx
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from loguru import logger

from ..utils.database import db_manager
from ..models.mcp import MCPServerConfig, MCPToolDefinition, MCPAuthConfig, MCPAuthType


class MCPToolService:
    """MCP工具管理服务 - 数据库驱动版本"""
    
    def __init__(self):
        self.http_client = None
        self.is_initialized = False
    
    async def initialize(self):
        """初始化服务"""
        if self.is_initialized:
            return
        
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.is_initialized = True
        logger.info("MCP工具服务已初始化")
    
    async def shutdown(self):
        """关闭服务"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        self.is_initialized = False
        logger.info("MCP工具服务已关闭")
    
    # ===============================
    # 用户工具管理 API
    # ===============================
    
    async def get_user_tools(self, user_id: uuid.UUID, 
                           server_name: Optional[str] = None,
                           tool_name: Optional[str] = None,
                           is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        """获取用户的MCP工具列表"""
        try:
            query = """
                SELECT * FROM user_mcp_tools_view
                WHERE user_id = $1
            """
            params = [user_id]
            param_count = 1
            
            if server_name:
                param_count += 1
                query += f" AND server_name = ${param_count}"
                params.append(server_name)
            
            if tool_name:
                param_count += 1
                query += f" AND tool_name ILIKE ${param_count}"
                params.append(f"%{tool_name}%")
            
            if is_active is not None:
                param_count += 1
                query += f" AND is_tool_active = ${param_count} AND is_server_active = ${param_count}"
                params.append(is_active)
            
            query += " ORDER BY server_name, tool_name"
            
            result = await db_manager.fetch_all(query, *params)
            
            # 转换为字典格式
            tools = []
            for row in result:
                tool = dict(row)
                # 确保JSON字段正确解析
                if tool.get('tool_parameters'):
                    if isinstance(tool['tool_parameters'], str):
                        tool['tool_parameters'] = json.loads(tool['tool_parameters'])
                tools.append(tool)
            
            logger.debug(f"获取用户 {user_id} 的工具数量: {len(tools)}")
            return tools
            
        except Exception as e:
            logger.error(f"获取用户工具失败: {e}")
            raise
    
    async def add_mcp_server(self, user_id: uuid.UUID, 
                           server_name: str,
                           server_url: str,
                           auth_config: Optional[Dict[str, Any]] = None,
                           server_description: Optional[str] = None) -> Dict[str, Any]:
        """添加MCP服务器并发现工具"""
        try:
            await self.initialize()
            
            # 1. 测试服务器连接
            logger.info(f"测试MCP服务器连接: {server_name} ({server_url})")
            server_status, discovered_tools = await self._discover_server_tools(
                server_url, auth_config or {}
            )
            
            if server_status != 'healthy':
                raise ValueError(f"无法连接到MCP服务器: {server_name}")
            
            if not discovered_tools:
                logger.warning(f"MCP服务器 {server_name} 未发现任何工具")
            
            # 2. 批量插入工具到数据库
            added_tools = []
            for tool in discovered_tools:
                try:
                    tool_id = await self._insert_tool(
                        user_id=user_id,
                        server_name=server_name,
                        server_url=server_url,
                        server_description=server_description,
                        auth_config=auth_config or {},
                        tool_name=tool['name'],
                        tool_description=tool['description'],
                        tool_parameters=tool['parameters']
                    )
                    added_tools.append({
                        'tool_id': str(tool_id),
                        'tool_name': tool['name'],
                        'server_name': server_name
                    })
                except Exception as tool_error:
                    logger.warning(f"插入工具 {tool['name']} 失败: {tool_error}")
                    continue
            
            logger.info(f"成功添加MCP服务器 {server_name}，发现 {len(added_tools)} 个工具")
            
            return {
                'server_name': server_name,
                'server_url': server_url,
                'server_status': server_status,
                'tools_discovered': len(discovered_tools),
                'tools_added': len(added_tools),
                'added_tools': added_tools
            }
            
        except Exception as e:
            logger.error(f"添加MCP服务器失败: {e}")
            raise
    
    async def update_tool(self, user_id: uuid.UUID, tool_id: uuid.UUID,
                         updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新工具配置"""
        try:
            # 验证工具所有权
            tool = await db_manager.fetch_one(
                "SELECT * FROM mcp_tool_registry WHERE tool_id = $1 AND user_id = $2 AND is_deleted = FALSE",
                tool_id, user_id
            )
            
            if not tool:
                raise ValueError(f"工具不存在或无权限访问: {tool_id}")
            
            # 构建更新SQL
            update_fields = []
            params = []
            param_count = 0
            
            allowed_fields = {
                'server_description', 'auth_config', 'timeout_seconds',
                'tool_description', 'is_server_active', 'is_tool_active'
            }
            
            for field, value in updates.items():
                if field in allowed_fields:
                    param_count += 1
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value)
            
            if not update_fields:
                raise ValueError("没有有效的更新字段")
            
            param_count += 1
            update_fields.append(f"updated_at = NOW()")
            params.extend([tool_id, user_id])
            
            query = f"""
                UPDATE mcp_tool_registry 
                SET {', '.join(update_fields)}
                WHERE tool_id = ${param_count} AND user_id = ${param_count + 1}
                RETURNING *
            """
            
            updated_tool = await db_manager.fetch_one(query, *params)
            
            logger.info(f"工具更新成功: {tool_id}")
            return dict(updated_tool)
            
        except Exception as e:
            logger.error(f"更新工具失败: {e}")
            raise
    
    async def delete_tool(self, user_id: uuid.UUID, tool_id: uuid.UUID) -> bool:
        """删除工具（软删除）"""
        try:
            result = await db_manager.execute(
                """
                UPDATE mcp_tool_registry 
                SET is_deleted = TRUE, updated_at = NOW()
                WHERE tool_id = $1 AND user_id = $2 AND is_deleted = FALSE
                """,
                tool_id, user_id
            )
            
            if result == "UPDATE 1":
                # 同时删除相关的Agent绑定
                await db_manager.execute(
                    "DELETE FROM agent_tool_binding WHERE tool_id = $1",
                    tool_id
                )
                logger.info(f"工具删除成功: {tool_id}")
                return True
            else:
                logger.warning(f"工具不存在或已删除: {tool_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除工具失败: {e}")
            raise
    
    async def delete_server_tools(self, user_id: uuid.UUID, server_name: str) -> int:
        """删除服务器的所有工具"""
        try:
            # 获取要删除的工具ID列表
            tool_ids = await db_manager.fetch_all(
                "SELECT tool_id FROM mcp_tool_registry WHERE user_id = $1 AND server_name = $2 AND is_deleted = FALSE",
                user_id, server_name
            )
            
            if not tool_ids:
                return 0
            
            # 批量软删除工具
            result = await db_manager.execute(
                """
                UPDATE mcp_tool_registry 
                SET is_deleted = TRUE, updated_at = NOW()
                WHERE user_id = $1 AND server_name = $2 AND is_deleted = FALSE
                """,
                user_id, server_name
            )
            
            # 删除相关的Agent绑定
            for tool_row in tool_ids:
                await db_manager.execute(
                    "DELETE FROM agent_tool_binding WHERE tool_id = $1",
                    tool_row['tool_id']
                )
            
            deleted_count = len(tool_ids)
            logger.info(f"删除服务器 {server_name} 的 {deleted_count} 个工具")
            return deleted_count
            
        except Exception as e:
            logger.error(f"删除服务器工具失败: {e}")
            raise
    
    async def rediscover_server_tools(self, user_id: uuid.UUID, server_name: str) -> Dict[str, Any]:
        """重新发现服务器工具"""
        try:
            # 获取服务器配置
            server_config = await db_manager.fetch_one(
                """
                SELECT DISTINCT server_url, auth_config, server_description
                FROM mcp_tool_registry 
                WHERE user_id = $1 AND server_name = $2 AND is_deleted = FALSE
                LIMIT 1
                """,
                user_id, server_name
            )
            
            if not server_config:
                raise ValueError(f"服务器不存在: {server_name}")
            
            # 重新发现工具
            server_url = server_config['server_url']
            auth_config = server_config['auth_config'] or {}
            
            logger.info(f"重新发现服务器工具: {server_name}")
            server_status, discovered_tools = await self._discover_server_tools(server_url, auth_config)
            
            # 获取现有工具
            existing_tools = await self.get_user_tools(user_id, server_name=server_name)
            existing_tool_names = {tool['tool_name'] for tool in existing_tools}
            
            # 添加新工具
            new_tools = []
            updated_tools = []
            
            for tool in discovered_tools:
                if tool['name'] not in existing_tool_names:
                    # 新工具，添加
                    tool_id = await self._insert_tool(
                        user_id=user_id,
                        server_name=server_name,
                        server_url=server_url,
                        server_description=server_config.get('server_description'),
                        auth_config=auth_config,
                        tool_name=tool['name'],
                        tool_description=tool['description'],
                        tool_parameters=tool['parameters']
                    )
                    new_tools.append(tool['name'])
                else:
                    # 已有工具，更新参数
                    await db_manager.execute(
                        """
                        UPDATE mcp_tool_registry 
                        SET tool_description = $1, tool_parameters = $2, 
                            last_tool_discovery = NOW(), updated_at = NOW()
                        WHERE user_id = $3 AND server_name = $4 AND tool_name = $5
                        """,
                        tool['description'], json.dumps(tool['parameters']),
                        user_id, server_name, tool['name']
                    )
                    updated_tools.append(tool['name'])
            
            # 更新服务器状态
            await db_manager.execute(
                """
                UPDATE mcp_tool_registry 
                SET server_status = $1, last_health_check = NOW(), error_count = 0
                WHERE user_id = $2 AND server_name = $3
                """,
                server_status, user_id, server_name
            )
            
            result = {
                'server_name': server_name,
                'server_status': server_status,
                'tools_discovered': len(discovered_tools),
                'new_tools': len(new_tools),
                'updated_tools': len(updated_tools),
                'new_tool_names': new_tools,
                'updated_tool_names': updated_tools
            }
            
            logger.info(f"重新发现完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"重新发现服务器工具失败: {e}")
            raise
    
    async def test_tool_call(self, user_id: uuid.UUID, tool_id: uuid.UUID,
                           test_arguments: Dict[str, Any]) -> Dict[str, Any]:
        """测试工具调用"""
        try:
            # 获取工具信息
            tool = await db_manager.fetch_one(
                """
                SELECT tool_name, server_name, server_url, auth_config, tool_parameters
                FROM mcp_tool_registry 
                WHERE tool_id = $1 AND user_id = $2 AND is_deleted = FALSE
                """,
                tool_id, user_id
            )
            
            if not tool:
                raise ValueError("工具不存在或无权限访问")
            
            # 调用工具
            start_time = datetime.now()
            success = False
            result_data = None
            error_message = None
            
            try:
                result_data = await self._call_tool(
                    tool['server_url'],
                    tool['auth_config'] or {},
                    tool['tool_name'],
                    test_arguments
                )
                success = True
                
            except Exception as call_error:
                error_message = str(call_error)
                logger.warning(f"工具调用失败: {call_error}")
            
            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # 记录调用日志
            await db_manager.execute(
                """
                INSERT INTO mcp_tool_call_log (
                    tool_id, user_id, call_arguments, call_result, 
                    success, error_message, execution_time_ms
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                tool_id, user_id, json.dumps(test_arguments),
                json.dumps(result_data) if result_data else None,
                success, error_message, execution_time_ms
            )
            
            # 更新工具使用统计
            if success:
                await db_manager.execute(
                    """
                    UPDATE mcp_tool_registry 
                    SET tool_usage_count = tool_usage_count + 1,
                        last_tool_call = NOW(),
                        success_rate = (
                            SELECT COALESCE(
                                AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) * 100, 
                                0
                            )
                            FROM mcp_tool_call_log 
                            WHERE tool_id = $1
                        )
                    WHERE tool_id = $1
                    """,
                    tool_id
                )
            
            return {
                'tool_name': tool['tool_name'],
                'server_name': tool['server_name'],
                'success': success,
                'execution_time_ms': execution_time_ms,
                'result': result_data,
                'error': error_message
            }
            
        except Exception as e:
            logger.error(f"测试工具调用失败: {e}")
            raise
    
    # ===============================
    # 内部辅助方法
    # ===============================
    
    async def _discover_server_tools(self, server_url: str, 
                                   auth_config: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
        """发现服务器工具"""
        try:
            await self.initialize()
            
            # 构建认证头
            headers = self._build_auth_headers(auth_config)
            
            # 健康检查
            try:
                health_response = await self.http_client.get(
                    f"{server_url}/health",
                    headers=headers,
                    timeout=10.0
                )
                if health_response.status_code != 200:
                    return 'unhealthy', []
            except:
                return 'error', []
            
            # 发现工具
            try:
                tools_response = await self.http_client.get(
                    f"{server_url}/tools",
                    headers=headers,
                    timeout=15.0
                )
                
                if tools_response.status_code == 200:
                    tools_data = tools_response.json()
                    tools = tools_data.get('tools', [])
                    
                    # 格式化工具定义
                    formatted_tools = []
                    for tool in tools:
                        formatted_tool = {
                            'name': tool.get('name', ''),
                            'description': tool.get('description', ''),
                            'parameters': tool.get('inputSchema', {})
                        }
                        formatted_tools.append(formatted_tool)
                    
                    return 'healthy', formatted_tools
                else:
                    return 'error', []
                    
            except Exception as tools_error:
                logger.warning(f"获取工具列表失败: {tools_error}")
                return 'healthy', []  # 服务器健康但无工具
                
        except Exception as e:
            logger.error(f"发现服务器工具失败: {e}")
            return 'error', []
    
    async def _call_tool(self, server_url: str, auth_config: Dict[str, Any],
                        tool_name: str, arguments: Dict[str, Any]) -> Any:
        """调用工具"""
        try:
            await self.initialize()
            
            headers = self._build_auth_headers(auth_config)
            
            call_data = {
                'name': tool_name,
                'arguments': arguments
            }
            
            response = await self.http_client.post(
                f"{server_url}/tools/call",
                json=call_data,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('content', [])
            else:
                raise Exception(f"工具调用失败: HTTP {response.status_code}, {response.text}")
                
        except Exception as e:
            logger.error(f"调用工具失败: {e}")
            raise
    
    def _build_auth_headers(self, auth_config: Dict[str, Any]) -> Dict[str, str]:
        """构建认证头"""
        headers = {"Content-Type": "application/json"}
        
        if not auth_config:
            return headers
        
        auth_type = auth_config.get("type", "")
        
        if auth_type == "bearer":
            token = auth_config.get("token")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            key = auth_config.get("key")
            if key:
                headers["X-API-Key"] = key
        elif auth_type == "basic":
            username = auth_config.get("username")
            password = auth_config.get("password")
            if username and password:
                import base64
                credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"
        
        return headers
    
    async def _insert_tool(self, user_id: uuid.UUID, server_name: str,
                          server_url: str, server_description: Optional[str],
                          auth_config: Dict[str, Any], tool_name: str,
                          tool_description: str, tool_parameters: Dict[str, Any]) -> uuid.UUID:
        """插入工具到数据库"""
        try:
            tool_id = uuid.uuid4()
            
            await db_manager.execute(
                """
                INSERT INTO mcp_tool_registry (
                    tool_id, user_id, server_name, server_url, server_description,
                    auth_config, tool_name, tool_description, tool_parameters,
                    server_status, last_health_check, last_tool_discovery
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
                """,
                tool_id, user_id, server_name, server_url, server_description,
                json.dumps(auth_config), tool_name, tool_description,
                json.dumps(tool_parameters), 'healthy'
            )
            
            return tool_id
            
        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e):
                # 工具已存在，获取现有ID
                existing = await db_manager.fetch_one(
                    "SELECT tool_id FROM mcp_tool_registry WHERE user_id = $1 AND server_name = $2 AND tool_name = $3",
                    user_id, server_name, tool_name
                )
                if existing:
                    return existing['tool_id']
            raise


# 创建全局实例
mcp_tool_service = MCPToolService()