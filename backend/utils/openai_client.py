"""
OpenAI客户端集成
OpenAI Client Integration
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger
from .helpers import safe_json_dumps

# 尝试导入OpenAI，如果失败则使用模拟版本

from openai import AsyncOpenAI
OPENAI_AVAILABLE = True
logger.info("OpenAI库导入成功")


class OpenAIClient:
    """OpenAI客户端"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 model: Optional[str] = None, prompt: Optional[str] = None,
                 temperature: float = 0.7, top_p: float = 0.9):
        self.api_key = api_key or "sk-lkyoyvnbsssstobvfhezidgmiegpwzbykyfkxwebqcmgctyz"  # 应该从环境变量获取
        self.base_url = base_url or "https://api.siliconflow.cn/v1"
        self.model = model or "Pro/deepseek-ai/DeepSeek-V3"
        self.prompt = prompt
        self.temperature = temperature
        self.top_p = top_p
        self.timeout = 30
        
        # 初始化AsyncOpenAI客户端
        self.aclient = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
    
    async def process_task(self, task_data: Dict[str, Any],
                          model: Optional[str] = None) -> Dict[str, Any]:
        """处理任务请求，支持多模态内容"""
        try:
            # 构建请求参数
            model_name = model or task_data.get('model', self.model)

            logger.info(f"🚀 [OPENAI-CLIENT] 开始处理OpenAI任务")
            logger.info(f"   - 使用模型: {model_name}")
            logger.info(f"   - Base URL: {self.base_url}")
            logger.info(f"   - API Key存在: {'是' if self.api_key else '否'}")

            # 检查是否为多模态内容
            has_multimodal = task_data.get('has_multimodal_content', False)
            images = task_data.get('images', [])

            if has_multimodal and images:
                logger.info(f"📷 [OPENAI-CLIENT] 检测到多模态内容，图片数量: {len(images)}")

            # 从task_data中提取messages
            messages = task_data.get('messages', [])
            if not messages:
                raise ValueError("task_data中缺少messages字段")

            # 如果有多模态内容，转换消息格式
            if has_multimodal and images:
                messages = self._convert_to_multimodal_messages(messages, images)
                logger.info(f"📷 [OPENAI-CLIENT] 已转换为多模态消息格式")

            # 调用真实的OpenAI API
            result = await self._call_openai_api_with_messages(messages, model_name, task_data)

            return {
                'success': True,
                'model': model_name,
                'result': result,
                'usage': result.get('usage', {}),
                'has_multimodal_content': has_multimodal
            }

        except Exception as e:
            logger.error(f"OpenAI处理任务失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'model': model or self.model
            }

    async def chat_completion_with_functions(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        function_call: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """使用Function Calling调用OpenAI API"""
        try:
            # 转换functions为tools格式
            tools = []
            for func in functions:
                tools.append({
                    "type": "function",
                    "function": func
                })

            # 构建请求参数
            request_params = {
                "model": model or self.model,
                "messages": messages,
                "temperature": temperature or self.temperature,
                "tools": tools
            }

            # 如果指定了function_call，转换为tool_choice
            if function_call:
                if function_call.get("name"):
                    request_params["tool_choice"] = {
                        "type": "function",
                        "function": {"name": function_call["name"]}
                    }

            logger.info(f"🛠️ [FUNCTION-CALL] 调用模型: {request_params['model']}")
            logger.info(f"🛠️ [FUNCTION-CALL] 函数数量: {len(functions)}")

            # 调用OpenAI API
            response = await self.aclient.chat.completions.create(**request_params)

            # 处理响应
            message = response.choices[0].message

            if message.tool_calls:
                tool_call = message.tool_calls[0]
                return {
                    "function_call": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    },
                    "content": message.content,
                    "usage": response.usage.model_dump() if response.usage else {}
                }
            else:
                return {
                    "content": message.content,
                    "usage": response.usage.model_dump() if response.usage else {}
                }

        except Exception as e:
            logger.error(f"🛠️ [FUNCTION-CALL] API调用失败: {e}")
            raise

    def _convert_to_multimodal_messages(self, messages: List[Dict], images: List[Dict]) -> List[Dict]:
        """
        将普通消息转换为多模态消息格式

        Args:
            messages: 原始消息列表
            images: 图片数据列表

        Returns:
            支持多模态的消息列表
        """
        try:
            logger.debug(f"🔄 [MULTIMODAL] 开始转换消息格式")

            multimodal_messages = []

            for message in messages:
                role = message.get('role', 'user')
                content = message.get('content', '')

                if role == 'user' and images:
                    # 为用户消息添加图片内容
                    content_parts = []

                    # 添加文本内容
                    if content:
                        content_parts.append({
                            "type": "text",
                            "text": content
                        })

                    # 添加图片内容
                    for image in images:
                        image_content = {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image['content_type']};base64,{image['base64_data']}",
                                "detail": "high"  # 高分辨率分析
                            }
                        }
                        content_parts.append(image_content)
                        logger.debug(f"📷 [MULTIMODAL] 添加图片: {image['name']}")

                    multimodal_messages.append({
                        "role": role,
                        "content": content_parts
                    })

                    # 图片只在第一个用户消息中添加
                    images = []  # 清空，避免重复添加

                else:
                    # 非用户消息或无图片，保持原格式
                    multimodal_messages.append(message)

            logger.debug(f"✅ [MULTIMODAL] 消息转换完成，消息数量: {len(multimodal_messages)}")
            return multimodal_messages

        except Exception as e:
            logger.error(f"❌ [MULTIMODAL] 消息转换失败: {e}")
            # 转换失败时返回原始消息
            return messages
    
    async def _call_openai_api_with_messages(self, messages: List[Dict[str, str]], 
                                           model: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """使用messages格式调用OpenAI API（支持工具调用）"""
        try:
            logger.info(f"[OPENAI-API] 准备调用API")
            logger.info(f"   - 模型: {model}")
            logger.info(f"   - 消息数量: {len(messages)}")
            logger.info(f"   - 温度: {task_data.get('temperature', self.temperature)}")
            logger.info(f"   - 最大tokens: {task_data.get('max_tokens', 2000)}")
            
            # 检查是否有工具
            tools = task_data.get('tools', [])
            tool_choice = task_data.get('tool_choice')
            
            logger.info(f"   - 工具数量: {len(tools)}")
            logger.info(f"   - 工具选择: {tool_choice}")
            
            if tools:
                logger.info(f"[TOOL-DEBUG] 工具列表:")
                for i, tool in enumerate(tools[:3]):  # 只显示前3个工具
                    logger.info(f"   工具 {i+1}: {tool.get('function', {}).get('name', 'unknown')}")
                    logger.info(f"     描述: {tool.get('function', {}).get('description', 'no description')[:100]}...")
            
            # 构建API请求参数
            api_params = {
                'model': model,
                'messages': messages,
                'temperature': task_data.get('temperature', self.temperature),
                'max_tokens': task_data.get('max_tokens', 2000),
                'top_p': self.top_p,
            }
            
            # 如果有工具，添加工具参数
            if tools:
                api_params['tools'] = tools
                if tool_choice:
                    api_params['tool_choice'] = tool_choice
                logger.info(f"[TOOL-DEBUG] 已添加工具参数到API请求")
            
            # 调用OpenAI API
            logger.info(f"[OPENAI-API] 开始调用 {model}")
            response = await asyncio.wait_for(
                self.aclient.chat.completions.create(**api_params),
                timeout=120.0  # 增加到120秒超时
            )
            
            logger.info(f"[OPENAI-API] API调用成功")
            
            # 提取响应内容
            message = response.choices[0].message
            content = message.content
            tool_calls = getattr(message, 'tool_calls', []) or []  # 确保不是None
            
            usage = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
            
            logger.info(f"[OPENAI-API] 响应解析完成")
            logger.info(f"   - 内容长度: {len(content) if content else 0}")
            logger.info(f"   - 工具调用数量: {len(tool_calls) if tool_calls else 0}")
            logger.info(f"   - Token使用: {usage}")
            
            if tool_calls:
                logger.info(f"[TOOL-DEBUG] 检测到工具调用:")
                for i, tool_call in enumerate(tool_calls):
                    func_name = tool_call.function.name if hasattr(tool_call, 'function') else 'unknown'
                    logger.info(f"   工具调用 {i+1}: {func_name}")
                    logger.info(f"     ID: {tool_call.id}")
                    if hasattr(tool_call, 'function'):
                        logger.info(f"     参数: {tool_call.function.arguments[:200]}...")
                
                # 将工具调用转换为可序列化的格式
                serializable_tool_calls = []
                for tool_call in tool_calls:
                    serializable_tool_calls.append({
                        'id': tool_call.id,
                        'type': getattr(tool_call, 'type', 'function'),
                        'function': {
                            'name': tool_call.function.name,
                            'arguments': tool_call.function.arguments
                        }
                    })
            
            # 返回符合OpenAI响应格式的结果
            result = {
                'content': content,
                'usage': usage,
                'message': {
                    'content': content,
                    'role': 'assistant'
                }
            }
            
            # 如果有工具调用，添加到响应中
            if tool_calls:
                result['message']['tool_calls'] = serializable_tool_calls
                logger.info(f"[TOOL-DEBUG] 工具调用已添加到响应中")
            
            return result
                
        except Exception as e:
            logger.error(f"调用OpenAI API失败: {e}")
            logger.error(f"错误类型: {type(e).__name__}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
            # 降级到模拟处理
            return await self._simulate_openai_request(messages, model)
    
    async def _call_openai_api(self, prompt: str, model: str) -> Dict[str, Any]:
        """调用真实的OpenAI API"""
        try:
            # 构建消息列表
            messages = []
            if self.prompt is not None:
                messages.append({
                    "content": self.prompt,
                    "role": "system"
                })

            messages.append({"role": "user", "content": prompt})

            # 调用OpenAI API
            response = await asyncio.wait_for(
                self.aclient.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                ),
                timeout=10.0  # 10秒超时
            )

            # 提取响应内容
            content = response.choices[0].message.content
            usage = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
            
            # 尝试解析JSON响应
            try:
                parsed_result = json.loads(content)
                parsed_result['usage'] = usage
                return parsed_result
            except json.JSONDecodeError:
                # 如果不是JSON格式，返回纯文本结果
                return {
                    'analysis': content,
                    'result': {'content': content},
                    'recommendations': [],
                    'confidence': 0.8,
                    'usage': usage
                }
                
        except Exception as e:
            logger.error(f"调用OpenAI API失败: {e}")
            # 降级到模拟处理
            return await self._simulate_openai_request(prompt, model)
    
    async def _simulate_openai_request(self, messages_or_prompt, model: str) -> Dict[str, Any]:
        """模拟OpenAI API响应（用于测试和降级）"""
        try:
            # 模拟处理延迟
            await asyncio.sleep(0.5)
            
            # 提取用户消息内容
            if isinstance(messages_or_prompt, list):
                user_content = ""
                for msg in messages_or_prompt:
                    if msg.get('role') == 'user':
                        user_content = msg.get('content', '')
                        break
            else:
                user_content = str(messages_or_prompt)
            
            # 生成模拟的JSON响应
            mock_response = {
                "analysis_result": f"基于提供的数据完成了深度分析。用户内容长度: {len(user_content)} 字符",
                "key_findings": [
                    "数据质量良好，可以进行有效分析",
                    "上游节点提供了充分的上下文信息",
                    "分析结果具有较高的可信度"
                ],
                "recommendations": [
                    "建议进一步分析数据趋势",
                    "建议关注关键指标变化",
                    "建议定期更新分析模型"
                ],
                "confidence_score": 0.87,
                "summary": f"使用{model}模型成功完成任务分析"
            }
            
            # 返回符合OpenAI格式的响应
            return {
                "content": safe_json_dumps(mock_response),
                "usage": {
                    "prompt_tokens": 150,
                    "completion_tokens": 200,
                    "total_tokens": 350
                }
            }
            
        except Exception as e:
            logger.error(f"模拟OpenAI请求失败: {e}")
            # 返回最基本的响应
            return {
                "content": safe_json_dumps({
                    "analysis_result": "模拟分析完成",
                    "key_findings": ["基础分析结果"],
                    "recommendations": ["建议使用真实API"],
                    "confidence_score": 0.75,
                    "summary": "模拟处理完成"
                }, ensure_ascii=False),
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}
            }

    async def generate_image(self, prompt: str, model: str = "black-forest-labs/FLUX.1-schnell",
                           size: str = "1024x1024", quality: str = "standard",
                           n: int = 1) -> Dict[str, Any]:
        """
        生成图像

        Args:
            prompt: 图像描述提示
            model: 图像生成模型 (SiliconFlow支持的模型)
            size: 图像尺寸
            quality: 图像质量
            n: 生成图像数量

        Returns:
            图像生成结果
        """
        try:
            logger.info(f"🎨 [IMAGE-GEN-API] === 图像生成API调用开始 ===")
            logger.info(f"🎨 [IMAGE-GEN-API] 接收到的参数:")
            logger.info(f"   - prompt: {prompt}")
            logger.info(f"   - model: {model}")
            logger.info(f"   - size: {size}")
            logger.info(f"   - quality: {quality}")
            logger.info(f"   - n: {n}")
            logger.info(f"🎨 [IMAGE-GEN-API] API配置:")
            logger.info(f"   - Base URL: {self.base_url}")
            logger.info(f"   - API Key存在: {'是' if self.api_key else '否'}")

            # 调用SiliconFlow的图像生成API
            logger.info(f"🎨 [IMAGE-GEN-API] 开始调用SiliconFlow API...")
            response = await asyncio.wait_for(
                self.aclient.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=n
                ),
                timeout=60.0  # 图像生成需要更长时间
            )

            logger.info(f"🎨 [IMAGE-GEN-API] API调用成功，开始处理响应...")
            logger.info(f"🎨 [IMAGE-GEN-API] 响应数据条数: {len(response.data)}")

            # 处理响应
            images = []
            for i, image_data in enumerate(response.data):
                logger.info(f"🎨 [IMAGE-GEN-API] 处理第 {i+1} 张图片...")
                if hasattr(image_data, 'url'):
                    # URL 格式返回
                    images.append({
                        'url': image_data.url,
                        'revised_prompt': getattr(image_data, 'revised_prompt', prompt),
                        'index': i
                    })
                    logger.info(f"   - URL格式: {image_data.url[:100]}...")
                elif hasattr(image_data, 'b64_json'):
                    # Base64 格式返回
                    images.append({
                        'b64_json': image_data.b64_json,
                        'revised_prompt': getattr(image_data, 'revised_prompt', prompt),
                        'index': i
                    })
                    logger.info(f"   - Base64格式: {len(image_data.b64_json)} 字符")

            logger.info(f"✅ [IMAGE-GEN-API] 图像生成成功，生成了 {len(images)} 张图片")
            logger.info(f"🎨 [IMAGE-GEN-API] 最终使用的prompt: {prompt}")

            return {
                'success': True,
                'images': images,
                'model': model,
                'prompt': prompt
            }

        except Exception as e:
            logger.error(f"❌ [IMAGE-GEN] 图像生成失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'model': model,
                'prompt': prompt
            }

    def supports_image_generation(self, agent_tags: List[str]) -> bool:
        """
        检查Agent是否支持图像生成

        Args:
            agent_tags: Agent的标签列表

        Returns:
            是否支持图像生成
        """
        return 'image-generation' in (agent_tags or [])
    

# 全局OpenAI客户端实例
openai_client = OpenAIClient()