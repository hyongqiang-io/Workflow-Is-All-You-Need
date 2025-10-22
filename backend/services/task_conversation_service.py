"""
人类任务AI对话服务
Human Task AI Conversation Service
"""

import uuid
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from ..models.instance import TaskInstanceStatus
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..repositories.conversation.task_conversation_repository import TaskConversationRepository
from ..utils.openai_client import openai_client


class TaskConversationService:
    """人类任务AI对话服务"""

    def __init__(self):
        self.task_repo = TaskInstanceRepository()
        self.conversation_repo = TaskConversationRepository()
        self.openai_client = openai_client

    async def send_message(self, task_id: uuid.UUID, user_id: uuid.UUID,
                          message: str, include_context: bool = True,
                          context_type: str = 'summary') -> Dict[str, Any]:
        """发送消息并获取AI回复"""
        try:
            logger.info(f"🤖 用户 {user_id} 为任务 {task_id} 发送消息")

            # 验证任务权限
            logger.info(f"🔍 开始验证任务权限...")
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")

            if task.get('assigned_user_id') != str(user_id):
                raise PermissionError("无权访问此任务的对话")

            logger.info(f"✅ 任务权限验证通过")

            # 获取或创建对话会话
            logger.info(f"🔗 获取或创建对话会话...")
            try:
                session = await self.conversation_repo.create_or_get_session(task_id, user_id)
                session_id = session['session_id']
                logger.info(f"✅ 会话创建/获取成功: {session_id}")
            except Exception as session_error:
                logger.error(f"❌ 会话创建/获取失败: {session_error}")
                logger.error(f"会话错误类型: {type(session_error)}")
                import traceback
                logger.error(f"会话错误堆栈: {traceback.format_exc()}")
                raise

            # 添加用户消息到数据库
            logger.info(f"💬 添加用户消息到数据库...")
            try:
                await self.conversation_repo.add_message(
                    session_id=session_id,
                    role='user',
                    content=message,
                    context_data=None
                )
                logger.info(f"✅ 用户消息添加成功")
            except Exception as msg_error:
                logger.error(f"❌ 添加用户消息失败: {msg_error}")
                logger.error(f"消息错误类型: {type(msg_error)}")
                import traceback
                logger.error(f"消息错误堆栈: {traceback.format_exc()}")
                raise

            # 准备AI对话的系统提示和上下文
            logger.info(f"🧠 准备AI对话上下文...")
            try:
                system_prompt, context_data = await self._prepare_conversation_context(
                    task, include_context, context_type
                )
                logger.info(f"✅ AI对话上下文准备成功")
            except Exception as context_error:
                logger.error(f"❌ 准备AI对话上下文失败: {context_error}")
                logger.error(f"上下文错误类型: {type(context_error)}")
                import traceback
                logger.error(f"上下文错误堆栈: {traceback.format_exc()}")
                raise

            # 获取历史消息用于AI对话
            logger.info(f"📜 获取历史消息...")
            try:
                recent_messages = await self.conversation_repo.get_session_messages(
                    session_id, limit=20  # 最近20条消息
                )
                logger.info(f"✅ 获取到 {len(recent_messages)} 条历史消息")
            except Exception as history_error:
                logger.error(f"❌ 获取历史消息失败: {history_error}")
                logger.error(f"历史消息错误类型: {type(history_error)}")
                import traceback
                logger.error(f"历史消息错误堆栈: {traceback.format_exc()}")
                raise

            # 构建对话历史
            messages = [{'role': 'system', 'content': system_prompt}]

            # 添加历史消息（限制数量避免token过多）
            for msg in recent_messages[-10:]:  # 最近10条消息
                messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })

            # 调用OpenAI API
            logger.info(f"🤖 调用OpenAI API...")
            try:
                ai_response = await self._call_openai_api(messages)
                logger.info(f"✅ OpenAI API调用成功")
            except Exception as api_error:
                logger.error(f"❌ OpenAI API调用失败: {api_error}")
                logger.error(f"API错误类型: {type(api_error)}")
                import traceback
                logger.error(f"API错误堆栈: {traceback.format_exc()}")
                raise

            # 添加AI回复到数据库
            logger.info(f"💾 添加AI回复到数据库...")
            try:
                ai_message = await self.conversation_repo.add_message(
                    session_id=session_id,
                    role='assistant',
                    content=ai_response,
                    context_data=context_data if include_context else None
                )
                logger.info(f"✅ AI回复添加成功")
            except Exception as ai_msg_error:
                logger.error(f"❌ 添加AI回复失败: {ai_msg_error}")
                logger.error(f"AI回复错误类型: {type(ai_msg_error)}")
                import traceback
                logger.error(f"AI回复错误堆栈: {traceback.format_exc()}")
                raise

            # 获取对话统计
            logger.info(f"📊 获取对话统计...")
            try:
                stats = await self.conversation_repo.get_conversation_stats(task_id)
                logger.info(f"✅ AI对话完成，会话消息总数: {stats.get('message_count', 0)}")
            except Exception as stats_error:
                logger.error(f"❌ 获取对话统计失败: {stats_error}")
                logger.error(f"统计错误类型: {type(stats_error)}")
                import traceback
                logger.error(f"统计错误堆栈: {traceback.format_exc()}")
                # 统计失败不影响主流程，设置默认值
                stats = {'message_count': 0}

            return {
                'message_id': str(ai_message['message_id']),
                'content': ai_response,
                'suggestions': self._extract_suggestions(ai_response),
                'context_used': context_data if include_context else None,
                'conversation_length': stats.get('message_count', 0),
                'session_id': str(session_id)
            }

        except Exception as e:
            logger.error(f"❌ AI对话失败: {e}")
            logger.error(f"主要错误类型: {type(e)}")
            import traceback
            logger.error(f"主要错误堆栈: {traceback.format_exc()}")
            raise

    async def get_conversation_history(self, task_id: uuid.UUID,
                                     user_id: uuid.UUID) -> Dict[str, Any]:
        """获取任务的对话历史"""
        try:
            # 验证任务权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")

            if task.get('assigned_user_id') != str(user_id):
                raise PermissionError("无权访问此任务的对话")

            # 从数据库获取对话历史
            conversation = await self.conversation_repo.get_conversation_history(task_id, user_id)

            # 格式化消息时间戳
            for message in conversation.get('messages', []):
                if message.get('created_at'):
                    message['timestamp'] = message['created_at'].isoformat() if hasattr(message['created_at'], 'isoformat') else message['created_at']

            return conversation

        except Exception as e:
            logger.error(f"❌ 获取对话历史失败: {e}")
            raise

    async def clear_conversation(self, task_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """清空任务的对话历史"""
        try:
            # 验证任务权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")

            if task.get('assigned_user_id') != str(user_id):
                raise PermissionError("无权清空此任务的对话")

            # 从数据库清空对话历史
            result = await self.conversation_repo.clear_conversation(task_id, user_id)

            logger.info(f"🧹 已清空任务 {task_id} 的对话历史")
            return result

        except Exception as e:
            logger.error(f"❌ 清空对话历史失败: {e}")
            raise

    async def get_conversation_stats(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, Any]:
        """获取对话统计信息"""
        try:
            # 验证权限
            task = await self.task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError("任务不存在")

            if task.get('assigned_user_id') != str(user_id):
                raise PermissionError("无权访问此任务的对话统计")

            # 获取统计信息
            stats = await self.conversation_repo.get_conversation_stats(task_id)
            return stats

        except Exception as e:
            logger.error(f"❌ 获取对话统计失败: {e}")
            raise

    async def admin_search_conversations(self, task_title: Optional[str] = None,
                                       user_name: Optional[str] = None,
                                       start_date: Optional[str] = None,
                                       end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """管理员搜索对话记录"""
        try:
            # 这里可以实现复杂的搜索逻辑
            # 暂时返回空列表，实际应该根据参数搜索数据库
            logger.info(f"🔍 管理员搜索对话: task_title={task_title}, user_name={user_name}, "
                       f"start_date={start_date}, end_date={end_date}")

            # TODO: 实现具体的搜索逻辑
            return []

        except Exception as e:
            logger.error(f"❌ 管理员搜索对话失败: {e}")
            raise

    async def get_workflow_conversation_nodes(self, workflow_instance_id: uuid.UUID,
                                            user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流实例中包含对话的节点列表"""
        try:
            logger.info(f"🔍 获取工作流 {workflow_instance_id} 的对话节点")

            # 获取工作流实例的所有任务
            workflow_tasks = await self.task_repo.get_tasks_by_workflow_instance(workflow_instance_id)

            conversation_nodes = []

            for task in workflow_tasks:
                task_id = task.get('task_instance_id')
                if not task_id:
                    continue

                try:
                    # 检查任务是否有对话记录
                    task_uuid = uuid.UUID(task_id)
                    conversation = await self.conversation_repo.get_conversation_history(task_uuid, user_id)

                    if conversation and conversation.get('messages') and len(conversation.get('messages', [])) > 0:
                        # 获取对话统计
                        stats = await self.conversation_repo.get_conversation_stats(task_uuid)

                        node_info = {
                            'task_instance_id': task_id,
                            'node_name': task.get('node_name', '未知节点'),
                            'task_title': task.get('task_title', ''),
                            'task_description': task.get('task_description', ''),
                            'status': task.get('status', ''),
                            'assigned_user_id': task.get('assigned_user_id'),
                            'conversation_stats': {
                                'message_count': stats.get('message_count', 0),
                                'last_message_at': stats.get('last_message_at'),
                                'first_message_at': stats.get('first_message_at')
                            },
                            'recent_messages': conversation.get('messages', [])[-3:] if conversation.get('messages') else []  # 最近3条消息预览
                        }
                        conversation_nodes.append(node_info)

                except Exception as task_error:
                    logger.warning(f"⚠️ 检查任务 {task_id} 对话记录失败: {task_error}")
                    continue

            logger.info(f"✅ 找到 {len(conversation_nodes)} 个包含对话的节点")
            return conversation_nodes

        except Exception as e:
            logger.error(f"❌ 获取工作流对话节点失败: {e}")
            raise

    async def _prepare_conversation_context(self, task: Dict[str, Any],
                                          include_context: bool,
                                          context_type: str) -> tuple[str, Dict[str, Any]]:
        """准备AI对话的上下文信息"""
        try:
            # 基础任务信息
            task_info = {
                'title': task.get('task_title', ''),
                'description': task.get('task_description', ''),
                'type': task.get('task_type', ''),
                'status': task.get('status', ''),
                'instructions': task.get('instructions', '')
            }

            context_data = {'task_info': task_info}

            # 系统提示
            system_prompt = f"""你是一个专业的工作流任务助手，正在帮助用户完成人工任务。

**当前任务信息：**
- 标题：{task_info['title']}
- 描述：{task_info['description']}
- 类型：{task_info['type']}
- 状态：{task_info['status']}

**你的角色：**
1. 帮助用户理解任务要求和上下文数据
2. 提供任务执行建议和指导
3. 协助分析上游节点的输出结果
4. 建议合适的任务完成策略

**回复原则：**
- 简洁明了，直接有用
- 基于任务上下文提供具体建议
- 如果用户询问上游数据，详细解释数据含义
- 提供可执行的操作建议

请根据用户的问题，结合任务上下文，提供专业的帮助。"""

            # 根据context_type添加不同详细程度的上下文
            if include_context:
                if context_type == 'full':
                    # 完整上下文：包含所有上游数据和工作流信息
                    context_data.update(await self._get_full_context(task))
                    system_prompt += f"\n\n**完整上下文数据：**\n{json.dumps(context_data, indent=2, ensure_ascii=False)}"

                elif context_type == 'summary':
                    # 摘要上下文：关键信息概述
                    summary = await self._get_context_summary(task)
                    context_data.update(summary)
                    system_prompt += f"\n\n**上下文摘要：**\n{self._format_context_summary(summary)}"

                elif context_type == 'minimal':
                    # 最小上下文：仅基本任务信息
                    pass

            return system_prompt, context_data

        except Exception as e:
            logger.error(f"❌ 准备对话上下文失败: {e}")
            return f"你是任务助手，请帮助用户完成任务：{task.get('task_title', '未知任务')}", {}

    async def _get_full_context(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """获取完整的任务上下文"""
        try:
            # 暂时简化，避免调用可能有bug的方法
            logger.info("🔧 简化上下文获取，避免时间戳解析错误")

            return {
                'task_basic_info': {
                    'title': task.get('task_title', ''),
                    'description': task.get('task_description', ''),
                    'status': task.get('status', ''),
                    'type': task.get('task_type', '')
                },
                'simplified': True,
                'note': '为避免时间戳解析错误，当前使用简化上下文'
            }

        except Exception as e:
            logger.error(f"❌ 获取完整上下文失败: {e}")
            return {}

    async def _get_context_summary(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """获取上下文摘要"""
        try:
            from ..services.human_task_service import HumanTaskService
            human_service = HumanTaskService()

            upstream_context = await human_service._get_upstream_context(task)

            # 生成摘要
            summary = {
                'upstream_nodes_count': upstream_context.get('upstream_node_count', 0),
                'has_attachments': len(upstream_context.get('context_attachments', [])) > 0,
                'workflow_name': upstream_context.get('workflow_name', ''),
                'key_upstream_outputs': []
            }

            # 提取关键上游输出
            immediate_results = upstream_context.get('immediate_upstream_results', {})
            for node_key, node_data in list(immediate_results.items())[:3]:  # 最多3个
                summary['key_upstream_outputs'].append({
                    'node_name': node_data.get('node_name', node_key),
                    'has_output': bool(node_data.get('output_data')),
                    'summary': human_service._extract_data_summary(node_data.get('output_data', {}))
                })

            return summary

        except Exception as e:
            logger.error(f"❌ 获取上下文摘要失败: {e}")
            return {}

    def _format_context_summary(self, summary: Dict[str, Any]) -> str:
        """格式化上下文摘要为可读文本"""
        try:
            parts = []

            if summary.get('workflow_name'):
                parts.append(f"• 工作流：{summary['workflow_name']}")

            upstream_count = summary.get('upstream_nodes_count', 0)
            if upstream_count > 0:
                parts.append(f"• 上游节点数：{upstream_count}")

                key_outputs = summary.get('key_upstream_outputs', [])
                if key_outputs:
                    parts.append("• 关键上游输出：")
                    for output in key_outputs:
                        status = "有数据" if output['has_output'] else "无数据"
                        parts.append(f"  - {output['node_name']}: {status} ({output['summary']})")

            if summary.get('has_attachments'):
                parts.append("• 包含相关附件")

            return "\n".join(parts) if parts else "无特殊上下文"

        except Exception as e:
            logger.error(f"❌ 格式化上下文摘要失败: {e}")
            return "上下文摘要不可用"

    async def _call_openai_api(self, messages: List[Dict[str, str]]) -> str:
        """调用OpenAI API获取AI回复"""
        try:
            if not self.openai_client:
                return "AI服务暂时不可用，请稍后再试。"

            # 使用现有的openai_client调用方法
            task_data = {
                'temperature': 0.7,
                'max_tokens': 1500,
                'tools': [],  # 不使用工具
                'tool_choice': None
            }

            response = await self.openai_client._call_openai_api_with_messages(
                messages=messages,
                model=self.openai_client.model,  # 使用客户端配置的模型
                task_data=task_data
            )

            # 提取回复内容
            if response and 'content' in response:
                ai_response = response['content']
                logger.info(f"🤖 OpenAI API 调用成功，回复长度: {len(ai_response)}")
                return ai_response
            else:
                logger.error(f"❌ OpenAI API 回复格式异常: {response}")
                return "抱歉，AI服务回复格式异常，请稍后再试。"

        except Exception as e:
            logger.error(f"❌ OpenAI API 调用失败: {e}")
            return f"抱歉，AI服务遇到问题：{str(e)}。请尝试重新表述您的问题。"

    def _extract_suggestions(self, ai_response: str) -> List[str]:
        """从AI回复中提取建议操作"""
        try:
            suggestions = []

            # 简单的关键词匹配提取建议
            if "上传" in ai_response or "附件" in ai_response:
                suggestions.append("上传相关文件")

            if "检查" in ai_response or "验证" in ai_response:
                suggestions.append("检查上游数据")

            if "提交" in ai_response or "完成" in ai_response:
                suggestions.append("提交任务结果")

            if "询问" in ai_response or "联系" in ai_response:
                suggestions.append("寻求帮助")

            return suggestions[:3]  # 最多3个建议

        except Exception as e:
            logger.error(f"❌ 提取建议失败: {e}")
            return []