import React from 'react';

// 导入主工作流的CustomInstanceNode组件
import { CustomInstanceNode } from './CustomInstanceNode';

interface SubWorkflowInfo {
  has_subdivision: boolean;
  subdivision_count: number;
  subdivision_status?: 'draft' | 'running' | 'completed' | 'failed' | 'cancelled';
  is_expandable: boolean;
  expansion_level: number;
}

interface TaskNodeData {
  id: string;
  name: string;
  description: string;
  type: 'start' | 'process' | 'decision' | 'end' | 'human' | 'ai';
  status: 'pending' | 'in_progress' | 'running' | 'assigned' | 'completed' | 'failed' | 'error' | 'blocked' | 'paused';
  assignee?: {
    id: string;
    name: string;
    type: 'user' | 'agent';
  };
  priority?: number;
  position: { x: number; y: number };
  estimated_duration?: number;
  actual_duration?: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface ExpandableSubWorkflowNodeProps {
  data: {
    task: TaskNodeData;
    isAssignedToMe: boolean;
    isCreator: boolean;
    subWorkflowInfo?: SubWorkflowInfo;
    isExpanded?: boolean;
    isLoading?: boolean;
    onStartTask?: (taskId: string) => void;
    onCompleteTask?: (taskId: string) => void;
    onPauseTask?: (taskId: string) => void;
    onSubdivideTask?: (taskId: string, taskTitle: string, taskDescription?: string) => void;
    onExpandNode?: (nodeId: string) => void;
    onCollapseNode?: (nodeId: string) => void;
    onNodeClick?: (task: TaskNodeData) => void;
  };
  selected?: boolean;
}

const ExpandableSubWorkflowNode: React.FC<ExpandableSubWorkflowNodeProps> = ({ 
  data, 
  selected = false 
}) => {
  const { task } = data;
  
  // 将ExpandableSubWorkflowNode的数据格式转换为CustomInstanceNode需要的格式
  const nodeData = {
    // 基础信息映射
    label: task.name,
    status: task.status,
    nodeId: task.id,
    
    // 添加任务特定的标识
    showTaskActions: true,
    task: {
      task_instance_id: task.id,
      task_title: task.name,
      task_type: task.type,
      priority: task.priority,
      estimated_duration: task.estimated_duration,
      isAssignedToMe: data.isAssignedToMe,
      isCreator: data.isCreator
    },
    
    // 处理器信息
    processor_name: task.assignee?.name,
    processor_type: task.assignee?.type,
    
    // subdivision相关
    subWorkflowInfo: data.subWorkflowInfo,
    isExpanded: data.isExpanded,
    isLoading: data.isLoading,
    
    // 回调函数映射
    onNodeClick: () => data.onNodeClick?.(task),
    onNodeDoubleClick: () => data.onNodeClick?.(task),
    onExpandNode: data.onExpandNode,
    onCollapseNode: data.onCollapseNode,
    
    // 任务操作回调
    onStartTask: data.onStartTask,
    onCompleteTask: data.onCompleteTask,
    onPauseTask: data.onPauseTask,
    onSubdivideTask: (taskId: string) => data.onSubdivideTask?.(taskId, task.name, task.description)
  };

  return <CustomInstanceNode data={nodeData} selected={selected} />;
};

export default ExpandableSubWorkflowNode;