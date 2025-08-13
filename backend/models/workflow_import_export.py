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
    # 注意：不包含processor_id，这是关键


class ExportConnection(BaseModel):
    """导出连接模型"""
    from_node_name: str = Field(..., description="源节点名称")
    to_node_name: str = Field(..., description="目标节点名称")
    connection_type: str = Field("normal", description="连接类型")


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
        if len(node_names) != len(set(node_names)):
            errors.append("节点名称必须唯一")
        
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
        for conn in self.connections:
            if conn.from_node_name not in node_names:
                errors.append(f"连接中的源节点 '{conn.from_node_name}' 不存在")
            if conn.to_node_name not in node_names:
                errors.append(f"连接中的目标节点 '{conn.to_node_name}' 不存在")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


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