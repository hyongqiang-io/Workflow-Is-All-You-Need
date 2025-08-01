"""
级联删除服务
Cascade Deletion Service
"""

import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ..repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
from ..repositories.instance.node_instance_repository import NodeInstanceRepository
from ..repositories.instance.task_instance_repository import TaskInstanceRepository
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..utils.helpers import now_utc


class CascadeDeletionService:
    """级联删除服务 - 处理工作流相关数据的级联删除"""
    
    def __init__(self):
        self.workflow_repo = WorkflowRepository()
        self.workflow_instance_repo = WorkflowInstanceRepository()
        self.node_instance_repo = NodeInstanceRepository()
        self.task_instance_repo = TaskInstanceRepository()
    
    async def delete_workflow_instance_cascade(self, instance_id: uuid.UUID, 
                                             soft_delete: bool = True) -> Dict[str, Any]:
        """级联删除工作流实例及其所有相关数据"""
        try:
            logger.info(f"🗑️ 开始级联删除工作流实例: {instance_id}")
            logger.info(f"   删除方式: {'软删除' if soft_delete else '硬删除'}")
            
            # 使用工作流实例仓库的级联删除方法
            deletion_result = await self.workflow_instance_repo.delete_instance_cascade(
                instance_id, soft_delete
            )
            
            logger.info(f"✅ 工作流实例级联删除完成")
            return deletion_result
            
        except Exception as e:
            logger.error(f"级联删除工作流实例失败: {e}")
            raise
    
    async def delete_workflow_base_cascade(self, workflow_base_id: uuid.UUID, 
                                         soft_delete: bool = True) -> Dict[str, Any]:
        """级联删除工作流基础定义及其所有实例和相关数据"""
        try:
            logger.info(f"🗑️ 开始级联删除工作流基础定义: {workflow_base_id}")
            logger.info(f"   删除方式: {'软删除' if soft_delete else '硬删除'}")
            
            # 统计删除的数据量
            deletion_stats = {
                'workflow_base_id': str(workflow_base_id),
                'deleted_workflow_instances': 0,
                'deleted_tasks': 0,
                'deleted_nodes': 0,
                'deleted_workflow_base': False,
                'soft_delete': soft_delete,
                'instance_details': []
            }
            
            # 1. 查找所有基于此工作流的实例
            logger.info(f"📋 步骤1: 查找所有相关的工作流实例")
            instances_query = """
                SELECT workflow_instance_id, instance_name, status 
                FROM workflow_instance 
                WHERE workflow_base_id = $1 AND is_deleted = FALSE
            """
            instances = await self.workflow_instance_repo.db.fetch_all(
                instances_query, workflow_base_id
            )
            
            logger.info(f"   找到 {len(instances)} 个工作流实例需要删除")
            
            # 2. 逐个级联删除每个工作流实例
            total_deleted_tasks = 0
            total_deleted_nodes = 0
            
            for instance in instances:
                instance_id = instance['workflow_instance_id']
                instance_name = instance.get('instance_name', '未命名')
                
                logger.info(f"📋 删除工作流实例: {instance_name} ({instance_id})")
                
                # 级联删除单个工作流实例
                instance_deletion = await self.delete_workflow_instance_cascade(
                    instance_id, soft_delete
                )
                
                total_deleted_tasks += instance_deletion['deleted_tasks']
                total_deleted_nodes += instance_deletion['deleted_nodes']
                deletion_stats['instance_details'].append({
                    'instance_id': str(instance_id),
                    'instance_name': instance_name,
                    'deleted_tasks': instance_deletion['deleted_tasks'],
                    'deleted_nodes': instance_deletion['deleted_nodes'],
                    'success': instance_deletion['deleted_workflow']
                })
            
            deletion_stats['deleted_workflow_instances'] = len(instances)
            deletion_stats['deleted_tasks'] = total_deleted_tasks
            deletion_stats['deleted_nodes'] = total_deleted_nodes
            
            # 3. 删除工作流基础定义本身
            logger.info(f"📋 步骤3: 删除工作流基础定义")
            if soft_delete:
                workflow_deleted = await self.workflow_repo.delete(
                    workflow_base_id, "workflow_base_id", soft_delete=True
                )
            else:
                query = "DELETE FROM workflow WHERE workflow_base_id = $1"
                result = await self.workflow_repo.db.execute(query, workflow_base_id)
                workflow_deleted = "1" in result
            
            deletion_stats['deleted_workflow_base'] = workflow_deleted
            
            if workflow_deleted:
                logger.info(f"✅ 工作流基础定义级联删除成功:")
                logger.info(f"   - 工作流基础ID: {workflow_base_id}")
                logger.info(f"   - 删除的工作流实例: {deletion_stats['deleted_workflow_instances']} 个")
                logger.info(f"   - 删除的任务总数: {deletion_stats['deleted_tasks']} 个")
                logger.info(f"   - 删除的节点实例总数: {deletion_stats['deleted_nodes']} 个")
                logger.info(f"   - 删除方式: {'软删除' if soft_delete else '硬删除'}")
            else:
                logger.error(f"❌ 工作流基础定义级联删除失败: {workflow_base_id}")
            
            return deletion_stats
            
        except Exception as e:
            logger.error(f"级联删除工作流基础定义失败: {e}")
            raise
    
    async def get_deletion_preview(self, workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """预览删除操作将影响的数据量（不执行实际删除）"""
        try:
            logger.info(f"🔍 预览工作流删除影响: {workflow_base_id}")
            
            # 查询所有相关的工作流实例
            instances_query = """
                SELECT wi.workflow_instance_id, wi.instance_name, wi.status,
                       COUNT(DISTINCT ni.node_instance_id) as node_count,
                       COUNT(DISTINCT ti.task_instance_id) as task_count
                FROM workflow_instance wi
                LEFT JOIN node_instance ni ON wi.workflow_instance_id = ni.workflow_instance_id 
                                             AND ni.is_deleted = FALSE
                LEFT JOIN task_instance ti ON wi.workflow_instance_id = ti.workflow_instance_id 
                                             AND ti.is_deleted = FALSE
                WHERE wi.workflow_base_id = $1 AND wi.is_deleted = FALSE
                GROUP BY wi.workflow_instance_id, wi.instance_name, wi.status
            """
            instances = await self.workflow_instance_repo.db.fetch_all(
                instances_query, workflow_base_id
            )
            
            total_instances = len(instances)
            total_nodes = sum(int(inst.get('node_count', 0)) for inst in instances)
            total_tasks = sum(int(inst.get('task_count', 0)) for inst in instances)
            
            # 按状态分组统计
            status_summary = {}
            for instance in instances:
                status = instance.get('status', 'unknown')
                if status not in status_summary:
                    status_summary[status] = 0
                status_summary[status] += 1
            
            preview = {
                'workflow_base_id': str(workflow_base_id),
                'total_workflow_instances': total_instances,
                'total_node_instances': total_nodes,
                'total_task_instances': total_tasks,
                'instance_status_summary': status_summary,
                'instance_details': [
                    {
                        'instance_id': str(inst['workflow_instance_id']),
                        'instance_name': inst.get('instance_name', '未命名'),
                        'status': inst.get('status'),
                        'node_count': int(inst.get('node_count', 0)),
                        'task_count': int(inst.get('task_count', 0))
                    }
                    for inst in instances
                ]
            }
            
            logger.info(f"📊 删除预览结果:")
            logger.info(f"   - 工作流实例: {total_instances} 个")
            logger.info(f"   - 节点实例: {total_nodes} 个")
            logger.info(f"   - 任务实例: {total_tasks} 个")
            logger.info(f"   - 状态分布: {status_summary}")
            
            return preview
            
        except Exception as e:
            logger.error(f"获取删除预览失败: {e}")
            raise


# 创建全局服务实例
cascade_deletion_service = CascadeDeletionService()