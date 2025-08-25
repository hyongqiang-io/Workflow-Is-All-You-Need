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
            
            # 智能URL映射：如果是自己的公网IP，使用本地地址
            test_url = server_url
            if "106.54.12.39" in server_url:
                test_url = server_url.replace("106.54.12.39", "autolabflow.online")
                logger.info(f"🌐 [HEALTH-CHECK] 检测到公网IP，映射为本地地址")
                logger.info(f"   - 原始URL: {server_url}")
                logger.info(f"   - 映射URL: {test_url}")
            
            # 尝试访问健康检查端点
            logger.debug(f"🏥 [HEALTH-CHECK] 测试服务器健康: {test_url}")
            response = await self.http_client.get(
                f"{test_url.rstrip('/')}/health",
                timeout=timeout
            )
            
            is_healthy = response.status_code == 200
            logger.info(f"🏥 [HEALTH-CHECK] 服务器 {server_url} 健康状态: {'✅健康' if is_healthy else '❌不健康'}")
            
            return is_healthy
            
        except Exception as e:
            logger.warning(f"🏥 [HEALTH-CHECK] 服务器 {server_url} 健康检查失败: {e}")
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
            logger.info(f"🔍 [DB-MCP] 查询Agent工具")
            logger.info(f"   - Agent ID: {agent_id}")
            logger.info(f"   - User ID: {user_id}")
            
            # 基于Agent工具绑定表查询，获取实际绑定到该Agent的工具
            tools_query = """
                SELECT 
                    mtr.tool_id, mtr.tool_name, mtr.server_name, mtr.server_url,
                    mtr.tool_description, mtr.tool_parameters,
                    mtr.is_tool_active, mtr.is_server_active, mtr.server_status,
                    atb.is_active as binding_active
                FROM mcp_tool_registry mtr
                JOIN agent_tool_binding atb ON mtr.tool_id = atb.tool_id
                WHERE atb.agent_id = $1 
                AND atb.is_active = true
                AND mtr.is_tool_active = true 
                AND mtr.is_server_active = true
                AND mtr.server_status != 'unhealthy'
                AND mtr.is_deleted = false
                ORDER BY mtr.tool_name
            """
            
            logger.info(f"🔍 [DB-MCP] 执行查询SQL")
            logger.info(f"   - 查询条件: Agent绑定激活, 工具激活, 服务器激活, 非unhealthy状态")
            
            raw_tools = await db_manager.fetch_all(tools_query, agent_id)
            
            logger.info(f"🔍 [DB-MCP] 查询结果")
            logger.info(f"   - 原始结果数量: {len(raw_tools)}")
            
            for i, tool in enumerate(raw_tools):
                logger.info(f"   - 工具 {i+1}: {tool['tool_name']} @ {tool['server_name']}")
                logger.info(f"     * 工具激活: {tool['is_tool_active']}")
                logger.info(f"     * 服务器激活: {tool['is_server_active']}")
                logger.info(f"     * 服务器状态: {tool['server_status']}")
                logger.info(f"     * 绑定激活: {tool['binding_active']}")
            
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
                
                logger.info(f"✅ [DB-MCP] 工具转换完成: {compatible_tool['name']}")
            
            logger.info(f"Agent {agent_id} 可用工具: {len(compatible_tools)} 个")
            if compatible_tools:
                logger.info(f"  工具列表: {[tool['name'] for tool in compatible_tools]}")
            
            logger.info(f"🎯 [DB-MCP] 最终返回工具数量: {len(compatible_tools)}")
            return compatible_tools
            
        except Exception as e:
            logger.error(f"❌ [DB-MCP] 获取Agent工具失败: {e}")
            logger.error(f"   - Agent ID: {agent_id}")
            import traceback
            logger.error(f"   - 错误详情: {traceback.format_exc()}")
            return []
    
    async def call_tool(self, tool_name: str, server_name: str, 
                       arguments: Dict[str, Any], user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """调用远程工具"""
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"🔧 [TOOL-CALL] 开始调用MCP工具")
            logger.info(f"   - 工具名称: {tool_name}")
            logger.info(f"   - 服务器: {server_name}")
            logger.info(f"   - 调用用户: {user_id or '系统/Agent调用'}")
            
            # 从数据库获取工具信息 - 移除严格的用户过滤以支持跨用户工具访问
            tool_query = """
                SELECT tool_id, user_id as tool_owner, server_url, tool_parameters, 
                       is_tool_active, is_server_active, server_status
                FROM mcp_tool_registry
                WHERE tool_name = $1 AND server_name = $2
                AND is_deleted = false
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            logger.debug(f"   - 执行工具查询: {tool_query}")
            tool_info = await db_manager.fetch_one(tool_query, tool_name, server_name)
            
            if not tool_info:
                logger.warning(f"   ❌ 未找到工具: {tool_name} @ {server_name}")
                raise ValueError(f"工具 {tool_name} 不存在于服务器 {server_name}")
            
            # 记录工具权限信息
            tool_owner = tool_info['tool_owner']
            logger.info(f"   - 工具所有者: {tool_owner}")
            if user_id and tool_owner != user_id:
                logger.info(f"   ⚠️ 跨用户工具访问: 调用者({user_id}) != 工具所有者({tool_owner})")
            elif not user_id:
                logger.info(f"   🤖 系统/Agent调用: 跳过用户权限验证")
            
            if not tool_info['is_tool_active']:
                logger.warning(f"   ❌ 工具已被禁用: {tool_name}")
                raise ValueError(f"工具 {tool_name} 已被禁用")
            
            if not tool_info['is_server_active']:
                logger.warning(f"   ❌ 服务器不可用: {server_name}")
                raise ValueError(f"服务器 {server_name} 不可用")
            
            if tool_info['server_status'] == 'unhealthy':
                logger.warning(f"   ❌ 服务器状态不健康: {server_name} ({tool_info['server_status']})")
                raise ValueError(f"服务器 {server_name} 状态不健康")
            
            logger.info(f"   ✅ 工具权限验证通过")
            
            # 获取服务器URL和认证信息
            server_url = tool_info['server_url']
            
            # 智能URL映射：处理公网IP访问问题
            call_url = server_url
            if "106.54.12.39" in server_url:
                call_url = server_url.replace("106.54.12.39", "autolabflow.online")
                logger.info(f"🌐 [TOOL-CALL] 检测到公网IP，映射为本地地址")
                logger.info(f"   - 原始URL: {server_url}")
                logger.info(f"   - 调用URL: {call_url}")
            
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
            
            logger.info(f"   🚀 开始执行工具调用")
            logger.debug(f"   - 工具参数: {safe_json_dumps(arguments)}")
            logger.debug(f"   - 调用地址: {call_url}")
            
            # 发送工具调用请求
            response = await self.http_client.post(
                f"{call_url.rstrip('/')}/call",
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"工具调用失败: HTTP {response.status_code}, {response.text}")
            
            result = response.json()
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000  # 毫秒
            
            logger.info(f"   ✅ 工具调用成功")
            logger.info(f"   - 耗时: {execution_time:.1f}ms")
            logger.info(f"   - 调用者: {user_id or 'Agent系统'}")
            logger.info(f"   - 工具所有者: {tool_owner}")
            
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
            
            logger.error(f"   ❌ MCP工具调用失败")
            logger.error(f"   - 工具: {tool_name} @ {server_name}")
            logger.error(f"   - 调用者: {user_id or 'Agent系统'}")
            logger.error(f"   - 错误: {e}")
            if 'tool_info' in locals() and tool_info:
                logger.error(f"   - 工具所有者: {tool_info.get('tool_owner', '未知')}")
            
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
            # 从数据库获取认证配置 - 移除用户过滤以支持跨用户工具访问
            auth_query = """
                SELECT auth_config
                FROM mcp_tool_registry
                WHERE server_name = $1 
                AND auth_config IS NOT NULL
                AND is_deleted = false
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            auth_record = await db_manager.fetch_one(auth_query, server_name)
            
            if not auth_record or not auth_record['auth_config']:
                logger.debug(f"   - 服务器 {server_name} 无认证配置，使用默认头")
                return headers
            
            auth_config = auth_record['auth_config']
            
            # 确保auth_config是字典格式
            if isinstance(auth_config, str):
                try:
                    import json
                    auth_config = json.loads(auth_config)
                except json.JSONDecodeError:
                    logger.warning(f"   - 无效的认证配置格式: {server_name}")
                    return headers
            
            auth_type = auth_config.get("type", "")
            logger.debug(f"   - 认证类型: {auth_type}")
            
            if auth_type == "bearer":
                token = auth_config.get("token")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    logger.debug(f"   - 添加Bearer认证")
            elif auth_type == "api_key":
                key = auth_config.get("key")
                if key:
                    headers["X-API-Key"] = key
                    logger.debug(f"   - 添加API Key认证")
            elif auth_type == "basic":
                username = auth_config.get("username")
                password = auth_config.get("password")
                if username and password:
                    import base64
                    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
                    headers["Authorization"] = f"Basic {credentials}"
                    logger.debug(f"   - 添加Basic认证")
            
        except Exception as e:
            logger.error(f"   ❌ 获取认证头失败: {server_name}, 错误: {e}")
        
        return headers
    
    async def _log_tool_call(self, tool_id: uuid.UUID, user_id: Optional[uuid.UUID],
                           arguments: Dict[str, Any], result: Dict[str, Any],
                           execution_time_ms: int, success: bool):
        """记录工具调用日志 - 已禁用"""
        # 不进行日志记录，避免数据库表依赖
        pass
    
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