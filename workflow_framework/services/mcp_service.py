"""
MCP (Model Context Protocol) 服务
MCP Service for Tool Integration

注意：此文件已重构为使用数据库驱动的实现
Note: This file has been refactored to use database-driven implementation
"""

import uuid
import json
import asyncio
import httpx
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from loguru import logger

# 导入新的数据库驱动实现
from .database_mcp_service import DatabaseMCPService, database_mcp_service

# 保持向后兼容的类定义
class MCPServerConfig:
    """MCP服务器配置（向后兼容）"""
    
    def __init__(self, name: str, url: str, capabilities: List[str] = None,
                 auth: Dict[str, Any] = None, timeout: int = 30):
        self.name = name
        self.url = url.rstrip('/')
        self.capabilities = capabilities or []
        self.auth = auth or {}
        self.timeout = timeout
        self.is_active = True
        self.last_check = None
        self.error_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "capabilities": self.capabilities,
            "auth": self.auth,
            "timeout": self.timeout,
            "is_active": self.is_active,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "error_count": self.error_count
        }


class MCPTool:
    """MCP工具定义（向后兼容）"""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any],
                 server_name: str, server_url: str):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.server_name = server_name
        self.server_url = server_url
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为OpenAI tools格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "server_name": self.server_name,
            "server_url": self.server_url
        }


class MCPService:
    """MCP服务管理器（向后兼容包装器）"""
    
    def __init__(self):
        self._database_service = database_mcp_service
        # 为了向后兼容，保留一些属性
        self.servers = {}
        self.tools_cache = {}
        self.http_client = None
        self.is_initialized = False
    
    async def initialize(self):
        """初始化MCP服务"""
        await self._database_service.initialize()
        self.is_initialized = True
        logger.info("MCP服务已初始化（使用数据库驱动）")
    
    async def shutdown(self):
        """关闭MCP服务"""
        await self._database_service.shutdown()
        self.is_initialized = False
        logger.info("MCP服务已关闭（使用数据库驱动）")
    
    async def add_server(self, config: MCPServerConfig, user_id: Optional[uuid.UUID] = None) -> bool:
        """添加MCP服务器"""
        if not user_id:
            logger.warning("添加MCP服务器需要提供user_id，使用数据库驱动模式")
            return False
        
        server_config = {
            'name': config.name,
            'url': config.url,
            'description': f"兼容模式添加的服务器",
            'auth': config.auth
        }
        
        return await self._database_service.add_server(server_config, user_id)
    
    async def remove_server(self, server_name: str, user_id: Optional[uuid.UUID] = None) -> bool:
        """移除MCP服务器"""
        if not user_id:
            logger.warning("移除MCP服务器需要提供user_id，使用数据库驱动模式")
            return False
        
        return await self._database_service.remove_server(server_name, user_id)
    
    async def discover_tools(self, server_name: str) -> List[MCPTool]:
        """发现服务器工具"""
        tools_data = await self._database_service.discover_tools(server_name)
        
        # 转换为MCPTool对象以保持向后兼容
        mcp_tools = []
        for tool_data in tools_data:
            tool = MCPTool(
                name=tool_data['name'],
                description=tool_data.get('description', ''),
                parameters=tool_data.get('parameters', {}),
                server_name=tool_data['server_name'],
                server_url=tool_data['server_url']
            )
            mcp_tools.append(tool)
        
        return mcp_tools
    
    async def call_tool(self, tool_name: str, server_name: str, 
                       arguments: Dict[str, Any], user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """调用远程工具"""
        return await self._database_service.call_tool(tool_name, server_name, arguments, user_id)
    
    async def get_agent_tools(self, agent_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> List[MCPTool]:
        """获取Agent可用的工具列表"""
        try:
            # 使用新的数据库驱动方式
            tools_data = await self._database_service.get_agent_tools(agent_id, user_id)
            
            # 转换为MCPTool对象以保持向后兼容
            mcp_tools = []
            for tool_data in tools_data:
                tool = MCPTool(
                    name=tool_data['name'],
                    description=tool_data.get('description', ''),
                    parameters=tool_data.get('parameters', {}),
                    server_name=tool_data['server_name'],
                    server_url=tool_data['server_url']
                )
                mcp_tools.append(tool)
            
            logger.info(f"Agent {agent_id} 可用工具: {len(mcp_tools)} 个（数据库驱动模式）")
            return mcp_tools
            
        except Exception as e:
            logger.error(f"获取Agent工具列表失败: {agent_id}, 错误: {e}")
            return []
    
    def format_tools_for_openai(self, tools: Union[List[MCPTool], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """转换工具列表为OpenAI格式"""
        if not tools:
            return []
        
        # 检查是否是MCPTool对象列表
        if isinstance(tools[0], MCPTool):
            return [tool.to_openai_format() for tool in tools]
        else:
            # 使用数据库服务的格式化方法
            return self._database_service.format_tools_for_openai(tools)
    
    async def get_server_status(self, server_name: str, user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """获取服务器状态"""
        return await self._database_service.get_server_status(server_name, user_id)
    
    async def get_all_servers_status(self, user_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """获取所有服务器状态"""
        return await self._database_service.get_all_servers_status(user_id)
    
    def clear_tools_cache(self, server_name: str = None):
        """清除工具缓存（兼容方法，数据库驱动模式下无需缓存管理）"""
        logger.info("数据库驱动模式下无需手动清除缓存")


# 全局MCP服务实例（保持向后兼容）
mcp_service = MCPService()