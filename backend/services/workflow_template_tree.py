"""
Workflow Template Tree - 工作流模板树

核心设计：
1. 每个节点都是工作流模板，而不是subdivision
2. 连接信息是父节点与子工作流的替换信息
3. 支持基于工作流模板树的合并和UI显示
4. 直接基于subdivision数据构建，但结构更清晰
"""

import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class WorkflowTemplateNode:
    """工作流模板节点 - 代表一个工作流模板"""
    workflow_base_id: str
    workflow_name: str
    workflow_instance_id: Optional[str] = None
    parent_node: Optional['WorkflowTemplateNode'] = None
    children: List['WorkflowTemplateNode'] = field(default_factory=list)
    node_replacements: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # 记录内部节点的替换关系: node_id -> source_subdivision
    depth: int = 0
    status: str = "unknown"
    # 添加字段来存储来源subdivision信息
    source_subdivision: Optional[Dict[str, Any]] = None
    
    # 🔧 新增：合并所需的完整数据，避免后续查subdivision表
    original_node_id: Optional[str] = None  # 被替换的原始节点ID
    original_task_id: Optional[str] = None  # 被替换的原始任务ID
    original_node_name: Optional[str] = None  # 被替换的原始节点名称
    original_node_position: Optional[Dict[str, int]] = None  # 原始节点位置 {x, y}
    merge_node_key: Optional[str] = None  # 用于合并操作的唯一标识
    
    def add_child_replacement(self, child_node: 'WorkflowTemplateNode', source_subdivision: Dict[str, Any]):
        """添加子工作流替换关系 - 记录哪个内部节点被哪个子工作流替换"""
        child_node.parent_node = self
        child_node.depth = self.depth + 1
        
        # 避免重复添加同一个子节点
        if child_node not in self.children:
            self.children.append(child_node)
        
        # 记录替换关系：内部节点ID -> 替换信息
        original_node_id = source_subdivision.get('original_task_id')  # 修正：使用original_task_id
        original_node_name = source_subdivision.get('original_node_name', '')
        
        # 如果没有original_task_id，使用original_node_name作为key
        replacement_key = str(original_node_id) if original_node_id else original_node_name
        
        if replacement_key:
            self.node_replacements[replacement_key] = {
                'child_workflow_base_id': child_node.workflow_base_id,
                'child_workflow_name': child_node.workflow_name,
                'child_workflow_instance_id': child_node.workflow_instance_id,
                'subdivision_id': source_subdivision.get('subdivision_id'),
                'original_node_name': original_node_name,
                'task_title': source_subdivision.get('task_title'),
                'created_at': source_subdivision.get('created_at')
            }
            
        logger.info(f"  📎 添加子工作流替换: {self.workflow_name}[{original_node_name}] -> {child_node.workflow_name}")
    
    def get_replacement_for_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取指定内部节点的替换信息"""
        return self.node_replacements.get(str(node_id))
    
    def get_all_replaced_nodes(self) -> List[str]:
        """获取所有被替换的内部节点ID列表"""
        return list(self.node_replacements.keys())
    
    def get_replacement_summary(self) -> Dict[str, Any]:
        """获取替换关系摘要"""
        return {
            'total_replacements': len(self.node_replacements),
            'replaced_nodes': list(self.node_replacements.keys()),
            'child_workflows': list(set(r['child_workflow_base_id'] for r in self.node_replacements.values())),
            'replacements_by_node': self.node_replacements
        }
    
    def get_all_descendants(self) -> List['WorkflowTemplateNode']:
        """获取所有后代节点"""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "workflow_base_id": self.workflow_base_id,
            "workflow_name": self.workflow_name,
            "workflow_instance_id": self.workflow_instance_id,
            "depth": self.depth,
            "status": self.status,
            "children_count": len(self.children),
            "node_replacements": self.node_replacements,
            "replaced_nodes_count": len(self.node_replacements),
            "replacement_summary": self.get_replacement_summary(),
            "source_subdivision": self.source_subdivision
        }


class WorkflowTemplateTree:
    """
    工作流模板树 - 替代SubdivisionTree的新结构
    
    核心思想：
    1. 以工作流模板为节点，而不是subdivision
    2. 树的边代表工作流替换关系
    3. 支持合并操作和UI显示
    4. 更清晰的数据结构，便于理解和维护
    """
    
    def __init__(self):
        self.nodes: Dict[str, WorkflowTemplateNode] = {}  # workflow_base_id -> node
        self.roots: List[WorkflowTemplateNode] = []
        self.instance_to_base: Dict[str, str] = {}  # workflow_instance_id -> workflow_base_id
    
    async def build_from_subdivisions(self, subdivisions: List[Dict[str, Any]], 
                               root_workflow_instance_id: str) -> 'WorkflowTemplateTree':
        """
        从subdivision数据构建工作流模板树
        
        Args:
            subdivisions: subdivision数据列表（这些是边的信息）
            root_workflow_instance_id: 根工作流实例ID
            
        Returns:
            构建好的工作流模板树
        """
        logger.info(f"🌳 构建工作流模板树: {len(subdivisions)} 个subdivision边, 根实例: {root_workflow_instance_id}")
        
        # 第一步：创建根节点（当前工作流实例对应的工作流模板）
        root_node = await self._create_root_node(root_workflow_instance_id)
        if root_node:
            self.nodes[root_node.workflow_base_id] = root_node
            self.roots.append(root_node)
            # 重要：将根节点也加入映射
            self.instance_to_base[root_workflow_instance_id] = root_node.workflow_base_id
            logger.info(f"  🌳 创建根节点: {root_node.workflow_name} ({str(root_node.workflow_base_id)[:8]})")
        
        # 第二步：为每个subdivision记录创建工作流模板节点，并预查询原始节点信息
        template_instances = {}
        
        # 🔧 批量查询原始节点信息，减少数据库查询
        original_nodes_info = await self._batch_get_original_nodes_info(subdivisions)
        
        for sub in subdivisions:
            subdivision_id = str(sub['subdivision_id'])
            child_workflow_base_id = str(sub['sub_workflow_base_id'])
            child_workflow_instance_id = str(sub['sub_workflow_instance_id'])
            
            # 从预查询结果中获取原始节点信息
            original_node_info = original_nodes_info.get(subdivision_id)
            
            # 为每个subdivision创建独立的工作流模板节点
            template_instances[subdivision_id] = sub
            
            # 建立实例到基础ID的映射
            self.instance_to_base[child_workflow_instance_id] = child_workflow_base_id
            
            # 还要记录父工作流实例的映射
            parent_instance_id = str(sub.get('root_workflow_instance_id', ''))
            if parent_instance_id and parent_instance_id != root_workflow_instance_id:
                # 查找父工作流实例对应的workflow_base_id
                for other_sub in subdivisions:
                    if str(other_sub.get('sub_workflow_instance_id', '')) == parent_instance_id:
                        parent_base_id = str(other_sub['sub_workflow_base_id'])
                        self.instance_to_base[parent_instance_id] = parent_base_id
                        break
        
        logger.info(f"📊 发现 {len(template_instances)} 个工作流模板实例节点")
        logger.info(f"🔗 建立 {len(self.instance_to_base)} 个实例->基础ID映射")
        
        # 调试：输出所有映射关系
        for instance_id, base_id in self.instance_to_base.items():
            instance_str = str(instance_id)[:8] if instance_id else "None"
            base_str = str(base_id)[:8] if base_id else "None"
            logger.info(f"    映射: {instance_str}... -> {base_str}...")
        
        # 第三步：为每个subdivision记录创建独立的工作流模板节点
        for subdivision_id, sub_data in template_instances.items():
            child_workflow_base_id = str(sub_data['sub_workflow_base_id'])
            child_workflow_instance_id = str(sub_data['sub_workflow_instance_id'])
            
            # 获取预查询的原始节点信息
            original_node_info = original_nodes_info.get(subdivision_id, {})
            
            # 使用subdivision_id作为节点的唯一标识，但保留工作流模板的信息
            node = WorkflowTemplateNode(
                workflow_base_id=child_workflow_base_id,  # 保留模板ID用于识别
                workflow_name=sub_data['sub_workflow_name'] or f"Workflow_{str(child_workflow_base_id)[:8]}",
                workflow_instance_id=child_workflow_instance_id,
                status=sub_data.get('sub_workflow_status', 'unknown'),
                source_subdivision=sub_data,  # 存储完整的subdivision信息
                # 🔧 新增：合并所需的完整数据
                original_node_id=original_node_info.get('node_id'),
                original_task_id=original_node_info.get('original_task_id'),
                original_node_name=original_node_info.get('name'),
                original_node_position={
                    'x': original_node_info.get('position_x', 0),
                    'y': original_node_info.get('position_y', 0)
                } if original_node_info.get('position_x') is not None else None,
                merge_node_key=subdivision_id  # 使用subdivision_id作为合并标识
            )
            
            # 使用subdivision_id作为节点的key，确保每个subdivision都有独立节点
            self.nodes[subdivision_id] = node
            logger.info(f"  🔧 创建工作流模板节点: {node.workflow_name} [subdivision: {subdivision_id[:8]}]")
        
        # 第四步：基于subdivision数据构建父子关系（subdivision作为边的信息）
        self._build_hierarchy_from_subdivisions(subdivisions, root_workflow_instance_id)
        
        logger.info(f"✅ 工作流模板树构建完成: {len(self.nodes)} 个模板节点, {len(self.roots)} 个根节点")
        logger.info(f"📊 最大深度: {self.get_max_depth()}")
        
        # 调试：输出树结构
        self._debug_print_tree_structure()
        
        return self
    
    async def _create_root_node(self, root_workflow_instance_id: str) -> Optional[WorkflowTemplateNode]:
        """创建根节点 - 当前工作流实例对应的工作流模板"""
        from ..repositories.base import BaseRepository
        
        try:
            db = BaseRepository("workflow_template_tree").db
            
            # 查询工作流实例对应的工作流模板信息
            root_info = await db.fetch_one("""
                SELECT wi.workflow_base_id, w.name, wi.status, wi.workflow_instance_id
                FROM workflow_instance wi
                JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id 
                WHERE wi.workflow_instance_id = %s 
                AND w.is_current_version = TRUE
            """, root_workflow_instance_id)
            
            if root_info:
                return WorkflowTemplateNode(
                    workflow_base_id=str(root_info['workflow_base_id']),
                    workflow_name=root_info['name'] or f"Root_Workflow_{str(root_info['workflow_base_id'])[:8]}",
                    workflow_instance_id=str(root_info['workflow_instance_id']),
                    status=root_info.get('status', 'unknown'),
                    depth=0  # 根节点深度为0
                )
            else:
                logger.warning(f"找不到根工作流实例信息: {root_workflow_instance_id}")
                return None
                
        except Exception as e:
            logger.error(f"创建根节点失败: {e}")
            return None
    
    async def _batch_get_original_nodes_info(self, subdivisions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """批量查询原始节点信息，避免重复数据库查询"""
        from ..repositories.base import BaseRepository
        
        if not subdivisions:
            return {}
            
        try:
            db = BaseRepository("workflow_template_tree").db
            
            # 提取所有subdivision_id
            subdivision_ids = [str(sub['subdivision_id']) for sub in subdivisions]
            logger.info(f"🔍 批量查询 {len(subdivision_ids)} 个subdivision的原始节点信息")
            
            # 构建批量查询SQL
            placeholders = ','.join(['%s'] * len(subdivision_ids))
            
            # 批量查询subdivision -> original_task -> node信息
            original_nodes = await db.fetch_all(f"""
                SELECT 
                    CAST(ts.subdivision_id AS CHAR) as subdivision_id,
                    ts.original_task_id,
                    ti.task_instance_id,
                    ni.node_instance_id,
                    n.node_id, 
                    n.position_x, 
                    n.position_y, 
                    n.name, 
                    n.type, 
                    n.task_description,
                    n.workflow_id, 
                    w.name as workflow_name
                FROM task_subdivision ts
                JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id  
                JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
                JOIN node n ON ni.node_id = n.node_id
                JOIN workflow w ON n.workflow_id = w.workflow_id
                WHERE ts.subdivision_id IN ({placeholders})
                AND ts.is_deleted = FALSE
            """, *subdivision_ids)
            
            # 构建subdivision_id -> 原始节点信息的映射
            result = {}
            for node_info in original_nodes:
                subdivision_id = node_info['subdivision_id']
                result[subdivision_id] = {
                    'original_task_id': node_info['original_task_id'],
                    'node_id': node_info['node_id'],
                    'position_x': node_info['position_x'],
                    'position_y': node_info['position_y'],
                    'name': node_info['name'],
                    'type': node_info['type'],
                    'task_description': node_info['task_description'],
                    'workflow_id': node_info['workflow_id'],
                    'workflow_name': node_info['workflow_name']
                }
            
            logger.info(f"✅ 批量查询完成: 找到 {len(result)} 个原始节点信息")
            
            # 调试：显示缺失的subdivision
            missing_subdivisions = set(subdivision_ids) - set(result.keys())
            if missing_subdivisions:
                logger.warning(f"⚠️ 缺失原始节点信息的subdivision: {list(missing_subdivisions)}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 批量查询原始节点信息失败: {e}")
            return {}
    
    def _build_hierarchy_from_subdivisions(self, subdivisions: List[Dict[str, Any]], 
                                         root_workflow_instance_id: str):
        """根据subdivision数据构建层级关系 - subdivision作为边的信息"""
        logger.info(f"🔗 构建工作流模板层级关系")
        
        # subdivision数据表示：parent_workflow中的某个节点被child_workflow替换
        for sub in subdivisions:
            subdivision_id = str(sub['subdivision_id'])
            child_workflow_base_id = str(sub['sub_workflow_base_id'])
            parent_workflow_instance_id = str(sub.get('root_workflow_instance_id', ''))
            
            # 构建替换信息 - 需要包含被替换的节点信息
            source_subdivision = {
                'subdivision_id': subdivision_id,
                'original_node_id': sub.get('original_task_id'),  # 添加被替换的节点ID
                'original_node_name': sub.get('original_node_name', ''),
                'task_title': sub.get('task_title', ''),
                'parent_workflow_instance_id': parent_workflow_instance_id,
                'created_at': sub.get('subdivision_created_at')
            }
            
            # 找到父工作流模板节点
            parent_node = None
            if parent_workflow_instance_id == root_workflow_instance_id:
                # 直接连接到根节点
                if len(self.roots) > 0:
                    parent_node = self.roots[0]
            else:
                # 查找对应的父工作流模板节点 - 现在需要通过subdivision_id查找
                for other_subdivision_id, other_node in self.nodes.items():
                    if (other_node.workflow_instance_id == parent_workflow_instance_id):
                        parent_node = other_node
                        break
            
            # 找到子工作流模板节点 - 现在使用subdivision_id作为key
            child_node = self.nodes.get(subdivision_id)
            
            if parent_node and child_node and child_node.parent_node is None:
                parent_node.add_child_replacement(child_node, sub)
                logger.info(f"    📎 建立替换关系: {parent_node.workflow_name}[{sub.get('original_node_name', '')}] -> {child_node.workflow_name}")
            else:
                if not parent_node:
                    logger.warning(f"    ⚠️ 找不到父工作流模板: {parent_workflow_instance_id}")
                if not child_node:
                    logger.warning(f"    ⚠️ 找不到子工作流模板: subdivision {subdivision_id}")
                if child_node and child_node.parent_node:
                    logger.warning(f"    ⚠️ 子工作流已有父节点: {child_node.workflow_name}")
        
        logger.info(f"🔗 层级关系构建完成")
    
    def _debug_print_tree_structure(self):
        """调试：输出树结构"""
        logger.info(f"🌳 [调试] 工作流模板树结构:")
        
        def print_node(node: WorkflowTemplateNode, prefix: str = "", is_last: bool = True):
            connector = "└── " if is_last else "├── "
            logger.info(f"{prefix}{connector}{node.workflow_name} (深度: {node.depth}, 替换: {len(node.node_replacements)})")
            
            # 输出替换信息
            for node_id, replacement in node.node_replacements.items():
                logger.info(f"{prefix}    📋 替换节点 {replacement['original_node_name']} -> {replacement['child_workflow_name']}")
            
            # 递归输出子节点
            children = node.children
            for i, child in enumerate(children):
                is_child_last = (i == len(children) - 1)
                child_prefix = prefix + ("    " if is_last else "│   ")
                print_node(child, child_prefix, is_child_last)
        
        for i, root in enumerate(self.roots):
            is_root_last = (i == len(self.roots) - 1)
            print_node(root, "", is_root_last)
    
    def get_merge_candidates_with_tree_data(self) -> List[Dict[str, Any]]:
        """获取可合并的候选节点 - 直接从树数据生成，无需查询subdivision表"""
        candidates = []
        
        # 获取所有非根节点（这些节点代表可合并的工作流）
        for node_key, node in self.nodes.items():
            if node.parent_node is not None:  # 排除根节点
                # 使用tree中已有的完整数据构建候选项
                candidate = {
                    'merge_node_key': node.merge_node_key or node_key,  # 合并标识
                    'subdivision_id': node.merge_node_key or node_key,  # 兼容字段
                    'parent_subdivision_id': self._find_node_key(node.parent_node) if node.parent_node else None,
                    'workflow_instance_id': node.workflow_instance_id or "",
                    'workflow_base_id': node.workflow_base_id,
                    'node_name': node.original_node_name or node.workflow_name,
                    'depth': node.depth,
                    'can_merge': True,
                    'merge_reason': "基于工作流模板树",
                    # 合并所需的完整数据
                    'original_node_id': node.original_node_id,
                    'original_task_id': node.original_task_id,
                    'original_node_position': node.original_node_position,
                    'status': node.status,
                    'tree_node': node  # 直接引用树节点，避免后续查询
                }
                candidates.append(candidate)
        
        # 按深度从高到低排序（深度优先，叶子节点先合并）
        candidates.sort(key=lambda c: c['depth'], reverse=True)
        
        logger.info(f"🔍 从工作流模板树获得 {len(candidates)} 个合并候选项")
        return candidates
    
    def _find_node_key(self, target_node: WorkflowTemplateNode) -> Optional[str]:
        """根据节点对象查找对应的key"""
        for key, node in self.nodes.items():
            if node is target_node:
                return key
        return None
    
    def calculate_recursive_merge_path(self, selected_node_keys: List[str]) -> List[Dict[str, Any]]:
        """
        计算递归合并路径 - 基于工作流模板树结构
        
        从选中的叶子节点开始，沿着树的路径向上递归到根节点
        返回需要合并的完整路径上的所有节点
        """
        logger.info(f"🌳 计算递归合并路径: {len(selected_node_keys)} 个选中节点")
        logger.info(f"🔍 [Debug] 选中的节点keys: {selected_node_keys}")
        
        # 🔧 调试：显示树中所有可用的keys
        available_keys = list(self.nodes.keys())
        logger.info(f"🔍 [Debug] 树中可用的keys数量: {len(available_keys)}")
        logger.info(f"🔍 [Debug] 树中前5个keys示例: {available_keys[:5]}")
        
        # 🔧 调试：检查key格式差异
        if selected_node_keys and available_keys:
            selected_sample = selected_node_keys[0]
            available_sample = available_keys[0]
            logger.info(f"🔍 [Debug] 选中key示例: '{selected_sample}' (长度: {len(selected_sample)})")
            logger.info(f"🔍 [Debug] 可用key示例: '{available_sample}' (长度: {len(available_sample)})")
        
        recursive_candidates = []
        processed_keys = set()
        
        for selected_key in selected_node_keys:
            if selected_key not in self.nodes:
                logger.warning(f"⚠️ 未找到选中的节点: {selected_key}")
                
                # 🔧 调试：尝试模糊匹配以发现问题
                potential_matches = []
                for available_key in available_keys:
                    if selected_key in available_key or available_key in selected_key:
                        potential_matches.append(available_key)
                
                if potential_matches:
                    logger.info(f"🔍 [Debug] 可能匹配的keys: {potential_matches[:3]}")
                else:
                    logger.warning(f"🔍 [Debug] 没有找到任何可能匹配的keys")
                continue
                
            logger.info(f"🔍 追踪节点路径: {selected_key}")
            
            # 从当前节点向上追踪到根节点
            current_node = self.nodes[selected_key]
            path_nodes = []
            
            while current_node is not None:
                current_key = self._find_node_key(current_node)
                
                if current_key and current_key not in processed_keys:
                    # 只有非根节点才需要合并（根节点代表初始工作流）
                    if current_node.parent_node is not None:
                        path_nodes.append({
                            'merge_node_key': current_key,
                            'subdivision_id': current_key,  # 兼容字段
                            'workflow_instance_id': current_node.workflow_instance_id or "",
                            'workflow_base_id': current_node.workflow_base_id,
                            'node_name': current_node.original_node_name or current_node.workflow_name,
                            'depth': current_node.depth,
                            'can_merge': True,
                            'merge_reason': f"递归合并路径节点",
                            # 合并所需的完整数据
                            'original_node_id': current_node.original_node_id,
                            'original_task_id': current_node.original_task_id,
                            'original_node_position': current_node.original_node_position,
                            'status': current_node.status,
                            'tree_node': current_node  # 直接引用树节点
                        })
                        processed_keys.add(current_key)
                        logger.info(f"   ✅ 添加到递归路径: {current_node.workflow_name} (深度: {current_node.depth})")
                
                # 向上移动到父节点
                current_node = current_node.parent_node
            
            recursive_candidates.extend(path_nodes)
        
        # 按深度从高到低排序（从叶子到根）
        recursive_candidates.sort(key=lambda c: c['depth'], reverse=True)
        
        logger.info(f"🔄 递归合并路径计算完成:")
        for candidate in recursive_candidates:
            logger.info(f"   - {candidate['node_name']} (深度: {candidate['depth']})")
        
        return recursive_candidates
    
    def get_all_nodes(self) -> List[WorkflowTemplateNode]:
        """获取所有节点的扁平列表"""
        return list(self.nodes.values())
    
    def get_merge_candidates(self) -> List[WorkflowTemplateNode]:
        """获取可合并的候选节点 - 按深度从高到低排序，包括根节点"""
        all_nodes = self.get_all_nodes()
        # 从最深层开始，包括根节点（深度0）
        # 根节点最后合并，因为它需要所有子工作流先完成合并
        return sorted(all_nodes, key=lambda n: n.depth, reverse=True)
    
    def get_max_depth(self) -> int:
        """获取最大深度"""
        if not self.roots:
            return 0
        
        def get_subtree_max_depth(node: WorkflowTemplateNode) -> int:
            if not node.children:
                return node.depth
            return max(get_subtree_max_depth(child) for child in node.children)
        
        return max(get_subtree_max_depth(root) for root in self.roots)
    
    def to_graph_data(self) -> Dict[str, Any]:
        """转换为前端图形数据"""
        nodes = []
        edges = []
        
        # 计算布局位置
        positions = self._calculate_layout_positions()
        
        # 生成节点
        for node_key, node in self.nodes.items():
            pos = positions.get(node_key, {"x": 0, "y": 0})
            
            # 为了前端兼容性，从第一个替换信息中提取字段
            first_replacement = None
            if node.node_replacements:
                first_replacement = list(node.node_replacements.values())[0]
            
            nodes.append({
                "id": f"template_{node_key}",  # 使用node_key（subdivision_id）作为ID
                "type": "workflowTemplate",
                "position": pos,
                "data": {
                    "label": node.workflow_name,
                    "workflow_base_id": node.workflow_base_id,
                    "workflow_instance_id": node.workflow_instance_id,
                    "status": node.status,
                    "depth": node.depth,
                    "isRoot": node.parent_node is None,
                    "isMainWorkflow": node.parent_node is None,  # 兼容前端字段
                    "children_count": len(node.children),
                    "node_replacements": node.node_replacements,
                    "replaced_nodes_count": len(node.node_replacements),
                    # 兼容原有subdivision字段 - 使用第一个替换信息
                    "subdivision_id": first_replacement.get('subdivision_id') if first_replacement else node_key,
                    "task_title": first_replacement.get('task_title') if first_replacement else None,
                    "node_name": first_replacement.get('original_node_name') if first_replacement else None
                }
            })
        
        # 生成边（工作流替换关系）- 基于父子关系
        for parent_key, parent_node in self.nodes.items():
            for child in parent_node.children:
                # 找到child对应的subdivision_id
                child_key = None
                for key, node in self.nodes.items():
                    if node is child:
                        child_key = key
                        break
                
                if child_key and child.source_subdivision:
                    # 直接从child的source_subdivision获取信息
                    sub_data = child.source_subdivision
                    original_node_name = sub_data.get('original_node_name', '')
                    
                    # 构建边的标签：节点名 -> 子工作流名
                    if original_node_name:
                        edge_label = f"{original_node_name} → {child.workflow_name}"
                    else:
                        # fallback：使用task_title
                        task_title = sub_data.get('task_title', '')
                        edge_label = f"{task_title} → {child.workflow_name}" if task_title else f"Node → {child.workflow_name}"
                    
                    edges.append({
                        "id": f"replacement_{parent_key}_{child_key}",
                        "source": f"template_{parent_key}",
                        "target": f"template_{child_key}",
                        "type": "smoothstep",
                        "animated": child.status == "running",
                        "label": edge_label,
                        "data": {
                            "relationship": "workflow_replacement",
                            "original_node_id": child_key,
                            "source_subdivision": {
                                'subdivision_id': child_key,
                                'original_node_name': original_node_name,
                                'task_title': sub_data.get('task_title', ''),
                                'child_workflow_name': child.workflow_name
                            },
                            # 兼容原有subdivision字段
                            "subdivision_id": child_key,
                            "subdivision_name": original_node_name,
                            "task_title": sub_data.get('task_title', '')
                        }
                    })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "layout": {
                "algorithm": "workflow_template_tree",
                "max_depth": self.get_max_depth(),
                "total_templates": len(self.nodes),
                "root_count": len(self.roots)
            }
        }
    
    def _calculate_layout_positions(self, node_spacing: int = 350, level_spacing: int = 250) -> Dict[str, Dict[str, int]]:
        """计算树状布局位置"""
        positions = {}
        
        # 为每个根节点分配起始X位置
        current_x = 0
        for root in self.roots:
            self._calculate_subtree_positions(
                root, current_x, 0, node_spacing, level_spacing, positions
            )
            current_x += 800  # 根节点之间的间距
        
        return positions
    
    def _calculate_subtree_positions(self, node: WorkflowTemplateNode, x: int, y: int, 
                                   node_spacing: int, level_spacing: int,
                                   positions: Dict[str, Dict[str, int]]):
        """递归计算子树位置"""
        # 找到节点对应的key
        node_key = None
        for key, n in self.nodes.items():
            if n is node:
                node_key = key
                break
        
        if node_key:
            positions[node_key] = {"x": x, "y": y}
        
        # 子节点排布
        child_count = len(node.children)
        if child_count > 0:
            # 计算子节点起始位置
            total_width = (child_count - 1) * node_spacing
            start_x = x - total_width // 2
            child_y = y + level_spacing
            
            for i, child in enumerate(node.children):
                child_x = start_x + i * node_spacing
                self._calculate_subtree_positions(
                    child, child_x, child_y, node_spacing, level_spacing, positions
                )
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取树统计信息 - 兼容旧版API格式"""
        all_nodes = self.get_all_nodes()
        
        # 按深度统计
        by_depth = {}
        total_replacements = 0
        
        for node in all_nodes:
            depth = node.depth
            if depth not in by_depth:
                by_depth[depth] = 0
            by_depth[depth] += 1
            total_replacements += len(node.node_replacements)
        
        # 兼容旧版API格式
        return {
            # 新格式字段
            "total_workflow_templates": len(all_nodes),
            "root_templates": len(self.roots),
            "max_depth": self.get_max_depth(),
            "by_depth": by_depth,
            "total_replacements": total_replacements,
            # 兼容旧版API格式
            "total_subdivisions": total_replacements,  # 用总替换数来代表subdivision数量
            "root_subdivisions": len(self.roots),
            "completed_workflows": len([n for n in all_nodes if n.status == "completed"]),
            "running_workflows": len([n for n in all_nodes if n.status == "running"]),
            "failed_workflows": len([n for n in all_nodes if n.status == "failed"]),
            # 其他兼容字段
            "completed_sub_workflows": len([n for n in all_nodes if n.status == "completed"]),
            "unique_workflows": len(all_nodes)
        }