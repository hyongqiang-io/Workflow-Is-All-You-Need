"""
工作流实例数据访问层
Workflow Instance Repository
"""

import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger


# 使用helpers中的通用JSON序列化器

from ..base import BaseRepository
from ...models.instance import (
    WorkflowInstance, WorkflowInstanceCreate, WorkflowInstanceUpdate, 
    WorkflowInstanceStatus, ExecutionStatistics
)
from ...utils.helpers import now_utc, safe_json_dumps, safe_json_serializer
from ...utils.database import db_manager


class WorkflowInstanceRepository(BaseRepository[WorkflowInstance]):
    """工作流实例数据访问层"""
    
    def __init__(self):
        super().__init__("workflow_instance")
    
    async def create_instance(self, instance_data: WorkflowInstanceCreate) -> Optional[Dict[str, Any]]:
        """创建工作流实例"""
        logger.info(f"🚀 开始创建工作流实例: {instance_data.workflow_instance_name}")
        logger.info(f"   - 工作流Base ID: {instance_data.workflow_base_id}")
        logger.info(f"   - 执行者ID: {instance_data.executor_id}")
        logger.info(f"   - 输入数据: {len(instance_data.input_data or {})} 个字段")
        
        try:
            # 获取当前版本的工作流
            logger.info(f"🔍 查询工作流信息: {instance_data.workflow_base_id}")
            workflow_query = """
                SELECT workflow_id, workflow_base_id, name 
                FROM workflow 
                WHERE workflow_base_id = $1 AND is_current_version = TRUE AND is_deleted = FALSE
            """
            workflow = await self.db.fetch_one(workflow_query, instance_data.workflow_base_id)
            if not workflow:
                logger.error(f"❌ 工作流不存在或已被删除: {instance_data.workflow_base_id}")
                raise ValueError("工作流不存在或已被删除")
            
            logger.info(f"✅ 找到工作流: {workflow['name']} (ID: {workflow['workflow_id']})")
            
            # 准备实例数据
            workflow_instance_id = uuid.uuid4()
            data = {
                "workflow_instance_id": workflow_instance_id,  # Primary key
                "workflow_base_id": instance_data.workflow_base_id,
                "workflow_id": workflow['workflow_id'],
                "executor_id": instance_data.executor_id,
                "created_by": instance_data.executor_id,  # 创建者设为执行者
                "workflow_instance_name": instance_data.workflow_instance_name,
                "input_data": safe_json_dumps(instance_data.input_data or {}),
                "context_data": safe_json_dumps(instance_data.context_data or {}),
                "status": WorkflowInstanceStatus.PENDING.value,
                "created_at": now_utc(),
                "updated_at": now_utc(),
                "is_deleted": False
            }
            
            logger.info(f"💾 写入数据库: 工作流实例 {workflow_instance_id}")
            logger.info(f"   - 实例名称: {instance_data.workflow_instance_name}")
            logger.info(f"   - 初始状态: {WorkflowInstanceStatus.PENDING.value}")
            logger.info(f"   - 关联工作流: {workflow['name']}")
            
            result = await self.create(data)
            if result:
                logger.info(f"✅ 工作流实例创建成功!")
                logger.info(f"   - 实例ID: {result['workflow_instance_id']}")
                logger.info(f"   - 实例名称: {instance_data.workflow_instance_name}")
                logger.info(f"   - 状态: {result.get('status', 'unknown')}")
                logger.info(f"   - 创建时间: {result.get('created_at', 'unknown')}")
                
                # 解析JSON字段
                result['input_data'] = json.loads(result.get('input_data', '{}'))
                result['context_data'] = json.loads(result.get('context_data', '{}'))
                if result.get('output_data'):
                    result['output_data'] = json.loads(result['output_data'])
            else:
                logger.error(f"❌ 工作流实例创建失败: 数据库返回空结果")
            
            return result
        except Exception as e:
            logger.error(f"❌ 创建工作流实例失败: {e}")
            logger.error(f"   - 实例名称: {instance_data.workflow_instance_name}")
            logger.error(f"   - 工作流Base ID: {instance_data.workflow_base_id}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            raise
    
    async def get_instance_by_id(self, instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取工作流实例"""
        try:
            query = """
                SELECT wi.*, w.name as workflow_name, u.username as executor_name
                FROM workflow_instance wi
                LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                LEFT JOIN "user" u ON u.user_id = wi.executor_id
                WHERE wi.workflow_instance_id = $1 AND wi.is_deleted = FALSE
            """
            result = await self.db.fetch_one(query, instance_id)
            if result:
                # 解析JSON字段
                result = dict(result)
                result['input_data'] = json.loads(result.get('input_data', '{}'))
                result['context_data'] = json.loads(result.get('context_data', '{}'))
                if result.get('output_data'):
                    result['output_data'] = json.loads(result['output_data'])
                
                # 解析新增的结构化输出字段
                if result.get('execution_summary'):
                    result['execution_summary'] = json.loads(result['execution_summary'])
                if result.get('quality_metrics'):
                    result['quality_metrics'] = json.loads(result['quality_metrics'])
                if result.get('data_lineage'):
                    result['data_lineage'] = json.loads(result['data_lineage'])
                if result.get('output_summary'):
                    result['output_summary'] = json.loads(result['output_summary'])
            
            return result
        except Exception as e:
            logger.error(f"获取工作流实例失败: {e}")
            raise
    
    async def update_instance(self, instance_id: uuid.UUID, 
                             update_data: WorkflowInstanceUpdate) -> Optional[Dict[str, Any]]:
        """更新工作流实例"""
        try:
            # 准备更新数据
            data = {"updated_at": now_utc()}
            
            if update_data.workflow_instance_name is not None:
                data["workflow_instance_name"] = update_data.workflow_instance_name
            if update_data.status is not None:
                data["status"] = update_data.status.value
            if update_data.input_data is not None:
                data["input_data"] = safe_json_dumps(update_data.input_data)
            if update_data.context_data is not None:
                data["context_data"] = safe_json_dumps(update_data.context_data)
            if update_data.output_data is not None:
                data["output_data"] = safe_json_dumps(update_data.output_data)
            if update_data.error_message is not None:
                data["error_message"] = update_data.error_message
            if update_data.current_node_id is not None:
                data["current_node_id"] = update_data.current_node_id
            
            # 新增结构化输出字段支持
            if hasattr(update_data, 'execution_summary') and update_data.execution_summary is not None:
                data["execution_summary"] = safe_json_dumps(update_data.execution_summary)
            if hasattr(update_data, 'quality_metrics') and update_data.quality_metrics is not None:
                data["quality_metrics"] = safe_json_dumps(update_data.quality_metrics)
            if hasattr(update_data, 'data_lineage') and update_data.data_lineage is not None:
                data["data_lineage"] = safe_json_dumps(update_data.data_lineage)
            if hasattr(update_data, 'output_summary') and update_data.output_summary is not None:
                # 将Pydantic模型转换为字典再序列化
                output_summary_dict = update_data.output_summary.dict() if hasattr(update_data.output_summary, 'dict') else update_data.output_summary
                data["output_summary"] = safe_json_dumps(output_summary_dict)
            
            # 根据状态更新时间戳
            if update_data.status == WorkflowInstanceStatus.RUNNING:
                data["started_at"] = now_utc()
            elif update_data.status in [WorkflowInstanceStatus.COMPLETED, 
                                       WorkflowInstanceStatus.FAILED, 
                                       WorkflowInstanceStatus.CANCELLED]:
                data["completed_at"] = now_utc()
            
            if not data or len(data) == 1:  # 只有updated_at
                return await self.get_instance_by_id(instance_id)
            
            logger.info(f"💾 更新工作流实例数据库记录: {instance_id}")
            result = await self.update(instance_id, data, "workflow_instance_id")
            if result:
                logger.info(f"✅ 工作流实例状态更新成功!")
                logger.info(f"   - 实例ID: {instance_id}")
                logger.info(f"   - 新状态: {update_data.status}")
                if update_data.status == WorkflowInstanceStatus.RUNNING:
                    logger.info(f"   - 🏃 工作流开始执行")
                elif update_data.status == WorkflowInstanceStatus.COMPLETED:
                    logger.info(f"   - 🎉 工作流执行完成")
                elif update_data.status == WorkflowInstanceStatus.FAILED:
                    logger.info(f"   - ❌ 工作流执行失败")
                    if update_data.error_message:
                        logger.error(f"   - 错误信息: {update_data.error_message}")
                elif update_data.status == WorkflowInstanceStatus.CANCELLED:
                    logger.info(f"   - ⏹️ 工作流被取消")
                return await self.get_instance_by_id(instance_id)
            
            return None
        except Exception as e:
            logger.error(f"更新工作流实例失败: {e}")
            raise
    
    async def get_instances_by_executor(self, executor_id: uuid.UUID, 
                                      status: Optional[WorkflowInstanceStatus] = None,
                                      limit: int = 50) -> List[Dict[str, Any]]:
        """获取执行者的工作流实例列表"""
        try:
            if status:
                query = """
                    SELECT wi.*, w.name as workflow_name, u.username as executor_name
                    FROM workflow_instance wi
                    LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                    LEFT JOIN "user" u ON u.user_id = wi.executor_id
                    WHERE wi.executor_id = $1 AND wi.status = $2 AND wi.is_deleted = FALSE
                    ORDER BY wi.created_at DESC
                    LIMIT $3
                """
                results = await self.db.fetch_all(query, executor_id, status.value, limit)
            else:
                query = """
                    SELECT wi.*, w.name as workflow_name, u.username as executor_name
                    FROM workflow_instance wi
                    LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                    LEFT JOIN "user" u ON u.user_id = wi.executor_id
                    WHERE wi.executor_id = $1 AND wi.is_deleted = FALSE
                    ORDER BY wi.created_at DESC
                    LIMIT $2
                """
                results = await self.db.fetch_all(query, executor_id, limit)
            
            # 解析JSON字段
            formatted_results = []
            for result in results:
                result = dict(result)
                result['input_data'] = json.loads(result.get('input_data', '{}'))
                result['context_data'] = json.loads(result.get('context_data', '{}'))
                if result.get('output_data'):
                    result['output_data'] = json.loads(result['output_data'])
                
                # 解析新增的结构化输出字段
                if result.get('execution_summary'):
                    result['execution_summary'] = json.loads(result['execution_summary'])
                if result.get('quality_metrics'):
                    result['quality_metrics'] = json.loads(result['quality_metrics'])
                if result.get('data_lineage'):
                    result['data_lineage'] = json.loads(result['data_lineage'])
                if result.get('output_summary'):
                    result['output_summary'] = json.loads(result['output_summary'])
                    
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"获取执行者实例列表失败: {e}")
            raise
    
    async def get_instances_by_workflow(self, workflow_base_id: uuid.UUID, 
                                       limit: int = 50) -> List[Dict[str, Any]]:
        """获取工作流的所有实例"""
        try:
            query = """
                SELECT wi.*, w.name as workflow_name, u.username as executor_name
                FROM workflow_instance wi
                LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                LEFT JOIN "user" u ON u.user_id = wi.executor_id
                WHERE wi.workflow_base_id = $1 AND wi.is_deleted = FALSE
                ORDER BY wi.created_at DESC
                LIMIT $2
            """
            results = await self.db.fetch_all(query, workflow_base_id, limit)
            
            # 解析JSON字段
            formatted_results = []
            for result in results:
                result = dict(result)
                result['input_data'] = json.loads(result.get('input_data', '{}'))
                result['context_data'] = json.loads(result.get('context_data', '{}'))
                if result.get('output_data'):
                    result['output_data'] = json.loads(result['output_data'])
                
                # 解析新增的结构化输出字段
                if result.get('execution_summary'):
                    result['execution_summary'] = json.loads(result['execution_summary'])
                if result.get('quality_metrics'):
                    result['quality_metrics'] = json.loads(result['quality_metrics'])
                if result.get('data_lineage'):
                    result['data_lineage'] = json.loads(result['data_lineage'])
                if result.get('output_summary'):
                    result['output_summary'] = json.loads(result['output_summary'])
                    
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"获取工作流实例列表失败: {e}")
            raise
    
    async def get_running_instances(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有运行中的实例"""
        try:
            query = """
                SELECT wi.*, w.name as workflow_name, u.username as executor_name
                FROM workflow_instance wi
                LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                LEFT JOIN "user" u ON u.user_id = wi.executor_id
                WHERE wi.status = $1 AND wi.is_deleted = FALSE
                ORDER BY wi.started_at ASC
                LIMIT $2
            """
            results = await self.db.fetch_all(query, WorkflowInstanceStatus.RUNNING.value, limit)
            
            # 解析JSON字段
            formatted_results = []
            for result in results:
                result = dict(result)
                result['input_data'] = json.loads(result.get('input_data', '{}'))
                result['context_data'] = json.loads(result.get('context_data', '{}'))
                if result.get('output_data'):
                    result['output_data'] = json.loads(result['output_data'])
                
                # 解析新增的结构化输出字段
                if result.get('execution_summary'):
                    result['execution_summary'] = json.loads(result['execution_summary'])
                if result.get('quality_metrics'):
                    result['quality_metrics'] = json.loads(result['quality_metrics'])
                if result.get('data_lineage'):
                    result['data_lineage'] = json.loads(result['data_lineage'])
                if result.get('output_summary'):
                    result['output_summary'] = json.loads(result['output_summary'])
                    
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"获取运行中实例列表失败: {e}")
            raise
    
    async def delete_instance(self, instance_id: uuid.UUID, soft_delete: bool = True) -> bool:
        """删除工作流实例"""
        try:
            logger.info(f"🗑️ 开始删除工作流实例: {instance_id}")
            logger.info(f"   - 删除方式: {'软删除' if soft_delete else '硬删除'}")
            
            # 首先检查实例是否存在
            logger.info(f"🔍 检查实例是否存在")
            existing_instance = await self.get_instance_by_id(instance_id)
            if not existing_instance:
                logger.warning(f"⚠️ 要删除的实例不存在: {instance_id}")
                return False
            
            logger.info(f"📋 找到待删除实例:")
            logger.info(f"   - 实例名称: {existing_instance.get('workflow_instance_name', '未命名')}")
            logger.info(f"   - 当前状态: {existing_instance.get('status')}")
            logger.info(f"   - is_deleted: {existing_instance.get('is_deleted', False)}")
            
            if existing_instance.get('is_deleted', False):
                logger.warning(f"⚠️ 实例已被标记为删除，跳过操作")
                return True
            
            if soft_delete:
                logger.info(f"🎯 执行软删除操作")
                logger.info(f"   - 调用 self.update({instance_id}, {{'is_deleted': True}}, 'workflow_instance_id')")
                
                try:
                    result = await self.update(instance_id, {
                        "is_deleted": True,
                        "updated_at": now_utc()
                    }, "workflow_instance_id")
                    
                    logger.info(f"   - update()方法返回结果: {result}")
                    success = result is not None
                    
                    if success:
                        logger.info(f"✅ 软删除成功")
                        # 验证删除结果
                        verification = await self.get_instance_by_id(instance_id)
                        if verification:
                            logger.info(f"   - 验证: 实例仍可查询到 (软删除)")
                            logger.info(f"   - 验证: is_deleted = {verification.get('is_deleted')}")
                        else:
                            logger.info(f"   - 验证: 实例已不可查询 (软删除生效)")
                    else:
                        logger.error(f"❌ 软删除失败: update()返回None")
                        
                except Exception as update_error:
                    logger.error(f"❌ 执行软删除时发生异常:")
                    logger.error(f"   - 异常类型: {type(update_error).__name__}")
                    logger.error(f"   - 异常信息: {str(update_error)}")
                    import traceback
                    logger.error(f"   - 异常堆栈: {traceback.format_exc()}")
                    raise update_error
                    
            else:
                logger.info(f"🎯 执行硬删除操作")
                query = "DELETE FROM workflow_instance WHERE workflow_instance_id = $1"
                logger.info(f"   - SQL查询: {query}")
                logger.info(f"   - 参数: {instance_id}")
                
                try:
                    result = await self.db.execute(query, instance_id)
                    logger.info(f"   - 数据库执行结果: {result}")
                    success = "1" in result
                    
                    if success:
                        logger.info(f"✅ 硬删除成功")
                    else:
                        logger.error(f"❌ 硬删除失败: 执行结果不包含'1'")
                        
                except Exception as delete_error:
                    logger.error(f"❌ 执行硬删除时发生异常:")
                    logger.error(f"   - 异常类型: {type(delete_error).__name__}")
                    logger.error(f"   - 异常信息: {str(delete_error)}")
                    import traceback
                    logger.error(f"   - 异常堆栈: {traceback.format_exc()}")
                    raise delete_error
            
            if success:
                action = "软删除" if soft_delete else "硬删除"
                logger.info(f"✅ {action}工作流实例成功: {instance_id}")
            else:
                action = "软删除" if soft_delete else "硬删除"
                logger.error(f"❌ {action}工作流实例失败: {instance_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 删除工作流实例总体异常:")
            logger.error(f"   - 实例ID: {instance_id}")
            logger.error(f"   - 删除方式: {'软删除' if soft_delete else '硬删除'}")
            logger.error(f"   - 异常类型: {type(e).__name__}")
            logger.error(f"   - 异常信息: {str(e)}")
            import traceback
            logger.error(f"   - 完整异常堆栈: {traceback.format_exc()}")
            raise
    
    async def delete_instance_cascade(self, instance_id: uuid.UUID, soft_delete: bool = True) -> Dict[str, Any]:
        """级联删除工作流实例及其相关数据"""
        try:
            logger.info(f"🗑️ 开始级联删除工作流实例: {instance_id} (软删除: {soft_delete})")
            
            # 统计删除的数据量
            deletion_stats = {
                'workflow_instance_id': str(instance_id),
                'deleted_tasks': 0,
                'deleted_nodes': 0,
                'deleted_workflow': False,
                'soft_delete': soft_delete
            }
            
            # 1. 首先删除所有任务实例
            logger.info(f"📋 步骤1: 删除相关任务实例")
            from .task_instance_repository import TaskInstanceRepository
            task_repo = TaskInstanceRepository()
            deleted_tasks = await task_repo.delete_tasks_by_workflow_instance(instance_id, soft_delete)
            deletion_stats['deleted_tasks'] = deleted_tasks
            
            # 2. 然后删除所有节点实例
            logger.info(f"📋 步骤2: 删除相关节点实例")
            from .node_instance_repository import NodeInstanceRepository
            node_repo = NodeInstanceRepository()
            deleted_nodes = await node_repo.delete_nodes_by_workflow_instance(instance_id, soft_delete)
            deletion_stats['deleted_nodes'] = deleted_nodes
            
            # 3. 最后删除工作流实例本身
            logger.info(f"📋 步骤3: 删除工作流实例")
            workflow_deleted = await self.delete_instance(instance_id, soft_delete)
            deletion_stats['deleted_workflow'] = workflow_deleted
            
            if workflow_deleted:
                logger.info(f"✅ 级联删除工作流实例成功:")
                logger.info(f"   - 工作流实例: {instance_id}")
                logger.info(f"   - 删除的任务: {deleted_tasks} 个")
                logger.info(f"   - 删除的节点实例: {deleted_nodes} 个")
                logger.info(f"   - 删除方式: {'软删除' if soft_delete else '硬删除'}")
            else:
                logger.error(f"❌ 级联删除工作流实例失败: {instance_id}")
            
            return deletion_stats
            
        except Exception as e:
            logger.error(f"级联删除工作流实例失败: {e}")
            raise
    
    async def get_execution_statistics(self, instance_id: uuid.UUID) -> Optional[ExecutionStatistics]:
        """获取实例执行统计"""
        try:
            # 获取节点统计
            node_stats_query = """
                SELECT 
                    COUNT(*) as total_nodes,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_nodes,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_nodes,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_nodes
                FROM node_instance 
                WHERE workflow_instance_id = $1 AND is_deleted = FALSE
            """
            node_stats = await self.db.fetch_one(node_stats_query, instance_id)
            
            # 获取任务统计
            task_stats_query = """
                SELECT 
                    COUNT(*) as total_tasks,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_tasks,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
                    COUNT(CASE WHEN task_type = 'human' THEN 1 END) as human_tasks,
                    COUNT(CASE WHEN task_type = 'agent' THEN 1 END) as agent_tasks,
                    COUNT(CASE WHEN task_type = 'mixed' THEN 1 END) as mixed_tasks,
                    AVG(actual_duration) as average_task_duration
                FROM task_instance 
                WHERE workflow_instance_id = $1 AND is_deleted = FALSE
            """
            task_stats = await self.db.fetch_one(task_stats_query, instance_id)
            
            # 获取总执行时间
            instance = await self.get_instance_by_id(instance_id)
            if not instance:
                return None
            
            total_execution_time = None
            if instance.get('started_at') and instance.get('completed_at'):
                start_time = datetime.fromisoformat(instance['started_at'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(instance['completed_at'].replace('Z', '+00:00'))
                total_execution_time = int((end_time - start_time).total_seconds() / 60)
            
            return ExecutionStatistics(
                workflow_instance_id=instance_id,
                total_nodes=node_stats['total_nodes'] or 0,
                completed_nodes=node_stats['completed_nodes'] or 0,
                failed_nodes=node_stats['failed_nodes'] or 0,
                pending_nodes=node_stats['pending_nodes'] or 0,
                total_tasks=task_stats['total_tasks'] or 0,
                completed_tasks=task_stats['completed_tasks'] or 0,
                failed_tasks=task_stats['failed_tasks'] or 0,
                pending_tasks=task_stats['pending_tasks'] or 0,
                human_tasks=task_stats['human_tasks'] or 0,
                agent_tasks=task_stats['agent_tasks'] or 0,
                mixed_tasks=task_stats['mixed_tasks'] or 0,
                average_task_duration=float(task_stats['average_task_duration']) if task_stats['average_task_duration'] else None,
                total_execution_time=total_execution_time
            )
        except Exception as e:
            logger.error(f"获取执行统计失败: {e}")
            raise
    
    async def search_instances(self, keyword: str, executor_id: Optional[uuid.UUID] = None, 
                              limit: int = 50) -> List[Dict[str, Any]]:
        """搜索工作流实例"""
        try:
            if executor_id:
                query = """
                    SELECT wi.*, w.name as workflow_name, u.username as executor_name
                    FROM workflow_instance wi
                    LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                    LEFT JOIN "user" u ON u.user_id = wi.executor_id
                    WHERE (wi.workflow_instance_name ILIKE $1 OR w.name ILIKE $1) 
                          AND wi.executor_id = $2 AND wi.is_deleted = FALSE
                    ORDER BY wi.created_at DESC
                    LIMIT $3
                """
                results = await self.db.fetch_all(query, f"%{keyword}%", executor_id, limit)
            else:
                query = """
                    SELECT wi.*, w.name as workflow_name, u.username as executor_name
                    FROM workflow_instance wi
                    LEFT JOIN workflow w ON w.workflow_id = wi.workflow_id
                    LEFT JOIN "user" u ON u.user_id = wi.executor_id
                    WHERE (wi.workflow_instance_name ILIKE $1 OR w.name ILIKE $1) 
                          AND wi.is_deleted = FALSE
                    ORDER BY wi.created_at DESC
                    LIMIT $2
                """
                results = await self.db.fetch_all(query, f"%{keyword}%", limit)
            
            # 解析JSON字段
            formatted_results = []
            for result in results:
                result = dict(result)
                result['input_data'] = json.loads(result.get('input_data', '{}'))
                result['context_data'] = json.loads(result.get('context_data', '{}'))
                if result.get('output_data'):
                    result['output_data'] = json.loads(result['output_data'])
                
                # 解析新增的结构化输出字段
                if result.get('execution_summary'):
                    result['execution_summary'] = json.loads(result['execution_summary'])
                if result.get('quality_metrics'):
                    result['quality_metrics'] = json.loads(result['quality_metrics'])
                if result.get('data_lineage'):
                    result['data_lineage'] = json.loads(result['data_lineage'])
                if result.get('output_summary'):
                    result['output_summary'] = json.loads(result['output_summary'])
                    
                formatted_results.append(result)
            
            return formatted_results
        except Exception as e:
            logger.error(f"搜索工作流实例失败: {e}")
            raise
    
    # ================== 工作流持久化功能 ==================
    
    async def save_workflow_context_snapshot(self, 
                                           workflow_instance_id: uuid.UUID,
                                           context_data: Dict[str, Any],
                                           node_states: Dict[str, Any] = None,
                                           snapshot_type: str = 'auto',
                                           description: str = None,
                                           created_by: uuid.UUID = None) -> Optional[uuid.UUID]:
        """保存工作流上下文快照"""
        try:
            logger.info(f"💾 [持久化] 保存工作流上下文快照: {workflow_instance_id}")
            logger.info(f"   - 快照类型: {snapshot_type}")
            logger.info(f"   - 描述: {description or '自动快照'}")
            
            snapshot_id = uuid.uuid4()
            
            # 获取当前工作流状态用于快照
            workflow_instance = await self.get_instance_by_id(workflow_instance_id)
            if not workflow_instance:
                logger.error(f"❌ [持久化] 工作流实例不存在: {workflow_instance_id}")
                return None
            
            current_status = workflow_instance.get('status', 'unknown')
            
            data = {
                'snapshot_id': snapshot_id,
                'workflow_instance_id': workflow_instance_id,
                'snapshot_type': snapshot_type,
                'context_data': safe_json_dumps(context_data or {}),
                'node_states': safe_json_dumps(node_states or {}),
                'execution_state': current_status,
                'created_at': now_utc(),
                'created_by': created_by,
                'description': description,
                'is_deleted': False
            }
            
            # MySQL兼容的插入语句
            insert_query = """
                INSERT INTO workflow_context_snapshot 
                (snapshot_id, workflow_instance_id, snapshot_type, context_data, 
                 node_states, execution_state, created_at, created_by, description, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            await self.db.execute(insert_query, 
                                snapshot_id, workflow_instance_id, snapshot_type,
                                data['context_data'], data['node_states'], 
                                current_status, data['created_at'], created_by, 
                                description, False)
            
            logger.info(f"✅ [持久化] 工作流上下文快照已保存: {snapshot_id}")
            return snapshot_id
            
        except Exception as e:
            logger.error(f"❌ [持久化] 保存工作流上下文快照失败: {e}")
            import traceback
            logger.error(f"   - 错误堆栈: {traceback.format_exc()}")
            return None

    async def get_latest_context_snapshot(self, workflow_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取最新的上下文快照"""
        try:
            logger.debug(f"📸 [持久化] 获取最新上下文快照: {workflow_instance_id}")
            
            query = """
                SELECT snapshot_id, workflow_instance_id, snapshot_type, 
                       context_data, node_states, execution_state, 
                       created_at, created_by, description
                FROM workflow_context_snapshot
                WHERE workflow_instance_id = %s AND is_deleted = FALSE
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            result = await self.db.fetch_one(query, workflow_instance_id)
            
            if result:
                logger.debug(f"✅ [持久化] 找到最新快照: {result['snapshot_id']}")
                return dict(result)
            else:
                logger.debug(f"📸 [持久化] 没有找到快照: {workflow_instance_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [持久化] 获取最新上下文快照失败: {e}")
            return None
    
    async def load_workflow_context_snapshot(self, 
                                           workflow_instance_id: uuid.UUID,
                                           snapshot_id: uuid.UUID = None) -> Optional[Dict[str, Any]]:
        """加载工作流上下文快照（默认加载最新的）"""
        try:
            if snapshot_id:
                # 加载指定快照
                query = """
                    SELECT * FROM workflow_context_snapshot 
                    WHERE snapshot_id = %s AND workflow_instance_id = %s AND is_deleted = FALSE
                """
                result = await self.db.fetch_one(query, snapshot_id, workflow_instance_id)
            else:
                # 加载最新快照
                query = """
                    SELECT * FROM workflow_context_snapshot 
                    WHERE workflow_instance_id = %s AND is_deleted = FALSE
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                result = await self.db.fetch_one(query, workflow_instance_id)
            
            if result:
                # 解析JSON字段
                snapshot_data = dict(result)
                snapshot_data['context_data'] = json.loads(snapshot_data.get('context_data', '{}'))
                snapshot_data['node_states'] = json.loads(snapshot_data.get('node_states', '{}'))
                
                logger.info(f"✅ [持久化] 成功加载工作流上下文快照")
                logger.info(f"   - 快照ID: {snapshot_data.get('snapshot_id')}")
                logger.info(f"   - 创建时间: {snapshot_data.get('created_at')}")
                logger.info(f"   - 快照类型: {snapshot_data.get('snapshot_type')}")
                
                return snapshot_data
            else:
                logger.warning(f"⚠️ [持久化] 未找到工作流上下文快照: {workflow_instance_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ [持久化] 加载工作流上下文快照失败: {e}")
            return None
    
    async def log_workflow_event(self, 
                               workflow_instance_id: uuid.UUID,
                               event_type: str,
                               event_data: Dict[str, Any] = None,
                               node_instance_id: uuid.UUID = None,
                               task_instance_id: uuid.UUID = None,
                               user_id: uuid.UUID = None) -> Optional[uuid.UUID]:
        """记录工作流事件到事件日志"""
        try:
            event_id = uuid.uuid4()
            
            # 获取下一个序列号（简化实现）
            sequence_number = int(datetime.now().timestamp() * 1000000)  # 微秒级时间戳作为序列号
            
            data = {
                'event_id': event_id,
                'workflow_instance_id': workflow_instance_id,
                'event_type': event_type,
                'event_data': safe_json_dumps(event_data or {}),
                'node_instance_id': node_instance_id,
                'task_instance_id': task_instance_id,
                'user_id': user_id,
                'timestamp': now_utc(),
                'sequence_number': sequence_number,
                'is_deleted': False
            }
            
            # MySQL兼容的插入语句
            insert_query = """
                INSERT INTO workflow_instance_event_log 
                (event_id, workflow_instance_id, event_type, event_data, 
                 node_instance_id, task_instance_id, user_id, timestamp, 
                 sequence_number, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            await self.db.execute(insert_query,
                                event_id, workflow_instance_id, event_type,
                                data['event_data'], node_instance_id, 
                                task_instance_id, user_id, data['timestamp'],
                                sequence_number, False)
            
            logger.debug(f"📝 [事件日志] 记录工作流事件: {event_type}")
            logger.debug(f"   - 工作流: {workflow_instance_id}")
            logger.debug(f"   - 事件ID: {event_id}")
            
            return event_id
            
        except Exception as e:
            logger.error(f"❌ [事件日志] 记录工作流事件失败: {e}")
            return None
    
    async def get_workflow_event_history(self, 
                                       workflow_instance_id: uuid.UUID,
                                       event_types: List[str] = None,
                                       limit: int = 100) -> List[Dict[str, Any]]:
        """获取工作流事件历史"""
        try:
            if event_types:
                placeholders = ', '.join(['%s'] * len(event_types))
                query = f"""
                    SELECT * FROM workflow_instance_event_log 
                    WHERE workflow_instance_id = %s 
                    AND event_type IN ({placeholders})
                    AND is_deleted = FALSE
                    ORDER BY sequence_number DESC
                    LIMIT %s
                """
                params = [workflow_instance_id] + event_types + [limit]
            else:
                query = """
                    SELECT * FROM workflow_instance_event_log 
                    WHERE workflow_instance_id = %s AND is_deleted = FALSE
                    ORDER BY sequence_number DESC
                    LIMIT %s
                """
                params = [workflow_instance_id, limit]
            
            results = await self.db.fetch_all(query, *params)
            
            # 解析JSON字段
            formatted_events = []
            for result in results:
                event = dict(result)
                event['event_data'] = json.loads(event.get('event_data', '{}'))
                formatted_events.append(event)
            
            logger.debug(f"📋 [事件历史] 获取到 {len(formatted_events)} 条事件记录")
            return formatted_events
            
        except Exception as e:
            logger.error(f"❌ [事件历史] 获取工作流事件历史失败: {e}")
            return []
    
    async def update_workflow_persistence_fields(self, 
                                                workflow_instance_id: uuid.UUID,
                                                execution_context: Dict[str, Any] = None,
                                                node_dependencies: Dict[str, Any] = None,
                                                completed_nodes: List[str] = None,
                                                execution_trace: List[Dict[str, Any]] = None,
                                                instance_metadata: Dict[str, Any] = None) -> bool:
        """更新工作流实例的持久化字段"""
        try:
            update_fields = []
            params = []
            
            if execution_context is not None:
                update_fields.append('execution_context = %s')
                params.append(safe_json_dumps(execution_context))
            
            if node_dependencies is not None:
                update_fields.append('node_dependencies = %s')
                params.append(safe_json_dumps(node_dependencies))
            
            if completed_nodes is not None:
                update_fields.append('completed_nodes = %s')
                params.append(safe_json_dumps(completed_nodes))
            
            if execution_trace is not None:
                update_fields.append('execution_trace = %s')
                params.append(safe_json_dumps(execution_trace))
            
            if instance_metadata is not None:
                update_fields.append('instance_metadata = %s')
                params.append(safe_json_dumps(instance_metadata))
            
            if not update_fields:
                return True  # 没有字段需要更新
            
            # 添加更新时间
            update_fields.append('updated_at = %s')
            params.append(now_utc())
            
            # 添加WHERE条件参数
            params.append(workflow_instance_id)
            
            query = f"""
                UPDATE workflow_instance 
                SET {', '.join(update_fields)}
                WHERE workflow_instance_id = %s
            """
            
            result = await self.db.execute(query, *params)
            
            logger.debug(f"📊 [持久化] 更新工作流持久化字段成功: {workflow_instance_id}")
            logger.debug(f"   - 更新字段: {len(update_fields) - 1} 个")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [持久化] 更新工作流持久化字段失败: {e}")
            return False
    
    async def auto_save_workflow_context(self, 
                                       workflow_instance_id: uuid.UUID,
                                       context_data: Dict[str, Any],
                                       save_threshold: int = 10) -> bool:
        """自动保存工作流上下文（批量优化）"""
        try:
            # 检查是否需要创建新快照（简化逻辑：每隔一定操作数保存一次）
            should_save = True  # 简化实现，每次调用都保存
            
            if should_save:
                snapshot_id = await self.save_workflow_context_snapshot(
                    workflow_instance_id=workflow_instance_id,
                    context_data=context_data,
                    snapshot_type='auto',
                    description=f'自动保存 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                )
                
                if snapshot_id:
                    # 记录自动保存事件
                    await self.log_workflow_event(
                        workflow_instance_id=workflow_instance_id,
                        event_type='context_auto_saved',
                        event_data={'snapshot_id': str(snapshot_id)}
                    )
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ [自动保存] 自动保存工作流上下文失败: {e}")
            return False
    
    async def cleanup_old_snapshots(self, 
                                  workflow_instance_id: uuid.UUID,
                                  keep_count: int = 50) -> int:
        """清理旧的工作流快照，保留最新的N个"""
        try:
            # 查询要删除的快照
            query = """
                SELECT snapshot_id FROM workflow_context_snapshot 
                WHERE workflow_instance_id = %s AND is_deleted = FALSE
                ORDER BY created_at DESC
                LIMIT 18446744073709551615 OFFSET %s
            """
            
            old_snapshots = await self.db.fetch_all(query, workflow_instance_id, keep_count)
            
            if old_snapshots:
                # 批量标记为删除
                snapshot_ids = [row['snapshot_id'] for row in old_snapshots]
                placeholders = ', '.join(['%s'] * len(snapshot_ids))
                
                delete_query = f"""
                    UPDATE workflow_context_snapshot 
                    SET is_deleted = TRUE, updated_at = %s
                    WHERE snapshot_id IN ({placeholders})
                """
                
                await self.db.execute(delete_query, now_utc(), *snapshot_ids)
                
                logger.info(f"🧹 [清理] 清理了 {len(snapshot_ids)} 个旧快照")
                return len(snapshot_ids)
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ [清理] 清理旧快照失败: {e}")
            return 0