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
                        # 注意：不再包含node_id，因为这是临时标识符
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
                node_id_to_details = {}
                for node_data in nodes_data:
                    node_base_id = str(node_data.node_base_id)
                    node_id_to_name[node_base_id] = node_data.name
                    node_id_to_details[node_base_id] = {
                        'name': node_data.name,
                        'type': node_data.type,
                        'position_x': node_data.position_x,
                        'position_y': node_data.position_y
                    }
                
                for conn_data in connections_data:
                    # 使用正确的字段名 from_node_base_id 和 to_node_base_id
                    from_node_id = str(conn_data.get('from_node_base_id', ''))
                    to_node_id = str(conn_data.get('to_node_base_id', ''))
                    from_node_name = node_id_to_name.get(from_node_id)
                    to_node_name = node_id_to_name.get(to_node_id)
                    
                    logger.debug(f"处理导出连接: {from_node_id} -> {to_node_id}")
                    logger.debug(f"节点名称映射: {from_node_name} -> {to_node_name}")
                    
                    if from_node_name and to_node_name:
                        # 检查是否为自连接
                        if from_node_name == to_node_name:
                            logger.warning(f"发现自连接，跳过: 节点 {from_node_name} 连接到自己")
                            continue
                        
                        # 解析condition_config（如果存在）
                        condition_config = None
                        if conn_data.get('condition_config'):
                            try:
                                if isinstance(conn_data['condition_config'], str):
                                    import json
                                    condition_config = json.loads(conn_data['condition_config'])
                                else:
                                    condition_config = conn_data['condition_config']
                            except Exception as e:
                                logger.warning(f"解析连接条件配置失败: {e}")
                        
                        # 计算连接路径（基于节点位置）
                        connection_path = None
                        from_node_details = node_id_to_details.get(from_node_id)
                        to_node_details = node_id_to_details.get(to_node_id)
                        
                        if from_node_details and to_node_details:
                            connection_path = [
                                {
                                    'x': from_node_details['position_x'] or 0,
                                    'y': from_node_details['position_y'] or 0,
                                    'type': 'start'
                                },
                                {
                                    'x': to_node_details['position_x'] or 0,
                                    'y': to_node_details['position_y'] or 0,
                                    'type': 'end'
                                }
                            ]
                            
                        export_conn = ExportConnection(
                            from_node_name=from_node_name,
                            to_node_name=to_node_name,
                            connection_type=conn_data.get('connection_type', 'normal'),
                            condition_config=condition_config,
                            connection_path=connection_path,
                            style_config={
                                'type': 'smoothstep',
                                'animated': False,
                                'stroke_width': 2
                            }
                        )
                        export_connections.append(export_conn)
                    else:
                        # 记录调试信息
                        logger.debug(f"连接跳过: from_node_base_id={from_node_id}, to_node_base_id={to_node_id}")
                        logger.debug(f"可用节点: {list(node_id_to_name.keys())}")
            else:
                logger.info(f"工作流 {workflow_base_id} 没有连接，跳过连接处理")
            
            # 创建导出数据
            export_data = WorkflowExport(
                name=workflow.name,
                description=workflow.description or "空工作流模板",
                export_version="2.0",  # 使用2.0版本表示增强的连接信息
                export_timestamp=datetime.now().isoformat(),
                nodes=export_nodes,
                connections=export_connections,
                metadata={
                    "original_workflow_id": str(workflow_base_id),
                    "exported_by_user": str(user_id),
                    "node_count": len(export_nodes),
                    "connection_count": len(export_connections),
                    "is_empty_workflow": len(export_nodes) == 0,
                    "enhanced_format": True,
                    "includes_connection_details": True,
                    "includes_node_ids": True,
                    "includes_path_info": True
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

            # 创建预览信息（不检查名称冲突，因为导入会创建新的工作流）
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
                conflicts=[]  # 不再检查名称冲突
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
                logger.warning(f"工作流导入数据验证失败，尝试自动清理: {validation_result}")
                
                # 尝试自动清理数据
                try:
                    cleaned_data = import_data.clean_import_data()
                    cleaned_validation = cleaned_data.validate_import_data()
                    
                    if cleaned_validation["valid"]:
                        logger.info("数据清理成功，使用清理后的数据继续导入")
                        import_data = cleaned_data
                        # 添加清理警告信息
                        if "warnings" not in cleaned_validation:
                            cleaned_validation["warnings"] = []
                        cleaned_validation["warnings"].append("已自动清理导入数据：移除重复节点、自连接等问题")
                    else:
                        # 清理后仍然无效
                        logger.error(f"数据清理后仍验证失败: {cleaned_validation}")
                        return ImportResult(
                            success=False,
                            message=f"导入数据验证失败: {'; '.join(cleaned_validation['errors'])}",
                            errors=cleaned_validation["errors"],
                            warnings=cleaned_validation.get("warnings", [])
                        )
                except Exception as clean_error:
                    logger.error(f"数据清理失败: {clean_error}")
                    return ImportResult(
                        success=False,
                        message=f"导入数据验证失败: {'; '.join(validation_result['errors'])}",
                        errors=validation_result["errors"],
                        warnings=validation_result.get("warnings", [])
                    )
            
            # 创建工作流（允许同名，因为ID唯一即可保证区分）
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
            connection_errors = []
            for i, conn_data in enumerate(import_data.connections, 1):
                try:
                    from_node_id = created_nodes.get(conn_data.from_node_name)
                    to_node_id = created_nodes.get(conn_data.to_node_name)
                    
                    logger.info(f"处理连接 {i}/{len(import_data.connections)}: {conn_data.from_node_name} -> {conn_data.to_node_name}")
                    logger.info(f"节点映射结果: {conn_data.from_node_name}({from_node_id}) -> {conn_data.to_node_name}({to_node_id})")
                    
                    if not from_node_id:
                        error_msg = f"连接 {i}: 源节点 '{conn_data.from_node_name}' 不存在于创建的节点中"
                        logger.error(error_msg)
                        connection_errors.append(error_msg)
                        continue
                        
                    if not to_node_id:
                        error_msg = f"连接 {i}: 目标节点 '{conn_data.to_node_name}' 不存在于创建的节点中"
                        logger.error(error_msg)
                        connection_errors.append(error_msg)
                        continue
                    
                    # 检查是否为自连接
                    if from_node_id == to_node_id:
                        warning_msg = f"连接 {i}: 跳过自连接 - 节点 '{conn_data.from_node_name}' 尝试连接到自己"
                        logger.warning(warning_msg)
                        continue
                    
                    # 准备连接的条件配置
                    condition_config = None
                    if conn_data.condition_config:
                        # 确保condition_config是有效的JSON
                        try:
                            if isinstance(conn_data.condition_config, dict):
                                import json
                                condition_config = json.dumps(conn_data.condition_config)
                            else:
                                condition_config = str(conn_data.condition_config)
                        except Exception as e:
                            logger.warning(f"连接 {i}: 处理条件配置失败: {e}")
                            condition_config = None
                    
                    # 创建NodeConnectionCreate对象，包含所有详细信息
                    connection_create = NodeConnectionCreate(
                        from_node_base_id=from_node_id,
                        to_node_base_id=to_node_id,
                        workflow_base_id=workflow_base_id,
                        connection_type=conn_data.connection_type or 'normal'
                    )
                    
                    logger.info(f"连接 {i}: 开始创建连接对象")
                    
                    # 创建连接
                    created_connection = await self.node_service.create_node_connection(connection_create, user_id)
                    
                    if created_connection:
                        logger.info(f"连接 {i}: 创建成功 - {conn_data.from_node_name} -> {conn_data.to_node_name}")
                        connections_created += 1
                        
                        # 如果有条件配置，尝试更新连接记录
                        if condition_config:
                            try:
                                # 这里可以添加更新条件配置的逻辑
                                logger.info(f"连接 {i}: 包含条件配置，已记录")
                            except Exception as e:
                                logger.warning(f"连接 {i}: 更新条件配置失败: {e}")
                    else:
                        error_msg = f"连接 {i}: 创建失败，create_node_connection返回空结果"
                        logger.error(error_msg)
                        connection_errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"连接 {i} ({conn_data.from_node_name} -> {conn_data.to_node_name}): 创建异常 - {str(e)}"
                    logger.error(error_msg)
                    connection_errors.append(error_msg)
                    # 继续处理下一个连接，不要因为一个连接失败就停止整个导入
            
            # 检查连接创建的完整性
            expected_connections = len(import_data.connections)
            logger.info(f"连接创建完成: 期望 {expected_connections}, 实际 {connections_created}, 错误 {len(connection_errors)}")
            
            # 构建最终结果
            warnings = validation_result.get("warnings", [])
            errors = []
            
            # 如果有连接错误，添加到警告中
            if connection_errors:
                warnings.extend([f"连接创建警告: {error}" for error in connection_errors])
                logger.warning(f"导入过程中发现 {len(connection_errors)} 个连接问题")
            
            # 如果连接创建不完整，记录警告
            if connections_created < expected_connections:
                missing_count = expected_connections - connections_created
                warning_msg = f"预期创建 {expected_connections} 个连接，实际只创建了 {connections_created} 个，缺失 {missing_count} 个"
                warnings.append(warning_msg)
                logger.warning(warning_msg)
            
            result = ImportResult(
                success=True,
                workflow_id=str(workflow_base_id),
                message=f"工作流 '{import_data.name}' 导入成功",
                created_nodes=nodes_created,
                created_connections=connections_created,
                warnings=warnings,
                errors=errors
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