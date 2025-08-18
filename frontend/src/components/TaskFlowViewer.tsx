import React, { useState, useEffect } from 'react';
import { Card, Tag, Button, Modal, Descriptions, Timeline, Badge, Space, Typography, Alert, Spin, message } from 'antd';
import { 
  PlayCircleOutlined, 
  CheckCircleOutlined, 
  ClockCircleOutlined, 
  UserOutlined,
  RobotOutlined,
  BranchesOutlined,
  EyeOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background, 
  MiniMap,
  NodeTypes,
  useNodesState,
  useEdgesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import { executionAPI } from '../services/api';
import TaskSubdivisionModal from './TaskSubdivisionModal';

const { Title, Text, Paragraph } = Typography;

interface TaskNode {
  id: string;
  name: string;
  description: string;
  type: 'start' | 'process' | 'decision' | 'end' | 'human' | 'ai';
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'blocked';
  assignee?: {
    id: string;
    name: string;
    type: 'user' | 'agent';
  };
  position: { x: number; y: number };
  estimated_duration?: number;
  actual_duration?: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface TaskFlow {
  workflow_id: string;
  workflow_name?: string;
  workflow_description?: string;
  status?: 'draft' | 'active' | 'completed' | 'paused';
  workflow_instance_status?: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  executor_username?: string;
  creator?: {
    id: string;
    name: string;
  };
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  nodes: any[];
  tasks?: any[];
  edges?: Array<{
    id: string;
    source: string;
    target: string;
    label?: string;
  }>;
  current_user_role?: 'creator' | 'assignee' | 'viewer';
  assigned_tasks?: TaskNode[];
  statistics?: {
    total_nodes: number;
    total_tasks: number;
    node_status_count: {
      [key: string]: number;
    };
    task_status_count: {
      [key: string]: number;
    };
    progress_percentage: number;
    is_completed: boolean;
    is_running: boolean;
    is_failed: boolean;
  };
}

interface TaskFlowViewerProps {
  workflowId: string;
  currentUserId: string;
  onTaskAction?: (taskId: string, action: 'start' | 'complete' | 'pause') => void;
}

// 自定义节点组件
const TaskNodeComponent: React.FC<{ data: any }> = ({ data }) => {
  const { task, isAssignedToMe, isCreator } = data;
  
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return '#faad14';
      case 'in_progress': 
      case 'running':
      case 'assigned': return '#1890ff';
      case 'completed': return '#52c41a';
      case 'failed': 
      case 'error': return '#ff4d4f';
      case 'blocked': return '#722ed1';
      case 'paused': return '#fa8c16';
      default: return '#d9d9d9';
    }
  };

  const getStatusBackgroundColor = (status: string) => {
    switch (status) {
      case 'pending': return '#fff7e6';
      case 'in_progress': 
      case 'running':
      case 'assigned': return '#e6f7ff';
      case 'completed': return '#f6ffed';
      case 'failed': 
      case 'error': return '#fff2f0';
      case 'blocked': return '#f9f0ff';
      case 'paused': return '#fff2e8';
      default: return '#fafafa';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <ClockCircleOutlined />;
      case 'in_progress': return <PlayCircleOutlined />;
      case 'completed': return <CheckCircleOutlined />;
      case 'failed': return <InfoCircleOutlined />;
      case 'blocked': return <InfoCircleOutlined />;
      default: return <ClockCircleOutlined />;
    }
  };

  const getNodeTypeIcon = (type: string) => {
    switch (type) {
      case 'start': return <PlayCircleOutlined />;
      case 'end': return <CheckCircleOutlined />;
      case 'human': return <UserOutlined />;
      case 'ai': return <RobotOutlined />;
      case 'decision': return <BranchesOutlined />;
      default: return <InfoCircleOutlined />;
    }
  };

  const isHighlighted = isAssignedToMe || isCreator;

  return (
    <div 
      style={{
        padding: '12px',
        borderRadius: '8px',
        border: isHighlighted ? '2px solid #1890ff' : `2px solid ${getStatusColor(task.status)}`,
        backgroundColor: getStatusBackgroundColor(task.status),
        minWidth: '150px',
        boxShadow: isHighlighted ? '0 2px 8px rgba(24, 144, 255, 0.2)' : `0 2px 8px ${getStatusColor(task.status)}33`
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
        {getNodeTypeIcon(task.type)}
        <Text strong style={{ marginLeft: '4px', fontSize: '12px' }}>
          {task.name}
        </Text>
      </div>
      
      <div style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Tag 
          color={getStatusColor(task.status)} 
          icon={getStatusIcon(task.status)}
          style={{ fontWeight: 'bold', fontSize: '11px' }}
        >
          {task.status === 'pending' ? '待处理' :
           task.status === 'in_progress' ? '进行中' :
           task.status === 'running' ? '运行中' :
           task.status === 'assigned' ? '已分配' :
           task.status === 'completed' ? '已完成' :
           task.status === 'failed' ? '失败' :
           task.status === 'error' ? '错误' :
           task.status === 'blocked' ? '阻塞' :
           task.status === 'paused' ? '暂停' : '未知'}
        </Tag>
      </div>

      {task.assignee && (
        <div style={{ marginBottom: '4px' }}>
          <Text type="secondary" style={{ fontSize: '10px' }}>
            {task.assignee.type === 'user' ? <UserOutlined /> : <RobotOutlined />}
            {' '}{task.assignee.name}
          </Text>
        </div>
      )}

      {isAssignedToMe && task.status === 'pending' && (
        <Button 
          type="primary" 
          size="small" 
          style={{ width: '100%', marginTop: '4px' }}
          onClick={() => data.onStartTask?.(task.id)}
        >
          开始任务
        </Button>
      )}

      {isAssignedToMe && task.status === 'in_progress' && (
        <Space direction="vertical" size="small" style={{ width: '100%', marginTop: '4px' }}>
          <Space size="small" style={{ width: '100%' }}>
            <Button 
              type="primary" 
              size="small" 
              style={{ flex: 1 }}
              onClick={() => data.onCompleteTask?.(task.id)}
            >
              完成任务
            </Button>
            <Button 
              size="small" 
              onClick={() => data.onPauseTask?.(task.id)}
            >
              暂停
            </Button>
          </Space>
          <Button 
            size="small" 
            icon={<BranchesOutlined />}
            style={{ width: '100%' }}
            onClick={() => data.onSubdivideTask?.(task.id, task.name, task.description)}
          >
            细分任务
          </Button>
        </Space>
      )}
    </div>
  );
};

const nodeTypes: NodeTypes = {
  taskNode: TaskNodeComponent,
};

const TaskFlowViewer: React.FC<TaskFlowViewerProps> = ({ 
  workflowId, 
  currentUserId, 
  onTaskAction 
}) => {
  const [taskFlow, setTaskFlow] = useState<TaskFlow | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<TaskNode | null>(null);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [subdivisionModalVisible, setSubdivisionModalVisible] = useState(false);
  const [subdivisionTaskId, setSubdivisionTaskId] = useState<string>('');
  const [subdivisionTaskTitle, setSubdivisionTaskTitle] = useState<string>('');
  const [subdivisionTaskDescription, setSubdivisionTaskDescription] = useState<string>('');
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    loadTaskFlow();
  }, [workflowId]);

  useEffect(() => {
    if (taskFlow) {
      updateFlowView();
    }
  }, [taskFlow]);

  const loadTaskFlow = async () => {
    setLoading(true);
    try {
      const response: any = await executionAPI.getWorkflowTaskFlow(workflowId);
      if (response && response.success && response.data) {
        setTaskFlow(response.data);
      } else {
        console.error('API响应格式错误:', response);
      }
    } catch (error) {
      console.error('加载任务流程失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateFlowView = () => {
    if (!taskFlow) return;

    // 转换节点为ReactFlow格式（使用实时数据库状态）
    const flowNodes: Node[] = (taskFlow.nodes || []).map((node, index) => {
      // 查找该节点关联的任务以获取分配信息
      const nodeTasks = (taskFlow.tasks || []).filter(task => task.node_instance_id === node.node_instance_id);
      const primaryTask = nodeTasks.length > 0 ? nodeTasks[0] : null;
      
      return {
        id: node.node_instance_id || `node-${index}`,
        type: 'taskNode',
        position: { x: (index % 3) * 300, y: Math.floor(index / 3) * 200 },
        data: {
          task: {
            id: node.node_instance_id,
            name: node.node_name || '未命名节点',
            type: node.node_type || 'process',
            status: node.status || 'pending', // 来自数据库的实时状态
            description: node.description || '',
            assignee: primaryTask?.assignee || null, // 从任务中获取分配信息
            position: { x: (index % 3) * 300, y: Math.floor(index / 3) * 200 },
            execution_duration_seconds: node.execution_duration_seconds,
            retry_count: node.retry_count,
            task_count: node.task_count,
            error_message: node.error_message,
            start_at: node.start_at,
            completed_at: node.completed_at
          },
          isAssignedToMe: primaryTask?.assignee?.id === currentUserId,
          isCreator: taskFlow.creator ? currentUserId === taskFlow.creator.id : false,
          onStartTask: handleStartTask,
          onCompleteTask: handleCompleteTask,
          onPauseTask: handlePauseTask,
          onSubdivideTask: handleSubdivideTask
        }
      };
    });

    // 转换边为ReactFlow格式（使用实际的边缘数据）
    const flowEdges: Edge[] = (taskFlow.edges || []).map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: 'smoothstep',
      style: { stroke: '#1890ff', strokeWidth: 2 }
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  };

  const handleStartTask = (taskId: string) => {
    onTaskAction?.(taskId, 'start');
    // 更新本地状态
    setTaskFlow(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        nodes: prev.nodes.map(node => 
          node.id === taskId 
            ? { ...node, status: 'in_progress', started_at: new Date().toISOString() }
            : node
        )
      };
    });
  };

  const handleCompleteTask = (taskId: string) => {
    onTaskAction?.(taskId, 'complete');
    // 更新本地状态
    setTaskFlow(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        nodes: prev.nodes.map(node => 
          node.id === taskId 
            ? { ...node, status: 'completed', completed_at: new Date().toISOString() }
            : node
        )
      };
    });
  };

  const handlePauseTask = (taskId: string) => {
    onTaskAction?.(taskId, 'pause');
    // 更新本地状态
    setTaskFlow(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        nodes: prev.nodes.map(node => 
          node.id === taskId 
            ? { ...node, status: 'blocked' }
            : node
        )
      };
    });
  };

  const handleSubdivideTask = (taskId: string, taskTitle: string, taskDescription?: string) => {
    setSubdivisionTaskId(taskId);
    setSubdivisionTaskTitle(taskTitle);
    setSubdivisionTaskDescription(taskDescription || '');
    setSubdivisionModalVisible(true);
  };

  const handleSubdivisionSuccess = () => {
    setSubdivisionModalVisible(false);
    message.success('任务细分创建成功！');
    // 可以选择重新加载任务流程
    loadTaskFlow();
  };

  const handleSubdivisionCancel = () => {
    setSubdivisionModalVisible(false);
    setSubdivisionTaskId('');
    setSubdivisionTaskTitle('');
    setSubdivisionTaskDescription('');
  };

  const handleNodeClick = (event: any, node: Node) => {
    const task = taskFlow?.nodes.find(n => n.id === node.id);
    if (task) {
      setSelectedTask(task);
      setDetailModalVisible(true);
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>加载任务流程中...</div>
        </div>
      </Card>
    );
  }

  if (!taskFlow) {
    return (
      <Card>
        <Alert
          message="加载失败"
          description="无法加载任务流程信息"
          type="error"
          showIcon
        />
      </Card>
    );
  }

  return (
    <div>
      {/* 工作流信息 */}
      <Card style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={4} style={{ margin: 0 }}>
              {taskFlow.workflow_name || '未命名工作流'}
            </Title>
            <Text type="secondary">{taskFlow.workflow_description || '暂无描述'}</Text>
            {taskFlow.statistics && (
              <div style={{ marginTop: '8px' }}>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  进度: {taskFlow.statistics.progress_percentage}% 
                  ({taskFlow.statistics.node_status_count['completed'] || 0}/{taskFlow.statistics.total_nodes} 节点完成)
                </Text>
              </div>
            )}
          </div>
          <div>
            <Tag color={
              taskFlow.workflow_instance_status === 'running' ? 'blue' :
              taskFlow.workflow_instance_status === 'completed' ? 'green' :
              taskFlow.workflow_instance_status === 'failed' ? 'red' :
              taskFlow.workflow_instance_status === 'paused' ? 'orange' : 'default'
            }>
              {taskFlow.workflow_instance_status === 'running' ? '运行中' :
               taskFlow.workflow_instance_status === 'completed' ? '已完成' :
               taskFlow.workflow_instance_status === 'failed' ? '执行失败' :
               taskFlow.workflow_instance_status === 'paused' ? '已暂停' :
               taskFlow.workflow_instance_status === 'pending' ? '等待执行' : '未知状态'}
            </Tag>
            {taskFlow.creator && (
              <Text type="secondary" style={{ marginLeft: '8px' }}>
                执行者: {taskFlow.creator.name}
              </Text>
            )}
            {taskFlow.created_at && (
              <div style={{ marginTop: '4px' }}>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  创建时间: {formatDate(taskFlow.created_at)}
                </Text>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* 角色提示 */}
      <Card style={{ marginBottom: '16px' }}>
        <Alert
          message={
            taskFlow.current_user_role === 'creator' 
              ? '您是这个工作流的创建者，可以看到完整的流程和所有任务状态'
              : taskFlow.current_user_role === 'assignee'
              ? '您是被分配的任务执行者，高亮显示的是分配给您的任务'
              : '您正在查看工作流的执行状态'
          }
          type="info"
          showIcon
          icon={<InfoCircleOutlined />}
        />
      </Card>

      {/* 任务流程图 */}
      <Card title="任务流程" style={{ marginBottom: '16px' }}>
        <div style={{ height: '600px' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            nodeTypes={nodeTypes}
            fitView
          >
            <Controls />
            <Background />
            <MiniMap />
          </ReactFlow>
        </div>
      </Card>

      {/* 我的任务列表（仅对被分配者显示） */}
      {taskFlow.current_user_role === 'assignee' && taskFlow.assigned_tasks && taskFlow.assigned_tasks.length > 0 && (
        <Card title="我的任务" style={{ marginBottom: '16px' }}>
          {taskFlow.assigned_tasks.map(task => (
            <Card 
              key={task.id} 
              size="small" 
              style={{ marginBottom: '8px' }}
              extra={
                <Space>
                  {task.status === 'pending' && (
                    <Button 
                      type="primary" 
                      size="small"
                      onClick={() => handleStartTask(task.id)}
                    >
                      开始任务
                    </Button>
                  )}
                  {task.status === 'in_progress' && (
                    <Space>
                      <Button 
                        type="primary" 
                        size="small"
                        onClick={() => handleCompleteTask(task.id)}
                      >
                        完成任务
                      </Button>
                      <Button 
                        size="small"
                        onClick={() => handlePauseTask(task.id)}
                      >
                        暂停
                      </Button>
                      <Button 
                        size="small"
                        icon={<BranchesOutlined />}
                        onClick={() => handleSubdivideTask(task.id, task.name, task.description)}
                      >
                        细分
                      </Button>
                    </Space>
                  )}
                </Space>
              }
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text strong>{task.name}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    {task.description}
                  </Text>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <Tag color={
                    task.status === 'pending' ? 'orange' :
                    task.status === 'in_progress' ? 'blue' :
                    task.status === 'completed' ? 'green' :
                    task.status === 'failed' ? 'red' : 'purple'
                  }>
                    {task.status === 'pending' ? '待处理' :
                     task.status === 'in_progress' ? '进行中' :
                     task.status === 'completed' ? '已完成' :
                     task.status === 'failed' ? '失败' :
                     task.status === 'blocked' ? '阻塞' : '未知'}
                  </Tag>
                  <br />
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    预计: {formatDuration(task.estimated_duration)}
                  </Text>
                </div>
              </div>
            </Card>
          ))}
        </Card>
      )}

      {/* 任务详情模态框 */}
      <Modal
        title="任务详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={600}
      >
        {selectedTask && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="任务名称">
              {selectedTask.name}
            </Descriptions.Item>
            <Descriptions.Item label="任务描述">
              {selectedTask.description}
            </Descriptions.Item>
            <Descriptions.Item label="任务类型">
              <Tag color={
                selectedTask.type === 'start' ? 'green' :
                selectedTask.type === 'end' ? 'red' :
                selectedTask.type === 'human' ? 'blue' :
                selectedTask.type === 'ai' ? 'purple' : 'orange'
              }>
                {selectedTask.type === 'start' ? '开始节点' :
                 selectedTask.type === 'end' ? '结束节点' :
                 selectedTask.type === 'human' ? '人工任务' :
                 selectedTask.type === 'ai' ? 'AI任务' :
                 selectedTask.type === 'decision' ? '决策节点' : '处理节点'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="任务状态">
              <Tag color={
                selectedTask.status === 'pending' ? 'orange' :
                selectedTask.status === 'in_progress' ? 'blue' :
                selectedTask.status === 'completed' ? 'green' :
                selectedTask.status === 'failed' ? 'red' : 'purple'
              }>
                {selectedTask.status === 'pending' ? '待处理' :
                 selectedTask.status === 'in_progress' ? '进行中' :
                 selectedTask.status === 'completed' ? '已完成' :
                 selectedTask.status === 'failed' ? '失败' :
                 selectedTask.status === 'blocked' ? '阻塞' : '未知'}
              </Tag>
            </Descriptions.Item>
            {selectedTask.assignee && (
              <Descriptions.Item label="执行者">
                <Space>
                  {selectedTask.assignee.type === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  {selectedTask.assignee.name}
                </Space>
              </Descriptions.Item>
            )}
            <Descriptions.Item label="创建时间">
              {formatDate(selectedTask.created_at)}
            </Descriptions.Item>
            {selectedTask.started_at && (
              <Descriptions.Item label="开始时间">
                {formatDate(selectedTask.started_at)}
              </Descriptions.Item>
            )}
            {selectedTask.completed_at && (
              <Descriptions.Item label="完成时间">
                {formatDate(selectedTask.completed_at)}
              </Descriptions.Item>
            )}
            {selectedTask.estimated_duration && (
              <Descriptions.Item label="预计耗时">
                {formatDuration(selectedTask.estimated_duration)}
              </Descriptions.Item>
            )}
            {selectedTask.actual_duration && (
              <Descriptions.Item label="实际耗时">
                {formatDuration(selectedTask.actual_duration)}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>

      {/* 任务细分模态框 */}
      <TaskSubdivisionModal
        visible={subdivisionModalVisible}
        onCancel={handleSubdivisionCancel}
        onSuccess={handleSubdivisionSuccess}
        taskId={subdivisionTaskId}
        taskTitle={subdivisionTaskTitle}
        taskDescription={subdivisionTaskDescription}
      />
    </div>
  );
};

export default TaskFlowViewer; 