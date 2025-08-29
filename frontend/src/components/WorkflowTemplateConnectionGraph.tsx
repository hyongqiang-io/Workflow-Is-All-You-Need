import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  NodeTypes,
  ConnectionMode,
  Handle,
  Position
} from 'reactflow';
import 'reactflow/dist/style.css';
import './WorkflowTemplateConnectionGraph.css';
import { 
  workflowTemplateConnectionManager
} from '../services/workflowTemplateConnectionManager';

interface Props {
  workflowInstanceId: string;
  visible: boolean;
  onClose: () => void;
  onNodeClick?: (node: any) => void;
  onEdgeClick?: (edge: any) => void;
}

// 工作流节点组件 - 显示工作流实例，而不是subdivision
const WorkflowNodeComponent: React.FC<{ data: any }> = ({ data }) => {
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'completed': return '#52c41a';
      case 'running': return '#1890ff';
      case 'failed': return '#ff4d4f';
      case 'draft': return '#faad14';
      case 'cancelled': return '#8c8c8c';
      case 'parent': return '#722ed1'; // 主工作流特殊颜色
      default: return '#d9d9d9';
    }
  };

  const getStatusBackground = (status?: string) => {
    switch (status) {
      case 'completed': return '#f6ffed';
      case 'running': return '#e6f7ff';
      case 'failed': return '#fff2f0';
      case 'draft': return '#fff7e6';
      case 'cancelled': return '#f5f5f5';
      case 'parent': return '#f9f0ff'; // 主工作流特殊背景
      default: return '#fafafa';
    }
  };

  const statusColor = getStatusColor(data.status);
  const isMainWorkflow = data.isMainWorkflow;
  const depth = data.depth || 0;
  
  return (
    <div 
      style={{
        border: `3px solid ${statusColor}`,
        borderRadius: '16px',
        padding: '20px',
        backgroundColor: getStatusBackground(data.status),
        minWidth: isMainWorkflow ? '250px' : '220px',
        maxWidth: isMainWorkflow ? '300px' : '280px',
        textAlign: 'center',
        boxShadow: isMainWorkflow 
          ? '0 12px 32px rgba(114,46,209,0.3)' 
          : `0 6px 16px rgba(0,0,0,0.15)`,
        position: 'relative',
        transition: 'all 0.3s ease',
        cursor: 'pointer',
        transform: isMainWorkflow ? 'scale(1.05)' : 'scale(1)'
      }}
      onClick={() => data.onNodeClick?.(data)}
    >
      {/* 连接点 - 根据节点类型显示 */}
      {!isMainWorkflow && (
        <Handle
          type="target"
          position={Position.Top}
          id="top"
          style={{
            background: statusColor,
            border: '3px solid white',
            width: '14px',
            height: '14px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.2)'
          }}
        />
      )}
      
      {depth < 2 && ( // 只有前两层才显示输出连接点
        <Handle
          type="source"
          position={Position.Bottom}
          id="bottom"
          style={{
            background: statusColor,
            border: '3px solid white', 
            width: '14px',
            height: '14px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.2)'
          }}
        />
      )}
      
      {/* 工作流图标 */}
      <div style={{ 
        fontSize: isMainWorkflow ? '32px' : '28px', 
        marginBottom: '12px',
        color: statusColor
      }}>
        {isMainWorkflow ? '🏠' : '📦'}
      </div>
      
      {/* 工作流名称 */}
      <div style={{ 
        fontWeight: 'bold', 
        fontSize: isMainWorkflow ? '16px' : '14px',
        marginBottom: '8px',
        color: '#333',
        lineHeight: '1.4'
      }}>
        {data.label || '未知工作流'}
      </div>
      
      {/* 状态标签 */}
      <div style={{ 
        background: statusColor,
        color: 'white',
        padding: '4px 12px',
        borderRadius: '16px',
        fontSize: '12px',
        marginBottom: '10px',
        display: 'inline-block',
        fontWeight: 'bold'
      }}>
        {isMainWorkflow ? '主工作流' :
         data.status === 'running' ? '运行中' :
         data.status === 'completed' ? '已完成' :
         data.status === 'failed' ? '失败' :
         data.status === 'draft' ? '草稿' : '子工作流'}
      </div>
      
      {/* 工作流实例ID (简化显示) */}
      <div style={{ 
        fontSize: '10px', 
        color: '#999',
        marginBottom: '8px',
        fontFamily: 'monospace',
        background: '#f0f0f0',
        padding: '2px 6px',
        borderRadius: '4px'
      }}>
        {data.workflow_instance_id?.slice(0, 8)}...
      </div>
      
      {/* Subdivision信息 (对于子工作流) */}
      {!isMainWorkflow && data.subdivision_id && (
        <div style={{ 
          fontSize: '11px', 
          color: '#666',
          marginBottom: '6px',
          background: '#f8f8f8',
          padding: '3px 8px',
          borderRadius: '6px',
          border: `1px solid ${statusColor}30`
        }}>
          📋 来源任务: {data.task_title || data.node_name || 'Unknown'}
        </div>
      )}
      
      {/* 层级指示器 */}
      <div style={{ 
        position: 'absolute',
        top: '8px',
        right: '8px',
        background: statusColor,
        color: 'white',
        borderRadius: '12px',
        width: '24px',
        height: '24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '11px',
        fontWeight: 'bold',
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
      }}>
        {isMainWorkflow ? '🏠' : `L${depth}`}
      </div>
    </div>
  );
};

