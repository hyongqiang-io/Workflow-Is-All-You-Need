"""
工作流Tab补全预测服务
基于现有AI工作流生成器，提供增量预测和智能建议功能
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from loguru import logger
import asyncio

from .ai_workflow_generator import AIWorkflowGeneratorService
from ..utils.exceptions import ValidationError


class WorkflowTabPredictionService:
    """工作流Tab补全预测服务"""

    def __init__(self):
        # 复用现有的AI生成器
        self.ai_generator = AIWorkflowGeneratorService(prompt_mode="tab_completion")

        # 预测缓存
        self.prediction_cache = {}
        self.cache_ttl = 300  # 5分钟缓存

        logger.info("🔮 工作流Tab预测服务初始化完成")

    async def predict_next_nodes(
        self,
        context_summary: str,
        max_suggestions: int = 3
    ) -> List[Dict[str, Any]]:
        """
        基于工作流上下文预测下一个可能的节点

        Args:
            context_summary: 工作流上下文摘要
            max_suggestions: 最大建议数量

        Returns:
            List[Dict]: 节点建议列表
        """
        try:
            logger.info(f"🔮 [TAB-PREDICT] 开始预测下一个节点")
            logger.info(f"🔮 [TAB-PREDICT] 上下文摘要: {context_summary[:200]}...")

            # 检查缓存
            cache_key = f"nodes_{hash(context_summary)}_{max_suggestions}"
            if cache_key in self.prediction_cache:
                cached_result = self.prediction_cache[cache_key]
                if cached_result['timestamp'] + self.cache_ttl > asyncio.get_event_loop().time():
                    logger.info(f"🔮 [TAB-PREDICT] 使用缓存结果")
                    return cached_result['data']

            # 构建节点预测的特殊prompt
            node_prediction_prompt = self._build_node_prediction_prompt(context_summary, max_suggestions)

            # 调用AI API
            ai_response = await self.ai_generator._call_real_api(node_prediction_prompt)

            # 解析节点建议
            node_suggestions = self._parse_node_suggestions(ai_response)

            # 缓存结果
            self.prediction_cache[cache_key] = {
                'data': node_suggestions,
                'timestamp': asyncio.get_event_loop().time()
            }

            logger.info(f"🔮 [TAB-PREDICT] ✅ 节点预测完成，建议数量: {len(node_suggestions)}")
            return node_suggestions

        except Exception as e:
            logger.error(f"🔮 [TAB-PREDICT] ❌ 节点预测失败: {str(e)}")
            return []

    async def predict_next_connections(
        self,
        context_summary: str,
        source_node_id: str,
        max_suggestions: int = 3
    ) -> List[Dict[str, Any]]:
        """
        预测从指定节点出发的可能连接

        Args:
            context_summary: 工作流上下文摘要
            source_node_id: 源节点ID
            max_suggestions: 最大建议数量

        Returns:
            List[Dict]: 连接建议列表
        """
        try:
            logger.info(f"🔮 [TAB-PREDICT] 开始预测节点连接")
            logger.info(f"🔮 [TAB-PREDICT] 源节点: {source_node_id}")

            # 检查缓存
            cache_key = f"edges_{hash(context_summary)}_{source_node_id}_{max_suggestions}"
            if cache_key in self.prediction_cache:
                cached_result = self.prediction_cache[cache_key]
                if cached_result['timestamp'] + self.cache_ttl > asyncio.get_event_loop().time():
                    logger.info(f"🔮 [TAB-PREDICT] 使用缓存结果")
                    return cached_result['data']

            # 构建连接预测的特殊prompt
            connection_prediction_prompt = self._build_connection_prediction_prompt(
                context_summary, source_node_id, max_suggestions
            )

            # 调用AI API
            ai_response = await self.ai_generator._call_real_api(connection_prediction_prompt)

            # 解析连接建议
            connection_suggestions = self._parse_connection_suggestions(ai_response, source_node_id)

            # 缓存结果
            self.prediction_cache[cache_key] = {
                'data': connection_suggestions,
                'timestamp': asyncio.get_event_loop().time()
            }

            logger.info(f"🔮 [TAB-PREDICT] ✅ 连接预测完成，建议数量: {len(connection_suggestions)}")
            return connection_suggestions

        except Exception as e:
            logger.error(f"🔮 [TAB-PREDICT] ❌ 连接预测失败: {str(e)}")
            return []

    async def predict_workflow_completion(
        self,
        context_summary: str,
        partial_description: str
    ) -> List[Dict[str, Any]]:
        """
        预测工作流的完整结构

        Args:
            context_summary: 当前工作流状态
            partial_description: 部分任务描述

        Returns:
            List[Dict]: 完整工作流建议
        """
        try:
            logger.info(f"🔮 [TAB-PREDICT] 开始预测工作流完整结构")

            completion_prompt = self._build_workflow_completion_prompt(context_summary, partial_description)
            ai_response = await self.ai_generator._call_real_api(completion_prompt)

            # 解析完整工作流建议
            workflow_suggestions = self._parse_workflow_completion(ai_response)

            logger.info(f"🔮 [TAB-PREDICT] ✅ 工作流完整性预测完成")
            return workflow_suggestions

        except Exception as e:
            logger.error(f"🔮 [TAB-PREDICT] ❌ 工作流完整性预测失败: {str(e)}")
            return []

    def _build_node_prediction_prompt(self, context_summary: str, max_suggestions: int) -> str:
        """构建节点预测的prompt"""
        return f"""你是一个工作流设计助手。基于当前工作流状态，预测用户可能需要添加的下一个节点。

