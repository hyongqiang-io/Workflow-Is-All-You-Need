import React, { useState, useEffect, useMemo } from 'react';
import { Card, Tag, Button, Modal, Descriptions, Alert, Spin, message } from 'antd';
import { 
  PlayCircleOutlined, 
  CheckCircleOutlined, 
  ClockCircleOutlined, 
  UserOutlined,
  RobotOutlined,
  BranchesOutlined,
  InfoCircleOutlined,
  ShrinkOutlined,
  ExpandOutlined
} from '@ant-design/icons';
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background, 
  MiniMap,
  useNodesState,
  useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import './TaskFlowViewerRefactored.css';
import { executionAPI } from '../services/api';
import TaskSubdivisionModal from './TaskSubdivisionModal';
import { 
  validateAndFixEdges, 
  generateMissingConnections, 
  calculateDependencyBasedLayout,
  getNodeStatusColor,
  formatDuration,
  simpleTopologicalSort
} from '../utils/workflowLayoutUtils';

const { Title, Text } = Typography;
import { Typography } from 'antd';

// 原始API返回的节点数据结构
interface ApiWorkflowNode {
  id?: string;
  node_id?: string;
  node_instance_id?: string;
  name?: string;
  node_name?: string;
  type?: string;
  node_type?: string;
  status: string;
  assignee?: { id: string; name: string; type: 'user' | 'agent' };
  created_at?: string;
  start_at?: string;
  started_at?: string;
  completed_at?: string;
  execution_duration?: number;
  execution_duration_seconds?: number;
  task_count?: number;
  error_message?: string;
}

// 简化的节点数据结构
interface WorkflowNode {
  id: string;
  name: string;
  type: 'start' | 'process' | 'decision' | 'end' | 'human' | 'ai' | 'processor';
  status: 'pending' | 'waiting' | 'running' | 'in_progress' | 'completed' | 'failed' | 'blocked' | 'cancelled';
  assignee?: { id: string; name: string; type: 'user' | 'agent' };
  position: { x: number; y: number };
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  execution_duration?: number;
  task_count?: number;
  error_message?: string;
  
  // 子工作流信息 - 简化
  has_subworkflow?: boolean;
  subworkflow_count?: number;
  expanded_subworkflows?: WorkflowNode[];
}

interface WorkflowData {
  workflow_id: string;
  workflow_name: string;
  workflow_description?: string;
  status: 'draft' | 'active' | 'completed' | 'paused';
  nodes: ApiWorkflowNode[];
  edges: { id: string; source: string; target: string; label?: string }[];
  tasks?: any[];
  current_user_role?: 'creator' | 'assignee' | 'viewer';
  creator?: { id: string; name: string };
  statistics?: any;
}

interface TaskFlowViewerProps {
  workflowId: string;
  currentUserId: string;
  onTaskAction?: (taskId: string, action: 'start' | 'complete' | 'pause') => void;
}

// 优化的节点布局算法 - 使用工具函数
const calculateProperLayout = (nodes: WorkflowNode[], edges: any[]): Record<string, { x: number; y: number }> => {
  // 验证和修复边数据
  const validEdges = validateAndFixEdges(nodes, edges);
  
  // 如果没有有效边，生成默认连接
  const finalEdges = validEdges.length > 0 ? validEdges : generateMissingConnections(nodes);
  
  // 使用基于依赖关系的布局算法
  return calculateDependencyBasedLayout(nodes, finalEdges);
};

// 删除旧的复杂算法
// 删除 improvedTopologicalSort 函数（已移至工具文件）

