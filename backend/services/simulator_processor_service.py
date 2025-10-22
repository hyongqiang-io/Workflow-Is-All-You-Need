"""
Simulator处理器执行服务
Simulator Processor Execution Service
"""

import uuid
import json
from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime

from backend.models.processor import ProcessorType
from backend.models.simulator import (
    CreateSimulatorSessionRequest, SendSimulatorMessageRequest,
    SimulatorDecisionRequest, ConversationRole, SimulatorDecision,
    SimulatorExecutionType
)
from backend.services.simulator_conversation_service import SimulatorConversationService
from backend.repositories.processor.processor_repository import ProcessorRepository
from backend.repositories.agent.agent_repository import AgentRepository
from backend.utils.openai_client import OpenAIClient


class SimulatorProcessorService:
    """Simulator处理器执行服务"""

    def __init__(self):
        self.conversation_service = SimulatorConversationService()
        self.processor_repo = ProcessorRepository()
        self.agent_repo = AgentRepository()

    async def execute_simulator_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行Simulator任务 - 弱模型主导的智能决策"""
        try:
            task_id = task['task_instance_id']
            processor_id = task.get('processor_id')
            node_instance_id = task.get('node_instance_id')

            logger.info(f"🤖 开始执行Simulator任务: {task['task_title']}")

            # 获取处理器信息
            processor = await self.processor_repo.get_processor_by_id(processor_id)
            if not processor or processor['type'] != ProcessorType.SIMULATOR.value:
                raise ValueError(f"处理器{processor_id}不是Simulator类型")

            # 获取强模型信息（从processor绑定的agent获取）
            if not processor.get('agent_id'):
                raise ValueError("Simulator处理器必须绑定Agent作为强模型")

            agent = await self.agent_repo.get_agent_by_id(processor['agent_id'])
            if not agent:
                raise ValueError("处理器绑定的Agent不存在")

            strong_model = agent.get('model_name', 'gpt-4')
            weak_model = "Pro/Qwen/Qwen2.5-7B-Instruct"  # 默认弱模型

            logger.info(f"🤖 模型配置: 弱模型={weak_model}, 强模型={strong_model}")

            # 创建Simulator对话会话
            session_request = CreateSimulatorSessionRequest(
                task_instance_id=str(task_id),
                node_instance_id=str(node_instance_id),
                processor_id=str(processor_id),
                weak_model=weak_model,
                strong_model=strong_model,
                max_rounds=20
            )

            session = await self.conversation_service.create_session(session_request)
            logger.info(f"🤖 Simulator会话已创建: {session.session_id}")

            # 准备任务上下文
            task_description = task.get('task_description', '')
            task_context = task.get('context_data', {})
            input_data = task.get('input_data', {})

            # 第一步：弱模型分析任务并初次决策
            initial_decision = await self._weak_model_initial_analysis(
                task_description, task_context, input_data, session.session_id, agent
            )

            if initial_decision["decision"] == "direct_submit":
                # 弱模型选择直接提交
                logger.info(f"🤖 弱模型选择直接提交任务")
                return await self._handle_direct_submit(session.session_id, initial_decision)

            else:
                # 弱模型选择开启对话
                logger.info(f"🤖 弱模型选择开启对话，最多20轮")
                return await self._handle_conversation_mode(
                    session.session_id, initial_decision, strong_model, weak_model
                )

        except Exception as e:
            logger.error(f"❌ 执行Simulator任务失败: {e}")
            raise

    async def _weak_model_initial_analysis(
        self,
        task_description: str,
        task_context: Dict[str, Any],
        input_data: Dict[str, Any],
        session_id: str,
        agent: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """弱模型进行初次任务分析和决策 - 使用Function Calling确保结构化输出"""

        # 构建弱模型提示词
        prompt = self._build_weak_model_initial_prompt(task_description, task_context, input_data)

        # 记录弱模型分析消息
        weak_message_request = SendSimulatorMessageRequest(
            session_id=session_id,
            role=ConversationRole.WEAK_MODEL,
            content=prompt,
            metadata={
                "type": "initial_analysis",
                "model": "Pro/Qwen/Qwen2.5-7B-Instruct",
                "timestamp": datetime.now().isoformat()
            }
        )

        await self.conversation_service.send_message(weak_message_request)

        # 调用真实的弱模型API，使用Function Calling
        decision = await self._call_weak_model_with_function_calling(
            task_description, task_context, input_data, agent
        )

        logger.info(f"🤖 弱模型决策结果: {decision}")
        return decision

    async def _call_weak_model_with_function_calling(
        self,
        task_description: str,
        task_context: Dict[str, Any],
        input_data: Dict[str, Any],
        agent: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """使用Function Calling调用弱模型，确保结构化输出"""

        # 创建OpenAI客户端（弱模型）- 使用Agent配置如果提供
        weak_api_key = None
        weak_base_url = None
        if agent:
            weak_api_key = agent.get('api_key')
            weak_base_url = agent.get('base_url')

        weak_client = OpenAIClient(
            api_key=weak_api_key,
            base_url=weak_base_url,
            model="Pro/Qwen/Qwen2.5-7B-Instruct",
            temperature=0.3  # 降低温度提高一致性
        )

        # 定义Function Calling的函数schema
        function_schema = {
            "name": "task_decision",
            "description": "分析任务并决定是否需要对话或直接提交答案",
            "parameters": {
                "type": "object",
                "properties": {
                    "need_conversation": {
                        "type": "boolean",
                        "description": "是否需要与专家模型对话。true表示需要对话，false表示可以直接提交答案"
                    },
                    "content": {
                        "type": "string",
                        "description": "回答内容。如果need_conversation为false，这里是最终答案；如果为true，这里是你想讨论的问题或初步分析"
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "对决策的置信度，0.0到1.0之间"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "决策理由和分析过程"
                    }
                },
                "required": ["need_conversation", "content", "confidence", "reasoning"]
            }
        }

        # 构建完整的提示词 - 初学者角色
        system_prompt = """你是一个充满好奇心的初学者助手。你对学习新知识非常渴望，但经常会遇到自己不太理解的概念和任务。

