"""
MCP工具相关的数据模型
MCP Tools Data Models
"""

import uuid
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class MCPAuthType(str, Enum):
    """MCP认证类型"""
    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"


class MCPAuthConfig(BaseModel):
    """MCP认证配置"""
    type: MCPAuthType = Field(MCPAuthType.NONE, description="认证类型")
    token: Optional[str] = Field(None, description="Bearer token")
    key: Optional[str] = Field(None, description="API key")
    username: Optional[str] = Field(None, description="Basic auth用户名")
    password: Optional[str] = Field(None, description="Basic auth密码")


class MCPServerConfig(BaseModel):
    """MCP服务器配置"""
    name: str = Field(..., min_length=1, max_length=100, description="服务器名称")
    url: str = Field(..., description="服务器URL")
    capabilities: List[str] = Field(default_factory=list, description="服务器能力列表")
    auth: MCPAuthConfig = Field(default_factory=MCPAuthConfig, description="认证配置")
    timeout: int = Field(30, ge=1, le=300, description="超时时间（秒）")
    enabled: bool = Field(True, description="是否启用")


class MCPToolSelectionMode(str, Enum):
    """MCP工具选择模式"""
    AUTO = "auto"  # 自动选择
    MANUAL = "manual"  # 手动选择
    DISABLED = "disabled"  # 禁用工具调用


class MCPToolConfig(BaseModel):
    """MCP工具配置"""
    mcp_servers: List[MCPServerConfig] = Field(default_factory=list, description="MCP服务器列表")
    tool_selection: MCPToolSelectionMode = Field(MCPToolSelectionMode.AUTO, description="工具选择模式")
    max_tool_calls: int = Field(5, ge=0, le=20, description="最大工具调用次数")
    timeout: int = Field(30, ge=1, le=300, description="工具调用超时时间")
    allowed_tools: List[str] = Field(default_factory=list, description="允许的工具列表")
    blocked_tools: List[str] = Field(default_factory=list, description="禁用的工具列表")


class MCPToolCall(BaseModel):
    """MCP工具调用记录"""
    call_id: str = Field(..., description="调用ID")
    tool_name: str = Field(..., description="工具名称")
    server_name: str = Field(..., description="服务器名称")
    arguments: Dict[str, Any] = Field(..., description="调用参数")
    result: Optional[Dict[str, Any]] = Field(None, description="调用结果")
    success: bool = Field(False, description="是否成功")
    error_message: Optional[str] = Field(None, description="错误信息")
    duration_ms: Optional[int] = Field(None, description="执行时间（毫秒）")
    timestamp: str = Field(..., description="时间戳")


class MCPToolResponse(BaseModel):
    """MCP工具响应"""
    success: bool = Field(..., description="是否成功")
    tool_name: str = Field(..., description="工具名称")
    server_name: str = Field(..., description="服务器名称")
    result: Optional[Any] = Field(None, description="结果数据")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: str = Field(..., description="时间戳")
    duration_ms: Optional[int] = Field(None, description="执行时间")


class MCPServerStatus(BaseModel):
    """MCP服务器状态"""
    name: str = Field(..., description="服务器名称")
    url: str = Field(..., description="服务器URL")
    status: str = Field(..., description="状态：healthy/unhealthy/not_found")
    capabilities: List[str] = Field(default_factory=list, description="能力列表")
    is_active: bool = Field(True, description="是否激活")
    last_check: Optional[str] = Field(None, description="最后检查时间")
    error_count: int = Field(0, description="错误计数")
    tools_cached: int = Field(0, description="缓存的工具数量")


class MCPToolDefinition(BaseModel):
    """MCP工具定义"""
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    parameters: Dict[str, Any] = Field(..., description="参数定义")
    server_name: str = Field(..., description="所属服务器")
    server_url: str = Field(..., description="服务器URL")
    
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


# 用于Agent配置的tool_config字段的辅助函数
def create_default_mcp_config() -> Dict[str, Any]:
    """创建默认的MCP配置"""
    return MCPToolConfig().dict()


def validate_mcp_config(config: Dict[str, Any]) -> MCPToolConfig:
    """验证MCP配置"""
    return MCPToolConfig(**config)


def merge_mcp_config(base_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
    """合并MCP配置"""
    base = MCPToolConfig(**(base_config or {}))
    new = MCPToolConfig(**new_config)
    
    # 合并服务器配置（按名称去重）
    server_map = {server.name: server for server in base.mcp_servers}
    for server in new.mcp_servers:
        server_map[server.name] = server
    
    # 创建合并后的配置
    merged = MCPToolConfig(
        mcp_servers=list(server_map.values()),
        tool_selection=new.tool_selection,
        max_tool_calls=new.max_tool_calls,
        timeout=new.timeout,
        allowed_tools=list(set(base.allowed_tools + new.allowed_tools)),
        blocked_tools=list(set(base.blocked_tools + new.blocked_tools))
    )
    
    return merged.dict()