// 超简化的子工作流展示组件
const CompactSubWorkflow: React.FC<{
  subWorkflow: any;
  onCollapse: () => void;
  onNodeClick?: (node: any) => void;
}> = ({ subWorkflow, onCollapse, onNodeClick }) => {
  const nodes = subWorkflow.nodes || [];
  const completedCount = nodes.filter((n: any) => n.status === 'completed').length;
  const totalCount = nodes.length;
  const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;
  
  // 获取状态分布
  const statusCounts = nodes.reduce((acc: any, node: any) => {
    acc[node.status] = (acc[node.status] || 0) + 1;
    return acc;
  }, {});
  
  return (
    <div className="compact-subworkflow" style={{
      border: '1px solid #52c41a',
      borderRadius: '6px',
      backgroundColor: '#f6ffed',
      padding: '8px',
      margin: '4px 0',
      fontSize: '12px'
    }}>
      {/* 标题栏 */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '6px'
      }}>
        <span style={{ fontWeight: 'bold', color: '#52c41a' }}>
          📋 {subWorkflow.subdivision_name || '子工作流'}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ fontSize: '11px', color: '#666' }}>
            {completedCount}/{totalCount}
          </span>
          <Button type="text" size="small" icon={<ShrinkOutlined />} onClick={onCollapse} />
        </div>
      </div>
      
      {/* 节点网格 - 最多显示8个 */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(4, 1fr)', 
        gap: '3px',
        maxHeight: '60px',
        overflow: 'hidden'
      }}>
        {nodes.slice(0, 8).map((node: any, index: number) => (
          <div
            key={node.id || index}
            onClick={() => onNodeClick?.(node)}
            title={`${node.node_name || `节点${index + 1}`} (${node.status})`}
            style={{
              width: '40px',
              height: '24px',
              border: '1px solid #d9d9d9',
              borderRadius: '3px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '9px',
              backgroundColor: getNodeStatusColor(node.status),
              opacity: node.status === 'completed' ? 0.8 : 1,
              cursor: 'pointer',
              color: '#fff',
              fontWeight: 'bold'
            }}
          >
            {(node.node_name || `N${index + 1}`).slice(0, 2)}
          </div>
        ))}
        {totalCount > 8 && (
          <div style={{
            width: '40px', height: '24px', 
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '9px', color: '#999', border: '1px dashed #d9d9d9',
            borderRadius: '3px'
          }}>
            +{totalCount - 8}
          </div>
        )}
      </div>
      
      {/* 状态统计 - 仅显示非零的状态 */}
      {Object.keys(statusCounts).length > 0 && (
        <div style={{ 
          marginTop: '6px', 
          display: 'flex', 
          gap: '6px',
          fontSize: '10px'
        }}>
          {Object.entries(statusCounts)
            .filter(([, count]) => (count as number) > 0)
            .map(([status, count]) => (
              <span 
                key={status}
                style={{ 
                  color: getNodeStatusColor(status),
                  fontWeight: 'bold'
                }}
              >
                {`${status}: ${count}`}
              </span>
            ))}
        </div>
      )}
    </div>
  );
};