export const WorkflowTemplateConnectionGraph: React.FC<Props> = ({
  workflowInstanceId,
  visible,
  onClose,
  onNodeClick,
  onEdgeClick
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statistics, setStatistics] = useState<string>('');

  const nodeTypes: NodeTypes = useMemo(() => ({
    workflowTemplate: WorkflowNodeComponent,
    workflowNode: WorkflowNodeComponent,
    default: WorkflowNodeComponent
  }), []);

  // 加载subdivision树数据 - 简化版本，只显示工作流节点
  const loadSubdivisionTree = useCallback(async () => {
    if (!workflowInstanceId) return;

    try {
      setLoading(true);
      setError(null);
      console.log('🌳 [WorkflowTree] 加载subdivision工作流树:', workflowInstanceId);

      const response = await workflowTemplateConnectionManager.getWorkflowConnections(workflowInstanceId);
      
      console.log('🔍 [WorkflowTree] 收到API响应:', response);
      
      if (response.detailed_connection_graph && response.detailed_connection_graph.nodes) {
        console.log('✅ [WorkflowTree] 处理subdivision工作流树数据');
        console.log('🔍 [DEBUG] nodes数据:', response.detailed_connection_graph.nodes);
        console.log('🔍 [DEBUG] 第一个node示例:', response.detailed_connection_graph.nodes[0]);
        
        // 直接使用SubdivisionTree返回的数据
        const workflowNodes: Node[] = response.detailed_connection_graph.nodes.map((nodeData: any) => ({
          id: nodeData.id,
          type: nodeData.type || 'workflowTemplate',
          position: nodeData.position,
          data: {
            ...nodeData.data,
            onNodeClick: (clickData: any) => {
              console.log('🖱️ [WorkflowTree] 点击工作流节点:', clickData);
              onNodeClick?.(clickData);
            }
          }
        }));

        const workflowEdges: Edge[] = response.detailed_connection_graph.edges?.map((edgeData: any) => {
          const edgeType = edgeData.data?.relationship || 'subdivision';
          const subdivisionName = edgeData.data?.subdivision_name || edgeData.data?.task_title || edgeData.label || '细分关系';
          
          return {
            id: edgeData.id,
            source: edgeData.source,
            target: edgeData.target,
            type: 'smoothstep',
            style: { 
              stroke: edgeType === 'nested' ? '#ff6b35' : '#52c41a', 
              strokeWidth: 3,
              strokeDasharray: edgeType === 'nested' ? '8,4' : '5,5'
            },
            label: `📋 ${subdivisionName}`,
            labelStyle: { 
              fontSize: '12px', 
              fontWeight: 'bold',
              color: edgeType === 'nested' ? '#ff6b35' : '#52c41a',
              background: 'rgba(255,255,255,0.9)',
              padding: '2px 6px',
              borderRadius: '4px',
              border: `1px solid ${edgeType === 'nested' ? '#ff6b35' : '#52c41a'}`
            },
            animated: true,
            sourceHandle: 'bottom',
            targetHandle: 'top',
            data: edgeData.data // 保留subdivision信息
          };
        }) || [];
        
        setNodes(workflowNodes);
        setEdges(workflowEdges);
        
        console.log('✅ [WorkflowTree] 工作流树加载完成:', {
          workflowNodes: workflowNodes.length,
          subdivisionEdges: workflowEdges.length,
          mainWorkflows: workflowNodes.filter(n => n.data.isMainWorkflow).length,
          subWorkflows: workflowNodes.filter(n => !n.data.isMainWorkflow).length
        });
        
        setStatistics(workflowTemplateConnectionManager.formatStatistics(response.statistics));
      } else {
        console.warn('⚠️ [WorkflowTree] 后端返回数据格式错误');
        setError('无subdivision数据或数据格式错误');
      }

    } catch (err: any) {
      console.error('❌ [WorkflowTree] subdivision工作流树加载失败:', err);
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [workflowInstanceId, onNodeClick]);

  // 当组件显示时加载数据
  useEffect(() => {
    if (visible && workflowInstanceId) {
      loadSubdivisionTree();
    }
  }, [workflowInstanceId, visible, loadSubdivisionTree]);

  if (!visible) return null;

  return (
    <div className="workflow-template-connection-graph" data-layout="tree">
      <div className="tree-graph-header">
        <div className="header-left">
          <h3 className="tree-title">
            🌳 工作流细分树
          </h3>
          <span className="workflow-id">
            {workflowInstanceId.slice(0, 8)}...
          </span>
        </div>
        <div className="header-right">
          <button 
            onClick={loadSubdivisionTree} 
            className="refresh-button"
            disabled={loading}
          >
            {loading ? '🔄' : '↻'} 刷新
          </button>
          <button onClick={onClose} className="close-button">✕</button>
        </div>
      </div>
      
      {error && (
        <div className="error-message">
          ❌ {error}
          <button onClick={loadSubdivisionTree}>重试</button>
        </div>
      )}
      
      {loading ? (
        <div className="loading">🔄 加载subdivision树中...</div>
      ) : (
        <>
          <div className="statistics">
            📊 {statistics}
          </div>
          
          <div 
            className="tree-graph-container"
            style={{ 
              width: '100%', 
              height: '600px'
            }}
          >
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick ? (_, node) => onNodeClick(node) : undefined}
              onEdgeClick={onEdgeClick ? (_, edge) => onEdgeClick(edge) : undefined}
              nodeTypes={nodeTypes}
              connectionMode={ConnectionMode.Strict}
              fitView
              fitViewOptions={{ 
                padding: 80,
                includeHiddenNodes: false,
                maxZoom: 1.2,
                minZoom: 0.3
              }}
              defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
              nodesDraggable={true}
              nodesConnectable={false}
              elementsSelectable={true}
              panOnScroll={true}
              zoomOnScroll={true}
              preventScrolling={false}
            >
              <Controls 
                showZoom={true}
                showFitView={true}
                showInteractive={false}
                position="top-right"
              />
              <Background 
                color="#e2e8f0"
                gap={20}
                size={1}
                style={{ backgroundColor: '#f8fafc' }}
              />
            </ReactFlow>
          </div>
        </>
      )}
    </div>
  );
};

export default WorkflowTemplateConnectionGraph;