核心特征：
- 你承认自己的知识有限，不会假装什么都懂
- 遇到不熟悉的概念时，你会主动承认"我不太了解这个"
- 你对学习新知识充满热情，喜欢向专家请教
- 你会积极提出具体的学习问题，而不是空泛的询问
- 你喜欢通过具体例子来理解抽象概念

决策原则：
1. 如果任务涉及你不熟悉的专业概念或术语，优先选择 need_conversation=true，请教专家
2. 如果任务很基础且你确实理解，可以设置 need_conversation=false 尝试回答
3. 当不确定时，总是选择学习而非猜测

记住：作为初学者，承认不知道并积极学习是你最大的优势！"""

        user_prompt = f"""我遇到了一个任务，想请你帮我分析一下：

任务：{task_description}

背景信息：{json.dumps(task_context, ensure_ascii=False, indent=2) if task_context else "没有提供额外背景"}

相关数据：{json.dumps(input_data, ensure_ascii=False, indent=2) if input_data else "没有相关数据"}

作为初学者，我需要诚实地评估：
1. 这个任务中有我不熟悉的概念吗？
2. 我是否真的理解要做什么？
3. 我现在的知识水平能独立完成吗？

如果我觉得能够处理，我会尝试给出答案。
如果遇到不懂的地方，我会主动请教专家，提出具体的学习问题。

请用task_decision函数告诉我你的想法吧！"""

        try:
            # 调用弱模型API
            response = await weak_client.chat_completion_with_functions(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                functions=[function_schema],
                function_call={"name": "task_decision"}
            )

            # 解析Function Calling的结果
            if response and 'function_call' in response:
                function_result = json.loads(response['function_call']['arguments'])

                # 转换为标准格式
                if function_result.get("need_conversation"):
                    return {
                        "decision": "start_conversation",
                        "questions": [function_result.get("content", "需要更多信息来完成任务")],
                        "confidence": function_result.get("confidence", 0.6),
                        "reasoning": function_result.get("reasoning", "任务需要进一步讨论")
                    }
                else:
                    return {
                        "decision": "direct_submit",
                        "result": {
                            "answer": function_result.get("content", ""),
                            "reasoning": function_result.get("reasoning", ""),
                            "confidence": function_result.get("confidence", 0.8)
                        },
                        "confidence": function_result.get("confidence", 0.8),
                        "reasoning": function_result.get("reasoning", "弱模型直接处理")
                    }
            else:
                # 如果Function Calling失败，回退到简单逻辑
                logger.warning("🤖 Function Calling失败，使用回退逻辑")
                return await self._fallback_weak_model_decision(task_description, task_context, input_data)

        except Exception as e:
            logger.error(f"🤖 弱模型API调用失败: {e}")
            # 回退到简单逻辑
            return await self._fallback_weak_model_decision(task_description, task_context, input_data)

    async def _fallback_weak_model_decision(
        self,
        task_description: str,
        task_context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """弱模型API失败时的回退决策逻辑"""

        # 简单的启发式规则判断任务复杂度
        complexity_score = 0.0

        # 根据任务描述长度
        if len(task_description) > 100:
            complexity_score += 0.3

        # 根据上下文复杂度
        if task_context and len(str(task_context)) > 500:
            complexity_score += 0.4

        # 根据关键词判断
        complex_keywords = ['分析', '设计', '策略', '优化', '评估', '复杂', '详细', '研究', '方案']
        if any(keyword in task_description for keyword in complex_keywords):
            complexity_score += 0.3

        logger.info(f"🤖 回退逻辑 - 任务复杂度评分: {complexity_score}")

        if complexity_score < 0.5:
            # 简单任务，直接提交
            return {
                "decision": "direct_submit",
                "result": {
                    "answer": f"基于任务描述'{task_description}'，这是一个相对简单的任务，我可以直接处理。",
                    "reasoning": "任务描述清晰，复杂度较低，可以直接处理",
                    "confidence": 0.7
                },
                "confidence": 0.7,
                "reasoning": f"任务复杂度评分为{complexity_score}，低于阈值0.5，选择直接处理"
            }
        else:
            # 复杂任务，需要对话
            return {
                "decision": "start_conversation",
                "questions": [
                    "这个任务的核心目标是什么？",
                    "有什么特殊的要求或约束条件吗？",
                    "预期的输出格式和质量标准是什么？"
                ],
                "confidence": 0.6,
                "reasoning": f"任务复杂度评分为{complexity_score}，高于阈值0.5，需要与专家讨论"
            }

    def _build_weak_model_initial_prompt(
        self,
        task_description: str,
        task_context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> str:
        """构建弱模型初次分析的提示词 - 初学者版本"""

        prompt = f"""嗨！我是一个正在学习的初学者助手。我很想帮助完成任务，但我也会诚实地承认自己的不足。

