"""
工作流合并服务 - Workflow Template Tree Based Merge Service

核心功能：
1. 完全基于WorkflowTemplateTree进行合并
2. 支持递归合并：从子节点沿着路径一路合并到根节点
3. 避免直接查询subdivision表，减少数据库查询
4. 生成新的工作流模板
"""

import uuid
from typing import Dict, Any, List, Optional
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
        """基于workflow_template_tree获取合并候选项 - 重构版本，完全基于树数据"""
        try:
            logger.info(f"🔍 获取合并候选: {workflow_instance_id}")
            
            # 直接构建工作流模板树
            from .workflow_template_connection_service import WorkflowTemplateConnectionService
            connection_service = WorkflowTemplateConnectionService()
            subdivisions_data = await connection_service._get_all_subdivisions_simple(workflow_instance_id)
            
            if not subdivisions_data:
                logger.info("无subdivision数据")
                return []
                
            tree = await WorkflowTemplateTree().build_from_subdivisions(subdivisions_data, workflow_instance_id)
            
            # 🔧 完全基于tree获取候选项，不再查询subdivision表
            tree_candidates = tree.get_merge_candidates_with_tree_data()
            
            # 转换为MergeCandidate对象
            candidates = []
            for tree_candidate in tree_candidates:
                candidate = MergeCandidate(
                    subdivision_id=tree_candidate['subdivision_id'],
                    parent_subdivision_id=tree_candidate.get('parent_subdivision_id'),
                    workflow_instance_id=tree_candidate['workflow_instance_id'],
                    workflow_base_id=tree_candidate['workflow_base_id'],
                    node_name=tree_candidate['node_name'],
                    depth=tree_candidate['depth'],
                    can_merge=tree_candidate['can_merge'],
                    merge_reason=tree_candidate['merge_reason']
                )
                candidates.append(candidate)
                
                logger.info(f"   📋 候选项: {candidate.node_name} (深度: {candidate.depth})")
            
            logger.info(f"获得 {len(candidates)} 个候选项")
            return candidates
            
        except Exception as e:
            logger.error(f"获取合并候选失败: {e}")
            raise
    
    async def execute_merge(self, workflow_instance_id: uuid.UUID, 
                          selected_merges: List[str], 
                          creator_id: uuid.UUID, 
                          recursive: bool = True) -> Dict[str, Any]:
        """执行工作流合并 - 重构版本，完全基于workflow_template_tree，默认启用递归合并"""
        try:
            logger.info(f"🚀 [递归合并] 开始工作流合并")
            logger.info(f"   - workflow_instance_id: {workflow_instance_id}")
            logger.info(f"   - selected_merges: {selected_merges}")
            logger.info(f"   - creator_id: {creator_id}")
            logger.info(f"   - recursive: {recursive} (默认启用)")
            
            # 构建工作流模板树
            logger.info(f"🌳 [构建树] 开始构建工作流模板树...")
            from .workflow_template_connection_service import WorkflowTemplateConnectionService
            connection_service = WorkflowTemplateConnectionService()
            subdivisions_data = await connection_service._get_all_subdivisions_simple(workflow_instance_id)
            
            logger.info(f"📊 [subdivision数据] 获得 {len(subdivisions_data) if subdivisions_data else 0} 个subdivision记录")
            
            if not subdivisions_data:
                logger.warning(f"⚠️ [subdivision数据] 没有subdivision数据")
                return {"success": False, "message": "没有subdivision数据"}
                
            tree = await WorkflowTemplateTree().build_from_subdivisions(subdivisions_data, workflow_instance_id)
            logger.info(f"✅ [构建树] 工作流模板树构建完成")
            
            # 🔧 基于tree计算合并候选项（智能递归路径计算）
            logger.info(f"🔄 [智能递归] 计算递归合并路径...")
            
            # 🔧 修复：处理前端传递的template_前缀
            cleaned_selected_merges = []
            for merge_id in selected_merges:
                if merge_id.startswith('template_'):
                    # 移除template_前缀
                    cleaned_id = merge_id.replace('template_', '')
                    cleaned_selected_merges.append(cleaned_id)
                    logger.info(f"   🔧 清理节点ID: {merge_id} -> {cleaned_id}")
                else:
                    cleaned_selected_merges.append(merge_id)
            
            tree_candidates = tree.calculate_recursive_merge_path(cleaned_selected_merges)
            
            logger.info(f"📊 [合并路径] 递归合并路径包含 {len(tree_candidates)} 个节点")
            if not tree_candidates:
                logger.warning(f"⚠️ [合并路径] 未找到匹配的候选项")
                return {"success": False, "message": "未找到匹配的候选项"}
            
            for i, candidate in enumerate(tree_candidates):
                logger.info(f"   路径节点 {i+1}: {candidate['node_name']} (深度: {candidate['depth']})")
                
            # 获取初始工作流基础ID
            initial_workflow_base_id = await self._get_workflow_base_id(workflow_instance_id)
            if not initial_workflow_base_id:
                return {"success": False, "message": "无法获取工作流基础ID"}
            
            logger.info(f"📋 [初始工作流] 初始工作流基础ID: {initial_workflow_base_id}")
            
            # 🔧 改为真正的递归合并：一次性替换所有选中节点到一个新模板
            logger.info(f"🔄 [真递归合并] 开始真正的递归合并...")
            logger.info(f"📊 [合并候选] 将把 {len(tree_candidates)} 个节点递归合并到一个新模板中")
            
            # 生成单一的新工作流模板
            new_workflow_base_id = uuid.uuid4()
            logger.info(f"🆕 [新模板] 生成统一的新工作流基础ID: {new_workflow_base_id}")
            
            # 获取当前工作流的最佳版本ID
            current_workflow_id = await self._get_best_workflow_id_by_base(initial_workflow_base_id)
            if not current_workflow_id:
                return {"success": False, "error": f"无法找到当前工作流: {initial_workflow_base_id}"}
                
            logger.info(f"📋 [源工作流] 当前工作流ID: {current_workflow_id}")
            
            # 创建新的统一工作流记录
            unified_workflow_info = await self._create_unified_recursive_workflow_record(
                initial_workflow_base_id, new_workflow_base_id, len(tree_candidates), creator_id
            )
            new_workflow_id = unified_workflow_info['workflow_id']
            logger.info(f"✅ [新模板记录] 创建完成: {unified_workflow_info['name']} (ID: {new_workflow_id})")
            
            # 执行统一的递归节点替换合并
            logger.info(f"🔄 [开始递归替换] 执行统一的递归节点替换合并")
            merge_stats = await self._execute_unified_recursive_node_replacement(
                current_workflow_id, new_workflow_id, new_workflow_base_id, tree_candidates
            )
            
            total_merged = len(tree_candidates)
            
            logger.info(f"🎉 [真递归合并] 合并流程完成!")
            logger.info(f"   - 初始工作流基础ID: {initial_workflow_base_id}")
            logger.info(f"   - 最终工作流基础ID: {new_workflow_base_id}")
            logger.info(f"   - 总合并节点数: {total_merged}")
            logger.info(f"   - 合并模式: 真正递归（单一模板）")
            
            return {
                "success": True,
                "final_workflow_base_id": str(new_workflow_base_id),
                "total_merged": total_merged,
                "merge_layers": 1,  # 只有一个层级，因为是统一合并
                "workflow_info": unified_workflow_info,
                "merge_stats": merge_stats,
                "message": f"递归合并完成，处理了{total_merged}个节点到统一模板"
            }
                
        except Exception as e:
            logger.error(f"❌ [递归合并] 工作流合并失败: {e}")
            import traceback
            logger.error(f"   详细错误: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

    async def _find_parent_workflow_base_id(self, current_candidate: Dict[str, Any]) -> Optional[str]:
        """
        根据树结构找到当前候选项的父工作流基础ID
        
        Args:
            current_candidate: 当前候选项
            
        Returns:
            父工作流的基础ID，如果找不到则返回None
        """
        try:
            logger.info(f"🔍 [父工作流查找] 查找候选项的父工作流: {current_candidate['node_name']}")
            logger.info(f"   - 当前候选项深度: {current_candidate['depth']}")
            logger.info(f"   - subdivision_id: {current_candidate['subdivision_id']}")
            
            # 从tree中找到对应的节点
            current_tree_node = current_candidate.get('tree_node')
            if not current_tree_node:
                logger.warning(f"   ⚠️ 当前候选项没有tree_node引用")
                return None
            
            # 获取父节点
            parent_tree_node = current_tree_node.parent_node
            if not parent_tree_node:
                logger.info(f"   📋 当前节点是根节点，无父工作流")
                return None
            
            logger.info(f"   📋 找到父节点: {parent_tree_node.workflow_name}")
            logger.info(f"   📋 父节点workflow_base_id: {parent_tree_node.workflow_base_id}")
            logger.info(f"   📋 父节点workflow_instance_id: {parent_tree_node.workflow_instance_id}")
            
            # 获取父工作流的当前版本workflow_id
            if parent_tree_node.workflow_instance_id:
                parent_workflow_base_id = await self._get_workflow_base_id_from_instance(
                    parent_tree_node.workflow_instance_id
                )
                
                if parent_workflow_base_id:
                    logger.info(f"   ✅ 找到父工作流基础ID: {parent_workflow_base_id}")
                    return parent_workflow_base_id
            
            # 如果通过workflow_instance_id找不到，直接使用workflow_base_id
            parent_workflow_base_id = parent_tree_node.workflow_base_id
            logger.info(f"   🔧 使用父节点的workflow_base_id: {parent_workflow_base_id}")
            
            return parent_workflow_base_id
            
        except Exception as e:
            logger.error(f"❌ [父工作流查找] 查找失败: {e}")
            return None
    
    async def _get_workflow_base_id_from_instance(self, workflow_instance_id: str) -> Optional[str]:
        """根据工作流实例ID获取对应的工作流基础ID"""
        try:
            result = await self.db.fetch_one("""
                SELECT workflow_base_id FROM workflow_instance 
                WHERE workflow_instance_id = %s
            """, workflow_instance_id)
            
            return str(result['workflow_base_id']) if result else None
            
        except Exception as e:
            logger.error(f"根据实例ID获取基础ID失败: {e}")
            return None
        
    async def _get_workflow_base_id(self, workflow_instance_id: uuid.UUID) -> Optional[str]:
        """获取工作流基础ID"""
        result = await self.db.fetch_one("""
            SELECT workflow_base_id FROM workflow_instance 
            WHERE workflow_instance_id = %s
        """, workflow_instance_id)
        return str(result['workflow_base_id']) if result else None
    
    async def _merge_depth_layer_tree_based(self, current_workflow_base_id: str, 
                                          depth_candidates: List[Dict[str, Any]], 
                                          creator_id: uuid.UUID, depth: int) -> Dict[str, Any]:
        """基于tree数据的分层合并 - 不再查询subdivision表"""
        try:
            logger.info(f"🔧 [Tree合并] 开始合并深度 {depth}: {len(depth_candidates)} 个候选项")
            
            # 🔍 调试：分析当前合并状态
            logger.info(f"📊 [合并状态] 当前工作流基础ID: {current_workflow_base_id}")
            logger.info(f"📊 [合并状态] 创建者ID: {creator_id}")
            logger.info(f"📊 [合并状态] 合并深度: {depth}")
            
            # 🔧 新增：分析父工作流的版本情况
            await self._debug_workflow_versions(current_workflow_base_id, f"合并深度{depth}前")
            
            for i, candidate in enumerate(depth_candidates):
                logger.info(f"   候选项 {i+1}: {candidate.get('node_name', 'Unknown')}")
                logger.info(f"     - subdivision_id: {candidate.get('subdivision_id')}")
                logger.info(f"     - workflow_instance_id: {candidate.get('workflow_instance_id')}")
                logger.info(f"     - workflow_base_id: {candidate.get('workflow_base_id')}")
                logger.info(f"     - depth: {candidate.get('depth')}")
            
            # 1. 生成新的工作流版本
            new_workflow_base_id = uuid.uuid4()
            logger.info(f"🆕 [新工作流] 生成新工作流基础ID: {new_workflow_base_id}")
            
            # 2. 获取当前工作流的workflow_id - 🔧 智能版本选择
            current_workflow_id = await self._get_best_workflow_id_by_base(current_workflow_base_id)
            if not current_workflow_id:
                return {"success": False, "error": f"无法找到当前工作流: {current_workflow_base_id}"}
                
            logger.info(f"📋 [当前工作流] 当前工作流ID: {current_workflow_id}")
            
            # 🔍 调试：分析当前父工作流状态
            await self._debug_current_workflow_state(current_workflow_id, "合并前")
            
            # 3. 创建新的工作流记录
            new_workflow_info = await self._create_layered_workflow_record(
                current_workflow_base_id, new_workflow_base_id, depth, len(depth_candidates), creator_id
            )
            new_workflow_id = new_workflow_info['workflow_id']
            logger.info(f"✅ [新工作流记录] 创建完成: {new_workflow_info['name']} (ID: {new_workflow_id})")
            
            # 4. 执行基于tree的节点替换合并
            logger.info(f"🔄 [开始节点替换] 执行基于tree的节点替换合并")
            merge_stats = await self._execute_tree_based_node_replacement(
                current_workflow_id, new_workflow_id, new_workflow_base_id, depth_candidates
            )
            
            # 🔍 调试：分析合并后的新工作流状态
            await self._debug_current_workflow_state(new_workflow_id, "合并后")
            
            logger.info(f"✅ [Tree合并] 深度 {depth} 合并完成:")
            logger.info(f"   - 新工作流: {new_workflow_info['name']}")
            logger.info(f"   - 合并节点: {merge_stats.get('nodes_replaced', 0)}")
            logger.info(f"   - 重建连接: {merge_stats.get('connections_count', 0)}")
            
            # 🔍 调试：显示工作流切换过程
            logger.info(f"🔄 [工作流切换] 从 {current_workflow_base_id} 切换到 {new_workflow_base_id}")
            logger.info(f"   - 原工作流ID: {current_workflow_id}")
            logger.info(f"   - 新工作流ID: {new_workflow_id}")
            logger.info(f"   - 新工作流基础ID将作为下一层的输入")
            
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
            logger.error(f"❌ [Tree合并] 深度 {depth} 合并失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_tree_based_node_replacement(self, parent_workflow_id: str,
                                                 new_workflow_id: uuid.UUID, new_workflow_base_id: uuid.UUID,
                                                 tree_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """基于tree数据执行节点替换合并 - 混合方法：优先使用tree数据，必要时查询subdivision表"""
        try:
            # 1. 收集需要替换的节点ID（优先使用tree数据，必要时查询subdivision）
            nodes_to_replace = set()
            tree_mapping = {}  # original_node_id -> tree_candidate
            
            logger.info(f"🔍 [混合方法] 分析 {len(tree_candidates)} 个tree候选项:")
            for candidate in tree_candidates:
                original_node_id = candidate.get('original_node_id')
                subdivision_id = candidate.get('subdivision_id')
                node_name = candidate.get('node_name', 'Unknown')
                
                logger.info(f"     候选项: {node_name}")
                logger.info(f"       - original_node_id (from tree): {original_node_id}")
                logger.info(f"       - subdivision_id: {subdivision_id}")
                
                # 如果tree中有original_node_id，直接使用
                if original_node_id:
                    nodes_to_replace.add(original_node_id)
                    tree_mapping[original_node_id] = candidate
                    logger.info(f"   🔧 将替换节点 (来自tree): {node_name} (node_id: {original_node_id})")
                # 否则，回退到subdivision查询
                elif subdivision_id:
                    logger.info(f"   🔍 tree数据不完整，查询subdivision: {subdivision_id}")
                    original_node_info = await self._get_original_node_info(subdivision_id)
                    if original_node_info:
                        actual_node_id = original_node_info['node_id']
                        nodes_to_replace.add(actual_node_id)
                        # 将subdivision查询结果补充到candidate中
                        enhanced_candidate = candidate.copy()
                        enhanced_candidate.update({
                            'original_node_id': actual_node_id,
                            'original_task_id': original_node_info.get('original_task_id'),
                            'original_node_position': {
                                'x': original_node_info.get('position_x', 0),
                                'y': original_node_info.get('position_y', 0)
                            },
                            'original_node_info': original_node_info  # 完整信息供后续使用
                        })
                        tree_mapping[actual_node_id] = enhanced_candidate
                        logger.info(f"   🔧 将替换节点 (来自subdivision): {original_node_info['name']} (node_id: {actual_node_id})")
                    else:
                        logger.warning(f"   ❌ 无法获取subdivision的原始节点信息: {subdivision_id}")
                else:
                    logger.warning(f"   ⚠️ 候选项缺少识别信息: {node_name}")
            
            logger.info(f"🔄 [混合方法] 将替换 {len(nodes_to_replace)} 个节点")
            
            # 2. 复制父工作流的保留节点（排除要替换的节点）
            node_id_mapping = await self._copy_preserved_nodes_simple(
                parent_workflow_id, new_workflow_id, new_workflow_base_id, nodes_to_replace
            )
            
            # 3. 基于tree数据执行节点替换
            replacement_stats = await self._replace_nodes_from_tree_data(
                new_workflow_id, new_workflow_base_id, tree_mapping, node_id_mapping
            )
            
            # 4. 重建连接
            connection_stats = await self._rebuild_connections_from_tree_data(
                parent_workflow_id, new_workflow_id, tree_mapping, node_id_mapping
            )
            
            logger.info(f"✅ [混合方法] 完成: 替换{replacement_stats['nodes_replaced']}节点, 重建{connection_stats['connections_count']}连接")
            
            return {
                **replacement_stats,
                **connection_stats
            }
            
        except Exception as e:
            logger.error(f"❌ [混合方法] 执行失败: {e}")
            raise
    
    async def _copy_preserved_nodes_simple(self, parent_workflow_id: str, new_workflow_id: uuid.UUID,
                                          new_workflow_base_id: uuid.UUID, 
                                          nodes_to_replace: set) -> Dict[str, uuid.UUID]:
        """复制父工作流中需要保留的节点 - 修复版本"""
        node_id_mapping = {}
        
        # 🔧 调试：验证parent_workflow_id是否有效
        logger.info(f"🔍 [节点复制] 开始复制父工作流节点:")
        logger.info(f"   - 父工作流ID: {parent_workflow_id}")
        logger.info(f"   - 新工作流ID: {new_workflow_id}")
        logger.info(f"   - 新工作流基础ID: {new_workflow_base_id}")
        
        # 🔧 修复：先验证父工作流是否存在
        parent_workflow_check = await self.db.fetch_one("""
            SELECT workflow_id, name, workflow_base_id, is_current_version
            FROM workflow 
            WHERE workflow_id = %s
        """, parent_workflow_id)
        
        if not parent_workflow_check:
            logger.error(f"❌ [节点复制] 父工作流不存在: {parent_workflow_id}")
            return node_id_mapping
            
        logger.info(f"✅ [父工作流验证] 找到父工作流: {parent_workflow_check['name']}")
        logger.info(f"   - 工作流基础ID: {parent_workflow_check['workflow_base_id']}")
        logger.info(f"   - 是否当前版本: {parent_workflow_check['is_current_version']}")
        
        # 🔧 调试：先查询所有父工作流节点
        all_parent_nodes = await self.db.fetch_all("""
            SELECT node_id, name, type, workflow_id, is_deleted
            FROM node 
            WHERE workflow_id = %s
        """, parent_workflow_id)
        
        logger.info(f"🔍 [父工作流节点] 总节点数: {len(all_parent_nodes)}")
        active_nodes = [n for n in all_parent_nodes if not n['is_deleted']]
        logger.info(f"🔍 [父工作流节点] 活跃节点数: {len(active_nodes)}")
        
        for node in all_parent_nodes:
            status = "已删除" if node['is_deleted'] else "活跃"
            logger.info(f"     - {node['name']} ({node['type']}) ID: {node['node_id'][:8]}... 状态: {status}")
        
        logger.info(f"🔍 [待替换节点] 需要替换的节点ID集合: {[str(nid)[:8] + '...' for nid in nodes_to_replace]}")
        
        # 🔧 修复：分两步查询，更清晰地处理过滤逻辑
        if nodes_to_replace:
            # 构建NOT IN子句，注意UUID类型转换
            node_ids_list = list(nodes_to_replace)
            placeholders = ','.join(['%s'] * len(node_ids_list))
            
            logger.info(f"🔍 [查询参数] 执行NOT IN查询，排除 {len(node_ids_list)} 个节点")
            
            parent_nodes = await self.db.fetch_all(f"""
                SELECT node_id, node_base_id, name, type, task_description, 
                       position_x, position_y, version, is_deleted
                FROM node 
                WHERE workflow_id = %s 
                AND is_deleted = FALSE
                AND node_id NOT IN ({placeholders})
            """, parent_workflow_id, *node_ids_list)
        else:
            logger.info(f"🔍 [查询参数] 执行全量查询（无需排除节点）")
            parent_nodes = await self.db.fetch_all("""
                SELECT node_id, node_base_id, name, type, task_description, 
                       position_x, position_y, version, is_deleted
                FROM node 
                WHERE workflow_id = %s AND is_deleted = FALSE
            """, parent_workflow_id)
        
        logger.info(f"🔍 [过滤结果] 过滤后保留的节点数: {len(parent_nodes)}")
        
        if not parent_nodes:
            logger.warning(f"⚠️ [过滤结果] 没有找到任何需要保留的父工作流节点!")
            logger.warning(f"   可能原因:")
            logger.warning(f"   1. 所有父工作流节点都被标记为替换")
            logger.warning(f"   2. 父工作流中没有活跃节点") 
            logger.warning(f"   3. 数据库查询条件有问题")
            
            # 🔧 进一步调试：检查是否所有节点都在替换列表中
            if nodes_to_replace and all_parent_nodes:
                all_active_node_ids = {n['node_id'] for n in all_parent_nodes if not n['is_deleted']}
                replace_node_ids = set(nodes_to_replace)
                
                logger.warning(f"   调试信息:")
                logger.warning(f"   - 活跃节点总数: {len(all_active_node_ids)}")
                logger.warning(f"   - 待替换节点数: {len(replace_node_ids)}")
                logger.warning(f"   - 活跃节点ID: {[str(nid)[:8] + '...' for nid in all_active_node_ids]}")
                logger.warning(f"   - 待替换ID: {[str(nid)[:8] + '...' for nid in replace_node_ids]}")
                
                # 检查交集
                intersection = all_active_node_ids.intersection(replace_node_ids)
                remaining = all_active_node_ids - replace_node_ids
                
                logger.warning(f"   - 匹配的待替换节点: {len(intersection)} 个")
                logger.warning(f"   - 应该保留的节点: {len(remaining)} 个")
                
                if len(intersection) == 0:
                    logger.error(f"❌ [数据不一致] 待替换节点ID在父工作流中不存在!")
                if len(remaining) == 0:
                    logger.error(f"❌ [全部替换] 所有父工作流节点都被标记为替换!")
            
            return node_id_mapping
        
        for node in parent_nodes:
            logger.info(f"     ✅ 保留: {node['name']} ({node['type']}) ID: {node['node_id'][:8]}...")
        
        # 复制节点
        for node in parent_nodes:
            new_node_id = uuid.uuid4()
            new_node_base_id = uuid.uuid4()
            node_id_mapping[node['node_id']] = new_node_id
            
            logger.info(f"   📄 复制节点: {node['name']} -> 新ID: {str(new_node_id)[:8]}...")
            
            await self.db.execute("""
                INSERT INTO node (
                    node_id, node_base_id, workflow_id, workflow_base_id,
                    name, type, task_description, position_x, position_y,
                    version, is_current_version, created_at, is_deleted
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, new_node_id, new_node_base_id, new_workflow_id, new_workflow_base_id,
                 node['name'], node['type'], node['task_description'], 
                 node['position_x'], node['position_y'], 1, True, now_utc(), False)
        
        logger.info(f"✅ [节点复制] 成功复制了 {len(parent_nodes)} 个父工作流保留节点")
        logger.info(f"📊 [节点映射] 建立了 {len(node_id_mapping)} 个节点ID映射关系")
        
        return node_id_mapping
    
    async def _replace_nodes_from_tree_data(self, new_workflow_id: uuid.UUID, new_workflow_base_id: uuid.UUID,
                                           tree_mapping: Dict[str, Dict], 
                                           node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """基于tree数据替换节点 - 不查询subdivision表"""
        replaced_nodes = 0
        
        logger.info(f"🔄 [节点替换] 开始处理 {len(tree_mapping)} 个待替换的节点")
        
        for tree_candidate in tree_mapping.values():
            logger.info(f"🔄 [Tree替换] 处理节点: {tree_candidate['node_name']}")
            
            # 直接从tree_candidate获取子工作流结构
            tree_node = tree_candidate.get('tree_node')
            if not tree_node:
                logger.warning(f"⚠️ tree_candidate中没有tree_node引用")
                continue
            
            # 🔍 调试：显示子工作流信息
            logger.info(f"   📋 [子工作流] workflow_instance_id: {tree_node.workflow_instance_id}")
            logger.info(f"   📋 [子工作流] workflow_base_id: {tree_node.workflow_base_id}")
            logger.info(f"   📋 [子工作流] workflow_name: {tree_node.workflow_name}")
            logger.info(f"   📋 [子工作流] status: {tree_node.status}")
            
            # 从tree中获取原始节点位置信息    
            original_position = tree_candidate.get('original_node_position', {})
            center_x = original_position.get('x', 0)
            center_y = original_position.get('y', 0)
            logger.info(f"   📍 [原始位置] x: {center_x}, y: {center_y}")
            
            # 获取子工作流结构
            logger.info(f"   🔍 [分析子工作流] 开始分析子工作流结构...")
            workflow_structure = await self._analyze_subworkflow_structure_from_tree(
                tree_node, center_x, center_y
            )
            
            # 🔍 调试：显示子工作流结构分析结果
            business_nodes = workflow_structure['business_nodes']
            entry_points = workflow_structure['entry_points']
            exit_points = workflow_structure['exit_points']
            business_connections = workflow_structure['business_connections']
            
            logger.info(f"   📊 [子工作流结构] 业务节点数: {len(business_nodes)}")
            logger.info(f"   📊 [子工作流结构] 入口点数: {len(entry_points)}")
            logger.info(f"   📊 [子工作流结构] 出口点数: {len(exit_points)}")
            logger.info(f"   📊 [子工作流结构] 内部连接数: {len(business_connections)}")
            
            for i, node in enumerate(business_nodes):
                logger.info(f"     业务节点 {i+1}: {node['name']} ({node['type']}) pos:({node['position_x']},{node['position_y']})")
            
            for i, entry in enumerate(entry_points):
                logger.info(f"     入口点 {i+1}: {entry['name']} ({entry['type']})")
                
            for i, exit_point in enumerate(exit_points):
                logger.info(f"     出口点 {i+1}: {exit_point['name']} ({exit_point['type']})")
            
            # 复制子工作流的业务节点
            logger.info(f"   📄 [复制节点] 开始复制 {len(business_nodes)} 个业务节点")
            for node in workflow_structure['business_nodes']:
                new_node_id = uuid.uuid4()
                new_node_base_id = uuid.uuid4()
                
                # 🔧 修复：使用复合key避免映射冲突 (原节点ID + 子工作流标识)
                composite_key = f"{node['node_id']}@{tree_candidate['node_name']}"
                node_id_mapping[composite_key] = new_node_id
                
                # 🔧 为了向后兼容，也保留原始映射，但要确保不覆盖
                if node['node_id'] not in node_id_mapping:
                    node_id_mapping[node['node_id']] = new_node_id
                else:
                    # 如果已存在，记录原始映射用于连接重建
                    logger.info(f"   🔧 原始节点ID冲突: {node['node_id']} 已存在映射，使用复合key: {composite_key}")
                
                logger.info(f"   📄 复制业务节点: {node['name']} -> 新ID: {new_node_id} (key: {composite_key})")
                
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
        
        logger.info(f"✅ [Tree替换] 替换了 {replaced_nodes} 个节点")
        return {"nodes_replaced": replaced_nodes}
    
    async def _analyze_subworkflow_structure_from_tree(self, tree_node: WorkflowTemplateNode, 
                                                     center_x: int, center_y: int) -> Dict[str, Any]:
        """基于tree节点分析子工作流结构 - 重用现有逻辑"""
        # 直接调用现有的分析方法，使用tree_node中的workflow_instance_id
        return await self._analyze_subworkflow_structure(
            tree_node.workflow_instance_id, center_x, center_y
        )
    
    async def _rebuild_connections_from_tree_data(self, parent_workflow_id: str, new_workflow_id: uuid.UUID,
                                                tree_mapping: Dict[str, Dict],
                                                node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """基于tree数据重建连接"""
        logger.info(f"🔗 [连接重建] 开始重建连接")
        logger.info(f"   - 父工作流ID: {parent_workflow_id}")
        logger.info(f"   - 新工作流ID: {new_workflow_id}")
        logger.info(f"   - 节点映射数量: {len(node_id_mapping)}")
        logger.info(f"   - 待替换节点数量: {len(tree_mapping)}")
        
        # 获取父工作流的所有连接
        parent_connections = await self.db.fetch_all("""
            SELECT from_node_id, to_node_id, connection_type, condition_config
            FROM node_connection 
            WHERE workflow_id = %s
        """, parent_workflow_id)
        
        logger.info(f"📊 [父工作流连接] 找到 {len(parent_connections)} 个父工作流连接")
        for i, conn in enumerate(parent_connections):
            logger.info(f"   连接 {i+1}: {conn['from_node_id']} -> {conn['to_node_id']} (类型: {conn.get('connection_type', 'normal')})")
        
        parent_connections_copied = 0
        subworkflow_connections_copied = 0
        cross_boundary_connections_created = 0
        
        replaced_node_ids = set(tree_mapping.keys())
        logger.info(f"🔧 [替换节点] 被替换的节点ID集合: {list(replaced_node_ids)}")
        
        # 1. 复制父工作流的保留连接（不涉及被替换节点的连接）
        logger.info(f"📋 [保留连接] 开始复制父工作流的保留连接...")
        for conn in parent_connections:
            from_id, to_id = conn['from_node_id'], conn['to_node_id']
            
            # 跳过涉及被替换节点的连接（这些连接需要在跨边界连接中重建）
            if from_id in replaced_node_ids or to_id in replaced_node_ids:
                logger.info(f"   跳过涉及替换节点的连接: {from_id} -> {to_id}")
                continue
            
            if from_id in node_id_mapping and to_id in node_id_mapping:
                new_from_id = node_id_mapping[from_id]
                new_to_id = node_id_mapping[to_id]
                
                await self.db.execute("""
                    INSERT INTO node_connection (
                        from_node_id, to_node_id, workflow_id,
                        connection_type, condition_config, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, new_from_id, new_to_id,
                     new_workflow_id, conn.get('connection_type', 'normal'),
                     conn.get('condition_config'), now_utc())
                parent_connections_copied += 1
                logger.info(f"   ✅ 复制保留连接: {from_id} -> {to_id} 映射为 {new_from_id} -> {new_to_id}")
            else:
                logger.info(f"   ⏭️ 跳过连接（节点不在映射中）: {from_id} -> {to_id}")
        
        logger.info(f"📊 [保留连接] 复制了 {parent_connections_copied} 个父工作流保留连接")
        
        # 2. 复制子工作流内部连接并收集出入口点映射
        logger.info(f"🔄 [子工作流连接] 开始处理 {len(tree_mapping)} 个子工作流的内部连接...")
        
        # 3. 🔧 新增：收集替换节点的出入口点映射
        logger.info(f"🔗 [映射收集] 收集替换节点的出入口点映射...")
        replaced_to_exit_mapping = {}  # replaced_node_id -> [exit_point_new_ids]
        replaced_to_entry_mapping = {}  # replaced_node_id -> [entry_point_new_ids]
        for original_node_id, tree_candidate in tree_mapping.items():
            logger.info(f"   处理子工作流: {tree_candidate['node_name']}")
            
            tree_node = tree_candidate.get('tree_node')
            if not tree_node:
                logger.warning(f"   ⚠️ 跳过：缺少tree_node引用")
                continue
                
            original_position = tree_candidate.get('original_node_position', {})
            workflow_structure = await self._analyze_subworkflow_structure_from_tree(
                tree_node, original_position.get('x', 0), original_position.get('y', 0)
            )
            
            # 复制子工作流内部连接
            business_connections = workflow_structure['business_connections']
            logger.info(f"     📋 [内部连接] 发现 {len(business_connections)} 个子工作流内部连接")
            
            # 🔧 调试：显示子工作流的完整结构
            business_nodes = workflow_structure['business_nodes']
            entry_points = workflow_structure['entry_points']
            exit_points = workflow_structure['exit_points']
            
            logger.info(f"     📊 [子工作流结构详情] {tree_candidate['node_name']}:")
            logger.info(f"       - 业务节点: {len(business_nodes)}个")
            for i, node in enumerate(business_nodes):
                logger.info(f"         节点{i+1}: {node['name']} (ID: {node['node_id'][:8]}...) pos:({node['position_x']},{node['position_y']})")
            
            logger.info(f"       - 入口点: {len(entry_points)}个")
            for i, entry in enumerate(entry_points):
                logger.info(f"         入口{i+1}: {entry['name']} (ID: {entry['node_id'][:8]}...)")
                
            logger.info(f"       - 出口点: {len(exit_points)}个")
            for i, exit_pt in enumerate(exit_points):
                logger.info(f"         出口{i+1}: {exit_pt['name']} (ID: {exit_pt['node_id'][:8]}...)")
            
            logger.info(f"       - 内部连接: {len(business_connections)}个")
            for i, conn in enumerate(business_connections):
                logger.info(f"         连接{i+1}: {conn['from_node_id'][:8]}... -> {conn['to_node_id'][:8]}...")
            
            for conn in business_connections:
                from_id, to_id = conn['from_node_id'], conn['to_node_id']
                
                # 🔧 调试：检查节点映射状态
                from_mapped = from_id in node_id_mapping
                to_mapped = to_id in node_id_mapping
                logger.info(f"     🔍 [连接检查] {from_id[:8]}... -> {to_id[:8]}... (from_mapped:{from_mapped}, to_mapped:{to_mapped})")
                
                if from_mapped and to_mapped:
                    new_from_id = node_id_mapping[from_id]
                    new_to_id = node_id_mapping[to_id]
                    
                    logger.info(f"     ✅ [连接复制] {from_id[:8]}... -> {to_id[:8]}... 映射为 {new_from_id} -> {new_to_id}")
                    
                    await self.db.execute("""
                        INSERT INTO node_connection (
                            from_node_id, to_node_id, workflow_id,
                            connection_type, condition_config, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, new_from_id, new_to_id,
                         new_workflow_id, conn.get('connection_type', 'normal'),
                         conn.get('condition_config'), now_utc())
                    subworkflow_connections_copied += 1
                else:
                    logger.warning(f"     ❌ [连接跳过] {from_id[:8]}... -> {to_id[:8]}... (from_mapped:{from_mapped}, to_mapped:{to_mapped})")
                    if not from_mapped:
                        logger.warning(f"       缺失from节点映射: {from_id}")
                    if not to_mapped:
                        logger.warning(f"       缺失to节点映射: {to_id}")
            
            # 🔧 关键修复：处理递归展开的跨边界连接
            logger.info(f"     🔗 [跨边界连接] 开始处理候选项 {tree_candidate['node_name']} 的跨边界连接")
            
            # 获取当前候选项在新工作流中的入口和出口节点
            business_nodes = workflow_structure['business_nodes']
            entry_points = workflow_structure['entry_points'] or (business_nodes[:1] if business_nodes else [])
            exit_points = workflow_structure['exit_points'] or (business_nodes[-1:] if business_nodes else [])
            
            logger.info(f"       - 业务节点数: {len(business_nodes)}")
            logger.info(f"       - 入口点数: {len(entry_points)}")
            logger.info(f"       - 出口点数: {len(exit_points)}")
            
            # 🔧 关键修复：检查这个候选项是否被递归展开了
            # 如果当前候选项的业务节点在其他候选项中被进一步替换，则使用展开后的节点
            final_entry_new_ids = []
            final_exit_new_ids = []
            
            for entry in entry_points:
                original_entry_id = entry['node_id']
                entry_node_name = entry['name']
                
                # 检查这个入口节点是否在其他候选项中被递归展开
                expanded_entry_ids = []
                for other_original_node_id, other_candidate in tree_mapping.items():
                    if other_candidate != tree_candidate:
                        # 检查其他候选项是否是当前入口节点的展开
                        if other_candidate.get('original_node_id') == original_entry_id:
                            logger.info(f"       🔍 [递归检测] 入口节点 {entry_node_name} 被递归展开为 {other_candidate['node_name']}")
                            
                            # 获取展开后的子工作流结构
                            other_tree_node = other_candidate.get('tree_node')
                            if other_tree_node:
                                other_structure = await self._analyze_subworkflow_structure_from_tree(
                                    other_tree_node, entry['position_x'], entry['position_y']
                                )
                                
                                # 使用展开后的入口节点
                                for expanded_entry in other_structure['entry_points']:
                                    expanded_entry_id = expanded_entry['node_id']
                                    # 优先使用复合key
                                    composite_key = f"{expanded_entry_id}@{other_candidate['node_name']}"
                                    
                                    if composite_key in node_id_mapping:
                                        expanded_entry_ids.append(node_id_mapping[composite_key])
                                        logger.info(f"       ✅ [递归入口] 找到展开入口: {expanded_entry['name']} -> {node_id_mapping[composite_key]}")
                                    elif expanded_entry_id in node_id_mapping:
                                        expanded_entry_ids.append(node_id_mapping[expanded_entry_id])
                                        logger.info(f"       ✅ [递归入口] 找到展开入口: {expanded_entry['name']} -> {node_id_mapping[expanded_entry_id]}")
                
                # 如果找到了递归展开的节点，使用展开后的节点
                if expanded_entry_ids:
                    final_entry_new_ids.extend(expanded_entry_ids)
                    logger.info(f"       🔄 [使用展开入口] {entry_node_name} -> {len(expanded_entry_ids)}个展开入口")
                else:
                    # 没有递归展开，使用原始节点
                    composite_key = f"{original_entry_id}@{tree_candidate['node_name']}"
                    
                    new_entry_id = None
                    if composite_key in node_id_mapping:
                        new_entry_id = node_id_mapping[composite_key]
                        logger.info(f"       📍 [原始入口] 找到复合key: {composite_key} -> {new_entry_id}")
                    elif original_entry_id in node_id_mapping:
                        new_entry_id = node_id_mapping[original_entry_id]
                        logger.info(f"       📍 [原始入口] 找到原始key: {original_entry_id} -> {new_entry_id}")
                    
                    if new_entry_id:
                        final_entry_new_ids.append(new_entry_id)
                    else:
                        logger.warning(f"       ❌ [入口映射] 未找到映射: {original_entry_id}")
            
            # 同样处理出口点
            for exit_point in exit_points:
                original_exit_id = exit_point['node_id']
                exit_node_name = exit_point['name']
                
                # 检查这个出口节点是否在其他候选项中被递归展开
                expanded_exit_ids = []
                for other_original_node_id, other_candidate in tree_mapping.items():
                    if other_candidate != tree_candidate:
                        # 检查其他候选项是否是当前出口节点的展开
                        if other_candidate.get('original_node_id') == original_exit_id:
                            logger.info(f"       🔍 [递归检测] 出口节点 {exit_node_name} 被递归展开为 {other_candidate['node_name']}")
                            
                            # 获取展开后的子工作流结构
                            other_tree_node = other_candidate.get('tree_node')
                            if other_tree_node:
                                other_structure = await self._analyze_subworkflow_structure_from_tree(
                                    other_tree_node, exit_point['position_x'], exit_point['position_y']
                                )
                                
                                # 使用展开后的出口节点
                                for expanded_exit in other_structure['exit_points']:
                                    expanded_exit_id = expanded_exit['node_id']
                                    # 优先使用复合key
                                    composite_key = f"{expanded_exit_id}@{other_candidate['node_name']}"
                                    
                                    if composite_key in node_id_mapping:
                                        expanded_exit_ids.append(node_id_mapping[composite_key])
                                        logger.info(f"       ✅ [递归出口] 找到展开出口: {expanded_exit['name']} -> {node_id_mapping[composite_key]}")
                                    elif expanded_exit_id in node_id_mapping:
                                        expanded_exit_ids.append(node_id_mapping[expanded_exit_id])
                                        logger.info(f"       ✅ [递归出口] 找到展开出口: {expanded_exit['name']} -> {node_id_mapping[expanded_exit_id]}")
                
                # 如果找到了递归展开的节点，使用展开后的节点
                if expanded_exit_ids:
                    final_exit_new_ids.extend(expanded_exit_ids)
                    logger.info(f"       🔄 [使用展开出口] {exit_node_name} -> {len(expanded_exit_ids)}个展开出口")
                else:
                    # 没有递归展开，使用原始节点
                    composite_key = f"{original_exit_id}@{tree_candidate['node_name']}"
                    
                    new_exit_id = None
                    if composite_key in node_id_mapping:
                        new_exit_id = node_id_mapping[composite_key]
                        logger.info(f"       📍 [原始出口] 找到复合key: {composite_key} -> {new_exit_id}")
                    elif original_exit_id in node_id_mapping:
                        new_exit_id = node_id_mapping[original_exit_id]
                        logger.info(f"       📍 [原始出口] 找到原始key: {original_exit_id} -> {new_exit_id}")
                    
                    if new_exit_id:
                        final_exit_new_ids.append(new_exit_id)
                    else:
                        logger.warning(f"       ❌ [出口映射] 未找到映射: {original_exit_id}")
            
            logger.info(f"       📊 [最终映射] 入口节点: {len(final_entry_new_ids)}个, 出口节点: {len(final_exit_new_ids)}个")
            
            # 重建上游连接 - 连接到递归展开后的入口节点
            upstream_count = 0
            for conn in parent_connections:
                if conn['to_node_id'] == original_node_id:
                    from_id = conn['from_node_id']
                    if from_id in node_id_mapping:
                        new_from_id = node_id_mapping[from_id]
                        
                        # 🔧 关键修复：连接到最终的入口节点（可能是递归展开后的节点）
                        for new_entry_id in final_entry_new_ids:
                            try:
                                await self.db.execute("""
                                    INSERT INTO node_connection (
                                        from_node_id, to_node_id, workflow_id,
                                        connection_type, condition_config, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                """, new_from_id, new_entry_id,
                                     new_workflow_id, conn.get('connection_type', 'normal'),
                                     conn.get('condition_config'), now_utc())
                                cross_boundary_connections_created += 1
                                upstream_count += 1
                                logger.info(f"       ✅ [上游连接] {from_id[:8]}... -> {new_entry_id} (原连接: {conn['from_node_id'][:8]}... -> {original_node_id[:8]}...)")
                            except Exception as e:
                                logger.error(f"       ❌ [上游连接] 创建失败: {e}")
            
            # 重建下游连接 - 连接到递归展开后的出口节点
            downstream_count = 0
            for conn in parent_connections:
                if conn['from_node_id'] == original_node_id:
                    to_id = conn['to_node_id']
                    if to_id in node_id_mapping:
                        new_to_id = node_id_mapping[to_id]
                        
                        # 🔧 关键修复：从最终的出口节点连接（可能是递归展开后的节点）
                        for new_exit_id in final_exit_new_ids:
                            try:
                                await self.db.execute("""
                                    INSERT INTO node_connection (
                                        from_node_id, to_node_id, workflow_id,
                                        connection_type, condition_config, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                """, new_exit_id, new_to_id,
                                     new_workflow_id, conn.get('connection_type', 'normal'),
                                     conn.get('condition_config'), now_utc())
                                cross_boundary_connections_created += 1
                                downstream_count += 1
                                logger.info(f"       ✅ [下游连接] {new_exit_id} -> {to_id[:8]}... (原连接: {original_node_id[:8]}... -> {conn['to_node_id'][:8]}...)")
                            except Exception as e:
                                logger.error(f"       ❌ [下游连接] 创建失败: {e}")
            
            # 将当前候选项的出入口点加入到全局映射中，供替换节点间连接使用
            replaced_to_entry_mapping[original_node_id] = final_entry_new_ids
            replaced_to_exit_mapping[original_node_id] = final_exit_new_ids
            
            logger.info(f"     📊 [映射收集] {tree_candidate['node_name']}: {len(final_entry_new_ids)}个入口点, {len(final_exit_new_ids)}个出口点")
            
            logger.info(f"     📊 [跨边界统计] 上游连接: {upstream_count}个, 下游连接: {downstream_count}个")
        
        # 4. 🔧 新增：重建替换节点之间的连接
        logger.info(f"🔗 [替换连接] 重建替换节点之间的连接...")
        replaced_connections_created = 0
        
        for conn in parent_connections:
            from_id, to_id = conn['from_node_id'], conn['to_node_id']
            
            # 只处理替换节点之间的连接
            if from_id in replaced_node_ids and to_id in replaced_node_ids:
                logger.info(f"   🔗 [替换连接] 处理: {from_id} -> {to_id}")
                
                # 获取from节点的出口点和to节点的入口点
                from_exit_points = replaced_to_exit_mapping.get(from_id, [])
                to_entry_points = replaced_to_entry_mapping.get(to_id, [])
                
                logger.info(f"     - From出口点数: {len(from_exit_points)}, To入口点数: {len(to_entry_points)}")
                
                # 建立出口点到入口点的连接
                for from_exit_id in from_exit_points:
                    for to_entry_id in to_entry_points:
                        await self.db.execute("""
                            INSERT INTO node_connection (
                                from_node_id, to_node_id, workflow_id,
                                connection_type, condition_config, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, from_exit_id, to_entry_id,
                             new_workflow_id, conn.get('connection_type', 'normal'),
                             conn.get('condition_config'), now_utc())
                        replaced_connections_created += 1
                        logger.info(f"     ✅ 创建替换连接: {from_exit_id} -> {to_entry_id}")
        
        logger.info(f"✅ [Tree连接] 重建完成: 父连接{parent_connections_copied}, 子连接{subworkflow_connections_copied}, 跨边界{cross_boundary_connections_created}, 替换连接{replaced_connections_created}")
        
        return {
            "parent_connections_copied": parent_connections_copied,
            "subworkflow_connections_copied": subworkflow_connections_copied,
            "cross_boundary_connections_created": cross_boundary_connections_created,
            "replaced_connections_created": replaced_connections_created,
            "connections_count": parent_connections_copied + subworkflow_connections_copied + cross_boundary_connections_created + replaced_connections_created
        }
    
    async def _get_best_workflow_id_by_base(self, workflow_base_id: str) -> Optional[str]:
        """智能选择最佳的workflow_id - 优先当前版本，如果当前版本为空则选择有节点的版本"""
        try:
            logger.info(f"🔍 [智能版本选择] 为基础ID选择最佳版本: {workflow_base_id}")
            
            # 首先尝试获取当前版本
            current_version = await self.db.fetch_one("""
                SELECT w.workflow_id, w.version, COUNT(n.node_id) as node_count
                FROM workflow w
                LEFT JOIN node n ON w.workflow_id = n.workflow_id AND n.is_deleted = FALSE
                WHERE w.workflow_base_id = %s AND w.is_current_version = TRUE
                GROUP BY w.workflow_id, w.version
            """, workflow_base_id)
            
            if current_version:
                current_node_count = current_version['node_count'] or 0
                logger.info(f"✅ [当前版本] 找到当前版本: {current_version['workflow_id']}")
                logger.info(f"   - 版本: {current_version['version']}")
                logger.info(f"   - 节点数: {current_node_count}")
                
                if current_node_count > 0:
                    logger.info(f"✅ [选择当前版本] 当前版本有节点，使用当前版本")
                    return current_version['workflow_id']
                else:
                    logger.warning(f"⚠️ [当前版本为空] 当前版本无节点，寻找有节点的版本")
            
            # 如果当前版本为空或不存在，查找有节点的最新版本
            best_version = await self.db.fetch_one("""
                SELECT w.workflow_id, w.version, w.is_current_version, COUNT(n.node_id) as node_count
                FROM workflow w
                LEFT JOIN node n ON w.workflow_id = n.workflow_id AND n.is_deleted = FALSE
                WHERE w.workflow_base_id = %s AND w.is_deleted = FALSE
                GROUP BY w.workflow_id, w.version, w.is_current_version
                HAVING node_count > 0
                ORDER BY w.version DESC, w.created_at DESC
                LIMIT 1
            """, workflow_base_id)
            
            if best_version:
                best_node_count = best_version['node_count'] or 0
                is_current = "✓当前" if best_version['is_current_version'] else "历史"
                logger.info(f"🔧 [找到有节点版本] {is_current}版本: {best_version['workflow_id']}")
                logger.info(f"   - 版本: {best_version['version']}")
                logger.info(f"   - 节点数: {best_node_count}")
                logger.info(f"   - 将使用此版本进行合并")
                return best_version['workflow_id']
            
            logger.error(f"❌ [无可用版本] 找不到任何有节点的工作流版本")
            return None
            
        except Exception as e:
            logger.error(f"❌ [智能版本选择] 选择失败: {e}")
            return None
            
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
    
    async def _debug_workflow_versions(self, workflow_base_id: str, stage: str):
        """调试：分析工作流的所有版本及其节点情况"""
        try:
            logger.info(f"🔍 [版本分析-{stage}] 分析工作流基础ID: {workflow_base_id}")
            
            # 查询该workflow_base_id下的所有版本
            all_versions = await self.db.fetch_all("""
                SELECT w.workflow_id, w.workflow_base_id, w.name, w.description, w.version,
                       w.creator_id, w.is_current_version, w.created_at, w.is_deleted,
                       COUNT(n.node_id) as node_count
                FROM workflow w
                LEFT JOIN node n ON w.workflow_id = n.workflow_id AND n.is_deleted = FALSE
                WHERE w.workflow_base_id = %s
                GROUP BY w.workflow_id, w.workflow_base_id, w.name, w.description, w.version,
                         w.creator_id, w.is_current_version, w.created_at, w.is_deleted
                ORDER BY w.version DESC, w.created_at DESC
            """, workflow_base_id)
            
            logger.info(f"📊 [版本统计] 找到 {len(all_versions)} 个版本:")
            
            current_version = None
            best_version_with_nodes = None
            
            for version in all_versions:
                is_current = "✓当前" if version['is_current_version'] else ""
                is_deleted = "已删除" if version['is_deleted'] else "活跃"
                node_count = version['node_count'] or 0
                
                logger.info(f"   版本 {version['version']}: {node_count}个节点 {is_current} {is_deleted}")
                logger.info(f"     - 工作流ID: {version['workflow_id']}")
                logger.info(f"     - 名称: {version['name']}")
                logger.info(f"     - 创建时间: {version['created_at']}")
                
                if version['is_current_version']:
                    current_version = version
                
                # 找到第一个有节点的版本作为最佳候选
                if node_count > 0 and not best_version_with_nodes:
                    best_version_with_nodes = version
            
            # 分析结果
            if current_version:
                current_node_count = current_version['node_count'] or 0
                logger.info(f"✅ [当前版本分析] 当前版本有 {current_node_count} 个节点")
                
                if current_node_count == 0:
                    logger.warning(f"⚠️ [版本问题] 当前版本为空工作流!")
                    
                    if best_version_with_nodes:
                        logger.info(f"🔧 [建议] 发现有节点的版本:")
                        logger.info(f"   - 版本 {best_version_with_nodes['version']}: {best_version_with_nodes['node_count']}个节点")
                        logger.info(f"   - 工作流ID: {best_version_with_nodes['workflow_id']}")
                        logger.info(f"   - 可以考虑使用此版本进行合并")
                    else:
                        logger.error(f"❌ [严重问题] 所有版本都没有节点!")
            else:
                logger.error(f"❌ [版本错误] 找不到当前版本!")
            
            return {
                'current_version': current_version,
                'best_version_with_nodes': best_version_with_nodes,
                'all_versions': all_versions
            }
            
        except Exception as e:
            logger.error(f"❌ [版本分析] 分析失败: {e}")
            return None
    
    async def _debug_current_workflow_state(self, workflow_id: str, stage: str):
        """调试：显示当前工作流状态"""
        try:
            logger.info(f"🔍 [工作流状态-{stage}] 分析工作流: {workflow_id}")
            
            # 查询工作流基本信息
            workflow_info = await self.db.fetch_one("""
                SELECT w.workflow_id, w.workflow_base_id, w.name, w.description, w.version,
                       w.creator_id, w.is_current_version, w.created_at
                FROM workflow w
                WHERE w.workflow_id = %s
            """, workflow_id)
            
            if workflow_info:
                logger.info(f"   📋 [工作流信息]")
                logger.info(f"     - 工作流ID: {workflow_info['workflow_id']}")
                logger.info(f"     - 工作流基础ID: {workflow_info['workflow_base_id']}")
                logger.info(f"     - 名称: {workflow_info['name']}")
                logger.info(f"     - 描述: {workflow_info['description']}")
                logger.info(f"     - 版本: {workflow_info['version']}")
                logger.info(f"     - 是否当前版本: {workflow_info['is_current_version']}")
                logger.info(f"     - 创建时间: {workflow_info['created_at']}")
            else:
                logger.warning(f"   ❌ 找不到工作流信息: {workflow_id}")
                return
            
            # 查询所有节点
            nodes = await self.db.fetch_all("""
                SELECT n.node_id, n.node_base_id, n.name, n.type, n.task_description,
                       n.position_x, n.position_y, n.version, n.is_current_version,
                       n.created_at, n.is_deleted
                FROM node n
                WHERE n.workflow_id = %s
                ORDER BY n.position_x, n.position_y, n.name
            """, workflow_id)
            
            logger.info(f"   📊 [节点统计] 总节点数: {len(nodes)}")
            
            # 按类型分类节点
            nodes_by_type = {}
            for node in nodes:
                node_type = node['type']
                if node_type not in nodes_by_type:
                    nodes_by_type[node_type] = []
                nodes_by_type[node_type].append(node)
            
            for node_type, type_nodes in nodes_by_type.items():
                logger.info(f"     - {node_type}类型: {len(type_nodes)}个")
            
            # 详细显示每个节点
            logger.info(f"   📋 [节点详情]")
            for i, node in enumerate(nodes):
                status_info = f"v{node['version']}"
                if node['is_current_version']:
                    status_info += " (当前版本)"
                if node['is_deleted']:
                    status_info += " (已删除)"
                    
                logger.info(f"     节点 {i+1}: {node['name']} ({node['type']})")
                logger.info(f"       - 节点ID: {node['node_id']}")
                logger.info(f"       - 节点基础ID: {node['node_base_id']}")
                logger.info(f"       - 位置: ({node['position_x']}, {node['position_y']})")
                logger.info(f"       - 状态: {status_info}")
                if node['task_description']:
                    logger.info(f"       - 描述: {node['task_description']}")
            
            # 查询连接
            connections = await self.db.fetch_all("""
                SELECT nc.from_node_id, nc.to_node_id, nc.connection_type, nc.condition_config,
                       from_n.name as from_node_name, from_n.type as from_node_type,
                       to_n.name as to_node_name, to_n.type as to_node_type
                FROM node_connection nc
                JOIN node from_n ON nc.from_node_id = from_n.node_id
                JOIN node to_n ON nc.to_node_id = to_n.node_id
                WHERE nc.workflow_id = %s
                ORDER BY from_n.name, to_n.name
            """, workflow_id)
            
            logger.info(f"   🔗 [连接统计] 总连接数: {len(connections)}")
            logger.info(f"   📋 [连接详情]")
            for i, conn in enumerate(connections):
                conn_type = conn.get('connection_type', 'normal')
                condition = conn.get('condition_config', '')
                condition_info = f" (条件: {condition})" if condition else ""
                
                logger.info(f"     连接 {i+1}: {conn['from_node_name']} -> {conn['to_node_name']} (类型: {conn_type}){condition_info}")
                logger.info(f"       - 从节点: {conn['from_node_id']} ({conn['from_node_type']})")
                logger.info(f"       - 到节点: {conn['to_node_id']} ({conn['to_node_type']})")
            
            if not connections:
                logger.info(f"     ⚠️ 该工作流暂无连接")
                
        except Exception as e:
            logger.error(f"❌ [工作流状态调试] 分析失败: {e}")
    
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
                # 🔧 修复：改进连接查询，确保获取子工作流的所有连接
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
                    ORDER BY from_n.position_x, from_n.position_y, to_n.position_x, to_n.position_y
                """, sub_workflow_id)
                
                # 🔧 调试：显示所有找到的连接
                logger.info(f"   🔗 [连接详情] 子工作流连接分析:")
                for i, conn in enumerate(all_connections):
                    logger.info(f"     连接{i+1}: {conn['from_node_name']}({conn['from_node_type']}) -> {conn['to_node_name']}({conn['to_node_type']})")
                    logger.info(f"       from_node_id: {conn['from_node_id']}")
                    logger.info(f"       to_node_id: {conn['to_node_id']}")
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

    async def _create_unified_recursive_workflow_record(self, parent_workflow_base_id: str,
                                                      new_workflow_base_id: uuid.UUID,
                                                      total_candidates: int,
                                                      creator_id: uuid.UUID) -> Dict[str, Any]:
        """创建统一递归合并的工作流记录"""
        try:
            # 获取父工作流名称
            parent_workflow = await self.db.fetch_one("""
                SELECT name FROM workflow 
                WHERE workflow_base_id = %s AND is_current_version = TRUE
            """, parent_workflow_base_id)
            
            parent_name = parent_workflow['name'] if parent_workflow else "Unknown_Workflow"
            
            # 生成递归合并的工作流名称
            new_workflow_id = uuid.uuid4()
            merged_name = f"{parent_name}_递归合并_{total_candidates}项"
            merged_description = f"递归合并{total_candidates}个subdivision到统一模板，基于{parent_name}"
            
            await self.db.execute("""
                INSERT INTO workflow (
                    workflow_id, workflow_base_id, name, description, 
                    creator_id, is_current_version, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, new_workflow_id, new_workflow_base_id, merged_name, merged_description,
                 creator_id, True, now_utc())
            
            logger.info(f"✅ [统一工作流记录] 创建递归合并工作流: {merged_name}")
            
            return {
                "workflow_id": str(new_workflow_id),
                "workflow_base_id": str(new_workflow_base_id),
                "name": merged_name,
                "description": merged_description
            }
            
        except Exception as e:
            logger.error(f"❌ [统一工作流记录] 创建递归合并工作流失败: {e}")
            raise

    async def _execute_unified_recursive_node_replacement(self, parent_workflow_id: str,
                                                        new_workflow_id: uuid.UUID, 
                                                        new_workflow_base_id: uuid.UUID,
                                                        tree_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """执行统一的递归节点替换合并 - 一次性处理所有候选项"""
        try:
            logger.info(f"🔄 [统一递归替换] 开始处理 {len(tree_candidates)} 个候选项")
            
            # 1. 收集需要替换的节点ID
            nodes_to_replace = set()
            tree_mapping = {}  # original_node_id -> tree_candidate
            
            logger.info(f"🔍 [候选项分析] 分析 {len(tree_candidates)} 个tree候选项:")
            for candidate in tree_candidates:
                original_node_id = candidate.get('original_node_id')
                subdivision_id = candidate.get('subdivision_id')
                node_name = candidate.get('node_name', 'Unknown')
                
                logger.info(f"     候选项: {node_name} (深度: {candidate.get('depth', 0)})")
                logger.info(f"       - original_node_id: {original_node_id}")
                logger.info(f"       - subdivision_id: {subdivision_id}")
                
                # 如果tree中有original_node_id，直接使用
                if original_node_id:
                    nodes_to_replace.add(original_node_id)
                    tree_mapping[original_node_id] = candidate
                    logger.info(f"   🔧 将替换节点: {node_name} (node_id: {original_node_id})")
                # 否则，回退到subdivision查询
                elif subdivision_id:
                    logger.info(f"   🔍 tree数据不完整，查询subdivision: {subdivision_id}")
                    original_node_info = await self._get_original_node_info(subdivision_id)
                    if original_node_info:
                        actual_node_id = original_node_info['node_id']
                        nodes_to_replace.add(actual_node_id)
                        # 将subdivision查询结果补充到candidate中
                        enhanced_candidate = candidate.copy()
                        enhanced_candidate.update({
                            'original_node_id': actual_node_id,
                            'original_task_id': original_node_info.get('original_task_id'),
                            'original_node_position': {
                                'x': original_node_info.get('position_x', 0),
                                'y': original_node_info.get('position_y', 0)
                            },
                            'original_node_info': original_node_info
                        })
                        tree_mapping[actual_node_id] = enhanced_candidate
                        logger.info(f"   🔧 将替换节点: {original_node_info['name']} (node_id: {actual_node_id})")
                    else:
                        logger.warning(f"   ❌ 无法获取subdivision的原始节点信息: {subdivision_id}")
                else:
                    logger.warning(f"   ⚠️ 候选项缺少识别信息: {node_name}")
            
            logger.info(f"🔄 [统一替换] 将替换 {len(nodes_to_replace)} 个节点")
            
            # 2. 复制父工作流的保留节点（排除要替换的节点）
            node_id_mapping = await self._copy_preserved_nodes_simple(
                parent_workflow_id, new_workflow_id, new_workflow_base_id, nodes_to_replace
            )
            
            # 3. 执行统一的递归节点替换
            replacement_stats = await self._replace_nodes_with_recursive_expansion(
                new_workflow_id, new_workflow_base_id, tree_mapping, node_id_mapping
            )
            
            # 4. 重建连接 - 🔧 统一递归合并的连接重建  
            connection_stats = await self._rebuild_unified_recursive_connections(
                parent_workflow_id, new_workflow_id, tree_mapping, node_id_mapping
            )
            
            logger.info(f"✅ [统一递归替换] 完成: 替换{replacement_stats['nodes_replaced']}节点, 重建{connection_stats['connections_count']}连接")
            
            return {
                **replacement_stats,
                **connection_stats
            }
            
        except Exception as e:
            logger.error(f"❌ [统一递归替换] 执行失败: {e}")
            raise

    async def _replace_nodes_with_recursive_expansion(self, new_workflow_id: uuid.UUID, 
                                                    new_workflow_base_id: uuid.UUID,
                                                    tree_mapping: Dict[str, Dict], 
                                                    node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """递归展开替换节点 - 修复版：真正理解递归替换的含义"""
        replaced_nodes = 0
        
        logger.info(f"🔄 [真递归理解] 重新理解递归替换")
        logger.info(f"📊 [候选分析] 待替换候选项: {len(tree_mapping)}")
        
        # 🔧 关键理解：每个候选项代表一个subdivision，即一个节点被子工作流替换
        # 真正的递归是：如果子工作流中的节点也被subdivision，那么继续展开
        
        for original_node_id, tree_candidate in tree_mapping.items():
            logger.info(f"🔄 [候选项处理] 处理: {tree_candidate['node_name']} (深度: {tree_candidate.get('depth', 0)})")
            logger.info(f"   subdivision_id: {tree_candidate.get('subdivision_id')}")
            logger.info(f"   workflow_instance_id: {tree_candidate.get('workflow_instance_id')}")
            
            # 获取子工作流结构
            tree_node = tree_candidate.get('tree_node')
            if not tree_node:
                logger.warning(f"⚠️ tree_candidate中没有tree_node引用")
                continue
            
            # 从tree中获取原始节点位置信息    
            original_position = tree_candidate.get('original_node_position', {})
            center_x = original_position.get('x', 0)
            center_y = original_position.get('y', 0)
            logger.info(f"   📍 [原始位置] x: {center_x}, y: {center_y}")
            
            # 获取子工作流的基础结构
            base_structure = await self._analyze_subworkflow_structure_from_tree(
                tree_node, center_x, center_y
            )
            
            logger.info(f"   📊 [子工作流基础] 业务节点: {len(base_structure['business_nodes'])}个")
            for i, node in enumerate(base_structure['business_nodes']):
                logger.info(f"     业务节点{i+1}: {node['name']} (ID: {node['node_id'][:8]}...)")
            
            # 🔧 关键递归逻辑：检查子工作流的业务节点是否还需要进一步展开
            # 传递所有tree_candidates作为参数，而不是tree_mapping
            all_tree_candidates = list(tree_mapping.values())
            final_business_nodes = await self._recursive_expand_business_nodes(
                base_structure['business_nodes'], all_tree_candidates, tree_candidate['node_name']
            )
            
            logger.info(f"   📊 [递归展开后] 最终业务节点: {len(final_business_nodes)}个")
            for i, node in enumerate(final_business_nodes):
                logger.info(f"     最终节点{i+1}: {node['name']} (ID: {node.get('node_id', 'NEW')[:8] if node.get('node_id') else 'NEW'}...)")
            
            # 复制最终展开的业务节点
            for node in final_business_nodes:
                new_node_id = uuid.uuid4()
                new_node_base_id = uuid.uuid4()
                
                # 🔧 使用复合key避免映射冲突
                composite_key = f"{node.get('node_id', new_node_id)}@{tree_candidate['node_name']}"
                node_id_mapping[composite_key] = new_node_id
                
                # 向后兼容映射
                if node.get('node_id') and node['node_id'] not in node_id_mapping:
                    node_id_mapping[node['node_id']] = new_node_id
                else:
                    logger.info(f"   🔧 节点ID处理: 使用复合key: {composite_key}")
                
                logger.info(f"   📄 复制最终节点: {node['name']} -> 新ID: {new_node_id}")
                
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
        
        logger.info(f"✅ [真递归展开] 完成真正的递归展开，共替换 {replaced_nodes} 个节点")
        return {"nodes_replaced": replaced_nodes}
    
    async def _recursive_expand_business_nodes(self, business_nodes: List[Dict], 
                                             all_tree_candidates: List[Dict[str, Any]],
                                             parent_name: str) -> List[Dict]:
        """递归展开业务节点 - 正确匹配子工作流节点与subdivision"""
        logger.info(f"   🔍 [递归展开检查] 检查 {len(business_nodes)} 个业务节点是否需要进一步展开")
        logger.info(f"   📋 [候选项] 可用的tree候选项: {len(all_tree_candidates)}个")
        
        # 🔧 关键修复：构建subdivision_id到子工作流实例的映射
        subdivision_to_instance = {}
        for candidate in all_tree_candidates:
            tree_node = candidate.get('tree_node')
            if tree_node and tree_node.workflow_instance_id:
                subdivision_id = candidate.get('subdivision_id')
                subdivision_to_instance[subdivision_id] = tree_node.workflow_instance_id
                logger.info(f"     映射: subdivision {subdivision_id[:8]}... -> instance {tree_node.workflow_instance_id[:8]}...")
        
        final_nodes = []
        
        for node in business_nodes:
            node_id = node['node_id']
            node_name = node['name']
            logger.info(f"     🔍 [节点检查] 检查节点: {node_name} (ID: {node_id[:8]}...)")
            
            # 🔧 关键修复：通过task_subdivision表查找这个节点是否被subdivision
            needs_expansion = False
            matching_candidate = None
            
            # 查找以这个节点为原始节点的subdivision
            try:
                subdivision_record = await self.db.fetch_one("""
                    SELECT ts.subdivision_id, ts.original_task_id,
                           ti.node_instance_id, ni.node_id as original_node_id
                    FROM task_subdivision ts
                    JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
                    JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
                    WHERE ni.node_id = %s AND ts.is_deleted = FALSE
                """, node_id)
                
                if subdivision_record:
                    subdivision_id = str(subdivision_record['subdivision_id'])
                    logger.info(f"       🔍 [发现subdivision] 节点 {node_name} 有subdivision: {subdivision_id[:8]}...")
                    
                    # 在tree候选项中找到对应的candidate
                    for candidate in all_tree_candidates:
                        if candidate.get('subdivision_id') == subdivision_id:
                            logger.info(f"       🔄 [发现匹配] 节点 {node_name} 需要展开为 {candidate['node_name']}")
                            needs_expansion = True
                            matching_candidate = candidate
                            break
                
            except Exception as e:
                logger.warning(f"       ⚠️ [查询失败] 查找subdivision失败: {e}")
            
            if needs_expansion and matching_candidate:
                logger.info(f"       🔧 [递归展开] 展开节点 {node_name} -> {matching_candidate['node_name']}")
                
                # 获取匹配候选项的子工作流结构
                tree_node = matching_candidate.get('tree_node')
                if tree_node:
                    # 递归获取子工作流结构
                    sub_structure = await self._analyze_subworkflow_structure_from_tree(
                        tree_node, node['position_x'], node['position_y']
                    )
                    
                    # 递归展开子工作流的业务节点
                    expanded_sub_nodes = await self._recursive_expand_business_nodes(
                        sub_structure['business_nodes'], all_tree_candidates, f"{parent_name}->{matching_candidate['node_name']}"
                    )
                    
                    logger.info(f"       📋 [展开结果] {node_name} 展开为 {len(expanded_sub_nodes)} 个节点")
                    final_nodes.extend(expanded_sub_nodes)
                else:
                    logger.warning(f"       ⚠️ [展开失败] 匹配候选项缺少tree_node")
                    final_nodes.append(node)
            else:
                logger.info(f"       ✅ [保持不变] 节点 {node_name} 无需展开")
                final_nodes.append(node)
        
        logger.info(f"   📊 [递归展开结果] 原始 {len(business_nodes)} 个节点 -> 最终 {len(final_nodes)} 个节点")
        return final_nodes

    async def _fully_recursive_analyze_subworkflow(self, tree_node: WorkflowTemplateNode, 
                                                  center_x: int, center_y: int,
                                                  tree_mapping: Dict[str, Dict]) -> Dict[str, Any]:
        """完全递归分析子工作流结构 - 简化的真正递归展开"""
        try:
            logger.info(f"🔍 [完全递归分析] 分析节点: {tree_node.workflow_name}")
            
            # 🔧 简化策略：直接使用基础分析，真正的递归展开由上层统一处理
            # 这样避免复杂的嵌套递归逻辑，让每个子工作流只处理自己的直接结构
            base_structure = await self._analyze_subworkflow_structure_from_tree(
                tree_node, center_x, center_y
            )
            
            logger.info(f"   📊 [基础结构] 业务节点数: {len(base_structure['business_nodes'])}")
            logger.info(f"      - 入口点: {len(base_structure['entry_points'])}个")  
            logger.info(f"      - 出口点: {len(base_structure['exit_points'])}个")
            logger.info(f"      - 业务连接: {len(base_structure['business_connections'])}个")
            
            return base_structure
            
        except Exception as e:
            logger.error(f"❌ [完全递归分析] 分析失败: {e}")
            # 失败时返回基础结构
            return await self._analyze_subworkflow_structure_from_tree(tree_node, center_x, center_y)

    async def _rebuild_unified_recursive_connections(self, parent_workflow_id: str, new_workflow_id: uuid.UUID,
                                                   tree_mapping: Dict[str, Dict],
                                                   node_id_mapping: Dict[str, uuid.UUID]) -> Dict[str, int]:
        """统一递归合并的连接重建 - 简化版本，重用现有逻辑"""
        logger.info(f"🔗 [统一递归连接] 开始重建连接")
        logger.info(f"   - 父工作流ID: {parent_workflow_id}")
        logger.info(f"   - 新工作流ID: {new_workflow_id}")
        logger.info(f"   - 节点映射数量: {len(node_id_mapping)}")
        logger.info(f"   - 递归候选项数量: {len(tree_mapping)}")
        
        # 🔧 重用现有的连接重建逻辑
        # 统一递归合并的连接处理本质上和分层合并相同，只是规模更大
        return await self._rebuild_connections_from_tree_data(
            parent_workflow_id, new_workflow_id, tree_mapping, node_id_mapping
        )

    async def _get_child_subdivisions(self, workflow_instance_id: str) -> List[Dict[str, Any]]:
        """获取工作流实例的子subdivision"""
        try:
            child_subdivisions = await self.db.fetch_all("""
                SELECT subdivision_id, sub_workflow_instance_id, sub_workflow_base_id,
                       task_title, subdivision_name, sub_workflow_status
                FROM workflow_subdivisions 
                WHERE root_workflow_instance_id = %s AND is_deleted = FALSE
            """, workflow_instance_id)
            
            return child_subdivisions if child_subdivisions else []
            
        except Exception as e:
            logger.error(f"获取子subdivision失败: {e}")
            return []

    async def _recursive_expand_subworkflow(self, base_structure: Dict[str, Any], 
                                          child_subdivisions: List[Dict[str, Any]],
                                          center_x: int, center_y: int) -> Dict[str, Any]:
        """递归展开子工作流结构"""
        logger.info(f"🔄 [递归展开子工作流] 处理 {len(child_subdivisions)} 个子subdivision")
        
        # 这里应该递归处理每个child_subdivision
        # 但为了简化，我们暂时直接返回基础结构
        # 在实际实现中，这里应该递归调用类似的展开逻辑
        
        return base_structure