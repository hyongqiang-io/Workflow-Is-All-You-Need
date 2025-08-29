"""
工作流实例映射关系查询服务
Workflow Instance Mapping Service
"""

import uuid
from typing import Optional, Dict, Any, List, Set
from loguru import logger
from backend.repositories.base import BaseRepository


class WorkflowInstanceMappingService:
    """工作流实例映射关系查询服务"""
    
    def __init__(self):
        self.db = BaseRepository("workflow_mapping").db
    
    async def get_complete_workflow_mapping(self, workflow_instance_id: uuid.UUID, 
                                          max_depth: int = 10) -> Dict[str, Any]:
        """
        获取工作流实例的完整映射关系
        
        Args:
            workflow_instance_id: 根工作流实例ID
            max_depth: 最大递归深度，防止无限递归
            
        Returns:
            完整的工作流-节点-子工作流映射关系
        """
        try:
            logger.info(f"🔍 开始查询工作流实例完整映射: {workflow_instance_id}")
            
            # 存储已处理的工作流实例，防止循环引用
            processed_workflows: Set[str] = set()
            
            # 递归查询根工作流及其所有子工作流
            root_mapping = await self._get_workflow_mapping_recursive(
                workflow_instance_id, 0, max_depth, processed_workflows
            )
            
            # 构建完整的映射结构
            complete_mapping = {
                "root_workflow_instance_id": str(workflow_instance_id),
                "mapping_data": root_mapping,
                "metadata": {
                    "total_workflows": len(processed_workflows),
                    "max_depth_reached": root_mapping.get("depth", 0),
                    "query_timestamp": self._get_current_timestamp()
                }
            }
            
            logger.info(f"✅ 工作流映射查询完成: 总共 {len(processed_workflows)} 个工作流")
            return complete_mapping
            
        except Exception as e:
            logger.error(f"查询工作流映射失败: {e}")
            raise
    
    async def _get_workflow_mapping_recursive(self, workflow_instance_id: uuid.UUID, 
                                            current_depth: int, max_depth: int,
                                            processed_workflows: Set[str]) -> Dict[str, Any]:
        """
        递归获取工作流映射关系
        
        Args:
            workflow_instance_id: 当前工作流实例ID
            current_depth: 当前递归深度
            max_depth: 最大递归深度
            processed_workflows: 已处理的工作流实例集合
            
        Returns:
            当前工作流及其子工作流的映射关系
        """
        try:
            workflow_id_str = str(workflow_instance_id)
            
            # 防止循环引用和深度超限
            if workflow_id_str in processed_workflows:
                logger.warning(f"检测到循环引用，跳过: {workflow_instance_id}")
                return {"error": "circular_reference", "workflow_instance_id": workflow_id_str}
            
            if current_depth > max_depth:
                logger.warning(f"达到最大递归深度 {max_depth}，停止递归")
                return {"error": "max_depth_reached", "workflow_instance_id": workflow_id_str}
            
            processed_workflows.add(workflow_id_str)
            
            # 1. 获取工作流实例基本信息
            workflow_info = await self._get_workflow_instance_info(workflow_instance_id)
            if not workflow_info:
                return {"error": "workflow_not_found", "workflow_instance_id": workflow_id_str}
            
            # 2. 获取工作流的所有节点实例
            node_instances = await self._get_workflow_node_instances(workflow_instance_id)
            
            # 3. 为每个节点实例查询其subdivision关系
            nodes_with_subdivisions = []
            
            for node_instance in node_instances:
                node_mapping = await self._get_node_subdivision_mapping(
                    node_instance, current_depth, max_depth, processed_workflows
                )
                nodes_with_subdivisions.append(node_mapping)
            
            # 4. 构建当前工作流的完整映射
            mapping = {
                "workflow_instance_id": workflow_id_str,
                "workflow_instance_name": workflow_info["workflow_instance_name"],
                "workflow_base_id": str(workflow_info["workflow_base_id"]),
                "workflow_name": workflow_info["workflow_name"],
                "status": workflow_info["status"],
                "depth": current_depth,
                "total_nodes": len(node_instances),
                "nodes": nodes_with_subdivisions,
                "created_at": str(workflow_info["created_at"]),
                "has_subdivisions": any(node.get("subdivisions") for node in nodes_with_subdivisions)
            }
            
            return mapping
            
        except Exception as e:
            logger.error(f"递归查询工作流映射失败: {e}")
            raise
    
    async def _get_workflow_instance_info(self, workflow_instance_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """获取工作流实例基本信息"""
        try:
            query = """
            SELECT 
                wi.workflow_instance_id,
                wi.workflow_instance_name,
                wi.workflow_base_id,
                wi.status,
                wi.created_at,
                wi.started_at,
                wi.completed_at,
                w.name as workflow_name,
                w.workflow_description
            FROM workflow_instance wi
            JOIN workflow w ON wi.workflow_base_id = w.workflow_base_id 
                AND w.is_current_version = TRUE
            WHERE wi.workflow_instance_id = $1 
                AND wi.is_deleted = FALSE
            """
            
            result = await self.db.fetch_one(query, workflow_instance_id)
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"获取工作流实例信息失败: {e}")
            return None
    
    async def _get_workflow_node_instances(self, workflow_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取工作流的所有节点实例"""
        try:
            query = """
            SELECT 
                ni.node_instance_id,
                ni.node_instance_name,
                ni.node_id,
                ni.node_base_id,
                ni.status as node_instance_status,
                ni.created_at as node_instance_created_at,
                n.name as node_name,
                n.type as node_type,
                n.task_description,
                n.position_x,
                n.position_y
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            WHERE ni.workflow_instance_id = $1 
                AND ni.is_deleted = FALSE
            ORDER BY ni.created_at ASC
            """
            
            results = await self.db.fetch_all(query, workflow_instance_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取工作流节点实例失败: {e}")
            return []
    
    async def _get_node_subdivision_mapping(self, node_instance: Dict[str, Any], 
                                          current_depth: int, max_depth: int,
                                          processed_workflows: Set[str]) -> Dict[str, Any]:
        """获取节点的subdivision映射关系"""
        try:
            node_instance_id = node_instance["node_instance_id"]
            
            # 基本节点信息
            node_mapping = {
                "node_instance_id": str(node_instance_id),
                "node_instance_name": node_instance["node_instance_name"],
                "node_base_id": str(node_instance["node_base_id"]),
                "node_name": node_instance["node_name"],
                "node_type": node_instance["node_type"],
                "task_description": node_instance["task_description"],
                "status": node_instance["node_instance_status"],
                "position": {
                    "x": node_instance.get("position_x"),
                    "y": node_instance.get("position_y")
                },
                "subdivisions": []
            }
            
            # 查询该节点的任务实例
            tasks = await self._get_node_task_instances(node_instance_id)
            
            if tasks:
                node_mapping["tasks"] = []
                
                for task in tasks:
                    task_mapping = {
                        "task_instance_id": str(task["task_instance_id"]),
                        "task_title": task["task_title"],
                        "task_type": task["task_type"],
                        "status": task["status"],
                        "subdivisions": []
                    }
                    
                    # 查询该任务的subdivisions
                    subdivisions = await self._get_task_subdivisions(task["task_instance_id"])
                    
                    for subdivision in subdivisions:
                        subdivision_mapping = await self._get_subdivision_mapping(
                            subdivision, current_depth, max_depth, processed_workflows
                        )
                        task_mapping["subdivisions"].append(subdivision_mapping)
                    
                    node_mapping["tasks"].append(task_mapping)
                
                # 将任务级别的subdivisions提升到节点级别
                all_subdivisions = []
                for task in node_mapping["tasks"]:
                    all_subdivisions.extend(task["subdivisions"])
                node_mapping["subdivisions"] = all_subdivisions
            
            return node_mapping
            
        except Exception as e:
            logger.error(f"获取节点subdivision映射失败: {e}")
            return {
                "node_instance_id": str(node_instance.get("node_instance_id", "")),
                "error": str(e),
                "subdivisions": []
            }
    
    async def _get_node_task_instances(self, node_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的任务实例"""
        try:
            query = """
            SELECT 
                ti.task_instance_id,
                ti.task_title,
                ti.task_type,
                ti.status,
                ti.created_at,
                ti.assigned_at,
                ti.completed_at
            FROM task_instance ti
            WHERE ti.node_instance_id = $1 
                AND ti.is_deleted = FALSE
            ORDER BY ti.created_at ASC
            """
            
            results = await self.db.fetch_all(query, node_instance_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取节点任务实例失败: {e}")
            return []
    
    async def _get_task_subdivisions(self, task_instance_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取任务的subdivisions"""
        try:
            query = """
            SELECT 
                ts.subdivision_id,
                ts.subdivision_name,
                ts.subdivision_description,
                ts.status as subdivision_status,
                ts.sub_workflow_base_id,
                ts.sub_workflow_instance_id,
                ts.context_passed,
                ts.created_at as subdivision_created_at,
                sw.name as sub_workflow_name,
                sw.workflow_description as sub_workflow_description
            FROM task_subdivision ts
            LEFT JOIN workflow sw ON ts.sub_workflow_base_id = sw.workflow_base_id 
                AND sw.is_current_version = TRUE
            WHERE ts.original_task_id = $1 
                AND ts.is_deleted = FALSE
            ORDER BY ts.subdivision_created_at DESC
            """
            
            results = await self.db.fetch_all(query, task_instance_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取任务subdivisions失败: {e}")
            return []
    
    async def _get_subdivision_mapping(self, subdivision: Dict[str, Any], 
                                     current_depth: int, max_depth: int,
                                     processed_workflows: Set[str]) -> Dict[str, Any]:
        """获取subdivision的完整映射关系"""
        try:
            subdivision_mapping = {
                "subdivision_id": str(subdivision["subdivision_id"]),
                "subdivision_name": subdivision["subdivision_name"],
                "subdivision_description": subdivision["subdivision_description"],
                "status": subdivision["subdivision_status"],
                "sub_workflow_base_id": str(subdivision["sub_workflow_base_id"]) if subdivision["sub_workflow_base_id"] else None,
                "sub_workflow_name": subdivision["sub_workflow_name"],
                "sub_workflow_description": subdivision["sub_workflow_description"],
                "context_passed": subdivision["context_passed"],
                "created_at": str(subdivision["subdivision_created_at"]),
                "sub_workflow_mapping": None
            }
            
            # 如果有子工作流实例，递归查询其映射关系
            sub_workflow_instance_id = subdivision["sub_workflow_instance_id"]
            if sub_workflow_instance_id:
                subdivision_mapping["sub_workflow_instance_id"] = str(sub_workflow_instance_id)
                
                # 递归查询子工作流映射
                sub_mapping = await self._get_workflow_mapping_recursive(
                    sub_workflow_instance_id, current_depth + 1, max_depth, processed_workflows
                )
                subdivision_mapping["sub_workflow_mapping"] = sub_mapping
            
            return subdivision_mapping
            
        except Exception as e:
            logger.error(f"获取subdivision映射失败: {e}")
            return {
                "subdivision_id": str(subdivision.get("subdivision_id", "")),
                "error": str(e),
                "sub_workflow_mapping": None
            }
    
    async def get_workflow_node_subdivision_summary(self, workflow_instance_id: uuid.UUID) -> Dict[str, Any]:
        """
        获取工作流节点subdivision摘要信息（不递归，只查询直接子工作流）
        
        Returns:
            节点subdivision摘要信息
        """
        try:
            query = """
            SELECT 
                -- 节点信息
                ni.node_instance_id,
                ni.node_instance_name,
                ni.node_base_id,
                n.name as node_name,
                n.type as node_type,
                
                -- 任务信息
                ti.task_instance_id,
                ti.task_title,
                ti.task_type,
                ti.status as task_status,
                
                -- Subdivision信息
                ts.subdivision_id,
                ts.subdivision_name,
                ts.status as subdivision_status,
                ts.sub_workflow_base_id,
                ts.sub_workflow_instance_id,
                
                -- 子工作流信息
                sw.name as sub_workflow_name,
                swi.workflow_instance_name as sub_workflow_instance_name,
                swi.status as sub_workflow_instance_status,
                
                -- 统计信息
                (SELECT COUNT(*) FROM node n2 
                 WHERE n2.workflow_base_id = ts.sub_workflow_base_id 
                 AND n2.is_deleted = FALSE) as sub_workflow_total_nodes,
                 
                (SELECT COUNT(*) FROM node_instance ni2 
                 JOIN node n2 ON ni2.node_id = n2.node_id
                 WHERE n2.workflow_base_id = ts.sub_workflow_base_id 
                 AND ni2.workflow_instance_id = ts.sub_workflow_instance_id
                 AND ni2.status = 'completed'
                 AND ni2.is_deleted = FALSE) as sub_workflow_completed_nodes
                 
            FROM node_instance ni
            JOIN node n ON ni.node_id = n.node_id
            LEFT JOIN task_instance ti ON ni.node_instance_id = ti.node_instance_id 
                AND ti.is_deleted = FALSE
            LEFT JOIN task_subdivision ts ON ti.task_instance_id = ts.original_task_id 
                AND ts.is_deleted = FALSE
            LEFT JOIN workflow sw ON ts.sub_workflow_base_id = sw.workflow_base_id 
                AND sw.is_current_version = TRUE
            LEFT JOIN workflow_instance swi ON ts.sub_workflow_instance_id = swi.workflow_instance_id
            WHERE ni.workflow_instance_id = $1 
                AND ni.is_deleted = FALSE
            ORDER BY ni.created_at ASC, ti.created_at ASC, ts.subdivision_created_at DESC
            """
            
            results = await self.db.fetch_all(query, workflow_instance_id)
            
            # 组织数据结构
            nodes_map = {}
            
            for result in results:
                node_id = str(result["node_instance_id"])
                
                if node_id not in nodes_map:
                    nodes_map[node_id] = {
                        "node_instance_id": node_id,
                        "node_instance_name": result["node_instance_name"],
                        "node_base_id": str(result["node_base_id"]),
                        "node_name": result["node_name"],
                        "node_type": result["node_type"],
                        "tasks": {},
                        "total_subdivisions": 0
                    }
                
                # 如果有任务实例
                if result["task_instance_id"]:
                    task_id = str(result["task_instance_id"])
                    
                    if task_id not in nodes_map[node_id]["tasks"]:
                        nodes_map[node_id]["tasks"][task_id] = {
                            "task_instance_id": task_id,
                            "task_title": result["task_title"],
                            "task_type": result["task_type"],
                            "task_status": result["task_status"],
                            "subdivisions": []
                        }
                    
                    # 如果有subdivision
                    if result["subdivision_id"]:
                        subdivision_info = {
                            "subdivision_id": str(result["subdivision_id"]),
                            "subdivision_name": result["subdivision_name"],
                            "subdivision_status": result["subdivision_status"],
                            "sub_workflow_base_id": str(result["sub_workflow_base_id"]) if result["sub_workflow_base_id"] else None,
                            "sub_workflow_name": result["sub_workflow_name"],
                            "sub_workflow_instance_id": str(result["sub_workflow_instance_id"]) if result["sub_workflow_instance_id"] else None,
                            "sub_workflow_instance_name": result["sub_workflow_instance_name"],
                            "sub_workflow_instance_status": result["sub_workflow_instance_status"],
                            "sub_workflow_total_nodes": result["sub_workflow_total_nodes"],
                            "sub_workflow_completed_nodes": result["sub_workflow_completed_nodes"]
                        }
                        
                        nodes_map[node_id]["tasks"][task_id]["subdivisions"].append(subdivision_info)
                        nodes_map[node_id]["total_subdivisions"] += 1
            
            # 转换为列表格式
            nodes_list = []
            for node_data in nodes_map.values():
                # 将tasks从字典转换为列表
                node_data["tasks"] = list(node_data["tasks"].values())
                nodes_list.append(node_data)
            
            return {
                "workflow_instance_id": str(workflow_instance_id),
                "nodes": nodes_list,
                "total_nodes": len(nodes_list),
                "total_subdivisions": sum(node.get("total_subdivisions", 0) for node in nodes_list)
            }
            
        except Exception as e:
            logger.error(f"获取工作流节点subdivision摘要失败: {e}")
            raise
    
    async def get_node_subdivision_bindings(self, node_base_id: uuid.UUID, 
                                          workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """
        获取特定节点的所有subdivision绑定关系
        
        Args:
            node_base_id: 节点基础ID
            workflow_base_id: 工作流基础ID
            
        Returns:
            节点的所有subdivision绑定关系
        """
        try:
            query = """
            SELECT 
                -- 节点信息
                n.node_base_id,
                n.name as node_name,
                n.type as node_type,
                n.workflow_base_id,
                
                -- 节点实例信息
                ni.node_instance_id,
                ni.node_instance_name,
                ni.status as node_instance_status,
                ni.workflow_instance_id,
                wi.workflow_instance_name,
                
                -- 任务实例信息
                ti.task_instance_id,
                ti.task_title,
                ti.task_type,
                ti.status as task_status,
                
                -- Subdivision信息
                ts.subdivision_id,
                ts.subdivision_name,
                ts.subdivision_description,
                ts.status as subdivision_status,
                ts.sub_workflow_base_id,
                ts.sub_workflow_instance_id,
                ts.context_passed,
                ts.subdivision_created_at,
                
                -- 子工作流信息
                sw.name as sub_workflow_name,
                sw.workflow_description as sub_workflow_description,
                swi.workflow_instance_name as sub_workflow_instance_name,
                swi.status as sub_workflow_instance_status
                
            FROM node n
            JOIN node_instance ni ON n.node_id = ni.node_id
            JOIN workflow_instance wi ON ni.workflow_instance_id = wi.workflow_instance_id
            LEFT JOIN task_instance ti ON ni.node_instance_id = ti.node_instance_id 
                AND ti.is_deleted = FALSE
            LEFT JOIN task_subdivision ts ON ti.task_instance_id = ts.original_task_id 
                AND ts.is_deleted = FALSE
            LEFT JOIN workflow sw ON ts.sub_workflow_base_id = sw.workflow_base_id 
                AND sw.is_current_version = TRUE
            LEFT JOIN workflow_instance swi ON ts.sub_workflow_instance_id = swi.workflow_instance_id
            WHERE n.node_base_id = $1 
                AND n.workflow_base_id = $2
                AND n.is_current_version = TRUE
                AND n.is_deleted = FALSE
                AND ni.is_deleted = FALSE
                AND wi.is_deleted = FALSE
            ORDER BY wi.created_at DESC, ni.created_at ASC, ti.created_at ASC, ts.subdivision_created_at DESC
            """
            
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return [dict(result) for result in results]
            
        except Exception as e:
            logger.error(f"获取节点subdivision绑定关系失败: {e}")
            raise
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.utcnow().isoformat()


# 使用示例和测试函数
async def test_workflow_mapping_service():
    """测试工作流映射服务"""
    service = WorkflowInstanceMappingService()
    
    # 测试完整映射查询
    try:
        # 需要提供一个真实的workflow_instance_id进行测试
        test_workflow_id = uuid.uuid4()  # 替换为真实ID
        
        print("=== 测试完整工作流映射查询 ===")
        complete_mapping = await service.get_complete_workflow_mapping(test_workflow_id)
        print(f"映射结果: {complete_mapping}")
        
        print("\\n=== 测试节点subdivision摘要查询 ===")
        summary = await service.get_workflow_node_subdivision_summary(test_workflow_id)
        print(f"摘要结果: {summary}")
        
    except Exception as e:
        print(f"测试失败: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_workflow_mapping_service())