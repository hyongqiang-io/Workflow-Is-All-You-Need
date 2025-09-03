import React, { useState, useEffect, useMemo } from 'react';
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
import ExpandableSubWorkflowNode from './ExpandableSubWorkflowNode';
import SubWorkflowContainer from './SubWorkflowContainer';
import { useSubWorkflowExpansion } from '../hooks/useSubWorkflowExpansion';

// 导入主工作流的CustomInstanceNode组件
import { CustomInstanceNode } from './CustomInstanceNode';

const { Title, Text, Paragraph } = Typography;

interface TaskNode {
  id: string;
  name: string;
  description: string;
  type: 'start' | 'process' | 'decision' | 'end' | 'human' | 'ai' | 'processor';
  status: 'pending' | 'waiting' | 'running' | 'in_progress' | 'completed' | 'failed' | 'blocked' | 'cancelled';
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
  // 子工作流节点专有字段
  isSubWorkflowNode?: boolean;
  workflow_instance_id?: string;
  node_instance_id?: string;
  retry_count?: number;
  task_count?: number;
  error_message?: string;
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
  disableNodeClick?: boolean; // 新增：是否禁用节点点击
}

// 使用主工作流的CustomInstanceNode组件，包装任务特定的功能
const TaskNodeWrapper: React.FC<{ data: any }> = ({ data }) => {
  // 检查是否是子工作流容器
  if (data.isSubWorkflowContainer) {
    console.log('🔍 [TaskNodeWrapper] 渲染子工作流容器:', data);
    return (
      <SubWorkflowContainer
        subWorkflow={data.subWorkflow}
        parentNodeId={data.parentNodeId}
        expansionLevel={data.expansionLevel}
        onCollapse={data.onCollapse}
        onNodeClick={data.onNodeClick || (() => {})} // 传递节点点击回调
        workflowInstanceId={data.subWorkflow?.sub_workflow_instance_id}
      />
    );
  }

  // 将TaskFlowViewer的数据格式转换为CustomInstanceNode需要的格式
  const nodeData = {
    ...data,
    // 基础信息映射
    label: data.task?.task_title || data.label,
    status: data.task?.status || data.status,
    
    // 添加任务特定的标识
    showTaskActions: true,
    task: data.task,
    
    // 保持原有的回调
    onNodeClick: data.onNodeClick,
    onNodeDoubleClick: data.onNodeDoubleClick,
    
    // 任务操作回调映射
    onStartTask: data.onStartTask,
    onCompleteTask: data.onCompleteTask,
    onPauseTask: data.onPauseTask,
    onSubdivideTask: data.onSubdivideTask
  };

  return <CustomInstanceNode data={nodeData} selected={data.selected} />;
};

const nodeTypes: NodeTypes = {
  taskNode: ExpandableSubWorkflowNode,
  default: TaskNodeWrapper, // 使用包装后的CustomInstanceNode
};

