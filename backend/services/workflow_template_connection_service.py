"""
工作流模板连接服务 - Linus式重构版本
Workflow Template Connection Service - Linus Refactored

核心思想：
1. subdivision就是树，不是复杂的图
2. 一个查询，一个数据结构，一套算法
3. 消除所有特殊情况和4层嵌套
4. "好程序员关心数据结构，不是代码" - Linus
"""

import uuid
from typing import Optional, Dict, Any, List
from loguru import logger

from ..repositories.base import BaseRepository
from ..utils.helpers import now_utc


class WorkflowTemplateConnectionService:
    """工作流模板连接服务 - 重构版本"""
    
    def __init__(self):
        self.db = BaseRepository("workflow_template_connection").db
    
    async def get_detailed_workflow_connections(self, workflow_instance_id: uuid.UUID, max_depth: int = 10) -> Dict[str, Any]:
        """
        Linus式简化版本：subdivision就是树，别搞复杂了
        
        Args:
            workflow_instance_id: 工作流实例ID
            max_depth: 最大递归深度（实际上用不到，树天然有限深度）
            
        Returns:
            简化的连接图数据结构
        """
        # try:
        logger.info(f"🌳 [Linus式简化] 获取subdivision树: {workflow_instance_id}")
        
        # 简单查询：获取所有subdivision，让树构建器处理层级关系
        subdivisions = await self._get_all_subdivisions_simple(workflow_instance_id)
        
        if not subdivisions:
            logger.info(f"📋 未找到subdivision: {workflow_instance_id}")
            return self._empty_connection_result(workflow_instance_id)
        
        # 使用新的工作流模板树构建器
        from .workflow_template_tree import WorkflowTemplateTree
        tree = await WorkflowTemplateTree().build_from_subdivisions(subdivisions, workflow_instance_id)
        
        # 直接从树获取图形数据和统计信息
        graph_data = tree.to_graph_data()
        statistics = tree.get_statistics()
        
        result = {
            "workflow_instance_id": str(workflow_instance_id),
            "template_connections": [],  # 保持兼容性，实际数据在graph里
            "detailed_workflows": {},    # 简化后不需要
            "merge_candidates": [],      # 简化后不需要
            "detailed_connection_graph": graph_data,
            "statistics": statistics
        }
        
        logger.info(f"✅ [Linus式简化] subdivision树构建完成: {statistics}")
        return result
            
        # except Exception as e:
        #     logger.error(f"❌ [Linus式简化] 获取subdivision树失败: {e}")
        #     # 如果Linus式简化失败，回退到旧版本
        #     logger.info(f"🔄 [回退] 使用旧版本方法")
        #     return await self._get_detailed_workflow_connections_old(workflow_instance_id, max_depth)

    async def _get_all_subdivisions_simple(self, workflow_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        递归查询：获取所有subdivision（包括嵌套的），构建完整的subdivision树
        
        subdivision表有parent_subdivision_id，但我们需要跨工作流实例递归查找
        """
        try:
            logger.info(f"🌳 开始递归查询subdivision: {workflow_instance_id}")
            logger.info(f"📊 [调试] 工作流实例ID类型: {type(workflow_instance_id)}, 值: {workflow_instance_id}")
            
            all_subdivisions = []
            processed_workflows = set()
            
            # 🔧 增加调试：检查工作流实例是否存在
            workflow_check = await self.db.fetch_one("""
                SELECT workflow_instance_id, status, created_at 
                FROM workflow_instance 
                WHERE workflow_instance_id = %s
            """, workflow_instance_id)
            logger.info(f"📊 [调试] 工作流实例检查: {workflow_check}")
            
            if not workflow_check:
                logger.error(f"❌ [严重错误] 工作流实例不存在: {workflow_instance_id}")
                return []
            
            # 🔧 增加调试：检查task_subdivision表是否有记录
            subdivision_count = await self.db.fetch_one("""
                SELECT COUNT(*) as count 
                FROM task_subdivision ts
                JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
                WHERE ti.workflow_instance_id = %s
                AND ts.is_deleted = FALSE
            """, workflow_instance_id)
            logger.info(f"📊 [调试] subdivision总数量: {subdivision_count['count'] if subdivision_count else 0}")
            
            async def recursive_query(current_workflow_id: uuid.UUID, current_depth: int = 1, max_depth: int = 10):
                """递归查询subdivision"""
                if current_depth > max_depth or str(current_workflow_id) in processed_workflows:
                    return
                
                processed_workflows.add(str(current_workflow_id))
                logger.info(f"  🔍 查询第{current_depth}层: {current_workflow_id}")
                
                # 🔧 先检查基础数据
                basic_check = await self.db.fetch_all("""
                    SELECT COUNT(*) as total_subdivisions,
                           COUNT(ts.sub_workflow_instance_id) as subdivisions_with_workflow,
                           COUNT(ts.sub_workflow_base_id) as subdivisions_with_base_id
                    FROM task_subdivision ts
                    JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
                    WHERE ti.workflow_instance_id = %s
                    AND ts.is_deleted = FALSE
                    AND ti.is_deleted = FALSE
                """, current_workflow_id)
                logger.info(f"    📊 基础统计: {dict(basic_check[0]) if basic_check else 'None'}")
                
                # 查询当前工作流的subdivisions - 修复版本
                query = """
                SELECT 
                    ts.subdivision_id,
                    ts.parent_subdivision_id,
                    ts.subdivision_name,
                    ts.subdivision_description,
                    ts.subdivision_created_at,
                    ts.sub_workflow_base_id,
                    ts.sub_workflow_instance_id,
                    
                    -- 任务信息
                    ti.task_title,
                    ti.task_description,
                    
                    -- 节点信息
                    n.name as original_node_name,
                    n.type as original_node_type,
                    
                    -- 工作流信息
                    sw.name as sub_workflow_name,
                    sw.description as sub_workflow_description,
                    
                    -- 实例状态
                    swi.status as sub_workflow_status,
                    swi.started_at as sub_workflow_started_at,
                    swi.completed_at as sub_workflow_completed_at,
                    
                    -- 层级信息
                    %s as depth,
                    %s as root_workflow_instance_id
                    
                FROM task_subdivision ts
                JOIN task_instance ti ON ts.original_task_id = ti.task_instance_id
                JOIN node_instance ni ON ti.node_instance_id = ni.node_instance_id
                LEFT JOIN node n ON ni.node_id = n.node_id  -- 🔧 修复：改为LEFT JOIN，兼容空版本工作流
                LEFT JOIN workflow sw ON ts.sub_workflow_base_id = sw.workflow_base_id AND sw.is_current_version = TRUE
                LEFT JOIN workflow_instance swi ON ts.sub_workflow_instance_id = swi.workflow_instance_id
                WHERE ti.workflow_instance_id = %s
                AND ts.is_deleted = FALSE
                AND ti.is_deleted = FALSE
                AND ni.is_deleted = FALSE
                -- 🔧 修复：不要过滤掉 sub_workflow_instance_id 为 NULL 的记录
                -- 因为有些subdivision可能处于创建中或者有其他状态
                ORDER BY ts.subdivision_created_at
                """
                
                logger.info(f"    🔍 执行subdivision查询...")
                subdivisions = await self.db.fetch_all(query, current_depth, current_workflow_id, current_workflow_id)
                current_level_subdivisions = [dict(row) for row in subdivisions]
                
                logger.info(f"    📦 第{current_depth}层原始查询结果: {len(current_level_subdivisions)} 个subdivision")
                
                # 🔧 增加详细调试信息
                for i, sub in enumerate(current_level_subdivisions[:3]):  # 显示前3个
                    logger.info(f"      subdivision {i+1}:")
                    logger.info(f"        subdivision_id: {sub.get('subdivision_id')}")
                    logger.info(f"        sub_workflow_instance_id: {sub.get('sub_workflow_instance_id')}")
                    logger.info(f"        sub_workflow_base_id: {sub.get('sub_workflow_base_id')}")
                    logger.info(f"        subdivision_name: {sub.get('subdivision_name')}")
                    logger.info(f"        task_title: {sub.get('task_title')}")
                    logger.info(f"        sub_workflow_status: {sub.get('sub_workflow_status')}")
                
                # 过滤有效的subdivision：必须有sub_workflow_base_id
                valid_subdivisions = []
                for sub in current_level_subdivisions:
                    if sub.get('sub_workflow_base_id'):
                        valid_subdivisions.append(sub)
                    else:
                        logger.warning(f"      ⚠️ 跳过无效subdivision (缺少sub_workflow_base_id): {sub.get('subdivision_id')}")
                
                logger.info(f"    ✅ 第{current_depth}层有效subdivision: {len(valid_subdivisions)} 个")
                
                if valid_subdivisions:
                    all_subdivisions.extend(valid_subdivisions)
                    
                    # 递归查询子工作流的subdivisions - 只对有workflow_instance_id的继续递归
                    child_workflow_ids = []
                    for sub in valid_subdivisions:
                        if sub.get('sub_workflow_instance_id'):
                            child_workflow_ids.append(uuid.UUID(sub['sub_workflow_instance_id']))
                    
                    logger.info(f"    🔄 准备递归查询 {len(child_workflow_ids)} 个子工作流")
                    
                    # 对每个子工作流进行递归查询
                    for child_id in child_workflow_ids:
                        await recursive_query(child_id, current_depth + 1, max_depth)
                else:
                    logger.info(f"    📭 第{current_depth}层无有效subdivision")
            
            # 开始递归查询
            await recursive_query(workflow_instance_id, 1)
            
            logger.info(f"🌳 递归查询完成: 找到 {len(all_subdivisions)} 个subdivision记录（包括嵌套）")
            
            # 调试输出层级信息
            by_depth = {}
            for sub in all_subdivisions:
                depth = sub['depth']
                if depth not in by_depth:
                    by_depth[depth] = []
                by_depth[depth].append(sub['subdivision_name'])
            
            for depth in sorted(by_depth.keys()):
                names_str = ', '.join(by_depth[depth])
                logger.info(f"  第{depth}层: {names_str}")
            
            return all_subdivisions
            
        except Exception as e:
            logger.error(f"❌ 递归查询subdivision失败: {e}")
            raise
    
    def _empty_connection_result(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """返回空的连接结果"""
        logger.warning(f"🔍 返回空的连接结果: {workflow_instance_id}")
        return {
            "workflow_instance_id": str(workflow_instance_id),
            "template_connections": [],
            "detailed_workflows": {},
            "merge_candidates": [],
            "detailed_connection_graph": {
                "nodes": [],
                "edges": [],
                "layout": {
                    "algorithm": "simple_tree",
                    "max_depth": 0,
                    "total_nodes": 0,
                    "root_count": 0
                }
            },
            "statistics": {
                "total_subdivisions": 0,
                "completed_sub_workflows": 0,
                "unique_workflows": 0,
                "max_depth": 0
            }
        }
    
    # 保持向后兼容的旧方法（委托给新方法）
    async def get_workflow_template_connections(self, workflow_instance_id: uuid.UUID, max_depth: int = 10) -> Dict[str, Any]:
        """向后兼容方法，委托给新的简化实现"""
        result = await self.get_detailed_workflow_connections(workflow_instance_id, max_depth)
        
        # 转换为旧格式
        return {
            "workflow_instance_id": result["workflow_instance_id"],
            "template_connections": result["template_connections"],
            "connection_graph": result["detailed_connection_graph"],
            "recursive_levels": result["statistics"]["max_depth"],
            "statistics": result["statistics"]
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
            LEFT JOIN node n ON ni.node_id = n.node_id  -- 🔧 修复：改为LEFT JOIN，兼容空版本工作流
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