// 优化的节点组件
const OptimizedNodeComponent: React.FC<{
  data: {
    node: WorkflowNode;
    isAssignedToMe: boolean;
    expanded_subworkflows?: any[];
    onToggleExpand?: () => void;
    onNodeClick?: () => void;
  };
  selected?: boolean;
}> = ({ data, selected }) => {
  const { node, isAssignedToMe, expanded_subworkflows, onToggleExpand, onNodeClick } = data;
  const statusColor = getNodeStatusColor(node.status);
  
  return (
    <div style={{ position: 'relative' }}>
      {/* 主节点 */}
      <div
        onClick={onNodeClick}
        className={`workflow-node ${node.status} ${selected ? 'selected' : ''}`}
        style={{
          minWidth: '160px',
          padding: '10px',
          border: `2px solid ${statusColor}`,
          borderRadius: '8px',
          backgroundColor: isAssignedToMe ? '#fff7e6' : '#ffffff',
          boxShadow: selected 
            ? '0 6px 16px rgba(0,0,0,0.15)' 
            : '0 2px 8px rgba(0,0,0,0.08)',
          cursor: 'pointer',
          transition: 'all 0.2s ease'
        }}
      >
        {/* 节点标题 */}
        <div style={{ 
          fontWeight: 600, 
          fontSize: '13px', 
          marginBottom: '6px',
          color: '#262626',
          lineHeight: '1.2'
        }}>
          {node.name}
        </div>
        
        {/* 状态和操作栏 */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '4px'
        }}>
          <Tag color={statusColor} style={{ 
            margin: 0,
            fontSize: '11px',
            lineHeight: '16px',
            padding: '0 6px'
          }}>
            {node.status}
          </Tag>
          
          {node.has_subworkflow && (
            <Button
              type="text"
              size="small"
              icon={expanded_subworkflows?.length ? <ShrinkOutlined /> : <ExpandOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand?.();
              }}
              style={{ 
                padding: '2px 4px', 
                height: '20px',
                fontSize: '11px'
              }}
            >
              {node.subworkflow_count || 0}
            </Button>
          )}
        </div>
        
        {/* 执行者信息 */}
        {node.assignee && (
          <div style={{ 
            marginTop: '6px', 
            fontSize: '11px', 
            color: '#666',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            {node.assignee.type === 'user' ? 
              <UserOutlined style={{ fontSize: '10px' }} /> : 
              <RobotOutlined style={{ fontSize: '10px' }} />
            }
            <span style={{ 
              maxWidth: '100px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              {node.assignee.name}
            </span>
          </div>
        )}
        
        {/* 执行时间 */}
        {node.execution_duration && (
          <div style={{ 
            fontSize: '10px', 
            color: '#999', 
            marginTop: '4px'
          }}>
            ⏱️ {formatDuration(node.execution_duration)}
          </div>
        )}
      </div>
      
      {/* 展开的子工作流 - 紧凑显示 */}
      {expanded_subworkflows && expanded_subworkflows.length > 0 && (
        <div style={{ 
          marginTop: '8px',
          position: 'relative',
          zIndex: 10
        }}>
          {expanded_subworkflows.map((subWorkflow, index) => (
            <CompactSubWorkflow
              key={subWorkflow.subdivision_id || index}
              subWorkflow={subWorkflow}
              onCollapse={onToggleExpand!}
              onNodeClick={onNodeClick}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// Define nodeTypes outside component to prevent recreation warnings
const nodeTypes = {
  default: OptimizedNodeComponent
};

const TaskFlowViewerRefactored: React.FC<TaskFlowViewerProps> = ({
  workflowId,
  currentUserId,
  onTaskAction
}) => {
  const [workflowData, setWorkflowData] = useState<WorkflowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<any>(null);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [subdivisionModalVisible, setSubdivisionModalVisible] = useState(false);
  const [subdivisionTaskId, setSubdivisionTaskId] = useState<string>('');
  
  useEffect(() => {
    loadWorkflowData();
  }, [workflowId]);

  const loadWorkflowData = async () => {
    setLoading(true);
    try {
      const response: any = await executionAPI.getWorkflowTaskFlow(workflowId);
      if (response && response.success && response.data) {
        setWorkflowData(response.data);
      }
    } catch (error) {
      console.error('加载工作流数据失败:', error);
      message.error('加载工作流数据失败');
    } finally {
      setLoading(false);
    }
  };

  // 转换和布局节点 - 优化的数据处理
  const { nodes, edges } = useMemo(() => {
    if (!workflowData) return { nodes: [], edges: [] };

    console.log('🔄 开始处理工作流数据:', {
      nodeCount: workflowData.nodes?.length || 0,
      edgeCount: workflowData.edges?.length || 0
    });

    // 转换节点数据 - 统一数据格式
    const workflowNodes: WorkflowNode[] = (workflowData.nodes || []).map(node => {
      // 统一ID处理
      const nodeId = node.node_instance_id || node.id || `node-${Math.random()}`;
      
      // 查找对应的任务信息（保持兼容性）
      const relatedTasks = (workflowData.tasks || []).filter((task: any) => 
        task.node_instance_id === nodeId
      );
      const primaryTask = relatedTasks.length > 0 ? relatedTasks[0] : null;
      
      return {
        id: nodeId,
        name: node.node_name || node.name || '未命名节点',
        type: (node.node_type || node.type || 'process') as WorkflowNode['type'],
        status: (node.status || 'pending') as WorkflowNode['status'],
        assignee: primaryTask?.assignee || node.assignee || undefined,
        position: { x: 0, y: 0 }, // 稍后计算
        created_at: node.created_at || node.start_at,
        started_at: node.started_at || node.start_at,
        completed_at: node.completed_at,
        execution_duration: node.execution_duration_seconds || node.execution_duration,
        task_count: node.task_count || relatedTasks.length,
        error_message: node.error_message,
        // 简化子工作流判断
        has_subworkflow: (node.task_count || relatedTasks.length) > 0,
        subworkflow_count: node.task_count || relatedTasks.length
      };
    });

    console.log('✅ 节点数据转换完成:', workflowNodes.length);

    // 验证和修复边数据
    const originalEdges = workflowData.edges || [];
    console.log('🔗 开始处理边数据:', originalEdges.length, '条原始边');
    
    // 使用工具函数处理边数据
    const validatedEdges = validateAndFixEdges(workflowNodes, originalEdges);
    console.log('✅ 边数据验证完成:', validatedEdges.length, '条有效边');
    
    // 如果没有有效的边，生成默认连接
    const finalEdges = validatedEdges.length > 0 ? 
      validatedEdges : 
      generateMissingConnections(workflowNodes);
    
    console.log('🎯 最终边数据:', finalEdges.length, '条边');

    // 使用优化的布局算法计算位置
    const positions = calculateProperLayout(workflowNodes, finalEdges);
    
    // 应用计算的位置
    workflowNodes.forEach(node => {
      const calculatedPosition = positions[node.id];
      if (calculatedPosition) {
        node.position = calculatedPosition;
      } else {
        console.warn(`⚠️ 节点 ${node.name} 没有计算到位置，使用默认位置`);
        node.position = { x: 100, y: 100 };
      }
    });

    console.log('📍 节点布局计算完成');

    // 转换为ReactFlow节点格式
    const reactFlowNodes: Node[] = workflowNodes.map(node => ({
      id: node.id,
      type: 'default',
      position: node.position,
      data: {
        node,
        isAssignedToMe: node.assignee?.id === currentUserId,
        expanded_subworkflows: expandedNodes.has(node.id) ? [] : undefined, // TODO: 加载实际子工作流数据
        onToggleExpand: () => toggleNodeExpansion(node.id),
        onNodeClick: () => handleNodeClick(node)
      }
    }));

    // 转换边为ReactFlow格式
    const reactFlowEdges: Edge[] = finalEdges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'smoothstep',
      style: { stroke: '#1890ff', strokeWidth: 2 }
    }));

    console.log('🎨 ReactFlow数据准备完成:', {
      nodes: reactFlowNodes.length,
      edges: reactFlowEdges.length
    });

    return { nodes: reactFlowNodes, edges: reactFlowEdges };
  }, [workflowData, expandedNodes, currentUserId]);

  const [reactFlowNodes, setNodes, onNodesChange] = useNodesState(nodes);
  const [reactFlowEdges, setEdges, onEdgesChange] = useEdgesState(edges);

  // 同步更新
  useEffect(() => {
    setNodes(nodes);
    setEdges(edges);
  }, [nodes, edges, setNodes, setEdges]);

  const toggleNodeExpansion = async (nodeId: string) => {
    if (expandedNodes.has(nodeId)) {
      setExpandedNodes(prev => {
        const newSet = new Set(prev);
        newSet.delete(nodeId);
        return newSet;
      });
    } else {
      try {
        // 加载子工作流数据
        const response: any = await executionAPI.getWorkflowSubdivisionInfo(workflowId);
        // TODO: 处理响应，更新展开状态
        setExpandedNodes(prev => {
          const newSet = new Set(prev);
          newSet.add(nodeId);
          return newSet;
        });
      } catch (error) {
        message.error('加载子工作流失败');
      }
    }
  };

  const handleNodeClick = (node: WorkflowNode) => {
    setSelectedTask(node);
    setDetailModalVisible(true);
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>加载工作流数据中...</div>
        </div>
      </Card>
    );
  }

  if (!workflowData) {
    return (
      <Card>
        <Alert message="加载失败" description="无法加载工作流数据" type="error" showIcon />
      </Card>
    );
  }

  return (
    <div>
      {/* 工作流信息头部 */}
      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>{workflowData.workflow_name}</Title>
            <Text type="secondary">{workflowData.workflow_description}</Text>
          </div>
          <Tag color="blue">{workflowData.status}</Tag>
        </div>
      </Card>

      {/* 优化的流程图 */}
      <Card title="工作流程图">
        <div style={{ 
          height: '600px', 
          width: '100%',
          position: 'relative'
        }}>
          <ReactFlow
            nodes={reactFlowNodes}
            edges={reactFlowEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.1 }}
            style={{ width: '100%', height: '100%' }}
          >
            <Controls />
            <Background />
            <MiniMap />
          </ReactFlow>
        </div>
      </Card>

      {/* 节点详情模态框 */}
      <Modal
        title="节点详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={600}
      >
        {selectedTask && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="节点名称">{selectedTask.name}</Descriptions.Item>
            <Descriptions.Item label="节点类型">
              <Tag>{selectedTask.type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedTask.status === 'completed' ? 'green' : 'blue'}>
                {selectedTask.status}
              </Tag>
            </Descriptions.Item>
            {selectedTask.assignee && (
              <Descriptions.Item label="执行者">
                {selectedTask.assignee.name}
              </Descriptions.Item>
            )}
            {selectedTask.created_at && (
              <Descriptions.Item label="创建时间">
                {new Date(selectedTask.created_at).toLocaleString()}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>

      {/* 任务细分模态框 */}
      <TaskSubdivisionModal
        visible={subdivisionModalVisible}
        onCancel={() => setSubdivisionModalVisible(false)}
        onSuccess={() => {
          setSubdivisionModalVisible(false);
          loadWorkflowData(); // 重新加载数据
        }}
        taskId={subdivisionTaskId}
        taskTitle=""
        taskDescription=""
      />
    </div>
  );
};

export default TaskFlowViewerRefactored;