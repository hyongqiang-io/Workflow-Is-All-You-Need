"""
任务细分服务 - 重构版本
Task Subdivision Service - Refactored Version

核心思想：
1. 分离模板(Template)和实例(Instance)
2. 用户可以选择现有工作流模板或创建新模板
3. 一个模板可以多次执行，每次执行创建一个实例
4. API保持兼容，内部逻辑简化
"""

import uuid
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from loguru import logger

from ..models.task_subdivision import (
    TaskSubdivisionCreate, TaskSubdivisionResponse, TaskSubdivisionStatus,
    WorkflowAdoptionCreate, WorkflowAdoptionResponse,
    SubdivisionPreviewResponse, WorkflowSubdivisionsResponse
)
from ..models.workflow import WorkflowCreate
from ..repositories.task_subdivision.task_subdivision_repository import TaskSubdivisionRepository
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..services.workflow_service import WorkflowService
from ..services.node_service import NodeService
from ..services.execution_service import execution_engine
from ..utils.helpers import now_utc
from ..utils.exceptions import ValidationError


class TaskSubdivisionService:
    """任务细分服务 - 重构版本"""
    
    def __init__(self):
        self.subdivision_repo = TaskSubdivisionRepository()
        self.task_repo = TaskInstanceRepository()
        self.workflow_service = WorkflowService()
        self.node_service = NodeService()
    
    async def create_task_subdivision(self, subdivision_data: TaskSubdivisionCreate,
                                    execute_immediately: bool = False) -> TaskSubdivisionResponse:
        """
        创建任务细分 - 重构版本
        
        核心逻辑：
        1. 如果用户提供了工作流模板ID，使用现有模板
        2. 如果没有，根据sub_workflow_data创建新模板（一次）
        3. 创建细分记录，关联到模板
        4. 如果需要执行，从模板创建实例执行
        """
        try:
            logger.info(f"🔄 开始创建任务细分: {subdivision_data.subdivision_name}")
            
            # 1. 验证原始任务
            original_task = await self.task_repo.get_task_by_id(subdivision_data.original_task_id)
            if not original_task:
                raise ValidationError("原始任务不存在")
            
            # 权限检查
            if str(original_task.get('assigned_user_id')) != str(subdivision_data.subdivider_id):
                raise ValidationError("只能细分分配给自己的任务")
            
            # 2. 验证父级细分（如果提供）- 链式细分支持
            if subdivision_data.parent_subdivision_id:
                parent_subdivision = await self.subdivision_repo.get_subdivision_by_id(subdivision_data.parent_subdivision_id)
                if not parent_subdivision:
                    raise ValidationError("父级细分不存在")
                
                # 检查权限：只能在自己创建的细分下创建子级
                if str(parent_subdivision.get('subdivider_id')) != str(subdivision_data.subdivider_id):
                    raise ValidationError("只能在自己创建的细分下创建子级细分")
                
                # 防止循环引用：不能将细分设为自己的父级
                if str(parent_subdivision.get('subdivision_id')) == str(subdivision_data.original_task_id):
                    raise ValidationError("不能创建循环引用的细分")
                
                logger.info(f"✅ 父级细分验证通过: {parent_subdivision.get('subdivision_name')}")
            
            # 3. 处理工作流模板 - 这是关键改进
            template_id = await self._get_or_create_workflow_template(
                subdivision_data.sub_workflow_base_id,
                subdivision_data.sub_workflow_data,
                subdivision_data.subdivision_name,
                subdivision_data.subdivider_id,
                subdivision_data.context_to_pass
            )
            
            # 3. 创建细分记录
            subdivision_record = await self.subdivision_repo.create_subdivision(subdivision_data)
            if not subdivision_record:
                raise ValueError("创建细分记录失败")
            
            subdivision_id = subdivision_record['subdivision_id']
            
            # 4. 更新细分记录的工作流模板ID
            await self.subdivision_repo.update_subdivision_workflow_ids(
                subdivision_id, template_id
            )
            
            # 5. 如果需要立即执行，创建工作流实例
            instance_id = None
            if execute_immediately:
                instance_id = await self._execute_workflow_template(
                    template_id, subdivision_id, subdivision_data.subdivider_id, 
                    subdivision_data.context_to_pass
                )
                
                # 更新细分记录的实例ID
                if instance_id:
                    await self.subdivision_repo.update_subdivision_workflow_ids(
                        subdivision_id, template_id, instance_id
                    )
            
            logger.info(f"✅ 任务细分创建成功: {subdivision_id}")
            
            # 6. 返回响应
            return await self._format_subdivision_response(subdivision_record, {
                'original_task_title': original_task.get('task_title'),
                'sub_workflow_base_id': template_id,
                'sub_workflow_instance_id': instance_id
            })
            
        except Exception as e:
            logger.error(f"创建任务细分失败: {e}")
            raise
    
    async def _get_or_create_workflow_template(self, 
                                             provided_template_id: Optional[uuid.UUID],
                                             workflow_data: Dict[str, Any],
                                             subdivision_name: str,
                                             creator_id: uuid.UUID,
                                             context: str) -> uuid.UUID:
        """
        获取或创建工作流模板
        
        这是关键改进：明确分离模板获取和创建逻辑
        """
        # 情况1：用户选择了现有工作流模板
        if provided_template_id:
            logger.info(f"🔄 使用用户选择的工作流模板: {provided_template_id}")
            
            # 验证模板存在且有权限访问
            template = await self.workflow_service.get_workflow_by_base_id(provided_template_id)
            if not template:
                raise ValidationError(f"指定的工作流模板不存在: {provided_template_id}")
            
            # 验证模板是否有有效内容（至少有非start/end节点）
            node_count_result = await self.node_service.node_repository.db.fetch_one(
                "SELECT COUNT(*) as count FROM node WHERE workflow_base_id = %s AND is_deleted = FALSE AND type NOT IN ('start', 'end')",
                provided_template_id
            )
            node_count = node_count_result.get('count', 0) if node_count_result else 0
            
            if node_count == 0:
                logger.warning(f"⚠️ 选择的工作流模板 {template.name} 没有有效节点")
                raise ValidationError(f"选择的工作流模板 '{template.name}' 是空模板，请选择包含有效节点的工作流模板或创建新模板")
            else:
                logger.info(f"✅ 找到现有工作流模板: {template.name} (包含 {node_count} 个有效节点)")
                return provided_template_id
        
        # 情况2：创建新的工作流模板
        logger.info(f"🔄 创建新的工作流模板: {subdivision_name}")
        
        # 验证工作流数据是否有效
        nodes_data = workflow_data.get('nodes', [])
        if not nodes_data:
            raise ValidationError("创建新工作流模板需要提供有效的节点数据，请在工作流设计器中添加节点后再提交")
        
        # 创建工作流模板
        template_create = WorkflowCreate(
            name=subdivision_name,
            description=f"任务细分工作流模板 - {subdivision_name}",
            creator_id=creator_id
        )
        
        template = await self.workflow_service.create_workflow(template_create)
        template_id = template.workflow_base_id
        
        # 为新模板创建节点和连接
        await self._create_template_nodes_and_connections(
            template_id, workflow_data, creator_id, context
        )
        
        logger.info(f"✅ 新工作流模板创建成功: {template_id}")
        return template_id
    
    async def _execute_workflow_template(self, 
                                       template_id: uuid.UUID,
                                       subdivision_id: uuid.UUID,
                                       executor_id: uuid.UUID,
                                       context: str) -> Optional[uuid.UUID]:
        """
        执行工作流模板，创建新实例
        
        这是另一个关键改进：每次执行都是从模板创建新实例
        """
        try:
            logger.info(f"🚀 从模板创建工作流实例: {template_id}")
            
            # 构造执行请求
            from ..models.instance import WorkflowExecuteRequest
            execute_request = WorkflowExecuteRequest(
                workflow_base_id=template_id,
                workflow_instance_name=f"细分执行_{subdivision_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                input_data={},
                context_data={
                    "subdivision_context": context,
                    "subdivision_id": str(subdivision_id),
                    "execution_type": "task_subdivision"
                }
            )
            
            # 执行工作流（从模板创建实例）
            result = await execution_engine.execute_workflow(execute_request, executor_id)
            
            # 提取实例ID
            instance_id = self._extract_instance_id(result)
            
            if instance_id:
                # 注册完成回调
                await self._register_completion_callback(subdivision_id, instance_id, executor_id)
                logger.info(f"✅ 工作流实例创建并启动成功: {instance_id}")
                return instance_id
            else:
                logger.error(f"❌ 无法从执行结果中提取实例ID: {result}")
                return None
                
        except Exception as e:
            logger.error(f"执行工作流模板失败: {e}")
            raise
    
    async def _create_template_nodes_and_connections(self, 
                                                   template_id: uuid.UUID,
                                                   workflow_data: Dict[str, Any], 
                                                   creator_id: uuid.UUID,
                                                   context: str = "") -> None:
        """为工作流模板创建节点和连接"""
        try:
            logger.info(f"🔄 为模板 {template_id} 创建节点和连接")
            
            # 检查是否已有节点（防止重复创建）
            existing_nodes_query = "SELECT COUNT(*) as node_count FROM node WHERE workflow_base_id = %s"
            existing_nodes_result = await self.node_service.node_repository.db.fetch_one(
                existing_nodes_query, template_id
            )
            existing_node_count = existing_nodes_result.get('node_count', 0) if existing_nodes_result else 0
            
            if existing_node_count > 0:
                logger.warning(f"🛡️ 模板 {template_id} 已有 {existing_node_count} 个节点，跳过创建")
                return
            
            nodes_data = workflow_data.get('nodes', [])
            connections_data = workflow_data.get('connections', [])
            
            if not nodes_data:
                logger.warning("没有节点数据，跳过节点创建")
                return
            
            logger.info(f"📦 准备创建 {len(nodes_data)} 个节点和 {len(connections_data)} 个连接")
            
            # 创建节点
            node_id_mapping = {}
            for node_data in nodes_data:
                try:
                    from ..models.node import NodeCreate
                    
                    # 对开始节点注入上下文
                    task_description = node_data.get('task_description', '')
                    if node_data.get('type') == 'start' and context:
                        task_description = f"{task_description}\n\n--- 任务上下文 ---\n{context}"
                    
                    node_create = NodeCreate(
                        workflow_base_id=template_id,
                        name=node_data.get('name', '未命名节点'),
                        type=node_data.get('type', 'processor'),
                        task_description=task_description,
                        position_x=float(node_data.get('position_x', 0)),
                        position_y=float(node_data.get('position_y', 0)),
                        processor_id=node_data.get('processor_id')
                    )
                    
                    created_node = await self.node_service.create_node(node_create, creator_id)
                    
                    if created_node:
                        frontend_id = node_data.get('node_base_id') or node_data.get('id')
                        node_id_mapping[frontend_id] = created_node.node_base_id
                        logger.debug(f"   ✅ 节点创建成功: {created_node.name}")
                        
                except Exception as e:
                    logger.error(f"创建节点失败: {node_data.get('name', '未知')}, 错误: {e}")
                    continue
            
            # 创建连接
            if connections_data and len(node_id_mapping) > 1:
                for connection_data in connections_data:
                    try:
                        from ..models.node import NodeConnectionCreate
                        
                        from_node_frontend_id = connection_data.get('from_node_id') or connection_data.get('from')
                        to_node_frontend_id = connection_data.get('to_node_id') or connection_data.get('to')
                        
                        from_node_id = node_id_mapping.get(from_node_frontend_id)
                        to_node_id = node_id_mapping.get(to_node_frontend_id)
                        
                        if not from_node_id or not to_node_id:
                            logger.warning(f"连接跳过，节点ID映射失败: {from_node_frontend_id} -> {to_node_frontend_id}")
                            continue
                        
                        connection_create = NodeConnectionCreate(
                            from_node_base_id=from_node_id,
                            to_node_base_id=to_node_id,
                            workflow_base_id=template_id,
                            connection_type=connection_data.get('connection_type', 'normal')
                        )
                        
                        await self.node_service.create_node_connection(connection_create, creator_id)
                        
                    except Exception as e:
                        logger.error(f"创建连接失败: {connection_data}, 错误: {e}")
                        continue
            
            logger.info(f"🎉 模板 {template_id} 的节点和连接创建完成")
            
        except Exception as e:
            logger.error(f"创建模板节点和连接失败: {e}")
            raise
    
    def _extract_instance_id(self, result) -> Optional[uuid.UUID]:
        """从执行结果中提取实例ID"""
        if not result:
            return None
            
        try:
            if isinstance(result, dict):
                if 'instance_id' in result:
                    return uuid.UUID(result['instance_id'])
                elif 'workflow_instance_id' in result:
                    return uuid.UUID(result['workflow_instance_id'])
            elif hasattr(result, 'workflow_instance_id'):
                return result.workflow_instance_id
            elif isinstance(result, str):
                return uuid.UUID(result)
        except (ValueError, TypeError):
            logger.error(f"无法解析实例ID: {result}")
            
        return None
    
    async def _register_completion_callback(self, subdivision_id: uuid.UUID, 
                                          instance_id: uuid.UUID,
                                          executor_id: uuid.UUID):
        """注册工作流完成回调"""
        try:
            from ..services.monitoring_service import monitoring_service
            
            async def completion_callback(instance_id: uuid.UUID, status: str, results: dict):
                await self._handle_completion(subdivision_id, instance_id, status, results, executor_id)
            
            await monitoring_service.register_workflow_completion_callback(
                instance_id, completion_callback
            )
            
        except Exception as e:
            logger.error(f"注册完成回调失败: {e}")
    
    async def _handle_completion(self, subdivision_id: uuid.UUID,
                               instance_id: uuid.UUID,
                               status: str,
                               results: dict,
                               executor_id: uuid.UUID):
        """处理工作流完成事件"""
        try:
            logger.info(f"🎯 处理细分工作流完成: {subdivision_id}")
            
            # 获取细分信息
            subdivision = await self.subdivision_repo.get_subdivision_by_id(subdivision_id)
            if not subdivision:
                return
            
            original_task_id = subdivision['original_task_id']
            
            # 更新细分状态
            if status == 'completed':
                await self._update_subdivision_status(subdivision_id, 'completed', results)
                await self._save_results_to_task(original_task_id, subdivision_id, results, executor_id)
            else:
                await self._update_subdivision_status(subdivision_id, 'failed', results)
            
        except Exception as e:
            logger.error(f"处理完成事件失败: {e}")
    
    async def _update_subdivision_status(self, subdivision_id: uuid.UUID, 
                                       status: str, results: dict):
        """更新细分状态"""
        try:
            status_enum = TaskSubdivisionStatus.COMPLETED if status == 'completed' else TaskSubdivisionStatus.FAILED
            await self.subdivision_repo.update_subdivision_status(subdivision_id, status_enum)
            
        except Exception as e:
            logger.error(f"更新细分状态失败: {e}")
    
    async def _save_results_to_task(self, task_id: uuid.UUID,
                                  subdivision_id: uuid.UUID,
                                  results: dict,
                                  executor_id: uuid.UUID):
        """保存结果到原始任务并触发工作流继续执行"""
        try:
            from ..models.instance import TaskInstanceUpdate
            
            # 生成结构化的结果数据
            result_data = {
                'type': 'subdivision_result',
                'subdivision_id': str(subdivision_id),
                'final_output': results.get('final_output', ''),
                'execution_summary': {
                    'status': results.get('status', 'unknown'),
                    'total_tasks': results.get('total_tasks', 0),
                    'completed_tasks': results.get('completed_tasks', 0),
                    'failed_tasks': results.get('failed_tasks', 0)
                },
                'completion_time': now_utc().isoformat(),
                'auto_submitted': False  # 自动提交subdivision结果
            }
            
            # 🔧 关键修复：标记原始任务为已完成并触发工作流继续执行
            task_update = TaskInstanceUpdate(
                # status=TaskInstanceStatus.COMPLETED,  # 标记任务为已完成
                output_data=json.dumps(result_data, ensure_ascii=False, indent=2),
                instructions="细分工作流已完成，结果已自动提交。",
                # completed_at=now_utc()  # 设置完成时间
            )
            
            await self.task_repo.update_task(task_id, task_update)
            logger.info(f"✅ 细分结果已保存到任务并标记为完成: {task_id}")
            
            # 🔧 关键修复：获取任务的节点实例信息并触发工作流继续执行
            # task_info = await self.task_repo.get_task_by_id(task_id)
            # if task_info:
            #     node_instance_id = task_info['node_instance_id']
            #     workflow_instance_id = task_info['workflow_instance_id']
                
            #     # 更新节点实例状态为已完成
            #     from ..repositories.instance.node_instance_repository import NodeInstanceRepository
            #     node_repo = NodeInstanceRepository()
            #     await node_repo.update_node_status(node_instance_id, 'completed')
            #     logger.info(f"✅ 节点实例状态已更新为完成: {node_instance_id}")
                
            #     # 🔧 关键修复：触发执行引擎检查下游节点，这是之前缺失的步骤！
            #     from ..services.execution_service import execution_engine
            #     await execution_engine._check_downstream_nodes_for_task_creation(workflow_instance_id)
                
            #     # 检查工作流完成状态
            #     await execution_engine._check_workflow_completion(workflow_instance_id)
                
            #     logger.info(f"🎯 subdivision完成后已触发下游节点检查和工作流继续执行")
            
        except Exception as e:
            logger.error(f"保存结果到任务失败: {e}")
            import traceback
            logger.error(f"错误堆栈: {traceback.format_exc()}")
    
    # ============ 保持兼容性的方法 ============
    
    async def get_task_subdivisions(self, task_id: uuid.UUID) -> List[TaskSubdivisionResponse]:
        """获取任务的所有细分 - 兼容接口"""
        subdivisions = await self.subdivision_repo.get_subdivisions_by_task(task_id)
        return [await self._format_subdivision_response(subdivision) for subdivision in subdivisions]
    
    async def get_subdivision_workflow_instance(self, subdivision_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取细分的子工作流实例信息 - 兼容接口"""
        subdivision = await self.subdivision_repo.get_subdivision_by_id(subdivision_id)
        if not subdivision:
            return None
            
        instance_id = subdivision.get('sub_workflow_instance_id')
        if not instance_id:
            return None
            
        from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        workflow_instance_repo = WorkflowInstanceRepository()
        
        return await workflow_instance_repo.get_instance_by_id(uuid.UUID(instance_id))
    
    async def _format_subdivision_response(self, subdivision: Dict[str, Any], 
                                         extra_data: Optional[Dict[str, Any]] = None) -> TaskSubdivisionResponse:
        """格式化细分响应 - 兼容接口"""
        extra_data = extra_data or {}
        
        sub_workflow_base_id = extra_data.get('sub_workflow_base_id') or subdivision.get('sub_workflow_base_id')
        if sub_workflow_base_id is None:
            sub_workflow_base_id = uuid.uuid4()  # 防护措施
            
        return TaskSubdivisionResponse(
            subdivision_id=subdivision['subdivision_id'],
            original_task_id=subdivision['original_task_id'],
            original_task_title=extra_data.get('original_task_title'),
            subdivider_id=subdivision['subdivider_id'],
            subdivider_name=subdivision.get('subdivider_name'),
            sub_workflow_base_id=sub_workflow_base_id,
            sub_workflow_instance_id=extra_data.get('sub_workflow_instance_id') or subdivision.get('sub_workflow_instance_id'),
            subdivision_name=subdivision['subdivision_name'],
            subdivision_description=subdivision['subdivision_description'],
            status=TaskSubdivisionStatus(subdivision['status']),
            parent_task_description=subdivision.get('parent_task_description', ''),
            context_passed=subdivision.get('context_passed', ''),
            subdivision_created_at=subdivision['subdivision_created_at'].isoformat(),
            completed_at=subdivision['completed_at'].isoformat() if subdivision.get('completed_at') else None,
            sub_workflow_name=extra_data.get('sub_workflow_name'),
            total_sub_nodes=subdivision.get('total_sub_nodes', 0),
            completed_sub_nodes=subdivision.get('completed_sub_nodes', 0)
        )
    
    def _format_subdivision_output(self, workflow_results: dict) -> str:
        """格式化细分工作流输出为可读文本"""
        try:
            if not workflow_results:
                return "子工作流尚未产生任何输出结果。"
            
            # 提取关键信息
            status = workflow_results.get('status', 'unknown')
            final_output = workflow_results.get('final_output', '')
            total_tasks = workflow_results.get('total_tasks', 0)
            completed_tasks = workflow_results.get('completed_tasks', 0)
            failed_tasks = workflow_results.get('failed_tasks', 0)
            
            # 构建格式化输出
            formatted_lines = []
            formatted_lines.append("=== 子工作流执行结果 ===")
            formatted_lines.append(f"执行状态: {status}")
            
            if total_tasks > 0:
                formatted_lines.append(f"任务统计: 总计 {total_tasks} 个任务，已完成 {completed_tasks} 个，失败 {failed_tasks} 个")
            
            if final_output:
                formatted_lines.append("\n=== 最终输出 ===")
                formatted_lines.append(final_output)
            
            # 如果有任务执行详情
            if workflow_results.get('task_outputs'):
                formatted_lines.append("\n=== 任务执行详情 ===")
                for i, task_output in enumerate(workflow_results.get('task_outputs', []), 1):
                    if isinstance(task_output, dict):
                        task_title = task_output.get('task_title', f'任务 {i}')
                        task_result = task_output.get('result_data', task_output.get('output_data', ''))
                        formatted_lines.append(f"{i}. {task_title}")
                        if task_result:
                            # 限制每个任务结果的长度
                            result_preview = str(task_result)[:300]
                            if len(str(task_result)) > 300:
                                result_preview += "..."
                            formatted_lines.append(f"   结果: {result_preview}")
                        formatted_lines.append("")
            
            formatted_lines.append("=== 结果结束 ===")
            
            return "\n".join(formatted_lines)
            
        except Exception as e:
            logger.error(f"格式化细分输出失败: {e}")
            return f"格式化输出时出现错误: {str(e)}"


# 创建重构后的服务实例
task_subdivision_service = TaskSubdivisionService()