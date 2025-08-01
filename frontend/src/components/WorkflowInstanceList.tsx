import React, { useState, useEffect } from 'react';
import { Table, Tag, Button, Space, Modal, message, Tooltip, Badge, Progress, Tabs } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, StopOutlined, ReloadOutlined, EyeOutlined, InfoCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import ReactFlow, {
  Node,
  Edge,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { executionAPI } from '../services/api';

interface WorkflowInstance {
  instance_id: string;
  instance_name: string;
  workflow_name: string;
  status: string;
  executor_id: string;
  executor_username?: string;
  created_at: string;
  updated_at: string;
  input_data: any;
  output_data: any;
  error_message?: string;
  progress_percentage?: number;
  total_nodes?: number;
  completed_nodes?: number;
  running_nodes?: number;
  failed_nodes?: number;
  current_node?: string;
  current_running_nodes?: string[];
}

interface WorkflowInstanceListProps {
  workflowBaseId: string;
  visible: boolean;
  onClose: () => void;
}

// 自定义ReactFlow节点组件（移到组件外部避免重新创建）
const CustomInstanceNode = ({ data, selected }: { data: any; selected?: boolean }) => {
  const getNodeColor = (status?: string) => {
    switch (status) {
      case 'completed':
        return '#52c41a';
      case 'running':
        return '#1890ff';
      case 'failed':
        return '#ff4d4f';
      case 'pending':
      case 'waiting':
        return '#faad14';
      case 'cancelled':
        return '#8c8c8c';
      default:
        return '#d9d9d9';
    }
  };

  const getNodeBackground = (status?: string) => {
    switch (status) {
      case 'completed':
        return '#f6ffed';
      case 'running':
        return '#e6f7ff';
      case 'failed':
        return '#fff2f0';
      case 'pending':
      case 'waiting':
        return '#fffbe6';
      case 'cancelled':
        return '#f5f5f5';
      default:
        return '#fafafa';
    }
  };

  const getStatusText = (status?: string) => {
    switch (status) {
      case 'completed':
        return '已完成';
      case 'running':
        return '运行中';
      case 'failed':
        return '失败';
      case 'pending':
        return '等待中';
      case 'waiting':
        return '等待中';
      case 'cancelled':
        return '已取消';
      default:
        return '未知';
    }
  };

  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '8px',
        border: `2px solid ${selected ? '#1890ff' : getNodeColor(data.status)}`,
        backgroundColor: getNodeBackground(data.status),
        minWidth: '180px',
        textAlign: 'center',
        boxShadow: selected ? '0 0 0 2px rgba(24, 144, 255, 0.2)' : '0 2px 8px rgba(0,0,0,0.1)',
        transition: 'all 0.3s ease',
        cursor: 'pointer',
      }}
      onClick={() => data.onNodeClick && data.onNodeClick(data)}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '14px' }}>
        {data.label}
      </div>
      <div style={{ marginBottom: '6px' }}>
        <Tag color={getNodeColor(data.status)} style={{ fontSize: '11px' }}>
          {getStatusText(data.status)}
        </Tag>
      </div>
      {data.processor_name && (
        <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
          {data.processor_name}
        </div>
      )}
      {data.task_count && (
        <div style={{ fontSize: '11px', color: '#999' }}>
          任务数: {data.task_count}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};

const nodeTypes = {
  customInstance: CustomInstanceNode,
};

const WorkflowInstanceList: React.FC<WorkflowInstanceListProps> = ({
  workflowBaseId,
  visible,
  onClose
}) => {
  const [instances, setInstances] = useState<WorkflowInstance[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedInstance, setSelectedInstance] = useState<WorkflowInstance | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [pendingAction, setPendingAction] = useState<{instanceId: string; instanceName: string; action: 'cancel' | 'delete'} | null>(null);
  const [nodesDetail, setNodesDetail] = useState<any>(null);
  const [loadingNodesDetail, setLoadingNodesDetail] = useState(false);
  
  // ReactFlow states
  const [activeTab, setActiveTab] = useState('detail');
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNodeForDetail, setSelectedNodeForDetail] = useState<any>(null);



  // 计算基于层次的节点布局
  const calculateNodeLayout = (nodes: any[], edges: any[] = []) => {
    // 构建邻接列表
    const adjacencyList: { [key: string]: string[] } = {};
    const inDegree: { [key: string]: number } = {};
    
    // 初始化所有节点
    nodes.forEach(node => {
      const nodeId = node.node_instance_id;
      adjacencyList[nodeId] = [];
      inDegree[nodeId] = 0;
    });
    
    // 构建图结构
    edges.forEach(edge => {
      const source = edge.source;
      const target = edge.target;
      adjacencyList[source].push(target);
      inDegree[target]++;
    });
    
    // 拓扑排序分层
    const layers: string[][] = [];
    const queue: string[] = [];
    const processed = new Set<string>();
    
    // 找到入度为0的节点（起始节点）
    Object.keys(inDegree).forEach(nodeId => {
      if (inDegree[nodeId] === 0) {
        queue.push(nodeId);
      }
    });
    
    // 如果没有入度为0的节点，取第一个节点作为起始
    if (queue.length === 0 && nodes.length > 0) {
      queue.push(nodes[0].node_instance_id);
    }
    
    // 按层次分组节点
    while (queue.length > 0) {
      const currentLayer: string[] = [];
      const currentLevelSize = queue.length;
      
      for (let i = 0; i < currentLevelSize; i++) {
        const nodeId = queue.shift()!;
        currentLayer.push(nodeId);
        processed.add(nodeId);
        
        // 将邻居节点的入度减1
        adjacencyList[nodeId].forEach(neighbor => {
          inDegree[neighbor]--;
          if (inDegree[neighbor] === 0 && !processed.has(neighbor)) {
            queue.push(neighbor);
          }
        });
      }
      
      if (currentLayer.length > 0) {
        layers.push(currentLayer);
      }
    }
    
    // 处理未处理的节点（可能存在循环）
    const unprocessed = nodes.filter(node => !processed.has(node.node_instance_id));
    if (unprocessed.length > 0) {
      layers.push(unprocessed.map(node => node.node_instance_id));
    }
    
    // 计算节点位置
    const nodePositions: { [key: string]: { x: number; y: number } } = {};
    const layerHeight = 200;
    const nodeWidth = 300;
    
    layers.forEach((layer, layerIndex) => {
      const y = layerIndex * layerHeight;
      const layerWidth = layer.length * nodeWidth;
      const startX = -layerWidth / 2; // 居中对齐
      
      layer.forEach((nodeId, nodeIndex) => {
        nodePositions[nodeId] = {
          x: startX + nodeIndex * nodeWidth,
          y: y
        };
      });
    });
    
    return nodePositions;
  };

  // 将节点数据转换为ReactFlow格式
  const convertToReactFlowData = () => {
    if (!selectedInstance || !nodesDetail?.nodes) {
      return { nodes: [], edges: [] };
    }

    // 先获取边数据用于布局计算
    const edgesData = nodesDetail?.edges || [];
    
    // 计算节点布局
    const nodePositions = calculateNodeLayout(nodesDetail.nodes, edgesData);

    const flowNodes: Node[] = nodesDetail.nodes.map((node: any, index: number) => {
      const nodeId = node.node_instance_id || `node-${index}`;
      const position = nodePositions[nodeId] || { x: (index % 4) * 250, y: Math.floor(index / 4) * 150 };
      
      return {
        id: nodeId,
        type: 'customInstance',
        position: position,
        data: {
          label: node.node_name || `节点 ${index + 1}`,
          status: node.status,
          processor_name: node.processor_name,
          processor_type: node.processor_type,
          task_count: node.task_count,
          retry_count: node.retry_count,
          execution_duration_seconds: node.execution_duration_seconds,
          input_data: node.input_data,
          output_data: node.output_data,
          error_message: node.error_message,
          start_at: node.start_at,
          completed_at: node.completed_at,
          tasks: node.tasks || [],
          onNodeClick: setSelectedNodeForDetail
        },
      };
    });

    // 使用从API返回的真实连接关系构建边
    const flowEdges: Edge[] = [];
    if (nodesDetail?.edges && Array.isArray(nodesDetail.edges)) {
      nodesDetail.edges.forEach((edge: any) => {
        // 确保源节点和目标节点都存在
        const sourceExists = flowNodes.find(n => n.id === edge.source);
        const targetExists = flowNodes.find(n => n.id === edge.target);
        
        if (sourceExists && targetExists) {
          flowEdges.push({
            id: edge.id || `edge-${edge.source}-${edge.target}`,
            source: edge.source,
            target: edge.target,
            type: 'smoothstep',
            style: { 
              stroke: '#1890ff', 
              strokeWidth: 2 
            },
            label: edge.connection_type === 'conditional' ? edge.condition_label : undefined,
            labelStyle: { fontSize: '10px', fill: '#666' },
            labelBgPadding: [4, 4],
            labelBgBorderRadius: 4,
            labelBgStyle: { fill: '#fff', color: '#666', fillOpacity: 0.8 }
          });
        } else {
          console.warn('跳过无效连接:', edge, '源节点存在:', !!sourceExists, '目标节点存在:', !!targetExists);
        }
      });
    } else {
      // 如果没有边数据，回退到简单的顺序连接
      console.warn('未找到边数据，使用顺序连接');
      for (let i = 0; i < flowNodes.length - 1; i++) {
        flowEdges.push({
          id: `edge-${i}`,
          source: flowNodes[i].id,
          target: flowNodes[i + 1].id,
          type: 'smoothstep',
          style: { stroke: '#1890ff', strokeWidth: 2 },
        });
      }
    }

    return { nodes: flowNodes, edges: flowEdges };
  };

  // 当选择的实例或节点详情改变时，更新ReactFlow数据
  useEffect(() => {
    if (selectedInstance && nodesDetail) {
      const { nodes: flowNodes, edges: flowEdges } = convertToReactFlowData();
      setNodes(flowNodes);
      setEdges(flowEdges);
    }
  }, [selectedInstance, nodesDetail]);

  // 测试Modal功能
  const testModal = () => {
    console.log('🧪 测试Modal功能');
    
    try {
      const modal = Modal.info({
        title: '测试Modal',
        content: '这是一个测试Modal，用于验证Modal组件是否正常工作',
        onOk() {
          console.log('✅ 测试Modal确认');
        },
      });
      
      console.log('📋 测试Modal返回值:', modal);
      
      if (!modal) {
        console.error('❌ 测试Modal返回undefined');
        alert('Modal组件可能存在问题');
      }
    } catch (error) {
      console.error('❌ 测试Modal异常:', error);
      alert('Modal组件异常: ' + error);
    }
  };

  // 强化去重函数
  const deduplicateInstances = (instancesData: any[]) => {
    const instancesMap = new Map<string, WorkflowInstance>();
    const seen = new Set<string>();
    
    instancesData.forEach((instance: any) => {
      if (instance.instance_id && !seen.has(instance.instance_id)) {
        instancesMap.set(instance.instance_id, instance);
        seen.add(instance.instance_id);
      } else if (instance.instance_id && seen.has(instance.instance_id)) {
        console.warn('跳过重复的instance_id:', instance.instance_id);
      }
    });
    
    return Array.from(instancesMap.values());
  };

  const fetchInstances = async (showMessage = false) => {
    if (!workflowBaseId) return;
    
    setLoading(true);
    try {
      const response: any = await executionAPI.getWorkflowInstances(workflowBaseId);
      if (response && response.success) {
        const instancesData = response.data || [];
        const uniqueInstances = deduplicateInstances(instancesData);
        setInstances(uniqueInstances);
        if (showMessage) {
          const runningCount = uniqueInstances.filter((i: any) => i.status === 'running').length;
          const completedCount = uniqueInstances.filter((i: any) => i.status === 'completed').length;
          const failedCount = uniqueInstances.filter((i: any) => i.status === 'failed').length;
          message.success(`已更新：共 ${uniqueInstances.length} 个实例（运行中:${runningCount}, 完成:${completedCount}, 失败:${failedCount}）`);
        }
      } else if (response && response.data?.success) {
        const instancesData = response.data.data || [];
        const uniqueInstances = deduplicateInstances(instancesData);
        setInstances(uniqueInstances);
        if (showMessage) {
          const runningCount = uniqueInstances.filter((i: any) => i.status === 'running').length;
          const completedCount = uniqueInstances.filter((i: any) => i.status === 'completed').length;
          const failedCount = uniqueInstances.filter((i: any) => i.status === 'failed').length;
          message.success(`已更新：共 ${uniqueInstances.length} 个实例（运行中:${runningCount}, 完成:${completedCount}, 失败:${failedCount}）`);
        }
      } else {
        message.error('获取执行实例失败');
        setInstances([]);
        console.error('获取执行实例失败 - 响应格式:', response);
      }
    } catch (error: any) {
      console.error('获取执行实例失败:', error);
      message.error(`获取执行实例失败: ${error.response?.data?.detail || error.message}`);
      setInstances([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible && workflowBaseId) {
      fetchInstances();
    }
  }, [visible, workflowBaseId]);

  // 自动刷新机制
  useEffect(() => {
    if (autoRefresh && visible) {
      const interval = setInterval(() => {
        fetchInstances();
      }, 3000); // 每3秒刷新一次
      setRefreshInterval(interval);
      return () => {
        clearInterval(interval);
      };
    } else {
      if (refreshInterval) {
        clearInterval(refreshInterval);
        setRefreshInterval(null);
      }
    }
  }, [autoRefresh, visible]);

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  }, [refreshInterval]);

  const getStatusTag = React.useCallback((status: string) => {
    const statusConfig = {
      'pending': { color: 'orange', text: '等待中', icon: '⏳' },
      'running': { color: 'blue', text: '执行中', icon: '▶️' },
      'completed': { color: 'green', text: '已完成', icon: '✅' },
      'failed': { color: 'red', text: '失败', icon: '❌' },
      'cancelled': { color: 'default', text: '已取消', icon: '⛔' },
      'paused': { color: 'gold', text: '已暂停', icon: '⏸️' }
    };
    
    const config = statusConfig[status as keyof typeof statusConfig] || { color: 'default', text: status, icon: '❓' };
    return (
      <Tag color={config.color}>
        <span style={{ marginRight: 4 }}>{config.icon}</span>
        {config.text}
      </Tag>
    );
  }, []);

  const getExecutionDuration = React.useCallback((createdAt: string, updatedAt: string, status: string) => {
    if (!createdAt) return '-';
    
    const start = new Date(createdAt);
    const end = status === 'running' ? new Date() : new Date(updatedAt || createdAt);
    const diff = Math.floor((end.getTime() - start.getTime()) / 1000);
    
    if (diff < 60) return `${diff}秒`;
    if (diff < 3600) return `${Math.floor(diff / 60)}分${diff % 60}秒`;
    return `${Math.floor(diff / 3600)}时${Math.floor((diff % 3600) / 60)}分`;
  }, []);

  const getProgressInfo = React.useCallback((instance: WorkflowInstance) => {
    if (instance.total_nodes && instance.completed_nodes !== undefined) {
      const percentage = Math.round((instance.completed_nodes / instance.total_nodes) * 100);
      return { percentage, completed: instance.completed_nodes, total: instance.total_nodes };
    }
    return null;
  }, []);

  const filteredInstances = React.useMemo(() => {
    // 先确保数据没有重复
    const uniqueInstances = instances.filter((instance, index, self) => 
      index === self.findIndex(i => i.instance_id === instance.instance_id)
    );
    
    return statusFilter === 'all' 
      ? uniqueInstances 
      : uniqueInstances.filter(instance => instance.status === statusFilter);
  }, [instances, statusFilter]);

  const handleControlWorkflow = async (instanceId: string, action: 'pause' | 'resume' | 'cancel') => {
    const actionText = { pause: '暂停', resume: '恢复', cancel: '取消' }[action];
    
    console.log('🎮 用户点击工作流控制按钮:', {
      instanceId,
      action,
      actionText,
      timestamp: new Date().toISOString()
    });
    
    // 如果是取消操作，显示确认对话框
    if (action === 'cancel') {
      console.log('🚫 显示取消确认对话框');
      const instance = instances.find(i => i.instance_id === instanceId);
      setPendingAction({
        instanceId,
        instanceName: instance?.instance_name || '未知实例',
        action: 'cancel'
      });
      setCancelModalVisible(true);
      return;
    }
    
    // 其他操作直接执行
    console.log('⚡ 直接执行控制操作:', action);
    await executeControlAction(instanceId, action, actionText);
  };

  const executeControlAction = async (instanceId: string, action: 'pause' | 'resume' | 'cancel', actionText: string) => {
    console.log('🚀 开始执行工作流控制操作:', {
      instanceId,
      action,
      actionText,
      timestamp: new Date().toISOString()
    });

    try {
      console.log('📡 发送API请求: executionAPI.controlWorkflow');
      console.log('   - URL: /api/execution/workflows/' + instanceId + '/control');
      console.log('   - Method: POST');
      console.log('   - Data:', { action });
      
      const response: any = await executionAPI.controlWorkflow(instanceId, { action });
      
      console.log('📥 收到API响应:', {
        response,
        success: response?.success,
        dataSuccess: response?.data?.success,
        message: response?.message,
        data: response?.data
      });
      
      if (response?.success || response?.data?.success) {
        console.log('✅ 控制操作成功');
        message.success(`工作流${actionText}成功`);
        
        console.log('🔄 刷新实例列表');
        await fetchInstances(true); // 刷新列表并显示提示
        console.log('✅ 实例列表刷新完成');
      } else {
        console.log('❌ 控制操作失败 - 响应中success为false');
        console.log('   - response:', response);
        message.error(`工作流${actionText}失败`);
      }
    } catch (error: any) {
      console.error('❌ 控制工作流异常:', {
        error,
        message: error.message,
        response: error.response,
        responseData: error.response?.data,
        responseStatus: error.response?.status,
        responseHeaders: error.response?.headers
      });
      
      console.error('❌ 完整错误对象:', error);
      
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || '未知错误';
      console.error('❌ 显示给用户的错误信息:', errorMessage);
      
      message.error(`工作流${actionText}失败: ${errorMessage}`);
    }
  };

  const handleDeleteInstance = async (instanceId: string, instanceName: string) => {
    console.log('🗑️ 用户点击删除按钮:', { instanceId, instanceName });
    
    setPendingAction({
      instanceId,
      instanceName: instanceName || '未知实例',
      action: 'delete'
    });
    setDeleteModalVisible(true);
  };

  const handleConfirmAction = async () => {
    if (!pendingAction) return;

    const { instanceId, action } = pendingAction;
    
    if (action === 'cancel') {
      console.log('✅ 用户确认取消操作');
      setCancelModalVisible(false);
      await executeControlAction(instanceId, 'cancel', '取消');
    } else if (action === 'delete') {
      console.log('🗑️ 用户确认删除，开始执行删除操作:', instanceId);
      setDeleteModalVisible(false);
      
      try {
        const response: any = await executionAPI.deleteWorkflowInstance(instanceId);
        console.log('✅ 删除API调用成功，响应:', response);
        
        if (response?.success || response?.data?.success) {
          message.success('工作流实例删除成功');
          console.log('✅ 删除成功，开始刷新列表');
          await fetchInstances(true);
        } else {
          console.error('❌ 删除响应表明失败:', response);
          message.error('删除工作流实例失败');
        }
      } catch (error: any) {
        console.error('❌ 删除工作流实例异常:', error);
        
        if (error.response?.status === 400) {
          message.error(error.response?.data?.detail || '无法删除正在运行的实例，请先取消');
        } else if (error.response?.status === 403) {
          message.error('无权删除此工作流实例');
        } else if (error.response?.status === 404) {
          message.error('工作流实例不存在');
        } else {
          message.error(`删除工作流实例失败: ${error.response?.data?.detail || error.message}`);
        }
      }
    }
    
    setPendingAction(null);
  };

  const handleCancelAction = () => {
    console.log('❌ 用户取消操作');
    setCancelModalVisible(false);
    setDeleteModalVisible(false);
    setPendingAction(null);
  };

  const showInstanceDetail = async (instance: WorkflowInstance) => {
    try {
      setLoadingNodesDetail(true);
      
      // 获取实例详细状态
      const response: any = await executionAPI.getWorkflowInstanceDetail(instance.instance_id);
      if (response && (response.success || response.data?.success)) {
        const detailData = response.data || response;
        setSelectedInstance(detailData.data || detailData);
      } else {
        setSelectedInstance(instance);
      }

      // 获取节点详细输出信息
      try {
        const nodesResponse: any = await executionAPI.getWorkflowNodesDetail(instance.instance_id);
        if (nodesResponse && (nodesResponse.success || nodesResponse.data?.success)) {
          const nodesData = nodesResponse.data || nodesResponse;
          setNodesDetail(nodesData.data || nodesData);
          console.log('🔍 获取节点详细信息成功:', nodesData);
        } else {
          console.warn('获取节点详细信息失败:', nodesResponse);
          setNodesDetail(null);
        }
      } catch (nodesError) {
        console.error('获取节点详细信息异常:', nodesError);
        setNodesDetail(null);
      }
      
    } catch (error) {
      console.warn('获取实例详情失败，使用基本信息:', error);
      setSelectedInstance(instance);
      setNodesDetail(null);
    } finally {
      setLoadingNodesDetail(false);
    }
    
    setDetailVisible(true);
  };

  const columns = [
    {
      title: '实例名称',
      dataIndex: 'instance_name',
      key: 'instance_name',
      ellipsis: true,
      render: (text: string, record: WorkflowInstance) => (
        <div>
          <div style={{ fontWeight: 'bold', fontSize: '14px' }}>{text}</div>
          <div style={{ fontSize: '12px', color: '#666' }}>ID: {record.instance_id.slice(0, 8)}...</div>
        </div>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '执行时长',
      key: 'duration',
      width: 100,
      render: (_: any, record: WorkflowInstance) => {
        const progressInfo = getProgressInfo(record);
        return (
          <div>
            <div style={{ fontSize: '12px', marginBottom: 4 }}>
              {getExecutionDuration(record.created_at, record.updated_at, record.status)}
            </div>
            {progressInfo && (
              <Progress 
                percent={progressInfo.percentage} 
                size="small" 
                format={() => `${progressInfo.completed}/${progressInfo.total}`}
                strokeColor={record.status === 'running' ? '#1890ff' : record.status === 'completed' ? '#52c41a' : '#ff4d4f'}
              />
            )}
          </div>
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (text: string) => (
        <span style={{ fontSize: '12px' }}>
          {text ? new Date(text).toLocaleString('zh-CN') : '-'}
        </span>
      ),
    },
    {
      title: '执行者',
      dataIndex: 'executor_id',
      key: 'executor_id',
      width: 100,
      render: (executorId: string) => (
        <span style={{ fontSize: '12px', color: '#666' }}>
          {executorId ? executorId.slice(0, 8) + '...' : '-'}
        </span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: WorkflowInstance) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => showInstanceDetail(record)}
            />
          </Tooltip>
          
          {record.status === 'running' && (
            <Tooltip title="暂停">
              <Button
                type="text"
                icon={<PauseCircleOutlined />}
                onClick={() => handleControlWorkflow(record.instance_id, 'pause')}
              />
            </Tooltip>
          )}
          
          {record.status === 'paused' && (
            <Tooltip title="恢复">
              <Button
                type="text"
                icon={<PlayCircleOutlined />}
                onClick={() => handleControlWorkflow(record.instance_id, 'resume')}
              />
            </Tooltip>
          )}
          
          {(record.status === 'pending' || record.status === 'running' || record.status === 'paused') && (
            <Tooltip title="取消">
              <Button
                type="text"
                danger
                icon={<StopOutlined />}
                onClick={(e) => {
                  console.log('🖱️ 取消按钮被点击:', {
                    event: e,
                    instanceId: record.instance_id,
                    status: record.status,
                    timestamp: new Date().toISOString()
                  });
                  e.preventDefault();
                  e.stopPropagation();
                  handleControlWorkflow(record.instance_id, 'cancel');
                }}
              />
            </Tooltip>
          )}
          
          {(record.status === 'completed' || record.status === 'failed' || record.status === 'cancelled') && (
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDeleteInstance(record.instance_id, record.instance_name)}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <Modal
        title={(
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>工作流执行实例</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Button 
                size="small" 
                type="primary" 
                ghost 
                onClick={testModal}
                style={{ fontSize: '12px' }}
              >
                测试Modal
              </Button>
              {instances.filter(i => i.status === 'running').length > 0 && (
                <Badge 
                  count={instances.filter(i => i.status === 'running').length} 
                  style={{ backgroundColor: '#1890ff' }}
                  title={`${instances.filter(i => i.status === 'running').length} 个实例正在执行`}
                />
              )}
            </div>
          </div>
        )}
        open={visible}
        onCancel={() => {
          // 关闭时停止自动刷新
          setAutoRefresh(false);
          onClose();
        }}
        width={1200}
        footer={[
          <div key="footer-content" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <div style={{ fontSize: '12px', color: '#666' }}>
              {instances.length > 0 && (
                <span>
                  最近更新: {new Date().toLocaleTimeString('zh-CN')}
                  {autoRefresh && <span style={{ marginLeft: 8, color: '#1890ff' }}>(正在自动刷新)</span>}
                </span>
              )}
            </div>
            <Space>
              <Button 
                icon={<ReloadOutlined />} 
                onClick={() => fetchInstances(true)}
                loading={loading}
                size="small"
              >
                手动刷新
              </Button>
              <Button 
                type={autoRefresh ? 'primary' : 'default'}
                onClick={() => setAutoRefresh(!autoRefresh)}
                size="small"
              >
                {autoRefresh ? '停止自动刷新' : '开启自动刷新'}
              </Button>
              <Button onClick={() => {
                setAutoRefresh(false);
                onClose();
              }} size="small">
                关闭
              </Button>
            </Space>
          </div>
        ]}
      >
        <div style={{ marginBottom: 16 }}>
          <Space wrap>
            <span>共 {instances.length} 个执行实例</span>
            
            {/* 状态过滤器 */}
            <Space>
              <Button 
                size="small" 
                type={statusFilter === 'all' ? 'primary' : 'default'}
                onClick={() => setStatusFilter('all')}
              >
                全部 ({instances.length})
              </Button>
              <Button 
                size="small" 
                type={statusFilter === 'running' ? 'primary' : 'default'}
                onClick={() => setStatusFilter('running')}
              >
                运行中 ({instances.filter(i => i.status === 'running').length})
              </Button>
              <Button 
                size="small" 
                type={statusFilter === 'completed' ? 'primary' : 'default'}
                onClick={() => setStatusFilter('completed')}
              >
                已完成 ({instances.filter(i => i.status === 'completed').length})
              </Button>
              <Button 
                size="small" 
                type={statusFilter === 'failed' ? 'primary' : 'default'}
                onClick={() => setStatusFilter('failed')}
              >
                失败 ({instances.filter(i => i.status === 'failed').length})
              </Button>
            </Space>
            
            {autoRefresh && (
              <Badge status="processing" text="自动刷新中 (3秒间隔)" />
            )}
            
            {instances.filter(i => i.status === 'running').length > 0 && (
              <Tag color="blue">
                <PlayCircleOutlined style={{ marginRight: 4 }} />
                {instances.filter(i => i.status === 'running').length} 个正在执行
              </Tag>
            )}
          </Space>
        </div>
        
        <Table
          columns={columns}
          dataSource={filteredInstances}
          rowKey={(record) => {
            // 使用instance_id和时间戳来生成唯一key，防止重复
            const timestamp = record.created_at ? new Date(record.created_at).getTime() : Date.now();
            const randomSuffix = Math.random().toString(36).substr(2, 9);
            return `workflow-instance-${record.instance_id}-${timestamp}-${randomSuffix}`;
          }}
          loading={loading}
          size="small"
          pagination={{
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => {
              const statusText = statusFilter === 'all' ? '全部' : 
                statusFilter === 'running' ? '运行中' : 
                statusFilter === 'completed' ? '已完成' : '失败';
              return `显示 ${range[0]}-${range[1]} 条，共 ${total} 条${statusText}记录`;
            },
            pageSize: 10,
            pageSizeOptions: ['10', '20', '50']
          }}
          rowClassName={(record) => {
            if (record.status === 'running') return 'running-row';
            if (record.status === 'failed') return 'failed-row';
            return '';
          }}
        />
        
        <style>{`
          .running-row {
            background-color: #f0f9ff !important;
          }
          .failed-row {
            background-color: #fef2f2 !important;
          }
        `}</style>
      </Modal>

      {/* 实例详情弹窗 */}
      <Modal
        title={(
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span>实例详情</span>
            {selectedInstance && selectedInstance.status === 'running' && (
              <Badge status="processing" text="正在执行" style={{ marginLeft: 12 }} />
            )}
          </div>
        )}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        width={1200}
        footer={[
          <Button key="close" onClick={() => setDetailVisible(false)}>
            关闭
          </Button>
        ]}
      >
        {selectedInstance && (
          <Tabs 
            activeKey={activeTab} 
            onChange={setActiveTab}
            style={{ height: '60vh' }}
            items={[
              {
                key: 'detail',
                label: '详情视图',
                children: (
                  <div style={{ maxHeight: '50vh', overflow: 'auto' }}>
            <div style={{ marginBottom: 16 }}>
              <strong>实例ID:</strong> {selectedInstance.instance_id}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>实例名称:</strong> {selectedInstance.instance_name}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>工作流名称:</strong> {selectedInstance.workflow_name}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>状态:</strong> {getStatusTag(selectedInstance.status)}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>执行者:</strong> 
              {selectedInstance.executor_username ? (
                <span>{selectedInstance.executor_username} ({selectedInstance.executor_id?.slice(0, 8)}...)</span>
              ) : (
                <span>{selectedInstance.executor_id}</span>
              )}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>执行时长:</strong> {getExecutionDuration(selectedInstance.created_at, selectedInstance.updated_at, selectedInstance.status)}
            </div>
            
            {getProgressInfo(selectedInstance) && (
              <div style={{ marginBottom: 16 }}>
                <strong>执行进度:</strong>
                <div style={{ marginTop: 8 }}>
                  <Progress 
                    percent={getProgressInfo(selectedInstance)!.percentage} 
                    strokeColor={selectedInstance.status === 'running' ? '#1890ff' : selectedInstance.status === 'completed' ? '#52c41a' : '#ff4d4f'}
                    format={(percent) => {
                      const info = getProgressInfo(selectedInstance)!;
                      return `${info.completed}/${info.total} (${percent}%)`;
                    }}
                  />
                </div>
              </div>
            )}
            
            {selectedInstance.current_node && (
              <div style={{ marginBottom: 16 }}>
                <strong>当前节点:</strong> 
                <Tag color="processing">{selectedInstance.current_node}</Tag>
              </div>
            )}
            
            {selectedInstance.current_running_nodes && selectedInstance.current_running_nodes.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>正在执行的节点:</strong>
                <div style={{ marginTop: 8 }}>
                  {selectedInstance.current_running_nodes.map((nodeName: string, index: number) => (
                    <Tag key={`running-node-${index}-${nodeName}`} color="processing" style={{ marginBottom: 4 }}>
                      {nodeName}
                    </Tag>
                  ))}
                </div>
              </div>
            )}
            
            {(selectedInstance as any).node_instances && (
              <div style={{ marginBottom: 16 }}>
                <strong>节点执行状态:</strong>
                <div style={{ 
                  maxHeight: '200px', 
                  overflow: 'auto', 
                  marginTop: 8,
                  border: '1px solid #d9d9d9',
                  borderRadius: 4,
                  padding: 8
                }}>
                  {(selectedInstance as any).node_instances.map((node: any, index: number) => (
                    <div key={`node-instance-${node.node_instance_id || index}-${node.node_name}`} style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '4px 0',
                      borderBottom: index < (selectedInstance as any).node_instances.length - 1 ? '1px solid #f0f0f0' : 'none'
                    }}>
                      <div>
                        <strong>{node.node_name}</strong>
                        <span style={{ marginLeft: 8, fontSize: '12px', color: '#666' }}>({node.node_type})</span>
                      </div>
                      <div>
                        {getStatusTag(node.status)}
                        {node.completed_at && (
                          <span style={{ marginLeft: 8, fontSize: '12px', color: '#666' }}>
                            {new Date(node.completed_at).toLocaleString('zh-CN')}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div style={{ marginBottom: 16 }}>
              <strong>创建时间:</strong> {selectedInstance.created_at ? new Date(selectedInstance.created_at).toLocaleString() : '-'}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>更新时间:</strong> {selectedInstance.updated_at ? new Date(selectedInstance.updated_at).toLocaleString() : '-'}
            </div>
            
            {selectedInstance.input_data && Object.keys(selectedInstance.input_data).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>输入数据:</strong>
                <pre style={{ 
                  background: '#f5f5f5', 
                  padding: 12, 
                  borderRadius: 4, 
                  marginTop: 8,
                  fontSize: '12px'
                }}>
                  {JSON.stringify(selectedInstance.input_data, null, 2)}
                </pre>
              </div>
            )}
            
            {selectedInstance.output_data && Object.keys(selectedInstance.output_data).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>工作流输出数据:</strong>
                <pre style={{ 
                  background: '#f5f5f5', 
                  padding: 12, 
                  borderRadius: 4, 
                  marginTop: 8,
                  fontSize: '12px'
                }}>
                  {JSON.stringify(selectedInstance.output_data, null, 2)}
                </pre>
              </div>
            )}

            {/* 节点详细输出信息 */}
            {loadingNodesDetail && (
              <div style={{ marginBottom: 16, textAlign: 'center' }}>
                <strong>正在加载节点详细信息...</strong>
              </div>
            )}

            {nodesDetail && nodesDetail.nodes && (
              <div style={{ marginBottom: 16 }}>
                <strong>节点详细输出:</strong>
                <div style={{ 
                  maxHeight: '400px', 
                  overflow: 'auto', 
                  marginTop: 8,
                  border: '1px solid #d9d9d9',
                  borderRadius: 4
                }}>
                  {nodesDetail.nodes.map((node: any, index: number) => (
                    <div key={`node-detail-${node.node_instance_id}-${index}`} style={{ 
                      borderBottom: index < nodesDetail.nodes.length - 1 ? '1px solid #f0f0f0' : 'none',
                      padding: 16
                    }}>
                      {/* 节点基本信息 */}
                      <div style={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center',
                        marginBottom: 12
                      }}>
                        <div>
                          <strong style={{ fontSize: '14px' }}>{node.node_name}</strong>
                          <span style={{ marginLeft: 8, fontSize: '12px', color: '#666' }}>
                            ({node.node_type})
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          {getStatusTag(node.status)}
                          {node.execution_duration_seconds && (
                            <span style={{ fontSize: '12px', color: '#666' }}>
                              {Math.round(node.execution_duration_seconds / 60 * 100) / 100}分钟
                            </span>
                          )}
                        </div>
                      </div>

                      {/* 任务统计 */}
                      {node.task_statistics && node.task_statistics.total_tasks > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: '12px', color: '#666' }}>
                            任务统计: 总计{node.task_statistics.total_tasks}个，
                            完成{node.task_statistics.completed_tasks}个，
                            失败{node.task_statistics.failed_tasks}个，
                            成功率{node.task_statistics.success_rate.toFixed(1)}%
                          </div>
                        </div>
                      )}

                      {/* 节点输入数据 */}
                      {node.input_data && Object.keys(node.input_data).length > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: 4 }}>输入数据:</div>
                          <pre style={{ 
                            background: '#f8f9fa', 
                            padding: 8, 
                            borderRadius: 4, 
                            fontSize: '11px',
                            margin: 0,
                            maxHeight: '100px',
                            overflow: 'auto'
                          }}>
                            {JSON.stringify(node.input_data, null, 2)}
                          </pre>
                        </div>
                      )}

                      {/* 节点输出数据 */}
                      {node.output_data && Object.keys(node.output_data).length > 0 && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: 4, color: '#1890ff' }}>
                            输出数据:
                          </div>
                          <pre style={{ 
                            background: '#e6f7ff', 
                            padding: 8, 
                            borderRadius: 4, 
                            fontSize: '11px',
                            margin: 0,
                            maxHeight: '200px',
                            overflow: 'auto',
                            border: '1px solid #91d5ff'
                          }}>
                            {JSON.stringify(node.output_data, null, 2)}
                          </pre>
                        </div>
                      )}

                      {/* 节点错误信息 */}
                      {node.error_message && (
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: 4, color: '#ff4d4f' }}>
                            错误信息:
                          </div>
                          <div style={{ 
                            background: '#fff2f0', 
                            border: '1px solid #ffccc7',
                            padding: 8, 
                            borderRadius: 4, 
                            fontSize: '12px',
                            color: '#ff4d4f'
                          }}>
                            {node.error_message}
                          </div>
                        </div>
                      )}

                      {/* 任务详细信息 */}
                      {node.tasks && node.tasks.length > 0 && (
                        <div>
                          <div style={{ fontSize: '12px', fontWeight: 'bold', marginBottom: 8 }}>
                            任务详情 ({node.tasks.length}个):
                          </div>
                          <div style={{ maxHeight: '200px', overflow: 'auto' }}>
                            {node.tasks.map((task: any, taskIndex: number) => (
                              <div key={`task-${task.task_instance_id}-${taskIndex}`} style={{
                                background: '#fafafa',
                                border: '1px solid #f0f0f0',
                                borderRadius: 4,
                                padding: 8,
                                marginBottom: 8,
                                fontSize: '11px'
                              }}>
                                <div style={{ 
                                  display: 'flex', 
                                  justifyContent: 'space-between', 
                                  alignItems: 'center',
                                  marginBottom: 4
                                }}>
                                  <strong>{task.task_title}</strong>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                    {getStatusTag(task.status)}
                                    <span style={{ color: '#666' }}>({task.task_type})</span>
                                  </div>
                                </div>
                                
                                {task.task_description && (
                                  <div style={{ color: '#666', marginBottom: 4 }}>
                                    {task.task_description}
                                  </div>
                                )}

                                {task.result_summary && (
                                  <div style={{ color: '#52c41a', marginBottom: 4 }}>
                                    结果: {task.result_summary}
                                  </div>
                                )}

                                {task.output_data && Object.keys(task.output_data).length > 0 && (
                                  <details style={{ marginBottom: 4 }}>
                                    <summary style={{ cursor: 'pointer', color: '#1890ff' }}>
                                      任务输出数据
                                    </summary>
                                    <pre style={{ 
                                      background: '#fff', 
                                      padding: 4, 
                                      borderRadius: 2, 
                                      fontSize: '10px',
                                      margin: '4px 0 0 0',
                                      maxHeight: '80px',
                                      overflow: 'auto'
                                    }}>
                                      {JSON.stringify(task.output_data, null, 2)}
                                    </pre>
                                  </details>
                                )}

                                {task.error_message && (
                                  <div style={{ color: '#ff4d4f', fontSize: '10px' }}>
                                    错误: {task.error_message}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* 时间信息 */}
                      <div style={{ fontSize: '11px', color: '#999', marginTop: 8 }}>
                        创建: {node.timestamps?.created_at ? new Date(node.timestamps.created_at).toLocaleString('zh-CN') : '-'} | 
                        开始: {node.timestamps?.started_at ? new Date(node.timestamps.started_at).toLocaleString('zh-CN') : '-'} | 
                        完成: {node.timestamps?.completed_at ? new Date(node.timestamps.completed_at).toLocaleString('zh-CN') : '-'}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {selectedInstance.error_message && (
              <div style={{ marginBottom: 16 }}>
                <strong>错误信息:</strong>
                <div style={{ 
                  background: '#fff2f0', 
                  border: '1px solid #ffccc7',
                  padding: 12, 
                  borderRadius: 4, 
                  marginTop: 8,
                  color: '#ff4d4f'
                }}>
                  {selectedInstance.error_message}
                </div>
              </div>
            )}
                  </div>
                )
              },
              {
                key: 'graph',
                label: '图形视图',
                children: (
                  <div style={{ height: '50vh' }}>
                    <ReactFlow
                      nodes={nodes}
                      edges={edges}
                      onNodesChange={onNodesChange}
                      onEdgesChange={onEdgesChange}
                      nodeTypes={nodeTypes}
                      fitView
                      fitViewOptions={{ padding: 0.2 }}
                    >
                      <Controls />
                      <Background />
                      <MiniMap />
                    </ReactFlow>
                  </div>
                )
              }
            ]}
          />
        )}
      </Modal>

      {/* 节点详细信息弹窗 */}
      <Modal
        title="节点详细信息"
        open={!!selectedNodeForDetail}
        onCancel={() => setSelectedNodeForDetail(null)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setSelectedNodeForDetail(null)}>
            关闭
          </Button>
        ]}
      >
        {selectedNodeForDetail && (
          <div style={{ maxHeight: '60vh', overflow: 'auto' }}>
            <div style={{ marginBottom: 16 }}>
              <strong>节点名称:</strong> {selectedNodeForDetail.label}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>节点状态:</strong> {getStatusTag(selectedNodeForDetail.status)}
            </div>
            {selectedNodeForDetail.processor_name && (
              <div style={{ marginBottom: 16 }}>
                <strong>处理器:</strong> {selectedNodeForDetail.processor_name} ({selectedNodeForDetail.processor_type})
              </div>
            )}
            {selectedNodeForDetail.task_count && (
              <div style={{ marginBottom: 16 }}>
                <strong>任务数量:</strong> {selectedNodeForDetail.task_count}
              </div>
            )}
            {selectedNodeForDetail.retry_count !== undefined && (
              <div style={{ marginBottom: 16 }}>
                <strong>重试次数:</strong> {selectedNodeForDetail.retry_count}
              </div>
            )}
            {selectedNodeForDetail.execution_duration_seconds && (
              <div style={{ marginBottom: 16 }}>
                <strong>执行时长:</strong> {Math.round(selectedNodeForDetail.execution_duration_seconds / 60 * 100) / 100}分钟
              </div>
            )}
            
            {/* 输入数据 */}
            {selectedNodeForDetail.input_data && Object.keys(selectedNodeForDetail.input_data).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>输入数据:</strong>
                <pre style={{ 
                  background: '#f8f9fa', 
                  padding: 12, 
                  borderRadius: 4, 
                  marginTop: 8,
                  fontSize: '12px',
                  maxHeight: '200px',
                  overflow: 'auto'
                }}>
                  {JSON.stringify(selectedNodeForDetail.input_data, null, 2)}
                </pre>
              </div>
            )}
            
            {/* 输出数据 */}
            {selectedNodeForDetail.output_data && Object.keys(selectedNodeForDetail.output_data).length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>输出数据:</strong>
                <pre style={{ 
                  background: '#e6f7ff', 
                  padding: 12, 
                  borderRadius: 4, 
                  marginTop: 8,
                  fontSize: '12px',
                  maxHeight: '200px',
                  overflow: 'auto'
                }}>
                  {JSON.stringify(selectedNodeForDetail.output_data, null, 2)}
                </pre>
              </div>
            )}
            
            {/* 任务列表 */}
            {selectedNodeForDetail.tasks && selectedNodeForDetail.tasks.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <strong>任务列表:</strong>
                <div style={{ 
                  background: '#f5f5f5', 
                  padding: 8, 
                  borderRadius: 4, 
                  marginTop: 8,
                  maxHeight: '300px',
                  overflow: 'auto'
                }}>
                  {selectedNodeForDetail.tasks.map((task: any, index: number) => (
                    <div key={index} style={{ 
                      background: '#fff', 
                      padding: 8, 
                      borderRadius: 4, 
                      marginBottom: 8,
                      border: '1px solid #e8e8e8'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                        <strong>{task.task_title || `任务 ${index + 1}`}</strong>
                        {task.status && getStatusTag(task.status)}
                      </div>
                      {task.task_description && (
                        <div style={{ color: '#666', fontSize: '12px', marginBottom: 4 }}>
                          {task.task_description}
                        </div>
                      )}
                      {task.result_summary && (
                        <div style={{ color: '#52c41a', fontSize: '12px' }}>
                          结果: {task.result_summary}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* 错误信息 */}
            {selectedNodeForDetail.error_message && (
              <div style={{ marginBottom: 16 }}>
                <strong>错误信息:</strong>
                <div style={{ 
                  background: '#fff2f0', 
                  border: '1px solid #ffccc7',
                  padding: 12, 
                  borderRadius: 4, 
                  marginTop: 8,
                  color: '#ff4d4f',
                  fontSize: '12px'
                }}>
                  {selectedNodeForDetail.error_message}
                </div>
              </div>
            )}
            
            {/* 时间信息 */}
            <div style={{ fontSize: '12px', color: '#999' }}>
              <div>开始时间: {selectedNodeForDetail.start_at ? new Date(selectedNodeForDetail.start_at).toLocaleString('zh-CN') : '-'}</div>
              <div>完成时间: {selectedNodeForDetail.completed_at ? new Date(selectedNodeForDetail.completed_at).toLocaleString('zh-CN') : '-'}</div>
            </div>
          </div>
        )}
      </Modal>

      {/* 取消工作流确认对话框 */}
      <Modal
        title="确认取消工作流"
        open={cancelModalVisible}
        onOk={handleConfirmAction}
        onCancel={handleCancelAction}
        okText="确定取消"
        cancelText="暂不取消"
        okType="danger"
        centered
        width={400}
        maskClosable={false}
      >
        <p>取消后的工作流无法恢复，确定要取消此工作流实例吗？</p>
        {pendingAction && (
          <p style={{ color: '#666', fontSize: '12px', marginTop: '8px' }}>
            实例名称: {pendingAction.instanceName}
          </p>
        )}
      </Modal>

      {/* 删除工作流实例确认对话框 */}
      <Modal
        title="确认删除工作流实例"
        open={deleteModalVisible}
        onOk={handleConfirmAction}
        onCancel={handleCancelAction}
        okText="确定删除"
        cancelText="取消"
        okType="danger"
        centered
        width={450}
        maskClosable={false}
      >
        <div>
          <p>确定要删除工作流实例 "<strong>{pendingAction?.instanceName}</strong>" 吗？</p>
          <p style={{ color: '#ff4d4f', fontSize: '12px', marginTop: '8px' }}>
            注意：删除后的工作流实例无法恢复，所有相关数据将被标记为已删除。
          </p>
        </div>
      </Modal>
    </>
  );
};

export default WorkflowInstanceList;