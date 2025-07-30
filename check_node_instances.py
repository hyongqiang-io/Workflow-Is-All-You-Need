import asyncio
from workflow_framework.repositories.instance.node_instance_repository import NodeInstanceRepository
from workflow_framework.models.instance import NodeInstanceStatus

async def check_node_instances():
    repo = NodeInstanceRepository()
    
    # 获取等待执行的节点实例
    pending_instances = await repo.get_pending_instances()
    print(f'等待执行的节点实例: {len(pending_instances)} 个')
    
    for inst in pending_instances[:5]:
        print(f'  - 节点实例ID: {inst["node_instance_id"]}, 工作流实例ID: {inst["workflow_instance_id"]}, 节点ID: {inst["node_id"]}, 状态: {inst["status"]}, 节点名称: {inst.get("node_name", "未知")}, 节点类型: {inst.get("node_type", "未知")}')
    
    # 获取运行中的节点实例
    running_instances = await repo.get_running_instances()
    print(f'\n运行中的节点实例: {len(running_instances)} 个')
    
    for inst in running_instances[:5]:
        print(f'  - 节点实例ID: {inst["node_instance_id"]}, 工作流实例ID: {inst["workflow_instance_id"]}, 节点ID: {inst["node_id"]}, 状态: {inst["status"]}, 节点名称: {inst.get("node_name", "未知")}, 节点类型: {inst.get("node_type", "未知")}')
    
    # 检查是否有工作流实例
    from workflow_framework.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
    workflow_repo = WorkflowInstanceRepository()
    
    # 获取最近的工作流实例
    try:
        query = "SELECT * FROM workflow_instance ORDER BY created_at DESC LIMIT 5"
        workflow_instances = await workflow_repo.db.fetch_all(query)
        print(f'\n最近的工作流实例: {len(workflow_instances)} 个')
        
        for wi in workflow_instances:
            print(f'  - 工作流实例ID: {wi["workflow_instance_id"]}, 名称: {wi.get("workflow_instance_name", "未知")}, 状态: {wi.get("status", "未知")}, 创建时间: {wi.get("created_at", "未知")}')
            
            # 获取该工作流实例的节点实例
            node_instances = await repo.get_instances_by_workflow_instance(wi["workflow_instance_id"])
            print(f'    该工作流实例的节点实例: {len(node_instances)} 个')
            
            for ni in node_instances:
                print(f'      - 节点实例ID: {ni["node_instance_id"]}, 节点名称: {ni.get("node_name", "未知")}, 节点类型: {ni.get("node_type", "未知")}, 状态: {ni["status"]}')
    except Exception as e:
        print(f'获取工作流实例失败: {e}')

if __name__ == '__main__':
    asyncio.run(check_node_instances())