"""
节点业务服务
Node Service
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..models.node import (
    NodeCreate, NodeUpdate, NodeResponse, NodeConnection, 
    NodeConnectionCreate, NodeConnectionUpdate, NodeType
)
from ..models.processor import NodeProcessorCreate
from ..repositories.node.node_repository import NodeRepository, NodeConnectionRepository
from ..repositories.processor.processor_repository import NodeProcessorRepository
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..utils.helpers import now_utc
from ..utils.exceptions import ValidationError, ConflictError


class NodeService:
    """节点业务服务"""
    
    def __init__(self):
        self.node_repository = NodeRepository()
        self.node_connection_repository = NodeConnectionRepository()
        self.node_processor_repository = NodeProcessorRepository()
        self.workflow_repository = WorkflowRepository()
    
    def _check_workflow_permission(self, workflow: Dict[str, Any], user_id: uuid.UUID) -> bool:
        """
        检查工作流权限
        
        Args:
            workflow: 工作流记录
            user_id: 用户ID
            
        Returns:
            是否有权限
        """
        workflow_creator_id = workflow['creator_id']
        if isinstance(workflow_creator_id, str):
            workflow_creator_id = uuid.UUID(workflow_creator_id)
        
        # 确保user_id也是UUID类型
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)
        
        return workflow_creator_id == user_id
    
    def _format_node_response(self, node_record: Dict[str, Any]) -> NodeResponse:
        """格式化节点响应"""
        try:
            # 安全地处理created_at时间戳
            created_at_str = None
            if node_record.get('created_at'):
                created_at = node_record['created_at']
                if hasattr(created_at, 'isoformat'):
                    created_at_str = created_at.isoformat()
                elif isinstance(created_at, str):
                    created_at_str = created_at
            
            # 安全地处理processor_id
            processor_id_str = None
            if node_record.get('processor_id'):
                processor_id_str = str(node_record['processor_id'])
            
            return NodeResponse(
                node_id=node_record['node_id'],
                node_base_id=node_record['node_base_id'],
                workflow_id=node_record['workflow_id'],
                workflow_base_id=node_record['workflow_base_id'],
                name=node_record['name'],
                type=NodeType(node_record['type']),
                task_description=node_record.get('task_description'),
                position_x=node_record.get('position_x'),
                position_y=node_record.get('position_y'),
                version=node_record.get('version', 1),
                parent_version_id=node_record.get('parent_version_id'),
                is_current_version=node_record.get('is_current_version', True),
                created_at=created_at_str,
                workflow_name=node_record.get('workflow_name'),
                processor_id=processor_id_str
            )
        except Exception as e:
            logger.error(f"格式化节点响应时出错: {e}, 节点记录: {node_record}")
            raise
    
    async def create_node(self, node_data: NodeCreate, user_id: uuid.UUID) -> NodeResponse:
        """
        创建新节点
        
        Args:
            node_data: 节点创建数据
            user_id: 创建用户ID
            
        Returns:
            节点响应数据
            
        Raises:
            ValidationError: 输入数据无效
        """
        try:
            logger.info(f"开始创建节点 - 用户: {user_id}, 工作流: {node_data.workflow_base_id}")
            
            # 验证输入数据
            if not node_data.name or len(node_data.name.strip()) < 1:
                raise ValidationError("节点名称不能为空", "name")
            
            # 检查工作流是否存在
            workflow = await self.workflow_repository.get_workflow_by_base_id(node_data.workflow_base_id)
            if not workflow:
                raise ValidationError("工作流不存在", "workflow_base_id")
            
            # 检查权限 - 只有工作流创建者可以添加节点  
            if not self._check_workflow_permission(workflow, user_id):
                raise ValueError("只有工作流创建者可以添加节点")
            
            # 创建节点
            logger.info(f"[DEBUG] 开始调用node_repository.create_node")
            try:
                node_record = await self.node_repository.create_node(node_data)
                logger.info(f"[DEBUG] node_repository.create_node返回成功: {node_record is not None}")
                if node_record:
                    logger.info(f"[DEBUG] 返回的节点记录字段: {list(node_record.keys())}")
                    logger.info(f"[DEBUG] 节点记录内容: {node_record}")
            except Exception as repo_e:
                logger.error(f"[DEBUG] node_repository.create_node异常: {repo_e}")
                raise repo_e
            
            if not node_record:
                logger.error(f"[DEBUG] 节点创建返回None")
                raise ValueError("创建节点失败")
            
            logger.info(f"用户 {user_id} 在工作流 {node_data.workflow_base_id} 中创建了节点: {node_data.name}")
            
            # 处理processor_id关联（如果提供了）
            if hasattr(node_data, 'processor_id') and node_data.processor_id:
                try:
                    node_base_id = node_record.get('node_base_id')
                    logger.info(f"为新创建的节点添加处理器关联: {node_base_id} -> {node_data.processor_id}")
                    await self._add_node_processor_association(node_base_id, node_data.workflow_base_id, node_data.processor_id)
                    logger.info(f"成功添加节点-处理器关联")
                except Exception as e:
                    logger.error(f"添加节点-处理器关联失败: {e}")
                    # 不抛出异常，因为节点创建已经成功
            
            # 格式化节点响应
            logger.info(f"[DEBUG] 开始调用_format_node_response")
            try:
                response = self._format_node_response(node_record)
                logger.info(f"[DEBUG] _format_node_response返回成功")
                return response
            except Exception as format_e:
                logger.error(f"[DEBUG] _format_node_response异常: {format_e}")
                logger.error(f"[DEBUG] 异常类型: {type(format_e)}")
                import traceback
                logger.error(f"[DEBUG] 异常堆栈: {traceback.format_exc()}")
                raise format_e
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"创建节点失败: {e}")
            raise ValueError(f"创建节点失败: {str(e)}")
    
    async def get_node_by_base_id(self, node_base_id: uuid.UUID, 
                                 workflow_base_id: uuid.UUID) -> Optional[NodeResponse]:
        """
        根据基础ID获取当前版本节点
        
        Args:
            node_base_id: 节点基础ID
            workflow_base_id: 工作流基础ID
            
        Returns:
            节点响应数据或None
        """
        try:
            node_record = await self.node_repository.get_node_by_base_id(
                node_base_id, workflow_base_id
            )
            if not node_record:
                return None
            
            return self._format_node_response(node_record)
            
        except Exception as e:
            logger.error(f"获取节点失败: {e}")
            raise ValueError(f"获取节点失败: {str(e)}")
    
    async def get_workflow_nodes(self, workflow_base_id: uuid.UUID, 
                                user_id: uuid.UUID) -> List[NodeResponse]:
        """
        获取工作流的所有节点
        
        Args:
            workflow_base_id: 工作流基础ID
            user_id: 用户ID
            
        Returns:
            节点列表
        """
        try:
            logger.info(f"获取工作流节点 - 用户: {user_id}, 工作流: {workflow_base_id}")
            
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow:
                raise ValueError("工作流不存在")
            
            # 权限检查
            if not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权访问此工作流的节点")

            # 获取节点列表
            node_records = await self.node_repository.get_workflow_nodes(workflow_base_id)
            
            return [
                self._format_node_response(record) 
                for record in node_records
            ]
            
        except Exception as e:
            logger.error(f"获取工作流节点列表失败: {e}")
            raise ValueError(f"获取工作流节点列表失败: {str(e)}")
    
    async def update_node(self, node_base_id: uuid.UUID, 
                         workflow_base_id: uuid.UUID,
                         node_data: NodeUpdate, 
                         user_id: uuid.UUID) -> NodeResponse:
        """
        更新节点信息
        
        Args:
            node_base_id: 节点基础ID
            workflow_base_id: 工作流基础ID
            node_data: 更新数据
            user_id: 操作用户ID
            
        Returns:
            更新后的节点响应数据
        """
        try:
            logger.info(f"开始更新节点: node_base_id={node_base_id}, workflow_base_id={workflow_base_id}, user_id={user_id}")
            
            # 检查节点是否存在
            existing_node = await self.node_repository.get_node_by_base_id(
                node_base_id, workflow_base_id
            )
            logger.info(f"查询节点结果: existing_node={'存在' if existing_node else '不存在'}")
            
            if not existing_node:
                logger.error(f"节点不存在: node_base_id={node_base_id}, workflow_base_id={workflow_base_id}")
                raise ValueError("节点不存在")
            
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow or not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权修改此节点")
            
            # 处理和验证更新数据
            processed_data = NodeUpdate(
                name=node_data.name if node_data.name is not None else existing_node.get('name'),
                type=node_data.type if node_data.type is not None else NodeType(existing_node.get('type')),
                task_description=node_data.task_description if node_data.task_description is not None else existing_node.get('task_description', ''),
                position_x=node_data.position_x if node_data.position_x is not None else existing_node.get('position_x'),
                position_y=node_data.position_y if node_data.position_y is not None else existing_node.get('position_y'),
                processor_id=node_data.processor_id if hasattr(node_data, 'processor_id') else None
            )
            
            # 更新节点
            updated_node = await self.node_repository.update_node(
                node_base_id, workflow_base_id, processed_data
            )
            
            # 处理UPDATE成功但无法获取完整记录的情况
            if updated_node and updated_node.get("_update_success"):
                logger.info(f"节点更新成功但使用fallback响应: {node_base_id}")
                # 尝试重新查询节点信息
                try:
                    refreshed_node = await self.node_repository.get_node_by_base_id(node_base_id, workflow_base_id)
                    if refreshed_node:
                        updated_node = refreshed_node
                        logger.info(f"成功刷新节点数据: {node_base_id}")
                    else:
                        # 如果查询失败，构造基本的返回数据
                        logger.warning(f"无法刷新节点数据，使用基本信息: {node_base_id}")
                        updated_node = {
                            "node_base_id": node_base_id,
                            "workflow_base_id": workflow_base_id,
                            "name": processed_data.name,
                            "type": processed_data.type.value if processed_data.type else "processor",
                            "position_x": processed_data.position_x,
                            "position_y": processed_data.position_y,
                            "task_description": processed_data.task_description,
                            "_fallback": True
                        }
                except Exception as refresh_e:
                    logger.error(f"刷新节点数据失败: {refresh_e}")
                    # 仍然返回基本信息表示更新成功
                    updated_node = {
                        "node_base_id": node_base_id,
                        "workflow_base_id": workflow_base_id,
                        "name": processed_data.name,
                        "_fallback": True
                    }
            
            if not updated_node:
                raise ValueError("更新节点失败")
            
            # 处理处理器关联
            if node_data.processor_id is not None:
                logger.info(f"处理节点-处理器关联: node_base_id={node_base_id}, processor_id={node_data.processor_id}")
                
                if node_data.processor_id.strip():  # 如果有有效的processor_id
                    try:
                        # 先删除现有关联
                        await self._remove_node_processor_associations(node_base_id, workflow_base_id)
                        # 添加新关联
                        await self._add_node_processor_association(node_base_id, workflow_base_id, node_data.processor_id.strip())
                        logger.info(f"成功更新节点-处理器关联: {node_base_id} -> {node_data.processor_id}")
                    except Exception as e:
                        logger.error(f"更新节点-处理器关联失败: {e}")
                        # 不抛出异常，因为节点更新已经成功
                else:
                    # 如果processor_id为空，删除所有关联
                    await self._remove_node_processor_associations(node_base_id, workflow_base_id)
                    logger.info(f"清空节点-处理器关联: {node_base_id}")
            
            logger.info(f"用户 {user_id} 更新了节点: {node_base_id}")
            
            # 重新查询节点以包含最新的processor关联信息
            final_node = await self._get_node_with_processor(node_base_id, workflow_base_id)
            if final_node:
                return self._format_node_response_with_processor(final_node)
            else:
                # 如果查询失败，返回基本信息
                return self._format_node_response(updated_node)
            
        except ValidationError as e:
            logger.warning(f"节点更新数据验证失败: {e}")
            raise e
        except Exception as e:
            logger.error(f"更新节点失败: {e}")
            raise ValueError(f"更新节点失败: {str(e)}")
    
    async def delete_node(self, node_base_id: uuid.UUID, 
                         workflow_base_id: uuid.UUID,
                         user_id: uuid.UUID) -> bool:
        """
        删除节点
        
        Args:
            node_base_id: 节点基础ID
            workflow_base_id: 工作流基础ID
            user_id: 操作用户ID
            
        Returns:
            是否删除成功
        """
        try:
            # 检查节点是否存在
            existing_node = await self.node_repository.get_node_by_base_id(
                node_base_id, workflow_base_id
            )
            if not existing_node:
                raise ValueError("节点不存在")
            
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow or not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权删除此节点")
            
            # 执行删除
            success = await self.node_repository.delete_node(node_base_id, workflow_base_id)
            
            if success:
                logger.info(f"用户 {user_id} 删除了节点: {node_base_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"删除节点失败: {e}")
            raise ValueError(f"删除节点失败: {str(e)}")
    
    async def create_node_connection(self, connection_data: NodeConnectionCreate, 
                                   user_id: uuid.UUID) -> Dict[str, Any]:
        """
        创建节点连接
        
        Args:
            connection_data: 连接创建数据
            user_id: 操作用户ID
            
        Returns:
            连接信息
        """
        try:
            logger.info(f"创建节点连接 - 用户: {user_id}, 从 {connection_data.from_node_base_id} 到 {connection_data.to_node_base_id}")
            
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(
                connection_data.workflow_base_id
            )
            if not workflow:
                raise ValueError("工作流不存在")
            
            if not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权在此工作流中创建连接")
            
            # 检查源节点和目标节点是否存在
            from_node = await self.node_repository.get_node_by_base_id(
                connection_data.from_node_base_id, connection_data.workflow_base_id
            )
            to_node = await self.node_repository.get_node_by_base_id(
                connection_data.to_node_base_id, connection_data.workflow_base_id
            )
            
            if not from_node:
                raise ValueError("源节点不存在")
            if not to_node:
                raise ValueError("目标节点不存在")
            
            # 检查不能自己连接自己
            if connection_data.from_node_base_id == connection_data.to_node_base_id:
                raise ValueError("节点不能连接自己")
            
            # 创建连接
            connection = await self.node_connection_repository.create_connection(connection_data)
            if not connection:
                raise ValueError("创建节点连接失败")
            
            logger.info(f"用户 {user_id} 创建了节点连接: {connection_data.from_node_base_id} -> {connection_data.to_node_base_id}")
            
            # 格式化返回数据 - 确保创建的和现有的连接都正确格式化
            if connection and 'created_at' in connection and connection['created_at']:
                if hasattr(connection['created_at'], 'isoformat'):
                    connection['created_at'] = connection['created_at'].isoformat()
                # 如果已经是字符串格式，保持不变
            
            return connection
            
        except Exception as e:
            logger.error(f"创建节点连接失败: {e}")
            raise ValueError(f"创建节点连接失败: {str(e)}")
    
    async def get_workflow_connections(self, workflow_base_id: uuid.UUID, 
                                     user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        获取工作流的所有节点连接
        
        Args:
            workflow_base_id: 工作流基础ID
            user_id: 用户ID
            
        Returns:
            连接列表
        """
        try:
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow:
                raise ValueError("工作流不存在")
            
            # 权限检查
            if not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权访问此工作流的连接")
            
            # 获取连接列表
            connections = await self.node_connection_repository.get_workflow_connections(workflow_base_id)
            
            # 格式化时间戳
            for connection in connections:
                if connection.get('created_at'):
                    connection['created_at'] = connection['created_at'].isoformat()
            
            return connections
            
        except Exception as e:
            logger.error(f"获取工作流连接列表失败: {e}")
            raise ValueError(f"获取工作流连接列表失败: {str(e)}")
    
    async def delete_node_connection(self, from_node_base_id: uuid.UUID,
                                   to_node_base_id: uuid.UUID,
                                   workflow_base_id: uuid.UUID,
                                   user_id: uuid.UUID) -> bool:
        """
        删除节点连接
        
        Args:
            from_node_base_id: 源节点基础ID
            to_node_base_id: 目标节点基础ID
            workflow_base_id: 工作流基础ID
            user_id: 操作用户ID
            
        Returns:
            是否删除成功
        """
        try:
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow or not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权删除此工作流的连接")
            
            # 删除连接
            success = await self.node_connection_repository.delete_connection(
                from_node_base_id, to_node_base_id, workflow_base_id
            )
            
            if success:
                logger.info(f"用户 {user_id} 删除了节点连接: {from_node_base_id} -> {to_node_base_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"删除节点连接失败: {e}")
            raise ValueError(f"删除节点连接失败: {str(e)}")
    
    async def assign_processor_to_node(self, node_base_id: uuid.UUID,
                                     workflow_base_id: uuid.UUID,
                                     processor_id: uuid.UUID,
                                     user_id: uuid.UUID) -> Dict[str, Any]:
        """
        为节点分配处理器
        
        Args:
            node_base_id: 节点基础ID
            workflow_base_id: 工作流基础ID
            processor_id: 处理器ID
            user_id: 操作用户ID
            
        Returns:
            分配结果
        """
        try:
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow or not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权为此工作流的节点分配处理器")
            
            # 检查节点是否存在
            node = await self.node_repository.get_node_by_base_id(node_base_id, workflow_base_id)
            if not node:
                raise ValueError("节点不存在")
            
            # 🔧 Linus式修复：先删除旧的处理器绑定，避免重复绑定
            logger.info(f"🔧 为节点 {node_base_id} 分配处理器前，先清理旧绑定")
            await self.node_processor_repository.soft_delete_by_node(node_base_id)

            # 创建节点处理器关联
            assignment_data = NodeProcessorCreate(
                node_base_id=node_base_id,
                workflow_base_id=workflow_base_id,
                processor_id=processor_id
            )
            
            result = await self.node_processor_repository.create_node_processor(assignment_data)
            if not result:
                raise ValueError("分配处理器失败")
            
            logger.info(f"用户 {user_id} 为节点 {node_base_id} 分配了处理器 {processor_id}")
            
            # 格式化返回数据
            result['created_at'] = result['created_at'].isoformat() if result['created_at'] else None
            
            return result
            
        except Exception as e:
            logger.error(f"为节点分配处理器失败: {e}")
            raise ValueError(f"为节点分配处理器失败: {str(e)}")
    
    async def get_node_processors(self, node_base_id: uuid.UUID,
                                workflow_base_id: uuid.UUID,
                                user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        获取节点的处理器列表
        
        Args:
            node_base_id: 节点基础ID
            workflow_base_id: 工作流基础ID
            user_id: 用户ID
            
        Returns:
            处理器列表
        """
        try:
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow or not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权访问此工作流的节点处理器")
            
            # 获取处理器列表
            processors = await self.node_processor_repository.get_node_processors(
                node_base_id, workflow_base_id
            )
            
            # 格式化时间戳
            for processor in processors:
                if processor.get('created_at'):
                    processor['created_at'] = processor['created_at'].isoformat()
            
            return processors
            
        except Exception as e:
            logger.error(f"获取节点处理器列表失败: {e}")
            raise ValueError(f"获取节点处理器列表失败: {str(e)}")
    
    async def remove_processor_from_node(self, node_base_id: uuid.UUID,
                                       workflow_base_id: uuid.UUID,
                                       processor_id: uuid.UUID,
                                       user_id: uuid.UUID) -> bool:
        """
        从节点移除处理器
        
        Args:
            node_base_id: 节点基础ID
            workflow_base_id: 工作流基础ID
            processor_id: 处理器ID
            user_id: 操作用户ID
            
        Returns:
            是否移除成功
        """
        try:
            # 检查工作流权限
            workflow = await self.workflow_repository.get_workflow_by_base_id(workflow_base_id)
            if not workflow or not self._check_workflow_permission(workflow, user_id):
                raise ValueError("无权移除此工作流节点的处理器")
            
            # 移除处理器
            success = await self.node_processor_repository.delete_node_processor(
                node_base_id, workflow_base_id, processor_id
            )
            
            if success:
                logger.info(f"用户 {user_id} 从节点 {node_base_id} 移除了处理器 {processor_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"从节点移除处理器失败: {e}")
            raise ValueError(f"从节点移除处理器失败: {str(e)}")
    
    async def _remove_node_processor_associations(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID):
        """移除节点的所有处理器关联"""
        try:
            # 直接从数据库查询关联，避免权限检查
            existing_associations = await self.node_processor_repository.get_node_processors(
                node_base_id, workflow_base_id
            )
            
            # 删除所有关联
            for association in existing_associations:
                await self.node_processor_repository.delete_node_processor(
                    node_base_id, workflow_base_id, association['processor_id']
                )
                logger.info(f"移除节点-处理器关联: {node_base_id} -> {association['processor_id']}")
                
        except Exception as e:
            logger.error(f"移除节点处理器关联失败: {e}")
            # 不抛出异常，避免影响主要更新流程
    
    async def _add_node_processor_association(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID, processor_id: str):
        """添加节点-处理器关联"""
        try:
            import uuid as uuid_module
            
            # 转换processor_id为UUID
            processor_uuid = uuid_module.UUID(processor_id)
            
            # 创建关联
            assignment_data = NodeProcessorCreate(
                node_base_id=node_base_id,
                workflow_base_id=workflow_base_id,
                processor_id=processor_uuid
            )
            
            result = await self.node_processor_repository.create_node_processor(assignment_data)
            if result:
                logger.info(f"创建节点-处理器关联成功: {node_base_id} -> {processor_id}")
            else:
                logger.error(f"创建节点-处理器关联失败: {node_base_id} -> {processor_id}")
                
        except Exception as e:
            logger.error(f"添加节点处理器关联失败: {e}")
            raise
    
    async def _get_node_with_processor(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取包含processor信息的节点"""
        try:
            query = """
                SELECT 
                    n.*,
                    np.processor_id
                FROM `node` n
                LEFT JOIN node_processor np ON np.node_id = n.node_id
                WHERE n.node_base_id = %s 
                AND n.workflow_base_id = %s
                AND n.is_current_version = true 
                AND n.is_deleted = false
            """
            result = await self.node_repository.db.fetch_one(query, node_base_id, workflow_base_id)
            return result
        except Exception as e:
            logger.error(f"查询节点processor信息失败: {e}")
            return None
    
    def _format_node_response_with_processor(self, node_record: Dict[str, Any]) -> NodeResponse:
        """格式化包含processor的节点响应"""
        return NodeResponse(
            node_id=node_record['node_id'],
            node_base_id=node_record['node_base_id'],
            workflow_id=node_record['workflow_id'],
            workflow_base_id=node_record['workflow_base_id'],
            name=node_record['name'],
            type=NodeType(node_record['type']),
            task_description=node_record.get('task_description'),
            position_x=node_record.get('position_x'),
            position_y=node_record.get('position_y'),
            version=node_record['version'],
            parent_version_id=node_record.get('parent_version_id'),
            is_current_version=node_record['is_current_version'],
            created_at=node_record['created_at'].isoformat() if node_record['created_at'] else None,
            workflow_name=node_record.get('workflow_name'),
            processor_id=str(node_record['processor_id']) if node_record.get('processor_id') else None
        )