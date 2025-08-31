"""
工作流合并服务 - Subdivision Tree Merge Service

核心功能：
1. 从最低层开始逐层合并subdivision
2. 将父节点用子工作流替换
3. 去除子工作流的开始和结束节点
4. 重新连接上下游节点
5. 生成新的工作流模板
"""

import uuid
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from loguru import logger

from ..repositories.base import BaseRepository
from ..utils.helpers import now_utc
from .subdivision_tree_builder import SubdivisionTree, SubdivisionNode


@dataclass
class MergeCandidate:
    """合并候选项"""
    subdivision_id: str
    parent_subdivision_id: Optional[str]
    workflow_instance_id: str
    workflow_base_id: str
    node_name: str
    depth: int
    can_merge: bool = True
    merge_reason: str = ""


@dataclass
class MergeOperation:
    """合并操作"""
    target_node_id: str  # 被替换的父节点ID
    sub_workflow_id: str  # 替换用的子工作流ID
    subdivision_id: str  # 对应的subdivision ID
    depth: int  # 合并深度


class WorkflowMergeService:
    """工作流合并服务"""
    
    def __init__(self):
        self.db = BaseRepository("workflow_merge").db
    
    async def get_merge_candidates(self, workflow_instance_id: uuid.UUID) -> List[MergeCandidate]:
        """
        获取可合并的subdivision列表
        
        Args:
            workflow_instance_id: 工作流实例ID
            
        Returns:
            合并候选项列表，按深度从高到低排序（从叶子节点开始）
        """
        try:
            logger.info(f"🔍 获取合并候选: {workflow_instance_id}")
            
            # 使用subdivision tree builder获取树结构
            from .workflow_template_connection_service import WorkflowTemplateConnectionService
            connection_service = WorkflowTemplateConnectionService()
            
            subdivisions_data = await connection_service._get_all_subdivisions_simple(workflow_instance_id)
            
            if not subdivisions_data:
                logger.info(f"无subdivision数据: {workflow_instance_id}")
                return []
            
            tree = SubdivisionTree().build_from_subdivisions(subdivisions_data)
            candidates = []
            
            # 收集所有节点并按深度排序
            all_nodes = tree.get_all_nodes()
            # 从最深层开始（叶子节点优先合并）
            sorted_nodes = sorted(all_nodes, key=lambda n: n.depth, reverse=True)
            
            for node in sorted_nodes:
                # 检查是否可以合并
                can_merge, reason = await self._check_merge_feasibility(node)
                
                candidate = MergeCandidate(
                    subdivision_id=node.subdivision_id,
                    parent_subdivision_id=node.parent_id,
                    workflow_instance_id=node.workflow_instance_id or "",
                    workflow_base_id=node.workflow_base_id,
                    node_name=node.node_name,
                    depth=node.depth,
                    can_merge=can_merge,
                    merge_reason=reason
                )
                candidates.append(candidate)
            
            logger.info(f"✅ 找到 {len(candidates)} 个合并候选")
            return candidates
            
        except Exception as e:
            logger.error(f"❌ 获取合并候选失败: {e}")
            raise
    
    async def execute_merge(self, workflow_instance_id: uuid.UUID, 
                          selected_merges: List[str], 
                          creator_id: uuid.UUID) -> Dict[str, Any]:
        """
        执行工作流合并
        
        Args:
            workflow_instance_id: 主工作流实例ID
            selected_merges: 选中的subdivision ID列表
            creator_id: 合并操作执行者ID
            
        Returns:
            合并结果信息
        """
        try:
            logger.info(f"🚀 开始工作流合并: {workflow_instance_id}")
            logger.info(f"选中的subdivisions: {selected_merges}")
            logger.info(f"合并执行者: {creator_id}")
            
            # 1. 获取合并候选项并筛选
            candidates = await self.get_merge_candidates(workflow_instance_id)
            
            # 支持通过subdivision_id或workflow_instance_id匹配
            selected_candidates = []
            for c in candidates:
                # 可以通过subdivision_id或对应的workflow_instance_id选择
                if c.subdivision_id in selected_merges or c.workflow_instance_id in selected_merges:
                    selected_candidates.append(c)
            
            logger.info(f"📋 候选匹配结果: {len(selected_candidates)}/{len(candidates)} 个候选被选中")
            
            if not selected_candidates:
                return {"success": False, "message": "没有找到有效的合并候选"}
            
            # 2. 按深度排序（从最深层开始合并）
            selected_candidates.sort(key=lambda c: c.depth, reverse=True)
            
            # 3. 创建新的工作流模板
            new_workflow_base_id = uuid.uuid4()
            merge_operations = []
            
            # 4. 逐层执行合并，收集节点和连接数据
            all_merged_nodes = []
            all_merged_connections = []
            
            for candidate in selected_candidates:
                if not candidate.can_merge:
                    logger.warning(f"⚠️ 跳过不可合并的节点: {candidate.subdivision_id} - {candidate.merge_reason}")
                    continue
                
                logger.info(f"🔄 合并层级 {candidate.depth}: {candidate.node_name}")
                
                # 执行单个合并操作
                merge_result = await self._execute_single_merge(candidate, new_workflow_base_id)
                
                if merge_result['success']:
                    merge_operations.append(merge_result['operation'])
                    all_merged_nodes.extend(merge_result['merged_nodes'])
                    all_merged_connections.extend(merge_result['merged_connections'])
                else:
                    logger.error(f"❌ 合并失败: {candidate.subdivision_id} - {merge_result['error']}")
            
            # 5. 生成最终的合并工作流
            if merge_operations:
                final_workflow = await self._finalize_merged_workflow(
                    workflow_instance_id, new_workflow_base_id, merge_operations, 
                    creator_id, all_merged_nodes, all_merged_connections
                )
                
                return {
                    "success": True,
                    "new_workflow_base_id": str(new_workflow_base_id),
                    "merged_count": len(merge_operations),
                    "merge_operations": [op.__dict__ for op in merge_operations],
                    "final_workflow": final_workflow
                }
            else:
                return {"success": False, "message": "没有成功执行任何合并操作"}
                
        except Exception as e:
            logger.error(f"❌ 工作流合并失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _check_merge_feasibility(self, node: SubdivisionNode) -> Tuple[bool, str]:
        """检查节点是否可以合并"""
        try:
            if not node.workflow_instance_id:
                return False, "缺少子工作流实例"
            
            # 检查子工作流状态
            workflow_status = await self.db.fetch_one("""
                SELECT status FROM workflow_instance WHERE workflow_instance_id = %s
            """, node.workflow_instance_id)
            
            if not workflow_status:
                return False, "子工作流实例不存在"
            
            if workflow_status['status'] not in ['completed', 'draft']:
                return False, f"子工作流状态不允许合并: {workflow_status['status']}"
            
            return True, "可以合并"
            
        except Exception as e:
            logger.error(f"检查合并可行性失败: {e}")
            return False, f"检查失败: {str(e)}"
    
    async def _execute_single_merge(self, candidate: MergeCandidate, 
                                  new_workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """执行单个subdivision的合并"""
        try:
            logger.info(f"🔧 执行单个合并: {candidate.node_name}")
            
            # 获取子工作流的所有节点
            sub_workflow_id = await self.db.fetch_one("""
                SELECT workflow_id FROM workflow 
                WHERE workflow_base_id = %s 
                AND is_current_version = TRUE
            """, candidate.workflow_base_id)
            
            if not sub_workflow_id:
                raise Exception(f"找不到子工作流: {candidate.workflow_base_id}")
            
            sub_workflow_id = sub_workflow_id['workflow_id']
            
            # 获取子工作流的节点（排除开始和结束节点）
            nodes_query = """
            SELECT node_id, node_base_id, name, type, task_description, 
                   position_x, position_y, version
            FROM node 
            WHERE workflow_id = %s 
            AND is_deleted = FALSE 
            AND type NOT IN ('start', 'end')
            ORDER BY name
            """
            
            sub_nodes = await self.db.fetch_all(nodes_query, sub_workflow_id)
            logger.info(f"📋 子工作流有 {len(sub_nodes)} 个可合并节点")
            
            # 获取子工作流的连接
            connections_query = """
            SELECT from_node_id, to_node_id, condition_config
            FROM node_connection 
            WHERE workflow_id = %s
            """
            
            sub_connections = await self.db.fetch_all(connections_query, sub_workflow_id)
            logger.info(f"🔗 子工作流有 {len(sub_connections)} 个连接")
            
            operation = MergeOperation(
                target_node_id=candidate.subdivision_id,
                sub_workflow_id=candidate.workflow_base_id,
                subdivision_id=candidate.subdivision_id,
                depth=candidate.depth
            )
            
            return {
                "success": True,
                "operation": operation,
                "merged_nodes": sub_nodes,
                "merged_connections": sub_connections
            }
            
        except Exception as e:
            logger.error(f"❌ 单个合并执行失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _finalize_merged_workflow(self, original_workflow_id: uuid.UUID, 
                                      new_workflow_base_id: uuid.UUID, 
                                      merge_operations: List[MergeOperation],
                                      creator_id: uuid.UUID,
                                      merged_nodes: List[Dict[str, Any]],
                                      merged_connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """完成合并后的工作流生成"""
        try:
            logger.info(f"🎯 完成合并工作流生成: {new_workflow_base_id}")
            
            # 获取父工作流名称
            parent_workflow = await self.db.fetch_one("""
                SELECT w.name, w.workflow_base_id 
                FROM workflow_instance wi
                JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id
                WHERE wi.workflow_instance_id = %s 
                AND w.is_current_version = TRUE
            """, original_workflow_id)
            
            parent_name = parent_workflow['name'] if parent_workflow else "Unknown_Workflow"
            
            # 生成合并序号
            existing_merges = await self.db.fetch_all("""
                SELECT name FROM workflow 
                WHERE name LIKE %s AND is_deleted = FALSE
                ORDER BY created_at
            """, f"{parent_name}_合并_%")
            
            merge_number = len(existing_merges) + 1
            
            new_workflow_id = uuid.uuid4()
            merged_name = f"{parent_name}_合并_{merge_number}"
            merged_description = f"合并了{len(merge_operations)}个subdivision的工作流，基于{parent_name}"
            
            await self.db.execute("""
                INSERT INTO workflow (
                    workflow_id, workflow_base_id, name, description, 
                    creator_id, is_current_version, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, new_workflow_id, new_workflow_base_id, merged_name, merged_description,
                 creator_id, True, now_utc())
            
            logger.info(f"✅ 创建合并工作流记录: {merged_name}")
            
            # 复制父工作流的基础结构（开始和结束节点）
            parent_workflow_id = await self.db.fetch_one("""
                SELECT w.workflow_id FROM workflow_instance wi
                JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id
                WHERE wi.workflow_instance_id = %s 
                AND w.is_current_version = TRUE
            """, original_workflow_id)
            
            if parent_workflow_id:
                parent_workflow_id = parent_workflow_id['workflow_id']
                
                # 复制父工作流的开始和结束节点
                parent_nodes = await self.db.fetch_all("""
                    SELECT node_id, node_base_id, name, type, task_description, 
                           position_x, position_y, version
                    FROM node 
                    WHERE workflow_id = %s AND is_deleted = FALSE
                    AND type IN ('start', 'end')
                """, parent_workflow_id)
                
                logger.info(f"📋 复制父工作流的 {len(parent_nodes)} 个基础节点")
                
                # 创建节点ID映射
                node_id_mapping = {}
                
                # 复制基础节点
                for node in parent_nodes:
                    new_node_id = uuid.uuid4()
                    new_node_base_id = uuid.uuid4()
                    node_id_mapping[node['node_id']] = new_node_id
                    
                    await self.db.execute("""
                        INSERT INTO node (
                            node_id, node_base_id, workflow_id, workflow_base_id,
                            name, type, task_description, position_x, position_y,
                            version, is_current_version, created_at, is_deleted
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, new_node_id, new_node_base_id, new_workflow_id, new_workflow_base_id,
                         node['name'], node['type'], node['task_description'], 
                         node['position_x'], node['position_y'], 1, True, now_utc(), False)
                
                # 复制合并的节点
                for node in merged_nodes:
                    new_node_id = uuid.uuid4()
                    new_node_base_id = uuid.uuid4()
                    node_id_mapping[node['node_id']] = new_node_id
                    
                    await self.db.execute("""
                        INSERT INTO node (
                            node_id, node_base_id, workflow_id, workflow_base_id,
                            name, type, task_description, position_x, position_y,
                            version, is_current_version, created_at, is_deleted
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, new_node_id, new_node_base_id, new_workflow_id, new_workflow_base_id,
                         node['name'], node['type'], node['task_description'], 
                         node['position_x'], node['position_y'], 1, True, now_utc(), False)
                
                logger.info(f"✅ 复制了 {len(merged_nodes)} 个合并节点")
                
                # 复制连接
                connections_copied = 0
                for connection in merged_connections:
                    if (connection['from_node_id'] in node_id_mapping and 
                        connection['to_node_id'] in node_id_mapping):
                        
                        await self.db.execute("""
                            INSERT INTO node_connection (
                                from_node_id, to_node_id, workflow_id,
                                condition_config, created_at
                            ) VALUES (%s, %s, %s, %s, %s)
                        """, node_id_mapping[connection['from_node_id']],
                             node_id_mapping[connection['to_node_id']],
                             new_workflow_id, connection.get('condition_config'),
                             now_utc())
                        connections_copied += 1
                
                logger.info(f"✅ 复制了 {connections_copied} 个连接")
                
                total_nodes = len(parent_nodes) + len(merged_nodes)
                
                return {
                    "workflow_id": str(new_workflow_id),
                    "workflow_base_id": str(new_workflow_base_id),
                    "name": merged_name,
                    "description": merged_description,
                    "nodes_count": total_nodes,
                    "connections_count": connections_copied,
                    "merge_operations_count": len(merge_operations)
                }
            else:
                raise Exception("无法找到父工作流信息")
            
        except Exception as e:
            logger.error(f"❌ 完成合并工作流生成失败: {e}")
            raise