const TaskFlowViewer: React.FC<TaskFlowViewerProps> = ({ 
  workflowId, 
  currentUserId, 
  onTaskAction,
  disableNodeClick = false // 默认不禁用节点点击
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

  // 使用子工作流展开功能
  const {
    loadSubdivisionInfo,
    expandNode,
    collapseNode,
    getNodeExpansionState,
    getNodeSubdivisionInfo,
    hasSubdivision,
    isExpandable,
    subdivisionInfo,
    isLoadingSubdivisionInfo
  } = useSubWorkflowExpansion({
    workflowInstanceId: workflowId,
    onExpansionChange: (nodeId, isExpanded) => {
      console.log(`Node ${nodeId} expansion changed to:`, isExpanded);
      // 可以在这里添加额外的逻辑，比如更新布局
    }
  });

  useEffect(() => {
    loadTaskFlow();
  }, [workflowId]); // 移除loadSubdivisionInfo依赖

  useEffect(() => {
    // 单独处理subdivision信息加载
    if (workflowId) {
      console.log('🔍 TaskFlowViewer: 开始加载subdivision信息, workflowId:', workflowId);
      loadSubdivisionInfo(workflowId);
    }
  }, [workflowId]); // 只依赖workflowId

  useEffect(() => {
    console.log('🔍 TaskFlowViewer: subdivisionInfo状态更新:', subdivisionInfo);
    console.log('🔍 TaskFlowViewer: 有subdivision的节点:', Object.keys(subdivisionInfo).filter(id => subdivisionInfo[id]?.has_subdivision));
  }, [subdivisionInfo]);

  useEffect(() => {
    if (taskFlow) {
      updateFlowView();
    }
  }, [taskFlow, subdivisionInfo]); // 当subdivisionInfo变化时也更新视图

  const loadTaskFlow = async () => {
    setLoading(true);
    try {
      const response: any = await executionAPI.getWorkflowTaskFlow(workflowId);
      if (response && response.success && response.data) {
        console.log('🔄 [TaskFlowViewer] API响应数据:', {
          hasNodes: !!(response.data.nodes && response.data.nodes.length),
          nodesCount: response.data.nodes?.length || 0,
          hasEdges: !!(response.data.edges && response.data.edges.length),
          edgesCount: response.data.edges?.length || 0,
          edges: response.data.edges
        });
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

  // 智能布局算法 - 基于执行顺序的垂直排列
  const calculateOptimizedLayout = (nodes: any[], expandedNodeIds: string[]) => {
    console.log('🔄 [TaskFlowViewer] 开始计算垂直布局:', {
      nodesCount: nodes.length,
      expandedNodeIds,
      nodes: nodes.map(n => ({ id: n.node_instance_id, name: n.node_name, type: n.node_type }))
    });

    const verticalGap = 180; // 节点间的垂直间距
    const horizontalOffset = 300; // 水平偏移（居中）
    
    const positions: Record<string, { x: number; y: number }> = {};
    
    // 首先尝试根据节点连接关系确定执行顺序
    const sortedNodes = calculateExecutionOrder(nodes);
    console.log('📊 [TaskFlowViewer] 执行顺序计算完成:', {
      originalOrder: nodes.map(n => n.node_name),
      sortedOrder: sortedNodes.map(n => n.node_name)
    });
    
    // 为每个节点按执行顺序计算垂直位置
    let currentY = 50; // 起始Y坐标
    
    sortedNodes.forEach((node, orderIndex) => {
      const nodeId = node.node_instance_id || `node-${orderIndex}`;
      
      // 基础位置：水平居中，垂直按顺序排列
      let baseX = horizontalOffset;
      let baseY = currentY;
      
      // 检查是否有展开的子工作流，如果有则为后续节点留出额外空间
      if (expandedNodeIds.includes(nodeId)) {
        // 为展开的子工作流预留更多垂直空间
        currentY += verticalGap + 300; // 额外空间给子工作流
      } else {
        currentY += verticalGap;
      }
      
      // 处理并行分支：如果多个节点没有严格的先后关系，可以水平排列
      const parallelNodes = findParallelNodes(node);
      if (parallelNodes.length > 1) {
        parallelNodes.forEach((parallelNode, parallelIndex) => {
          const parallelNodeId = parallelNode.node_instance_id || `node-${parallelIndex}`;
          positions[parallelNodeId] = {
            x: baseX + (parallelIndex - Math.floor(parallelNodes.length / 2)) * 250,
            y: baseY
          };
        });
      } else {
        positions[nodeId] = {
          x: baseX,
          y: baseY
        };
      }

      console.log(`📍 [TaskFlowViewer] 节点 ${node.node_name} (${nodeId}) 位置:`, {
        x: positions[nodeId]?.x || baseX,
        y: positions[nodeId]?.y || baseY,
        orderIndex
      });
    });
    
    console.log('✅ [TaskFlowViewer] 垂直布局计算完成:', positions);
    return positions;
  };

  // 计算节点的执行顺序
  const calculateExecutionOrder = (nodes: any[]) => {
    console.log('🔄 [calculateExecutionOrder] 开始计算执行顺序:', {
      nodesCount: nodes.length,
      hasEdges: !!(taskFlow?.edges && taskFlow.edges.length > 0),
      edgesCount: taskFlow?.edges?.length || 0
    });

    // 如果有edges信息，根据连接关系进行拓扑排序
    if (taskFlow?.edges && taskFlow.edges.length > 0) {
      console.log('📈 [calculateExecutionOrder] 使用拓扑排序:', taskFlow.edges);
      return topologicalSort(nodes, taskFlow.edges);
    }
    
    console.log('📝 [calculateExecutionOrder] 使用属性排序（没有edges数据）');
    // 如果没有连接信息，尝试根据其他属性排序
    return nodes.sort((a, b) => {
      // 1. 优先按节点类型排序（start -> process -> end）
      const typeOrder: Record<string, number> = { 'start': 0, 'process': 1, 'processor': 1, 'human': 1, 'ai': 1, 'decision': 2, 'end': 3 };
      const aTypeOrder = typeOrder[a.node_type as string] || 1;
      const bTypeOrder = typeOrder[b.node_type as string] || 1;
      
      if (aTypeOrder !== bTypeOrder) {
        console.log(`⚖️ [calculateExecutionOrder] 按类型排序: ${a.node_name}(${a.node_type}:${aTypeOrder}) vs ${b.node_name}(${b.node_type}:${bTypeOrder})`);
        return aTypeOrder - bTypeOrder;
      }
      
      // 2. 按创建时间排序
      if (a.created_at && b.created_at) {
        console.log(`⏰ [calculateExecutionOrder] 按时间排序: ${a.node_name}(${a.created_at}) vs ${b.node_name}(${b.created_at})`);
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      
      // 3. 按位置排序（如果有position信息）
      if (a.position && b.position) {
        console.log(`📍 [calculateExecutionOrder] 按位置排序: ${a.node_name}(${a.position.y},${a.position.x}) vs ${b.node_name}(${b.position.y},${b.position.x})`);
        return a.position.y - b.position.y || a.position.x - b.position.x;
      }
      
      // 4. 最后按名称排序
      console.log(`🔤 [calculateExecutionOrder] 按名称排序: ${a.node_name} vs ${b.node_name}`);
      return (a.node_name || '').localeCompare(b.node_name || '');
    });
  };

  // 拓扑排序实现
  const topologicalSort = (nodes: any[], edges: any[]) => {
    console.log('🔄 [topologicalSort] 开始拓扑排序:', { nodes: nodes.length, edges: edges.length });
    
    const graph = new Map<string, string[]>();
    const inDegree = new Map<string, number>();
    const nodeMap = new Map<string, any>();
    
    // 初始化图结构
    nodes.forEach(node => {
      const nodeId = node.node_instance_id || node.id;
      graph.set(nodeId, []);
      inDegree.set(nodeId, 0);
      nodeMap.set(nodeId, node);
    });
    
    // 构建图和计算入度
    edges.forEach(edge => {
      const from = edge.source;
      const to = edge.target;
      
      if (graph.has(from) && graph.has(to)) {
        graph.get(from)?.push(to);
        inDegree.set(to, (inDegree.get(to) || 0) + 1);
        console.log(`🔗 [topologicalSort] 边: ${from} -> ${to}`);
      } else {
        console.warn(`⚠️ [topologicalSort] 无效边: ${from} -> ${to} (节点不存在)`);
      }
    });
    
    // 拓扑排序
    const queue: string[] = [];
    const result: any[] = [];
    
    // 找到所有入度为0的节点
    inDegree.forEach((degree, nodeId) => {
      if (degree === 0) {
        queue.push(nodeId);
        console.log(`🚀 [topologicalSort] 起始节点: ${nodeId} (入度: ${degree})`);
      }
    });
    
    while (queue.length > 0) {
      const currentId = queue.shift()!;
      const currentNode = nodeMap.get(currentId);
      if (currentNode) {
        result.push(currentNode);
        console.log(`✅ [topologicalSort] 处理节点: ${currentNode.node_name} (${currentId})`);
      }
      
      // 减少邻接节点的入度
      graph.get(currentId)?.forEach(neighborId => {
        const newDegree = (inDegree.get(neighborId) || 0) - 1;
        inDegree.set(neighborId, newDegree);
        if (newDegree === 0) {
          queue.push(neighborId);
          console.log(`➡️ [topologicalSort] 节点可处理: ${neighborId} (入度: ${newDegree})`);
        }
      });
    }
    
    // 如果还有节点没有被排序（可能存在环），则追加到结果中
    nodes.forEach(node => {
      const nodeId = node.node_instance_id || node.id;
      if (!result.find(n => (n.node_instance_id || n.id) === nodeId)) {
        result.push(node);
        console.log(`⚠️ [topologicalSort] 追加未排序节点: ${node.node_name} (${nodeId})`);
      }
    });
    
    console.log('✅ [topologicalSort] 拓扑排序完成:', result.map(n => n.node_name));
    return result;
  };

  // 查找并行执行的节点
  const findParallelNodes = (currentNode: any) => {
    // 简单实现：目前只返回当前节点，后续可以根据实际需求扩展
    // 可以根据节点的依赖关系、执行时间等判断哪些节点可以并行执行
    return [currentNode];
  };

  // 生成默认的节点连接关系（当API没有提供edges时）
  const generateDefaultEdges = (nodes: any[]): any[] => {
    console.log('🔗 [TaskFlowViewer] 生成默认边连接:', nodes.length);
    
    if (!nodes || nodes.length < 2) {
      console.log('📝 [TaskFlowViewer] 节点数量不足，无需生成边');
      return [];
    }

    const defaultEdges: any[] = [];
    
    // 根据节点类型和执行顺序生成简单的线性连接
    const sortedNodes = calculateExecutionOrder(nodes);
    
    for (let i = 0; i < sortedNodes.length - 1; i++) {
      const currentNode = sortedNodes[i];
      const nextNode = sortedNodes[i + 1];
      
      const currentId = currentNode.node_instance_id || `node-${i}`;
      const nextId = nextNode.node_instance_id || `node-${i + 1}`;
      
      // 跳过end节点作为源节点
      if (currentNode.node_type === 'end') continue;
      
      // 跳过start节点作为目标节点（除非它是第一个节点）
      if (nextNode.node_type === 'start' && i > 0) continue;
      
      const edge = {
        id: `default-edge-${i}`,
        source: currentId,
        target: nextId,
        label: `步骤 ${i + 1}`,
        type: 'default'
      };
      
      defaultEdges.push(edge);
      console.log(`🔗 [generateDefaultEdges] 生成边: ${currentNode.node_name} -> ${nextNode.node_name}`);
    }
    
    console.log('✅ [generateDefaultEdges] 生成完成，总计:', defaultEdges.length, '条边');
    return defaultEdges;
  };

  const updateFlowView = () => {
    if (!taskFlow) return;

    // 获取当前展开的节点ID列表
    const expandedNodeIds = Object.keys(subdivisionInfo).filter(nodeId => {
      const expansionState = getNodeExpansionState(nodeId);
      return expansionState.isExpanded;
    });

    // 计算优化后的布局
    const optimizedPositions = calculateOptimizedLayout(taskFlow.nodes || [], expandedNodeIds);

    // 生成主要的节点和子工作流容器
    const allNodes: Node[] = [];
    const allEdges: Edge[] = [];

    // 转换主要节点为ReactFlow格式（使用优化后的位置）
    const flowNodes: Node[] = (taskFlow.nodes || []).map((node, index) => {
      // 查找该节点关联的任务以获取分配信息
      const nodeTasks = (taskFlow.tasks || []).filter(task => task.node_instance_id === node.node_instance_id);
      const primaryTask = nodeTasks.length > 0 ? nodeTasks[0] : null;
      const nodeInstanceId = node.node_instance_id || `node-${index}`;
      
      // 获取节点的细分信息和展开状态
      const subWorkflowInfo = getNodeSubdivisionInfo(nodeInstanceId);
      const expansionState = getNodeExpansionState(nodeInstanceId);
      
      // 使用优化后的位置
      const position = optimizedPositions[nodeInstanceId] || { x: 300, y: 50 + index * 180 }; // 垂直布局作为回退
      
      console.log(`🎯 [updateFlowView] 节点 ${node.node_name} 最终位置:`, {
        nodeInstanceId,
        position,
        hasOptimizedPosition: !!optimizedPositions[nodeInstanceId],
        optimizedPosition: optimizedPositions[nodeInstanceId]
      });
      
      return {
        id: nodeInstanceId,
        type: 'taskNode',
        position,
        data: {
          task: {
            id: nodeInstanceId,
            name: node.node_name || '未命名节点',
            type: node.node_type || 'process',
            status: node.status || 'pending', // 来自数据库的实时状态
            description: node.description || '',
            assignee: primaryTask?.assignee || null, // 从任务中获取分配信息
            position,
            execution_duration_seconds: node.execution_duration_seconds,
            retry_count: node.retry_count,
            task_count: node.task_count,
            error_message: node.error_message,
            start_at: node.start_at,
            completed_at: node.completed_at,
            input_data: node.input_data,
            output_data: node.output_data
          },
          isAssignedToMe: primaryTask?.assignee?.id === currentUserId,
          isCreator: taskFlow.creator ? currentUserId === taskFlow.creator.id : false,
          subWorkflowInfo,
          isExpanded: expansionState.isExpanded,
          isLoading: expansionState.isLoading,
          onStartTask: handleStartTask,
          onCompleteTask: handleCompleteTask,
          onPauseTask: handlePauseTask,
          onSubdivideTask: handleSubdivideTask,
          onExpandNode: expandNode,
          onCollapseNode: collapseNode,
          onNodeClick: handleNodeClick // 添加主工作流节点点击处理
        }
      };
    });

    allNodes.push(...flowNodes);

    // 转换边为ReactFlow格式（使用实际的边缘数据或生成默认边）
    let edgesData = taskFlow.edges;
    
    // 如果没有边数据，生成默认连接关系
    if (!edgesData || edgesData.length === 0) {
      console.log('📝 [updateFlowView] 没有边数据，生成默认连接');
      edgesData = generateDefaultEdges(taskFlow.nodes || []);
    }
    
    const flowEdges: Edge[] = (edgesData || []).map((edge, index) => ({
      id: edge.id || `edge-${index}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      type: edge.type || 'smoothstep',
      style: { 
        stroke: edge.type === 'default' ? '#52c41a' : '#1890ff', 
        strokeWidth: 2,
        strokeDasharray: edge.type === 'default' ? '5,5' : undefined
      },
      labelStyle: edge.type === 'default' ? { fontSize: '12px', fill: '#52c41a' } : undefined
    }));

    allEdges.push(...flowEdges);
    
    console.log('📊 [updateFlowView] 边生成完成:', {
      originalEdges: taskFlow.edges?.length || 0,
      generatedEdges: edgesData?.length || 0,
      finalEdges: flowEdges.length,
      edgesList: flowEdges.map(e => `${e.source} -> ${e.target} (${e.label})`)
    });

    // 为展开的节点添加子工作流容器节点
    flowNodes.forEach((node) => {
      const expansionState = getNodeExpansionState(node.id);
      
      if (expansionState.isExpanded && expansionState.subWorkflowData) {
        expansionState.subWorkflowData.forEach((subWorkflow, subIndex) => {
          // 为每个子工作流创建一个容器节点
          const containerId = `subworkflow-${node.id}-${subWorkflow.subdivision_id}`;
          
          // 智能计算子工作流容器位置
          const containerPosition = {
            x: node.position.x + 350, // 在父节点右侧
            y: node.position.y + (subIndex * 450) // 垂直堆叠多个子工作流
          };
          
          const containerNode: Node = {
            id: containerId,
            type: 'default', // 使用默认类型，在渲染中特殊处理
            position: containerPosition,
            data: {
              isSubWorkflowContainer: true,
              subWorkflow,
              parentNodeId: node.id,
              expansionLevel: 0,
              onCollapse: collapseNode,
              onNodeClick: (task: any) => {
                // 直接使用主工作流的Modal显示逻辑
                setSelectedTask(task);
                setDetailModalVisible(true);
              }
            },
            draggable: false,
            selectable: false,
            zIndex: 1000 // 确保子工作流容器在最上层
          };

          allNodes.push(containerNode);

          // 添加从父节点到子工作流容器的连接线
          const connectionEdge: Edge = {
            id: `connection-${node.id}-${containerId}`,
            source: node.id,
            target: containerId,
            type: 'smoothstep',
            style: { 
              stroke: '#52c41a', 
              strokeWidth: 3,
              strokeDasharray: '8,8' 
            },
            label: '细分工作流',
            labelStyle: { fontSize: '12px', fontWeight: 'bold', fill: '#52c41a' },
            labelBgStyle: { fill: '#f6ffed', fillOpacity: 0.9 },
            zIndex: 999
          };

          allEdges.push(connectionEdge);
        });
      }
    });

    setNodes(allNodes);
    setEdges(allEdges);
  };

  const handleStartTask = (taskId: string) => {
    onTaskAction?.(taskId, 'start');
    // 更新本地状态
    setTaskFlow(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        nodes: prev.nodes.map(node => 
          (node.node_instance_id || node.id) === taskId 
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
          (node.node_instance_id || node.id) === taskId 
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
          (node.node_instance_id || node.id) === taskId 
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

  // 节点点击处理 - 可根据disableNodeClick属性禁用
  const handleNodeClick = (event: any, node: Node) => {
    if (disableNodeClick) {
      console.log('🚫 [TaskFlowViewer] 节点点击已被禁用 (子工作流模式)');
      return;
    }
    
    console.log('🖱️ [TaskFlowViewer] 节点点击:', { event, node });
    
    // 直接查找主工作流节点 - 使用node_instance_id匹配
    let task = taskFlow?.nodes.find(n => (n.node_instance_id || n.id) === node.id);
    
    if (task) {
      // 确保包含所有需要的数据，包括input_data和output_data
      const taskWithAllData = {
        ...task,
        // 基础任务信息
        name: task.node_name || task.name || '未命名节点',
        type: task.node_type || task.type || 'process',
        created_at: task.created_at,
        started_at: task.start_at,
        completed_at: task.completed_at,
        estimated_duration: task.estimated_duration,
        actual_duration: task.execution_duration_seconds,
        // 确保包含输入输出数据
        input_data: task.input_data,
        output_data: task.output_data
      };
      setSelectedTask(taskWithAllData);
      setDetailModalVisible(true);
    } else if (node.data && node.data.task) {
      // 如果没有找到原始节点，尝试从node.data中获取任务信息
      setSelectedTask(node.data.task);
      setDetailModalVisible(true);
    } else if (node.data) {
      // 最后的回退：子工作流节点直接使用原始数据
      setSelectedTask(node.data);
      setDetailModalVisible(true);
    } else {
      console.warn('⚠️ [TaskFlowViewer] 无法找到节点对应的任务信息:', node);
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
        width="90%"
        style={{ maxWidth: '1000px', top: 20 }}
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
                selectedTask.type === 'ai' ? 'purple' :
                selectedTask.type === 'processor' ? 'cyan' : 'orange'
              }>
                {selectedTask.type === 'start' ? '开始节点' :
                 selectedTask.type === 'end' ? '结束节点' :
                 selectedTask.type === 'human' ? '人工任务' :
                 selectedTask.type === 'ai' ? 'AI任务' :
                 selectedTask.type === 'processor' ? '处理节点' :
                 selectedTask.type === 'decision' ? '决策节点' : '处理节点'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="任务状态">
              <Tag color={
                selectedTask.status === 'pending' ? 'orange' :
                selectedTask.status === 'waiting' ? 'blue' :
                selectedTask.status === 'running' ? 'blue' :
                selectedTask.status === 'in_progress' ? 'blue' :
                selectedTask.status === 'completed' ? 'green' :
                selectedTask.status === 'failed' ? 'red' :
                selectedTask.status === 'cancelled' ? 'gray' : 'purple'
              }>
                {selectedTask.status === 'pending' ? '待处理' :
                 selectedTask.status === 'waiting' ? '等待中' :
                 selectedTask.status === 'running' ? '运行中' :
                 selectedTask.status === 'in_progress' ? '进行中' :
                 selectedTask.status === 'completed' ? '已完成' :
                 selectedTask.status === 'failed' ? '失败' :
                 selectedTask.status === 'cancelled' ? '已取消' :
                 selectedTask.status === 'blocked' ? '阻塞' : '未知'}
              </Tag>
            </Descriptions.Item>
            
            {/* 子工作流节点特有信息 */}
            {selectedTask.isSubWorkflowNode && (
              <>
                <Descriptions.Item label="节点来源">
                  <Tag color="purple">子工作流节点</Tag>
                </Descriptions.Item>
                {selectedTask.workflow_instance_id && (
                  <Descriptions.Item label="所属工作流实例">
                    <Text code>{selectedTask.workflow_instance_id}</Text>
                  </Descriptions.Item>
                )}
                {selectedTask.node_instance_id && (
                  <Descriptions.Item label="节点实例ID">
                    <Text code>{selectedTask.node_instance_id}</Text>
                  </Descriptions.Item>
                )}
              </>
            )}
            
            {selectedTask.assignee && (
              <Descriptions.Item label="执行者">
                <Space>
                  {selectedTask.assignee.type === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  {selectedTask.assignee.name}
                </Space>
              </Descriptions.Item>
            )}
            
            {/* 执行详细信息 */}
            {(selectedTask.retry_count && selectedTask.retry_count > 0) && (
              <Descriptions.Item label="重试次数">
                <Tag color="orange">{selectedTask.retry_count} 次</Tag>
              </Descriptions.Item>
            )}
            
            {(selectedTask.task_count && selectedTask.task_count > 0) && (
              <Descriptions.Item label="任务数量">
                <Badge count={selectedTask.task_count} style={{ backgroundColor: '#52c41a' }} />
              </Descriptions.Item>
            )}
            
            {selectedTask.error_message && (
              <Descriptions.Item label="错误信息">
                <Text type="danger">{selectedTask.error_message}</Text>
              </Descriptions.Item>
            )}
            
            <Descriptions.Item label="创建时间">
              {selectedTask.created_at ? formatDate(selectedTask.created_at) : '-'}
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
            
            {/* 输入数据 */}
            {selectedTask.input_data && (
              <Descriptions.Item label="输入数据">
                <div style={{
                  maxHeight: '200px',
                  overflowY: 'auto',
                  border: '1px solid #d9d9d9',
                  borderRadius: '4px',
                  padding: '8px',
                  backgroundColor: '#f5f5f5',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {typeof selectedTask.input_data === 'string' 
                    ? selectedTask.input_data 
                    : JSON.stringify(selectedTask.input_data, null, 2)}
                </div>
              </Descriptions.Item>
            )}
            
            {/* 输出数据 */}
            {selectedTask.output_data && (
              <Descriptions.Item label="输出数据">
                <div style={{
                  maxHeight: '200px',
                  overflowY: 'auto',
                  border: '1px solid #d9d9d9',
                  borderRadius: '4px',
                  padding: '8px',
                  backgroundColor: '#f5f5f5',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {typeof selectedTask.output_data === 'string' 
                    ? selectedTask.output_data 
                    : JSON.stringify(selectedTask.output_data, null, 2)}
                </div>
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