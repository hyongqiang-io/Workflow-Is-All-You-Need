"""
AI工作流生成服务
AI Workflow Generation Service
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from loguru import logger
import httpx
import asyncio

from ..models.workflow_import_export import WorkflowExport, ExportNode, ExportConnection, ExportNodeType
from ..utils.exceptions import ValidationError
from .enhanced_prompt import get_recommended_prompt, ERROR_HANDLING_PROMPTS


class AIWorkflowGeneratorService:
    """AI工作流生成服务"""
    
    def __init__(self, prompt_mode: str = "production"):
        # 硬编码API配置
        self.api_key = "sk-omusfjrjuzhvqjmteijszqyqahtvhbcbwfyfdkucvzbeynve"
        self.base_url = "https://api.siliconflow.cn/v1"
        self.model_name = "Pro/deepseek-ai/DeepSeek-V3"
        
        # 使用增强版prompt系统
        self.prompt_mode = prompt_mode
        self.system_prompt = get_recommended_prompt(prompt_mode)
        
        logger.info(f"AI工作流生成器初始化完成，prompt模式: {prompt_mode}")

    async def generate_workflow_from_description(
        self, 
        task_description: str,
        user_id: uuid.UUID
    ) -> WorkflowExport:
        """
        根据任务描述生成工作流模板
        
        Args:
            task_description: 用户输入的任务描述
            user_id: 用户ID
            
        Returns:
            WorkflowExport: 生成的工作流模板
        """
        try:
            logger.info(f"开始AI生成工作流 - 用户: {user_id}, 任务: {task_description[:50]}...")
            
            # 1. 调用AI API生成JSON
            workflow_json = await self._call_ai_api(task_description)
            
            # 2. 解析并验证JSON
            workflow_data = self._parse_and_validate_json(workflow_json)
            
            # 3. 转换为WorkflowExport格式
            workflow_export = self._convert_to_workflow_export(workflow_data, task_description)
            
            logger.info(f"AI工作流生成成功: {workflow_export.name}")
            return workflow_export
            
        except Exception as e:
            logger.error(f"AI工作流生成失败: {e}")
            # API失败时返回明确错误，不再使用模板
            raise ValidationError(f"AI工作流生成服务不可用，请检查网络连接或稍后重试。详细错误: {str(e)}")

    async def _call_ai_api(self, task_description: str) -> str:
        """调用DeepSeek AI API"""
        try:
            logger.info(f"准备调用AI API，任务描述长度: {len(task_description)}")
            return await self._call_real_api(task_description)
                
        except Exception as e:
            logger.error(f"AI API调用失败: {type(e).__name__}: {str(e)}")
            raise Exception(f"AI服务暂时不可用，请稍后重试。错误详情: {str(e)}")
    
    async def _call_real_api(self, task_description: str) -> str:
        """调用真实的AI API"""
        import requests
        import asyncio
        
        try:
            logger.info(f"使用增强prompt调用AI API，模式: {self.prompt_mode}")
            logger.info(f"任务描述: {task_description}")
            
            # 构建请求，使用实例的system_prompt
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user", 
                        "content": f"请为以下任务生成工作流：{task_description}"
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 3000,  # 增加token限制以获得更详细的响应
                "stream": False
            }
            
            logger.info(f"调用AI API: {self.base_url}/chat/completions")
            
            # 在异步函数中运行同步的requests调用
            def make_request():
                try:
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=120,  # 增加超时时间到2分钟
                        verify=True  # 保持SSL验证
                    )
                    return response
                except requests.exceptions.Timeout:
                    raise Exception("API请求超时，请稍后重试")
                except requests.exceptions.ConnectionError:
                    raise Exception("无法连接到AI服务，请检查网络连接")
                except requests.exceptions.RequestException as e:
                    raise Exception(f"网络请求错误: {str(e)}")
                except Exception as e:
                    logger.error(f"requests调用异常: {e}")
                    raise e
            
            # 使用线程池执行同步请求
            response = await asyncio.get_event_loop().run_in_executor(None, make_request)
            
            logger.info(f"API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                
                # 检查响应结构
                if "choices" not in response_data or not response_data["choices"]:
                    raise Exception("AI API返回格式异常：缺少choices字段")
                
                ai_response = response_data["choices"][0]["message"]["content"]
                
                if not ai_response or len(ai_response.strip()) == 0:
                    raise Exception("AI API返回空响应")
                
                logger.info(f"AI API调用成功，返回长度: {len(ai_response)}")
                logger.info(f"AI响应预览: {ai_response[:200]}...")
                return ai_response
                
            elif response.status_code == 401:
                raise Exception("API密钥无效或已过期")
            elif response.status_code == 429:
                raise Exception("API调用频率超限，请稍后重试")
            elif response.status_code >= 500:
                raise Exception("AI服务器内部错误，请稍后重试")
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "未知错误")
                except:
                    error_message = response.text[:200] if response.text else "未知错误"
                raise Exception(f"API调用失败 ({response.status_code}): {error_message}")
                
        except Exception as e:
            logger.error(f"AI API调用失败: {type(e).__name__}: {str(e)}")
            raise e
    

    def _parse_and_validate_json(self, ai_response: str) -> Dict[str, Any]:
        """解析并验证AI返回的JSON"""
        try:
            # 尝试提取JSON（去除可能的markdown标记）
            json_str = ai_response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()
            
            # 解析JSON
            workflow_data = json.loads(json_str)
            
            # 基本验证
            required_fields = ["name", "description", "nodes", "connections"]
            for field in required_fields:
                if field not in workflow_data:
                    raise Exception(f"缺少必需字段: {field}")
            
            # 验证节点
            if not workflow_data["nodes"]:
                raise Exception("工作流至少需要一个节点")
            
            # 验证节点类型
            start_nodes = [n for n in workflow_data["nodes"] if n.get("type") == "start"]
            end_nodes = [n for n in workflow_data["nodes"] if n.get("type") == "end"]
            
            if len(start_nodes) != 1:
                raise Exception("工作流必须有且仅有一个开始节点")
            if len(end_nodes) != 1:
                raise Exception("工作流必须有且仅有一个结束节点")
            
            logger.info(f"JSON解析成功: {workflow_data['name']}")
            return workflow_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"原始响应: {ai_response[:500]}...")
            raise Exception(f"AI返回的JSON格式无效: {str(e)}")
        except Exception as e:
            logger.error(f"JSON验证失败: {e}")
            raise Exception(f"工作流数据验证失败: {str(e)}")

    def _convert_to_workflow_export(self, workflow_data: Dict[str, Any], original_description: str) -> WorkflowExport:
        """将JSON数据转换为WorkflowExport格式"""
        try:
            from datetime import datetime
            
            # 构建节点列表
            nodes = []
            for node_data in workflow_data["nodes"]:
                node = ExportNode(
                    name=node_data["name"],
                    type=ExportNodeType(node_data["type"]),
                    task_description=node_data.get("task_description", ""),
                    position_x=node_data.get("position_x", 100),
                    position_y=node_data.get("position_y", 200)
                )
                nodes.append(node)
            
            # 构建连接列表
            connections = []
            for conn_data in workflow_data["connections"]:
                connection = ExportConnection(
                    from_node_name=conn_data["from_node_name"],
                    to_node_name=conn_data["to_node_name"],
                    connection_type=conn_data.get("connection_type", "normal"),
                    condition_config=conn_data.get("condition_config"),
                    connection_path=conn_data.get("connection_path", []),
                    style_config=conn_data.get("style_config", {
                        "type": "smoothstep", 
                        "animated": False, 
                        "stroke_width": 2
                    })
                )
                connections.append(connection)
            
            # 构建WorkflowExport对象
            workflow_export = WorkflowExport(
                name=workflow_data["name"],
                description=workflow_data["description"],
                export_version=workflow_data.get("export_version", "2.0"),
                export_timestamp=workflow_data.get("export_timestamp", datetime.now().isoformat()),
                nodes=nodes,
                connections=connections,
                metadata=workflow_data.get("metadata", {
                    "generated_by": "AI",
                    "original_task": original_description,
                    "node_count": len(nodes),
                    "connection_count": len(connections),
                    "is_empty_workflow": False,
                    "enhanced_format": True,
                    "includes_connection_details": True
                })
            )
            
            return workflow_export
            
        except Exception as e:
            logger.error(f"格式转换失败: {e}")
            raise Exception(f"格式转换失败: {str(e)}")