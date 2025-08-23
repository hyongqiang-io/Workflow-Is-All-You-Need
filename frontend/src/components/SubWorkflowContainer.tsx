import React, { useMemo } from 'react';
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
  MiniMap,
  useNodesState,
  useEdgesState,
  ReactFlowProvider
} from 'reactflow';
import 'reactflow/dist/style.css';
import './SubWorkflowExpansion.css';

// 导入统一的节点组件和hooks
import { useSubWorkflowExpansion } from '../hooks/useSubWorkflowExpansion';
// 导入主工作流的CustomInstanceNode组件
import { CustomInstanceNode } from './CustomInstanceNode';
// 导入统一的API
import { executionAPI } from '../services/api';

const { Title, Text } = Typography;

interface SubWorkflowNode {
  node_instance_id: string;
  node_id: string;
  node_name: string;
  node_type: string;
  status: string;
  task_count: number;
  created_at?: string;
  completed_at?: string;
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
  onNodeClick?: (node: SubWorkflowNode) => void;
  className?: string;
  style?: React.CSSProperties;
  // 新增：支持递归subdivision查询的工作流实例ID
  workflowInstanceId?: string;
}

// 统一的节点类型定义 - 使用导入的CustomInstanceNode
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
  
  // 添加节点详细信息状态 - 使用统一的task-flow数据结构
  const [taskFlowData, setTaskFlowData] = React.useState<any>(null);
  const [loadingTaskFlow, setLoadingTaskFlow] = React.useState(true);
  
  // 添加递归subdivision支持 - 确保使用正确的工作流实例ID
  const targetWorkflowInstanceId = subWorkflow.sub_workflow_instance_id || workflowInstanceId;
  
  console.log(`🔍 [SubWorkflowContainer] 层级${expansionLevel + 1} 初始化useSubWorkflowExpansion`);
  console.log(`   - 使用的工作流实例ID: ${targetWorkflowInstanceId}`);
  
  const {
    loadSubdivisionInfo,
    expandNode,
    collapseNode,
    getNodeExpansionState,
    getNodeSubdivisionInfo,
    subdivisionInfo
  } = useSubWorkflowExpansion({
    workflowInstanceId: targetWorkflowInstanceId,
    onExpansionChange: (nodeId, isExpanded) => {
      console.log(`🔍 [SubWorkflowContainer] 层级${expansionLevel + 1} 节点展开变化:`, nodeId, isExpanded);
      console.log(`   - 使用的工作流实例ID: ${targetWorkflowInstanceId}`);
    }
  });
  
  // 加载子工作流的task-flow数据 - 使用统一API
  React.useEffect(() => {
    const loadTaskFlowData = async () => {
      if (!subWorkflow.sub_workflow_instance_id) {
        console.warn('⚠️ [SubWorkflowContainer] 缺少子工作流实例ID，无法加载task-flow数据');
        console.warn('⚠️ [SubWorkflowContainer] subWorkflow对象:', subWorkflow);
        setLoadingTaskFlow(false);
        return;
      }
      
      console.log('🔄 [SubWorkflowContainer] 开始加载task-flow数据:', subWorkflow.sub_workflow_instance_id);
      console.log('🔄 [SubWorkflowContainer] 完整subWorkflow对象:', JSON.stringify(subWorkflow, null, 2));
      
      try {
        // 使用统一的task-flow API获取完整数据
        console.log('🌐 [SubWorkflowContainer] 调用API:', `/execution/workflows/${subWorkflow.sub_workflow_instance_id}/task-flow`);
        const response: any = await executionAPI.getWorkflowTaskFlow(subWorkflow.sub_workflow_instance_id);
        
        console.log('📥 [SubWorkflowContainer] API原始响应:', response);
        console.log('📥 [SubWorkflowContainer] 响应状态:', response?.status);
        console.log('📥 [SubWorkflowContainer] 响应数据类型:', typeof response?.data);
        
        if (response && response.data) {
          const flowData = response.data.data || response.data;
          console.log('📊 [SubWorkflowContainer] 解析后的flowData:', JSON.stringify(flowData, null, 2));
          console.log('📊 [SubWorkflowContainer] flowData.nodes数量:', flowData.nodes?.length);
          console.log('📊 [SubWorkflowContainer] flowData.tasks数量:', flowData.tasks?.length);
          console.log('📊 [SubWorkflowContainer] flowData.edges数量:', flowData.edges?.length);
          
          // 详细检查每个节点的数据
          if (flowData.nodes) {
            flowData.nodes.forEach((node: any, index: number) => {
              console.log(`🔍 [SubWorkflowContainer] 节点 ${index + 1} 详细信息:`, {
                node_instance_id: node.node_instance_id,
                node_name: node.node_name,
                node_type: node.node_type,
                status: node.status,
                processor_name: node.processor_name,
                processor_type: node.processor_type,
                task_count: node.task_count,
                tasks: node.tasks,
                input_data: node.input_data,
                output_data: node.output_data,
                timestamps: node.timestamps
              });
            });
          }
          
          setTaskFlowData(flowData);
          console.log('✅ [SubWorkflowContainer] task-flow数据加载完成:', flowData.nodes?.length, '个节点');
        } else {
          console.warn('⚠️ [SubWorkflowContainer] task-flow响应数据格式异常:', response);
          console.warn('⚠️ [SubWorkflowContainer] response.data:', response?.data);
          console.warn('⚠️ [SubWorkflowContainer] response结构:', Object.keys(response || {}));
        }
        
      } catch (error) {
        console.error('❌ [SubWorkflowContainer] 加载task-flow数据失败:', error);
        
        // Type-safe error handling
        const errorDetails: any = {};
        if (error instanceof Error) {
          errorDetails.message = error.message;
          errorDetails.stack = error.stack;
        }
        if (error && typeof error === 'object' && 'response' in error) {
          errorDetails.response = (error as any).response?.data;
        }
        
        console.error('❌ [SubWorkflowContainer] 错误详细信息:', errorDetails);
      } finally {
        setLoadingTaskFlow(false);
      }
    };
    
    loadTaskFlowData();
  }, [subWorkflow.sub_workflow_instance_id]);
  
  // 在组件加载时获取subdivision信息 - 确保使用正确的工作流实例ID
  React.useEffect(() => {
    // 优先使用子工作流的实例ID，如果没有则使用传入的workflowInstanceId
    const targetInstanceId = subWorkflow.sub_workflow_instance_id || workflowInstanceId;
    
    if (targetInstanceId) {
      console.log(`🔄 [SubWorkflowContainer] 层级${expansionLevel + 1} 加载subdivision信息`);
      console.log(`   - 目标工作流实例ID: ${targetInstanceId}`);
      console.log(`   - 子工作流实例ID: ${subWorkflow.sub_workflow_instance_id}`);
      console.log(`   - 传入的工作流实例ID: ${workflowInstanceId}`);
      console.log(`   - 预期API调用: /api/execution/workflows/${targetInstanceId}/subdivision-info`);
      
      loadSubdivisionInfo(targetInstanceId);
    } else {
      console.warn(`⚠️ [SubWorkflowContainer] 层级${expansionLevel + 1} 缺少工作流实例ID，无法加载subdivision信息`);
    }
  }, [subWorkflow.sub_workflow_instance_id, workflowInstanceId, loadSubdivisionInfo, expansionLevel]);
  
  // 计算布局位置 - 使用task-flow数据
  const calculateSubWorkflowLayout = (nodes: any[]) => {
    const nodeWidth = 180;
    const nodeHeight = 120;
    const horizontalGap = 200;
    const verticalGap = 150;
    
    // 简单的网格布局，可以后续优化为更智能的布局算法
    return nodes.map((node, index) => {
      const row = Math.floor(index / 3);
      const col = index % 3;
      
      return {
        x: col * horizontalGap,
        y: row * verticalGap
      };
    });
  };

  // 转换节点数据为ReactFlow格式 - 使用统一的task-flow数据结构
  const [nodes, setNodes, onNodesChange] = useNodesState(
    useMemo(() => {
      console.log('🔄 [SubWorkflowContainer] 开始转换节点数据');
      console.log('🔄 [SubWorkflowContainer] taskFlowData:', taskFlowData);
      console.log('🔄 [SubWorkflowContainer] subWorkflow.nodes:', subWorkflow.nodes);
      
      // 如果task-flow数据还没加载完成，使用fallback数据
      const sourceNodes = taskFlowData?.nodes || subWorkflow.nodes || [];
      console.log('🔄 [SubWorkflowContainer] 选择的sourceNodes数量:', sourceNodes.length);
      console.log('🔄 [SubWorkflowContainer] sourceNodes详细:', JSON.stringify(sourceNodes, null, 2));
      
      const positions = calculateSubWorkflowLayout(sourceNodes);
      
      return sourceNodes.map((node: any, index: number) => {
        const nodeId = node.node_instance_id;
        
        console.log(`🔍 [SubWorkflowContainer] 处理节点 ${index + 1}:`, {
          node_instance_id: nodeId,
          node_name: node.node_name,
          node_type: node.node_type,
          status: node.status,
          processor_name: node.processor_name,
          processor_type: node.processor_type,
          task_count: node.task_count,
          tasks_length: node.tasks?.length,
          has_input_data: !!node.input_data,
          has_output_data: !!node.output_data,
          has_timestamps: !!node.timestamps
        });
        
        // 获取递归subdivision信息
        const subWorkflowInfo = getNodeSubdivisionInfo(nodeId);
        const expansionState = getNodeExpansionState(nodeId);
        
        console.log(`🔍 [SubWorkflowContainer] 层级${expansionLevel + 1} 节点 ${node.node_name} subdivision信息:`, subWorkflowInfo);
        console.log(`📊 [SubWorkflowContainer] 节点 ${node.node_name} task-flow数据:`, node);
        
        // 构建节点数据 - 确保所有字段都有值
        const nodeData = {
          // 使用与主工作流相同的数据结构 - 直接使用task-flow数据
          nodeId: nodeId,
          label: node.node_name || node.name || `节点 ${index + 1}`,
          status: node.status || 'unknown',
          // 处理器信息 - 直接从task-flow数据获取，有fallback
          processor_name: node.processor_name || node.processor?.name || `子工作流节点`,
          processor_type: node.processor_type || node.processor?.type || node.node_type || 'unknown',
          task_count: node.task_count || node.tasks?.length || 0,
          // 详细信息 - 使用task-flow提供的完整数据，有fallback
          retry_count: node.retry_count || 0,
          execution_duration_seconds: node.execution_duration_seconds || 0,
          input_data: node.input_data || {},
          output_data: node.output_data || {},
          error_message: node.error_message || '',
          start_at: node.start_at || node.timestamps?.started_at || node.started_at,
          completed_at: node.completed_at || node.timestamps?.completed_at,
          tasks: node.tasks || [],
          onNodeClick: (nodeData: any) => {
            console.log('🖱️ [SubWorkflowContainer] 子工作流节点点击:', nodeData);
            // 构造符合Modal显示要求的节点数据格式
            const modalNodeData = {
              // 传递完整的原始节点数据作为基础
              ...node,
              // 覆盖和补充必要的字段
              id: nodeId,
              node_instance_id: nodeId,
              name: node.node_name || node.name,
              node_name: node.node_name || node.name,
              type: node.node_type,
              node_type: node.node_type,
              status: node.status,
              created_at: node.timestamps?.created_at || node.created_at,
              completed_at: node.completed_at || node.timestamps?.completed_at,
              task_count: node.task_count || node.tasks?.length || 0,
              // 添加其他可能需要的字段
              processor_type: node.processor_type || node.node_type,
              processor_name: node.processor_name,
              workflow_instance_id: subWorkflow.sub_workflow_instance_id || workflowInstanceId
            };
            console.log('🖱️ [SubWorkflowContainer] 传递给Modal的数据:', modalNodeData);
            onNodeClick?.(modalNodeData);
          },
          // 支持递归subdivision
          subWorkflowInfo,
          isExpanded: expansionState.isExpanded,
          isLoading: expansionState.isLoading,
          onExpandNode: expandNode,
          onCollapseNode: collapseNode,
          // 层级信息
          expansionLevel: expansionLevel + 1
        };
        
        console.log(`✅ [SubWorkflowContainer] 节点 ${node.node_name || nodeId} 数据转换完成:`, nodeData);
        
        return {
          id: nodeId,
          type: 'customInstance', // 使用统一的节点类型
          position: positions[index],
          data: nodeData,
          draggable: false,
          selectable: true
        };
      });
    }, [taskFlowData, subWorkflow.nodes, expansionLevel, onNodeClick, getNodeSubdivisionInfo, getNodeExpansionState, expandNode, collapseNode])
  );

  // 转换边数据为ReactFlow格式 - 使用task-flow数据
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    useMemo(() => {
      let processedEdges = [];
      
      // 优先使用task-flow的边数据
      const sourceEdges = taskFlowData?.edges || subWorkflow.edges || [];
      const sourceNodes = taskFlowData?.nodes || subWorkflow.nodes || [];
      
      // 首先处理后端返回的边数据
      if (sourceEdges && sourceEdges.length > 0) {
        processedEdges = sourceEdges.map((edge: any) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.label,
          type: 'smoothstep',
          style: { 
            stroke: '#52c41a', 
            strokeWidth: 2,
            strokeDasharray: '5,5' // 虚线表示子工作流内部连接
          },
          labelStyle: { fontSize: '10px', fill: '#666' },
          labelBgStyle: { fill: '#f0f0f0', fillOpacity: 0.8 }
        }));
      } else if (sourceNodes && sourceNodes.length > 1) {
        // 如果没有边数据，为简单的工作流创建默认连接
        console.log('🔗 [SubWorkflowContainer] 没有边数据，创建默认连接');
        
        // 按节点类型排序：start -> process -> end
        const sortedNodes = [...sourceNodes].sort((a: any, b: any) => {
          const getTypeOrder = (type: string) => {
            if (type === 'start') return 0;
            if (type === 'end') return 2;
            return 1; // process, human, ai等
          };
          return getTypeOrder(a.node_type) - getTypeOrder(b.node_type);
        });
        
        // 创建顺序连接
        for (let i = 0; i < sortedNodes.length - 1; i++) {
          const source = sortedNodes[i].node_instance_id;
          const target = sortedNodes[i + 1].node_instance_id;
          
          processedEdges.push({
            id: `default-edge-${source}-${target}`,
            source: source,
            target: target,
            type: 'smoothstep',
            style: { 
              stroke: '#52c41a', 
              strokeWidth: 2,
              strokeDasharray: '5,5'
            },
            label: '自动连接',
            labelStyle: { fontSize: '10px', fill: '#666' },
            labelBgStyle: { fill: '#f0f0f0', fillOpacity: 0.8 }
          });
          
          console.log(`🔗 创建默认连接: ${sortedNodes[i].node_name} -> ${sortedNodes[i + 1].node_name}`);
        }
      }
      
      console.log(`🔗 [SubWorkflowContainer] 最终边数量: ${processedEdges.length}`, processedEdges);
      return processedEdges;
    }, [taskFlowData?.edges, taskFlowData?.nodes, subWorkflow.edges, subWorkflow.nodes])
  );

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
  
  // 计算进度 - 优先使用task-flow数据的统计信息
  const statistics = taskFlowData?.statistics;
  const totalNodes = statistics?.total_nodes || subWorkflow.total_nodes || 0;
  const completedNodes = statistics?.node_status_count?.completed || subWorkflow.completed_nodes || 0;
  const runningNodes = statistics?.node_status_count?.running || subWorkflow.running_nodes || 0;
  const failedNodes = statistics?.node_status_count?.failed || subWorkflow.failed_nodes || 0;
  
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
      bodyStyle={{ padding: '16px' }}
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <BranchesOutlined style={{ color: '#52c41a' }} />
            <Title level={5} style={{ margin: 0, color: '#52c41a' }}>
              {subWorkflow.subdivision_name}
            </Title>
            <Tag color={statusInfo.color} icon={statusInfo.icon} className={subWorkflow.status === 'running' ? 'status-running' : ''}>
              {statusInfo.text}
            </Tag>
          </Space>
          
          <Space>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              层级 {expansionLevel + 1}
            </Text>
            <Tooltip title="收起子工作流">
              <Button
                type="text"
                size="small"
                icon={<ShrinkOutlined />}
                onClick={() => onCollapse(parentNodeId)}
                style={{ color: '#52c41a' }}
              />
            </Tooltip>
          </Space>
        </div>
      }
      extra={
        <Space direction="vertical" size="small" style={{ textAlign: 'right' }}>
          <Text style={{ fontSize: '12px' }}>
            进度: {completedNodes}/{totalNodes}
          </Text>
          <Progress 
            percent={progressPercentage} 
            size="small" 
            strokeColor={statusInfo.color}
            format={() => `${progressPercentage}%`}
          />
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
            <MiniMap 
              nodeColor={() => '#52c41a'}
              nodeStrokeWidth={2}
              style={{
                backgroundColor: '#fafafa',
                border: '1px solid #e8e8e8'
              }}
            />
          </ReactFlow>
        </ReactFlowProvider>
      </div>

      {/* 渲染递归展开的子工作流 */}
      {Object.keys(subdivisionInfo).map(nodeId => {
        const expansionState = getNodeExpansionState(nodeId);
        
        // 检查节点是否已展开且有子工作流数据
        if (expansionState.isExpanded && expansionState.subWorkflowData) {
          console.log(`🔍 [SubWorkflowContainer] 渲染层级${expansionLevel + 1}的展开子工作流:`, nodeId, expansionState.subWorkflowData.length);
          
          return expansionState.subWorkflowData.map((subDetail: any, index: number) => (
            <SubWorkflowContainer
              key={`${nodeId}-sub-${index}`}
              subWorkflow={subDetail}
              parentNodeId={nodeId}
              expansionLevel={expansionLevel + 1}
              onCollapse={collapseNode}
              onNodeClick={onNodeClick}
              workflowInstanceId={subDetail.sub_workflow_instance_id}
              style={{
                marginTop: '16px',
                marginLeft: `${(expansionLevel + 1) * 20}px`, // 缩进显示层级
                borderColor: `hsl(${120 + (expansionLevel + 1) * 60}, 70%, 50%)` // 不同层级使用不同颜色
              }}
            />
          ));
        }
        return null;
      })}

      {/* 层级指示器 */}
      <div className="expansion-level-indicator">
        {expansionLevel + 1}
      </div>

      {/* 展开提示信息 */}
      <div style={{ 
        position: 'absolute', 
        top: '8px', 
        left: '8px',
        backgroundColor: `rgba(82, 196, 26, ${0.1 + expansionLevel * 0.05})`,
        padding: '4px 8px',
        borderRadius: '4px',
        border: '1px solid #52c41a'
      }}>
        <Text style={{ fontSize: '10px', color: '#52c41a', fontWeight: 'bold' }}>
          子工作流展开视图 (层级 {expansionLevel + 1})
        </Text>
      </div>
    </Card>
  );
};

export default SubWorkflowContainer;