遇到的任务：{task_description}

任务背景：{json.dumps(task_context, ensure_ascii=False, indent=2) if task_context else "没有额外背景信息"}

相关数据：{json.dumps(input_data, ensure_ascii=False, indent=2) if input_data else "没有提供数据"}

作为初学者，我需要坦诚地思考：

🤔 **我的自我评估：**
- 这个任务里有我不太熟悉的专业术语或概念吗？
- 我现在的知识水平真的足够处理这个任务吗？
- 如果我不太确定，最好的学习方式是什么？

💡 **我的原则：**
- 如果我能理解并有信心完成，我会尝试直接回答
- 如果遇到不懂的概念，我会主动承认并请教专家
- 我更愿意提出具体的学习问题，而不是假装什么都知道

📝 **我需要选择：**
1. **直接尝试** (direct_submit): 如果我觉得能够独立处理
2. **请教专家** (start_conversation): 如果我需要学习和讨论

让我想想应该怎么办...

请用以下JSON格式回复：
{{
    "decision": "direct_submit" 或 "start_conversation",
    "result": "你的答案（仅在direct_submit时提供）",
    "questions": ["你想讨论的问题（仅在start_conversation时提供）"],
    "reasoning": "你的决策理由",
    "confidence": 0.0-1.0
}}"""

        return prompt

    async def _simulate_weak_model_decision_v2(
        self,
        task_description: str,
        task_context: Dict[str, Any],
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟弱模型的决策过程 - 改进版"""

        # 简单的启发式规则判断任务复杂度
        complexity_score = 0.0

        # 根据任务描述长度
        if len(task_description) > 100:
            complexity_score += 0.3

        # 根据上下文复杂度
        if task_context and len(str(task_context)) > 500:
            complexity_score += 0.4

        # 根据关键词判断
        complex_keywords = ['分析', '设计', '策略', '优化', '评估', '复杂', '详细']
        if any(keyword in task_description for keyword in complex_keywords):
            complexity_score += 0.3

        logger.info(f"🤖 任务复杂度评分: {complexity_score}")

        if complexity_score < 0.5:
            # 简单任务，直接提交
            return {
                "decision": "direct_submit",
                "result": {
                    "answer": f"基于任务描述'{task_description}'，我认为这是一个相对简单的任务。",
                    "reasoning": "任务描述清晰，复杂度较低，可以直接处理",
                    "confidence": 0.8
                },
                "confidence": 0.8,
                "reasoning": f"任务复杂度评分为{complexity_score}，低于阈值0.5，选择直接处理"
            }
        else:
            # 复杂任务，需要对话
            return {
                "decision": "start_conversation",
                "questions": [
                    "这个任务的核心目标是什么？",
                    "有什么特殊的要求或约束条件吗？",
                    "预期的输出格式和质量标准是什么？"
                ],
                "confidence": 0.6,
                "reasoning": f"任务复杂度评分为{complexity_score}，高于阈值0.5，需要与专家讨论"
            }

    async def _handle_direct_submit(self, session_id: str, initial_decision: Dict[str, Any]) -> Dict[str, Any]:
        """处理弱模型直接提交的情况"""
        try:
            logger.info(f"🤖 处理直接提交: {initial_decision}")

            # 记录弱模型的决策
            decision_request = SimulatorDecisionRequest(
                session_id=session_id,
                decision_type=SimulatorDecision.DIRECT_SUBMIT,
                result_data=initial_decision["result"],
                confidence_score=initial_decision.get("confidence", 0.8),
                decision_reasoning=initial_decision.get("reasoning", "弱模型直接处理")
            )

            execution_result = await self.conversation_service.make_decision(decision_request)

            return {
                "status": "completed",
                "execution_type": "direct_submit",
                "result": initial_decision["result"],
                "execution_result": execution_result.model_dump(),
                "confidence": initial_decision.get("confidence", 0.8)
            }

        except Exception as e:
            logger.error(f"❌ 处理直接提交失败: {e}")
            raise

    async def _handle_conversation_mode(
        self,
        session_id: str,
        initial_decision: Dict[str, Any],
        strong_model: str,
        weak_model: str
    ) -> Dict[str, Any]:
        """处理弱模型选择对话模式的情况"""
        try:
            logger.info(f"🤖 开启对话模式: {initial_decision}")

            # 发送弱模型的初始问题
            questions = initial_decision.get("questions", ["请提供更多信息以帮助完成任务"])
            initial_message = f"我需要与您讨论以下问题来更好地完成任务：\n" + "\n".join(f"- {q}" for q in questions)

            weak_message_request = SendSimulatorMessageRequest(
                session_id=session_id,
                role=ConversationRole.WEAK_MODEL,
                content=initial_message,
                metadata={
                    "type": "conversation_start",
                    "model": weak_model,
                    "questions": questions,
                    "timestamp": datetime.now().isoformat()
                }
            )

            await self.conversation_service.send_message(weak_message_request)

            # 立即触发强模型回复
            await self._trigger_strong_model_response(session_id, strong_model)

            # 获取会话状态
            session_response = await self.conversation_service.get_session_with_messages(session_id)

            return {
                "status": "conversation_started",
                "session": session_response,
                "next_action": session_response.next_action,
                "initial_questions": questions,
                "reasoning": initial_decision.get("reasoning", "需要更多信息")
            }

        except Exception as e:
            logger.error(f"❌ 处理对话模式失败: {e}")
            raise

    async def _trigger_strong_model_response(self, session_id: str, strong_model: str):
        """触发强模型自动回复"""
        try:
            logger.info(f"🤖 触发强模型回复: {strong_model}")

            # 获取会话消息
            session_response = await self.conversation_service.get_session_with_messages(session_id)
            messages = session_response.messages  # 修复：直接访问messages属性
            session = session_response.session

            if not messages:
                logger.warning("🤖 没有消息可供强模型回复")
                return

            # 获取Agent信息用于API配置
            agent = None
            try:
                processor_id = session.processor_id
                processor = await self.processor_repo.get_processor_by_id(processor_id)
                if processor and processor.get('agent_id'):
                    agent = await self.agent_repo.get_agent_by_id(processor['agent_id'])
            except Exception as e:
                logger.warning(f"⚠️ 获取Agent配置失败: {e}，使用默认配置")

            # 获取最后一条弱模型消息
            last_weak_message = None
            for msg in reversed(messages):
                if msg.role == ConversationRole.WEAK_MODEL:
                    last_weak_message = msg
                    break

            if not last_weak_message:
                logger.warning("🤖 没有找到弱模型消息")
                return

            # 构建强模型回复内容
            strong_response = await self._generate_strong_model_response(
                last_weak_message.content, session.strong_model, messages, agent
            )

            # 发送强模型回复
            strong_message_request = SendSimulatorMessageRequest(
                session_id=session_id,
                role=ConversationRole.STRONG_MODEL,
                content=strong_response,
                metadata={
                    "type": "strong_model_response",
                    "model": strong_model,
                    "timestamp": datetime.now().isoformat()
                }
            )

            await self.conversation_service.send_message(strong_message_request)
            logger.info(f"✅ 强模型回复已发送")

            # 🔥 新增：触发弱模型继续分析
            await self._trigger_weak_model_continue_analysis(session_id)

        except Exception as e:
            logger.error(f"❌ 触发强模型回复失败: {e}")
            # 不抛出异常，避免中断主流程

    async def _trigger_weak_model_continue_analysis(self, session_id: str):
        """触发弱模型继续分析强模型回复"""
        try:
            logger.info(f"🤖 触发弱模型继续分析")

            # 获取会话信息和消息历史
            session_response = await self.conversation_service.get_session_with_messages(session_id)
            session = session_response.session
            messages = session_response.messages

            if not messages:
                logger.warning("🤖 没有消息历史可供分析")
                return

            # 检查是否已达到最大轮数
            if session.current_round >= session.max_rounds:
                logger.info(f"🤖 已达到最大轮数 {session.max_rounds}，终止对话")
                await self._finalize_conversation(session_id, "max_rounds_reached")
                return

            # 获取最后一条强模型回复
            last_strong_message = None
            for msg in reversed(messages):
                if msg.role == ConversationRole.STRONG_MODEL:
                    last_strong_message = msg
                    break

            if not last_strong_message:
                logger.warning("🤖 没有找到强模型回复")
                return

            # 获取Agent信息用于API配置
            agent = None
            try:
                processor_id = session.processor_id
                processor = await self.processor_repo.get_processor_by_id(processor_id)
                if processor and processor.get('agent_id'):
                    agent = await self.agent_repo.get_agent_by_id(processor['agent_id'])
            except Exception as e:
                logger.warning(f"⚠️ 获取Agent配置失败: {e}，使用默认配置")

            # 构建弱模型继续分析的提示
            continue_prompt = self._build_weak_model_continue_prompt(messages, last_strong_message.content)

            # 调用弱模型分析
            weak_response = await self._call_weak_model_analysis(continue_prompt, session.weak_model, agent)

            logger.info(f"🤖 弱模型继续分析结果: {weak_response.get('decision', 'unknown')}")

            # 发送弱模型分析消息
            weak_message_request = SendSimulatorMessageRequest(
                session_id=session_id,
                role=ConversationRole.WEAK_MODEL,
                content=self._format_weak_model_continue_message(weak_response),
                metadata={
                    "type": "continue_analysis",
                    "model": session.weak_model,
                    "decision": weak_response.get('decision'),
                    "timestamp": datetime.now().isoformat()
                }
            )

            await self.conversation_service.send_message(weak_message_request)

            # 根据弱模型决策执行下一步
            decision = weak_response.get('decision', 'unknown')

            if decision == 'submit_result':
                # 弱模型满意，提交最终结果
                logger.info(f"🤖 弱模型决定提交结果")
                await self._finalize_conversation(session_id, "consult_complete", weak_response.get('final_result'))

            elif decision == 'continue_conversation':
                # 弱模型需要继续对话
                logger.info(f"🤖 弱模型决定继续对话")
                new_questions = weak_response.get('questions', [])
                if new_questions:
                    # 更新轮数并触发强模型回复
                    await self._increment_conversation_round(session_id)
                    await self._trigger_strong_model_response(session_id, session.strong_model)
                else:
                    logger.warning("🤖 弱模型选择继续对话但没有提供问题")

            elif decision == 'terminate':
                # 弱模型主动终止
                logger.info(f"🤖 弱模型主动终止对话")
                await self._finalize_conversation(session_id, "weak_model_terminated")

            else:
                logger.warning(f"🤖 未知的弱模型决策: {decision}")

        except Exception as e:
            logger.error(f"❌ 弱模型继续分析失败: {e}")
            # 降级处理：自动提交
            try:
                await self._finalize_conversation(session_id, "interrupted", "由于分析失败，自动提交当前结果")
            except:
                logger.error(f"❌ 降级处理也失败")

    def _build_weak_model_continue_prompt(self, messages: List, strong_response: str) -> str:
        """构建弱模型继续分析的提示"""
        conversation_summary = []
        for msg in messages[-4:]:  # 最近4条消息
            role_name = "我" if msg.role == ConversationRole.WEAK_MODEL else "专家"
            conversation_summary.append(f"{role_name}: {msg.content[:200]}...")

        return f"""
我是一个学习中的助手，刚才向专家请教了问题，现在收到了专家的回复。我需要分析这个回复并决定下一步：

**对话历史摘要：**
{chr(10).join(conversation_summary)}

**专家最新回复：**
{strong_response}

现在我需要分析专家的回复，并做出决策：

🤔 **分析要点：**
1. 专家的回复是否完全回答了我的问题？
2. 我是否还有不清楚的地方需要进一步询问？
3. 基于专家的指导，我现在能否独立完成原始任务？

💡 **决策选项：**
1. **提交结果** (submit_result): 如果专家回复足够详细，我能基于此完成任务
2. **继续对话** (continue_conversation): 如果还有疑问需要进一步澄清
3. **终止对话** (terminate): 如果觉得已经获得足够信息但暂时不想提交

请用以下JSON格式回复：
{{
    "decision": "submit_result" 或 "continue_conversation" 或 "terminate",
    "final_result": "基于专家指导的最终答案（仅在submit_result时提供）",
    "questions": ["需要进一步澄清的问题（仅在continue_conversation时提供）"],
    "reasoning": "你的决策理由",
    "confidence": 0.0-1.0,
    "satisfaction": 0.0-1.0
}}
"""

    def _format_weak_model_continue_message(self, response: Dict) -> str:
        """格式化弱模型继续分析消息"""
        decision = response.get('decision', 'unknown')
        reasoning = response.get('reasoning', '未提供理由')

        if decision == 'submit_result':
            final_result = response.get('final_result', '未提供结果')
            return f"基于专家的详细指导，我现在可以提交最终结果：\n\n{final_result}\n\n决策理由：{reasoning}"

        elif decision == 'continue_conversation':
            questions = response.get('questions', [])
            questions_text = '\n- '.join(questions) if questions else '需要进一步澄清细节'
            return f"感谢专家的回复！我还有一些问题需要澄清：\n- {questions_text}\n\n决策理由：{reasoning}"

        elif decision == 'terminate':
            return f"感谢专家的指导！我觉得已经获得了足够的信息。\n\n决策理由：{reasoning}"

        else:
            return f"我正在分析专家的回复...\n\n决策理由：{reasoning}"

    async def _increment_conversation_round(self, session_id: str):
        """增加对话轮数"""
        try:
            # 这里应该调用conversation_service的方法来更新轮数
            # 暂时先记录日志
            logger.info(f"🤖 对话轮数+1")
        except Exception as e:
            logger.error(f"❌ 更新对话轮数失败: {e}")

    async def _finalize_conversation(self, session_id: str, decision_type: str, final_result: str = None):
        """结束对话并提交最终结果"""
        try:
            logger.info(f"🎯 结束对话: {decision_type}")

            # 这里应该：
            # 1. 更新会话状态为完成
            # 2. 记录最终决策
            # 3. 提交任务结果

            # 暂时先记录日志，具体实现需要根据conversation_service的接口
            logger.info(f"🎯 最终结果: {final_result if final_result else '无具体结果'}")

        except Exception as e:
            logger.error(f"❌ 结束对话失败: {e}")

    async def _call_weak_model_analysis(self, prompt: str, weak_model: str, agent: Dict[str, Any] = None) -> Dict[str, Any]:
        """调用弱模型进行分析，使用Function Calling确保结构化输出"""
        try:
            logger.info(f"🤖 调用弱模型分析: {weak_model}")

            # 创建OpenAI客户端（弱模型）- 使用Agent配置如果提供
            weak_api_key = None
            weak_base_url = None
            if agent:
                weak_api_key = agent.get('api_key')
                weak_base_url = agent.get('base_url')

            weak_client = OpenAIClient(
                api_key=weak_api_key,
                base_url=weak_base_url,
                model=weak_model,
                temperature=0.3  # 降低温度提高一致性
            )

            # 定义Function Calling的函数schema
            function_schema = {
                "name": "continue_decision",
                "description": "分析专家回复并决定下一步行动",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "decision": {
                            "type": "string",
                            "enum": ["submit_result", "continue_conversation", "terminate"],
                            "description": "决策类型：submit_result(提交结果)、continue_conversation(继续对话)、terminate(终止对话)"
                        },
                        "final_result": {
                            "type": "string",
                            "description": "最终结果内容（仅在decision为submit_result时需要）"
                        },
                        "questions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "需要进一步澄清的问题（仅在decision为continue_conversation时需要）"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "决策理由和分析过程"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "对决策的置信度，0.0到1.0之间"
                        },
                        "satisfaction": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "对专家回复的满意度，0.0到1.0之间"
                        }
                    },
                    "required": ["decision", "reasoning", "confidence", "satisfaction"]
                }
            }

            # 构建消息
            messages = [
                {"role": "system", "content": "你是一个学习中的初学者助手，正在分析专家的回复并决定下一步行动。"},
                {"role": "user", "content": prompt}
            ]

            # 调用Function Calling
            response = await weak_client.chat_completion_with_functions(
                messages=messages,
                functions=[function_schema],
                function_call={"name": "continue_decision"}
            )

            # 解析Function Calling结果
            if response.get("function_call"):
                function_result = json.loads(response["function_call"]["arguments"])
                logger.info(f"🤖 弱模型分析完成: {function_result.get('decision')}")
                return function_result
            else:
                logger.warning("🤖 弱模型未返回Function Call结果")
                return {
                    "decision": "terminate",
                    "reasoning": "分析结果解析失败",
                    "confidence": 0.1,
                    "satisfaction": 0.5
                }

        except Exception as e:
            logger.error(f"❌ 弱模型分析失败: {e}")
            # 返回默认的终止决策
            return {
                "decision": "terminate",
                "reasoning": f"分析过程中发生错误: {str(e)}",
                "confidence": 0.1,
                "satisfaction": 0.5
            }

    async def _generate_strong_model_response(self, weak_message: str, strong_model: str, messages: List, agent: Dict[str, Any] = None) -> str:
        """生成强模型回复"""
        try:
            # 构建对话历史
            conversation_history = []
            for msg in messages[:-1]:  # 排除最后一条消息（刚发送的弱模型消息）
                conversation_history.append({
                    "role": "assistant" if msg.role == ConversationRole.STRONG_MODEL else "user",
                    "content": msg.content
                })

            # 构建强模型提示
            prompt = f"""你是一个专业的AI助手。一个智能助手向你询问关于任务的问题，请提供专业的回答和指导。

助手的问题：{weak_message}

请根据助手的问题，提供有用的回答和建议。保持专业、详细，并尽可能提供具体的指导。
"""

            # 调用强模型API
            response = await self._call_openai_api(
                model=strong_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                agent=agent
            )

            return response.get("content", "抱歉，我现在无法提供回复。")

        except Exception as e:
            logger.error(f"❌ 生成强模型回复失败: {e}")
            return "抱歉，我现在无法提供详细回复，但我建议你可以继续详细描述你的需求。"

    async def _call_openai_api(self, model: str, messages: List, max_tokens: int = 1000, agent: Dict[str, Any] = None) -> Dict:
        """调用OpenAI API"""
        from ..utils.openai_client import OpenAIClient

        # 使用Agent配置创建客户端
        agent_api_key = None
        agent_base_url = None
        if agent:
            agent_api_key = agent.get('api_key')
            agent_base_url = agent.get('base_url')

        client = OpenAIClient(
            api_key=agent_api_key,
            base_url=agent_base_url,
            model=model
        )
        # 构建task_data以传递参数
        task_data = {
            'max_tokens': max_tokens,
            'temperature': 0.7,
            'tools': [],
            'tool_choice': None
        }
        return await client._call_openai_api_with_messages(
            messages=messages,
            model=model,
            task_data=task_data
        )

    def _build_weak_model_prompt(self, task_description: str, context: Dict[str, Any]) -> str:
        """构建弱模型的分析提示"""
        return f"""
作为一个智能助手，请分析以下任务：

任务描述：{task_description}

上下文信息：{context}

请评估：
1. 你是否能够独立完成这个任务？
2. 这个任务的复杂程度如何？
3. 是否需要与更强的模型进行讨论？

请提供你的初步分析和建议。
"""

    async def handle_conversation_response(
        self,
        session_id: str,
        user_input: str,
        action: str
    ) -> Dict[str, Any]:
        """处理对话中的用户响应"""
        try:
            if action == "continue_conversation":
                # 继续对话
                message_request = SendSimulatorMessageRequest(
                    session_id=session_id,
                    role=ConversationRole.STRONG_MODEL,
                    content=user_input,
                    metadata={
                        "type": "conversation_response",
                        "timestamp": datetime.now().isoformat()
                    }
                )

                await self.conversation_service.send_message(message_request)

                # 让弱模型分析强模型的回复并决定是否继续
                weak_model_decision = await self._weak_model_evaluate_continuation(
                    session_id, user_input
                )

                if weak_model_decision["should_terminate"]:
                    # 弱模型决定终止对话并提交结果
                    decision_request = SimulatorDecisionRequest(
                        session_id=session_id,
                        decision_type=SimulatorDecision.WEAK_MODEL_TERMINATED,
                        result_data=weak_model_decision["final_result"],
                        confidence_score=weak_model_decision.get("confidence", 0.8),
                        decision_reasoning=f"弱模型自主终止：{weak_model_decision['reasoning']}"
                    )

                    execution_result = await self.conversation_service.make_decision(decision_request)

                    return {
                        "status": "completed",
                        "execution_type": "weak_model_terminated",
                        "result": weak_model_decision["final_result"],
                        "execution_result": execution_result.model_dump(),
                        "termination_reason": weak_model_decision["reasoning"]
                    }
                else:
                    # 弱模型决定继续对话，发送继续的消息
                    weak_continue_message = SendSimulatorMessageRequest(
                        session_id=session_id,
                        role=ConversationRole.WEAK_MODEL,
                        content=weak_model_decision["continue_message"],
                        metadata={
                            "type": "weak_model_continuation",
                            "confidence": weak_model_decision.get("confidence", 0.7),
                            "timestamp": datetime.now().isoformat()
                        }
                    )

                    await self.conversation_service.send_message(weak_continue_message)

                    # 获取更新后的会话状态
                    session_response = await self.conversation_service.get_session_with_messages(session_id)

                    return {
                        "status": "conversation_continued",
                        "session": session_response,
                        "next_action": session_response.next_action,
                        "weak_model_analysis": weak_model_decision
                    }

            elif action == "submit_decision":
                # 提交最终决策
                decision_data = {
                    "answer": user_input,
                    "timestamp": datetime.now().isoformat()
                }

                decision_request = SimulatorDecisionRequest(
                    session_id=session_id,
                    decision_type=SimulatorDecision.CONSULT_COMPLETE,
                    result_data=decision_data,
                    confidence_score=0.9,
                    decision_reasoning="经过对话协商后的最终决策"
                )

                execution_result = await self.conversation_service.make_decision(decision_request)

                return {
                    "status": "completed",
                    "execution_type": "conversation_result",
                    "result": decision_data,
                    "execution_result": execution_result.model_dump()
                }

            elif action == "interrupt":
                # 中断对话
                await self.conversation_service.interrupt_session(session_id, "用户中断")

                return {
                    "status": "interrupted",
                    "message": "对话已中断"
                }

        except Exception as e:
            logger.error(f"处理对话响应失败: {e}")
            raise

    async def _weak_model_evaluate_continuation(
        self,
        session_id: str,
        strong_model_response: str
    ) -> Dict[str, Any]:
        """弱模型评估是否应该继续对话"""
        try:
            # 获取当前会话的所有消息
            session_response = await self.conversation_service.get_session_with_messages(session_id)
            messages = session_response.messages

            # 分析对话历史和强模型的最新回复
            conversation_analysis = self._analyze_conversation_progress(messages, strong_model_response)

            # 弱模型决策逻辑
            should_terminate = False
            reasoning = ""
            confidence = 0.0
            final_result = None
            continue_message = ""

            # 检查是否已经获得足够信息
            if conversation_analysis["information_completeness"] > 0.8:
                should_terminate = True
                reasoning = "已获得足够信息完成任务"
                confidence = conversation_analysis["information_completeness"]
                final_result = {
                    "answer": self._synthesize_final_answer(messages, strong_model_response),
                    "conversation_summary": conversation_analysis["summary"],
                    "confidence": confidence
                }

            # 检查对话是否陷入循环
            elif conversation_analysis["is_repetitive"]:
                should_terminate = True
                reasoning = "对话出现重复，无新信息产生"
                confidence = 0.7
                final_result = {
                    "answer": self._synthesize_final_answer(messages, strong_model_response),
                    "conversation_summary": "对话出现重复模式，基于现有信息给出答案",
                    "confidence": confidence
                }

            # 检查强模型回复质量
            elif conversation_analysis["response_quality"] < 0.3:
                should_terminate = True
                reasoning = "强模型回复质量较低，继续对话价值不大"
                confidence = 0.6
                final_result = {
                    "answer": self._synthesize_final_answer(messages, strong_model_response),
                    "conversation_summary": "基于现有对话内容综合分析得出答案",
                    "confidence": confidence
                }

            # 决定继续对话
            else:
                should_terminate = False
                reasoning = "仍需更多信息或澄清"
                confidence = conversation_analysis.get("continuation_confidence", 0.7)
                continue_message = self._generate_follow_up_question(messages, strong_model_response, conversation_analysis)

            return {
                "should_terminate": should_terminate,
                "reasoning": reasoning,
                "confidence": confidence,
                "final_result": final_result,
                "continue_message": continue_message,
                "conversation_analysis": conversation_analysis
            }

        except Exception as e:
            logger.error(f"弱模型评估继续对话失败: {e}")
            # 默认继续对话
            return {
                "should_terminate": False,
                "reasoning": "评估过程出错，默认继续对话",
                "confidence": 0.5,
                "continue_message": "请继续提供更多信息。"
            }

    def _analyze_conversation_progress(self, messages: List, strong_model_response: str) -> Dict[str, Any]:
        """分析对话进展情况"""
        if not messages:
            return {
                "information_completeness": 0.0,
                "is_repetitive": False,
                "response_quality": 0.5,
                "summary": "对话刚开始",
                "continuation_confidence": 0.8
            }

        # 简单的对话分析逻辑
        weak_messages = [m for m in messages if m.role == ConversationRole.WEAK_MODEL]
        strong_messages = [m for m in messages if m.role == ConversationRole.STRONG_MODEL]

        # 信息完整度评估
        total_content_length = sum(len(m.content) for m in messages)
        information_completeness = min(total_content_length / 1000, 1.0)  # 基于内容长度的简单评估

        # 检查重复性
        is_repetitive = self._detect_repetitive_patterns(messages)

        # 强模型回复质量评估
        response_quality = self._evaluate_response_quality(strong_model_response)

        # 对话轮次分析
        round_count = len(weak_messages)
        if round_count >= 5:  # 超过5轮对话，增加终止倾向
            information_completeness += 0.2

        return {
            "information_completeness": min(information_completeness, 1.0),
            "is_repetitive": is_repetitive,
            "response_quality": response_quality,
            "summary": f"已进行{round_count}轮对话，强模型提供了{len(strong_messages)}次回复",
            "continuation_confidence": 0.8 - (round_count * 0.1)  # 轮次越多，继续的信心越低
        }

    def _detect_repetitive_patterns(self, messages: List) -> bool:
        """检测对话是否出现重复模式"""
        if len(messages) < 4:
            return False

        # 简单检测：比较最近的消息是否与之前的消息过于相似
        recent_messages = messages[-4:]
        for i, msg1 in enumerate(recent_messages):
            for j, msg2 in enumerate(recent_messages[i+1:], i+1):
                if msg1.role == msg2.role:
                    # 计算内容相似度（简单的字符串包含检查）
                    content1_words = set(msg1.content.lower().split())
                    content2_words = set(msg2.content.lower().split())
                    if content1_words and content2_words:
                        similarity = len(content1_words & content2_words) / len(content1_words | content2_words)
                        if similarity > 0.7:  # 70%相似度认为重复
                            return True

        return False

    def _evaluate_response_quality(self, response: str) -> float:
        """评估强模型回复的质量"""
        if not response or len(response.strip()) < 10:
            return 0.1

        # 简单的质量评估指标
        quality_score = 0.5  # 基础分数

        # 长度适中加分
        if 50 <= len(response) <= 500:
            quality_score += 0.2

        # 包含问号（提出反问）加分
        if '？' in response or '?' in response:
            quality_score += 0.1

        # 包含具体信息加分
        if any(keyword in response for keyword in ['具体', '详细', '比如', '例如', '说明']):
            quality_score += 0.2

        return min(quality_score, 1.0)

    def _synthesize_final_answer(self, messages: List, latest_response: str) -> str:
        """基于对话历史综合生成最终答案"""
        if not messages:
            return f"基于最新信息：{latest_response}"

        # 收集所有强模型的关键信息
        strong_responses = [m.content for m in messages if m.role == ConversationRole.STRONG_MODEL]
        strong_responses.append(latest_response)

        # 简单的信息综合
        combined_info = " ".join(strong_responses[-3:])  # 使用最近3条强模型回复

        return f"综合对话信息分析：{combined_info[:300]}..."  # 限制长度

    def _generate_follow_up_question(self, messages: List, strong_response: str, analysis: Dict) -> str:
        """生成后续问题"""
        round_count = len([m for m in messages if m.role == ConversationRole.WEAK_MODEL])

        follow_up_questions = [
            "能否提供更具体的细节？",
            "这个方案有什么潜在的问题吗？",
            "还有其他需要考虑的因素吗？",
            "能否举个具体的例子说明？",
            "这个解决方案的可行性如何？"
        ]

        # 根据轮次选择不同的问题
        question_index = min(round_count, len(follow_up_questions) - 1)
        return follow_up_questions[question_index]