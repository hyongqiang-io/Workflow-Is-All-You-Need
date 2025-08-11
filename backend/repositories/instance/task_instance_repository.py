"""
任务实例数据访问层
Task Instance Repository
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ..base import BaseRepository
from ...models.instance import (
    TaskInstance, TaskInstanceCreate, TaskInstanceUpdate, 
    TaskInstanceStatus, TaskInstanceType
)
from ...utils.helpers import now_utc


class TaskInstanceRepository(BaseRepository[TaskInstance]):
    """任务实例数据访问层"""
    
    def __init__(self):
        super().__init__("task_instance")
    
    async def create_task(self, task_data: TaskInstanceCreate) -> Optional[Dict[str, Any]]:
        """创建任务实例"""
        try:
            task_instance_id = uuid.uuid4()
            logger.info(f"🚀 开始创建任务实例")
            logger.info(f"   任务标题: {task_data.task_title}")
            logger.info(f"   任务类型: {task_data.task_type.value}")
            logger.info(f"   任务ID: {task_instance_id}")
            logger.info(f"   节点实例ID: {task_data.node_instance_id}")
            logger.info(f"   工作流实例ID: {task_data.workflow_instance_id}")
            logger.info(f"   处理器ID: {task_data.processor_id}")
            logger.info(f"   预估时长: {task_data.estimated_duration}分钟")
            
            # 记录分配信息
            if task_data.assigned_user_id:
                logger.info(f"   📝 分配给用户: {task_data.assigned_user_id}")
            elif task_data.assigned_agent_id:
                logger.info(f"   🤖 分配给代理: {task_data.assigned_agent_id}")
            else:
                logger.info(f"   ⏳ 任务未分配，状态为PENDING")
            
            # 验证任务分配的一致性
            self._validate_task_assignment(task_data)
            
            # 智能确定任务状态：如果有分配对象，则状态为ASSIGNED，否则为PENDING
            initial_status = TaskInstanceStatus.PENDING.value
            assigned_at = None
            
            if task_data.assigned_user_id or task_data.assigned_agent_id:
                initial_status = TaskInstanceStatus.ASSIGNED.value
                assigned_at = now_utc()
                logger.info(f"   📌 任务已分配，初始状态设为 ASSIGNED")
                if task_data.assigned_user_id:
                    logger.info(f"      分配给用户: {task_data.assigned_user_id}")
                if task_data.assigned_agent_id:
                    logger.info(f"      分配给代理: {task_data.assigned_agent_id}")
            else:
                logger.info(f"   ⏳ 任务未分配，初始状态设为 PENDING")
            
            # 准备任务数据
            data = {
                "task_instance_id": task_instance_id,
                "node_instance_id": task_data.node_instance_id,
                "workflow_instance_id": task_data.workflow_instance_id,
                "processor_id": task_data.processor_id,
                "task_type": task_data.task_type.value,
                "task_title": task_data.task_title,
                "task_description": task_data.task_description,
                "input_data": task_data.input_data or "",
                "context_data": task_data.context_data or "",
                "assigned_user_id": task_data.assigned_user_id,
                "assigned_agent_id": task_data.assigned_agent_id,
                "assigned_at": assigned_at,
                "estimated_duration": task_data.estimated_duration,
                "status": initial_status,
                "created_at": now_utc(),
                "updated_at": now_utc(),
                "is_deleted": False
            }
            
            logger.info(f"   💾 正在写入数据库...")
            result = await self.create(data)
            
            if result:
                logger.info(f"✅ 任务实例创建成功!")
                logger.info(f"   任务ID: {result['task_instance_id']}")
                logger.info(f"   任务标题: {task_data.task_title}")
                logger.info(f"   初始状态: {TaskInstanceStatus.PENDING.value}")
                logger.info(f"   创建时间: {result.get('created_at')}")
                
                # input_data和output_data现在是文本格式，不需要JSON解析
                
                # 记录输入数据概要
                if result.get('input_data') and len(result['input_data'].strip()) > 0:
                    logger.info(f"   输入数据: {result['input_data'][:100]}{'...' if len(result['input_data']) > 100 else ''}")
                else:
                    logger.info(f"   输入数据: 空")
            else:
                logger.error(f"❌ 任务实例创建失败: 数据库返回空结果")
            
            return result
        except Exception as e:
            logger.error(f"❌ 创建任务实例失败: {e}")
            logger.error(f"   任务标题: {task_data.task_title}")
            logger.error(f"   错误详情: {str(e)}")
            import traceback
            logger.error(f"   异常堆栈: {traceback.format_exc()}")
            raise
    
    def _validate_task_assignment(self, task_data: TaskInstanceCreate):
        """验证任务分配的一致性（最小干预原则）"""
        # 仅记录警告，不自动修改数据，让上层业务逻辑处理
        if task_data.task_type == TaskInstanceType.HUMAN and task_data.assigned_agent_id:
            logger.warning(f"⚠️ HUMAN任务分配给了代理: {task_data.assigned_agent_id}")
        
        if task_data.task_type == TaskInstanceType.AGENT and task_data.assigned_user_id:
            logger.warning(f"⚠️ AGENT任务分配给了用户: {task_data.assigned_user_id}")
        
        if task_data.assigned_user_id and task_data.assigned_agent_id:
            logger.warning(f"⚠️ 任务同时分配给用户和代理")
        
        logger.debug(f"✅ 任务创建: 类型={task_data.task_type.value}, 用户={task_data.assigned_user_id}, 代理={task_data.assigned_agent_id}")
    
    async def get_task_by_id(self, task_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取任务实例"""
        try:
            query = """
                SELECT ti.*, 
                       p.name as processor_name, p.type as processor_type,
                       u.username as assigned_user_name,
                       a.agent_name as assigned_agent_name
                FROM task_instance ti
                LEFT JOIN processor p ON p.processor_id = ti.processor_id
                LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
                LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
                WHERE ti.task_instance_id = $1 AND ti.is_deleted = FALSE
            """
            result = await self.db.fetch_one(query, task_instance_id)
            if result:
                result = dict(result)
                # input_data, context_data, output_data现在是文本格式，不需要JSON解析
            
            return result
        except Exception as e:
            logger.error(f"获取任务实例失败: {e}")
            raise
    
    async def update_task(self, task_instance_id: uuid.UUID, 
                         update_data: TaskInstanceUpdate) -> Optional[Dict[str, Any]]:
        """更新任务实例"""
        try:
            logger.info(f"🔄 开始更新任务实例: {task_instance_id}")
            
            # 先获取当前任务状态以便对比
            current_task = await self.get_task_by_id(task_instance_id)
            if current_task:
                logger.info(f"   当前状态: {current_task.get('status', 'unknown')}")
                logger.info(f"   任务标题: {current_task.get('task_title', '未知')}")
            
            # 准备更新数据
            data = {"updated_at": now_utc()}
            
            if update_data.status is not None:
                data["status"] = update_data.status.value
                logger.info(f"   🎯 状态变更: {current_task.get('status', 'unknown') if current_task else 'unknown'} → {update_data.status.value}")
                
                # 根据状态设置时间戳
                if update_data.status == TaskInstanceStatus.IN_PROGRESS:
                    data["started_at"] = now_utc()
                    logger.info(f"   ⏰ 设置开始时间: {data['started_at']}")
                elif update_data.status in [TaskInstanceStatus.COMPLETED, TaskInstanceStatus.FAILED, TaskInstanceStatus.CANCELLED]:
                    data["completed_at"] = now_utc()
                    logger.info(f"   🏁 设置完成时间: {data['completed_at']}")
                    
                    # 计算实际执行时间
                    if current_task and current_task.get('started_at'):
                        try:
                            start_time = current_task['started_at']
                            if isinstance(start_time, str):
                                from datetime import datetime
                                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            actual_duration = int((data["completed_at"] - start_time).total_seconds() / 60)
                            data["actual_duration"] = actual_duration
                            logger.info(f"   ⏱️  计算实际执行时间: {actual_duration}分钟")
                        except Exception as e:
                            logger.warning(f"   ⚠️  计算执行时间失败: {e}")
            
            if update_data.input_data is not None:
                data["input_data"] = update_data.input_data
                if update_data.input_data and len(update_data.input_data.strip()) > 0:
                    logger.info(f"   📥 输入数据: {update_data.input_data[:100]}{'...' if len(update_data.input_data) > 100 else ''}")
                else:
                    logger.info(f"   📥 输入数据: 空")
                    
            if update_data.output_data is not None:
                data["output_data"] = update_data.output_data
                if update_data.output_data and len(update_data.output_data.strip()) > 0:
                    logger.info(f"   📤 输出数据: {update_data.output_data[:100]}{'...' if len(update_data.output_data) > 100 else ''}")
                else:
                    logger.info(f"   📤 输出数据: 空")
                    
            if update_data.result_summary is not None:
                data["result_summary"] = update_data.result_summary
                logger.info(f"   📝 结果摘要: {update_data.result_summary[:100]}{'...' if len(update_data.result_summary) > 100 else ''}")
                
            if update_data.error_message is not None:
                data["error_message"] = update_data.error_message
                logger.warning(f"   ❌ 错误信息: {update_data.error_message}")
                
            if update_data.actual_duration is not None:
                data["actual_duration"] = update_data.actual_duration
                logger.info(f"   ⏱️  实际持续时间: {update_data.actual_duration}分钟")
            
            
            # 避免重复设置时间戳（上面已经设置过了）
            if len(data) == 1:  # 只有updated_at
                logger.info(f"   ℹ️  没有实际更新内容，返回当前任务")
                return await self.get_task_by_id(task_instance_id)
            
            logger.info(f"   💾 正在写入数据库更新...")
            result = await self.update(task_instance_id, data, "task_instance_id")
            
            if result:
                logger.info(f"✅ 任务实例更新成功!")
                logger.info(f"   任务ID: {task_instance_id}")
                if update_data.status:
                    logger.info(f"   新状态: {update_data.status.value}")
                logger.info(f"   更新时间: {data['updated_at']}")
                
                # 获取更新后的完整任务信息
                updated_task = await self.get_task_by_id(task_instance_id)
                return updated_task
            else:
                logger.error(f"❌ 任务实例更新失败: 数据库返回空结果")
                return None
                
        except Exception as e:
            logger.error(f"❌ 更新任务实例失败: {e}")
            logger.error(f"   任务ID: {task_instance_id}")
            logger.error(f"   错误详情: {str(e)}")
            import traceback
            logger.error(f"   异常堆栈: {traceback.format_exc()}")
            raise
    
    async def get_tasks_by_node_instance(self, node_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点实例的所有任务"""
        try:
            query = """
                SELECT ti.*, 
                       p.name as processor_name, p.type as processor_type,
                       u.username as assigned_user_name,
                       a.agent_name as assigned_agent_name
                FROM task_instance ti
                LEFT JOIN processor p ON p.processor_id = ti.processor_id
                LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
                LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
                WHERE ti.node_instance_id = $1 AND ti.is_deleted = FALSE
                ORDER BY ti.created_at ASC
            """
            results = await self.db.fetch_all(query, node_instance_id)
            
            # 直接返回结果（input_data和output_data现在是文本格式）
            formatted_results = []
            for result in results:
                result = dict(result)
                # input_data和output_data现在是文本格式，不需要JSON解析
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"获取节点实例任务列表失败: {e}")
            raise
    
    async def get_tasks_by_workflow_instance(self, workflow_instance_id: uuid.UUID, 
                                           status: Optional[TaskInstanceStatus] = None) -> List[Dict[str, Any]]:
        """获取工作流实例的所有任务"""
        try:
            if status:
                query = """
                    SELECT ti.*, 
                           p.name as processor_name, p.type as processor_type,
                           u.username as assigned_user_name,
                           a.agent_name as assigned_agent_name
                    FROM task_instance ti
                    LEFT JOIN processor p ON p.processor_id = ti.processor_id
                    LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
                    LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
                    WHERE ti.workflow_instance_id = $1 AND ti.status = $2 AND ti.is_deleted = FALSE
                    ORDER BY ti.created_at ASC
                """
                results = await self.db.fetch_all(query, workflow_instance_id, status.value)
            else:
                query = """
                    SELECT ti.*, 
                           p.name as processor_name, p.type as processor_type,
                           u.username as assigned_user_name,
                           a.agent_name as assigned_agent_name
                    FROM task_instance ti
                    LEFT JOIN processor p ON p.processor_id = ti.processor_id
                    LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
                    LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
                    WHERE ti.workflow_instance_id = $1 AND ti.is_deleted = FALSE
                    ORDER BY ti.created_at ASC
                """
                results = await self.db.fetch_all(query, workflow_instance_id)
            
            # 直接返回结果（input_data和output_data现在是文本格式）
            formatted_results = []
            for result in results:
                result = dict(result)
                # input_data和output_data现在是文本格式，不需要JSON解析
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"获取工作流实例任务列表失败: {e}")
            raise
    
    async def get_human_tasks_for_user(self, user_id: uuid.UUID, 
                                     status: Optional[TaskInstanceStatus] = None,
                                     limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的人工任务"""
        try:
            logger.info(f"🗃️ [数据库查询] 查询用户人工任务:")
            logger.info(f"   - 用户ID: {user_id}")
            logger.info(f"   - 任务类型过滤: {TaskInstanceType.HUMAN.value}")
            logger.info(f"   - 状态过滤: {status.value if status else '全部'}")
            
            if status:
                query = """
                    SELECT ti.*, 
                           p.name as processor_name, p.type as processor_type,
                           wi.workflow_instance_name as workflow_instance_name,
                           w.name as workflow_name
                    FROM task_instance ti
                    LEFT JOIN processor p ON p.processor_id = ti.processor_id
                    LEFT JOIN workflow_instance wi ON wi.workflow_instance_id = ti.workflow_instance_id
                    LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                    WHERE ti.assigned_user_id = $1 AND ti.task_type = $2 
                          AND ti.status = $3 AND ti.is_deleted = FALSE
                    ORDER BY 
                        CASE ti.status 
                            WHEN 'assigned' THEN 1 
                            WHEN 'pending' THEN 2 
                            WHEN 'in_progress' THEN 3 
                            ELSE 4 
                        END,
                        ti.created_at DESC
                    LIMIT $4
                """
                logger.info(f"🗃️ [数据库查询] 执行带状态过滤的查询")
                results = await self.db.fetch_all(query, user_id, TaskInstanceType.HUMAN.value, 
                                                status.value, limit)
            else:
                query = """
                    SELECT ti.*, 
                           p.name as processor_name, p.type as processor_type,
                           wi.workflow_instance_name as workflow_instance_name,
                           w.name as workflow_name
                    FROM task_instance ti
                    LEFT JOIN processor p ON p.processor_id = ti.processor_id
                    LEFT JOIN workflow_instance wi ON wi.workflow_instance_id = ti.workflow_instance_id
                    LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                    WHERE ti.assigned_user_id = $1 AND ti.task_type = $2 AND ti.is_deleted = FALSE
                    ORDER BY 
                        CASE ti.status 
                            WHEN 'assigned' THEN 1 
                            WHEN 'pending' THEN 2 
                            WHEN 'in_progress' THEN 3 
                            ELSE 4 
                        END,
                        ti.created_at DESC
                    LIMIT $3
                """
                logger.info(f"🗃️ [数据库查询] 执行无状态过滤的查询")
                results = await self.db.fetch_all(query, user_id, TaskInstanceType.HUMAN.value, limit)
            
            logger.info(f"🗃️ [数据库查询] 查询完成，返回 {len(results)} 条记录")
            
            # 额外诊断：如果没有结果，查看是否有匹配的任务但条件不满足
            if len(results) == 0:
                logger.warning(f"⚠️ [数据库诊断] 没有找到匹配的任务，开始诊断...")
                
                # 诊断1：查询该用户的所有任务
                debug_query1 = """
                    SELECT task_instance_id, task_title, task_type, status, assigned_user_id
                    FROM task_instance 
                    WHERE assigned_user_id = $1 AND is_deleted = FALSE
                    LIMIT 5
                """
                debug_results1 = await self.db.fetch_all(debug_query1, user_id)
                logger.info(f"🔧 [诊断1] 该用户的所有任务: {len(debug_results1)} 个")
                for task in debug_results1:
                    logger.info(f"   - {task['task_title']} | 类型: {task['task_type']} | 状态: {task['status']}")
                
                # 诊断2：查询所有HUMAN类型的任务
                debug_query2 = """
                    SELECT task_instance_id, task_title, assigned_user_id, status
                    FROM task_instance 
                    WHERE task_type = $1 AND is_deleted = FALSE
                    LIMIT 5
                """
                debug_results2 = await self.db.fetch_all(debug_query2, TaskInstanceType.HUMAN.value)
                logger.info(f"🔧 [诊断2] 所有HUMAN类型任务: {len(debug_results2)} 个")
                for task in debug_results2:
                    logger.info(f"   - {task['task_title']} | 用户: {task['assigned_user_id']} | 状态: {task['status']}")
                    
                # 诊断3：查询目标任务的详细信息
                target_task_ids = ['183eba7b-160a-437e-9dba-ad0d484126f9', 'c2cd416c-2c38-4803-8066-4e876ebadb28']
                for task_id in target_task_ids:
                    debug_query3 = """
                        SELECT task_instance_id, task_title, task_type, assigned_user_id, status
                        FROM task_instance 
                        WHERE task_instance_id = $1
                    """
                    debug_result3 = await self.db.fetch_one(debug_query3, task_id)
                    if debug_result3:
                        logger.info(f"🔧 [诊断3] 目标任务 {task_id}:")
                        logger.info(f"   - 标题: {debug_result3['task_title']}")
                        logger.info(f"   - 类型: {debug_result3['task_type']}")
                        logger.info(f"   - 分配用户: {debug_result3['assigned_user_id']}")
                        logger.info(f"   - 状态: {debug_result3['status']}")
                    else:
                        logger.info(f"🔧 [诊断3] 目标任务 {task_id} 不存在")
            
            # 直接返回结果（input_data和output_data现在是文本格式）
            formatted_results = []
            for result in results:
                result = dict(result)
                # input_data和output_data现在是文本格式，不需要JSON解析
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"获取用户人工任务失败: {e}")
            raise
    
    async def get_agent_tasks_for_processing(self, agent_id: Optional[uuid.UUID] = None,
                                           limit: int = 100) -> List[Dict[str, Any]]:
        """获取待处理的Agent任务"""
        try:
            if agent_id:
                query = """
                    SELECT ti.*, 
                           p.name as processor_name, p.type as processor_type,
                           a.agent_name, a.base_url as agent_endpoint
                    FROM task_instance ti
                    LEFT JOIN processor p ON p.processor_id = ti.processor_id
                    LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
                    WHERE ti.assigned_agent_id = $1 AND ti.task_type IN ($2, $3)
                          AND ti.status = $4 AND ti.is_deleted = FALSE
                    ORDER BY ti.created_at ASC
                    LIMIT $5
                """
                results = await self.db.fetch_all(query, agent_id, TaskInstanceType.AGENT.value,
                                                TaskInstanceType.MIXED.value, 
                                                TaskInstanceStatus.PENDING.value, limit)
            else:
                query = """
                    SELECT ti.*, 
                           p.name as processor_name, p.type as processor_type,
                           a.agent_name, a.base_url as agent_endpoint
                    FROM task_instance ti
                    LEFT JOIN processor p ON p.processor_id = ti.processor_id
                    LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
                    WHERE ti.task_type IN ($1, $2) AND ti.status = $3 AND ti.is_deleted = FALSE
                    ORDER BY ti.created_at ASC
                    LIMIT $4
                """
                results = await self.db.fetch_all(query, TaskInstanceType.AGENT.value,
                                                TaskInstanceType.MIXED.value, 
                                                TaskInstanceStatus.PENDING.value, limit)
                                                
            logger.info(f"   - 查询结果: 找到 {len(results)} 个任务")
            
            # 解析JSON字段
            formatted_results = []
            for i, result in enumerate(results):
                result = dict(result)
                task_id = result.get('task_instance_id', 'unknown')
                task_title = result.get('task_title', 'unknown')
                task_status = result.get('status', 'unknown')
                assigned_agent_id = result.get('assigned_agent_id', 'none')
                processor_id = result.get('processor_id', 'none')
                
                logger.info(f"   - 任务{i+1}: {task_title} (ID: {task_id})")
                logger.info(f"     状态: {task_status}, Agent: {assigned_agent_id}, Processor: {processor_id}")
                
                # input_data和output_data现在是文本格式，不需要JSON解析
                formatted_results.append(result)
            
            logger.info(f"[OK] [TASK-REPO] Agent任务查找完成，返回 {len(formatted_results)} 个任务")
            return formatted_results
        except Exception as e:
            logger.error(f"[ERROR] [TASK-REPO] 获取Agent待处理任务失败: {e}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            raise
    
    async def assign_task_to_user(self, task_instance_id: uuid.UUID, 
                                 user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """将任务分配给用户"""
        try:
            logger.info(f"👤 开始将任务分配给用户")
            logger.info(f"   任务ID: {task_instance_id}")
            logger.info(f"   用户ID: {user_id}")
            
            # 获取当前任务信息
            current_task = await self.get_task_by_id(task_instance_id)
            if current_task:
                logger.info(f"   任务标题: {current_task.get('task_title', '未知')}")
                logger.info(f"   当前状态: {current_task.get('status', 'unknown')}")
                
                # 检查是否已经分配给其他用户或代理
                if current_task.get('assigned_user_id') and str(current_task['assigned_user_id']) != str(user_id):
                    logger.warning(f"   ⚠️  任务已分配给其他用户: {current_task['assigned_user_id']}")
                elif current_task.get('assigned_agent_id'):
                    logger.warning(f"   ⚠️  任务已分配给代理: {current_task['assigned_agent_id']}")
            
            assignment_time = now_utc()
            data = {
                "assigned_user_id": user_id,
                "assigned_agent_id": None,  # 清除代理分配
                "status": TaskInstanceStatus.ASSIGNED.value,
                "assigned_at": assignment_time,
                "updated_at": assignment_time
            }
            
            logger.info(f"   💾 正在更新数据库...")
            result = await self.update(task_instance_id, data, "task_instance_id")
            
            if result:
                logger.info(f"✅ 任务分配成功!")
                logger.info(f"   任务ID: {task_instance_id}")
                logger.info(f"   分配给用户: {user_id}")
                logger.info(f"   新状态: {TaskInstanceStatus.ASSIGNED.value}")
                logger.info(f"   分配时间: {assignment_time}")
                
                # 获取更新后的任务信息
                updated_task = await self.get_task_by_id(task_instance_id)
                return updated_task
            else:
                logger.error(f"❌ 任务分配失败: 数据库更新返回空结果")
                return None
                
        except Exception as e:
            logger.error(f"❌ 分配任务给用户失败: {e}")
            logger.error(f"   任务ID: {task_instance_id}")
            logger.error(f"   用户ID: {user_id}")
            logger.error(f"   错误详情: {str(e)}")
            import traceback
            logger.error(f"   异常堆栈: {traceback.format_exc()}")
            raise
    
    async def assign_task_to_agent(self, task_instance_id: uuid.UUID, 
                                  agent_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """将任务分配给Agent"""
        try:
            logger.info(f"🤖 开始将任务分配给Agent")
            logger.info(f"   任务ID: {task_instance_id}")
            logger.info(f"   代理ID: {agent_id}")
            
            # 获取当前任务信息
            current_task = await self.get_task_by_id(task_instance_id)
            if current_task:
                logger.info(f"   任务标题: {current_task.get('task_title', '未知')}")
                logger.info(f"   当前状态: {current_task.get('status', 'unknown')}")
                
                # 检查是否已经分配给其他用户或代理
                if current_task.get('assigned_agent_id') and str(current_task['assigned_agent_id']) != str(agent_id):
                    logger.warning(f"   ⚠️  任务已分配给其他Agent: {current_task['assigned_agent_id']}")
                elif current_task.get('assigned_user_id'):
                    logger.warning(f"   ⚠️  任务已分配给用户: {current_task['assigned_user_id']}")
            
            assignment_time = now_utc()
            data = {
                "assigned_agent_id": agent_id,
                "assigned_user_id": None,  # 清除用户分配
                "status": TaskInstanceStatus.ASSIGNED.value,
                "assigned_at": assignment_time,
                "updated_at": assignment_time
            }
            
            logger.info(f"   💾 正在更新数据库...")
            result = await self.update(task_instance_id, data, "task_instance_id")
            
            if result:
                logger.info(f"✅ 任务分配成功!")
                logger.info(f"   任务ID: {task_instance_id}")
                logger.info(f"   分配给Agent: {agent_id}")
                logger.info(f"   新状态: {TaskInstanceStatus.ASSIGNED.value}")
                logger.info(f"   分配时间: {assignment_time}")
                
                # 获取更新后的任务信息
                updated_task = await self.get_task_by_id(task_instance_id)
                return updated_task
            else:
                logger.error(f"❌ 任务分配失败: 数据库更新返回空结果")
                return None
                
        except Exception as e:
            logger.error(f"❌ 分配任务给Agent失败: {e}")
            logger.error(f"   任务ID: {task_instance_id}")
            logger.error(f"   代理ID: {agent_id}")
            logger.error(f"   错误详情: {str(e)}")
            import traceback
            logger.error(f"   异常堆栈: {traceback.format_exc()}")
            raise
    
    async def delete_task(self, task_instance_id: uuid.UUID, soft_delete: bool = True) -> bool:
        """删除任务实例"""
        try:
            if soft_delete:
                result = await self.update(task_instance_id, {
                    "is_deleted": True,
                    "updated_at": now_utc()
                }, "task_instance_id")
                success = result is not None
            else:
                query = "DELETE FROM task_instance WHERE task_instance_id = $1"
                result = await self.db.execute(query, task_instance_id)
                success = "1" in result
            
            if success:
                action = "软删除" if soft_delete else "硬删除"
                logger.info(f"{action}任务实例: {task_instance_id}")
            
            return success
        except Exception as e:
            logger.error(f"删除任务实例失败: {e}")
            raise
    
    async def get_task_statistics(self, workflow_instance_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """获取任务统计信息"""
        try:
            if workflow_instance_id:
                query = """
                    SELECT 
                        COUNT(*) as total_tasks,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_tasks,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
                        COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
                        COUNT(CASE WHEN task_type = 'human' THEN 1 END) as human_tasks,
                        COUNT(CASE WHEN task_type = 'agent' THEN 1 END) as agent_tasks,
                        COUNT(CASE WHEN task_type = 'mixed' THEN 1 END) as mixed_tasks,
                        AVG(actual_duration) as average_duration,
                        AVG(estimated_duration) as average_estimated_duration
                    FROM task_instance 
                    WHERE workflow_instance_id = $1 AND is_deleted = FALSE
                """
                result = await self.db.fetch_one(query, workflow_instance_id)
            else:
                query = """
                    SELECT 
                        COUNT(*) as total_tasks,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_tasks,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
                        COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
                        COUNT(CASE WHEN task_type = 'human' THEN 1 END) as human_tasks,
                        COUNT(CASE WHEN task_type = 'agent' THEN 1 END) as agent_tasks,
                        COUNT(CASE WHEN task_type = 'mixed' THEN 1 END) as mixed_tasks,
                        AVG(actual_duration) as average_duration,
                        AVG(estimated_duration) as average_estimated_duration
                    FROM task_instance 
                    WHERE is_deleted = FALSE
                """
                result = await self.db.fetch_one(query)
            
            return result if result else {}
        except Exception as e:
            logger.error(f"获取任务统计信息失败: {e}")
            raise

    async def search_tasks(self, keyword: str, task_type: Optional[TaskInstanceType] = None,
                          status: Optional[TaskInstanceStatus] = None, 
                          limit: int = 50) -> List[Dict[str, Any]]:
        """搜索任务实例"""
        try:
            where_conditions = ["ti.is_deleted = FALSE"]
            params = []
            param_count = 1
            
            # 关键字搜索
            where_conditions.append(f"(ti.task_title ILIKE ${param_count} OR ti.task_description ILIKE ${param_count})")
            params.append(f"%{keyword}%")
            param_count += 1
            
            # 任务类型过滤
            if task_type:
                where_conditions.append(f"ti.task_type = ${param_count}")
                params.append(task_type.value)
                param_count += 1
            
            # 状态过滤
            if status:
                where_conditions.append(f"ti.status = ${param_count}")
                params.append(status.value)
                param_count += 1
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                SELECT ti.*, 
                       p.name as processor_name, p.type as processor_type,
                       u.username as assigned_user_name,
                       a.agent_name as assigned_agent_name,
                       wi.workflow_instance_name as workflow_instance_name
                FROM task_instance ti
                LEFT JOIN processor p ON p.processor_id = ti.processor_id
                LEFT JOIN "user" u ON u.user_id = ti.assigned_user_id
                LEFT JOIN agent a ON a.agent_id = ti.assigned_agent_id
                LEFT JOIN workflow_instance wi ON wi.workflow_instance_id = ti.workflow_instance_id
                WHERE {where_clause}
                ORDER BY ti.created_at DESC
                LIMIT ${param_count}
            """
            params.append(limit)
            
            results = await self.db.fetch_all(query, *params)
            
            # 直接返回结果（input_data和output_data现在是文本格式）
            formatted_results = []
            for result in results:
                result = dict(result)
                # input_data和output_data现在是文本格式，不需要JSON解析
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"搜索任务实例失败: {e}")
            raise