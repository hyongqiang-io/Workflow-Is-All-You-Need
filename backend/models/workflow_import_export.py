"""
工作流导入导出模型
Workflow Import/Export Models
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ExportNodeType(str, Enum):
    """导出节点类型枚举"""
    START = "start"
    PROCESSOR = "processor" 
    END = "end"


class ExportNode(BaseModel):
    """导出节点模型 - 去除processor分配信息"""
    name: str = Field(..., description="节点名称")
    type: ExportNodeType = Field(..., description="节点类型")
    task_description: Optional[str] = Field(None, description="任务描述")
    position_x: float = Field(0, description="X坐标")
    position_y: float = Field(0, description="Y坐标")
    # 注意：不包含node_id，因为这是临时标识符，导入时会重新生成
    # 注意：不包含processor_id，这是关键特性


class ExportConnection(BaseModel):
    """导出连接模型 - 简化版本，只使用节点名称引用"""
    # 基本连接信息 - 只使用名称，不使用临时ID
    from_node_name: str = Field(..., description="源节点名称")
    to_node_name: str = Field(..., description="目标节点名称")
    
    # 连接详细信息
    connection_type: str = Field("normal", description="连接类型")
    condition_config: Optional[Dict[str, Any]] = Field(None, description="连接条件配置")
    
    # 可视化信息（如果有的话）
    connection_path: Optional[List[Dict[str, Any]]] = Field(None, description="连接路径坐标")
    style_config: Optional[Dict[str, Any]] = Field(None, description="连接样式配置")


class WorkflowExport(BaseModel):
    """工作流导出模型"""
    # 工作流元数据
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    
    # 版本信息
    export_version: str = Field("1.0", description="导出格式版本")
    export_timestamp: str = Field(..., description="导出时间戳")
    
    # 工作流结构
    nodes: List[ExportNode] = Field(..., description="节点列表")
    connections: List[ExportConnection] = Field(..., description="连接列表")
    
    # 额外元数据
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")


class WorkflowImport(BaseModel):
    """工作流导入模型"""
    # 工作流基本信息
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    
    # 工作流结构
    nodes: List[ExportNode] = Field(..., description="节点列表")
    connections: List[ExportConnection] = Field(..., description="连接列表")
    
    # 验证导入数据的完整性
    def validate_import_data(self) -> Dict[str, Any]:
        """验证导入数据的有效性"""
        errors = []
        warnings = []
        
        # 检查基本信息
        if not self.name or not self.name.strip():
            errors.append("工作流名称不能为空")
        
        # 检查节点
        if not self.nodes:
            errors.append("工作流至少需要一个节点")
        
        # 检查节点名称唯一性
        node_names = [node.name for node in self.nodes]
        duplicate_names = []
        seen_names = set()
        for name in node_names:
            if name in seen_names:
                duplicate_names.append(name)
            else:
                seen_names.add(name)
        
        if duplicate_names:
            errors.append(f"节点名称必须唯一，发现重复: {', '.join(set(duplicate_names))}")
        
        # 检查开始和结束节点
        start_nodes = [n for n in self.nodes if n.type == ExportNodeType.START]
        end_nodes = [n for n in self.nodes if n.type == ExportNodeType.END]
        
        if len(start_nodes) == 0:
            warnings.append("建议添加开始节点")
        elif len(start_nodes) > 1:
            warnings.append("建议只使用一个开始节点")
            
        if len(end_nodes) == 0:
            warnings.append("建议添加结束节点")
        elif len(end_nodes) > 1:
            warnings.append("建议只使用一个结束节点")
        
        # 检查连接的有效性
        unique_node_names = list(set(node_names))  # 使用去重后的名称列表
        for conn in self.connections:
            # 基本连接验证
            if conn.from_node_name not in unique_node_names:
                errors.append(f"连接中的源节点 '{conn.from_node_name}' 不存在")
            if conn.to_node_name not in unique_node_names:
                errors.append(f"连接中的目标节点 '{conn.to_node_name}' 不存在")
            
            # 检查自连接
            if conn.from_node_name == conn.to_node_name:
                errors.append(f"节点 '{conn.from_node_name}' 不能连接到自己")
            
            # 验证连接类型
            valid_connection_types = ['normal', 'conditional', 'parallel', 'fallback']
            if conn.connection_type not in valid_connection_types:
                warnings.append(f"连接类型 '{conn.connection_type}' 不在推荐类型中: {valid_connection_types}")
            
            # 验证新增字段的一致性（如果存在）
            if hasattr(conn, 'from_node_id') and hasattr(conn, 'to_node_id'):
                # 检查节点ID和名称的一致性
                from_node = next((n for n in self.nodes if n.name == conn.from_node_name), None)
                to_node = next((n for n in self.nodes if n.name == conn.to_node_name), None)
                
                if from_node and hasattr(from_node, 'node_id') and from_node.node_id != conn.from_node_id:
                    warnings.append(f"连接中源节点ID与节点定义不匹配: {conn.from_node_name}")
                
                if to_node and hasattr(to_node, 'node_id') and to_node.node_id != conn.to_node_id:
                    warnings.append(f"连接中目标节点ID与节点定义不匹配: {conn.to_node_name}")
            
            # 验证条件配置格式
            if hasattr(conn, 'condition_config') and conn.condition_config:
                try:
                    if isinstance(conn.condition_config, str):
                        import json
                        json.loads(conn.condition_config)
                except Exception:
                    warnings.append(f"连接 {conn.from_node_name} -> {conn.to_node_name} 的条件配置格式无效")
        
        # 检查工作流连通性
        if self.connections and len(self.nodes) > 1:
            # 简单的连通性检查：确保不是所有节点都孤立
            connected_nodes = set()
            for conn in self.connections:
                connected_nodes.add(conn.from_node_name)
                connected_nodes.add(conn.to_node_name)
            
            isolated_nodes = [n.name for n in self.nodes if n.name not in connected_nodes]
            if isolated_nodes:
                warnings.append(f"发现孤立节点（未连接）: {', '.join(isolated_nodes)}")
        
        # 检查是否有循环依赖（简单检查）
        if len(self.connections) > 0:
            # 构建邻接列表
            graph = {}
            for node in self.nodes:
                graph[node.name] = []
            
            for conn in self.connections:
                if conn.from_node_name in graph:
                    graph[conn.from_node_name].append(conn.to_node_name)
            
            # 检查是否有明显的循环（简单检查：A->B->A）
            for conn in self.connections:
                for reverse_conn in self.connections:
                    if (conn.from_node_name == reverse_conn.to_node_name and 
                        conn.to_node_name == reverse_conn.from_node_name):
                        warnings.append(f"发现潜在的循环依赖: {conn.from_node_name} <-> {conn.to_node_name}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def clean_import_data(self) -> 'WorkflowImport':
        """清理导入数据，自动修复常见问题"""
        # 1. 去除重复节点，保留第一个
        seen_names = set()
        cleaned_nodes = []
        for node in self.nodes:
            if node.name not in seen_names:
                seen_names.add(node.name)
                cleaned_nodes.append(node)
        
        # 2. 清理连接：移除自连接和无效连接
        valid_node_names = {node.name for node in cleaned_nodes}
        cleaned_connections = []
        
        for conn in self.connections:
            # 跳过自连接
            if conn.from_node_name == conn.to_node_name:
                continue
            
            # 跳过引用不存在节点的连接
            if (conn.from_node_name not in valid_node_names or 
                conn.to_node_name not in valid_node_names):
                continue
                
            cleaned_connections.append(conn)
        
        # 3. 去除重复连接
        unique_connections = []
        seen_connections = set()
        for conn in cleaned_connections:
            conn_key = (conn.from_node_name, conn.to_node_name, conn.connection_type)
            if conn_key not in seen_connections:
                seen_connections.add(conn_key)
                unique_connections.append(conn)
        
        # 返回清理后的数据
        return WorkflowImport(
            name=self.name,
            description=self.description,
            nodes=cleaned_nodes,
            connections=unique_connections
        )


class ImportPreview(BaseModel):
    """导入预览模型"""
    workflow_info: Dict[str, Any] = Field(..., description="工作流信息预览")
    nodes_count: int = Field(..., description="节点数量")
    connections_count: int = Field(..., description="连接数量")
    validation_result: Dict[str, Any] = Field(..., description="验证结果")
    conflicts: List[str] = Field([], description="可能的冲突")


class ImportResult(BaseModel):
    """导入结果模型"""
    success: bool = Field(..., description="是否成功")
    workflow_id: Optional[str] = Field(None, description="创建的工作流ID")
    message: str = Field(..., description="结果消息")
    created_nodes: int = Field(0, description="创建的节点数量")
    created_connections: int = Field(0, description="创建的连接数量")
    warnings: List[str] = Field([], description="警告信息")
    errors: List[str] = Field([], description="错误信息")