当前工作流状态:
{context_summary}

请预测最多{max_suggestions}个可能的下一个节点，返回JSON格式:

{{
  "suggestions": [
    {{
      "type": "start|processor|end",
      "name": "节点名称",
      "description": "节点描述",
      "confidence": 0.85,
      "reasoning": "建议此节点的理由",
      "processor_type": "human|agent|null",
      "suggested_position": {{"x": 200, "y": 300}}
    }}
  ]
}}

要求:
1. 根据工作流完整性分析最需要的节点类型
2. confidence表示置信度(0-1)
3. reasoning要简洁明确
4. 考虑典型的工作流模式
5. 确保返回有效的JSON"""

    def _build_connection_prediction_prompt(self, context_summary: str, source_node_id: str, max_suggestions: int) -> str:
        """构建连接预测的prompt"""
        return f"""你是一个工作流设计助手。基于当前工作流状态，预测从指定节点出发的可能连接。

当前工作流状态:
{context_summary}

源节点ID: {source_node_id}

请预测最多{max_suggestions}个可能的连接目标，返回JSON格式:

{{
  "suggestions": [
    {{
      "target_node_type": "start|processor|end",
      "target_node_name": "目标节点名称",
      "connection_type": "normal|conditional|parallel",
      "confidence": 0.90,
      "reasoning": "建议此连接的理由",
      "condition_config": {{"description": "条件描述"}}
    }}
  ]
}}

要求:
1. 分析源节点类型和当前工作流逻辑
2. 建议合理的目标节点类型
3. 确定连接类型(普通/条件/并行)
4. confidence表示置信度(0-1)
5. 确保返回有效的JSON"""

    def _build_workflow_completion_prompt(self, context_summary: str, partial_description: str) -> str:
        """构建工作流完整性预测的prompt"""
        return f"""你是一个工作流设计助手。基于当前工作流状态和部分任务描述，预测完整的工作流结构。

当前工作流状态:
{context_summary}

任务描述(部分):
{partial_description}

请预测完整的工作流结构，返回JSON格式:

{{
  "completion_suggestions": [
    {{
      "missing_nodes": [
        {{
          "type": "start|processor|end",
          "name": "节点名称",
          "description": "节点功能描述",
          "priority": "high|medium|low"
        }}
      ],
      "missing_connections": [
        {{
          "from_node": "源节点名称",
          "to_node": "目标节点名称",
          "connection_type": "normal|conditional|parallel",
          "priority": "high|medium|low"
        }}
      ],
      "overall_confidence": 0.80,
      "completion_reasoning": "整体完善建议"
    }}
  ]
}}

