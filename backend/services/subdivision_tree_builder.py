"""
Subdivision Tree Builder - Linus式简化版本

核心思想：
1. subdivision就是个该死的树，别搞复杂了
2. 有parent_subdivision_id就够了，直接构建树
3. 一个数据结构，一套算法，搞定所有布局
4. 消除所有特殊情况和边界条件

"如果你需要超过3层缩进，你就已经完蛋了" - Linus
"""

import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class SubdivisionNode:
    """subdivision节点，简单清晰"""
    subdivision_id: str
    parent_id: Optional[str]
    workflow_base_id: str
    workflow_name: str
    workflow_instance_id: Optional[str]
    status: str
    node_name: str
    task_title: str
    created_at: str
    depth: int = 0
    children: List['SubdivisionNode'] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    def add_child(self, child: 'SubdivisionNode'):
        """添加子节点"""
        child.depth = self.depth + 1
        self.children.append(child)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "subdivision_id": self.subdivision_id,
            "parent_id": self.parent_id,
            "workflow_base_id": self.workflow_base_id,
            "workflow_name": self.workflow_name,
            "workflow_instance_id": self.workflow_instance_id,
            "status": self.status,
            "node_name": self.node_name,
            "task_title": self.task_title,
            "created_at": self.created_at,
            "depth": self.depth,
            "children_count": len(self.children)
        }


class SubdivisionTree:
    """
    subdivision树构建器
    
    简单原则：
    - subdivision有parent_subdivision_id，这就是完美的树结构
    - 不需要复杂的图论算法
    - 不需要4套不同的数据结构
    - 一个查询，一次构建，一套布局算法
    """
    
    def __init__(self):
        self.nodes: Dict[str, SubdivisionNode] = {}
        self.roots: List[SubdivisionNode] = []
    
    def build_from_subdivisions(self, subdivisions: List[Dict[str, Any]]) -> 'SubdivisionTree':
        """
        从subdivision数据构建树
        
        Args:
            subdivisions: 从数据库查询的subdivision列表
            
        Returns:
            构建好的树
        """
        logger.info(f"🌳 构建subdivision树: {len(subdivisions)} 个节点")
        
        # 第一遍：创建所有节点
        for sub in subdivisions:
            node = SubdivisionNode(
                subdivision_id=str(sub['subdivision_id']),
                parent_id=str(sub['parent_subdivision_id']) if sub['parent_subdivision_id'] else None,
                workflow_base_id=str(sub['sub_workflow_base_id']),
                workflow_name=sub['sub_workflow_name'] or f"Workflow_{str(sub['sub_workflow_base_id'])[:8]}",
                workflow_instance_id=str(sub['sub_workflow_instance_id']) if sub['sub_workflow_instance_id'] else None,
                status=sub['sub_workflow_status'] or 'unknown',
                node_name=sub['original_node_name'],
                task_title=sub['task_title'],
                created_at=sub['subdivision_created_at'].isoformat() if hasattr(sub['subdivision_created_at'], 'isoformat') else str(sub['subdivision_created_at'])
            )
            self.nodes[node.subdivision_id] = node
        
        # 第二遍：构建父子关系
        for node in self.nodes.values():
            if node.parent_id and node.parent_id in self.nodes:
                self.nodes[node.parent_id].add_child(node)
            else:
                self.roots.append(node)
        
        logger.info(f"🌳 树构建完成: {len(self.roots)} 个根，最大深度 {self.get_max_depth()}")
        return self
    
    def get_max_depth(self) -> int:
        """获取最大深度"""
        max_depth = 0
        for root in self.roots:
            max_depth = max(max_depth, self._get_node_max_depth(root))
        return max_depth
    
    def _get_node_max_depth(self, node: SubdivisionNode) -> int:
        """递归获取节点最大深度"""
        if not node.children:
            return node.depth
        return max(self._get_node_max_depth(child) for child in node.children)
    
    def get_all_nodes(self) -> List[SubdivisionNode]:
        """获取所有节点的扁平列表"""
        nodes = []
        for root in self.roots:
            self._collect_nodes(root, nodes)
        return nodes
    
    def _collect_nodes(self, node: SubdivisionNode, result: List[SubdivisionNode]):
        """递归收集节点"""
        result.append(node)
        for child in node.children:
            self._collect_nodes(child, result)
    
    def calculate_layout_positions(self, node_spacing: int = 300, level_spacing: int = 200) -> Dict[str, Dict[str, int]]:
        """
        计算树状布局位置
        
        简单算法：
        - 每层从左到右排列
        - 子节点在父节点下方
        - 没有特殊情况
        """
        positions = {}
        
        for i, root in enumerate(self.roots):
            start_x = i * node_spacing * 2  # 根节点水平分布
            self._calculate_subtree_positions(root, start_x, 0, node_spacing, level_spacing, positions)
        
        return positions
    
    def _calculate_subtree_positions(self, node: SubdivisionNode, x: int, y: int, 
                                   node_spacing: int, level_spacing: int, 
                                   positions: Dict[str, Dict[str, int]]):
        """递归计算子树位置"""
        positions[node.subdivision_id] = {"x": x, "y": y}
        
        # 子节点在父节点下方水平排列
        child_count = len(node.children)
        if child_count > 0:
            start_x = x - (child_count - 1) * node_spacing // 2
            child_y = y + level_spacing
            
            for i, child in enumerate(node.children):
                child_x = start_x + i * node_spacing
                self._calculate_subtree_positions(child, child_x, child_y, node_spacing, level_spacing, positions)
    
    def to_graph_data(self) -> Dict[str, Any]:
        """
        转换为前端图形数据
        
        返回React Flow需要的nodes和edges格式
        """
        positions = self.calculate_layout_positions()
        
        nodes = []
        edges = []
        
        # 创建节点
        for node in self.get_all_nodes():
            pos = positions.get(node.subdivision_id, {"x": 0, "y": 0})
            
            flow_node = {
                "id": node.subdivision_id,
                "type": "workflowTemplate", 
                "position": pos,
                "data": {
                    "label": node.workflow_name,
                    "workflow_base_id": node.workflow_base_id,
                    "workflow_instance_id": node.workflow_instance_id,
                    "status": node.status,
                    "node_name": node.node_name,
                    "task_title": node.task_title,
                    "depth": node.depth,
                    "children_count": len(node.children),
                    "isRoot": node.parent_id is None
                }
            }
            nodes.append(flow_node)
            
            # 创建边
            for child in node.children:
                edge = {
                    "id": f"edge_{node.subdivision_id}_{child.subdivision_id}",
                    "source": node.subdivision_id,
                    "target": child.subdivision_id,
                    "type": "smoothstep",
                    "animated": child.status == "running",
                    "label": f"{node.node_name} → {child.workflow_name}"
                }
                edges.append(edge)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "layout": {
                "algorithm": "simple_tree",
                "max_depth": self.get_max_depth(),
                "total_nodes": len(nodes),
                "root_count": len(self.roots)
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取树统计信息"""
        all_nodes = self.get_all_nodes()
        
        return {
            "total_subdivisions": len(all_nodes),
            "root_subdivisions": len(self.roots),
            "max_depth": self.get_max_depth(),
            "completed_workflows": len([n for n in all_nodes if n.status == "completed"]),
            "running_workflows": len([n for n in all_nodes if n.status == "running"]),
            "failed_workflows": len([n for n in all_nodes if n.status == "failed"])
        }