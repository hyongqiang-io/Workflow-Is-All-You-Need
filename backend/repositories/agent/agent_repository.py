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
                "tags": agent_data.tags,  # 添加tags字段支持
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
        logger.info(f"🔥 [AGENT-READ] 开始读取Agent: {agent_id}")

        result = await self.get_by_id(agent_id, "agent_id")

        logger.info(f"🔥 [AGENT-READ] 从数据库读取的原始数据: {result}")

        if result:
            # 解析JSON字段
            result = self._parse_json_fields(result)
            logger.info(f"🔥 [AGENT-READ] 解析JSON字段后的数据: {result}")
            logger.info(f"🔥 [AGENT-READ] 最终tags字段: {result.get('tags')}")

        return result
    
    def _parse_json_fields(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """解析Agent数据中的JSON字段"""
        import json

        logger.info(f"🔥 [JSON-PARSE] 开始解析JSON字段，原始数据: {agent_data}")

        # 解析JSON字段
        json_fields = ['tool_config', 'parameters', 'capabilities', 'tags']
        for field in json_fields:
            if field in agent_data and agent_data[field]:
                logger.info(f"🔥 [JSON-PARSE] 处理字段 {field}, 原始值: {agent_data[field]}, 类型: {type(agent_data[field])}")
                if isinstance(agent_data[field], str):
                    try:
                        parsed_value = json.loads(agent_data[field])
                        agent_data[field] = parsed_value
                        logger.info(f"🔥 [JSON-PARSE] {field} 解析成功: {parsed_value}")
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error(f"🔥 [JSON-PARSE] {field} 解析失败: {e}")
                        # 如果解析失败，设为默认值
                        if field in ['capabilities', 'tags']:
                            agent_data[field] = []
                        else:
                            agent_data[field] = {}
                        logger.info(f"🔥 [JSON-PARSE] {field} 设置为默认值: {agent_data[field]}")

        # 确保必要字段存在且为正确类型
        if 'tool_config' not in agent_data or not isinstance(agent_data['tool_config'], dict):
            agent_data['tool_config'] = {}
            logger.info(f"🔥 [JSON-PARSE] tool_config 设置为默认值: {{}}")
        if 'parameters' not in agent_data or not isinstance(agent_data['parameters'], dict):
            agent_data['parameters'] = {}
            logger.info(f"🔥 [JSON-PARSE] parameters 设置为默认值: {{}}")
        if 'capabilities' not in agent_data or not isinstance(agent_data['capabilities'], list):
            agent_data['capabilities'] = []
            logger.info(f"🔥 [JSON-PARSE] capabilities 设置为默认值: []")
        if 'tags' not in agent_data or not isinstance(agent_data['tags'], list):
            agent_data['tags'] = []
            logger.info(f"🔥 [JSON-PARSE] tags 设置为默认值: []")

        logger.info(f"🔥 [JSON-PARSE] 最终解析结果: {agent_data}")
        logger.info(f"🔥 [JSON-PARSE] 最终tags值: {agent_data.get('tags')}")

        return agent_data
    
    async def get_agent_by_name(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取Agent"""
        try:
            query = "SELECT * FROM agent WHERE agent_name = $1 AND is_deleted = FALSE"
            result = await self.db.fetch_one(query, agent_name)
            if result:
                result = self._parse_json_fields(result)
            return result
        except Exception as e:
            logger.error(f"根据名称获取Agent失败: {e}")
            raise
    
    async def update_agent(self, agent_id: uuid.UUID, agent_data: AgentUpdate) -> Optional[Dict[str, Any]]:
        """更新Agent"""
        try:
            logger.info(f"🔥 [AGENT-UPDATE] 开始更新Agent: {agent_id}")
            logger.info(f"🔥 [AGENT-UPDATE] 原始更新数据: {agent_data.model_dump(exclude_unset=True)}")

            # 检查Agent是否存在
            existing_agent = await self.get_by_id(agent_id, "agent_id")
            if not existing_agent:
                raise ValueError(f"Agent {agent_id} 不存在")

            logger.info(f"🔥 [AGENT-UPDATE] 现有Agent数据: {existing_agent}")

            # 准备更新数据
            update_data = {}

            if agent_data.agent_name is not None:
                if agent_data.agent_name != existing_agent['agent_name']:
                    if await self.agent_name_exists(agent_data.agent_name):
                        raise ValueError(f"Agent名称 '{agent_data.agent_name}' 已存在")
                update_data["agent_name"] = agent_data.agent_name

            # 其他字段
            for field in ['description', 'base_url', 'api_key', 'model_name',
                         'tool_config', 'parameters', 'is_autonomous', 'tags']:
                value = getattr(agent_data, field, None)
                if value is not None:
                    update_data[field] = value
                    if field == 'tags':
                        logger.info(f"🔥 [AGENT-UPDATE] 准备更新tags: {value}")

            if not update_data:
                return existing_agent

            logger.info(f"🔥 [AGENT-UPDATE] 构建的更新数据: {update_data}")

            result = await self.update(agent_id, update_data, "agent_id")

            logger.info(f"🔥 [AGENT-UPDATE] 更新操作返回结果: {result}")

            # 重新读取数据验证
            verification_agent = await self.get_by_id(agent_id, "agent_id")
            logger.info(f"🔥 [AGENT-UPDATE] 验证读取Agent数据: {verification_agent}")

            return result
        except Exception as e:
            logger.error(f"更新Agent失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
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
            logger.info(f"🔥 [GET-ALL-AGENTS] 开始获取所有激活Agent，限制: {limit}")

            query = """
                SELECT agent_id, agent_name, description, base_url, api_key,
                       model_name, tool_config, parameters, is_autonomous,
                       tags, created_at, updated_at, is_deleted
                FROM agent
                WHERE is_deleted = FALSE
                ORDER BY created_at DESC
                LIMIT $1
            """
            results = await self.db.fetch_all(query, limit)

            logger.info(f"🔥 [GET-ALL-AGENTS] 查询到 {len(results)} 个Agent")

            # 解析JSON字段并添加兼容性字段
            processed_results = []
            for result in results:
                logger.info(f"🔥 [GET-ALL-AGENTS] 处理Agent: {result.get('agent_name')}")
                logger.info(f"🔥 [GET-ALL-AGENTS] 原始tags值: {result.get('tags')}")

                # 解析JSON字段
                parsed_result = self._parse_json_fields(dict(result))

                # 添加兼容性字段
                parsed_result['status'] = True  # 默认为激活状态

                logger.info(f"🔥 [GET-ALL-AGENTS] 解析后tags值: {parsed_result.get('tags')}")
                processed_results.append(parsed_result)

            logger.info(f"🔥 [GET-ALL-AGENTS] 返回 {len(processed_results)} 个处理后的Agent")
            return processed_results
        except Exception as e:
            logger.error(f"获取所有激活Agent失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            raise