要求:
1. 分析当前工作流的完整性
2. 识别缺失的关键节点和连接
3. 按优先级排序建议
4. 确保工作流逻辑合理
5. 确保返回有效的JSON"""

    def _parse_node_suggestions(self, ai_response: str) -> List[Dict[str, Any]]:
        """解析节点建议响应"""
        try:
            # 清理响应格式
            response_text = ai_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # 解析JSON
            parsed_response = json.loads(response_text)
            suggestions = parsed_response.get("suggestions", [])

            # 验证和标准化建议
            validated_suggestions = []
            for suggestion in suggestions:
                if self._validate_node_suggestion(suggestion):
                    validated_suggestions.append({
                        "id": f"suggested_{uuid.uuid4().hex[:8]}",
                        "type": suggestion.get("type", "processor"),
                        "name": suggestion.get("name", "未命名节点"),
                        "description": suggestion.get("description", ""),
                        "confidence": float(suggestion.get("confidence", 0.5)),
                        "reasoning": suggestion.get("reasoning", "AI建议"),
                        "processor_type": suggestion.get("processor_type"),
                        "suggested_position": suggestion.get("suggested_position", {"x": 200, "y": 200})
                    })

            return validated_suggestions

        except json.JSONDecodeError as e:
            logger.error(f"🔮 [PARSE] JSON解析失败: {e}")
            logger.error(f"🔮 [PARSE] 原始响应: {ai_response[:500]}...")
            return []
        except Exception as e:
            logger.error(f"🔮 [PARSE] 节点建议解析失败: {e}")
            return []

    def _parse_connection_suggestions(self, ai_response: str, source_node_id: str) -> List[Dict[str, Any]]:
        """解析连接建议响应"""
        try:
            # 清理响应格式
            response_text = ai_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # 解析JSON
            parsed_response = json.loads(response_text)
            suggestions = parsed_response.get("suggestions", [])

            # 验证和标准化建议
            validated_suggestions = []
            for suggestion in suggestions:
                if self._validate_connection_suggestion(suggestion):
                    validated_suggestions.append({
                        "id": f"edge_suggested_{uuid.uuid4().hex[:8]}",
                        "source_node_id": source_node_id,
                        "target_node_type": suggestion.get("target_node_type", "processor"),
                        "target_node_name": suggestion.get("target_node_name", "目标节点"),
                        "connection_type": suggestion.get("connection_type", "normal"),
                        "confidence": float(suggestion.get("confidence", 0.5)),
                        "reasoning": suggestion.get("reasoning", "AI建议"),
                        "condition_config": suggestion.get("condition_config")
                    })

            return validated_suggestions

        except json.JSONDecodeError as e:
            logger.error(f"🔮 [PARSE] JSON解析失败: {e}")
            return []
        except Exception as e:
            logger.error(f"🔮 [PARSE] 连接建议解析失败: {e}")
            return []

    def _parse_workflow_completion(self, ai_response: str) -> List[Dict[str, Any]]:
        """解析工作流完整性建议响应"""
        try:
            # 清理响应格式
            response_text = ai_response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # 解析JSON
            parsed_response = json.loads(response_text)
            suggestions = parsed_response.get("completion_suggestions", [])

            return suggestions

        except json.JSONDecodeError as e:
            logger.error(f"🔮 [PARSE] JSON解析失败: {e}")
            return []
        except Exception as e:
            logger.error(f"🔮 [PARSE] 工作流完整性建议解析失败: {e}")
            return []

    def _validate_node_suggestion(self, suggestion: Dict[str, Any]) -> bool:
        """验证节点建议的有效性"""
        required_fields = ["type", "name"]
        for field in required_fields:
            if field not in suggestion:
                return False

        # 验证节点类型
        valid_types = ["start", "processor", "end"]
        if suggestion["type"] not in valid_types:
            return False

        # 验证置信度
        confidence = suggestion.get("confidence", 0)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            return False

        return True

    def _validate_connection_suggestion(self, suggestion: Dict[str, Any]) -> bool:
        """验证连接建议的有效性"""
        required_fields = ["target_node_type", "connection_type"]
        for field in required_fields:
            if field not in suggestion:
                return False

        # 验证连接类型
        valid_connection_types = ["normal", "conditional", "parallel"]
        if suggestion["connection_type"] not in valid_connection_types:
            return False

        return True

    def clear_cache(self):
        """清空预测缓存"""
        self.prediction_cache.clear()
        logger.info("🔮 [CACHE] 预测缓存已清空")


# 全局预测服务实例
tab_prediction_service = WorkflowTabPredictionService()