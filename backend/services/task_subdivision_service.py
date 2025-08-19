"""
任务细分服务
Task Subdivision Service
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
from ..repositories.task_subdivision.task_subdivision_repository import (
    TaskSubdivisionRepository, WorkflowAdoptionRepository
)
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..services.workflow_service import WorkflowService
from ..services.node_service import NodeService
from ..services.execution_service import execution_engine
from ..utils.helpers import now_utc
from ..utils.exceptions import ValidationError


class TaskSubdivisionService:
    """任务细分服务"""
    
    def __init__(self):
        self.subdivision_repo = TaskSubdivisionRepository()
        self.adoption_repo = WorkflowAdoptionRepository()
        self.task_repo = TaskInstanceRepository()
        self.workflow_service = WorkflowService()
        self.node_service = NodeService()
        
        # 🔒 添加应用层锁，防止并发重复创建
        self._subdivision_locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()  # 保护locks字典本身
    
    async def create_task_subdivision(self, subdivision_data: TaskSubdivisionCreate,
                                    execute_immediately: bool = False) -> TaskSubdivisionResponse:
        """
        创建任务细分（带重复创建防护和应用层锁）
        
        Args:
            subdivision_data: 细分数据
            execute_immediately: 是否立即执行子工作流
            
        Returns:
            创建的细分响应
        """
        # 🔧 防护机制1：使用应用层锁防止竞态条件
        lock_key = f"{subdivision_data.original_task_id}_{subdivision_data.subdivider_id}_{subdivision_data.subdivision_name}"
        
        # 获取或创建锁
        async with self._locks_lock:
            if lock_key not in self._subdivision_locks:
                self._subdivision_locks[lock_key] = asyncio.Lock()
            lock = self._subdivision_locks[lock_key]
        
        async with lock:
            try:
                logger.info(f"🔄 开始创建任务细分: {subdivision_data.subdivision_name}")
                
                # 在锁内检查是否已存在相同的细分记录
                existing_subdivision_query = """
                SELECT subdivision_id, status FROM task_subdivision 
                WHERE original_task_id = %s AND subdivider_id = %s 
                AND subdivision_name = %s AND status IN ('created', 'executing', 'completed')
                LIMIT 1
                """
                existing_subdivision = await self.subdivision_repo.db.fetch_one(
                    existing_subdivision_query, 
                    subdivision_data.original_task_id,
                    subdivision_data.subdivider_id,
                    subdivision_data.subdivision_name
                )
                
                if existing_subdivision:
                    logger.warning(f"🛡️ 发现重复的细分请求: {subdivision_data.subdivision_name}")
                    logger.warning(f"   已存在细分ID: {existing_subdivision['subdivision_id']}")
                    logger.warning(f"   状态: {existing_subdivision['status']}")
                    
                    # 返回已存在的细分记录
                    subdivision_record = await self.subdivision_repo.get_subdivision_by_id(
                        existing_subdivision['subdivision_id']
                    )
                    if subdivision_record:
                        return await self._format_subdivision_response(subdivision_record)
                
                # 继续正常的创建流程...
                return await self._create_subdivision_internal(subdivision_data, execute_immediately)
                
            except Exception as e:
                logger.error(f"创建任务细分失败: {e}")
                raise
            finally:
                # 清理锁（可选，防止内存泄漏）
                async with self._locks_lock:
                    if lock_key in self._subdivision_locks:
                        # 如果当前没有其他协程在等待这个锁，就删除它
                        if not lock.locked():
                            del self._subdivision_locks[lock_key]
    
    async def _create_subdivision_internal(self, subdivision_data: TaskSubdivisionCreate,
                                         execute_immediately: bool = False) -> TaskSubdivisionResponse:
        """内部创建细分方法（无锁版本）"""
        try:
            original_task = await self.task_repo.get_task_by_id(subdivision_data.original_task_id)
            if not original_task:
                raise ValidationError("原始任务不存在")
            
            # 调试信息：输出任务分配和当前用户信息
            # logger.info(f"🔍 任务权限验证调试:")
            # logger.info(f"   - 任务ID: {subdivision_data.original_task_id}")
            # logger.info(f"   - 任务分配用户ID: {original_task.get('assigned_user_id')}")
            # logger.info(f"   - 当前用户ID: {subdivision_data.subdivider_id}")
            # logger.info(f"   - 任务状态: {original_task.get('status')}")
            # logger.info(f"   - 任务标题: {original_task.get('task_title')}")
            
            # 添加类型调试信息
            assigned_user_id = original_task.get('assigned_user_id')
            current_user_id = subdivision_data.subdivider_id
            logger.info(f"🔬 类型调试:")
            # logger.info(f"   - 任务分配用户ID类型: {type(assigned_user_id)}")
            # logger.info(f"   - 当前用户ID类型: {type(current_user_id)}")
            # logger.info(f"   - 任务分配用户ID值: {repr(assigned_user_id)}")
            # logger.info(f"   - 当前用户ID值: {repr(current_user_id)}")
            # logger.info(f"   - 相等比较: {assigned_user_id == current_user_id}")
            # logger.info(f"   - 字符串比较: {str(assigned_user_id) == str(current_user_id)}")
            
            # 修复类型不匹配问题：将两个值都转换为字符串进行比较
            if str(original_task.get('assigned_user_id')) != str(subdivision_data.subdivider_id):
                raise ValidationError("只能细分分配给自己的任务")
            
            # 2. 创建细分记录
            subdivision_record = await self.subdivision_repo.create_subdivision(subdivision_data)
            if not subdivision_record:
                raise ValueError("创建细分记录失败")
            
            subdivision_id = subdivision_record['subdivision_id']
            
            # 3. 创建或使用已有的子工作流
            if subdivision_data.sub_workflow_base_id:
                # 使用前端已创建的工作流
                logger.info(f"🔄 使用前端已创建的工作流: {subdivision_data.sub_workflow_base_id}")
                sub_workflow = await self.workflow_service.get_workflow_by_base_id(subdivision_data.sub_workflow_base_id)
                if not sub_workflow:
                    raise ValueError(f"指定的工作流不存在: {subdivision_data.sub_workflow_base_id}")
                    
                logger.info(f"✅ 找到预创建的工作流: {sub_workflow.name}")
                
                # 4. 为已有工作流添加节点和连接
                await self._create_subdivision_nodes_and_connections(
                    subdivision_data.sub_workflow_base_id,
                    subdivision_data.sub_workflow_data,
                    subdivision_data.subdivider_id,
                    subdivision_data.context_to_pass  # 传递任务上下文
                )
                
                sub_workflow_base_id = subdivision_data.sub_workflow_base_id
            else:
                # ⚠️ 这种情况不应该发生，因为前端应该总是预创建工作流
                logger.warning(f"⚠️ 前端没有预创建工作流，后端将创建新工作流")
                logger.warning(f"   这可能表明前端工作流创建失败或ID传递有问题")
                
                # 创建新的子工作流（仅基础信息）
                logger.info(f"🔄 后端创建新的子工作流")
                sub_workflow_create = WorkflowCreate(
                    name=subdivision_data.subdivision_name,  # 🔧 使用细分名称作为工作流名称
                    description=f"从任务 '{original_task.get('task_title', '')}' 细分而来\n\n{subdivision_data.subdivision_description}",
                    creator_id=subdivision_data.subdivider_id
                )
                
                sub_workflow = await self.workflow_service.create_workflow(sub_workflow_create)
                
                # 4. 创建子工作流的节点和连接
                await self._create_subdivision_nodes_and_connections(
                    sub_workflow.workflow_base_id,
                    subdivision_data.sub_workflow_data,
                    subdivision_data.subdivider_id,
                    subdivision_data.context_to_pass  # 传递任务上下文
                )
                
                sub_workflow_base_id = sub_workflow.workflow_base_id
            
            # 4. 更新细分记录的工作流ID
            await self.subdivision_repo.update_subdivision_workflow_ids(
                subdivision_id, sub_workflow_base_id
            )
            
            # 5. 更新细分的任务上下文
            await self.subdivision_repo.update_subdivision_task_context(
                subdivision_id, original_task.get('task_description', '')
            )
            
            # 6. 如果需要立即执行，启动子工作流实例
            sub_workflow_instance_id = None
            if execute_immediately:
                sub_workflow_instance_id = await self._execute_sub_workflow(
                    subdivision_id, sub_workflow_base_id, 
                    subdivision_data.subdivider_id, subdivision_data.context_to_pass
                )
            
            logger.info(f"✅ 任务细分创建成功: {subdivision_id}")
            
            # 7. 返回响应
            return await self._format_subdivision_response(subdivision_record, {
                'original_task_title': original_task.get('task_title'),
                'sub_workflow_name': sub_workflow.name if hasattr(sub_workflow, 'name') else subdivision_data.subdivision_name,
                'sub_workflow_base_id': sub_workflow_base_id,  # 使用统一的变量
                'sub_workflow_instance_id': sub_workflow_instance_id
            })
            
        except Exception as e:
            logger.error(f"创建任务细分失败: {e}")
            raise
    
    async def _execute_sub_workflow(self, subdivision_id: uuid.UUID, 
                                  sub_workflow_base_id: uuid.UUID,
                                  executor_id: uuid.UUID, 
                                  context_data: str) -> uuid.UUID:
        """执行子工作流（带重复执行防护）"""
        try:
            logger.info(f"🚀 启动子工作流执行: {sub_workflow_base_id}")
            logger.info(f"   上下文数据: {context_data[:100]}..." if context_data else "   无上下文数据")
            
            # 🔧 防护机制1：检查是否已有工作流实例
            existing_instance_query = """
            SELECT wi.workflow_instance_id, wi.status
            FROM workflow_instance wi
            WHERE wi.workflow_base_id = %s
            AND wi.workflow_instance_name LIKE %s
            AND wi.status IN ('running', 'pending', 'completed')
            ORDER BY wi.created_at DESC
            LIMIT 1
            """
            
            existing_instances = await self.workflow_service.workflow_repository.db.fetch_all(
                existing_instance_query,
                sub_workflow_base_id,
                f"细分执行_{subdivision_id}%"
            )
            
            if existing_instances:
                existing_instance = existing_instances[0]
                existing_instance_id = existing_instance['workflow_instance_id']
                existing_status = existing_instance['status']
                
                logger.warning(f"🛡️ 发现已存在的工作流实例: {existing_instance_id}")
                logger.warning(f"   状态: {existing_status}, 细分ID: {subdivision_id}")
                
                # 如果实例正在运行或已完成，直接返回
                if existing_status in ['running', 'pending', 'completed']:
                    logger.warning(f"   返回已存在的实例，跳过重复创建")
                    return uuid.UUID(str(existing_instance_id))
            
            # 构造执行请求
            from ..models.instance import WorkflowExecuteRequest
            execute_request = WorkflowExecuteRequest(
                workflow_base_id=sub_workflow_base_id,
                workflow_instance_name=f"细分执行_{subdivision_id}",
                input_data={},
                context_data={
                    "subdivision_context": context_data,
                    "subdivision_id": str(subdivision_id),
                    "execution_type": "task_subdivision"
                }
            )
            
            # 🛡️ 保护父工作流上下文：创建快照
            # 获取细分记录以获得原始任务ID
            subdivision_record = await self.subdivision_repo.get_subdivision_by_id(subdivision_id)
            if subdivision_record:
                original_task_id = subdivision_record['original_task_id']
                parent_workflow_id = await self._get_parent_workflow_id(original_task_id)
            else:
                parent_workflow_id = None
                logger.warning(f"⚠️ 无法获取细分记录: {subdivision_id}")
            parent_context_snapshot = None
            
            if parent_workflow_id:
                from .workflow_execution_context import get_context_manager
                context_manager = get_context_manager()
                parent_context_snapshot = await context_manager.create_context_snapshot(parent_workflow_id)
                logger.info(f"🔒 已创建父工作流上下文快照: {parent_workflow_id}")
            
            try:
                # 执行工作流
                result = await execution_engine.execute_workflow(execute_request, executor_id)
                
                logger.info(f"🔍 执行引擎返回结果: {result}")
                logger.info(f"🔍 结果类型: {type(result)}")
            finally:
                # 🔄 恢复父工作流上下文（无论子工作流是否成功）
                if parent_workflow_id and parent_context_snapshot:
                    try:
                        await context_manager.restore_from_snapshot(parent_workflow_id, parent_context_snapshot)
                        logger.info(f"✅ 已恢复父工作流上下文: {parent_workflow_id}")
                    except Exception as restore_error:
                        logger.error(f"❌ 恢复父工作流上下文失败: {restore_error}")
                        # 尝试从数据库恢复
                        try:
                            await context_manager._restore_context_from_database(parent_workflow_id)
                            logger.info(f"🔧 从数据库恢复父工作流上下文成功: {parent_workflow_id}")
                        except Exception as db_restore_error:
                            logger.error(f"❌ 从数据库恢复父工作流上下文也失败: {db_restore_error}")
            
            
            # 处理不同的返回格式
            instance_id = None
            if result:
                if isinstance(result, dict):
                    if 'instance_id' in result:
                        instance_id = uuid.UUID(result['instance_id'])
                    elif 'workflow_instance_id' in result:
                        instance_id = uuid.UUID(result['workflow_instance_id'])
                elif hasattr(result, 'workflow_instance_id'):
                    instance_id = result.workflow_instance_id
                elif isinstance(result, str):
                    try:
                        instance_id = uuid.UUID(result)
                    except ValueError:
                        logger.error(f"无法将字符串转换为UUID: {result}")
            
            if instance_id:
                # 更新细分记录的实例ID
                await self.subdivision_repo.update_subdivision_workflow_ids(
                    subdivision_id, sub_workflow_base_id, instance_id
                )
                
                # 注册工作流完成回调，用于自动提交结果给父工作流
                await self._register_subdivision_completion_callback(
                    subdivision_id, instance_id, executor_id
                )
                
                logger.info(f"✅ 子工作流启动成功: {instance_id}")
                return instance_id
            else:
                logger.error(f"❌ 无法从执行结果中提取实例ID: {result}")
                raise ValueError("子工作流启动失败")
                
        except Exception as e:
            logger.error(f"执行子工作流失败: {e}")
            raise
    
    async def _register_subdivision_completion_callback(self, subdivision_id: uuid.UUID, 
                                                       workflow_instance_id: uuid.UUID,
                                                       executor_id: uuid.UUID):
        """注册细分工作流完成回调"""
        try:
            logger.info(f"🔔 注册细分工作流完成回调: {workflow_instance_id}")
            
            # 导入监控服务来注册回调
            from ..services.monitoring_service import monitoring_service
            
            # 创建回调函数
            async def subdivision_completion_callback(instance_id: uuid.UUID, final_status: str, results: dict):
                await self._handle_subdivision_completion(
                    subdivision_id, instance_id, final_status, results, executor_id
                )
            
            # 注册到监控服务
            await monitoring_service.register_workflow_completion_callback(
                workflow_instance_id, subdivision_completion_callback
            )
            
            logger.info(f"✅ 细分工作流完成回调注册成功: {workflow_instance_id}")
            
        except Exception as e:
            logger.error(f"注册细分工作流完成回调失败: {e}")
            # 不抛出异常，避免影响主流程
    
    async def _handle_subdivision_completion(self, subdivision_id: uuid.UUID,
                                           workflow_instance_id: uuid.UUID,
                                           final_status: str,
                                           results: dict,
                                           executor_id: uuid.UUID):
        """处理细分工作流完成事件"""
        try:
            logger.info(f"🎯 处理细分工作流完成事件: {subdivision_id}")
            logger.info(f"   - 工作流实例ID: {workflow_instance_id}")
            logger.info(f"   - 最终状态: {final_status}")
            logger.info(f"   - 结果数据: {len(str(results))} 字符")
            
            # 获取细分信息
            subdivision = await self.subdivision_repo.get_subdivision_by_id(subdivision_id)
            if not subdivision:
                logger.error(f"未找到细分记录: {subdivision_id}")
                return
            
            original_task_id = subdivision['original_task_id']
            
            # 更新细分状态
            if final_status == 'completed':
                await self._update_subdivision_status(subdivision_id, 'completed', results)
                
                # 🔧 修改：仅保存结果供用户参考，不自动提交任务
                await self._save_subdivision_results_for_reference(
                    original_task_id, subdivision_id, results, executor_id
                )
            elif final_status in ['failed', 'timeout']:
                await self._update_subdivision_status(subdivision_id, 'failed', results)
                logger.error(f"细分工作流执行失败: {subdivision_id}, 状态: {final_status}")
            
        except Exception as e:
            logger.error(f"处理细分工作流完成事件失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
    
    async def _update_subdivision_status(self, subdivision_id: uuid.UUID, 
                                       status: str, results: dict):
        """更新细分状态"""
        try:
            from ..models.task_subdivision import TaskSubdivisionStatus
            
            # 构建结果摘要
            result_summary = self._generate_result_summary(results)
            
            # 转换字符串状态为枚举
            if status == 'completed':
                status_enum = TaskSubdivisionStatus.COMPLETED
            elif status == 'failed':
                status_enum = TaskSubdivisionStatus.FAILED
            elif status == 'executing':
                status_enum = TaskSubdivisionStatus.EXECUTING
            else:
                status_enum = TaskSubdivisionStatus.CREATED
            
            # 更新细分记录状态
            await self.subdivision_repo.update_subdivision_status(subdivision_id, status_enum)
            
            # 单独更新结果摘要（如果需要的话）
            if result_summary:
                update_data = {
                    'result_summary': result_summary,
                    'completed_at': now_utc() if status == 'completed' else None
                }
                await self.subdivision_repo.update(subdivision_id, update_data, id_column="subdivision_id")
            
            logger.info(f"✅ 更新细分状态成功: {subdivision_id} -> {status}")
            
        except Exception as e:
            logger.error(f"更新细分状态失败: {e}")
    
    def _serialize_for_json(self, obj):
        """JSON序列化助手函数，处理datetime等对象"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        elif isinstance(obj, dict):
            return {key: self._serialize_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_json(item) for item in obj]
        else:
            return obj
    
    async def _save_subdivision_results_for_reference(self, original_task_id: uuid.UUID,
                                                     subdivision_id: uuid.UUID,
                                                     results: dict,
                                                     executor_id: uuid.UUID):
        """保存细分工作流结果作为用户参考，不自动提交任务"""
        try:
            logger.info(f"💾 保存细分结果供用户参考: {original_task_id}")
            
            # 清理results中的datetime对象，确保可以JSON序列化
            clean_results = self._serialize_for_json(results)
            
            # 生成结果数据
            result_data = {
                'subdivision_id': str(subdivision_id),
                'execution_results': clean_results,
                'completion_time': now_utc().isoformat(),
                'executed_by': str(executor_id),
                'is_reference_data': True,  # 标记为参考数据
                'auto_submitted': False     # 未自动提交
            }
            
            # 格式化为可读文本
            formatted_output = self._format_subdivision_output(clean_results)
            
            # 导入任务仓库来更新任务上下文
            from ..repositories.instance.task_instance_repository import TaskInstanceRepository
            from ..models.instance import TaskInstanceUpdate
            
            task_repo = TaskInstanceRepository()
            
            # 仅更新context_data和instructions，不改变任务状态
            task_update = TaskInstanceUpdate(
                context_data=json.dumps(result_data, ensure_ascii=False, indent=2),
                instructions=f"细分工作流已完成，结果可作为提交参考。\n\n【参考结果】:\n{formatted_output}"
            )
            
            # 更新任务上下文（不改变状态）
            updated_task = await task_repo.update_task(original_task_id, task_update)
            
            if updated_task:
                logger.info(f"✅ 细分结果已保存供用户参考: {original_task_id}")
                logger.info(f"   - 任务状态: {updated_task.get('status')} (保持不变)")
                logger.info(f"   - 用户可在任务详情中查看细分结果并手动提交")
                
                # 🔧 重要修复：细分工作流完成后应该更新父节点实例状态
                # 即使任务状态保持不变（供用户手动提交），节点实例也应该标记为完成
                # 这样后续节点才能被触发
                try:
                    await self._update_parent_node_instance_status(original_task_id, formatted_output)
                    logger.info(f"✅ 父节点实例状态更新完成")
                except Exception as node_update_error:
                    logger.error(f"❌ 更新父节点实例状态失败: {node_update_error}")
                    import traceback
                    logger.error(f"节点状态更新错误详情: {traceback.format_exc()}")
            else:
                logger.error(f"❌ 保存细分结果失败: {original_task_id}")
            
        except Exception as e:
            logger.error(f"❌ 保存细分结果失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
    
    async def _update_parent_node_instance_status(self, original_task_id: uuid.UUID, output_data: str):
        """更新父节点实例状态为已完成"""
        try:
            logger.info(f"🔄 开始更新父节点实例状态: 任务 {original_task_id}")
            
            # 1. 通过任务ID获取节点实例ID
            from ..repositories.instance.task_instance_repository import TaskInstanceRepository
            task_repo = TaskInstanceRepository()
            
            task_info = await task_repo.get_task_by_id(original_task_id)
            if not task_info:
                logger.error(f"❌ 无法找到原始任务: {original_task_id}")
                return
            
            node_instance_id = task_info.get('node_instance_id')
            workflow_instance_id = task_info.get('workflow_instance_id')
            
            if not node_instance_id:
                logger.error(f"❌ 任务 {original_task_id} 没有关联的节点实例")
                return
            
            logger.info(f"   - 节点实例ID: {node_instance_id}")
            logger.info(f"   - 工作流实例ID: {workflow_instance_id}")
            
            # 2. 检查节点的所有任务是否都已完成
            node_tasks = await task_repo.get_tasks_by_node_instance(uuid.UUID(node_instance_id))
            if not node_tasks:
                logger.warning(f"⚠️ 节点实例 {node_instance_id} 没有关联的任务")
                return
            
            # 统计任务状态
            total_tasks = len(node_tasks)
            completed_tasks = [task for task in node_tasks if task.get('status') == 'completed']
            failed_tasks = [task for task in node_tasks if task.get('status') == 'failed']
            
            logger.info(f"   - 节点任务统计: 总计 {total_tasks}, 完成 {len(completed_tasks)}, 失败 {len(failed_tasks)}")
            
            # 3. 检查是否应该更新节点实例状态
            # 对于细分工作流完成的情况，即使原任务还未手动提交，也应该更新节点状态
            # 因为细分工作流的完成意味着节点的工作已经完成，只是等待用户确认
            should_update_node = False
            
            if len(completed_tasks) == total_tasks and len(failed_tasks) == 0:
                # 所有任务都已完成的标准情况
                should_update_node = True
                logger.info(f"🎯 节点 {node_instance_id} 的所有任务都已完成，更新节点状态")
            elif len(completed_tasks) == total_tasks - 1 and len(failed_tasks) == 0:
                # 细分工作流完成的特殊情况：只有一个任务未完成但有细分结果
                incomplete_tasks = [task for task in node_tasks if task.get('status') not in ['completed', 'failed']]
                if len(incomplete_tasks) == 1:
                    incomplete_task = incomplete_tasks[0]
                    # 检查这个未完成的任务是否有细分结果（即当前正在处理的任务）
                    if str(incomplete_task.get('task_instance_id')) == str(original_task_id):
                        should_update_node = True
                        logger.info(f"🎯 节点 {node_instance_id} 的细分工作流已完成，更新节点状态（任务等待手动提交）")
                        
            if should_update_node:
                
                # 导入节点实例相关模块
                from ..repositories.instance.node_instance_repository import NodeInstanceRepository
                from ..models.instance import NodeInstanceUpdate, NodeInstanceStatus
                
                node_instance_repo = NodeInstanceRepository()
                
                # 准备节点更新数据
                node_update = NodeInstanceUpdate(
                    status=NodeInstanceStatus.COMPLETED,
                    output_data={
                        'subdivision_result': output_data,
                        'completed_by': 'task_subdivision',
                        'completion_time': now_utc().isoformat()
                    },
                    completed_at=now_utc()
                )
                
                # 更新节点实例状态
                updated_node = await node_instance_repo.update_node_instance(
                    uuid.UUID(node_instance_id), node_update
                )
                
                if updated_node:
                    logger.info(f"✅ 节点实例状态更新成功: {node_instance_id}")
                    logger.info(f"   - 新状态: COMPLETED")
                    logger.info(f"   - 输出数据长度: {len(output_data)} 字符")
                    
                    # 4. 通知执行引擎检查工作流是否可以继续执行
                    await self._notify_workflow_engine_node_completion(
                        uuid.UUID(workflow_instance_id), uuid.UUID(node_instance_id)
                    )
                    
                else:
                    logger.error(f"❌ 节点实例状态更新失败: {node_instance_id}")
            else:
                logger.info(f"ℹ️ 节点 {node_instance_id} 还有未完成的任务，暂不更新节点状态")
                
        except Exception as e:
            logger.error(f"❌ 更新父节点实例状态失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
    
    async def _notify_workflow_engine_node_completion(self, workflow_instance_id: uuid.UUID, node_instance_id: uuid.UUID):
        """通知工作流执行引擎节点已完成"""
        try:
            logger.info(f"📢 通知执行引擎节点完成: 工作流 {workflow_instance_id}, 节点 {node_instance_id}")
            
            # 导入执行引擎
            from ..services.execution_service import execution_engine
            
            # 触发工作流状态检查，让执行引擎检查是否有新的节点可以执行
            await execution_engine._check_workflow_completion(workflow_instance_id)
            
            logger.info(f"✅ 已通知执行引擎检查工作流状态: {workflow_instance_id}")
            
        except Exception as e:
            logger.error(f"❌ 通知执行引擎失败: {e}")
            # 这个失败不影响主流程，只记录错误
    
    def _generate_result_summary(self, results: dict) -> str:
        """生成结果摘要"""
        try:
            if not results:
                return "细分工作流执行完成，无输出数据"
            
            # 统计任务完成情况
            total_tasks = results.get('total_tasks', 0)
            completed_tasks = results.get('completed_tasks', 0)
            
            summary_parts = [
                f"细分工作流执行完成",
                f"总任务数: {total_tasks}",
                f"完成任务数: {completed_tasks}"
            ]
            
            if 'final_output' in results:
                final_output = str(results['final_output'])
                if final_output:
                    summary_parts.append(f"最终输出: {final_output[:100]}...")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"生成结果摘要失败: {e}")
            return "细分工作流执行完成"
    
    def _format_subdivision_output(self, results: dict) -> str:
        """格式化细分工作流输出为文本"""
        try:
            if not results:
                return "细分工作流执行完成，但没有生成输出数据。"
            
            logger.info(f"🎨 格式化细分工作流输出，结果数据键: {list(results.keys())}")
            
            output_parts = [f"=== {results.get('workflow_instance_id', '子工作流')} 执行结果 ===\n"]
            
            # 基本统计信息
            if 'total_tasks' in results:
                output_parts.append(f"📊 执行统计:")
                output_parts.append(f"   • 总任务数: {results.get('total_tasks', 0)}")
                output_parts.append(f"   • 完成任务数: {results.get('completed_tasks', 0)}")
                output_parts.append(f"   • 失败任务数: {results.get('failed_tasks', 0)}")
                output_parts.append(f"   • 执行时长: {results.get('execution_duration', 'N/A')}")
                output_parts.append("")
            
            # 🔧 增强：主要输出结果（优先显示结束节点的完整输出）
            final_output = results.get('final_output', '')
            has_end_node_output = results.get('has_end_node_output', False)
            
            if final_output:
                if has_end_node_output:
                    output_parts.append("📋 工作流最终结果（来自结束节点）:")
                else:
                    output_parts.append("📋 工作流最终结果（来自任务输出）:")
                
                # 如果是长文本，进行适当的格式化
                if len(final_output) > 1000:
                    # 显示前500字符和后200字符
                    output_parts.append(final_output[:500])
                    output_parts.append("\n... [内容过长，已省略部分内容] ...\n")
                    output_parts.append(final_output[-200:])
                else:
                    output_parts.append(final_output)
                output_parts.append("")
            
            # 🔧 增强：如果没有详细的最终输出，显示各个任务的详细结果
            if not final_output or len(final_output) < 50:
                if 'task_results' in results and isinstance(results['task_results'], list):
                    completed_task_results = [t for t in results['task_results'] if t.get('status') == 'completed']
                    
                    if completed_task_results:
                        output_parts.append("📝 已完成任务的详细结果:")
                        for i, task_result in enumerate(completed_task_results, 1):
                            if isinstance(task_result, dict):
                                task_title = task_result.get('title', f'任务 {i}')
                                task_output = task_result.get('output', '无输出')
                                task_summary = task_result.get('result_summary', '')
                                
                                output_parts.append(f"   {i}. **{task_title}**")
                                
                                if task_summary:
                                    output_parts.append(f"      摘要: {task_summary}")
                                
                                if task_output and task_output != '无输出':
                                    # 限制单个任务输出的长度
                                    if len(str(task_output)) > 300:
                                        truncated_output = str(task_output)[:300] + "... [已截断]"
                                        output_parts.append(f"      结果: {truncated_output}")
                                    else:
                                        output_parts.append(f"      结果: {task_output}")
                                
                                output_parts.append("")
                            else:
                                output_parts.append(f"   {i}. {str(task_result)}")
                        output_parts.append("")
            
            # 执行状态和时间信息
            status = results.get('status', 'unknown')
            if status == 'completed':
                output_parts.append("✅ 细分工作流已成功完成所有任务。")
            elif status == 'failed':
                output_parts.append("❌ 细分工作流执行失败。")
            else:
                output_parts.append(f"ℹ️ 细分工作流状态: {status}")
            
            # 时间信息
            started_at = results.get('started_at')
            completed_at = results.get('completed_at')
            if started_at:
                output_parts.append(f"🕐 开始时间: {started_at}")
            if completed_at:
                output_parts.append(f"🕐 完成时间: {completed_at}")
            
            formatted_output = "\n".join(output_parts)
            logger.info(f"✅ 细分工作流输出格式化完成，总长度: {len(formatted_output)} 字符")
            
            return formatted_output
            
        except Exception as e:
            logger.error(f"格式化细分工作流输出失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return f"细分工作流执行完成，但输出格式化失败: {str(e)}"
    
    async def get_task_subdivisions(self, task_id: uuid.UUID) -> List[TaskSubdivisionResponse]:
        """获取任务的所有细分"""
        try:
            subdivisions = await self.subdivision_repo.get_subdivisions_by_task(task_id)
            
            return [
                await self._format_subdivision_response(subdivision)
                for subdivision in subdivisions
            ]
            
        except Exception as e:
            logger.error(f"获取任务细分列表失败: {e}")
            raise
    
    async def get_subdivision_workflow_instance(self, subdivision_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取细分的子工作流实例信息"""
        try:
            logger.info(f"📊 获取细分子工作流实例信息: {subdivision_id}")
            
            # 获取细分记录
            subdivision = await self.subdivision_repo.get_subdivision_by_id(subdivision_id)
            if not subdivision:
                logger.warning(f"未找到细分记录: {subdivision_id}")
                return None
            
            # 获取子工作流实例ID
            sub_workflow_instance_id = subdivision.get('sub_workflow_instance_id')
            if not sub_workflow_instance_id:
                logger.warning(f"细分没有关联的子工作流实例: {subdivision_id}")
                return None
            
            # 从工作流实例仓库获取实例信息
            from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
            workflow_instance_repo = WorkflowInstanceRepository()
            
            workflow_instance = await workflow_instance_repo.get_instance_by_id(
                uuid.UUID(sub_workflow_instance_id)
            )
            
            if workflow_instance:
                logger.info(f"✅ 找到子工作流实例: {sub_workflow_instance_id}")
                logger.info(f"   - 实例名称: {workflow_instance.get('workflow_instance_name')}")
                logger.info(f"   - 状态: {workflow_instance.get('status')}")
                return workflow_instance
            else:
                logger.warning(f"未找到子工作流实例: {sub_workflow_instance_id}")
                return None
            
        except Exception as e:
            logger.error(f"获取细分子工作流实例失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return None
    
    async def get_workflow_subdivisions(self, workflow_base_id: uuid.UUID) -> WorkflowSubdivisionsResponse:
        """获取工作流相关的所有细分（用于预览）"""
        try:
            # 获取工作流信息
            workflow = await self.workflow_service.get_workflow_by_base_id(workflow_base_id)
            if not workflow:
                raise ValidationError("工作流不存在")
            
            # 获取相关细分
            subdivisions = await self.subdivision_repo.get_subdivisions_by_workflow(workflow_base_id)
            
            # 格式化响应
            subdivision_previews = []
            for subdivision in subdivisions:
                total_nodes = subdivision.get('total_sub_nodes', 0)
                completed_nodes = subdivision.get('completed_sub_nodes', 0)
                success_rate = (completed_nodes / total_nodes * 100) if total_nodes > 0 else None
                
                preview = SubdivisionPreviewResponse(
                    subdivision_id=subdivision['subdivision_id'],
                    subdivision_name=subdivision['subdivision_name'],
                    subdivider_name=subdivision.get('subdivider_name', '未知'),
                    status=TaskSubdivisionStatus(subdivision['status']),
                    sub_workflow_name=subdivision.get('sub_workflow_name', ''),
                    total_nodes=total_nodes,
                    completed_nodes=completed_nodes,
                    success_rate=success_rate,
                    created_at=subdivision['subdivision_created_at'].isoformat(),
                    completed_at=subdivision['completed_at'].isoformat() if subdivision.get('completed_at') else None
                )
                subdivision_previews.append(preview)
            
            return WorkflowSubdivisionsResponse(
                workflow_base_id=workflow_base_id,
                workflow_name=workflow.name,
                subdivisions=subdivision_previews,
                total_count=len(subdivision_previews),
                completed_count=len([s for s in subdivision_previews if s.status == TaskSubdivisionStatus.COMPLETED])
            )
            
        except Exception as e:
            logger.error(f"获取工作流细分预览失败: {e}")
            raise
    
    async def adopt_subdivision(self, adoption_data: WorkflowAdoptionCreate) -> WorkflowAdoptionResponse:
        """
        采纳子工作流到原始工作流
        
        Args:
            adoption_data: 采纳数据
            
        Returns:
            采纳响应
        """
        try:
            logger.info(f"🔄 开始采纳子工作流: {adoption_data.subdivision_id}")
            
            # 1. 验证细分存在且已完成
            subdivision = await self.subdivision_repo.get_subdivision_by_id(adoption_data.subdivision_id)
            if not subdivision:
                raise ValidationError("细分不存在")
            
            if subdivision['status'] != TaskSubdivisionStatus.COMPLETED.value:
                raise ValidationError("只能采纳已完成的细分")
            
            # 2. 验证目标节点存在且属于指定工作流
            target_node = await self.node_service.get_node_by_id(adoption_data.target_node_id)
            if not target_node:
                raise ValidationError("目标节点不存在")
            
            # 3. 获取子工作流的节点定义
            sub_workflow_nodes = await self.node_service.get_workflow_nodes(
                subdivision['sub_workflow_base_id'], adoption_data.adopter_id
            )
            
            # 4. 在目标节点位置添加子工作流的节点
            new_node_ids = await self._add_subdivision_nodes_to_workflow(
                adoption_data.original_workflow_base_id,
                adoption_data.target_node_id,
                sub_workflow_nodes,
                adoption_data.adoption_name,
                adoption_data.adopter_id
            )
            
            # 5. 创建采纳记录
            adoption_record = await self.adoption_repo.create_adoption(adoption_data, new_node_ids)
            if not adoption_record:
                raise ValueError("创建采纳记录失败")
            
            logger.info(f"✅ 子工作流采纳成功，新增 {len(new_node_ids)} 个节点")
            
            # 6. 返回响应
            return WorkflowAdoptionResponse(
                adoption_id=adoption_record['adoption_id'],
                subdivision_id=adoption_data.subdivision_id,
                subdivision_name=subdivision.get('subdivision_name'),
                adopter_id=adoption_data.adopter_id,
                adopter_name=None,  # 可以从用户信息获取
                adoption_name=adoption_data.adoption_name,
                target_node_id=adoption_data.target_node_id,
                new_nodes_count=len(new_node_ids),
                adopted_at=adoption_record['adopted_at'].isoformat()
            )
            
        except Exception as e:
            logger.error(f"采纳子工作流失败: {e}")
            raise
    
    async def _add_subdivision_nodes_to_workflow(self, target_workflow_base_id: uuid.UUID,
                                               target_node_id: uuid.UUID,
                                               sub_nodes: List[Any],
                                               adoption_name: str,
                                               adopter_id: uuid.UUID) -> List[uuid.UUID]:
        """将子工作流的节点添加到目标工作流"""
        try:
            # 这里是具体的节点添加逻辑
            # 实际实现需要：
            # 1. 将子工作流的节点复制到目标工作流
            # 2. 重新映射节点连接关系
            # 3. 将原目标节点替换为节点群
            
            logger.info(f"🔄 开始添加 {len(sub_nodes)} 个节点到工作流")
            
            new_node_ids = []
            
            # 简化实现：直接在目标节点后添加子工作流节点
            for i, sub_node in enumerate(sub_nodes):
                from ..models.node import NodeCreate
                
                new_node_create = NodeCreate(
                    workflow_base_id=target_workflow_base_id,
                    creator_id=adopter_id,
                    name=f"{adoption_name}_{i+1}",
                    type=sub_node.type,
                    task_description=sub_node.task_description,
                    position_x=sub_node.position_x + 100,  # 偏移位置
                    position_y=sub_node.position_y + 100
                )
                
                new_node = await self.node_service.create_node(new_node_create, adopter_id)
                new_node_ids.append(new_node.node_base_id)
            
            logger.info(f"✅ 成功添加 {len(new_node_ids)} 个节点")
            return new_node_ids
            
        except Exception as e:
            logger.error(f"添加子工作流节点失败: {e}")
            raise
    
    async def _create_subdivision_nodes_and_connections(self, 
                                                       workflow_base_id: uuid.UUID,
                                                       sub_workflow_data: Dict[str, Any], 
                                                       creator_id: uuid.UUID,
                                                       task_context: str = "") -> None:
        """创建细分工作流的节点和连接（带重复创建防护）"""
        try:
            logger.info(f"🔄 开始为工作流 {workflow_base_id} 创建节点和连接")
            logger.info(f"📋 任务上下文数据长度: {len(task_context)} 字符")
            
            # 🔧 防护机制1：检查工作流是否已有节点
            existing_nodes_query = "SELECT COUNT(*) as node_count FROM node WHERE workflow_base_id = %s"
            existing_nodes_result = await self.node_service.node_repository.db.fetch_one(
                existing_nodes_query, workflow_base_id
            )
            existing_node_count = existing_nodes_result.get('node_count', 0) if existing_nodes_result else 0
            
            if existing_node_count > 0:
                logger.warning(f"🛡️ 工作流 {workflow_base_id} 已有 {existing_node_count} 个节点，跳过重复创建")
                return
            
            # 从细分数据中提取节点和连接信息
            nodes_data = sub_workflow_data.get('nodes', [])
            connections_data = sub_workflow_data.get('connections', [])
            
            if not nodes_data:
                logger.warning("没有节点数据，跳过节点创建")
                return
            
            logger.info(f"📦 准备创建 {len(nodes_data)} 个节点和 {len(connections_data)} 个连接")
            
            # 1. 创建节点
            node_id_mapping = {}  # 用于映射前端ID到后端ID
            created_nodes = []
            
            for node_data in nodes_data:
                try:
                    # 导入节点创建模型
                    from ..models.node import NodeCreate
                    
                    # 特殊处理开始节点，将任务上下文信息注入到开始节点
                    task_description = node_data.get('task_description', '')
                    if node_data.get('type') == 'start' and task_context:
                        # 将任务上下文信息注入到开始节点的任务描述中
                        task_description = f"{task_description}\n\n--- 任务上下文信息 ---\n{task_context}"
                        logger.info(f"✅ 已将任务上下文注入到开始节点: {node_data.get('name', '开始节点')}")
                    
                    # 创建节点数据
                    node_create = NodeCreate(
                        workflow_base_id=workflow_base_id,
                        name=node_data.get('name', '未命名节点'),
                        type=node_data.get('type', 'processor'),
                        task_description=task_description,
                        position_x=float(node_data.get('position_x', 0)),
                        position_y=float(node_data.get('position_y', 0)),
                        processor_id=node_data.get('processor_id')  # 添加processor_id
                    )
                    
                    # 调用节点服务创建节点
                    created_node = await self.node_service.create_node(node_create, creator_id)
                    
                    if created_node:
                        frontend_id = node_data.get('node_base_id') or node_data.get('id')
                        node_id_mapping[frontend_id] = created_node.node_base_id
                        created_nodes.append(created_node)
                        logger.debug(f"   ✅ 节点创建成功: {created_node.name} ({frontend_id} -> {created_node.node_base_id})")
                    else:
                        logger.error(f"   ❌ 节点创建失败: {node_data.get('name')}")
                        
                except Exception as e:
                    logger.error(f"创建节点失败: {node_data.get('name', '未知')}, 错误: {e}")
                    # 继续创建其他节点，不中断整个流程
                    continue
            
            logger.info(f"✅ 成功创建 {len(created_nodes)} 个节点")
            
            # 2. 创建连接
            if connections_data and len(created_nodes) > 1:
                created_connections = 0
                
                for connection_data in connections_data:
                    try:
                        # 导入连接创建模型
                        from ..models.node import NodeConnectionCreate
                        
                        # 获取映射后的节点ID - 修复字段名匹配
                        from_node_frontend_id = connection_data.get('from_node_id') or connection_data.get('from')
                        to_node_frontend_id = connection_data.get('to_node_id') or connection_data.get('to')
                        
                        logger.debug(f"   🔗 处理连接: {from_node_frontend_id} -> {to_node_frontend_id}")
                        
                        from_node_id = node_id_mapping.get(from_node_frontend_id)
                        to_node_id = node_id_mapping.get(to_node_frontend_id)
                        
                        if not from_node_id or not to_node_id:
                            logger.warning(f"连接跳过，节点ID映射失败: {from_node_frontend_id} -> {to_node_frontend_id}")
                            logger.warning(f"   可用映射: {list(node_id_mapping.keys())}")
                            continue
                        
                        # 创建连接数据
                        connection_create = NodeConnectionCreate(
                            from_node_base_id=from_node_id,
                            to_node_base_id=to_node_id,
                            workflow_base_id=workflow_base_id,
                            connection_type=connection_data.get('connection_type', 'normal')
                        )
                        
                        # 调用节点服务创建连接
                        created_connection = await self.node_service.create_node_connection(connection_create, creator_id)
                        
                        if created_connection:
                            created_connections += 1
                            logger.debug(f"   ✅ 连接创建成功: {from_node_id} -> {to_node_id}")
                        else:
                            logger.error(f"   ❌ 连接创建失败: {from_node_id} -> {to_node_id}")
                            
                    except Exception as e:
                        logger.error(f"创建连接失败: {connection_data}, 错误: {e}")
                        # 继续创建其他连接
                        continue
                
                logger.info(f"✅ 成功创建 {created_connections} 个连接")
            else:
                logger.info("没有连接数据或节点不足，跳过连接创建")
            
            logger.info(f"🎉 工作流 {workflow_base_id} 的节点和连接创建完成，任务上下文已注入到开始节点")
            
        except Exception as e:
            logger.error(f"创建细分工作流节点和连接失败: {e}")
            # 这里可以考虑添加回滚逻辑，删除已创建的节点
            raise
    
    async def _format_subdivision_response(self, subdivision: Dict[str, Any], 
                                         extra_data: Optional[Dict[str, Any]] = None) -> TaskSubdivisionResponse:
        """格式化细分响应"""
        extra_data = extra_data or {}
        
        total_nodes = subdivision.get('total_sub_nodes', 0)
        completed_nodes = subdivision.get('completed_sub_nodes', 0)
        
        # 🔧 修复：处理sub_workflow_base_id为None的情况
        sub_workflow_base_id = extra_data.get('sub_workflow_base_id') or subdivision.get('sub_workflow_base_id')
        if sub_workflow_base_id is None:
            # 如果没有工作流ID，生成一个默认的UUID（这通常不应该发生，但为了防护）
            import uuid
            sub_workflow_base_id = uuid.uuid4()
            logger.warning(f"⚠️ 细分记录 {subdivision['subdivision_id']} 缺少sub_workflow_base_id，使用默认值: {sub_workflow_base_id}")
        
        sub_workflow_instance_id = extra_data.get('sub_workflow_instance_id') or subdivision.get('sub_workflow_instance_id')
        
        return TaskSubdivisionResponse(
            subdivision_id=subdivision['subdivision_id'],
            original_task_id=subdivision['original_task_id'],
            original_task_title=extra_data.get('original_task_title') or subdivision.get('original_task_title'),
            subdivider_id=subdivision['subdivider_id'],
            subdivider_name=subdivision.get('subdivider_name'),
            sub_workflow_base_id=sub_workflow_base_id,
            sub_workflow_instance_id=sub_workflow_instance_id,
            subdivision_name=subdivision['subdivision_name'],
            subdivision_description=subdivision['subdivision_description'],
            status=TaskSubdivisionStatus(subdivision['status']),
            parent_task_description=subdivision.get('parent_task_description', ''),
            context_passed=subdivision.get('context_passed', ''),
            subdivision_created_at=subdivision['subdivision_created_at'].isoformat(),
            completed_at=subdivision['completed_at'].isoformat() if subdivision.get('completed_at') else None,
            sub_workflow_name=extra_data.get('sub_workflow_name') or subdivision.get('sub_workflow_name'),
            total_sub_nodes=total_nodes,
            completed_sub_nodes=completed_nodes
        )
    
    async def _get_parent_workflow_id(self, task_id: uuid.UUID) -> Optional[uuid.UUID]:
        """获取任务所属的父工作流实例ID"""
        try:
            # 通过任务ID获取对应的工作流实例ID
            task = await self.task_repo.get_task_by_id(task_id)
            if task:
                return task.get('workflow_instance_id')
            return None
        except Exception as e:
            logger.error(f"获取父工作流ID失败: {e}")
            return None


# 创建任务细分服务实例
task_subdivision_service = TaskSubdivisionService()