"""
工作流模板连接服务
Workflow Template Connection Service

用于获取和分析执行实例完成后的工作流模板之间的连接关系
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..repositories.base import BaseRepository
from ..utils.helpers import now_utc


class WorkflowTemplateConnectionService:
    """工作流模板连接服务"""
    
    def __init__(self):
        self.db = BaseRepository("workflow_template_connection").db
    
    async def get_workflow_template_connections(self, workflow_instance_id: uuid.UUID, max_depth: int = 10) -> Dict[str, Any]:
        """
        获取执行实例完成后的工作流模板连接图数据（支持递归展开）
        
        Args:
            workflow_instance_id: 工作流实例ID
            max_depth: 最大递归深度，防止无限递归
            
        Returns:
            包含模板连接关系的数据结构，支持多层嵌套
        """
        try:
            logger.info(f"🔍 获取工作流模板连接关系(递归深度 {max_depth}): {workflow_instance_id}")
            
            # 递归获取所有层级的模板连接关系
            all_connections = await self._get_recursive_template_connections(workflow_instance_id, max_depth)
            
            if not all_connections:
                logger.info(f"📋 未找到工作流实例的细分关系: {workflow_instance_id}")
                return {
                    "workflow_instance_id": str(workflow_instance_id),
                    "template_connections": [],
                    "connection_graph": {
                        "nodes": [],
                        "edges": []
                    },
                    "recursive_levels": 0
                }
            
            logger.info(f"📊 找到 {len(all_connections)} 个工作流模板连接关系（包含递归）")
            
            # 构建连接图数据结构（支持多层递归）
            connection_graph = self._build_recursive_connection_graph(all_connections)
            
            result = {
                "workflow_instance_id": str(workflow_instance_id),
                "template_connections": all_connections,
                "connection_graph": connection_graph,
                "recursive_levels": self._calculate_max_depth(all_connections),
                "statistics": {
                    "total_subdivisions": len(all_connections),
                    "completed_sub_workflows": len([c for c in all_connections if c["sub_workflow"]["status"] == "completed"]),
                    "unique_parent_workflows": len(set(c["parent_workflow"]["workflow_base_id"] for c in all_connections)),
                    "unique_sub_workflows": len(set(c["sub_workflow"]["workflow_base_id"] for c in all_connections)),
                    "max_recursion_depth": self._calculate_max_depth(all_connections)
                }
            }
            
            logger.info(f"✅ 工作流模板连接关系获取成功: {result['statistics']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取工作流模板连接关系失败: {e}")
            raise
    
    async def _get_recursive_template_connections(self, workflow_instance_id: uuid.UUID, max_depth: int, current_depth: int = 0) -> List[Dict[str, Any]]:
        """
        递归获取所有层级的模板连接关系
        
        Args:
            workflow_instance_id: 当前层级的工作流实例ID
            max_depth: 最大递归深度
            current_depth: 当前递归深度
            
        Returns:
            包含所有层级连接关系的列表
        """
        if current_depth >= max_depth:
            logger.warning(f"⚠️ 达到最大递归深度 {max_depth}，停止递归查询")
            return []
            
        logger.debug(f"🔄 递归查询层级 {current_depth}: {workflow_instance_id}")
        
        # 查询当前层级的直接子工作流
        subdivisions_query = """
        SELECT 
            ts.subdivision_id,
            ts.original_task_id,
            ts.sub_workflow_base_id,
            ts.sub_workflow_instance_id,
            ts.subdivision_name,
            ts.subdivision_description,
            ts.subdivision_created_at,
            
            -- 原始任务信息
            ti.task_title,
            ti.task_description,
            ti.node_instance_id,
            ti.workflow_instance_id as parent_workflow_instance_id,
            
            -- 原始节点信息  
            ni.node_id as original_node_id,
            n.node_base_id as original_node_base_id,
            n.name as original_node_name,
            n.type as original_node_type,
            n.workflow_base_id as parent_workflow_base_id,
            
            -- 父工作流信息
            pw.name as parent_workflow_name,
            pw.description as parent_workflow_description,
            
            -- 子工作流信息
            sw.name as sub_workflow_name,
            sw.description as sub_workflow_description,
            
            -- 子工作流实例完成状态
            swi.status as sub_workflow_status,
            swi.started_at as sub_workflow_started_at,
            swi.completed_at as sub_workflow_completed_at,
            
            -- 子工作流统计信息
            (SELECT COUNT(*) FROM node sn 
             WHERE sn.workflow_base_id = ts.sub_workflow_base_id 
             AND sn.is_current_version = TRUE 
             AND sn.is_deleted = FALSE) as sub_workflow_total_nodes,
             
            (SELECT COUNT(*) FROM node_instance sni 
             JOIN node sn ON sni.node_id = sn.node_id
             WHERE sn.workflow_base_id = ts.sub_workflow_base_id 
             AND sni.workflow_instance_id = ts.sub_workflow_instance_id
             AND sni.status = 'completed'
             AND sni.is_deleted = FALSE) as sub_workflow_completed_nodes
            
        FROM task_subdivision ts
        JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
        JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
        JOIN node n ON ni.node_id = n.node_id
        LEFT JOIN workflow pw ON n.workflow_base_id = pw.workflow_base_id AND pw.is_current_version = TRUE
        LEFT JOIN workflow sw ON ts.sub_workflow_base_id = sw.workflow_base_id AND sw.is_current_version = TRUE
        LEFT JOIN workflow_instance swi ON ts.sub_workflow_instance_id = swi.workflow_instance_id
        WHERE ti.workflow_instance_id = $1 
        AND ts.is_deleted = FALSE
        AND ti.is_deleted = FALSE
        AND ni.is_deleted = FALSE
        ORDER BY ts.subdivision_created_at
        """
        
        subdivisions = await self.db.fetch_all(subdivisions_query, workflow_instance_id)
        
        logger.info(f"📊 [DEBUG] 查询subdivision结果: 工作流实例 {workflow_instance_id}")
        logger.info(f"📊 [DEBUG] 找到 {len(subdivisions)} 个subdivision记录")
        
        for i, sub in enumerate(subdivisions):
            logger.info(f"📊 [DEBUG] Subdivision {i+1}:")
            logger.info(f"    - subdivision_id: {sub['subdivision_id']}")
            logger.info(f"    - subdivision_name: {sub['subdivision_name']}")
            logger.info(f"    - sub_workflow_base_id: {sub['sub_workflow_base_id']}")
            logger.info(f"    - sub_workflow_instance_id: {sub['sub_workflow_instance_id']}")
            logger.info(f"    - original_node_name: {sub['original_node_name']}")
            logger.info(f"    - sub_workflow_name: {sub['sub_workflow_name']}")
        
        # 转换当前层级的连接为标准格式
        current_connections = []
        child_instance_ids = []  # 记录子工作流实例ID，用于下层递归
        
        for subdivision in subdivisions:
            connection = {
                "subdivision_id": str(subdivision["subdivision_id"]),
                "subdivision_name": subdivision["subdivision_name"],
                "subdivision_description": subdivision["subdivision_description"] or "",
                "created_at": subdivision["subdivision_created_at"].isoformat() if subdivision["subdivision_created_at"] else None,
                "recursion_level": current_depth,  # 添加递归层级标识
                
                # 父工作流信息
                "parent_workflow": {
                    "workflow_base_id": str(subdivision["parent_workflow_base_id"]),
                    "workflow_name": subdivision["parent_workflow_name"] or f"工作流_{subdivision['parent_workflow_base_id'][:8]}",
                    "workflow_description": subdivision["parent_workflow_description"] or "",
                    "workflow_instance_id": str(subdivision["parent_workflow_instance_id"]),
                    "connected_node": {
                        "node_base_id": str(subdivision["original_node_base_id"]),
                        "node_name": subdivision["original_node_name"],
                        "node_type": subdivision["original_node_type"],
                        "task_title": subdivision["task_title"],
                        "task_description": subdivision["task_description"] or ""
                    }
                },
                
                # 子工作流信息
                "sub_workflow": {
                    "workflow_base_id": str(subdivision["sub_workflow_base_id"]),
                    "workflow_name": subdivision["sub_workflow_name"] or f"工作流_{subdivision['sub_workflow_base_id'][:8]}",
                    "workflow_description": subdivision["sub_workflow_description"] or "",
                    "instance_id": str(subdivision["sub_workflow_instance_id"]) if subdivision["sub_workflow_instance_id"] else None,
                    "status": subdivision["sub_workflow_status"] or "unknown",
                    "started_at": subdivision["sub_workflow_started_at"].isoformat() if subdivision["sub_workflow_started_at"] else None,
                    "completed_at": subdivision["sub_workflow_completed_at"].isoformat() if subdivision["sub_workflow_completed_at"] else None,
                    "total_nodes": subdivision["sub_workflow_total_nodes"] or 0,
                    "completed_nodes": subdivision["sub_workflow_completed_nodes"] or 0
                }
            }
            current_connections.append(connection)
            
            # 收集子工作流实例ID，用于递归查询
            if subdivision["sub_workflow_instance_id"]:
                child_instance_ids.append(subdivision["sub_workflow_instance_id"])
        
        # 递归查询子工作流的连接关系
        all_connections = current_connections.copy()
        for child_instance_id in child_instance_ids:
            try:
                child_connections = await self._get_recursive_template_connections(
                    child_instance_id, max_depth, current_depth + 1
                )
                all_connections.extend(child_connections)
            except Exception as e:
                logger.warning(f"⚠️ 递归查询子工作流 {child_instance_id} 失败: {e}")
                # 继续处理其他子工作流，不中断整个递归过程
                continue
        
        logger.debug(f"✅ 层级 {current_depth} 查询完成: 当前层 {len(current_connections)} 个，总计 {len(all_connections)} 个连接")
        return all_connections
    
    def _calculate_max_depth(self, connections: List[Dict[str, Any]]) -> int:
        """计算连接关系中的最大递归深度"""
        if not connections:
            return 0
        return max(conn.get("recursion_level", 0) for conn in connections) + 1
    
    def _build_recursive_connection_graph(self, template_connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建支持递归的连接图数据结构
        
        Args:
            template_connections: 包含所有层级的模板连接关系数据
            
        Returns:
            图形数据结构，包含多层级节点和边
        """
        try:
            nodes = {}
            edges = []
            
            # 按递归层级分组连接关系
            levels = {}
            for connection in template_connections:
                level = connection.get("recursion_level", 0)
                if level not in levels:
                    levels[level] = []
                levels[level].append(connection)
            
            logger.debug(f"🏗️ 构建递归连接图: {len(levels)} 个层级, 总计 {len(template_connections)} 个连接")
            
            # 构建节点（工作流模板）
            for connection in template_connections:
                parent_workflow = connection["parent_workflow"]
                sub_workflow = connection["sub_workflow"]
                recursion_level = connection.get("recursion_level", 0)
                
                # 添加父工作流节点
                parent_id = parent_workflow["workflow_base_id"]
                if parent_id not in nodes:
                    nodes[parent_id] = {
                        "id": parent_id,
                        "type": "workflow_template",
                        "label": parent_workflow["workflow_name"],
                        "description": parent_workflow["workflow_description"],
                        "is_parent": recursion_level == 0,  # 只有顶层是真正的父工作流
                        "recursion_level": recursion_level,
                        "connected_nodes": [],
                        "workflow_instance_id": parent_workflow.get("workflow_instance_id")
                    }
                
                # 记录连接的节点
                nodes[parent_id]["connected_nodes"].append({
                    "node_base_id": parent_workflow["connected_node"]["node_base_id"],
                    "node_name": parent_workflow["connected_node"]["node_name"],
                    "node_type": parent_workflow["connected_node"]["node_type"],
                    "subdivision_name": connection["subdivision_name"]
                })
                
                # 添加子工作流节点
                sub_id = sub_workflow["workflow_base_id"]
                if sub_id not in nodes:
                    nodes[sub_id] = {
                        "id": sub_id,
                        "type": "workflow_template",
                        "label": sub_workflow["workflow_name"],
                        "description": sub_workflow["workflow_description"],
                        "is_parent": False,
                        "recursion_level": recursion_level + 1,  # 子工作流在下一层级
                        "status": sub_workflow["status"],
                        "total_nodes": sub_workflow["total_nodes"],
                        "completed_nodes": sub_workflow["completed_nodes"],
                        "completion_rate": sub_workflow["completed_nodes"] / max(sub_workflow["total_nodes"], 1) if sub_workflow["total_nodes"] else 0,
                        "started_at": sub_workflow["started_at"],
                        "completed_at": sub_workflow["completed_at"],
                        "workflow_instance_id": sub_workflow.get("instance_id"),
                        "connected_nodes": []  # 添加缺失的字段
                    }
                
                # 添加连接边
                edge = {
                    "id": f"{parent_id}_{sub_id}_{connection['subdivision_id']}",
                    "source": parent_id,
                    "target": sub_id,
                    "type": "subdivision_connection",
                    "label": connection["subdivision_name"],
                    "subdivision_id": connection["subdivision_id"],
                    "connected_node_name": parent_workflow["connected_node"]["node_name"],
                    "task_title": parent_workflow["connected_node"]["task_title"],
                    "created_at": connection["created_at"],
                    "recursion_level": recursion_level,
                    "edge_weight": recursion_level + 1  # 用于可视化时的边权重
                }
                edges.append(edge)
            
            # 转换节点字典为列表
            node_list = list(nodes.values())
            
            # 按递归层级和名称排序节点
            node_list.sort(key=lambda x: (x["recursion_level"], not x["is_parent"], x["label"]))
            
            # 计算递归布局位置
            max_level = max(node["recursion_level"] for node in node_list) if node_list else 0
            level_node_counts = {}
            for node in node_list:
                level = node["recursion_level"]
                level_node_counts[level] = level_node_counts.get(level, 0) + 1
            
            # 构建节点位置映射（用于文件系统式布局）
            node_position_map = self._build_file_system_position_map(node_list, template_connections)
            
            # 构建树状布局的父子关系和位置映射
            tree_layout_data = self._build_tree_layout_data(node_list, template_connections)
            
            return {
                "nodes": node_list,
                "edges": edges,
                "layout": {
                    "algorithm": "recursive_hierarchical",
                    "direction": "TB",  # Top to Bottom
                    "node_spacing": 180,
                    "level_spacing": 120,
                    "max_recursion_level": max_level,
                    "level_node_counts": level_node_counts,
                    "node_position_map": node_position_map,  # 文件系统式布局映射
                    "tree_layout_data": tree_layout_data  # 新增：树状布局数据
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 构建递归连接图数据结构失败: {e}")
            return {
                "nodes": [],
                "edges": [],
                "layout": {}
            }
    
    def _build_tree_layout_data(self, node_list: List[Dict[str, Any]], template_connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建树状布局的数据结构
        
        Args:
            node_list: 节点列表
            template_connections: 模板连接关系
            
        Returns:
            树状布局数据结构
        """
        try:
            # 构建父子关系映射
            parent_child_map = {}  # parent_id -> [child_ids]
            child_parent_map = {}  # child_id -> parent_id
            
            for connection in template_connections:
                parent_id = connection["parent_workflow"]["workflow_base_id"]
                child_id = connection["sub_workflow"]["workflow_base_id"]
                
                if parent_id not in parent_child_map:
                    parent_child_map[parent_id] = []
                parent_child_map[parent_id].append(child_id)
                child_parent_map[child_id] = parent_id
            
            # 找到根节点（没有父节点的节点）
            all_node_ids = set(node["id"] for node in node_list)
            root_nodes = []
            for node_id in all_node_ids:
                if node_id not in child_parent_map:
                    root_nodes.append(node_id)
            
            # 构建树的层级结构
            tree_levels = {}  # level -> [node_ids]
            node_levels = {}  # node_id -> level
            
            # 使用BFS构建层级
            from collections import deque
            queue = deque()
            
            # 初始化根节点
            for root_id in root_nodes:
                queue.append((root_id, 0))
                node_levels[root_id] = 0
                if 0 not in tree_levels:
                    tree_levels[0] = []
                tree_levels[0].append(root_id)
            
            # BFS遍历构建树层级
            while queue:
                current_id, level = queue.popleft()
                
                # 添加子节点到下一层级
                if current_id in parent_child_map:
                    next_level = level + 1
                    if next_level not in tree_levels:
                        tree_levels[next_level] = []
                    
                    for child_id in parent_child_map[current_id]:
                        if child_id not in node_levels:  # 避免循环引用
                            node_levels[child_id] = next_level
                            tree_levels[next_level].append(child_id)
                            queue.append((child_id, next_level))
            
            # 计算每个节点在其层级中的位置
            node_positions = {}
            for level, node_ids in tree_levels.items():
                for index, node_id in enumerate(node_ids):
                    node_positions[node_id] = {
                        "level": level,
                        "index_in_level": index,
                        "total_in_level": len(node_ids),
                        "children": parent_child_map.get(node_id, []),
                        "parent": child_parent_map.get(node_id, None)
                    }
            
            logger.debug(f"🌳 构建树状布局数据: {len(tree_levels)} 层, {len(node_positions)} 个节点")
            
            return {
                "tree_levels": tree_levels,
                "node_levels": node_levels,
                "node_positions": node_positions,
                "parent_child_map": parent_child_map,
                "child_parent_map": child_parent_map,
                "root_nodes": root_nodes,
                "max_level": max(tree_levels.keys()) if tree_levels else 0
            }
            
        except Exception as e:
            logger.error(f"❌ 构建树状布局数据失败: {e}")
            return {
                "tree_levels": {},
                "node_levels": {},
                "node_positions": {},
                "parent_child_map": {},
                "child_parent_map": {},
                "root_nodes": [],
                "max_level": 0
            }
    
    def _build_file_system_position_map(self, node_list: List[Dict[str, Any]], template_connections: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        构建文件系统式布局的节点位置映射
        
        Args:
            node_list: 节点列表
            template_connections: 模板连接关系
            
        Returns:
            节点位置映射字典
        """
        try:
            position_map = {}
            
            # 按递归层级分组节点
            levels = {}
            for node in node_list:
                level = node.get("recursion_level", 0)
                if level not in levels:
                    levels[level] = []
                levels[level].append(node)
            
            # 构建父子关系映射
            parent_child_map = {}
            for connection in template_connections:
                parent_id = connection["parent_workflow"]["workflow_base_id"]
                child_id = connection["sub_workflow"]["workflow_base_id"]
                
                if parent_id not in parent_child_map:
                    parent_child_map[parent_id] = []
                parent_child_map[parent_id].append(child_id)
            
            # 为每个层级分配位置
            for level in sorted(levels.keys()):
                level_nodes = levels[level]
                
                if level == 0:  # 顶层节点
                    # 顶层节点按名称排序
                    level_nodes.sort(key=lambda x: x["label"])
                    for i, node in enumerate(level_nodes):
                        position_map[node["id"]] = {
                            "yIndex": i,
                            "indexInLevel": i,
                            "parentIndex": None
                        }
                else:  # 子层级节点
                    # 子节点按父节点分组，然后在父节点下方排列
                    y_index = 0
                    index_in_level = 0
                    
                    for node in level_nodes:
                        # 找到这个节点的父节点
                        parent_node = None
                        for connection in template_connections:
                            if connection["sub_workflow"]["workflow_base_id"] == node["id"]:
                                parent_id = connection["parent_workflow"]["workflow_base_id"]
                                parent_node = next((n for n in node_list if n["id"] == parent_id), None)
                                break
                        
                        parent_y_index = 0
                        if parent_node and parent_node["id"] in position_map:
                            parent_y_index = position_map[parent_node["id"]]["yIndex"]
                        
                        # 子节点放在父节点的下方
                        position_map[node["id"]] = {
                            "yIndex": parent_y_index + y_index + 1,  # 在父节点基础上加偏移
                            "indexInLevel": index_in_level,
                            "parentIndex": parent_y_index
                        }
                        
                        y_index += 1
                        index_in_level += 1
            
            logger.debug(f"🗂️ 构建文件系统位置映射: {len(position_map)} 个节点")
            return position_map
            
        except Exception as e:
            logger.error(f"❌ 构建文件系统位置映射失败: {e}")
            return {}
    
    def _build_connection_graph(self, template_connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建连接图数据结构
        
        Args:
            template_connections: 模板连接关系数据
            
        Returns:
            图形数据结构，包含节点和边
        """
        try:
            nodes = {}
            edges = []
            
            # 构建节点（工作流模板）
            for connection in template_connections:
                parent_workflow = connection["parent_workflow"]
                sub_workflow = connection["sub_workflow"]
                
                # 添加父工作流节点
                parent_id = parent_workflow["workflow_base_id"]
                if parent_id not in nodes:
                    nodes[parent_id] = {
                        "id": parent_id,
                        "type": "workflow_template",
                        "label": parent_workflow["workflow_name"],
                        "description": parent_workflow["workflow_description"],
                        "is_parent": True,
                        "connected_nodes": []
                    }
                
                # 记录连接的节点
                nodes[parent_id]["connected_nodes"].append({
                    "node_base_id": parent_workflow["connected_node"]["node_base_id"],
                    "node_name": parent_workflow["connected_node"]["node_name"],
                    "node_type": parent_workflow["connected_node"]["node_type"],
                    "subdivision_name": connection["subdivision_name"]
                })
                
                # 添加子工作流节点
                sub_id = sub_workflow["workflow_base_id"]
                if sub_id not in nodes:
                    nodes[sub_id] = {
                        "id": sub_id,
                        "type": "workflow_template",
                        "label": sub_workflow["workflow_name"],
                        "description": sub_workflow["workflow_description"],
                        "is_parent": False,
                        "status": sub_workflow["status"],
                        "total_nodes": sub_workflow["total_nodes"],
                        "completed_nodes": sub_workflow["completed_nodes"],
                        "completion_rate": sub_workflow["completed_nodes"] / max(sub_workflow["total_nodes"], 1),
                        "started_at": sub_workflow["started_at"],
                        "completed_at": sub_workflow["completed_at"],
                        "connected_nodes": []  # 添加缺失的字段
                    }
                
                # 添加连接边
                edge = {
                    "id": f"{parent_id}_{sub_id}_{connection['subdivision_id']}",
                    "source": parent_id,
                    "target": sub_id,
                    "type": "subdivision_connection",
                    "label": connection["subdivision_name"],
                    "subdivision_id": connection["subdivision_id"],
                    "connected_node_name": parent_workflow["connected_node"]["node_name"],
                    "task_title": parent_workflow["connected_node"]["task_title"],
                    "created_at": connection["created_at"]
                }
                edges.append(edge)
            
            # 转换节点字典为列表
            node_list = list(nodes.values())
            
            # 按层级排序节点（父工作流在前）
            node_list.sort(key=lambda x: (not x["is_parent"], x["label"]))
            
            return {
                "nodes": node_list,
                "edges": edges,
                "layout": {
                    "algorithm": "hierarchical",
                    "direction": "TB",  # Top to Bottom
                    "node_spacing": 150,
                    "level_spacing": 100
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 构建连接图数据结构失败: {e}")
            return {
                "nodes": [],
                "edges": [],
                "layout": {}
            }
    
    async def get_workflow_template_connection_summary(self, workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """
        获取工作流模板的连接关系摘要（用于显示模板级别的连接统计）
        
        Args:
            workflow_base_id: 工作流基础ID
            
        Returns:
            连接关系摘要数据
        """
        try:
            logger.info(f"🔍 获取工作流模板连接摘要: {workflow_base_id}")
            
            summary_query = """
            SELECT 
                COUNT(DISTINCT ts.subdivision_id) as total_subdivisions,
                COUNT(DISTINCT ts.sub_workflow_base_id) as unique_sub_workflows,
                COUNT(DISTINCT ni.node_base_id) as connected_nodes,
                COUNT(DISTINCT swi.workflow_instance_id) as sub_workflow_instances,
                COUNT(CASE WHEN swi.status = 'completed' THEN 1 END) as completed_instances,
                MIN(ts.subdivision_created_at) as first_subdivision_at,
                MAX(ts.subdivision_created_at) as last_subdivision_at
            FROM task_subdivision ts
            JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
            JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
            JOIN node n ON ni.node_id = n.node_id
            LEFT JOIN workflow_instance swi ON ts.sub_workflow_instance_id = swi.workflow_instance_id
            WHERE n.workflow_base_id = $1
            AND ts.is_deleted = FALSE
            AND ti.is_deleted = FALSE
            AND ni.is_deleted = FALSE
            """
            
            result = await self.db.fetch_one(summary_query, workflow_base_id)
            
            if result:
                summary = {
                    "workflow_base_id": str(workflow_base_id),
                    "total_subdivisions": result["total_subdivisions"] or 0,
                    "unique_sub_workflows": result["unique_sub_workflows"] or 0,
                    "connected_nodes": result["connected_nodes"] or 0,
                    "sub_workflow_instances": result["sub_workflow_instances"] or 0,
                    "completed_instances": result["completed_instances"] or 0,
                    "success_rate": (result["completed_instances"] or 0) / max(result["sub_workflow_instances"] or 1, 1),
                    "first_subdivision_at": result["first_subdivision_at"].isoformat() if result["first_subdivision_at"] else None,
                    "last_subdivision_at": result["last_subdivision_at"].isoformat() if result["last_subdivision_at"] else None
                }
                
                logger.info(f"✅ 工作流模板连接摘要: {summary}")
                return summary
            else:
                return {
                    "workflow_base_id": str(workflow_base_id),
                    "total_subdivisions": 0,
                    "unique_sub_workflows": 0,
                    "connected_nodes": 0,
                    "sub_workflow_instances": 0,
                    "completed_instances": 0,
                    "success_rate": 0,
                    "first_subdivision_at": None,
                    "last_subdivision_at": None
                }
                
        except Exception as e:
            logger.error(f"❌ 获取工作流模板连接摘要失败: {e}")
            raise
    
    async def get_detailed_workflow_connections(self, workflow_instance_id: uuid.UUID, max_depth: int = 10) -> Dict[str, Any]:
        """
        获取包含内部节点详情的工作流模板连接图数据
        
        Args:
            workflow_instance_id: 工作流实例ID
            max_depth: 最大递归深度
            
        Returns:
            包含详细内部节点信息的连接图数据
        """
        try:
            logger.info(f"🔍 获取详细工作流模板连接关系(递归深度 {max_depth}): {workflow_instance_id}")
            
            # 获取基础连接关系
            base_connections = await self.get_workflow_template_connections(workflow_instance_id, max_depth)
            
            # 获取每个工作流的详细内部结构
            detailed_workflows = {}
            unique_workflow_ids = set()
            
            # 收集所有唯一的工作流ID
            for connection in base_connections["template_connections"]:
                parent_id = connection["parent_workflow"]["workflow_base_id"]
                sub_id = connection["sub_workflow"]["workflow_base_id"]
                unique_workflow_ids.add(parent_id)
                unique_workflow_ids.add(sub_id)
            
            logger.info(f"📊 [DEBUG] 收集到的唯一工作流ID数量: {len(unique_workflow_ids)}")
            logger.info(f"📊 [DEBUG] 工作流ID列表: {list(unique_workflow_ids)}")
            logger.info(f"📊 [DEBUG] 模板连接关系数量: {len(base_connections['template_connections'])}")
            
            # 获取每个工作流的详细内部结构
            for workflow_base_id in unique_workflow_ids:
                logger.info(f"🔍 [DEBUG] 获取工作流 {workflow_base_id} 的内部结构...")
                detailed_workflows[workflow_base_id] = await self._get_workflow_internal_structure(
                    uuid.UUID(workflow_base_id)
                )
            
            # 分析可替换的节点对
            merge_candidates = self._analyze_merge_candidates(
                base_connections["template_connections"], 
                detailed_workflows
            )
            
            # 构建详细连接图
            detailed_graph = self._build_detailed_connection_graph(
                base_connections["template_connections"],
                detailed_workflows,
                merge_candidates
            )
            
            result = {
                **base_connections,
                "detailed_workflows": detailed_workflows,
                "merge_candidates": merge_candidates,
                "detailed_connection_graph": detailed_graph
            }
            
            logger.info(f"✅ 详细工作流模板连接关系获取成功: {len(detailed_workflows)} 个工作流")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取详细工作流模板连接关系失败: {e}")
            raise
    
    async def _get_workflow_internal_structure(self, workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """
        获取工作流的内部节点和连接结构
        
        Args:
            workflow_base_id: 工作流基础ID
            
        Returns:
            工作流内部结构数据
        """
        try:
            # 获取工作流的所有节点（基本信息，不包含processor）
            nodes_query = """
            SELECT 
                n.node_id,
                n.node_base_id,
                n.name,
                n.type,
                n.task_description,
                n.position_x,
                n.position_y,
                n.created_at,
                n.updated_at
            FROM node n
            WHERE n.workflow_base_id = $1
            AND n.is_current_version = TRUE
            AND n.is_deleted = FALSE
            ORDER BY n.created_at
            """
            
            nodes = await self.db.fetch_all(nodes_query, workflow_base_id)
            
            # 获取工作流的所有连接
            connections_query = """
            SELECT 
                CONCAT(nc.from_node_id, '-', nc.to_node_id) as connection_id,
                nc.from_node_id,
                nc.to_node_id,
                nc.connection_type,
                fn.node_base_id as from_node_base_id,
                fn.name as from_node_name,
                tn.node_base_id as to_node_base_id,
                tn.name as to_node_name
            FROM node_connection nc
            JOIN node fn ON nc.from_node_id = fn.node_id
            JOIN node tn ON nc.to_node_id = tn.node_id
            WHERE nc.workflow_id = (
                SELECT workflow_id 
                FROM workflow 
                WHERE workflow_base_id = %s 
                AND is_current_version = TRUE 
                LIMIT 1
            )
            ORDER BY nc.created_at
            """
            
            connections = await self.db.fetch_all(connections_query, workflow_base_id)
            
            # 转换节点数据格式
            formatted_nodes = []
            for node in nodes:
                formatted_nodes.append({
                    "node_id": str(node["node_id"]),
                    "node_base_id": str(node["node_base_id"]),
                    "name": node["name"],
                    "type": node["type"],
                    "task_description": node["task_description"] or "",
                    "position": {
                        "x": float(node["position_x"]) if node["position_x"] else 0,
                        "y": float(node["position_y"]) if node["position_y"] else 0
                    },
                    "created_at": node["created_at"].isoformat() if node["created_at"] else None,
                    "updated_at": node["updated_at"].isoformat() if node["updated_at"] else None
                })
            
            # 转换连接数据格式
            formatted_connections = []
            for connection in connections:
                formatted_connections.append({
                    "connection_id": str(connection["connection_id"]),
                    "from_node": {
                        "node_id": str(connection["from_node_id"]),
                        "node_base_id": str(connection["from_node_base_id"]),
                        "name": connection["from_node_name"]
                    },
                    "to_node": {
                        "node_id": str(connection["to_node_id"]),
                        "node_base_id": str(connection["to_node_base_id"]),
                        "name": connection["to_node_name"]
                    },
                    "connection_type": connection["connection_type"]
                })
            
            return {
                "workflow_base_id": str(workflow_base_id),
                "nodes": formatted_nodes,
                "connections": formatted_connections,
                "node_count": len(formatted_nodes),
                "connection_count": len(formatted_connections)
            }
            
        except Exception as e:
            logger.error(f"❌ 获取工作流内部结构失败: {workflow_base_id}, {e}")
            return {
                "workflow_base_id": str(workflow_base_id),
                "nodes": [],
                "connections": [],
                "node_count": 0,
                "connection_count": 0
            }
    
    def _analyze_merge_candidates(self, template_connections: List[Dict[str, Any]], detailed_workflows: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        分析可合并的节点对
        
        Args:
            template_connections: 模板连接关系
            detailed_workflows: 详细工作流结构
            
        Returns:
            可合并节点对列表
        """
        merge_candidates = []
        
        try:
            for connection in template_connections:
                parent_workflow_id = connection["parent_workflow"]["workflow_base_id"]
                sub_workflow_id = connection["sub_workflow"]["workflow_base_id"]
                connected_node_id = connection["parent_workflow"]["connected_node"]["node_base_id"]
                
                # 获取父工作流和子工作流的详细信息
                parent_workflow = detailed_workflows.get(parent_workflow_id, {})
                sub_workflow = detailed_workflows.get(sub_workflow_id, {})
                
                if not parent_workflow or not sub_workflow:
                    continue
                
                # 找到被细分的节点
                connected_node = None
                for node in parent_workflow.get("nodes", []):
                    if node["node_base_id"] == connected_node_id:
                        connected_node = node
                        break
                
                if not connected_node:
                    continue
                
                # 分析子工作流的开始和结束节点
                start_nodes = [n for n in sub_workflow.get("nodes", []) if n["type"] == "start"]
                end_nodes = [n for n in sub_workflow.get("nodes", []) if n["type"] == "end"]
                
                merge_candidate = {
                    "subdivision_id": connection["subdivision_id"],
                    "parent_workflow_id": parent_workflow_id,
                    "sub_workflow_id": sub_workflow_id,
                    "replaceable_node": {
                        "node_base_id": connected_node["node_base_id"],
                        "name": connected_node["name"],
                        "type": connected_node["type"],
                        "task_description": connected_node["task_description"]
                    },
                    "replacement_structure": {
                        "start_nodes": start_nodes,
                        "end_nodes": end_nodes,
                        "total_nodes": len(sub_workflow.get("nodes", [])),
                        "total_connections": len(sub_workflow.get("connections", []))
                    },
                    "compatibility": self._check_merge_compatibility(connected_node, sub_workflow),
                    "merge_complexity": "simple" if len(sub_workflow.get("nodes", [])) <= 5 else "complex"
                }
                
                merge_candidates.append(merge_candidate)
            
            logger.debug(f"🔍 分析到 {len(merge_candidates)} 个可合并节点对")
            return merge_candidates
            
        except Exception as e:
            logger.error(f"❌ 分析可合并节点对失败: {e}")
            return []
    
    def _check_merge_compatibility(self, parent_node: Dict[str, Any], sub_workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查节点合并的兼容性
        
        Args:
            parent_node: 父节点信息
            sub_workflow: 子工作流结构
            
        Returns:
            兼容性检查结果
        """
        try:
            compatibility = {
                "is_compatible": True,
                "issues": [],
                "recommendations": []
            }
            
            # 检查节点类型兼容性
            if parent_node["type"] != "processor":
                compatibility["is_compatible"] = False
                compatibility["issues"].append("只有处理器类型的节点可以被替换")
            
            # 检查子工作流结构
            start_nodes = [n for n in sub_workflow.get("nodes", []) if n["type"] == "start"]
            end_nodes = [n for n in sub_workflow.get("nodes", []) if n["type"] == "end"]
            
            if len(start_nodes) == 0:
                compatibility["issues"].append("子工作流缺少开始节点")
                compatibility["is_compatible"] = False
            elif len(start_nodes) > 1:
                compatibility["recommendations"].append("子工作流有多个开始节点，合并后可能需要调整连接")
            
            if len(end_nodes) == 0:
                compatibility["issues"].append("子工作流缺少结束节点")
                compatibility["is_compatible"] = False
            elif len(end_nodes) > 1:
                compatibility["recommendations"].append("子工作流有多个结束节点，合并后可能需要调整连接")
            
            # 检查复杂度
            node_count = len(sub_workflow.get("nodes", []))
            if node_count > 10:
                compatibility["recommendations"].append(f"子工作流较复杂({node_count}个节点)，建议仔细审查合并结果")
            
            return compatibility
            
        except Exception as e:
            logger.error(f"❌ 检查合并兼容性失败: {e}")
            return {
                "is_compatible": False,
                "issues": ["兼容性检查失败"],
                "recommendations": []
            }
    
    def _build_detailed_connection_graph(self, template_connections: List[Dict[str, Any]], detailed_workflows: Dict[str, Dict[str, Any]], merge_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        构建包含内部节点的详细连接图
        
        Args:
            template_connections: 模板连接关系
            detailed_workflows: 详细工作流结构
            merge_candidates: 可合并节点对
            
        Returns:
            详细连接图数据结构
        """
        try:
            nodes = []
            edges = []
            
            # 计算工作流布局位置
            workflow_positions = self._calculate_workflow_layout_positions(detailed_workflows)
            
            # 为每个工作流添加节点
            for workflow_id, workflow_data in detailed_workflows.items():
                workflow_pos = workflow_positions.get(workflow_id, {"x": 0, "y": 0})
                
                logger.info(f"🏗️ [DEBUG] 创建工作流容器节点: {workflow_id}")
                logger.info(f"    - 位置: x={workflow_pos['x']}, y={workflow_pos['y']}")
                logger.info(f"    - 节点数: {workflow_data.get('node_count', 0)}")
                logger.info(f"    - 连接数: {workflow_data.get('connection_count', 0)}")
                
                # 添加工作流容器节点
                workflow_node = {
                    "id": f"workflow_{workflow_id}",
                    "type": "workflow_container",
                    "label": f"工作流 {workflow_id[:8]}",
                    "position": {
                        "x": workflow_pos["x"],
                        "y": workflow_pos["y"]
                    },
                    "data": {
                        "workflow_base_id": workflow_id,
                        "node_count": workflow_data["node_count"],
                        "connection_count": workflow_data["connection_count"]
                    }
                }
                nodes.append(workflow_node)
                
                # 添加内部节点，基于工作流容器位置进行偏移
                internal_positions = self._calculate_internal_node_positions(
                    workflow_data.get("nodes", []),
                    workflow_pos,
                    workflow_data["node_count"]
                )
                
                for i, node in enumerate(workflow_data.get("nodes", [])):
                    internal_pos = internal_positions[i] if i < len(internal_positions) else {"x": 0, "y": 0}
                    
                    internal_node = {
                        "id": f"node_{node['node_base_id']}",
                        "type": "internal_node",
                        "label": node["name"],
                        "position": internal_pos,
                        "data": {
                            **node,
                            "parent_workflow_id": workflow_id,
                            "node_type": node["type"]
                        }
                    }
                    nodes.append(internal_node)
                
                # 添加内部连接
                for connection in workflow_data.get("connections", []):
                    internal_edge = {
                        "id": f"edge_{connection['connection_id']}",
                        "source": f"node_{connection['from_node']['node_base_id']}",
                        "target": f"node_{connection['to_node']['node_base_id']}",
                        "sourceHandle": "source",  # 添加默认的sourceHandle
                        "targetHandle": "target",  # 添加默认的targetHandle
                        "type": "internal_connection",
                        "label": connection["connection_type"],
                        "data": connection
                    }
                    edges.append(internal_edge)
            
            # 添加工作流间的连接
            for connection in template_connections:
                parent_id = connection["parent_workflow"]["workflow_base_id"]
                sub_id = connection["sub_workflow"]["workflow_base_id"]
                connected_node_id = connection["parent_workflow"]["connected_node"]["node_base_id"]
                
                # 添加从父工作流节点到子工作流的连接
                workflow_connection = {
                    "id": f"subdivision_{connection['subdivision_id']}",
                    "source": f"node_{connected_node_id}",
                    "target": f"workflow_{sub_id}",
                    "sourceHandle": "source",  # 添加默认的sourceHandle
                    "targetHandle": "target",  # 添加默认的targetHandle
                    "type": "subdivision_connection",
                    "label": connection["subdivision_name"],
                    "data": connection
                }
                edges.append(workflow_connection)
            
            logger.debug(f"🎨 构建详细连接图: {len(nodes)} 个节点, {len(edges)} 条边")
            
            return {
                "nodes": nodes,
                "edges": edges,
                "layout": {
                    "algorithm": "detailed_hierarchical",
                    "show_internal_nodes": True,
                    "node_spacing": 120,
                    "workflow_spacing": 300,
                    "level_spacing": 150
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 构建详细连接图失败: {e}")
            return {
                "nodes": [],
                "edges": [],
                "layout": {}
            }
    
    def _calculate_workflow_layout_positions(self, detailed_workflows: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """计算工作流的布局位置"""
        positions = {}
        workflow_spacing = 400
        
        workflow_ids = list(detailed_workflows.keys())
        
        for i, workflow_id in enumerate(workflow_ids):
            positions[workflow_id] = {
                "x": i * workflow_spacing,
                "y": 0
            }
        
        return positions
    
    def _calculate_internal_node_positions(self, nodes: List[Dict[str, Any]], base_position: Dict[str, float], node_count: int) -> List[Dict[str, float]]:
        """计算内部节点的位置"""
        positions = []
        node_spacing = 150
        nodes_per_row = 3
        
        base_x = base_position["x"] + 50  # 相对于工作流容器的偏移
        base_y = base_position["y"] + 100
        
        for i, node in enumerate(nodes):
            row = i // nodes_per_row
            col = i % nodes_per_row
            
            # 使用节点原始位置，如果没有则使用计算位置
            original_pos = node.get("position", {})
            if original_pos.get("x") and original_pos.get("y"):
                # 如果有原始位置，基于工作流容器进行偏移
                pos = {
                    "x": base_x + float(original_pos["x"]),
                    "y": base_y + float(original_pos["y"])
                }
            else:
                # 否则使用网格布局
                pos = {
                    "x": base_x + col * node_spacing,
                    "y": base_y + row * node_spacing
                }
            
            positions.append(pos)
        
        return positions