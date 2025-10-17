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
            logger.info(f"🤖 [AI-GENERATOR] 开始AI工作流生成")
            logger.info(f"🤖 [AI-GENERATOR] 用户ID: {user_id}")
            logger.info(f"🤖 [AI-GENERATOR] 任务描述: '{task_description}'")
            logger.info(f"🤖 [AI-GENERATOR] 任务描述长度: {len(task_description)}")
            logger.info(f"🤖 [AI-GENERATOR] Prompt模式: {self.prompt_mode}")
            
            # 1. 调用AI API生成JSON
            logger.info(f"🤖 [AI-GENERATOR] 步骤1: 开始调用AI API")
            workflow_json = await self._call_ai_api(task_description)
            logger.info(f"🤖 [AI-GENERATOR] 步骤1完成: AI API调用成功，返回长度: {len(workflow_json)}")
            
            # 2. 解析并验证JSON
            logger.info(f"🤖 [AI-GENERATOR] 步骤2: 开始解析AI返回的JSON")
            workflow_data = self._parse_and_validate_json(workflow_json)
            logger.info(f"🤖 [AI-GENERATOR] 步骤2完成: JSON解析成功，工作流名称: '{workflow_data['name']}'")
            logger.info(f"🤖 [AI-GENERATOR] JSON验证结果: {len(workflow_data['nodes'])}个节点, {len(workflow_data['connections'])}个连接")
            
            # 3. 转换为WorkflowExport格式
            logger.info(f"🤖 [AI-GENERATOR] 步骤3: 开始转换为WorkflowExport格式")
            workflow_export = self._convert_to_workflow_export(workflow_data, task_description)
            logger.info(f"🤖 [AI-GENERATOR] 步骤3完成: 格式转换成功")
            
            logger.info(f"🤖 [AI-GENERATOR] ✅ AI工作流生成完成: '{workflow_export.name}'")
            logger.info(f"🤖 [AI-GENERATOR] 最终结果: {len(workflow_export.nodes)}个节点, {len(workflow_export.connections)}个连接")
            return workflow_export
            
        except Exception as e:
            logger.error(f"🤖 [AI-GENERATOR] ❌ AI工作流生成失败: {type(e).__name__}: {str(e)}")
            logger.error(f"🤖 [AI-GENERATOR] 失败时的输入参数:")
            logger.error(f"🤖 [AI-GENERATOR]   - 用户ID: {user_id}")
            logger.error(f"🤖 [AI-GENERATOR]   - 任务描述: '{task_description}'")
            logger.error(f"🤖 [AI-GENERATOR]   - Prompt模式: {self.prompt_mode}")
            import traceback
            logger.error(f"🤖 [AI-GENERATOR] 异常堆栈: {traceback.format_exc()}")
            # API失败时返回明确错误，不再使用模板
            raise ValidationError(f"AI工作流生成服务不可用，请检查网络连接或稍后重试。详细错误: {str(e)}")

    async def _call_ai_api(self, task_description: str) -> str:
        """调用DeepSeek AI API"""
        try:
            logger.info(f"🤖 [AI-API] 准备调用AI API")
            logger.info(f"🤖 [AI-API] 任务描述长度: {len(task_description)}")
            logger.info(f"🤖 [AI-API] API基础URL: {self.base_url}")
            logger.info(f"🤖 [AI-API] 使用模型: {self.model_name}")
            return await self._call_real_api(task_description)
                
        except Exception as e:
            logger.error(f"🤖 [AI-API] ❌ AI API调用失败: {type(e).__name__}: {str(e)}")
            raise Exception(f"AI服务暂时不可用，请稍后重试。错误详情: {str(e)}")
    
    async def _call_real_api_with_functions(self, task_description: str, functions: list, function_call: str = None) -> dict:
        """使用Function Calling调用AI API"""
        import requests
        import asyncio

        try:
            logger.info(f"🤖 [FUNCTION-CALL] 开始Function Calling API调用")
            logger.info(f"🤖 [FUNCTION-CALL] 函数数量: {len(functions)}")

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            user_prompt = f"请分析以下工作流上下文并使用generate_graph_operations函数生成合适的图操作序列：{task_description}"

            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "functions": functions,
                "temperature": 0.7,
                "max_tokens": 4000,
                "stream": False
            }

            # 如果指定了特定函数调用
            if function_call:
                payload["function_call"] = {"name": function_call}

            logger.info(f"🤖 [FUNCTION-CALL] 发送Function Calling请求")

            def make_request():
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120
                )
                return response

            response = await asyncio.get_event_loop().run_in_executor(None, make_request)

            if response.status_code != 200:
                logger.error(f"🤖 [FUNCTION-CALL] API返回错误状态: {response.status_code}")
                logger.error(f"🤖 [FUNCTION-CALL] 错误内容: {response.text}")
                raise Exception(f"API调用失败，状态码: {response.status_code}")

            result = response.json()

            # 检查是否有function call
            message = result['choices'][0]['message']
            if 'function_call' in message:
                logger.info(f"🤖 [FUNCTION-CALL] ✅ 收到function call: {message['function_call']['name']}")
                return {
                    'type': 'function_call',
                    'function_call': message['function_call']
                }
            else:
                logger.info(f"🤖 [FUNCTION-CALL] ✅ 收到常规回复")
                return {
                    'type': 'text',
                    'content': message.get('content', '')
                }

        except Exception as e:
            logger.error(f"🤖 [FUNCTION-CALL] ❌ Function Calling失败: {str(e)}")
            raise Exception(f"Function Calling调用失败: {str(e)}")

    async def _call_real_api(self, task_description: str) -> str:
        """调用真实的AI API"""
        import requests
        import asyncio
        
        try:
            logger.info(f"🤖 [REAL-API] 开始调用真实AI API")
            logger.info(f"🤖 [REAL-API] 使用增强prompt，模式: {self.prompt_mode}")
            logger.info(f"🤖 [REAL-API] 任务描述: '{task_description}'")
            logger.info(f"🤖 [REAL-API] API端点: {self.base_url}/chat/completions")
            logger.info(f"🤖 [REAL-API] 模型: {self.model_name}")
            
            # 构建请求，使用实例的system_prompt
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            user_prompt = f"请为以下任务生成工作流：{task_description}"
            
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user", 
                        "content": user_prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 3000,  # 增加token限制以获得更详细的响应
                "stream": False
            }
            
            logger.info(f"🤖 [REAL-API] 请求头已设置")
            logger.info(f"🤖 [REAL-API] System prompt长度: {len(self.system_prompt)}")
            logger.info(f"🤖 [REAL-API] User prompt: '{user_prompt}'")
            logger.info(f"🤖 [REAL-API] 请求参数: temperature=0.7, max_tokens=3000")
            
            # 在异步函数中运行同步的requests调用
            def make_request():
                try:
                    logger.info(f"🤖 [REAL-API] 开始发送HTTP请求到: {self.base_url}/chat/completions")
                    response = requests.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=120,  # 增加超时时间到2分钟
                        verify=True  # 保持SSL验证
                    )
                    logger.info(f"🤖 [REAL-API] HTTP请求完成，状态码: {response.status_code}")
                    return response
                except requests.exceptions.Timeout:
                    logger.error(f"🤖 [REAL-API] 请求超时")
                    raise Exception("API请求超时，请稍后重试")
                except requests.exceptions.ConnectionError:
                    logger.error(f"🤖 [REAL-API] 连接错误")
                    raise Exception("无法连接到AI服务，请检查网络连接")
                except requests.exceptions.RequestException as e:
                    logger.error(f"🤖 [REAL-API] 网络请求异常: {e}")
                    raise Exception(f"网络请求错误: {str(e)}")
                except Exception as e:
                    logger.error(f"🤖 [REAL-API] requests调用异常: {e}")
                    raise e
            
            # 使用线程池执行同步请求
            logger.info(f"🤖 [REAL-API] 在线程池中执行请求")
            response = await asyncio.get_event_loop().run_in_executor(None, make_request)
            
            logger.info(f"🤖 [REAL-API] API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                logger.info(f"🤖 [REAL-API] API调用成功，开始解析响应")
                response_data = response.json()
                
                # 检查响应结构
                if "choices" not in response_data or not response_data["choices"]:
                    logger.error(f"🤖 [REAL-API] API返回格式异常：缺少choices字段")
                    logger.error(f"🤖 [REAL-API] 响应数据: {response_data}")
                    raise Exception("AI API返回格式异常：缺少choices字段")
                
                ai_response = response_data["choices"][0]["message"]["content"]
                
                if not ai_response or len(ai_response.strip()) == 0:
                    logger.error(f"🤖 [REAL-API] AI API返回空响应")
                    raise Exception("AI API返回空响应")
                
                logger.info(f"🤖 [REAL-API] ✅ AI API调用成功")
                logger.info(f"🤖 [REAL-API] 返回内容长度: {len(ai_response)}")
                logger.info(f"🤖 [REAL-API] AI响应预览: {ai_response[:200]}...")
                
                # 检查响应是否包含JSON
                if "```json" in ai_response or "{" in ai_response:
                    logger.info(f"🤖 [REAL-API] 响应包含JSON格式，看起来正常")
                else:
                    logger.warning(f"🤖 [REAL-API] 响应可能不包含JSON格式")
                
                return ai_response
                
            elif response.status_code == 401:
                logger.error(f"🤖 [REAL-API] API密钥无效或已过期")
                raise Exception("API密钥无效或已过期")
            elif response.status_code == 429:
                logger.error(f"🤖 [REAL-API] API调用频率超限")
                raise Exception("API调用频率超限，请稍后重试")
            elif response.status_code >= 500:
                logger.error(f"🤖 [REAL-API] AI服务器内部错误")
                raise Exception("AI服务器内部错误，请稍后重试")
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", "未知错误")
                    logger.error(f"🤖 [REAL-API] API调用失败，错误消息: {error_message}")
                except:
                    error_message = response.text[:200] if response.text else "未知错误"
                    logger.error(f"🤖 [REAL-API] API调用失败，错误响应: {error_message}")
                raise Exception(f"API调用失败 ({response.status_code}): {error_message}")
                
        except Exception as e:
            logger.error(f"🤖 [REAL-API] ❌ AI API调用失败: {type(e).__name__}: {str(e)}")
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
            if len(end_nodes) == 0:
                raise Exception("工作流必须至少有一个结束节点")
            
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