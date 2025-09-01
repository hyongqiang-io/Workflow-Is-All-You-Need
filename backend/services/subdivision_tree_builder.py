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
    root_workflow_instance_id: Optional[str] = None  # 添加根工作流ID
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
        从subdivision数据构建树，支持跨工作流实例的嵌套关系
        
        Args:
            subdivisions: 从数据库查询的subdivision列表（包括递归的）
            
        Returns:
            构建好的树
        """
        logger.info(f"🌳 构建subdivision树: {len(subdivisions)} 个节点")
        
        # 第一遍：创建所有节点
        subdivision_to_workflow = {}  # subdivision_id -> workflow_instance_id 映射
        workflow_to_subdivision = {}  # workflow_instance_id -> subdivision_id 映射
        
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
                created_at=sub['subdivision_created_at'].isoformat() if hasattr(sub['subdivision_created_at'], 'isoformat') else str(sub['subdivision_created_at']),
                root_workflow_instance_id=str(sub['root_workflow_instance_id']) if sub.get('root_workflow_instance_id') else None,
                depth=sub.get('depth', 0)
            )
            
            self.nodes[node.subdivision_id] = node
            
            # 建立subdivision到工作流实例的映射关系
            if node.workflow_instance_id:
                subdivision_to_workflow[node.subdivision_id] = node.workflow_instance_id
                workflow_to_subdivision[node.workflow_instance_id] = node.subdivision_id
        
        logger.info(f"🔗 映射关系: {len(subdivision_to_workflow)} 个subdivision->workflow")
        
        # 第二遍：构建父子关系 - 修复版本
        logger.info(f"🔗 构建父子关系: {len(self.nodes)} 个节点")
        
        for sub_data in subdivisions:
            subdivision_id = str(sub_data['subdivision_id'])
            node = self.nodes[subdivision_id]
            parent_found = False
            
            # 方式1：使用parent_subdivision_id（直接的subdivision父子关系）
            if node.parent_id and node.parent_id in self.nodes:
                self.nodes[node.parent_id].add_child(node)
                parent_found = True
                parent_workflow_name = self.nodes[node.parent_id].workflow_name
                logger.info(f"  📎 直接父子关系: {parent_workflow_name} -> {node.workflow_name}")
            
            # 方式2：跨工作流的implicit父子关系
            # 如果subdivision B是在subdivision A创建的子工作流中产生的，则A是B的父级
            elif not parent_found:
                current_source_workflow_id = sub_data.get('root_workflow_instance_id')  # 当前subdivision来源工作流
                
                # 查找父subdivision：其sub_workflow_instance_id等于当前subdivision的来源工作流ID
                for other_sub_data in subdivisions:
                    other_subdivision_id = str(other_sub_data['subdivision_id'])
                    other_sub_workflow_id = str(other_sub_data['sub_workflow_instance_id']) if other_sub_data['sub_workflow_instance_id'] else None
                    
                    # 正确逻辑：如果其他subdivision的子工作流ID == 当前subdivision的来源工作流ID
                    # 说明当前subdivision是在其他subdivision创建的子工作流中产生的，其他subdivision是父级
                    if (other_subdivision_id != subdivision_id and 
                        other_sub_workflow_id and 
                        current_source_workflow_id and
                        other_sub_workflow_id == current_source_workflow_id):
                        
                        if other_subdivision_id in self.nodes:
                            # 添加循环检测和深度验证
                            potential_parent = self.nodes[other_subdivision_id]
                            if self._is_valid_parent_child_relationship(potential_parent, node):
                                self.nodes[other_subdivision_id].add_child(node)
                                node.parent_id = other_subdivision_id
                                parent_found = True
                                parent_workflow_name = self.nodes[other_subdivision_id].workflow_name
                                logger.info(f"  🔗 跨工作流父子关系: {parent_workflow_name} -> {node.workflow_name}")
                                logger.info(f"    详情: subdivision({other_subdivision_id})的子工作流({other_sub_workflow_id}) == subdivision({subdivision_id})的来源工作流({current_source_workflow_id})")
                                break
                            else:
                                logger.warning(f"  ⚠️ 跳过无效的父子关系: {other_subdivision_id} -> {subdivision_id} (可能导致循环或深度过深)")
            
            # 方式3：如果还没找到父节点，则为根节点
            if not parent_found:
                self.roots.append(node)
                logger.info(f"  🌳 根节点: {node.workflow_name}")
        
        logger.info(f"🌳 树构建完成: {len(self.roots)} 个根，最大深度 {self.get_max_depth()}")
        return self
    
    def _is_valid_parent_child_relationship(self, potential_parent: SubdivisionNode, child: SubdivisionNode) -> bool:
        """
        验证父子关系是否有效，防止循环引用和深度过深
        
        Args:
            potential_parent: 潜在的父节点
            child: 子节点
            
        Returns:
            是否为有效的父子关系
        """
        # 1. 防止自引用
        if potential_parent.subdivision_id == child.subdivision_id:
            return False
        
        # 2. 防止循环引用：检查potential_parent是否已经是child的后代
        current = potential_parent
        visited = set()
        max_check_depth = 10  # 防止无限循环检查
        check_count = 0
        
        while current and current.parent_id and check_count < max_check_depth:
            if current.parent_id in visited:
                # 检测到循环，但这不影响当前关系的有效性
                break
            visited.add(current.parent_id)
            
            # 如果potential_parent的祖先链中包含child，则会形成循环
            if current.parent_id == child.subdivision_id:
                logger.warning(f"防止循环引用: {potential_parent.subdivision_id} -> {child.subdivision_id}")
                return False
            
            # 向上查找
            current = self.nodes.get(current.parent_id)
            check_count += 1
        
        # 3. 检查深度限制（可选）
        if potential_parent.depth >= 5:  # 限制最大深度
            logger.warning(f"深度限制: 父节点 {potential_parent.subdivision_id} 深度已达到 {potential_parent.depth}")
            return False
        
        return True
    
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
    
    def calculate_layout_positions(self, node_spacing: int = 350, level_spacing: int = 250) -> Dict[str, Dict[str, int]]:
        """
        计算优化的树状布局位置
        
        算法改进：
        - 使用基于子树宽度的居中布局
        - 避免节点重叠
        - 支持深度嵌套的可视化
        """
        positions = {}
        
        # 计算每个节点的子树宽度
        subtree_widths = self._calculate_subtree_widths(node_spacing)
        
        # 为每个根节点分配起始X位置
        current_x = 0
        for root in self.roots:
            root_width = subtree_widths[root.subdivision_id]
            root_x = current_x + root_width // 2
            self._calculate_subtree_positions_optimized(
                root, root_x, 0, node_spacing, level_spacing, positions, subtree_widths
            )
            current_x += root_width + node_spacing * 2  # 根节点之间的间距
        
        return positions
    
    def _calculate_subtree_widths(self, node_spacing: int) -> Dict[str, int]:
        """计算每个节点的子树宽度"""
        widths = {}
        
        def calculate_width(node: SubdivisionNode) -> int:
            if not node.children:
                widths[node.subdivision_id] = node_spacing
                return node_spacing
            
            child_widths = [calculate_width(child) for child in node.children]
            total_child_width = sum(child_widths) + (len(child_widths) - 1) * node_spacing
            
            # 节点宽度至少是其自身大小，或所有子节点的宽度
            width = max(node_spacing, total_child_width)
            widths[node.subdivision_id] = width
            return width
        
        for root in self.roots:
            calculate_width(root)
        
        return widths
    
    def _calculate_subtree_positions_optimized(self, node: SubdivisionNode, x: int, y: int, 
                                             node_spacing: int, level_spacing: int, 
                                             positions: Dict[str, Dict[str, int]], 
                                             subtree_widths: Dict[str, int]):
        """递归计算优化的子树位置"""
        positions[node.subdivision_id] = {"x": x, "y": y}
        
        # 子节点排布
        child_count = len(node.children)
        if child_count > 0:
            # 计算所有子节点的总宽度
            total_child_width = sum(subtree_widths[child.subdivision_id] for child in node.children)
            total_spacing = (child_count - 1) * node_spacing
            total_width = total_child_width + total_spacing
            
            # 居中排布子节点
            start_x = x - total_width // 2
            child_y = y + level_spacing
            
            current_x = start_x
            for child in node.children:
                child_width = subtree_widths[child.subdivision_id]
                child_x = current_x + child_width // 2
                
                self._calculate_subtree_positions_optimized(
                    child, child_x, child_y, node_spacing, level_spacing, 
                    positions, subtree_widths
                )
                
                current_x += child_width + node_spacing
    
    def to_graph_data(self) -> Dict[str, Any]:
        """
        转换为前端图形数据
        
        修改：节点代表工作流实例，边代表subdivision关系
        """
        # 收集所有工作流实例
        workflow_nodes = {}  # workflow_instance_id -> node_data
        subdivision_edges = []  # subdivision关系作为边
        
        # 添加主工作流节点（如果有subdivision数据，主工作流应该是根工作流）
        main_workflow_ids = set()
        for node in self.get_all_nodes():
            # 从root_workflow_instance_id获取主工作流ID
            if hasattr(node, 'created_at') and node.workflow_instance_id:
                # 查找哪些工作流是主工作流（不是任何subdivision的子工作流）
                for sub_node in self.get_all_nodes():
                    root_id = getattr(sub_node, 'root_workflow_instance_id', None)
                    if root_id and root_id not in [n.workflow_instance_id for n in self.get_all_nodes()]:
                        main_workflow_ids.add(root_id)
        
        # 添加主工作流节点
        positions = self.calculate_layout_positions()
        y_offset = 0
        
        for main_workflow_id in main_workflow_ids:
            if main_workflow_id not in workflow_nodes:
                workflow_nodes[main_workflow_id] = {
                    "id": f"workflow_{main_workflow_id}",
                    "type": "workflowTemplate",
                    "position": {"x": 0, "y": y_offset},
                    "data": {
                        "label": f"Main Workflow",
                        "workflow_instance_id": main_workflow_id,
                        "status": "parent",
                        "isMainWorkflow": True,
                        "depth": 0
                    }
                }
                y_offset += 200
        
        # 添加子工作流节点
        for node in self.get_all_nodes():
            if node.workflow_instance_id and node.workflow_instance_id not in workflow_nodes:
                pos = positions.get(node.subdivision_id, {"x": 200, "y": y_offset})
                
                workflow_nodes[node.workflow_instance_id] = {
                    "id": f"workflow_{node.workflow_instance_id}",
                    "type": "workflowTemplate",
                    "position": pos,
                    "data": {
                        "label": node.workflow_name,
                        "workflow_instance_id": node.workflow_instance_id,
                        "workflow_base_id": node.workflow_base_id,
                        "status": node.status,
                        "isMainWorkflow": False,
                        "depth": node.depth,
                        "subdivision_id": node.subdivision_id,
                        "task_title": node.task_title,
                        "node_name": node.node_name
                    }
                }
                y_offset += 150
        
        # 创建subdivision边：基于subdivision数据和树结构
        processed_edges = set()  # 避免重复边
        
        # 方式1：为每个subdivision创建从其来源工作流到子工作流的边
        for node in self.get_all_nodes():
            parent_workflow_id = node.root_workflow_instance_id
            child_workflow_id = node.workflow_instance_id
            
            if parent_workflow_id and child_workflow_id and parent_workflow_id != child_workflow_id:
                edge_key = f"{parent_workflow_id}_{child_workflow_id}"
                
                if edge_key not in processed_edges:
                    processed_edges.add(edge_key)
                    
                    parent_node_id = f"workflow_{parent_workflow_id}"
                    child_node_id = f"workflow_{child_workflow_id}"
                    edge_id = f"subdivision_{node.subdivision_id}"
                    
                    subdivision_edges.append({
                        "id": edge_id,
                        "source": parent_node_id,
                        "target": child_node_id,
                        "type": "smoothstep",
                        "animated": node.status == "running",
                        "label": f"Subdivision: {node.node_name}",
                        "data": {
                            "subdivision_id": node.subdivision_id,
                            "subdivision_name": getattr(node, 'subdivision_name', node.node_name),
                            "task_title": node.task_title,
                            "relationship": "subdivision"
                        }
                    })
        
        nodes_list = list(workflow_nodes.values())
        
        logger.info(f"📊 图数据生成完成: {len(nodes_list)} 个工作流节点，{len(subdivision_edges)} 条subdivision边")
        
        return {
            "nodes": nodes_list,
            "edges": subdivision_edges,
            "layout": {
                "algorithm": "workflow_tree",
                "max_depth": self.get_max_depth(),
                "total_workflows": len(nodes_list),
                "total_subdivisions": len(subdivision_edges),
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