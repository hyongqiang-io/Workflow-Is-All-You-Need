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
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

from ..repositories.base import BaseRepository
from ..utils.helpers import now_utc
from .workflow_template_tree import WorkflowTemplateTree, WorkflowTemplateNode


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
            logger.info(f"🔍 [合并候选] 获取合并候选: {workflow_instance_id}")
            
            # 使用subdivision tree builder获取树结构
            from .workflow_template_connection_service import WorkflowTemplateConnectionService
            connection_service = WorkflowTemplateConnectionService()
            
            subdivisions_data = await connection_service._get_all_subdivisions_simple(workflow_instance_id)
            
            logger.info(f"📋 [合并候选] 查询到subdivision数据: {len(subdivisions_data) if subdivisions_data else 0}条")
            
            if not subdivisions_data:
                logger.warning(f"❌ [合并候选失败] 无subdivision数据: {workflow_instance_id}")
                
                # 🔧 增强调试：检查是否真的没有subdivision数据
                debug_query = await self.db.fetch_all("""
                    SELECT ts.subdivision_id, ts.sub_workflow_instance_id, 
                           ti.workflow_instance_id, ti.task_title,
                           n.name as node_name
                    FROM task_subdivision ts
                    JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id  
                    JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
                    JOIN node n ON ni.node_id = n.node_id
                    WHERE ti.workflow_instance_id = %s
                    AND ts.is_deleted = FALSE
                    ORDER BY ts.subdivision_created_at DESC
                    LIMIT 10
                """, workflow_instance_id)
                
                logger.warning(f"   📊 [调试检查] 直接查询task_subdivision结果: {len(debug_query)}条")
                for i, row in enumerate(debug_query):
                    logger.warning(f"     {i+1}. subdivision_id: {row['subdivision_id']}")
                    logger.warning(f"        sub_workflow_instance_id: {row['sub_workflow_instance_id']}")
                    logger.warning(f"        node_name: {row['node_name']}")
                    logger.warning(f"        task_title: {row['task_title']}")
                
                if debug_query:
                    logger.error(f"🚨 [严重问题] subdivision数据存在但_get_all_subdivisions_simple未返回！")
                    logger.error(f"   这表明WorkflowTemplateConnectionService._get_all_subdivisions_simple存在bug")
                else:
                    logger.warning(f"   确认：该工作流确实没有subdivision数据")
                
                logger.warning(f"   可能原因:")
                logger.warning(f"   1. 工作流实例不存在")
                logger.warning(f"   2. 该工作流没有进行任何subdivision操作")
                logger.warning(f"   3. subdivision数据已被删除或标记为deleted")
                logger.warning(f"   建议:")
                logger.warning(f"   - 检查工作流实例是否存在于workflow_instance表")
                logger.warning(f"   - 检查task_subdivision表中是否有相关记录")
                return []
            
            # 调试：显示subdivision数据详情
            logger.info(f"📊 [合并候选] subdivision数据详情:")
            for i, sub in enumerate(subdivisions_data[:5]):  # 显示前5条
                logger.info(f"  subdivision {i+1}:")
                logger.info(f"    - subdivision_id: {sub.get('subdivision_id')}")
                logger.info(f"    - sub_workflow_instance_id: {sub.get('sub_workflow_instance_id')}")
                logger.info(f"    - sub_workflow_name: {sub.get('sub_workflow_name')}")
                logger.info(f"    - sub_workflow_status: {sub.get('sub_workflow_status')}")
                logger.info(f"    - original_node_name: {sub.get('original_node_name')}")
                logger.info(f"    - depth: {sub.get('depth')}")
            
            if len(subdivisions_data) > 5:
                logger.info(f"    ... 还有 {len(subdivisions_data) - 5} 条subdivision记录")
            
            tree = await WorkflowTemplateTree().build_from_subdivisions(subdivisions_data, workflow_instance_id)
            candidates = []
            
            # 收集所有节点并按深度排序
            all_nodes = tree.get_all_nodes()
            logger.info(f"📊 [合并候选] 树节点统计: {len(all_nodes)}个节点，{len(tree.roots)}个根节点")
            
            if len(all_nodes) == 0:
                logger.warning(f"❌ [合并候选失败] subdivision树构建失败，没有有效节点")
                logger.warning(f"   可能原因:")
                logger.warning(f"   1. subdivision数据格式不正确")
                logger.warning(f"   2. subdivision之间的关系存在问题")
                logger.warning(f"   3. SubdivisionTree构建算法存在bug")
                return []
            
            # 从最深层开始（叶子节点优先合并）
            sorted_nodes = sorted(all_nodes, key=lambda n: n.depth, reverse=True)
            
            logger.info(f"🔍 [合并候选] 开始逐一检查 {len(sorted_nodes)} 个节点的合并可行性...")
            
            total_candidates = 0
            mergeable_candidates = 0
            
            for node in sorted_nodes:
                total_candidates += 1
                
                logger.info(f"🔍 [节点检查 {total_candidates}] 检查节点: {node.workflow_name}")
                logger.info(f"   - workflow_base_id: {node.workflow_base_id}")
                logger.info(f"   - workflow_instance_id: {node.workflow_instance_id}")
                logger.info(f"   - workflow_name: {node.workflow_name}")
                logger.info(f"   - status: {node.status}")
                logger.info(f"   - depth: {node.depth}")
                logger.info(f"   - replacement_info: {node.replacement_info}")
                
                # 🔧 移除可行性检查，直接认为所有工作流模板都可以合并
                can_merge = True
                reason = "基于工作流模板树，直接允许合并"
                
                mergeable_candidates += 1
                logger.info(f"   - ✅ [可合并] 节点可以合并 (基于工作流模板树)")
                
                # 获取替换信息作为subdivision相关数据 - 使用新的source_subdivision
                source_subdivision = getattr(node, 'source_subdivision', {}) or {}
                
                candidate = MergeCandidate(
                    subdivision_id=source_subdivision.get('subdivision_id', f"template_{node.workflow_base_id}"),
                    parent_subdivision_id=node.parent_node.workflow_base_id if node.parent_node else None,
                    workflow_instance_id=node.workflow_instance_id or "",
                    workflow_base_id=node.workflow_base_id,
                    node_name=source_subdivision.get('original_node_name', node.workflow_name),
                    depth=node.depth,
                    can_merge=can_merge,
                    merge_reason=reason
                )
                candidates.append(candidate)
                
                logger.info(f"   - ✅ [候选项] 已添加到候选列表")
            
            logger.info(f"📊 [合并候选总结] 候选项统计:")
            logger.info(f"   - 总节点数: {total_candidates}")
            logger.info(f"   - 可合并节点: {mergeable_candidates}")
            logger.info(f"   - 不可合并节点: {total_candidates - mergeable_candidates}")
            
            if mergeable_candidates == 0:
                logger.warning(f"⚠️ [合并候选警告] 没有任何可合并的节点!")
                logger.warning(f"   常见原因:")
                logger.warning(f"   1. 所有子工作流状态为 'running' 或 'pending' (正在执行中)")
                logger.warning(f"   2. 子工作流实例不存在或已被删除")
                logger.warning(f"   3. subdivision数据不完整")
                logger.warning(f"   建议解决方案:")
                logger.warning(f"   1. 等待正在运行的工作流完成")
                logger.warning(f"   2. 检查workflow_instance表中的状态")
                logger.warning(f"   3. 验证subdivision数据的完整性")
            
            return candidates
            
        except Exception as e:
            logger.error(f"❌ [合并候选异常] 获取合并候选失败: {e}")
            logger.error(f"   异常详情: {type(e).__name__}: {str(e)}")
            logger.error(f"   可能影响:")
            logger.error(f"   1. subdivision查询失败")
            logger.error(f"   2. 树构建算法异常")
            logger.error(f"   3. 数据库连接问题")
            raise
    
    async def execute_merge(self, workflow_instance_id: uuid.UUID, 
                          selected_merges: List[str], 
                          creator_id: uuid.UUID) -> Dict[str, Any]:
        """
        执行分层渐进式工作流合并
        
        新的合并策略：
        1. 按深度层级分组候选项
        2. 从最深层开始，逐层向上合并
        3. 每层合并后生成新的工作流版本
        4. 下一层基于前一层的结果继续合并
        
        Args:
            workflow_instance_id: 主工作流实例ID
            selected_merges: 选中的subdivision ID列表
            creator_id: 合并操作执行者ID
            
        Returns:
            合并结果信息
        """
        try:
            logger.info(f"🚀 [分层合并] 开始工作流合并: {workflow_instance_id}")
            logger.info(f"选中的subdivisions: {selected_merges}")
            logger.info(f"合并执行者: {creator_id}")
            logger.info(f"📊 [调试] 工作流实例ID类型: {type(workflow_instance_id)}, 值: {workflow_instance_id}")
            
            # 🔧 增加调试：先检查工作流实例状态
            workflow_check = await self.db.fetch_one("""
                SELECT wi.workflow_instance_id, wi.status, wi.created_at, 
                       w.name as workflow_name, w.workflow_base_id
                FROM workflow_instance wi
                JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id AND w.is_current_version = TRUE
                WHERE wi.workflow_instance_id = %s
            """, workflow_instance_id)
            logger.info(f"📊 [合并调试] 目标工作流信息: {workflow_check}")
            
            if not workflow_check:
                logger.error(f"❌ [合并失败] 工作流实例不存在: {workflow_instance_id}")
                return {"success": False, "message": "目标工作流实例不存在"}
            
            # 1. 获取合并候选项并筛选
            logger.info(f"🔍 [合并步骤1] 获取合并候选项...")
            candidates = await self.get_merge_candidates(workflow_instance_id)
            logger.info(f"📋 获取到 {len(candidates)} 个候选项")
            
            # 详细显示每个候选项
            for i, candidate in enumerate(candidates):
                logger.info(f"  候选项 {i+1}:")
                logger.info(f"    - subdivision_id: {candidate.subdivision_id}")
                logger.info(f"    - workflow_instance_id: {candidate.workflow_instance_id}")
                logger.info(f"    - node_name: {candidate.node_name}")
                logger.info(f"    - can_merge: {candidate.can_merge}")
                logger.info(f"    - reason: {candidate.merge_reason}")
            
            # 支持通过subdivision_id或workflow_instance_id匹配
            selected_candidates = []
            logger.info(f"🔍 [合并步骤2] 匹配选中项: {selected_merges}")
            
            for c in candidates:
                subdivision_match = c.subdivision_id in selected_merges
                workflow_match = c.workflow_instance_id in selected_merges
                
                if subdivision_match or workflow_match:
                    selected_candidates.append(c)
                    match_type = "subdivision_id" if subdivision_match else "workflow_instance_id"
                    logger.info(f"  ✅ 匹配成功 ({match_type}): {c.node_name}")
                else:
                    logger.info(f"  ❌ 未匹配: {c.node_name} (subdivision: {c.subdivision_id}, workflow: {c.workflow_instance_id})")
            
            if not selected_candidates:
                logger.warning(f"⚠️ 没有找到匹配的候选项！")
                logger.warning(f"   选中项: {selected_merges}")
                logger.warning(f"   可用候选项:")
                for c in candidates:
                    logger.warning(f"     - subdivision_id: {c.subdivision_id}")
                    logger.warning(f"     - workflow_instance_id: {c.workflow_instance_id}")
                return {"success": False, "message": "没有找到有效的合并候选"}
            
            # 过滤出真正可合并的候选项
            mergeable_candidates = [c for c in selected_candidates if c.can_merge]
            logger.info(f"📊 [合并步骤3] 可合并候选项: {len(mergeable_candidates)} / {len(selected_candidates)}")
            
            if not mergeable_candidates:
                logger.warning(f"⚠️ 选中的候选项都不可合并！")
                for c in selected_candidates:
                    logger.warning(f"   - {c.node_name}: {c.merge_reason}")
                return {"success": False, "message": "选中的候选项都不可合并"}
            
            # 2. 按深度分组候选项
            candidates_by_depth = {}
            for candidate in mergeable_candidates:
                depth = candidate.depth
                if depth not in candidates_by_depth:
                    candidates_by_depth[depth] = []
                candidates_by_depth[depth].append(candidate)
            
            logger.info(f"📊 [分层合并] 候选项分组:")
            for depth, cands in candidates_by_depth.items():
                names = [c.node_name for c in cands]
                logger.info(f"   深度 {depth}: {len(cands)} 个候选项 - {names}")
            
            # 3. 获取初始工作流信息
            initial_workflow_base_id = await self._get_initial_workflow_base_id(workflow_instance_id)
            if not initial_workflow_base_id:
                return {"success": False, "message": "无法获取初始工作流基础ID"}
            
            # 4. 分层渐进式合并
            current_workflow_base_id = initial_workflow_base_id
            layer_results = []
            total_merged = 0
            
            # 从最深层开始向上逐层合并
            for depth in sorted(candidates_by_depth.keys(), reverse=True):
                depth_candidates = candidates_by_depth[depth]
                
                logger.info(f"🔄 [第{len(layer_results)+1}层] 合并深度 {depth}: {len(depth_candidates)} 个候选项")
                
                # 执行单层合并
                layer_result = await self._merge_single_depth_layer(
                    current_workflow_base_id, depth_candidates, creator_id, depth
                )
                
                if layer_result['success']:
                    layer_results.append(layer_result)
                    current_workflow_base_id = layer_result['new_workflow_base_id']
                    total_merged += layer_result['merged_count']
                    
                    logger.info(f"   ✅ [第{len(layer_results)}层] 合并成功: 合并了 {layer_result['merged_count']} 个subdivision")
                    logger.info(f"   📋 新工作流基础ID: {current_workflow_base_id}")
                else:
                    logger.error(f"   ❌ [第{len(layer_results)+1}层] 合并失败: {layer_result['error']}")
                    return {
                        "success": False,
                        "message": f"第{len(layer_results)+1}层合并失败",
                        "error": layer_result['error'],
                        "completed_layers": len(layer_results)
                    }
            
            # 5. 返回分层合并结果
            logger.info(f"✅ [分层合并] 全部完成: 共 {len(layer_results)} 层，合并了 {total_merged} 个subdivision")
            
            return {
                "success": True,
                "merge_type": "progressive_layered",
                "final_workflow_base_id": current_workflow_base_id,
                "initial_workflow_base_id": initial_workflow_base_id,
                "total_layers": len(layer_results),
                "total_merged": total_merged,
                "layer_results": layer_results,
                "summary": {
                    "completed_layers": len(layer_results),
                    "total_candidates": len(mergeable_candidates),
                    "successfully_merged": total_merged
                }
            }
                
        except Exception as e:
            logger.error(f"❌ [分层合并] 工作流合并失败: {e}")
            return {"success": False, "error": str(e)}

    
    async def _check_merge_feasibility(self, node: WorkflowTemplateNode) -> Tuple[bool, str]:
        """检查工作流模板节点是否可以合并 - 基于工作流模板树"""
        try:
            logger.info(f"🔍 [工作流模板可行性检查] 检查合并可行性: {node.workflow_name}")
            logger.info(f"   - workflow_base_id: {node.workflow_base_id}")
            logger.info(f"   - workflow_instance_id: {node.workflow_instance_id}")
            logger.info(f"   - status: {node.status}")
            
            # 基本检查：必须有子工作流实例ID
            if not node.workflow_instance_id:
                logger.warning(f"   ❌ [工作流模板检查] 缺少子工作流实例ID")
                return False, "缺少子工作流实例ID"
            
            # 基本检查：必须有workflow_base_id
            if not node.workflow_base_id:
                logger.warning(f"   ❌ [工作流模板检查] 缺少workflow_base_id")
                return False, "缺少workflow_base_id"
            
            # 🔧 简化逻辑：直接基于工作流模板树数据进行合并，不检查具体状态
            # 只要工作流模板数据完整，就认为可以合并
            logger.info(f"   ✅ [工作流模板检查] 可以合并 - 基于工作流模板树数据")
            return True, "基于工作流模板树数据，可以合并"
            
        except Exception as e:
            logger.error(f"❌ [简化可行性检查] 检查失败: {e}")
            return False, f"检查失败: {str(e)}"
    
    async def _get_initial_workflow_base_id(self, workflow_instance_id: uuid.UUID) -> Optional[str]:
        """获取初始工作流基础ID"""
        try:
            result = await self.db.fetch_one("""
                SELECT workflow_base_id FROM workflow_instance 
                WHERE workflow_instance_id = %s
            """, workflow_instance_id)
            
            if result:
                return str(result['workflow_base_id'])
            return None
            
        except Exception as e:
            logger.error(f"获取初始工作流基础ID失败: {e}")
            return None
    
    async def _merge_single_depth_layer(self, current_workflow_base_id: str, 
                                       depth_candidates: List[MergeCandidate], 
                                       creator_id: uuid.UUID, depth: int) -> Dict[str, Any]:
        """
        执行单层深度的合并
        
        Args:
            current_workflow_base_id: 当前工作流基础ID
            depth_candidates: 当前深度的候选项列表
            creator_id: 创建者ID
            depth: 当前深度
            
        Returns:
            单层合并结果
        """
        try:
            logger.info(f"🔧 [单层合并] 开始合并深度 {depth}: {len(depth_candidates)} 个候选项")
            
            # 1. 生成新的工作流版本
            new_workflow_base_id = uuid.uuid4()
            
            # 2. 获取当前工作流的workflow_id
            current_workflow_id = await self._get_current_workflow_id_by_base(current_workflow_base_id)
            if not current_workflow_id:
                return {"success": False, "error": f"无法找到当前工作流: {current_workflow_base_id}"}
            
            # 3. 创建新的工作流记录
            new_workflow_info = await self._create_layered_workflow_record(
                current_workflow_base_id, new_workflow_base_id, depth, len(depth_candidates), creator_id
            )
            new_workflow_id = new_workflow_info['workflow_id']
            
            # 4. 执行节点替换合并
            merge_stats = await self._execute_layer_node_replacement(
                current_workflow_id, new_workflow_id, new_workflow_base_id, depth_candidates
            )
            
            logger.info(f"✅ [单层合并] 深度 {depth} 合并完成:")
            logger.info(f"   - 新工作流: {new_workflow_info['name']}")
            logger.info(f"   - 合并节点: {merge_stats.get('nodes_replaced', 0)}")
            logger.info(f"   - 重建连接: {merge_stats.get('connections_count', 0)}")
            
            return {
                "success": True,
                "depth": depth,
                "new_workflow_base_id": str(new_workflow_base_id),
                "new_workflow_id": str(new_workflow_id),
                "merged_count": len(depth_candidates),
                "workflow_info": new_workflow_info,
                "merge_stats": merge_stats
            }
            
        except Exception as e:
            logger.error(f"❌ [单层合并] 深度 {depth} 合并失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_current_workflow_id_by_base(self, workflow_base_id: str) -> Optional[str]:
        """根据workflow_base_id获取当前版本的workflow_id"""
        try:
            result = await self.db.fetch_one("""
                SELECT workflow_id FROM workflow 
                WHERE workflow_base_id = %s AND is_current_version = TRUE
            """, workflow_base_id)
            
            return result['workflow_id'] if result else None
            
        except Exception as e:
            logger.error(f"获取当前工作流ID失败: {e}")
            return None
    
    async def _create_layered_workflow_record(self, parent_workflow_base_id: str,
                                            new_workflow_base_id: uuid.UUID,
                                            depth: int, merge_count: int,
                                            creator_id: uuid.UUID) -> Dict[str, Any]:
        """创建分层合并的工作流记录"""
        try:
            # 获取父工作流名称
            parent_workflow = await self.db.fetch_one("""
                SELECT name FROM workflow 
                WHERE workflow_base_id = %s AND is_current_version = TRUE
            """, parent_workflow_base_id)
            
            parent_name = parent_workflow['name'] if parent_workflow else "Unknown_Workflow"
            
            # 生成分层合并的工作流名称
            new_workflow_id = uuid.uuid4()
            merged_name = f"{parent_name}_合并_深度{depth}_{merge_count}项"
            merged_description = f"分层合并深度{depth}的{merge_count}个subdivision，基于{parent_name}"
            
            await self.db.execute("""
                INSERT INTO workflow (
                    workflow_id, workflow_base_id, name, description, 
                    creator_id, is_current_version, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, new_workflow_id, new_workflow_base_id, merged_name, merged_description,
                 creator_id, True, now_utc())
            
            logger.info(f"✅ [工作流记录] 创建分层合并工作流: {merged_name}")
            
            return {
                "workflow_id": str(new_workflow_id),
                "workflow_base_id": str(new_workflow_base_id),
                "name": merged_name,
                "description": merged_description
            }
            
        except Exception as e:
            logger.error(f"❌ [工作流记录] 创建分层合并工作流失败: {e}")
            raise
    
    async def _execute_layer_node_replacement(self, parent_workflow_id: str,
                                            new_workflow_id: uuid.UUID, new_workflow_base_id: uuid.UUID,
                                            depth_candidates: List[MergeCandidate]) -> Dict[str, Any]:
        """执行单层的节点替换合并"""
        try:
            # 1. 收集当前层需要替换的subdivision节点ID
            subdivision_node_ids = set()
            subdivision_mapping = {}  # node_id -> candidate
            
            for candidate in depth_candidates:
                # 获取subdivision对应的原始节点信息
                original_node_info = await self._get_original_node_info(candidate.subdivision_id)
                if original_node_info:
                    # 🔧 修复：使用node_id而不是task_instance_id来排除节点
                    node_id = original_node_info['node_id']
                    subdivision_node_ids.add(node_id)
                    subdivision_mapping[node_id] = {
                        'candidate': candidate,
                        'original_node': original_node_info
                    }
                    logger.info(f"   🔧 将排除节点: {original_node_info['name']} (node_id: {node_id})")
            
            logger.info(f"🔄 [节点替换] 将替换 {len(subdivision_node_ids)} 个subdivision节点")
            logger.info(f"   📋 排除的node_id列表: {list(subdivision_node_ids)}")
            
            # 2. 复制父工作流的保留节点（排除被subdivision的节点）
            node_id_mapping = await self._copy_preserved_nodes(
                parent_workflow_id, new_workflow_id, new_workflow_base_id, subdivision_node_ids
            )
            
            # 3. 为每个subdivision执行节点替换
            replacement_stats = await self._replace_subdivision_nodes_layered(
                new_workflow_id, new_workflow_base_id, subdivision_mapping, node_id_mapping
            )
            
            # 4. 重建所有连接
            connection_stats = await self._rebuild_layer_connections(
                parent_workflow_id, new_workflow_id, subdivision_mapping, node_id_mapping
            )
            
            logger.info(f"✅ [节点替换] 完成: 替换{replacement_stats['nodes_replaced']}节点, 重建{connection_stats['connections_count']}连接")
            
            return {
                **replacement_stats,
                **connection_stats
            }
            
        except Exception as e:
            logger.error(f"❌ [节点替换] 执行失败: {e}")
            raise
    
    async def _replace_subdivision_nodes_layered(self, new_workflow_id: uuid.UUID, new_workflow_base_id: uuid.UUID,
                                               subdivision_mapping: Dict[str, Dict], 
                                               node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """分层合并：用子工作流节点替换subdivision节点"""
        replaced_nodes = 0
        
        # 遍历每个subdivision，复制其子工作流的业务节点
        for original_node_id, mapping_info in subdivision_mapping.items():
            candidate = mapping_info['candidate']
            logger.info(f"🔄 [节点替换] 处理subdivision: {candidate.node_name}")
            
            # 获取子工作流结构（重新分析以确保数据完整）
            original_node_info = mapping_info['original_node']
            workflow_structure = await self._analyze_subworkflow_structure(
                candidate.workflow_instance_id,
                original_node_info['position_x'],
                original_node_info['position_y']
            )
            
            # 复制子工作流的业务节点
            for node in workflow_structure['business_nodes']:
                new_node_id = uuid.uuid4()
                new_node_base_id = uuid.uuid4()
                
                # 🔧 修复：将新节点加入映射，供连接重建使用
                node_id_mapping[node['node_id']] = new_node_id
                
                logger.info(f"   📄 复制业务节点: {node['name']} -> 新ID: {new_node_id}")
                
                await self.db.execute("""
                    INSERT INTO node (
                        node_id, node_base_id, workflow_id, workflow_base_id,
                        name, type, task_description, position_x, position_y,
                        version, is_current_version, created_at, is_deleted
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, new_node_id, new_node_base_id, new_workflow_id, new_workflow_base_id,
                     node['name'], node['type'], node['task_description'], 
                     node['position_x'], node['position_y'], 1, True, now_utc(), False)
                
                replaced_nodes += 1
        
        logger.info(f"✅ [分层合并] 替换了 {replaced_nodes} 个节点")
        return {"nodes_replaced": replaced_nodes}
    
    async def _rebuild_layer_connections(self, parent_workflow_id: str, new_workflow_id: uuid.UUID,
                                       subdivision_mapping: Dict[str, Dict],
                                       node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """重建分层合并的连接"""
        # 获取父工作流的所有连接
        parent_connections = await self.db.fetch_all("""
            SELECT from_node_id, to_node_id, connection_type, condition_config
            FROM node_connection 
            WHERE workflow_id = %s
        """, parent_workflow_id)
        
        parent_connections_copied = 0
        subworkflow_connections_copied = 0
        cross_boundary_connections_created = 0
        
        subdivision_node_ids = set(subdivision_mapping.keys())
        
        # 1. 复制父工作流的保留连接（不涉及subdivision节点）
        for conn in parent_connections:
            from_id, to_id = conn['from_node_id'], conn['to_node_id']
            
            if from_id in subdivision_node_ids or to_id in subdivision_node_ids:
                continue
            
            if from_id in node_id_mapping and to_id in node_id_mapping:
                await self.db.execute("""
                    INSERT INTO node_connection (
                        from_node_id, to_node_id, workflow_id,
                        connection_type, condition_config, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, node_id_mapping[from_id], node_id_mapping[to_id],
                     new_workflow_id, conn.get('connection_type', 'normal'),
                     conn.get('condition_config'), now_utc())
                parent_connections_copied += 1
        
        # 2. 复制每个子工作流的内部连接并重建跨边界连接
        for original_node_id, mapping_info in subdivision_mapping.items():
            candidate = mapping_info['candidate']
            
            sub_workflow_data = await self._get_subworkflow_data(candidate.workflow_base_id)
            if not sub_workflow_data:
                continue
                
            original_node_info = mapping_info['original_node']
            workflow_structure = await self._analyze_subworkflow_structure(
                candidate.workflow_instance_id,  # 🔧 修复：使用候选项的workflow_instance_id
                original_node_info['position_x'],
                original_node_info['position_y']
            )
            
            # 复制子工作流内部连接
            logger.info(f"   🔄 开始复制子工作流内部连接: {len(workflow_structure['business_connections'])}个")
            for conn in workflow_structure['business_connections']:
                from_id, to_id = conn['from_node_id'], conn['to_node_id']
                logger.info(f"      检查连接: {from_id} -> {to_id}")
                logger.info(f"      from_id在映射中: {from_id in node_id_mapping}")
                logger.info(f"      to_id在映射中: {to_id in node_id_mapping}")
                
                if from_id in node_id_mapping and to_id in node_id_mapping:
                    await self.db.execute("""
                        INSERT INTO node_connection (
                            from_node_id, to_node_id, workflow_id,
                            connection_type, condition_config, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, node_id_mapping[from_id], node_id_mapping[to_id],
                         new_workflow_id, conn.get('connection_type', 'normal'),
                         conn.get('condition_config'), now_utc())
                    subworkflow_connections_copied += 1
                    logger.info(f"      ✅ 成功复制连接: {node_id_mapping[from_id]} -> {node_id_mapping[to_id]}")
                else:
                    logger.warning(f"      ❌ 跳过连接（节点未在映射中）: {from_id} -> {to_id}")
            
            # 重建跨边界连接
            entry_points = workflow_structure['entry_points']
            exit_points = workflow_structure['exit_points']
            
            # 🔧 修复：使用正确的node_id进行连接重建
            subdivision_node_id = original_node_info['node_id']  # 使用node_id而不是task_instance_id
            
            # 重建上游连接
            for conn in parent_connections:
                if conn['to_node_id'] == subdivision_node_id:
                    from_id = conn['from_node_id']
                    if from_id in node_id_mapping:
                        for entry_point in entry_points:
                            if entry_point['node_id'] in node_id_mapping:
                                await self.db.execute("""
                                    INSERT INTO node_connection (
                                        from_node_id, to_node_id, workflow_id,
                                        connection_type, condition_config, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                """, node_id_mapping[from_id],
                                     node_id_mapping[entry_point['node_id']],
                                     new_workflow_id, conn.get('connection_type', 'normal'),
                                     conn.get('condition_config'), now_utc())
                                cross_boundary_connections_created += 1
                                logger.info(f"   🔗 上游连接: {from_id} -> {entry_point['name']}")
            
            # 重建下游连接
            for conn in parent_connections:
                if conn['from_node_id'] == subdivision_node_id:
                    to_id = conn['to_node_id']
                    if to_id in node_id_mapping:
                        for exit_point in exit_points:
                            if exit_point['node_id'] in node_id_mapping:
                                await self.db.execute("""
                                    INSERT INTO node_connection (
                                        from_node_id, to_node_id, workflow_id,
                                        connection_type, condition_config, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                """, node_id_mapping[exit_point['node_id']],
                                     node_id_mapping[to_id],
                                     new_workflow_id, conn.get('connection_type', 'normal'),
                                     conn.get('condition_config'), now_utc())
                                cross_boundary_connections_created += 1
                                logger.info(f"   🔗 下游连接: {exit_point['name']} -> {to_id}")
        
        logger.info(f"✅ [分层合并] 连接重建完成: 父连接{parent_connections_copied}, 子连接{subworkflow_connections_copied}, 跨边界{cross_boundary_connections_created}")
        
        return {
            "parent_connections_copied": parent_connections_copied,
            "subworkflow_connections_copied": subworkflow_connections_copied,
            "cross_boundary_connections_created": cross_boundary_connections_created,
            "connections_count": parent_connections_copied + subworkflow_connections_copied + cross_boundary_connections_created
        }
    
    async def _execute_single_merge(self, candidate: MergeCandidate, 
                                  new_workflow_base_id: uuid.UUID) -> Dict[str, Any]:
        """执行单个subdivision的合并 - 重构版本"""
        try:
            logger.info(f"🔧 执行单个合并: {candidate.node_name}")
            
            # 1. 获取子工作流信息
            sub_workflow_data = await self._get_subworkflow_data(candidate.workflow_base_id)
            if not sub_workflow_data:
                raise Exception(f"找不到子工作流: {candidate.workflow_base_id}")
            
            # 2. 获取被替换的subdivision节点信息
            original_node_info = await self._get_original_node_info(candidate.subdivision_id)
            if not original_node_info:
                raise Exception(f"找不到原始subdivision节点信息: {candidate.subdivision_id}")
            
            # 3. 分析子工作流结构
            workflow_structure = await self._analyze_subworkflow_structure(
                candidate.workflow_instance_id,  # 🔧 修复：使用候选项的workflow_instance_id
                original_node_info['position_x'],
                original_node_info['position_y']
            )
            
            # 4. 创建合并操作记录
            operation = MergeOperation(
                target_node_id=candidate.subdivision_id,
                sub_workflow_id=candidate.workflow_base_id,
                subdivision_id=candidate.subdivision_id,
                depth=candidate.depth
            )
            
            logger.info(f"✅ 合并准备完成: {len(workflow_structure['business_nodes'])}个业务节点, "
                       f"{len(workflow_structure['entry_points'])}个入口, "
                       f"{len(workflow_structure['exit_points'])}个出口")
            
            return {
                "success": True,
                "operation": operation,
                "original_node": original_node_info,
                "workflow_structure": workflow_structure,
                "candidate": candidate
            }
            
        except Exception as e:
            logger.error(f"❌ 单个合并执行失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_subworkflow_data(self, workflow_base_id: str) -> Optional[Dict[str, Any]]:
        """获取子工作流基本信息"""
        return await self.db.fetch_one("""
            SELECT workflow_id, name, description 
            FROM workflow 
            WHERE workflow_base_id = %s 
            AND is_current_version = TRUE
        """, workflow_base_id)
    
    async def _get_original_node_info(self, subdivision_id: str) -> Optional[Dict[str, Any]]:
        """获取被subdivision的原始节点信息"""
        logger.info(f"🔍 查找subdivision原始节点信息: {subdivision_id}")
        
        # 首先尝试通过不同的查询方式找到subdivision记录
        subdivision_record = None
        
        # 方法1: 直接匹配UUID字符串
        subdivision_record = await self.db.fetch_one("""
            SELECT subdivision_id, original_task_id, created_at 
            FROM task_subdivision 
            WHERE CAST(subdivision_id AS CHAR) = %s
        """, subdivision_id)
        
        if not subdivision_record:
            # 方法2: 尝试UUID转换
            try:
                import uuid as uuid_lib
                subdivision_uuid = uuid_lib.UUID(subdivision_id)
                subdivision_record = await self.db.fetch_one("""
                    SELECT subdivision_id, original_task_id, created_at 
                    FROM task_subdivision 
                    WHERE subdivision_id = %s
                """, subdivision_uuid)
            except ValueError:
                logger.info(f"   subdivision_id不是有效的UUID格式: {subdivision_id}")
        
        if not subdivision_record:
            # 方法3: 模糊匹配（用于调试）
            subdivision_record = await self.db.fetch_one("""
                SELECT subdivision_id, original_task_id, created_at 
                FROM task_subdivision 
                WHERE CAST(subdivision_id AS CHAR) LIKE %s
            """, f"%{subdivision_id}%")
        
        logger.info(f"   subdivision记录: {subdivision_record}")
        
        if not subdivision_record:
            logger.warning(f"   ❌ 在task_subdivision表中找不到subdivision: {subdivision_id}")
            
            # 调试：显示task_subdivision表中的所有记录
            all_subdivisions = await self.db.fetch_all("""
                SELECT CAST(subdivision_id AS CHAR) as subdivision_id_str, 
                       CAST(original_task_id AS CHAR) as original_task_id_str,
                       created_at 
                FROM task_subdivision 
                WHERE is_deleted = FALSE
                ORDER BY created_at DESC
                LIMIT 10
            """)
            logger.info(f"   调试：最近的10个subdivision记录:")
            for sub in all_subdivisions:
                logger.info(f"     - {sub['subdivision_id_str']} -> {sub['original_task_id_str']}")
            
            return None
            
        # 获取original_task_id
        original_task_id = subdivision_record['original_task_id']
        logger.info(f"   原始任务ID: {original_task_id}")
        
        # 查找对应的节点信息，通过task_instance -> node_instance -> node路径
        node_info = await self.db.fetch_one("""
            SELECT 
                ti.task_instance_id,
                ni.node_instance_id,
                n.node_id, n.position_x, n.position_y, n.name, n.type, n.task_description,
                n.workflow_id, w.name as workflow_name
            FROM task_instance ti
            JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id  
            JOIN node n ON ni.node_id = n.node_id
            JOIN workflow w ON n.workflow_id = w.workflow_id
            WHERE ti.task_instance_id = %s
        """, original_task_id)
        
        logger.info(f"   节点信息: {node_info}")
        
        if node_info:
            # 合并信息
            result = {
                'original_task_id': original_task_id,
                'node_id': node_info['node_id'],  # 🔧 添加node_id用于连接重建
                'position_x': node_info['position_x'],
                'position_y': node_info['position_y'],
                'name': node_info['name'],
                'type': node_info['type'],
                'task_description': node_info['task_description'],
                'workflow_id': node_info['workflow_id'],
                'workflow_name': node_info['workflow_name']
            }
            logger.info(f"   ✅ 成功找到原始节点信息")
            return result
        else:
            logger.warning(f"   ❌ 找不到节点信息: {original_task_id}")
            return None
    
    async def _analyze_subworkflow_structure(self, candidate_workflow_instance_id: str, 
                                           center_x: int, center_y: int) -> Dict[str, Any]:
        """
        分析子工作流结构，识别入口、出口和业务节点
        
        修复：从工作流实例中获取实际执行的节点数据，而不是从模板中获取
        """
        try:
            logger.info(f"🔍 开始分析子工作流结构: {candidate_workflow_instance_id}")
            
            # 🔧 修复：从工作流实例中获取实际节点（node_instance），而不是模板节点
            all_nodes = await self.db.fetch_all("""
                SELECT ni.node_instance_id, ni.node_id, n.node_base_id, n.name, n.type, 
                       n.position_x, n.position_y, n.task_description, n.version,
                       ti.status as task_status
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                LEFT JOIN task_instance ti ON ni.node_instance_id = ti.node_instance_id
                WHERE ni.workflow_instance_id = %s AND ni.is_deleted = FALSE 
                ORDER BY n.position_x, n.position_y
            """, candidate_workflow_instance_id)
            
            logger.info(f"   📋 子工作流实例总节点数: {len(all_nodes)}")
            
            # 🔧 修复：处理空版本问题，当前版本为空时回退到有数据的版本
            actual_workflow_info = await self.db.fetch_one("""
                SELECT DISTINCT n.workflow_id 
                FROM node_instance ni
                JOIN node n ON ni.node_id = n.node_id
                WHERE ni.workflow_instance_id = %s 
                LIMIT 1
            """, candidate_workflow_instance_id)
            
            if actual_workflow_info:
                sub_workflow_id = actual_workflow_info['workflow_id']
                logger.info(f"   🔍 实际子工作流模板ID: {sub_workflow_id}")
            else:
                # 如果通过节点实例找不到，尝试通过工作流基础ID找到有数据的版本
                logger.warning(f"   ⚠️ 无法通过节点实例找到工作流模板，尝试查找有数据的版本")
                
                workflow_instance_info = await self.db.fetch_one("""
                    SELECT workflow_base_id FROM workflow_instance 
                    WHERE workflow_instance_id = %s
                """, candidate_workflow_instance_id)
                
                if workflow_instance_info:
                    base_id = workflow_instance_info['workflow_base_id']
                    # 查找该基础ID下有节点数据的版本
                    workflow_with_data = await self.db.fetch_one("""
                        SELECT DISTINCT w.workflow_id, w.version, COUNT(n.node_id) as node_count
                        FROM workflow w
                        JOIN node n ON w.workflow_id = n.workflow_id
                        WHERE w.workflow_base_id = %s AND w.is_deleted = FALSE
                        GROUP BY w.workflow_id, w.version
                        HAVING node_count > 0
                        ORDER BY w.version DESC
                        LIMIT 1
                    """, base_id)
                    
                    if workflow_with_data:
                        sub_workflow_id = workflow_with_data['workflow_id']
                        logger.info(f"   🔧 找到有数据的版本 {workflow_with_data['version']}: {sub_workflow_id}")
                    else:
                        logger.error(f"   ❌ 找不到任何有数据的工作流版本: {base_id}")
                        sub_workflow_id = None
                else:
                    logger.error(f"   ❌ 找不到工作流实例信息: {candidate_workflow_instance_id}")
                    sub_workflow_id = None
            
            if sub_workflow_id:
                # 直接从实际模板连接表获取连接信息
                all_connections = await self.db.fetch_all("""
                    SELECT 
                        nc.from_node_id,
                        nc.to_node_id,
                        from_n.name as from_node_name,
                        to_n.name as to_node_name,
                        from_n.type as from_node_type,
                        to_n.type as to_node_type,
                        nc.connection_type,
                        nc.condition_config
                    FROM node_connection nc
                    JOIN node from_n ON nc.from_node_id = from_n.node_id
                    JOIN node to_n ON nc.to_node_id = to_n.node_id
                    WHERE nc.workflow_id = %s
                """, sub_workflow_id)
            else:
                all_connections = []
            
            logger.info(f"   🔗 子工作流实例总连接数: {len(all_connections)}")
            
            # 按类型分类节点
            start_nodes = [n for n in all_nodes if n['type'] == 'start']
            end_nodes = [n for n in all_nodes if n['type'] == 'end']
            business_nodes = [n for n in all_nodes if n['type'] not in ('start', 'end')]
            
            logger.info(f"   📊 节点分类: {len(start_nodes)}个开始, {len(business_nodes)}个业务, {len(end_nodes)}个结束")
            
            if not business_nodes:
                logger.warning(f"   ⚠️ 子工作流实例没有业务节点")
                return {
                    "business_nodes": [],
                    "entry_points": [],
                    "exit_points": [],
                    "business_connections": [],
                    "start_to_entry_connections": [],
                    "exit_to_end_connections": [],
                    "analysis_stats": {
                        "total_nodes": len(all_nodes),
                        "business_nodes": 0,
                        "start_nodes": len(start_nodes),
                        "end_nodes": len(end_nodes),
                        "total_connections": len(all_connections)
                    }
                }
            
            # 构建连接图 - 基于节点模板ID
            outgoing = {}  # from_node_id -> [connection_info, ...]
            incoming = {}  # to_node_id -> [connection_info, ...]
            
            for conn in all_connections:
                from_id, to_id = conn['from_node_id'], conn['to_node_id']
                outgoing.setdefault(from_id, []).append(conn)
                incoming.setdefault(to_id, []).append(conn)
            
            # 识别入口节点：从start节点直接或间接可达的业务节点
            entry_points = self._find_entry_points_enhanced(start_nodes, business_nodes, outgoing, incoming)
            logger.info(f"   📥 识别出 {len(entry_points)} 个入口节点: {[n['name'] for n in entry_points]}")
            
            # 识别出口节点：可以到达end节点的业务节点
            exit_points = self._find_exit_points_enhanced(end_nodes, business_nodes, incoming, outgoing)
            logger.info(f"   📤 识别出 {len(exit_points)} 个出口节点: {[n['name'] for n in exit_points]}")
            
            # 计算节点位置偏移（相对于原subdivision节点位置）
            positioned_nodes = self._calculate_node_positions(
                business_nodes, center_x, center_y
            )
            
            # 分类连接
            business_connections = []
            start_to_entry_connections = []
            exit_to_end_connections = []
            
            business_node_ids = {n['node_id'] for n in business_nodes}
            start_node_ids = {n['node_id'] for n in start_nodes}
            end_node_ids = {n['node_id'] for n in end_nodes}
            entry_point_ids = {n['node_id'] for n in entry_points}
            exit_point_ids = {n['node_id'] for n in exit_points}
            
            # 🔧 修复：简化连接分类逻辑，直接使用模板连接数据
            for conn in all_connections:
                from_node_id = conn['from_node_id']
                to_node_id = conn['to_node_id']
                
                # 创建标准化的连接对象
                normalized_conn = {
                    'from_node_id': from_node_id,
                    'to_node_id': to_node_id,
                    'connection_type': conn.get('connection_type', 'normal'),
                    'condition_config': conn.get('condition_config')
                }
                
                # 业务节点之间的连接
                if from_node_id in business_node_ids and to_node_id in business_node_ids:
                    business_connections.append(normalized_conn)
                    logger.info(f"      📋 业务连接: {conn['from_node_name']} -> {conn['to_node_name']}")
                # start -> entry 的连接
                elif from_node_id in start_node_ids and to_node_id in entry_point_ids:
                    start_to_entry_connections.append(normalized_conn)
                    logger.info(f"      📋 启动连接: {conn['from_node_name']} -> {conn['to_node_name']}")
                # exit -> end 的连接
                elif from_node_id in exit_point_ids and to_node_id in end_node_ids:
                    exit_to_end_connections.append(normalized_conn)
                    logger.info(f"      📋 结束连接: {conn['from_node_name']} -> {conn['to_node_name']}")
            
            logger.info(f"   🔗 连接分类:")
            logger.info(f"      - 业务连接: {len(business_connections)}个")
            logger.info(f"      - start->entry连接: {len(start_to_entry_connections)}个")
            logger.info(f"      - exit->end连接: {len(exit_to_end_connections)}个")
            
            analysis_stats = {
                "total_nodes": len(all_nodes),
                "business_nodes": len(business_nodes),
                "start_nodes": len(start_nodes),
                "end_nodes": len(end_nodes),
                "entry_points": len(entry_points),
                "exit_points": len(exit_points),
                "total_connections": len(all_connections),
                "business_connections": len(business_connections),
                "boundary_connections": len(start_to_entry_connections) + len(exit_to_end_connections)
            }
            
            logger.info(f"✅ 子工作流结构分析完成: {analysis_stats}")
            
            return {
                "business_nodes": positioned_nodes,
                "entry_points": entry_points,
                "exit_points": exit_points,
                "business_connections": business_connections,
                "start_to_entry_connections": start_to_entry_connections,
                "exit_to_end_connections": exit_to_end_connections,
                "analysis_stats": analysis_stats
            }
            
        except Exception as e:
            logger.error(f"❌ 分析子工作流结构失败: {e}")
            raise
    
    def _find_entry_points_enhanced(self, start_nodes: List[Dict], business_nodes: List[Dict], 
                                   outgoing: Dict, incoming: Dict = None) -> List[Dict]:
        """增强版入口点查找 - 支持复杂的入口模式"""
        entry_points = []
        start_node_ids = {n['node_id'] for n in start_nodes}
        business_node_ids = {n['node_id'] for n in business_nodes}
        
        # 方法1: 直接从start节点连接的业务节点
        for start_id in start_node_ids:
            if start_id in outgoing:
                for conn in outgoing[start_id]:
                    to_id = conn['to_node_id']
                    if to_id in business_node_ids:
                        entry_node = next(n for n in business_nodes if n['node_id'] == to_id)
                        if entry_node not in entry_points:
                            entry_points.append(entry_node)
                            logger.info(f"      找到直接入口点: {entry_node['name']} (from start)")
        
        # 方法2: 如果没有直接连接，找没有业务前驱的业务节点
        if not entry_points and incoming:
            for node in business_nodes:
                node_id = node['node_id']
                has_business_predecessor = False
                
                # 检查是否有来自其他业务节点的连接
                if node_id in incoming:
                    for conn in incoming.get(node_id, []):
                        if conn['from_node_id'] in business_node_ids:
                            has_business_predecessor = True
                            break
                
                if not has_business_predecessor:
                    entry_points.append(node)
                    logger.info(f"      找到间接入口点: {node['name']} (no business predecessor)")
        
        # 方法3: 如果还是没有，选择位置最前的节点作为入口点
        if not entry_points and business_nodes:
            entry_points = [business_nodes[0]]
            logger.info(f"      使用默认入口点: {business_nodes[0]['name']} (first node)")
            
        return entry_points
    
    def _find_exit_points_enhanced(self, end_nodes: List[Dict], business_nodes: List[Dict],
                                 incoming: Dict, outgoing: Dict = None) -> List[Dict]:
        """增强版出口点查找 - 支持复杂的出口模式"""
        exit_points = []
        end_node_ids = {n['node_id'] for n in end_nodes}
        business_node_ids = {n['node_id'] for n in business_nodes}
        
        # 方法1: 直接连接到end节点的业务节点
        for end_id in end_node_ids:
            if end_id in incoming:
                for conn in incoming[end_id]:
                    from_id = conn['from_node_id']
                    if from_id in business_node_ids:
                        exit_node = next(n for n in business_nodes if n['node_id'] == from_id)
                        if exit_node not in exit_points:
                            exit_points.append(exit_node)
                            logger.info(f"      找到直接出口点: {exit_node['name']} (to end)")
        
        # 方法2: 如果没有直接连接，找没有业务后继的业务节点
        if not exit_points and outgoing:
            for node in business_nodes:
                node_id = node['node_id']
                has_business_successor = False
                
                # 检查是否有到其他业务节点的连接
                for conn in outgoing.get(node_id, []):
                    if conn['to_node_id'] in business_node_ids:
                        has_business_successor = True
                        break
                
                if not has_business_successor:
                    exit_points.append(node)
                    logger.info(f"      找到间接出口点: {node['name']} (no business successor)")
        
        # 方法3: 如果还是没有，选择位置最后的节点作为出口点
        if not exit_points and business_nodes:
            exit_points = [business_nodes[-1]]
            logger.info(f"      使用默认出口点: {business_nodes[-1]['name']} (last node)")
            
        return exit_points
    
    def _find_entry_points(self, start_nodes: List[Dict], business_nodes: List[Dict], 
                          outgoing: Dict) -> List[Dict]:
        """找到子工作流的入口节点"""
        entry_points = []
        start_node_ids = {n['node_id'] for n in start_nodes}
        business_node_ids = {n['node_id'] for n in business_nodes}
        
        for start_id in start_node_ids:
            if start_id in outgoing:
                for conn in outgoing[start_id]:
                    to_id = conn['to_node_id']
                    if to_id in business_node_ids:
                        # 找到对应的业务节点
                        entry_node = next(n for n in business_nodes if n['node_id'] == to_id)
                        if entry_node not in entry_points:
                            entry_points.append(entry_node)
        
        # 如果没有找到明确的入口点，选择第一个业务节点
        if not entry_points and business_nodes:
            entry_points = [business_nodes[0]]
            
        return entry_points
    
    def _find_exit_points(self, end_nodes: List[Dict], business_nodes: List[Dict],
                         incoming: Dict) -> List[Dict]:
        """找到子工作流的出口节点"""
        exit_points = []
        end_node_ids = {n['node_id'] for n in end_nodes}
        business_node_ids = {n['node_id'] for n in business_nodes}
        
        for end_id in end_node_ids:
            if end_id in incoming:
                for conn in incoming[end_id]:
                    from_id = conn['from_node_id']
                    if from_id in business_node_ids:
                        # 找到对应的业务节点
                        exit_node = next(n for n in business_nodes if n['node_id'] == from_id)
                        if exit_node not in exit_points:
                            exit_points.append(exit_node)
        
        # 如果没有找到明确的出口点，选择最后一个业务节点
        if not exit_points and business_nodes:
            exit_points = [business_nodes[-1]]
            
        return exit_points
    
    def _calculate_node_positions(self, nodes: List[Dict], center_x: int, center_y: int) -> List[Dict]:
        """计算节点在合并后工作流中的位置"""
        if not nodes:
            return []
        
        # 计算原始节点的边界框
        min_x = min(n['position_x'] for n in nodes)
        max_x = max(n['position_x'] for n in nodes)
        min_y = min(n['position_y'] for n in nodes)
        max_y = max(n['position_y'] for n in nodes)
        
        # 计算偏移量，使子工作流居中于原subdivision节点位置
        offset_x = center_x - (min_x + max_x) // 2
        offset_y = center_y - (min_y + max_y) // 2
        
        # 应用偏移
        positioned_nodes = []
        for node in nodes:
            positioned_node = node.copy()
            positioned_node['position_x'] = node['position_x'] + offset_x
            positioned_node['position_y'] = node['position_y'] + offset_y
            positioned_nodes.append(positioned_node)
        
        return positioned_nodes
    
    async def _finalize_merged_workflow(self, original_workflow_id: uuid.UUID, 
                                      new_workflow_base_id: uuid.UUID, 
                                      merge_operations: List[MergeOperation],
                                      creator_id: uuid.UUID,
                                      merge_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """完成合并后的工作流生成 - 重构版本"""
        try:
            logger.info(f"🎯 开始生成合并工作流: {new_workflow_base_id}")
            
            # 1. 创建新的工作流记录
            workflow_info = await self._create_merged_workflow_record(
                original_workflow_id, new_workflow_base_id, len(merge_operations), creator_id
            )
            new_workflow_id = workflow_info['workflow_id']
            
            # 2. 获取父工作流信息
            parent_workflow_id = await self._get_parent_workflow_id(original_workflow_id)
            if not parent_workflow_id:
                raise Exception("无法获取父工作流信息")
            
            # 3. 执行真正的节点替换合并
            merge_stats = await self._execute_node_replacement_merge(
                parent_workflow_id, new_workflow_id, new_workflow_base_id, merge_results
            )
            
            logger.info(f"✅ 合并工作流生成完成: {workflow_info['name']}")
            
            return {
                **workflow_info,
                **merge_stats,
                "merge_operations_count": len(merge_operations)
            }
            
        except Exception as e:
            logger.error(f"❌ 完成合并工作流生成失败: {e}")
            raise
    
    async def _create_merged_workflow_record(self, original_workflow_id: uuid.UUID,
                                           new_workflow_base_id: uuid.UUID,
                                           merge_count: int,
                                           creator_id: uuid.UUID) -> Dict[str, Any]:
        """创建合并工作流记录"""
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
        merged_description = f"合并了{merge_count}个subdivision的工作流，基于{parent_name}"
        
        await self.db.execute("""
            INSERT INTO workflow (
                workflow_id, workflow_base_id, name, description, 
                creator_id, is_current_version, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, new_workflow_id, new_workflow_base_id, merged_name, merged_description,
             creator_id, True, now_utc())
        
        logger.info(f"✅ 创建合并工作流记录: {merged_name}")
        
        return {
            "workflow_id": str(new_workflow_id),
            "workflow_base_id": str(new_workflow_base_id),
            "name": merged_name,
            "description": merged_description
        }
    
    async def _get_parent_workflow_id(self, original_workflow_id: uuid.UUID) -> Optional[str]:
        """获取父工作流ID"""
        result = await self.db.fetch_one("""
            SELECT w.workflow_id FROM workflow_instance wi
            JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id
            WHERE wi.workflow_instance_id = %s 
            AND w.is_current_version = TRUE
        """, original_workflow_id)
        
        return result['workflow_id'] if result else None
    
    async def _execute_node_replacement_merge(self, parent_workflow_id: str, 
                                            new_workflow_id: uuid.UUID,
                                            new_workflow_base_id: uuid.UUID,
                                            merge_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行真正的节点替换合并"""
        
        # 1. 收集所有subdivision信息和被替换的节点ID
        subdivision_mapping = {}  # original_node_id -> merge_result
        subdivision_node_ids = set()
        
        for result in merge_results:
            if result.get("success"):
                original_node = result['original_node']
                original_node_id = original_node['original_task_id']
                subdivision_node_ids.add(original_node_id)
                subdivision_mapping[original_node_id] = result
        
        logger.info(f"🔄 将替换 {len(subdivision_node_ids)} 个subdivision节点")
        
        # 2. 复制父工作流的保留节点（排除被subdivision的节点）
        node_id_mapping = await self._copy_preserved_nodes(
            parent_workflow_id, new_workflow_id, new_workflow_base_id, subdivision_node_ids
        )
        
        # 3. 为每个subdivision执行节点替换
        replacement_stats = await self._replace_subdivision_nodes(
            parent_workflow_id, new_workflow_id, new_workflow_base_id,
            subdivision_mapping, node_id_mapping
        )
        
        # 4. 重建所有连接
        connection_stats = await self._rebuild_all_connections(
            parent_workflow_id, new_workflow_id, subdivision_mapping, node_id_mapping
        )
        
        return {
            **replacement_stats,
            **connection_stats
        }
    
    async def _copy_preserved_nodes(self, parent_workflow_id: str, new_workflow_id: uuid.UUID,
                                  new_workflow_base_id: uuid.UUID, 
                                  subdivision_node_ids: set) -> Dict[str, uuid.UUID]:
        """复制父工作流中需要保留的节点"""
        node_id_mapping = {}
        
        # 查询保留的节点
        if subdivision_node_ids:
            placeholders = ','.join(['%s'] * len(subdivision_node_ids))
            parent_nodes = await self.db.fetch_all(f"""
                SELECT node_id, node_base_id, name, type, task_description, 
                       position_x, position_y, version
                FROM node 
                WHERE workflow_id = %s AND is_deleted = FALSE
                AND node_id NOT IN ({placeholders})
            """, parent_workflow_id, *subdivision_node_ids)
        else:
            parent_nodes = await self.db.fetch_all("""
                SELECT node_id, node_base_id, name, type, task_description, 
                       position_x, position_y, version
                FROM node 
                WHERE workflow_id = %s AND is_deleted = FALSE
            """, parent_workflow_id)
        
        # 复制节点
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
        
        logger.info(f"✅ 复制了 {len(parent_nodes)} 个父工作流保留节点")
        return node_id_mapping
    
    async def _replace_subdivision_nodes(self, parent_workflow_id: str,
                                       new_workflow_id: uuid.UUID, new_workflow_base_id: uuid.UUID,
                                       subdivision_mapping: Dict[str, Dict],
                                       node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """用子工作流节点替换subdivision节点"""
        replaced_nodes = 0
        
        for original_node_id, result in subdivision_mapping.items():
            workflow_structure = result['workflow_structure']
            
            # 复制子工作流的业务节点
            for node in workflow_structure['business_nodes']:
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
                
                replaced_nodes += 1
        
        logger.info(f"✅ 替换了 {replaced_nodes} 个subdivision节点为子工作流业务节点")
        return {"nodes_replaced": replaced_nodes}
    
    async def _rebuild_all_connections(self, parent_workflow_id: str, new_workflow_id: uuid.UUID,
                                     subdivision_mapping: Dict[str, Dict],
                                     node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """重建所有连接 - 改进版本"""
        # 获取父工作流的所有连接
        parent_connections = await self.db.fetch_all("""
            SELECT from_node_id, to_node_id, connection_type, condition_config
            FROM node_connection 
            WHERE workflow_id = %s
        """, parent_workflow_id)
        
        parent_connections_copied = 0
        subworkflow_connections_copied = 0
        cross_boundary_connections_created = 0
        
        subdivision_node_ids = set(subdivision_mapping.keys())
        
        # 1. 复制父工作流的保留连接（不涉及subdivision节点）
        for conn in parent_connections:
            from_id, to_id = conn['from_node_id'], conn['to_node_id']
            
            # 跳过涉及subdivision节点的连接
            if from_id in subdivision_node_ids or to_id in subdivision_node_ids:
                continue
            
            # 复制连接
            if from_id in node_id_mapping and to_id in node_id_mapping:
                await self.db.execute("""
                    INSERT INTO node_connection (
                        from_node_id, to_node_id, workflow_id,
                        connection_type, condition_config, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, node_id_mapping[from_id], node_id_mapping[to_id],
                     new_workflow_id, conn.get('connection_type', 'normal'),
                     conn.get('condition_config'), now_utc())
                parent_connections_copied += 1
        
        # 2. 复制每个子工作流的内部连接
        for original_node_id, result in subdivision_mapping.items():
            workflow_structure = result['workflow_structure']
            
            # 复制子工作流内部连接
            for conn in workflow_structure['business_connections']:
                from_id, to_id = conn['from_node_id'], conn['to_node_id']
                if from_id in node_id_mapping and to_id in node_id_mapping:
                    await self.db.execute("""
                        INSERT INTO node_connection (
                            from_node_id, to_node_id, workflow_id,
                            connection_type, condition_config, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, node_id_mapping[from_id], node_id_mapping[to_id],
                         new_workflow_id, conn.get('connection_type', 'normal'),
                         conn.get('condition_config'), now_utc())
                    subworkflow_connections_copied += 1
        
        # 3. 重建跨边界连接（subdivision节点的上下游连接）
        cross_boundary_connections_created = await self._rebuild_cross_boundary_connections(
            parent_connections, subdivision_mapping, node_id_mapping, new_workflow_id
        )
        
        logger.info(f"✅ 连接重建完成:")
        logger.info(f"   - 父工作流连接: {parent_connections_copied}")
        logger.info(f"   - 子工作流内部连接: {subworkflow_connections_copied}")
        logger.info(f"   - 跨边界连接: {cross_boundary_connections_created}")
        
        return {
            "parent_connections_copied": parent_connections_copied,
            "subworkflow_connections_copied": subworkflow_connections_copied,
            "cross_boundary_connections_created": cross_boundary_connections_created,
            "connections_count": parent_connections_copied + subworkflow_connections_copied + cross_boundary_connections_created
        }
    
    async def _rebuild_cross_boundary_connections(self, parent_connections: List[Dict],
                                                subdivision_mapping: Dict[str, Dict],
                                                node_id_mapping: Dict[str, uuid.UUID],
                                                new_workflow_id: uuid.UUID) -> int:
        """重建跨边界连接 - 改进的连接算法"""
        connections_created = 0
        
        for original_node_id, result in subdivision_mapping.items():
            workflow_structure = result['workflow_structure']
            entry_points = workflow_structure['entry_points']
            exit_points = workflow_structure['exit_points']
            
            # 重建上游连接：找到所有指向原subdivision节点的连接
            for conn in parent_connections:
                if conn['to_node_id'] == original_node_id:
                    from_id = conn['from_node_id']
                    if from_id in node_id_mapping:
                        # 连接到所有入口点
                        for entry_point in entry_points:
                            if entry_point['node_id'] in node_id_mapping:
                                await self.db.execute("""
                                    INSERT INTO node_connection (
                                        from_node_id, to_node_id, workflow_id,
                                        connection_type, condition_config, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                """, node_id_mapping[from_id],
                                     node_id_mapping[entry_point['node_id']],
                                     new_workflow_id, conn.get('connection_type', 'normal'),
                                     conn.get('condition_config'), now_utc())
                                connections_created += 1
                                logger.info(f"   🔗 上游连接: {from_id} -> {entry_point['name']}")
            
            # 重建下游连接：找到所有从原subdivision节点出发的连接
            for conn in parent_connections:
                if conn['from_node_id'] == original_node_id:
                    to_id = conn['to_node_id']
                    if to_id in node_id_mapping:
                        # 从所有出口点连接
                        for exit_point in exit_points:
                            if exit_point['node_id'] in node_id_mapping:
                                await self.db.execute("""
                                    INSERT INTO node_connection (
                                        from_node_id, to_node_id, workflow_id,
                                        connection_type, condition_config, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                """, node_id_mapping[exit_point['node_id']],
                                     node_id_mapping[to_id],
                                     new_workflow_id, conn.get('connection_type', 'normal'),
                                     conn.get('condition_config'), now_utc())
                                connections_created += 1
                                logger.info(f"   🔗 下游连接: {exit_point['name']} -> {to_id}")
        
        return connections_created
    
    async def _validate_merge_consistency(self, merge_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """验证合并操作的数据一致性"""
        try:
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "stats": {
                    "total_subdivisions": len(merge_results),
                    "valid_subdivisions": 0,
                    "total_business_nodes": 0,
                    "total_connections": 0
                }
            }
            
            for result in merge_results:
                if not result.get("success"):
                    validation_results["errors"].append(f"合并失败的subdivision: {result.get('error', 'Unknown')}")
                    continue
                
                validation_results["stats"]["valid_subdivisions"] += 1
                
                # 验证工作流结构
                workflow_structure = result.get('workflow_structure', {})
                business_nodes = workflow_structure.get('business_nodes', [])
                business_connections = workflow_structure.get('business_connections', [])
                entry_points = workflow_structure.get('entry_points', [])
                exit_points = workflow_structure.get('exit_points', [])
                
                validation_results["stats"]["total_business_nodes"] += len(business_nodes)
                validation_results["stats"]["total_connections"] += len(business_connections)
                
                # 检查入口出口点
                if not entry_points:
                    validation_results["warnings"].append(f"Subdivision {result['candidate'].node_name} 没有识别出入口点")
                
                if not exit_points:
                    validation_results["warnings"].append(f"Subdivision {result['candidate'].node_name} 没有识别出出口点")
                
                # 检查节点ID唯一性
                node_ids = [n['node_id'] for n in business_nodes]
                if len(node_ids) != len(set(node_ids)):
                    validation_results["errors"].append(f"Subdivision {result['candidate'].node_name} 存在重复的节点ID")
                    validation_results["valid"] = False
                
                # 检查连接的节点是否存在
                for conn in business_connections:
                    from_id, to_id = conn['from_node_id'], conn['to_node_id']
                    if from_id not in node_ids or to_id not in node_ids:
                        validation_results["errors"].append(f"连接引用了不存在的节点: {from_id} -> {to_id}")
                        validation_results["valid"] = False
            
            if validation_results["errors"]:
                validation_results["valid"] = False
                
            logger.info(f"🔍 合并一致性验证完成:")
            logger.info(f"   - 有效: {validation_results['valid']}")
            logger.info(f"   - 错误: {len(validation_results['errors'])}个")
            logger.info(f"   - 警告: {len(validation_results['warnings'])}个")
            logger.info(f"   - 统计: {validation_results['stats']}")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"❌ 合并一致性验证失败: {e}")
            return {
                "valid": False,
                "errors": [f"验证过程失败: {str(e)}"],
                "warnings": [],
                "stats": {}
            }
