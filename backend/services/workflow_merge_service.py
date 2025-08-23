"""
工作流合并服务
Workflow Merge Service

处理工作流模板间的合并操作，包括节点替换、连接重构和新工作流生成
"""

import uuid
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from datetime import datetime

from ..repositories.base import BaseRepository
from ..repositories.workflow.workflow_repository import WorkflowRepository
from ..repositories.node.node_repository import NodeRepository
from ..models.workflow import WorkflowCreate
from ..models.node import NodeCreate, NodeType
from ..utils.helpers import now_utc


class WorkflowMergeService:
    """工作流合并服务"""
    
    def __init__(self):
        self.db = BaseRepository("workflow_merge").db
        self.workflow_repo = WorkflowRepository()
        self.node_repo = NodeRepository()
    
    async def preview_workflow_merge(
        self, 
        parent_workflow_id: uuid.UUID,
        merge_candidates: List[Dict[str, Any]],
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        预览工作流合并结果
        
        Args:
            parent_workflow_id: 父工作流基础ID
            merge_candidates: 合并候选列表
            user_id: 用户ID
            
        Returns:
            合并预览数据
        """
        try:
            logger.info(f"🔍 预览工作流合并: 父工作流={parent_workflow_id}, 候选数={len(merge_candidates)}")
            
            # 获取父工作流详细信息
            parent_workflow = await self._get_workflow_structure(parent_workflow_id)
            if not parent_workflow:
                raise ValueError("父工作流不存在")
            
            # 分析每个合并候选
            merge_previews = []
            for candidate in merge_candidates:
                preview = await self._analyze_merge_candidate(
                    parent_workflow, candidate, user_id
                )
                merge_previews.append(preview)
            
            # 生成整体合并预览
            overall_preview = self._build_merge_preview(
                parent_workflow, merge_previews
            )
            
            logger.info(f"✅ 工作流合并预览完成: {len(merge_previews)} 个候选")
            
            return overall_preview
            
        except Exception as e:
            logger.error(f"❌ 预览工作流合并失败: {e}")
            raise
    
    async def execute_workflow_merge(
        self,
        parent_workflow_id: uuid.UUID,
        selected_merges: List[Dict[str, Any]],
        merge_config: Dict[str, Any],
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        执行工作流合并操作
        
        Args:
            parent_workflow_id: 父工作流基础ID
            selected_merges: 选中的合并操作列表
            merge_config: 合并配置
            user_id: 用户ID
            
        Returns:
            合并结果
        """
        try:
            logger.info(f"🔄 [MERGE-START] 开始执行工作流合并")
            logger.info(f"📋 [MERGE-PARAMS] 父工作流ID: {parent_workflow_id}")
            logger.info(f"📋 [MERGE-PARAMS] 合并操作数: {len(selected_merges)}")
            logger.info(f"📋 [MERGE-PARAMS] 用户ID: {user_id}")
            logger.info(f"📋 [MERGE-PARAMS] 合并配置: {merge_config}")
            
            for i, merge in enumerate(selected_merges):
                logger.info(f"📋 [MERGE-PARAMS] 合并操作 {i+1}: {merge}")
            
            # 获取父工作流结构
            logger.info(f"🔍 [STEP-1] 获取父工作流结构...")
            parent_workflow = await self._get_workflow_structure(parent_workflow_id)
            if not parent_workflow:
                logger.error(f"❌ [STEP-1-FAILED] 父工作流不存在: {parent_workflow_id}")
                return {
                    "success": False,
                    "message": f"工作流不存在",
                    "errors": [f"工作流ID {parent_workflow_id} 不存在或已被删除"],
                    "warnings": ["请检查工作流ID是否正确，或选择其他有效的工作流"]
                }
            
            logger.info(f"✅ [STEP-1-SUCCESS] 父工作流结构获取成功:")
            logger.info(f"   - 工作流名称: {parent_workflow['workflow']['name']}")
            logger.info(f"   - 节点数量: {len(parent_workflow['nodes'])}")
            logger.info(f"   - 连接数量: {len(parent_workflow['connections'])}")
            
            # 验证合并配置
            logger.info(f"🔍 [STEP-2] 验证合并配置...")
            validation_result = await self._validate_merge_operations(
                parent_workflow, selected_merges, user_id
            )
            
            if not validation_result["valid"]:
                logger.error(f"❌ [STEP-2-FAILED] 合并验证失败:")
                logger.error(f"   - 错误: {validation_result['errors']}")
                logger.error(f"   - 警告: {validation_result['warnings']}")
                return {
                    "success": False,
                    "message": "合并验证失败",
                    "errors": validation_result["errors"],
                    "warnings": validation_result["warnings"]
                }
            
            logger.info(f"✅ [STEP-2-SUCCESS] 合并验证通过")
            if validation_result["warnings"]:
                logger.warning(f"⚠️ [STEP-2-WARNINGS] 验证警告: {validation_result['warnings']}")
            
            # 执行合并操作
            logger.info(f"🚀 [STEP-3] 执行合并操作...")
            merge_result = await self._perform_merge(
                parent_workflow, selected_merges, merge_config, user_id
            )
            
            if merge_result.get("success"):
                logger.info(f"✅ [MERGE-SUCCESS] 工作流合并执行完成:")
                logger.info(f"   - 新工作流ID: {merge_result.get('new_workflow_id')}")
                logger.info(f"   - 新工作流名称: {merge_result.get('new_workflow_name')}")
                logger.info(f"   - 合并统计: {merge_result.get('merge_statistics')}")
            else:
                logger.error(f"❌ [MERGE-FAILED] 合并操作失败: {merge_result.get('message')}")
            
            return merge_result
            
        except Exception as e:
            logger.error(f"❌ [MERGE-EXCEPTION] 执行工作流合并异常: {e}")
            logger.error(f"❌ [MERGE-EXCEPTION] 异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"❌ [MERGE-EXCEPTION] 异常堆栈: {traceback.format_exc()}")
            raise
    
    async def _get_workflow_structure(self, workflow_base_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取工作流的完整结构信息"""
        try:
            logger.info(f"🔍 [GET-WORKFLOW-STRUCTURE] 获取工作流结构: {workflow_base_id}")
            
            # 获取工作流基本信息
            logger.info(f"   📋 查询工作流基本信息...")
            workflow_query = """
            SELECT 
                w.workflow_id,
                w.workflow_base_id,
                w.name,
                w.description,
                w.creator_id,
                w.version
            FROM workflow w
            WHERE w.workflow_base_id = %s
            AND w.is_current_version = TRUE
            AND w.is_deleted = FALSE
            """
            
            workflow = await self.db.fetch_one(workflow_query, workflow_base_id)
            if not workflow:
                logger.error(f"   ❌ 工作流不存在或无当前版本: {workflow_base_id}")
                return None
            
            logger.info(f"   ✅ 工作流基本信息获取成功:")
            logger.info(f"     - ID: {workflow['workflow_id']}")
            logger.info(f"     - 名称: {workflow['name']}")
            logger.info(f"     - 版本: {workflow['version']}")
            logger.info(f"     - 创建者: {workflow['creator_id']}")
            
            # 获取所有节点（基本信息，不包含processor）
            logger.info(f"   📋 查询工作流节点...")
            nodes_query = """
            SELECT 
                n.node_id,
                n.node_base_id,
                n.name,
                n.type,
                n.task_description,
                n.position_x,
                n.position_y
            FROM node n
            WHERE n.workflow_base_id = %s
            AND n.is_current_version = TRUE
            AND n.is_deleted = FALSE
            ORDER BY n.created_at
            """
            
            nodes = await self.db.fetch_all(nodes_query, workflow_base_id)
            logger.info(f"   ✅ 工作流节点查询完成: {len(nodes)} 个节点")
            
            for i, node in enumerate(nodes):
                logger.info(f"     节点 {i+1}: {node['name']} (类型: {node['type']}, ID: {node['node_id']})")
            
            # 获取所有连接
            logger.info(f"   📋 查询工作流连接...")
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
            WHERE nc.workflow_id = %s
            ORDER BY nc.created_at
            """
            
            connections = await self.db.fetch_all(connections_query, workflow["workflow_id"])
            logger.info(f"   ✅ 工作流连接查询完成: {len(connections)} 个连接")
            
            for i, conn in enumerate(connections):
                logger.info(f"     连接 {i+1}: {conn['from_node_name']} -> {conn['to_node_name']} (类型: {conn['connection_type']})")
            
            result = {
                "workflow": workflow,
                "nodes": [dict(node) for node in nodes],
                "connections": [dict(conn) for conn in connections]
            }
            
            logger.info(f"✅ [GET-WORKFLOW-STRUCTURE-SUCCESS] 工作流结构获取完成:")
            logger.info(f"   - 节点总数: {len(result['nodes'])}")
            logger.info(f"   - 连接总数: {len(result['connections'])}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [GET-WORKFLOW-STRUCTURE-EXCEPTION] 获取工作流结构异常: {workflow_base_id}, {e}")
            logger.error(f"❌ [GET-WORKFLOW-STRUCTURE-EXCEPTION] 异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"❌ [GET-WORKFLOW-STRUCTURE-EXCEPTION] 异常堆栈: {traceback.format_exc()}")
            return None
    
    async def _analyze_merge_candidate(
        self,
        parent_workflow: Dict[str, Any],
        candidate: Dict[str, Any],
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """分析单个合并候选"""
        try:
            parent_workflow_id = candidate["parent_workflow_id"]
            sub_workflow_id = candidate["sub_workflow_id"]
            replaceable_node_id = candidate["replaceable_node"]["node_base_id"]
            
            # 获取子工作流结构
            sub_workflow = await self._get_workflow_structure(uuid.UUID(sub_workflow_id))
            if not sub_workflow:
                return {
                    "candidate_id": candidate.get("subdivision_id"),
                    "valid": False,
                    "error": "子工作流不存在",
                    "preview": None
                }
            
            # 找到要替换的节点
            target_node = None
            for node in parent_workflow["nodes"]:
                if str(node["node_base_id"]) == replaceable_node_id:
                    target_node = node
                    break
            
            if not target_node:
                return {
                    "candidate_id": candidate.get("subdivision_id"),
                    "valid": False,
                    "error": "目标节点不存在",
                    "preview": None
                }
            
            # 分析替换后的结构变化
            merge_preview = self._calculate_merge_impact(
                parent_workflow, sub_workflow, target_node
            )
            
            return {
                "candidate_id": candidate.get("subdivision_id"),
                "valid": True,
                "target_node": {
                    "node_base_id": str(target_node["node_base_id"]),
                    "name": target_node["name"],
                    "type": target_node["type"]
                },
                "replacement_info": {
                    "sub_workflow_name": sub_workflow["workflow"]["name"],
                    "nodes_to_add": len(sub_workflow["nodes"]),
                    "connections_to_add": len(sub_workflow["connections"])
                },
                "preview": merge_preview
            }
            
        except Exception as e:
            logger.error(f"❌ 分析合并候选失败: {e}")
            return {
                "candidate_id": candidate.get("subdivision_id"),
                "valid": False,
                "error": str(e),
                "preview": None
            }
    
    def _calculate_merge_impact(
        self,
        parent_workflow: Dict[str, Any],
        sub_workflow: Dict[str, Any],
        target_node: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算合并对工作流结构的影响"""
        try:
            # 分析连接变化
            incoming_connections = []
            outgoing_connections = []
            
            target_node_id = str(target_node["node_id"])
            
            # 找到目标节点的输入和输出连接
            for conn in parent_workflow["connections"]:
                if str(conn["to_node_id"]) == target_node_id:
                    incoming_connections.append(conn)
                elif str(conn["from_node_id"]) == target_node_id:
                    outgoing_connections.append(conn)
            
            # 分析子工作流的开始和结束节点
            start_nodes = [n for n in sub_workflow["nodes"] if n["type"] == "start"]
            end_nodes = [n for n in sub_workflow["nodes"] if n["type"] == "end"]
            
            # 计算新的连接策略
            connection_strategy = self._plan_connection_strategy(
                incoming_connections, outgoing_connections, start_nodes, end_nodes
            )
            
            return {
                "nodes_removed": 1,  # 目标节点
                "nodes_added": len(sub_workflow["nodes"]),
                "connections_removed": len(incoming_connections) + len(outgoing_connections),
                "connections_added": len(sub_workflow["connections"]) + len(connection_strategy["bridge_connections"]),
                "connection_strategy": connection_strategy,
                "complexity_increase": len(sub_workflow["nodes"]) - 1,
                "estimated_execution_time_change": self._estimate_execution_time_change(
                    target_node, sub_workflow["nodes"]
                )
            }
            
        except Exception as e:
            logger.error(f"❌ 计算合并影响失败: {e}")
            return {
                "nodes_removed": 0,
                "nodes_added": 0,
                "connections_removed": 0,
                "connections_added": 0,
                "error": str(e)
            }
    
    def _plan_connection_strategy(
        self,
        incoming_connections: List[Dict[str, Any]],
        outgoing_connections: List[Dict[str, Any]],
        start_nodes: List[Dict[str, Any]],
        end_nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """规划连接策略"""
        try:
            bridge_connections = []
            
            # 输入连接策略：连接到子工作流的开始节点
            for incoming in incoming_connections:
                if start_nodes:
                    # 如果有多个开始节点，选择第一个
                    target_start = start_nodes[0]
                    bridge_connections.append({
                        "type": "incoming_bridge",
                        "from_node_id": incoming["from_node_id"],
                        "to_node_id": target_start["node_id"],
                        "connection_type": incoming["connection_type"]
                    })
            
            # 输出连接策略：从子工作流的结束节点连接
            for outgoing in outgoing_connections:
                if end_nodes:
                    # 如果有多个结束节点，每个都要连接
                    for end_node in end_nodes:
                        bridge_connections.append({
                            "type": "outgoing_bridge", 
                            "from_node_id": end_node["node_id"],
                            "to_node_id": outgoing["to_node_id"],
                            "connection_type": outgoing["connection_type"]
                        })
            
            return {
                "bridge_connections": bridge_connections,
                "strategy": "replace_with_subflow",
                "start_nodes_count": len(start_nodes),
                "end_nodes_count": len(end_nodes),
                "connection_complexity": len(bridge_connections)
            }
            
        except Exception as e:
            logger.error(f"❌ 规划连接策略失败: {e}")
            return {
                "bridge_connections": [],
                "strategy": "error",
                "error": str(e)
            }
    
    def _estimate_execution_time_change(
        self,
        original_node: Dict[str, Any],
        replacement_nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """估算执行时间变化"""
        try:
            # 简单的启发式估算
            original_complexity = 1  # 单个节点的复杂度
            replacement_complexity = len(replacement_nodes)
            
            # 根据节点类型调整复杂度
            for node in replacement_nodes:
                if node["type"] in ["start", "end"]:
                    replacement_complexity -= 0.1  # 开始结束节点复杂度较低
                elif node["type"] == "processor":
                    replacement_complexity += 0.5  # 处理节点复杂度较高
            
            change_factor = replacement_complexity / original_complexity
            
            return {
                "original_complexity": original_complexity,
                "new_complexity": replacement_complexity,
                "change_factor": change_factor,
                "estimated_change": "increase" if change_factor > 1.2 else "similar" if change_factor > 0.8 else "decrease"
            }
            
        except Exception as e:
            logger.error(f"❌ 估算执行时间变化失败: {e}")
            return {
                "estimated_change": "unknown",
                "error": str(e)
            }
    
    def _build_merge_preview(
        self,
        parent_workflow: Dict[str, Any],
        merge_previews: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """构建整体合并预览"""
        try:
            valid_merges = [p for p in merge_previews if p["valid"]]
            invalid_merges = [p for p in merge_previews if not p["valid"]]
            
            # 计算整体影响
            total_nodes_added = sum(p["replacement_info"]["nodes_to_add"] for p in valid_merges)
            total_nodes_removed = len(valid_merges)  # 每个合并操作移除一个节点
            total_connections_added = sum(p["replacement_info"]["connections_to_add"] for p in valid_merges)
            
            return {
                "parent_workflow": {
                    "workflow_base_id": str(parent_workflow["workflow"]["workflow_base_id"]),
                    "name": parent_workflow["workflow"]["name"],
                    "current_nodes": len(parent_workflow["nodes"]),
                    "current_connections": len(parent_workflow["connections"])
                },
                "merge_summary": {
                    "total_merge_candidates": len(merge_previews),
                    "valid_merges": len(valid_merges),
                    "invalid_merges": len(invalid_merges),
                    "net_nodes_change": total_nodes_added - total_nodes_removed,
                    "net_connections_change": total_connections_added
                },
                "valid_merge_previews": valid_merges,
                "invalid_merge_previews": invalid_merges,
                "merge_feasibility": {
                    "can_proceed": len(valid_merges) > 0,
                    "complexity_increase": "high" if total_nodes_added > 20 else "medium" if total_nodes_added > 10 else "low",
                    "recommended_approach": self._recommend_merge_approach(valid_merges)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 构建合并预览失败: {e}")
            return {
                "error": str(e),
                "can_proceed": False
            }
    
    def _recommend_merge_approach(self, valid_merges: List[Dict[str, Any]]) -> str:
        """推荐合并方式"""
        if len(valid_merges) == 0:
            return "no_merge_possible"
        elif len(valid_merges) == 1:
            return "single_merge"
        elif len(valid_merges) <= 3:
            return "batch_merge"
        else:
            return "phased_merge"
    
    async def _validate_merge_operations(
        self,
        parent_workflow: Dict[str, Any],
        selected_merges: List[Dict[str, Any]],
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """验证合并操作的有效性"""
        try:
            errors = []
            warnings = []
            
            # 检查权限
            if str(parent_workflow["workflow"]["creator_id"]) != str(user_id):
                errors.append("用户无权限修改此工作流")
            
            # 检查节点冲突
            target_nodes = set()
            for merge in selected_merges:
                node_id = merge.get("target_node_id")
                if node_id in target_nodes:
                    errors.append(f"节点 {node_id} 被多个合并操作选中")
                target_nodes.add(node_id)
            
            # 检查子工作流的存在性
            for merge in selected_merges:
                sub_workflow_id = merge.get("sub_workflow_id")
                if sub_workflow_id:
                    sub_workflow = await self._get_workflow_structure(uuid.UUID(sub_workflow_id))
                    if not sub_workflow:
                        errors.append(f"子工作流 {sub_workflow_id} 不存在")
            
            # 复杂度检查
            total_new_nodes = sum(merge.get("nodes_to_add", 0) for merge in selected_merges)
            if total_new_nodes > 50:
                warnings.append(f"合并后将增加 {total_new_nodes} 个节点，工作流复杂度较高")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"❌ 验证合并操作失败: {e}")
            return {
                "valid": False,
                "errors": [f"验证过程发生错误: {e}"],
                "warnings": []
            }
    
    async def _perform_merge(
        self,
        parent_workflow: Dict[str, Any],
        selected_merges: List[Dict[str, Any]],
        merge_config: Dict[str, Any],
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """执行实际的合并操作"""
        try:
            logger.info(f"🔄 [MERGE-PERFORM-START] 开始执行实际合并操作")
            
            # 创建新的工作流
            new_workflow_name = merge_config.get("new_workflow_name", 
                f"{parent_workflow['workflow']['name']}_merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            logger.info(f"📝 [MERGE-PERFORM-STEP1] 准备创建新工作流:")
            logger.info(f"   - 新工作流名称: {new_workflow_name}")
            logger.info(f"   - 基于父工作流: {parent_workflow['workflow']['name']}")
            logger.info(f"   - 创建者ID: {user_id}")
            
            new_workflow_data = WorkflowCreate(
                name=new_workflow_name,
                description=f"通过模板连接合并生成的工作流，基于 {parent_workflow['workflow']['name']}",
                creator_id=user_id
            )
            
            # 创建工作流
            logger.info(f"🔧 [MERGE-PERFORM-STEP2] 正在创建新工作流...")
            new_workflow = await self.workflow_repo.create_workflow(new_workflow_data)
            
            if not new_workflow:
                logger.error(f"❌ [MERGE-PERFORM-STEP2-FAILED] 创建新工作流失败")
                return {
                    "success": False,
                    "message": "创建新工作流失败",
                    "error": "workflow_creation_failed"
                }
            
            logger.info(f"✅ [MERGE-PERFORM-STEP2-SUCCESS] 新工作流创建成功:")
            logger.info(f"   - 新工作流ID: {new_workflow['workflow_id']}")
            logger.info(f"   - 新工作流基础ID: {new_workflow['workflow_base_id']}")
            
            # 复制并修改节点和连接
            logger.info(f"🔧 [MERGE-PERFORM-STEP3] 开始执行节点替换...")
            merge_result = await self._execute_node_replacement(
                parent_workflow, 
                selected_merges, 
                new_workflow["workflow_base_id"],
                user_id
            )
            
            logger.info(f"✅ [MERGE-PERFORM-STEP3-SUCCESS] 节点替换完成:")
            logger.info(f"   - 创建节点数: {merge_result.get('nodes_created', 0)}")
            logger.info(f"   - 创建连接数: {merge_result.get('connections_created', 0)}")
            logger.info(f"   - 替换节点数: {merge_result.get('nodes_replaced', 0)}")
            
            logger.info(f"🎉 [MERGE-PERFORM-SUCCESS] 合并操作执行成功")
            return {
                "success": True,
                "message": "工作流合并成功",
                "new_workflow_id": str(new_workflow["workflow_base_id"]),
                "new_workflow_name": new_workflow_name,
                "merge_statistics": merge_result
            }
            
        except Exception as e:
            logger.error(f"❌ [MERGE-PERFORM-EXCEPTION] 执行合并操作异常: {e}")
            logger.error(f"❌ [MERGE-PERFORM-EXCEPTION] 异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"❌ [MERGE-PERFORM-EXCEPTION] 异常堆栈: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"合并操作失败: {str(e)}",
                "error": str(e)
            }
    
    async def _execute_node_replacement(
        self,
        parent_workflow: Dict[str, Any],
        selected_merges: List[Dict[str, Any]],
        new_workflow_base_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Dict[str, Any]:
        """执行节点替换操作（改进版本，避免冗余开始/结束节点）"""
        try:
            logger.info(f"🔄 [NODE-REPLACEMENT-START] 开始智能节点替换操作")
            logger.info(f"   - 新工作流基础ID: {new_workflow_base_id}")
            logger.info(f"   - 合并操作数: {len(selected_merges)}")
            
            nodes_created = 0
            connections_created = 0
            nodes_replaced = 0
            
            # 获取要替换的节点ID集合
            replaced_node_ids = set()
            replacement_mapping = {}  # 原节点base_id -> 替换信息映射
            
            logger.info(f"🔍 [NODE-REPLACEMENT-STEP1] 智能处理子工作流节点替换...")
            
            for i, merge in enumerate(selected_merges):
                logger.info(f"🔧 [NODE-REPLACEMENT-MERGE-{i+1}] 处理合并操作 {i+1}:")
                target_node_id = merge["target_node_id"]
                sub_workflow_id = merge["sub_workflow_id"]
                
                logger.info(f"   - 目标节点ID: {target_node_id}")
                logger.info(f"   - 子工作流ID: {sub_workflow_id}")
                
                replaced_node_ids.add(target_node_id)
                
                # 获取子工作流结构
                logger.info(f"   📋 获取子工作流结构...")
                sub_workflow = await self._get_workflow_structure(uuid.UUID(sub_workflow_id))
                
                if not sub_workflow:
                    logger.error(f"   ❌ 子工作流不存在: {sub_workflow_id}")
                    continue
                
                logger.info(f"   ✅ 子工作流结构获取成功:")
                logger.info(f"     - 子工作流名称: {sub_workflow['workflow']['name']}")
                logger.info(f"     - 子工作流节点数: {len(sub_workflow['nodes'])}")
                logger.info(f"     - 子工作流连接数: {len(sub_workflow['connections'])}")
                
                if sub_workflow:
                    # 🎯 智能节点处理：排除开始和结束节点，只复制处理节点
                    logger.info(f"   🧠 智能过滤节点类型...")
                    
                    start_nodes = [n for n in sub_workflow["nodes"] if n["type"] == "start"]
                    end_nodes = [n for n in sub_workflow["nodes"] if n["type"] == "end"]
                    process_nodes = [n for n in sub_workflow["nodes"] if n["type"] not in ["start", "end"]]
                    
                    logger.info(f"     - 开始节点: {len(start_nodes)} 个 (将被排除)")
                    logger.info(f"     - 结束节点: {len(end_nodes)} 个 (将被排除)")
                    logger.info(f"     - 处理节点: {len(process_nodes)} 个 (将被复制)")
                    
                    # 复制处理节点到新工作流（排除start/end节点避免冗余）
                    logger.info(f"   🔧 复制处理节点到新工作流...")
                    node_id_mapping = {}
                    
                    for j, sub_node in enumerate(process_nodes):
                        logger.info(f"     📝 创建处理节点 {j+1}: {sub_node['name']} (类型: {sub_node['type']})")
                        
                        new_node_data = NodeCreate(
                            name=sub_node["name"],
                            type=NodeType(sub_node["type"]),
                            task_description=sub_node.get("task_description", ""),
                            workflow_base_id=new_workflow_base_id,
                            position_x=sub_node.get("position_x", 0),
                            position_y=sub_node.get("position_y", 0),
                            creator_id=user_id
                        )
                        
                        try:
                            created_node = await self.node_repo.create_node(new_node_data)
                            if not created_node:
                                logger.error(f"     ❌ 节点创建失败: {sub_node['name']}")
                                continue
                                
                            node_id_mapping[str(sub_node["node_id"])] = created_node["node_id"]
                            nodes_created += 1
                            logger.info(f"     ✅ 处理节点创建成功: {created_node['node_id']}")
                        except Exception as e:
                            logger.error(f"     ❌ 节点创建异常: {e}")
                            continue
                    
                    logger.info(f"   ✅ 处理节点复制完成: 创建了 {len(node_id_mapping)} 个节点")
                    
                    # 🔗 智能连接处理：只处理处理节点之间的连接
                    logger.info(f"   🔗 智能处理内部连接...")
                    internal_connections = 0
                    
                    for k, sub_conn in enumerate(sub_workflow["connections"]):
                        from_node_id = node_id_mapping.get(str(sub_conn["from_node_id"]))
                        to_node_id = node_id_mapping.get(str(sub_conn["to_node_id"]))
                        
                        # 只处理两端都是处理节点的连接
                        if from_node_id and to_node_id:
                            logger.info(f"     🔗 创建内部连接 {k+1}: {from_node_id} -> {to_node_id}")
                            
                            try:
                                await self._create_node_connection(
                                    from_node_id, to_node_id, sub_conn["connection_type"]
                                )
                                connections_created += 1
                                internal_connections += 1
                                logger.info(f"     ✅ 内部连接创建成功")
                            except Exception as e:
                                logger.error(f"     ❌ 内部连接创建失败: {e}")
                        else:
                            # 跳过与开始/结束节点相关的连接
                            logger.debug(f"     ⏭️ 跳过边界连接: {sub_conn['from_node_id']} -> {sub_conn['to_node_id']}")
                    
                    logger.info(f"   ✅ 内部连接处理完成: 创建了 {internal_connections} 个连接")
                    
                    # 🎯 智能替换映射：找到入口和出口节点
                    entry_nodes = self._find_entry_nodes(sub_workflow["nodes"], sub_workflow["connections"], node_id_mapping)
                    exit_nodes = self._find_exit_nodes(sub_workflow["nodes"], sub_workflow["connections"], node_id_mapping)
                    
                    replacement_mapping[target_node_id] = {
                        "entry_nodes": entry_nodes,  # 替换后的入口节点
                        "exit_nodes": exit_nodes,    # 替换后的出口节点
                        "all_process_nodes": list(node_id_mapping.values())
                    }
                    
                    logger.info(f"   📋 智能替换映射完成:")
                    logger.info(f"     - 入口节点: {len(entry_nodes)} 个")
                    logger.info(f"     - 出口节点: {len(exit_nodes)} 个") 
                    logger.info(f"     - 处理节点总数: {len(node_id_mapping.values())} 个")
            
            logger.info(f"🔍 [NODE-REPLACEMENT-STEP2] 复制父工作流中未被替换的节点...")
            
            # 复制父工作流中未被替换的节点
            parent_node_mapping = {}
            for i, parent_node in enumerate(parent_workflow["nodes"]):
                if str(parent_node["node_base_id"]) not in replaced_node_ids:
                    logger.info(f"   📝 复制父节点 {i+1}: {parent_node['name']} (类型: {parent_node['type']})")
                    
                    new_node_data = NodeCreate(
                        name=parent_node["name"],
                        type=NodeType(parent_node["type"]),
                        task_description=parent_node.get("task_description", ""),
                        workflow_base_id=new_workflow_base_id,
                        position_x=parent_node.get("position_x", 0),
                        position_y=parent_node.get("position_y", 0),
                        creator_id=user_id
                    )
                    
                    try:
                        created_node = await self.node_repo.create_node(new_node_data)
                        if created_node:
                            parent_node_mapping[str(parent_node["node_id"])] = created_node["node_id"]
                            nodes_created += 1
                            logger.info(f"   ✅ 父节点复制成功: {created_node['node_id']}")
                        else:
                            logger.error(f"   ❌ 父节点复制失败: {parent_node['name']}")
                    except Exception as e:
                        logger.error(f"   ❌ 父节点复制异常: {e}")
                else:
                    logger.info(f"   ⏭️ 跳过被替换的节点: {parent_node['name']}")
            
            logger.info(f"✅ [NODE-REPLACEMENT-STEP2-COMPLETE] 父节点复制完成: {len(parent_node_mapping)} 个节点")
            
            logger.info(f"🔍 [NODE-REPLACEMENT-STEP3] 智能重建连接关系...")
            
            # 智能重建连接关系
            bridge_connections = await self._rebuild_intelligent_connections(
                parent_workflow["connections"], 
                parent_node_mapping, 
                replacement_mapping, 
                parent_workflow["nodes"]
            )
            connections_created += bridge_connections
            
            nodes_replaced = len(replaced_node_ids)
            
            logger.info(f"🎉 [NODE-REPLACEMENT-SUCCESS] 智能节点替换操作完成:")
            logger.info(f"   - 创建节点数: {nodes_created}")
            logger.info(f"   - 创建连接数: {connections_created}")
            logger.info(f"   - 替换节点数: {nodes_replaced}")
            logger.info(f"   - 替换操作数: {len(selected_merges)}")
            
            return {
                "nodes_created": nodes_created,
                "connections_created": connections_created,
                "nodes_replaced": nodes_replaced,
                "replacement_operations": len(selected_merges)
            }
            
        except Exception as e:
            logger.error(f"❌ [NODE-REPLACEMENT-EXCEPTION] 执行节点替换异常: {e}")
            logger.error(f"❌ [NODE-REPLACEMENT-EXCEPTION] 异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"❌ [NODE-REPLACEMENT-EXCEPTION] 异常堆栈: {traceback.format_exc()}")
            raise
    
    def _find_entry_nodes(
        self, 
        sub_nodes: List[Dict[str, Any]], 
        sub_connections: List[Dict[str, Any]], 
        node_id_mapping: Dict[str, uuid.UUID]
    ) -> List[uuid.UUID]:
        """
        找到子工作流中的入口节点（应该接收来自父工作流的输入）
        
        入口节点定义（改进版，处理无连接情况）：
        1. 直接连接到start节点的处理节点
        2. 如果没有start节点，则是没有前置节点的处理节点
        3. 如果没有连接数据，使用启发式方法确定入口节点
        """
        try:
            entry_nodes = []
            start_nodes = [n for n in sub_nodes if n["type"] == "start"]
            process_nodes = [n for n in sub_nodes if n["type"] not in ["start", "end"]]
            
            logger.debug(f"   🔍 分析入口节点: {len(start_nodes)} 个start节点, {len(sub_connections)} 个连接")
            
            # 情况1: 有连接数据且有start节点
            if sub_connections and start_nodes:
                logger.debug(f"   📡 情况1: 基于start节点连接分析")
                for start_node in start_nodes:
                    for conn in sub_connections:
                        if (str(conn["from_node_id"]) == str(start_node["node_id"]) and
                            str(conn["to_node_id"]) in node_id_mapping):
                            target_node_id = node_id_mapping[str(conn["to_node_id"])]
                            if target_node_id not in entry_nodes:
                                entry_nodes.append(target_node_id)
                                logger.debug(f"     ✅ 找到start连接的入口节点")
                                
            # 情况2: 有连接数据但没有start节点
            elif sub_connections and not start_nodes:
                logger.debug(f"   📡 情况2: 基于前置节点分析")
                for node_id, mapped_id in node_id_mapping.items():
                    has_predecessor = False
                    for conn in sub_connections:
                        if (str(conn["to_node_id"]) == node_id and
                            str(conn["from_node_id"]) in node_id_mapping):
                            has_predecessor = True
                            break
                    
                    if not has_predecessor:
                        entry_nodes.append(mapped_id)
                        logger.debug(f"     ✅ 找到无前置的入口节点")
                        
            # 情况3: 没有连接数据 - 启发式方法
            else:
                logger.warning(f"   ⚠️ 情况3: 无连接数据，使用启发式入口节点识别")
                
                # 启发式策略1: 如果有start节点，选择第一个紧跟的处理节点
                if start_nodes and process_nodes:
                    logger.debug(f"     🎯 启发式策略1: 选择start节点后的处理节点")
                    # 按创建时间排序，选择最早的处理节点作为入口
                    sorted_process_nodes = sorted(process_nodes, key=lambda x: x.get('created_at', ''))
                    if sorted_process_nodes:
                        first_process_node_id = str(sorted_process_nodes[0]["node_id"])
                        if first_process_node_id in node_id_mapping:
                            entry_nodes.append(node_id_mapping[first_process_node_id])
                            logger.debug(f"     ✅ 启发式选择: {sorted_process_nodes[0]['name']}")
                
                # 启发式策略2: 没有start节点，选择第一个处理节点
                elif process_nodes:
                    logger.debug(f"     🎯 启发式策略2: 选择第一个处理节点")
                    # 按节点位置或创建时间选择
                    sorted_nodes = sorted(process_nodes, key=lambda x: (
                        x.get('position_x', 0), 
                        x.get('position_y', 0),
                        x.get('created_at', '')
                    ))
                    
                    if sorted_nodes:
                        first_node_id = str(sorted_nodes[0]["node_id"])
                        if first_node_id in node_id_mapping:
                            entry_nodes.append(node_id_mapping[first_node_id])
                            logger.debug(f"     ✅ 启发式选择: {sorted_nodes[0]['name']}")
                
                # 启发式策略3: 兜底方案 - 选择所有处理节点中的第一个
                if not entry_nodes and node_id_mapping:
                    logger.debug(f"     🎯 启发式策略3: 兜底选择第一个可用节点")
                    first_mapped_id = next(iter(node_id_mapping.values()))
                    entry_nodes.append(first_mapped_id)
                    logger.debug(f"     ✅ 兜底选择完成")
            
            logger.info(f"   🎯 入口节点识别完成: {len(entry_nodes)} 个")
            return entry_nodes
            
        except Exception as e:
            logger.error(f"❌ 查找入口节点失败: {e}")
            # 兜底策略：如果有映射节点，至少返回一个
            if node_id_mapping:
                logger.warning(f"   🚑 启用兜底入口节点策略")
                return [next(iter(node_id_mapping.values()))]
            return []
    
    def _find_exit_nodes(
        self, 
        sub_nodes: List[Dict[str, Any]], 
        sub_connections: List[Dict[str, Any]], 
        node_id_mapping: Dict[str, uuid.UUID]
    ) -> List[uuid.UUID]:
        """
        找到子工作流中的出口节点（应该输出到父工作流的后续节点）
        
        出口节点定义（改进版，处理无连接情况）：
        1. 直接连接到end节点的处理节点
        2. 如果没有end节点，则是没有后续节点的处理节点
        3. 如果没有连接数据，使用启发式方法确定出口节点
        """
        try:
            exit_nodes = []
            end_nodes = [n for n in sub_nodes if n["type"] == "end"]
            process_nodes = [n for n in sub_nodes if n["type"] not in ["start", "end"]]
            
            logger.debug(f"   🔍 分析出口节点: {len(end_nodes)} 个end节点, {len(sub_connections)} 个连接")
            
            # 情况1: 有连接数据且有end节点
            if sub_connections and end_nodes:
                logger.debug(f"   📡 情况1: 基于end节点连接分析")
                for end_node in end_nodes:
                    for conn in sub_connections:
                        if (str(conn["to_node_id"]) == str(end_node["node_id"]) and
                            str(conn["from_node_id"]) in node_id_mapping):
                            source_node_id = node_id_mapping[str(conn["from_node_id"])]
                            if source_node_id not in exit_nodes:
                                exit_nodes.append(source_node_id)
                                logger.debug(f"     ✅ 找到end连接的出口节点")
                                
            # 情况2: 有连接数据但没有end节点
            elif sub_connections and not end_nodes:
                logger.debug(f"   📡 情况2: 基于后续节点分析")
                for node_id, mapped_id in node_id_mapping.items():
                    has_successor = False
                    for conn in sub_connections:
                        if (str(conn["from_node_id"]) == node_id and
                            str(conn["to_node_id"]) in node_id_mapping):
                            has_successor = True
                            break
                    
                    if not has_successor:
                        exit_nodes.append(mapped_id)
                        logger.debug(f"     ✅ 找到无后续的出口节点")
                        
            # 情况3: 没有连接数据 - 启发式方法
            else:
                logger.warning(f"   ⚠️ 情况3: 无连接数据，使用启发式出口节点识别")
                
                # 启发式策略1: 如果有end节点，选择最后一个处理节点
                if end_nodes and process_nodes:
                    logger.debug(f"     🎯 启发式策略1: 选择end节点前的处理节点")
                    # 按创建时间排序，选择最晚的处理节点作为出口
                    sorted_process_nodes = sorted(process_nodes, key=lambda x: x.get('created_at', ''), reverse=True)
                    if sorted_process_nodes:
                        last_process_node_id = str(sorted_process_nodes[0]["node_id"])
                        if last_process_node_id in node_id_mapping:
                            exit_nodes.append(node_id_mapping[last_process_node_id])
                            logger.debug(f"     ✅ 启发式选择: {sorted_process_nodes[0]['name']}")
                
                # 启发式策略2: 没有end节点，选择最后一个处理节点
                elif process_nodes:
                    logger.debug(f"     🎯 启发式策略2: 选择最后一个处理节点")
                    # 按节点位置或创建时间选择最后的节点
                    sorted_nodes = sorted(process_nodes, key=lambda x: (
                        x.get('position_x', 0), 
                        x.get('position_y', 0),
                        x.get('created_at', '')
                    ), reverse=True)
                    
                    if sorted_nodes:
                        last_node_id = str(sorted_nodes[0]["node_id"])
                        if last_node_id in node_id_mapping:
                            exit_nodes.append(node_id_mapping[last_node_id])
                            logger.debug(f"     ✅ 启发式选择: {sorted_nodes[0]['name']}")
                
                # 启发式策略3: 兜底方案 - 选择所有处理节点中的最后一个
                if not exit_nodes and node_id_mapping:
                    logger.debug(f"     🎯 启发式策略3: 兜底选择最后一个可用节点")
                    # 如果有多个节点，选择最后一个；否则选择唯一的节点
                    if len(node_id_mapping) > 1:
                        last_mapped_id = list(node_id_mapping.values())[-1]
                    else:
                        last_mapped_id = next(iter(node_id_mapping.values()))
                    exit_nodes.append(last_mapped_id)
                    logger.debug(f"     ✅ 兜底选择完成")
            
            logger.info(f"   🎯 出口节点识别完成: {len(exit_nodes)} 个")
            return exit_nodes
            
        except Exception as e:
            logger.error(f"❌ 查找出口节点失败: {e}")
            # 兜底策略：如果有映射节点，至少返回一个
            if node_id_mapping:
                logger.warning(f"   🚑 启用兜底出口节点策略")
                # 选择最后一个节点作为出口
                if len(node_id_mapping) > 1:
                    return [list(node_id_mapping.values())[-1]]
                else:
                    return [next(iter(node_id_mapping.values()))]
            return []
    
    async def _rebuild_intelligent_connections(
        self,
        parent_connections: List[Dict[str, Any]],
        parent_node_mapping: Dict[str, uuid.UUID],
        replacement_mapping: Dict[str, Dict[str, List[uuid.UUID]]],
        parent_nodes: List[Dict[str, Any]]
    ) -> int:
        """
        智能重建连接关系，确保替换后的子工作流正确连接到父工作流（改进版，支持备用策略）
        """
        try:
            bridge_connections = 0
            
            logger.info(f"🔗 [CONNECTION-REBUILD] 开始重建连接关系:")
            logger.info(f"   - 父连接数: {len(parent_connections)}")
            logger.info(f"   - 替换操作数: {len(replacement_mapping)}")
            logger.info(f"   - 父节点映射数: {len(parent_node_mapping)}")
            
            # 情况1: 有父连接数据 - 使用原始逻辑
            if parent_connections:
                logger.info(f"📡 [CONNECTION-REBUILD-CASE1] 基于现有父连接重建")
                
                for i, parent_conn in enumerate(parent_connections):
                    from_node_id = str(parent_conn["from_node_id"])
                    to_node_id = str(parent_conn["to_node_id"])
                    
                    logger.info(f"   🔗 处理父连接 {i+1}: {from_node_id} -> {to_node_id}")
                    
                    # 智能解析连接端点
                    new_from_nodes = self._intelligent_resolve_connection_endpoint(
                        from_node_id, parent_node_mapping, replacement_mapping, 
                        parent_nodes, "output"
                    )
                    new_to_nodes = self._intelligent_resolve_connection_endpoint(
                        to_node_id, parent_node_mapping, replacement_mapping, 
                        parent_nodes, "input"
                    )
                    
                    logger.info(f"     - 智能解析结果: from={len(new_from_nodes)}个节点, to={len(new_to_nodes)}个节点")
                    
                    # 创建桥接连接
                    for from_node in new_from_nodes:
                        for to_node in new_to_nodes:
                            try:
                                await self._create_node_connection(
                                    from_node, to_node, parent_conn["connection_type"]
                                )
                                bridge_connections += 1
                                logger.info(f"     ✅ 桥接连接创建成功: {from_node} -> {to_node}")
                            except Exception as e:
                                logger.error(f"     ❌ 桥接连接创建失败: {e}")
            
            # 情况2: 没有父连接数据 - 启用备用连接策略
            else:
                logger.warning(f"⚠️ [CONNECTION-REBUILD-CASE2] 没有父连接数据，启用备用连接策略")
                bridge_connections += await self._create_fallback_connections(
                    parent_node_mapping, replacement_mapping, parent_nodes
                )
            
            logger.info(f"✅ [CONNECTION-REBUILD-SUCCESS] 连接重建完成: {bridge_connections} 个连接")
            return bridge_connections
            
        except Exception as e:
            logger.error(f"❌ [CONNECTION-REBUILD-EXCEPTION] 智能重建连接异常: {e}")
            return 0
    
    def _intelligent_resolve_connection_endpoint(
        self,
        original_node_id: str,
        parent_node_mapping: Dict[str, uuid.UUID],
        replacement_mapping: Dict[str, Dict[str, List[uuid.UUID]]],
        parent_nodes: List[Dict[str, Any]],
        direction: str
    ) -> List[uuid.UUID]:
        """
        智能解析连接端点，正确处理节点替换的连接关系
        """
        try:
            # 首先检查节点是否被保留（未被替换）
            if original_node_id in parent_node_mapping:
                logger.debug(f"     📍 节点 {original_node_id} 被保留，直接映射")
                return [parent_node_mapping[original_node_id]]
            
            # 检查节点是否被替换了
            # 需要找到原node_id对应的node_base_id
            original_node_base_id = None
            for parent_node in parent_nodes:
                if str(parent_node["node_id"]) == original_node_id:
                    original_node_base_id = str(parent_node["node_base_id"])
                    break
            
            if not original_node_base_id:
                logger.warning(f"     ⚠️ 无法找到节点 {original_node_id} 的base_id")
                return []
            
            # 检查这个base_id是否在替换映射中
            if original_node_base_id in replacement_mapping:
                replacement = replacement_mapping[original_node_base_id]
                
                if direction == "output":
                    # 输出连接：使用子工作流的出口节点
                    logger.debug(f"     🚀 节点 {original_node_id} 被替换，使用出口节点 ({len(replacement['exit_nodes'])} 个)")
                    return replacement["exit_nodes"]
                else:
                    # 输入连接：使用子工作流的入口节点
                    logger.debug(f"     📥 节点 {original_node_id} 被替换，使用入口节点 ({len(replacement['entry_nodes'])} 个)")
                    return replacement["entry_nodes"]
            
            logger.warning(f"     ⚠️ 无法解析节点 {original_node_id} 的连接端点")
            return []
            
        except Exception as e:
            logger.error(f"❌ 智能解析连接端点失败: {original_node_id}, {e}")
            return []
    
    async def _create_node_connection(
        self,
        from_node_id: uuid.UUID,
        to_node_id: uuid.UUID,
        connection_type: str
    ):
        """创建节点连接"""
        try:
            # 使用MySQL格式的参数占位符
            connection_query = """
            INSERT INTO node_connection (
                from_node_id, to_node_id, connection_type, workflow_id, created_at
            )
            SELECT %s, %s, %s, 
                   (SELECT workflow_id FROM node WHERE node_id = %s LIMIT 1),
                   %s
            """
            
            await self.db.execute(
                connection_query,
                str(from_node_id), str(to_node_id), connection_type, str(from_node_id), now_utc()
            )
            
        except Exception as e:
            logger.error(f"❌ 创建节点连接失败: {e}")
            raise
    
    async def _create_fallback_connections(
        self,
        parent_node_mapping: Dict[str, uuid.UUID],
        replacement_mapping: Dict[str, Dict[str, List[uuid.UUID]]],
        parent_nodes: List[Dict[str, Any]]
    ) -> int:
        """
        创建备用连接策略 - 当父工作流没有连接数据时使用
        
        备用策略：
        1. 基于节点类型和位置创建基本的线性连接
        2. 确保start -> processor -> end的基本流程
        3. 正确整合替换的子工作流节点
        """
        try:
            logger.info(f"🚑 [FALLBACK-CONNECTION] 启动备用连接策略")
            fallback_connections = 0
            
            # 获取所有节点并按类型分类
            all_mapped_nodes = list(parent_node_mapping.values())
            start_nodes = []
            end_nodes = []
            processor_nodes = []
            
            # 分析父节点类型
            for parent_node in parent_nodes:
                if str(parent_node["node_id"]) in parent_node_mapping:
                    mapped_id = parent_node_mapping[str(parent_node["node_id"])]
                    node_type = parent_node["type"]
                    
                    if node_type == "start":
                        start_nodes.append((mapped_id, parent_node))
                    elif node_type == "end":
                        end_nodes.append((mapped_id, parent_node))
                    elif node_type == "processor":
                        processor_nodes.append((mapped_id, parent_node))
            
            logger.info(f"   📊 节点分类: {len(start_nodes)} 个start, {len(processor_nodes)} 个processor, {len(end_nodes)} 个end")
            
            # 获取替换节点（子工作流节点）
            all_replacement_nodes = []
            for replacement_info in replacement_mapping.values():
                all_replacement_nodes.extend(replacement_info["all_process_nodes"])
            
            logger.info(f"   🔄 替换节点: {len(all_replacement_nodes)} 个")
            
            # 策略1: 创建基本的线性连接
            logger.info(f"   🔗 策略1: 创建基本线性连接")
            
            # 合并所有处理节点（包括原有的和替换的）
            all_process_nodes = [node_id for node_id, _ in processor_nodes] + all_replacement_nodes
            
            # 按创建顺序或位置排序节点
            try:
                # 尝试按位置排序
                def get_node_position(node_id):
                    for node_id_str, mapped_id in parent_node_mapping.items():
                        if mapped_id == node_id:
                            for parent_node in parent_nodes:
                                if str(parent_node["node_id"]) == node_id_str:
                                    return (
                                        parent_node.get("position_x", 0),
                                        parent_node.get("position_y", 0),
                                        parent_node.get("created_at", "")
                                    )
                    return (0, 0, "")
                
                all_process_nodes.sort(key=get_node_position)
                logger.debug(f"     ✅ 节点按位置排序完成")
                
            except Exception as e:
                logger.warning(f"     ⚠️ 节点排序失败，使用原始顺序: {e}")
            
            # 创建连接序列
            connection_sequence = []
            
            # start -> first process node
            if start_nodes and all_process_nodes:
                start_id = start_nodes[0][0]
                first_process_id = all_process_nodes[0]
                connection_sequence.append((start_id, first_process_id, "normal"))
                logger.debug(f"     📌 start -> first_process: {start_id} -> {first_process_id}")
            
            # process node -> process node (linear chain)
            for i in range(len(all_process_nodes) - 1):
                from_id = all_process_nodes[i]
                to_id = all_process_nodes[i + 1]
                connection_sequence.append((from_id, to_id, "normal"))
                logger.debug(f"     📌 process chain: {from_id} -> {to_id}")
            
            # last process node -> end
            if all_process_nodes and end_nodes:
                last_process_id = all_process_nodes[-1]
                end_id = end_nodes[0][0]
                connection_sequence.append((last_process_id, end_id, "normal"))
                logger.debug(f"     📌 last_process -> end: {last_process_id} -> {end_id}")
            
            # 策略2: 创建替换节点的特殊连接
            logger.info(f"   🔗 策略2: 处理替换节点的入口/出口连接")
            
            for target_node_id, replacement_info in replacement_mapping.items():
                entry_nodes = replacement_info["entry_nodes"]
                exit_nodes = replacement_info["exit_nodes"]
                
                logger.debug(f"     🎯 处理替换节点 {target_node_id}: {len(entry_nodes)} 个入口, {len(exit_nodes)} 个出口")
                
                # 如果替换节点有多个入口/出口，创建额外的内部连接
                if len(entry_nodes) > 1 or len(exit_nodes) > 1:
                    # 将所有入口节点连接到第一个入口节点（聚合）
                    if len(entry_nodes) > 1:
                        main_entry = entry_nodes[0]
                        for i in range(1, len(entry_nodes)):
                            connection_sequence.append((entry_nodes[i], main_entry, "aggregation"))
                            logger.debug(f"     📌 入口聚合: {entry_nodes[i]} -> {main_entry}")
                    
                    # 将最后一个出口节点连接到所有出口节点（分发）
                    if len(exit_nodes) > 1:
                        main_exit = exit_nodes[-1]
                        for i in range(len(exit_nodes) - 1):
                            connection_sequence.append((main_exit, exit_nodes[i], "distribution"))
                            logger.debug(f"     📌 出口分发: {main_exit} -> {exit_nodes[i]}")
            
            # 执行连接创建
            logger.info(f"   🔧 执行连接创建: {len(connection_sequence)} 个连接")
            
            for from_id, to_id, conn_type in connection_sequence:
                try:
                    await self._create_node_connection(from_id, to_id, conn_type)
                    fallback_connections += 1
                    logger.debug(f"     ✅ 备用连接创建成功: {from_id} -> {to_id} ({conn_type})")
                except Exception as e:
                    logger.error(f"     ❌ 备用连接创建失败: {from_id} -> {to_id}, {e}")
                    # 继续创建其他连接，不中断整个过程
                    continue
            
            # 策略3: 确保基本可执行性
            logger.info(f"   🔗 策略3: 确保基本可执行性检查")
            
            if fallback_connections == 0:
                logger.warning(f"     ⚠️ 没有创建任何连接，尝试最基本的连接")
                
                # 最基本的连接：如果有任何两个节点，就连接它们
                if len(all_mapped_nodes) >= 2:
                    try:
                        await self._create_node_connection(
                            all_mapped_nodes[0], all_mapped_nodes[1], "basic"
                        )
                        fallback_connections += 1
                        logger.info(f"     🚑 创建基础连接: {all_mapped_nodes[0]} -> {all_mapped_nodes[1]}")
                    except Exception as e:
                        logger.error(f"     ❌ 基础连接创建失败: {e}")
            
            logger.info(f"✅ [FALLBACK-CONNECTION-SUCCESS] 备用连接策略完成: {fallback_connections} 个连接")
            return fallback_connections
            
        except Exception as e:
            logger.error(f"❌ [FALLBACK-CONNECTION-EXCEPTION] 备用连接策略失败: {e}")
            import traceback
            logger.error(f"❌ [FALLBACK-CONNECTION-EXCEPTION] 异常堆栈: {traceback.format_exc()}")
            return 0