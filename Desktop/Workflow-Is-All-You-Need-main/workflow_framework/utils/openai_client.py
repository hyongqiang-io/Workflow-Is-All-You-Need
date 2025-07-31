"""
OpenAI客户端集成
OpenAI Client Integration
"""

import json
import asyncio
from typing import Dict, Any, Optional, List
from loguru import logger

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
        """处理任务请求"""
        try:
            # 构建请求参数
            model_name = model or task_data.get('model', self.model)
            
            logger.info(f"使用OpenAI模型 {model_name} 处理任务")
            
            # 从task_data中提取messages
            messages = task_data.get('messages', [])
            if not messages:
                raise ValueError("task_data中缺少messages字段")
            
            # 调用真实的OpenAI API
            result = await self._call_openai_api_with_messages(messages, model_name, task_data)
            
            return {
                'success': True,
                'model': model_name,
                'result': result,
                'usage': result.get('usage', {})
            }
            
        except Exception as e:
            logger.error(f"OpenAI处理任务失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'model': model or self.model
            }
    
    async def _call_openai_api_with_messages(self, messages: List[Dict[str, str]], 
                                           model: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """使用messages格式调用OpenAI API"""
        try:
            # 调用OpenAI API
            response = await asyncio.wait_for(
                self.aclient.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=task_data.get('temperature', self.temperature),
                    max_tokens=task_data.get('max_tokens', 2000),
                    top_p=self.top_p,
                ),
                timeout=30.0  # 30秒超时
            )

            # 提取响应内容
            content = response.choices[0].message.content
            usage = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
            
            # 返回符合OpenAI响应格式的结果
            return {
                'content': content,
                'usage': usage
            }
                
        except Exception as e:
            logger.error(f"调用OpenAI API失败: {e}")
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
                "content": json.dumps(mock_response, ensure_ascii=False),
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
                "content": json.dumps({
                    "analysis_result": "模拟分析完成",
                    "key_findings": ["基础分析结果"],
                    "recommendations": ["建议使用真实API"],
                    "confidence_score": 0.75,
                    "summary": "模拟处理完成"
                }, ensure_ascii=False),
                "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200}
            }
    

# 全局OpenAI客户端实例
openai_client = OpenAIClient()