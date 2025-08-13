"""
工作流导入导出服务
Workflow Import/Export Service
"""

import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from ..models.workflow_import_export import (
    WorkflowExport, WorkflowImport, ExportNode, ExportConnection,
    ExportNodeType, ImportPreview, ImportResult
)
from ..models.workflow import WorkflowCreate
from ..models.node import NodeCreate, NodeType, NodeConnectionCreate
from ..services.workflow_service import WorkflowService
from ..services.node_service import NodeService
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..repositories.node.node_repository import NodeRepository
from ..utils.exceptions import ValidationError, ConflictError


class WorkflowImportExportService:
    """工作流导入导出服务"""
    
    def __init__(self):
        self.workflow_service = WorkflowService()
        self.node_service = NodeService()
        self.workflow_repository = WorkflowRepository()
        self.node_repository = NodeRepository()
    
    async def export_workflow(self, workflow_base_id: uuid.UUID, user_id: uuid.UUID) -> WorkflowExport:
        """
        导出工作流为JSON格式
        
        Args:
            workflow_base_id: 工作流基础ID
            user_id: 用户ID
            
        Returns:
            导出的工作流数据
        """
        try:
            logger.info(f"开始导出工作流: {workflow_base_id}")
            
            # 获取工作流信息
            workflow = await self.workflow_service.get_workflow_by_base_id(workflow_base_id)
            if not workflow:
                raise ValidationError("工作流不存在")
            
            # 检查权限
            if workflow.creator_id != user_id:
                raise ValidationError("无权导出此工作流")
            
            # 获取工作流节点（去除processor分配信息）
            nodes_data = await self.node_service.get_workflow_nodes(workflow_base_id, user_id)
            export_nodes = []
            
            # 处理节点数据 - 支持空工作流
            if nodes_data:
                for node_data in nodes_data:
                    export_node = ExportNode(
                        name=node_data.name,
                        type=ExportNodeType(node_data.type),
                        task_description=node_data.task_description,
                        position_x=node_data.position_x or 0,
                        position_y=node_data.position_y or 0
                        # 注意：这里不包含processor_id
                    )
                    export_nodes.append(export_node)
            else:
                logger.info(f"工作流 {workflow_base_id} 没有节点，导出空工作流模板")
            
            # 获取节点连接
            connections_data = await self.node_service.get_workflow_connections(workflow_base_id, user_id)
            export_connections = []
            
            # 创建节点ID到名称的映射 - 只有在有节点时才处理连接
            if nodes_data and connections_data:
                node_id_to_name = {}
                for node_data in nodes_data:
                    node_id_to_name[str(node_data.node_base_id)] = node_data.name
                
                for conn_data in connections_data:
                    # 使用正确的字段名 from_node_base_id 和 to_node_base_id
                    from_node_name = node_id_to_name.get(str(conn_data.get('from_node_base_id', '')))
                    to_node_name = node_id_to_name.get(str(conn_data.get('to_node_base_id', '')))
                    
                    logger.debug(f"处理导出连接: {conn_data.get('from_node_base_id')} -> {conn_data.get('to_node_base_id')}")
                    logger.debug(f"节点名称映射: {from_node_name} -> {to_node_name}")
                    
                    if from_node_name and to_node_name:
                        # 检查是否为自连接
                        if from_node_name == to_node_name:
                            logger.warning(f"发现自连接，跳过: 节点 {from_node_name} 连接到自己")
                            continue
                            
                        export_conn = ExportConnection(
                            from_node_name=from_node_name,
                            to_node_name=to_node_name,
                            connection_type=conn_data.get('connection_type', 'normal')
                        )
                        export_connections.append(export_conn)
                    else:
                        # 记录调试信息
                        logger.debug(f"连接跳过: from_node_base_id={conn_data.get('from_node_base_id')}, to_node_base_id={conn_data.get('to_node_base_id')}")
                        logger.debug(f"可用节点: {list(node_id_to_name.keys())}")
            else:
                logger.info(f"工作流 {workflow_base_id} 没有连接，跳过连接处理")
            
            # 创建导出数据
            export_data = WorkflowExport(
                name=workflow.name,
                description=workflow.description or "空工作流模板",
                export_version="1.0",
                export_timestamp=datetime.now().isoformat(),
                nodes=export_nodes,
                connections=export_connections,
                metadata={
                    "original_workflow_id": str(workflow_base_id),
                    "exported_by_user": str(user_id),
                    "node_count": len(export_nodes),
                    "connection_count": len(export_connections),
                    "is_empty_workflow": len(export_nodes) == 0
                }
            )
            
            logger.info(f"工作流导出完成: {workflow.name}, 节点数: {len(export_nodes)}, 连接数: {len(export_connections)}")
            return export_data
            
        except Exception as e:
            logger.error(f"导出工作流失败: {e}")
            raise
    
    async def preview_import(self, import_data: WorkflowImport, user_id: uuid.UUID) -> ImportPreview:
        """
        预览导入数据
        
        Args:
            import_data: 导入数据
            user_id: 用户ID
            
        Returns:
            导入预览信息
        """
        try:
            logger.info(f"预览工作流导入: {import_data.name}")
            
            # 验证数据
            validation_result = import_data.validate_import_data()
            
            # 检查名称冲突
            conflicts = []
            existing_workflows = await self.workflow_service.get_user_workflows(user_id)
            
            for workflow in existing_workflows:
                if workflow.name == import_data.name:
                    conflicts.append(f"已存在同名工作流: {import_data.name}")
                    break
            
            # 创建预览信息
            preview = ImportPreview(
                workflow_info={
                    "name": import_data.name,
                    "description": import_data.description or "无描述",
                    "export_version": getattr(import_data, 'export_version', '未知'),
                    "export_timestamp": getattr(import_data, 'export_timestamp', '未知')
                },
                nodes_count=len(import_data.nodes),
                connections_count=len(import_data.connections),
                validation_result=validation_result,
                conflicts=conflicts
            )
            
            return preview
            
        except Exception as e:
            logger.error(f"预览导入失败: {e}")
            raise
    
    async def import_workflow(
        self, 
        import_data: WorkflowImport, 
        user_id: uuid.UUID,
        overwrite: bool = False
    ) -> ImportResult:
        """
        导入工作流
        
        Args:
            import_data: 导入数据
            user_id: 用户ID
            overwrite: 是否覆盖同名工作流
            
        Returns:
            导入结果
        """
        try:
            logger.info(f"开始导入工作流: {import_data.name}")
            
            # 验证数据
            validation_result = import_data.validate_import_data()
            if not validation_result["valid"]:
                return ImportResult(
                    success=False,
                    message="导入数据验证失败",
                    errors=validation_result["errors"]
                )
            
            # 检查名称冲突
            if not overwrite:
                existing_workflows = await self.workflow_service.get_user_workflows(user_id)
                for workflow in existing_workflows:
                    if workflow.name == import_data.name:
                        return ImportResult(
                            success=False,
                            message=f"已存在同名工作流: {import_data.name}",
                            errors=[f"工作流名称 '{import_data.name}' 已存在"]
                        )
            
            # 创建工作流
            workflow_create = WorkflowCreate(
                name=import_data.name,
                description=import_data.description,
                creator_id=user_id
            )
            
            created_workflow = await self.workflow_service.create_workflow(workflow_create)
            workflow_base_id = created_workflow.workflow_base_id
            
            logger.info(f"工作流创建成功: {workflow_base_id}")
            
            # 创建节点
            created_nodes = {}  # name -> node_base_id
            nodes_created = 0
            
            # 检查重复节点名称
            node_names = [node_data.name for node_data in import_data.nodes]
            duplicate_names = [name for name in set(node_names) if node_names.count(name) > 1]
            if duplicate_names:
                logger.warning(f"发现重复的节点名称: {duplicate_names}")
            
            for node_data in import_data.nodes:
                node_create = NodeCreate(
                    name=node_data.name,
                    type=NodeType(node_data.type.value),
                    task_description=node_data.task_description,
                    position_x=node_data.position_x,
                    position_y=node_data.position_y,
                    workflow_base_id=workflow_base_id,
                    creator_id=user_id
                )
                
                created_node = await self.node_service.create_node(node_create, user_id)
                created_nodes[node_data.name] = created_node.node_base_id
                nodes_created += 1
                
                logger.debug(f"节点创建成功: {node_data.name} -> {created_node.node_base_id}")
                
            logger.info(f"创建了 {nodes_created} 个节点，节点映射: {created_nodes}")
            
            # 创建连接
            connections_created = 0
            for conn_data in import_data.connections:
                from_node_id = created_nodes.get(conn_data.from_node_name)
                to_node_id = created_nodes.get(conn_data.to_node_name)
                
                logger.info(f"处理连接: {conn_data.from_node_name} -> {conn_data.to_node_name}")
                logger.info(f"映射结果: {from_node_id} -> {to_node_id}")
                
                if from_node_id and to_node_id:
                    # 检查是否为自连接
                    if from_node_id == to_node_id:
                        logger.warning(f"跳过自连接: 节点 {conn_data.from_node_name} 尝试连接到自己")
                        continue
                    
                    # 创建NodeConnectionCreate对象
                    connection_create = NodeConnectionCreate(
                        from_node_base_id=from_node_id,
                        to_node_base_id=to_node_id,
                        workflow_base_id=workflow_base_id,
                        connection_type=conn_data.connection_type
                    )
                    
                    await self.node_service.create_node_connection(connection_create, user_id)
                    connections_created += 1
                    
                    logger.debug(f"连接创建成功: {conn_data.from_node_name} -> {conn_data.to_node_name}")
                else:
                    logger.warning(f"跳过连接: 找不到节点 {conn_data.from_node_name} 或 {conn_data.to_node_name}")
            
            result = ImportResult(
                success=True,
                workflow_id=str(workflow_base_id),
                message=f"工作流 '{import_data.name}' 导入成功",
                created_nodes=nodes_created,
                created_connections=connections_created,
                warnings=validation_result.get("warnings", [])
            )
            
            logger.info(f"工作流导入完成: {import_data.name}, 节点: {nodes_created}, 连接: {connections_created}")
            return result
            
        except Exception as e:
            logger.error(f"导入工作流失败: {e}")
            return ImportResult(
                success=False,
                message=f"导入失败: {str(e)}",
                errors=[str(e)]
            )
    
    def generate_workflow_filename(self, workflow_name: str) -> str:
        """生成工作流文件名"""
        # 清理文件名，移除特殊字符
        safe_name = "".join(c for c in workflow_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{safe_name}_{timestamp}.json"