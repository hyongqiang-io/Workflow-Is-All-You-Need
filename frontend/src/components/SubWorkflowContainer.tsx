import React from 'react';
import { Card, Typography, Tag, Progress, Space, Button, Tooltip } from 'antd';
import { 
  BranchesOutlined,
  ShrinkOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import ReactFlow, { 
  Controls, 
  Background, 
  useNodesState,
  useEdgesState,
  ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import './SubWorkflowExpansion.css';

// 直接复用主工作流的组件和逻辑
import { useSubWorkflowExpansion } from '../hooks/useSubWorkflowExpansion';
// 导入工作流实例列表组件中的节点显示逻辑
import { CustomInstanceNode } from './CustomInstanceNode';
import { executionAPI } from '../services/api';
// 导入主工作流的布局算法和连接逻辑
import { 
  validateAndFixEdges, 
  generateMissingConnections, 
  calculateDependencyBasedLayout 
} from '../utils/workflowLayoutUtils';

const { Title, Text } = Typography;

// 直接使用主工作流的节点数据结构，无需转换
interface SubWorkflowNode {
  node_instance_id: string;
  node_id: string;
  node_name: string;
  node_type: string;
  status: string;
  task_count: number;
  processor_name?: string;
  processor_type?: string;
  retry_count?: number;
  execution_duration_seconds?: number;
  input_data?: any;  // 直接使用解析后的对象
  output_data?: any; // 直接使用解析后的对象
  error_message?: string;
  start_at?: string;
  completed_at?: string;
  tasks?: any[];
  position?: { x: number; y: number };
  timestamps?: {
    created_at?: string;
    started_at?: string;
    completed_at?: string;
  };
}

interface SubWorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  from_node_name?: string;
  to_node_name?: string;
}

interface SubWorkflowDetail {
  subdivision_id: string;
  sub_workflow_instance_id?: string;
  subdivision_name: string;
  status: 'draft' | 'running' | 'completed' | 'failed' | 'cancelled';
  nodes: SubWorkflowNode[];
  edges: SubWorkflowEdge[];
  total_nodes: number;
  completed_nodes: number;
  running_nodes: number;
  failed_nodes: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface SubWorkflowContainerProps {
  subWorkflow: SubWorkflowDetail;
  parentNodeId: string;
  expansionLevel: number;
  onCollapse: (nodeId: string) => void;
  onNodeClick?: (task: any) => void; // 统一使用主工作流的task格式
  className?: string;
  style?: React.CSSProperties;
  // 新增：支持递归subdivision查询的工作流实例ID
  workflowInstanceId?: string;
}

// 直接复用主工作流的节点类型
const subWorkflowNodeTypes = {
  customInstance: CustomInstanceNode,
};

const SubWorkflowContainer: React.FC<SubWorkflowContainerProps> = ({
  subWorkflow,
  parentNodeId,
  expansionLevel,
  onCollapse,
  onNodeClick,
  className,
  style,
  workflowInstanceId
}) => {
  
  // 直接使用子工作流节点数据，无需转换
  
  // 直接从API获取任务流数据，使用与主工作流相同的接口
  const [taskFlowData, setTaskFlowData] = React.useState<any>(null);
  const [loadingTaskFlow, setLoadingTaskFlow] = React.useState(true);
  
  // 使用与主工作流相同的subdivision支持
  const targetWorkflowInstanceId = subWorkflow.sub_workflow_instance_id || workflowInstanceId;
  
  // 直接使用主工作流的subdivision扩展功能
  const {
    loadSubdivisionInfo,
    collapseNode,
    subdivisionInfo
  } = useSubWorkflowExpansion({
    workflowInstanceId: targetWorkflowInstanceId,
    onExpansionChange: (nodeId, isExpanded) => {
      console.log(`🔍 [SubWorkflowContainer] 层级${expansionLevel + 1} 节点展开变化:`, nodeId, isExpanded);
    }
  });
  // 直接使用主工作流的任务流加载逻辑
  React.useEffect(() => {
    const loadTaskFlowData = async () => {
      if (!subWorkflow.sub_workflow_instance_id) {
        console.warn('⚠️ [SubWorkflowContainer] 缺少子工作流实例ID');
        setLoadingTaskFlow(false);
        return;
      }
      
      try {
        // 直接使用主工作流的task-flow API
        const response: any = await executionAPI.getWorkflowTaskFlow(subWorkflow.sub_workflow_instance_id);
        
        if (response && response.success && response.data) {
          setTaskFlowData(response.data);
          console.log('✅ [SubWorkflowContainer] 任务流数据加载成功');
        } else {
          console.warn('⚠️ [SubWorkflowContainer] API响应格式异常:', response);
        }
      } catch (error) {
        console.error('❌ [SubWorkflowContainer] 加载任务流数据失败:', error);
      } finally {
        setLoadingTaskFlow(false);
      }
    };
    
    loadTaskFlowData();
  }, [subWorkflow.sub_workflow_instance_id]);
  
  // 直接使用主工作流的subdivision信息加载逻辑
  React.useEffect(() => {
    if (targetWorkflowInstanceId) {
      loadSubdivisionInfo(targetWorkflowInstanceId);
    }
  }, [subWorkflow.sub_workflow_instance_id, workflowInstanceId, expansionLevel]); // 移除函数依赖
  
  // 使用与主工作流相同的智能布局算法
  const calculateOptimizedSubWorkflowLayout = (nodes: any[], edges: any[]) => {
    console.log('📐 [SubWorkflowContainer] 开始使用主工作流布局算法');
    console.log('   - 节点数量:', nodes.length);
    console.log('   - 边数量:', edges.length);
    console.log('   - 原始节点数据:', nodes.map(n => ({
      node_instance_id: n.node_instance_id,
      node_id: n.node_id,
      id: n.id,
      node_name: n.node_name,
      name: n.name
    })));
    console.log('   - 原始边数据:', edges.map(e => ({
      id: e.id,
      source: e.source,
      target: e.target,
      from_node_instance_id: e.from_node_instance_id,
      to_node_instance_id: e.to_node_instance_id,
      from_node_id: e.from_node_id,
      to_node_id: e.to_node_id,
      label: e.label
    })));

    // **关键修复：子工作流的边数据可能使用不同的ID格式**
    const normalizedEdges = edges.map(edge => {
      // 尝试各种可能的源节点ID字段
      const source = edge.source || 
                    edge.from_node_instance_id || 
                    edge.from_node_id || 
                    edge.sourceId;
      
      // 尝试各种可能的目标节点ID字段
      const target = edge.target || 
                    edge.to_node_instance_id || 
                    edge.to_node_id || 
                    edge.targetId;
      
      console.log(`🔧 [SubWorkflowContainer] 边ID标准化: 
        原始: {source: ${edge.source}, target: ${edge.target}}
        from_node_*: {from_node_instance_id: ${edge.from_node_instance_id}, from_node_id: ${edge.from_node_id}}
        to_node_*: {to_node_instance_id: ${edge.to_node_instance_id}, to_node_id: ${edge.to_node_id}}
        标准化后: {source: ${source}, target: ${target}}`
      );
      
      return {
        ...edge,
        source,
        target
      };
    });

    console.log('🔧 [SubWorkflowContainer] 标准化后的边数据:', normalizedEdges);

    // 1. 验证和修复边数据
    const validatedEdges = validateAndFixEdges(nodes, normalizedEdges);
    console.log('✅ [SubWorkflowContainer] 边数据验证完成，有效边数量:', validatedEdges.length);

    // 2. 如果没有有效边，生成智能连接
    const finalEdges = validatedEdges.length > 0 ? 
      validatedEdges : 
      generateMissingConnections(nodes);

    console.log('🎯 [SubWorkflowContainer] 最终使用的边数据:', finalEdges);

    // 3. 使用基于依赖关系的智能布局
    const positions = calculateDependencyBasedLayout(nodes, finalEdges);
    
    console.log('📍 [SubWorkflowContainer] 智能布局计算完成:', positions);
    
    return { positions, edges: finalEdges };
  };

  // 直接使用主工作流的ReactFlow节点转换逻辑
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  // 当taskFlowData变化时更新节点和边 - 使用智能布局算法
  React.useEffect(() => {
    if (taskFlowData?.nodes && Array.isArray(taskFlowData.nodes)) {
      console.log('🔄 [SubWorkflowContainer] 开始使用智能布局转换数据');
      console.log('   - 节点数量:', taskFlowData.nodes.length);
      console.log('   - 原始边数据:', taskFlowData.edges);
      
      const sourceNodes = taskFlowData.nodes;
      const sourceEdges = taskFlowData.edges || [];
      
      // 使用主工作流的智能布局算法
      const { positions, edges: optimizedEdges } = calculateOptimizedSubWorkflowLayout(sourceNodes, sourceEdges);
      
      // 转换节点为ReactFlow格式
      const newNodes = sourceNodes.map((node: any, index: number) => {
        const nodeId = node.node_instance_id || node.id || `node-${index}`;
        
        console.log(`🔍 [SubWorkflowContainer] 处理节点:`, {
          nodeId,
          node_name: node.node_name,
          node_type: node.node_type,
          status: node.status,
          position: positions[nodeId]
        });
        
        const nodeData = {
          nodeId: nodeId,
          label: node.node_name || node.name || `节点 ${index + 1}`,
          status: node.status || 'unknown',
          processor_name: node.processor_name || '子工作流节点',
          processor_type: node.processor_type || node.node_type || 'unknown',
          task_count: node.task_count || 0,
          retry_count: node.retry_count || 0,
          execution_duration_seconds: node.execution_duration_seconds || 0,
          input_data: node.input_data || {},
          output_data: node.output_data || {},
          error_message: node.error_message || '',
          start_at: node.start_at || node.timestamps?.started_at,
          completed_at: node.completed_at || node.timestamps?.completed_at,
          tasks: node.tasks || [],
          onNodeClick: () => {
            console.log('🖱️ [SubWorkflowContainer] 节点点击:', node);
            onNodeClick?.(node);
          },
          expansionLevel: expansionLevel + 1
        };
        
        return {
          id: nodeId,
          type: 'customInstance',
          position: positions[nodeId] || { x: 300 + (index % 3) * 200, y: 100 + Math.floor(index / 3) * 150 },
          data: nodeData,
          draggable: false,
          selectable: true
        };
      });
      
      // 转换边为ReactFlow格式
      const newEdges = optimizedEdges.map((edge: any, index: number) => ({
        id: edge.id || `edge-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        type: 'smoothstep',
        style: { 
          stroke: '#52c41a', 
          strokeWidth: 2,
          strokeDasharray: edge.label === '智能连接' ? '5,5' : 'none'
        },
        labelStyle: { fontSize: '10px', fill: '#666' },
        labelBgStyle: { fill: '#f0f0f0', fillOpacity: 0.8 }
      }));
      
      console.log('✅ [SubWorkflowContainer] 智能布局转换完成');
      console.log('   - 节点数量:', newNodes.length);
      console.log('   - 边数量:', newEdges.length);
      console.log('   - 节点位置:', newNodes.map((n: any) => ({ id: n.id, position: n.position, label: n.data.label })));
      console.log('   - 边连接:', newEdges.map((e: any) => ({ id: e.id, source: e.source, target: e.target, label: e.label })));
      
      setNodes(newNodes);
      setEdges(newEdges);
      
    } else {
      console.log('📝 [SubWorkflowContainer] 数据为空，清空节点和边');
      setNodes([]);
      setEdges([]);
    }
  }, [taskFlowData, expansionLevel]); // 简化依赖，避免无限循环

  // 获取状态相关的样式和图标
  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'running':
        return { color: '#1890ff', icon: <PlayCircleOutlined />, text: '运行中' };
      case 'completed':
        return { color: '#52c41a', icon: <CheckCircleOutlined />, text: '已完成' };
      case 'failed':
        return { color: '#ff4d4f', icon: <ExclamationCircleOutlined />, text: '失败' };
      case 'draft':
        return { color: '#faad14', icon: <ClockCircleOutlined />, text: '草稿' };
      case 'cancelled':
        return { color: '#8c8c8c', icon: <InfoCircleOutlined />, text: '已取消' };
      default:
        return { color: '#d9d9d9', icon: <InfoCircleOutlined />, text: '未知' };
    }
  };

  const statusInfo = getStatusInfo(subWorkflow.status);
  
  // 直接使用taskFlowData的统计信息
  const statistics = taskFlowData?.statistics;
  const totalNodes = statistics?.total_nodes || 0;
  const completedNodes = statistics?.node_status_count?.completed || 0;
  const runningNodes = statistics?.node_status_count?.running || 0;
  const failedNodes = statistics?.node_status_count?.failed || 0;
  
  const progressPercentage = totalNodes > 0 
    ? Math.round((completedNodes / totalNodes) * 100) 
    : 0;

  return (
    <Card
      className={`subworkflow-container expansion-level-${expansionLevel} ${className || ''}`}
      style={{
        border: '2px dashed #52c41a',
        borderRadius: '12px',
        backgroundColor: 'rgba(240, 252, 240, 0.8)',
        margin: '16px',
        minWidth: '600px',
        minHeight: '400px',
        ...style
      }}
      styles={{ body: { padding: '16px' } }}
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <BranchesOutlined style={{ color: '#52c41a' }} />

            <Tag color={statusInfo.color} className={subWorkflow.status === 'running' ? 'status-running' : ''}>
              <span style={{ marginRight: '4px' }}>{statusInfo.icon}</span>
              {statusInfo.text}
            </Tag>
          </Space>
          
          <Space>

            <Tooltip title="收起子工作流">
              <Button
                type="text"
                size="small"
                icon={<ShrinkOutlined />}
                onClick={() => {
                  console.log('🔍 [SubWorkflowContainer] 收起按钮被点击，parentNodeId:', parentNodeId);
                  onCollapse(parentNodeId);
                }}
                style={{ color: '#52c41a' }}
              />
            </Tooltip>
          </Space>
        </div>
      }
      extra={
        <Space direction="vertical" size="small" style={{ textAlign: 'right' }}>

        </Space>
      }
    >
      {/* 子工作流统计信息 */}
      <div style={{ marginBottom: '16px', padding: '8px', backgroundColor: '#fafafa', borderRadius: '6px' }}>
        <Space wrap>
          <Tag color="blue">总节点: {totalNodes}</Tag>
          <Tag color="green">已完成: {completedNodes}</Tag>
          {runningNodes > 0 && (
            <Tag color="orange">运行中: {runningNodes}</Tag>
          )}
          {failedNodes > 0 && (
            <Tag color="red">失败: {failedNodes}</Tag>
          )}
        </Space>
        
        {subWorkflow.created_at && (
          <div style={{ marginTop: '8px' }}>
            <Text type="secondary" style={{ fontSize: '11px' }}>
              创建时间: {new Date(subWorkflow.created_at).toLocaleString('zh-CN')}
              {subWorkflow.completed_at && (
                <span style={{ marginLeft: '12px' }}>
                  完成时间: {new Date(subWorkflow.completed_at).toLocaleString('zh-CN')}
                </span>
              )}
            </Text>
          </div>
        )}
      </div>

      {/* 子工作流图形视图 */}
      <div style={{ height: '300px', border: '1px solid #e8e8e8', borderRadius: '6px' }}>

        
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={subWorkflowNodeTypes}
            fitView
            fitViewOptions={{ 
              padding: 0.2,
              maxZoom: 1.2,
              minZoom: 0.5
            }}
            defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={true}
            panOnDrag={true}
            zoomOnScroll={true}
            zoomOnPinch={true}
            preventScrolling={false}
          >
            <Controls 
              position="bottom-right"
            />
            <Background 
              color="#f0f0f0" 
              gap={20} 
              size={1} 
              style={{ opacity: 0.3 }}
            />

          </ReactFlow>
        </ReactFlowProvider>
        
        {/* 数据加载状态指示器 */}
        {loadingTaskFlow && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'rgba(255, 255, 255, 0.9)',
            padding: '20px',
            borderRadius: '8px',
            textAlign: 'center',
            zIndex: 999
          }}>
            <div style={{ fontSize: '14px', marginBottom: '8px' }}>正在加载子工作流数据...</div>
            <div style={{ fontSize: '12px', color: '#666' }}>请稍候</div>
          </div>
        )}
        
        {/* 无数据提示 */}
        {!loadingTaskFlow && nodes.length === 0 && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            textAlign: 'center',
            color: '#999',
            fontSize: '14px',
            zIndex: 999
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>📊</div>
            <div>子工作流暂无节点数据</div>
            <div style={{ fontSize: '12px', marginTop: '4px' }}>
              实例ID: {subWorkflow.sub_workflow_instance_id || '未指定'}
            </div>
          </div>
        )}
      </div>

      {/* 渲染递归展开的子工作流 - 暂时禁用，避免复杂的依赖循环 */}
      {/* 注释：为了避免函数依赖导致的无限循环，暂时禁用递归子工作流功能 */}
      {/* 后续可以考虑重新设计这个功能的实现方式 */}


    </Card>
  );
};

export default SubWorkflowContainer;