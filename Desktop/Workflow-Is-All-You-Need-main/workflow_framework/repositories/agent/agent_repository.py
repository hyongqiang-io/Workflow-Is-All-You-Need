"""
Agent数据访问层
Agent Repository
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..base import BaseRepository
from ...models.agent import Agent, AgentCreate, AgentUpdate
from ...utils.helpers import now_utc


class AgentRepository(BaseRepository[Agent]):
    """Agent数据访问层"""
    
    def __init__(self):
        super().__init__("agent")
    
    async def create_agent(self, agent_data: AgentCreate) -> Optional[Dict[str, Any]]:
        """创建Agent"""
        try:
            # 检查Agent名称是否已存在
            if await self.agent_name_exists(agent_data.agent_name):
                raise ValueError(f"Agent名称 '{agent_data.agent_name}' 已存在")
            
            # 准备数据
            data = {
                "agent_id": uuid.uuid4(),
                "agent_name": agent_data.agent_name,
                "description": agent_data.description,
                "base_url": agent_data.base_url,
                "api_key": agent_data.api_key,
                "model_name": agent_data.model_name,
                "tool_config": agent_data.tool_config,
                "parameters": agent_data.parameters,
                "is_autonomous": agent_data.is_autonomous,
                "created_at": now_utc(),
                "updated_at": now_utc(),
                "is_deleted": False
            }
            
            result = await self.create(data)
            return result
        except Exception as e:
            logger.error(f"创建Agent失败: {e}")
            raise
    
    async def get_agent_by_id(self, agent_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取Agent"""
        return await self.get_by_id(agent_id, "agent_id")
    
    async def get_agent_by_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取Agent"""
        try:
            query = "SELECT * FROM agent WHERE agent_name = $1 AND is_deleted = FALSE"
            result = await self.db.fetch_one(query, agent_name)
            return result
        except Exception as e:
            logger.error(f"根据名称获取Agent失败: {e}")
            raise
    
    async def update_agent(self, agent_id: uuid.UUID, agent_data: AgentUpdate) -> Optional[Dict[str, Any]]:
        """更新Agent"""
        try:
            # 检查Agent是否存在
            existing_agent = await self.get_by_id(agent_id, "agent_id")
            if not existing_agent:
                raise ValueError(f"Agent {agent_id} 不存在")
            
            # 准备更新数据
            update_data = {}
            
            if agent_data.agent_name is not None:
                if agent_data.agent_name != existing_agent['agent_name']:
                    if await self.agent_name_exists(agent_data.agent_name):
                        raise ValueError(f"Agent名称 '{agent_data.agent_name}' 已存在")
                update_data["agent_name"] = agent_data.agent_name
            
            # 其他字段
            for field in ['description', 'base_url', 'api_key', 'model_name', 
                         'tool_config', 'parameters', 'is_autonomous', 'capabilities']:
                value = getattr(agent_data, field, None)
                if value is not None:
                    update_data[field] = value
            
            if not update_data:
                return existing_agent
            
            result = await self.update(agent_id, update_data, "agent_id")
            return result
        except Exception as e:
            logger.error(f"更新Agent失败: {e}")
            raise
    
    async def delete_agent(self, agent_id: uuid.UUID, soft_delete: bool = True) -> bool:
        """删除Agent"""
        return await self.delete(agent_id, "agent_id", soft_delete)
    
    async def agent_name_exists(self, agent_name: str) -> bool:
        """检查Agent名称是否存在"""
        return await self.exists({"agent_name": agent_name})
    
    async def get_agents_by_model(self, model_name: str) -> List[Dict[str, Any]]:
        """根据模型名称获取Agent列表"""
        try:
            query = """
                SELECT * FROM agent 
                WHERE model_name = $1 AND is_deleted = FALSE 
                ORDER BY created_at DESC
            """
            results = await self.db.fetch_all(query, model_name)
            return results
        except Exception as e:
            logger.error(f"根据模型名称获取Agent列表失败: {e}")
            raise
    
    async def get_autonomous_agents(self) -> List[Dict[str, Any]]:
        """获取自主运行的Agent列表"""
        try:
            query = """
                SELECT * FROM agent 
                WHERE is_autonomous = TRUE AND is_deleted = FALSE 
                ORDER BY created_at DESC
            """
            results = await self.db.fetch_all(query)
            return results
        except Exception as e:
            logger.error(f"获取自主运行Agent列表失败: {e}")
            raise
    
    async def search_agents(self, keyword: str, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索Agent"""
        try:
            query = """
                SELECT * FROM agent 
                WHERE (agent_name ILIKE $1 OR description ILIKE $1 OR model_name ILIKE $1) 
                      AND is_deleted = FALSE 
                ORDER BY created_at DESC 
                LIMIT $2
            """
            keyword_pattern = f"%{keyword}%"
            results = await self.db.fetch_all(query, keyword_pattern, limit)
            return results
        except Exception as e:
            logger.error(f"搜索Agent失败: {e}")
            raise
    
    async def update_agent_config(self, agent_id: uuid.UUID, 
                                 tool_config: Optional[Dict[str, Any]] = None,
                                 parameters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """更新Agent配置"""
        try:
            update_data = {}
            if tool_config is not None:
                update_data["tool_config"] = tool_config
            if parameters is not None:
                update_data["parameters"] = parameters
            
            if not update_data:
                return await self.get_agent_by_id(agent_id)
            
            result = await self.update(agent_id, update_data, "agent_id")
            return result
        except Exception as e:
            logger.error(f"更新Agent配置失败: {e}")
            raise
    
    async def get_agents_stats(self) -> Dict[str, Any]:
        """获取Agent统计信息"""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_agents,
                    COUNT(CASE WHEN is_autonomous THEN 1 END) as autonomous_agents,
                    COUNT(CASE WHEN NOT is_autonomous THEN 1 END) as manual_agents,
                    COUNT(DISTINCT model_name) as unique_models
                FROM agent 
                WHERE is_deleted = FALSE
            """
            result = await self.db.fetch_one(query)
            return result
        except Exception as e:
            logger.error(f"获取Agent统计信息失败: {e}")
            raise
    
    async def validate_agent_connection(self, agent_id: uuid.UUID) -> bool:
        """验证Agent连接（这里只是示例，实际实现需要根据具体的Agent API进行验证）"""
        try:
            agent = await self.get_agent_by_id(agent_id)
            if not agent:
                return False
            
            # 这里应该实现实际的Agent连接验证逻辑
            # 例如调用Agent的健康检查API
            # 目前只返回True作为示例
            return True
        except Exception as e:
            logger.error(f"验证Agent连接失败: {e}")
            return False
    
    async def get_all_active_agents(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有激活Agent"""
        try:
            query = """
                SELECT agent_id, agent_name, description, endpoint, 
                       created_at, updated_at, is_deleted
                FROM agent 
                WHERE is_deleted = FALSE 
                ORDER BY created_at DESC 
                LIMIT $1
            """
            results = await self.db.fetch_all(query, limit)
            # 为每个agent添加兼容性字段
            for result in results:
                result['capabilities'] = []
                result['status'] = True  # 默认为激活状态
            return results
        except Exception as e:
            logger.error(f"获取所有激活Agent失败: {e}")
            raise