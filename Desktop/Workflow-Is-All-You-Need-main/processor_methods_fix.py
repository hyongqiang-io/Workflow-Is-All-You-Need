#!/usr/bin/env python3

# 直接修复ProcessorRepository的方法问题
import uuid
from typing import Dict, Any, List

def get_additional_methods():
    """返回要添加到ProcessorRepository的方法"""
    
    async def get_processors_by_node(self, node_base_id: uuid.UUID, workflow_base_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的处理器列表"""
        try:
            query = """
                SELECT np.*, p.name as processor_name, p.type as processor_type,
                       u.username, a.agent_name
                FROM node_processor np
                JOIN processor p ON p.processor_id = np.processor_id AND p.is_deleted = FALSE
                LEFT JOIN "user" u ON u.user_id = p.user_id AND u.is_deleted = FALSE
                LEFT JOIN agent a ON a.agent_id = p.agent_id AND a.is_deleted = FALSE
                JOIN node n ON n.node_id = np.node_id AND n.is_current_version = TRUE
                WHERE n.node_base_id = $1 AND n.workflow_base_id = $2
                ORDER BY np.created_at ASC
            """
            results = await self.db.fetch_all(query, node_base_id, workflow_base_id)
            return results
        except Exception as e:
            self.logger.error(f"获取节点处理器列表失败: {e}")
            raise
    
    return {
        'get_processors_by_node': get_processors_by_node
    }

if __name__ == "__main__":
    # 动态添加方法到ProcessorRepository
    import sys
    sys.path.insert(0, '.')
    
    from workflow_framework.repositories.processor.processor_repository import ProcessorRepository
    
    methods = get_additional_methods()
    
    # 动态添加方法
    for method_name, method_func in methods.items():
        setattr(ProcessorRepository, method_name, method_func)
        print(f"添加方法: {method_name}")
    
    # 测试
    repo = ProcessorRepository()
    print('Has get_processors_by_node:', hasattr(repo, 'get_processors_by_node'))