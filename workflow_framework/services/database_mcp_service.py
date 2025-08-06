"""
重构的MCP服务 - 支持数据库驱动
Refactored MCP Service with Database Support
"""

import uuid
import json
import asyncio
import httpx
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from loguru import logger

from ..utils.database import db_manager
from ..utils.helpers import safe_json_dumps, safe_json_loads
from .mcp_tool_service import mcp_tool_service
from .agent_tool_service import agent_tool_service


class DatabaseMCPService:
    """数据库驱动的MCP服务管理器"""
    
    def __init__(self):
        self.http_client = None
        self.is_initialized = False
        self._health_check_interval = 300  # 5分钟
        self._health_check_task = None
    
    async def initialize(self):
        """初始化MCP服务"""
        if self.is_initialized:
            return
        
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.is_initialized = True
        
        # 启动健康检查任务
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("数据库驱动的MCP服务已初始化")
    
    async def shutdown(self):
        """关闭MCP服务"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
            
        self.is_initialized = False
        logger.info("数据库驱动的MCP服务已关闭")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._check_all_servers_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查循环出错: {e}")
    
    async def _check_all_servers_health(self):
        """检查所有服务器健康状态"""
        try:
            # 获取所有活跃的服务器
            query = """
                SELECT DISTINCT server_name, server_url
                FROM mcp_tool_registry 
                WHERE is_server_active = TRUE
                GROUP BY server_name, server_url
            """
            
            servers = await db_manager.fetch_all(query)
            
            for server in servers:
                server_name = server['server_name']
                server_url = server['server_url']
                
                # 检查服务器健康状态
                is_healthy = await self._test_server_health(server_url)
                
                # 更新服务器状态
                await self._update_server_health_status(server_name, is_healthy)
                
        except Exception as e:
            logger.error(f"批量健康检查失败: {e}")
    
    async def _test_server_health(self, server_url: str, timeout: int = 10) -> bool:
        """测试服务器健康状态"""
        try:
            if not self.http_client:
                await self.initialize()
            
            # 尝试访问健康检查端点
            response = await self.http_client.get(
                f"{server_url.rstrip('/')}/health",
                timeout=timeout
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"服务器 {server_url} 健康检查失败: {e}")
            return False
    
    async def _update_server_health_status(self, server_name: str, is_healthy: bool):
        """更新服务器健康状态"""
        try:
            # 确定新的状态
            new_status = 'healthy' if is_healthy else 'unhealthy'
            
            # 更新所有该服务器的工具记录
            update_query = """
                UPDATE mcp_tool_registry 
                SET 
                    server_status = $1,
                    last_health_check = NOW(),
                    is_server_active = $2
                WHERE server_name = $3
            """
            
            await db_manager.execute(update_query, new_status, is_healthy, server_name)
            
            if not is_healthy:
                logger.warning(f"MCP服务器 {server_name} 健康检查失败，已标记为不可用")
            
        except Exception as e:
            logger.error(f"更新服务器健康状态失败: {server_name}, 错误: {e}")
    
    async def get_agent_tools(self, agent_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """获取Agent可用的工具列表"""
        try:
            # 直接从数据库获取可用工具，不依赖绑定关系
            # 允许Agent访问系统工具（通过特定用户ID分享）
            system_user_id = 'e92d6bc0-3187-430d-96e0-450b6267949a'  # 系统用户ID
            
            tools_query = """
                SELECT 
                    tool_id, tool_name, server_name, server_url,
                    tool_description, tool_parameters,
                    is_tool_active, is_server_active, server_status
                FROM mcp_tool_registry
                WHERE (user_id = $1 OR user_id IS NULL)
                AND is_tool_active = true 
                AND is_server_active = true
                AND server_status != 'unhealthy'
                ORDER BY tool_name
            """
            
            raw_tools = await db_manager.fetch_all(tools_query, system_user_id)
            
            # 转换为兼容格式
            compatible_tools = []
            for tool in raw_tools:
                # 解析工具参数
                parameters = tool.get("tool_parameters", {})
                if isinstance(parameters, str):
                    try:
                        import json
                        parameters = json.loads(parameters)
                    except:
                        parameters = {}
                
                compatible_tool = {
                    "name": tool["tool_name"],
                    "description": tool.get("tool_description", ""),
                    "parameters": parameters,
                    "server_name": tool["server_name"],
                    "server_url": tool["server_url"]
                }
                compatible_tools.append(compatible_tool)
            
            logger.info(f"Agent {agent_id} 可用工具: {len(compatible_tools)} 个")
            if compatible_tools:
                logger.info(f"  工具列表: {[tool['name'] for tool in compatible_tools]}")
            
            return compatible_tools
            
        except Exception as e:
            logger.error(f"获取Agent工具列表失败: {agent_id}, 错误: {e}")
            return []
    
    async def call_tool(self, tool_name: str, server_name: str, 
                       arguments: Dict[str, Any], user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """调用远程工具"""
        start_time = datetime.utcnow()
        
        try:
            # 从数据库获取工具信息
            tool_query = """
                SELECT tool_id, server_url, tool_parameters, is_tool_active, is_server_active, server_status
                FROM mcp_tool_registry
                WHERE tool_name = $1 AND server_name = $2
                AND ($3::uuid IS NULL OR user_id = $3)
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            tool_info = await db_manager.fetch_one(tool_query, tool_name, server_name, user_id)
            
            if not tool_info:
                raise ValueError(f"工具 {tool_name} 不存在于服务器 {server_name}")
            
            if not tool_info['is_tool_active']:
                raise ValueError(f"工具 {tool_name} 已被禁用")
            
            if not tool_info['is_server_active']:
                raise ValueError(f"服务器 {server_name} 不可用")
            
            # 获取服务器URL和认证信息
            server_url = tool_info['server_url']
            
            if not self.http_client:
                await self.initialize()
            
            # 构建工具调用请求
            request_data = {
                "tool": tool_name,
                "arguments": arguments,
                "timestamp": start_time.isoformat()
            }
            
            # 获取认证头（如果有）
            headers = await self._get_server_auth_headers(server_name, user_id)
            
            logger.info(f"调用MCP工具: {tool_name} @ {server_name}")
            logger.debug(f"工具参数: {safe_json_dumps(arguments)}")
            
            # 发送工具调用请求
            response = await self.http_client.post(
                f"{server_url.rstrip('/')}/call",
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"工具调用失败: HTTP {response.status_code}, {response.text}")
            
            result = response.json()
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000  # 毫秒
            
            # 记录工具调用日志
            await self._log_tool_call(
                tool_id=tool_info['tool_id'],
                user_id=user_id,
                arguments=arguments,
                result=result,
                execution_time_ms=int(execution_time),
                success=True
            )
            
            logger.info(f"工具调用成功: {tool_name}, 耗时: {execution_time:.1f}ms")
            
            return {
                "success": True,
                "tool_name": tool_name,
                "server_name": server_name,
                "result": result,
                "execution_time_ms": int(execution_time),
                "timestamp": start_time.isoformat()
            }
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 记录失败的调用
            if 'tool_info' in locals() and tool_info:
                await self._log_tool_call(
                    tool_id=tool_info['tool_id'],
                    user_id=user_id,
                    arguments=arguments,
                    result={"error": str(e)},
                    execution_time_ms=int(execution_time),
                    success=False
                )
            
            logger.error(f"调用MCP工具失败: {tool_name} @ {server_name}, 错误: {e}")
            
            return {
                "success": False,
                "tool_name": tool_name,
                "server_name": server_name,
                "error": str(e),
                "execution_time_ms": int(execution_time),
                "timestamp": start_time.isoformat()
            }
    
    async def _get_server_auth_headers(self, server_name: str, user_id: Optional[uuid.UUID] = None) -> Dict[str, str]:
        """获取服务器认证头"""
        headers = {"Content-Type": "application/json"}
        
        try:
            # 从数据库获取认证配置
            auth_query = """
                SELECT auth_config
                FROM mcp_tool_registry
                WHERE server_name = $1 
                AND ($2::uuid IS NULL OR user_id = $2)
                AND auth_config IS NOT NULL
                LIMIT 1
            """
            
            auth_record = await db_manager.fetch_one(auth_query, server_name, user_id)
            
            if not auth_record or not auth_record['auth_config']:
                return headers
            
            auth_config = auth_record['auth_config']
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
            
        except Exception as e:
            logger.error(f"获取认证头失败: {server_name}, 错误: {e}")
        
        return headers
    
    async def _log_tool_call(self, tool_id: uuid.UUID, user_id: Optional[uuid.UUID],
                           arguments: Dict[str, Any], result: Dict[str, Any],
                           execution_time_ms: int, success: bool):
        """记录工具调用日志"""
        try:
            log_query = """
                INSERT INTO mcp_tool_call_log (
                    tool_id, user_id, arguments, result, execution_time_ms, success, called_at
                ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """
            
            await db_manager.execute(
                log_query,
                tool_id,
                user_id,
                json.dumps(arguments),
                json.dumps(result),
                execution_time_ms,
                success
            )
            
        except Exception as e:
            logger.error(f"记录工具调用日志失败: {e}")
    
    def format_tools_for_openai(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """转换工具列表为OpenAI格式"""
        openai_tools = []
        
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            }
            openai_tools.append(openai_tool)
        
        return openai_tools
    
    async def get_server_status(self, server_name: str, user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """获取服务器状态"""
        try:
            status_query = """
                SELECT 
                    server_name,
                    server_url,
                    server_status,
                    is_server_active,
                    last_health_check,
                    COUNT(CASE WHEN is_tool_active THEN 1 END) as active_tools_count,
                    COUNT(*) as total_tools_count
                FROM mcp_tool_registry
                WHERE server_name = $1
                AND ($2::uuid IS NULL OR user_id = $2)
                GROUP BY server_name, server_url, server_status, is_server_active, last_health_check
            """
            
            result = await db_manager.fetch_one(status_query, server_name, user_id)
            
            if not result:
                return {"status": "not_found"}
            
            return {
                "status": result['server_status'] or 'unknown',
                "name": result['server_name'],
                "url": result['server_url'],
                "is_active": result['is_server_active'],
                "last_check": result['last_health_check'].isoformat() if result['last_health_check'] else None,
                "active_tools_count": result['active_tools_count'],
                "total_tools_count": result['total_tools_count']
            }
            
        except Exception as e:
            logger.error(f"获取服务器状态失败: {server_name}, 错误: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_all_servers_status(self, user_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """获取所有服务器状态"""
        try:
            status_query = """
                SELECT 
                    server_name,
                    server_url,
                    server_status,
                    is_server_active,
                    last_health_check,
                    COUNT(CASE WHEN is_tool_active THEN 1 END) as active_tools_count,
                    COUNT(*) as total_tools_count
                FROM mcp_tool_registry
                WHERE ($1::uuid IS NULL OR user_id = $1)
                GROUP BY server_name, server_url, server_status, is_server_active, last_health_check
                ORDER BY server_name
            """
            
            results = await db_manager.fetch_all(status_query, user_id)
            
            status_list = []
            for result in results:
                status = {
                    "status": result['server_status'] or 'unknown',
                    "name": result['server_name'],
                    "url": result['server_url'],
                    "is_active": result['is_server_active'],
                    "last_check": result['last_health_check'].isoformat() if result['last_health_check'] else None,
                    "active_tools_count": result['active_tools_count'],
                    "total_tools_count": result['total_tools_count']
                }
                status_list.append(status)
            
            return status_list
            
        except Exception as e:
            logger.error(f"获取所有服务器状态失败: {e}")
            return []
    
    async def refresh_server_tools(self, server_name: str, user_id: uuid.UUID) -> Dict[str, Any]:
        """刷新服务器工具列表"""
        try:
            # 委托给mcp_tool_service处理
            result = await mcp_tool_service.rediscover_server_tools(server_name, user_id)
            return result
            
        except Exception as e:
            logger.error(f"刷新服务器工具失败: {server_name}, 错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "new_tools": 0,
                "updated_tools": 0
            }
    
    # 向后兼容方法
    async def discover_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """发现服务器工具（向后兼容）"""
        try:
            tools_query = """
                SELECT tool_name as name, tool_description as description, 
                       tool_parameters as parameters, server_name, server_url
                FROM mcp_tool_registry
                WHERE server_name = $1 AND is_tool_active = TRUE
                ORDER BY tool_name
            """
            
            tools = await db_manager.fetch_all(tools_query, server_name)
            
            return [dict(tool) for tool in tools]
            
        except Exception as e:
            logger.error(f"发现工具失败，服务器: {server_name}, 错误: {e}")
            return []
    
    async def add_server(self, server_config: Dict[str, Any], user_id: uuid.UUID) -> bool:
        """添加MCP服务器（向后兼容，委托给mcp_tool_service）"""
        try:
            await mcp_tool_service.add_mcp_server(
                server_name=server_config.get('name'),
                server_url=server_config.get('url'),
                server_description=server_config.get('description', ''),
                auth_config=server_config.get('auth', {}),
                user_id=user_id
            )
            return True
            
        except Exception as e:
            logger.error(f"添加MCP服务器失败: {e}")
            return False
    
    async def remove_server(self, server_name: str, user_id: uuid.UUID) -> bool:
        """移除MCP服务器（向后兼容，委托给mcp_tool_service）"""
        try:
            await mcp_tool_service.delete_server_tools(server_name, user_id)
            return True
            
        except Exception as e:
            logger.error(f"移除MCP服务器失败: {e}")
            return False


# 全局数据库驱动的MCP服务实例
database_mcp_service = DatabaseMCPService()

# 保持向后兼容性，仍然提供旧的服务实例
# 但实际上会使用新的数据库驱动实现
mcp_service = database_mcp_service