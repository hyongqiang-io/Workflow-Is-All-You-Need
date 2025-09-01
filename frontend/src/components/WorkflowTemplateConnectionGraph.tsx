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

// 工作流节点组件 - 显示工作流实例，而不是subdivision，支持选择
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
  const isSelected = data.isSelected || false;
  const isInMergeMode = data.isInMergeMode || false;
  const canMerge = data.canMerge !== false; // 默认可合并，除非明确设置为false
  
  return (
    <div 
      style={{
        border: `3px solid ${isSelected ? '#ff6b35' : statusColor}`,
        borderRadius: '16px',
        padding: '20px',
        backgroundColor: isSelected 
          ? '#fff7e6' 
          : getStatusBackground(data.status),
        minWidth: isMainWorkflow ? '250px' : '220px',
        maxWidth: isMainWorkflow ? '300px' : '280px',
        textAlign: 'center',
        boxShadow: isMainWorkflow 
          ? '0 12px 32px rgba(114,46,209,0.3)' 
          : isSelected 
          ? '0 8px 24px rgba(255,107,53,0.4)'
          : `0 6px 16px rgba(0,0,0,0.15)`,
        position: 'relative',
        transition: 'all 0.3s ease',
        cursor: isInMergeMode ? 'pointer' : 'default',
        transform: isMainWorkflow ? 'scale(1.05)' : isSelected ? 'scale(1.02)' : 'scale(1)',
        opacity: isInMergeMode && !canMerge ? 0.5 : 1
      }}
      onClick={() => {
        const nodeId = data.id || data.workflow_instance_id; // 备用ID获取方式
        console.log('🖱️ [NodeClick] 节点点击:', { 
          nodeId, 
          dataId: data.id,
          workflowInstanceId: data.workflow_instance_id,
          isInMergeMode, 
          canMerge, 
          isMainWorkflow, 
          isSelected 
        });
        
        if (isInMergeMode && !isMainWorkflow) {
          // 合并模式下：非主工作流都可以选择
          data.onNodeSelection?.(nodeId, !isSelected);
        } else {
          // 普通点击逻辑
          data.onNodeClick?.(data);
        }
      }}
    >
      {/* 选择指示器 - 简化条件，更容易调试 */}
      {isInMergeMode && !isMainWorkflow && (
        <div style={{
          position: 'absolute',
          top: '8px',
          left: '8px',
          width: '24px',
          height: '24px',
          borderRadius: '50%',
          backgroundColor: isSelected ? '#ff6b35' : '#e8e8e8',
          border: '2px solid white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '14px',
          color: 'white',
          fontWeight: 'bold',
          zIndex: 10,
          cursor: 'pointer'
        }}>
          {isSelected ? '✓' : '○'}
        </div>
      )}
      
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
      
      {/* 合并状态指示器 */}
      {isInMergeMode && (
        <div style={{
          position: 'absolute',
          bottom: '8px',
          right: '8px',
          fontSize: '12px',
          color: canMerge ? '#52c41a' : '#ff4d4f',
          fontWeight: 'bold'
        }}>
          {canMerge ? (isMainWorkflow ? '🏠' : '🔗') : '🚫'}
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
  
  // 合并相关状态
  const [mergeMode, setMergeMode] = useState(false);
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [mergeCandidates, setMergeCandidates] = useState<any[]>([]);
  const [merging, setMerging] = useState(false);

  // 获取合并候选项
  const loadMergeCandidates = useCallback(async () => {
    if (!workflowInstanceId || !mergeMode) return;

    try {
      console.log('🔍 [MergeMode] 加载合并候选项...');
      const response = await workflowTemplateConnectionManager.getMergeCandidates(workflowInstanceId);
      
      if (response.success) {
        setMergeCandidates(response.candidates || []);
        console.log('✅ [MergeMode] 合并候选项加载完成:', response.candidates?.length);
      } else {
        console.error('❌ [MergeMode] 加载合并候选项失败:', response.message);
        setError(response.message || '加载合并候选项失败');
      }
    } catch (err: any) {
      console.error('❌ [MergeMode] 合并候选项加载异常:', err);
      setError(err.message || '加载合并候选项异常');
    }
  }, [workflowInstanceId, mergeMode]);


  // 节点选择处理
  const handleNodeSelection = useCallback((nodeId: string, isSelected: boolean) => {
    setSelectedNodes(prev => {
      const newSelected = new Set(prev);
      if (isSelected) {
        newSelected.add(nodeId);
      } else {
        newSelected.delete(nodeId);
      }
      console.log('🔘 [MergeMode] 节点选择更新:', Array.from(newSelected));
      return newSelected;
    });
  }, []);

  // 切换合并模式
  const toggleMergeMode = useCallback(() => {
    setMergeMode(prev => {
      const newMode = !prev;
      console.log('🔄 [MergeMode] 切换合并模式:', newMode);
      
      if (!newMode) {
        // 退出合并模式，清理状态
        setSelectedNodes(new Set());
        setMergeCandidates([]);
      }
      
      return newMode;
    });
  }, []);

  const nodeTypes: NodeTypes = useMemo(() => ({
    workflowTemplate: WorkflowNodeComponent,
    workflowNode: WorkflowNodeComponent,
    default: WorkflowNodeComponent
  }), []);

  // 加载合并候选项效果
  useEffect(() => {
    if (mergeMode) {
      loadMergeCandidates();
    }
  }, [mergeMode, loadMergeCandidates]);

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
        // console.log('✅ [WorkflowTree] 处理subdivision工作流树数据');
        // console.log('🔍 [DEBUG] nodes数据:', response.detailed_connection_graph.nodes);
        // console.log('🔍 [DEBUG] 第一个node示例:', response.detailed_connection_graph.nodes[0]);
        
        // 直接使用SubdivisionTree返回的数据，并添加合并模式支持
        const workflowNodes: Node[] = response.detailed_connection_graph.nodes.map((nodeData: any) => {
          const nodeId = nodeData.id;
          const isSelected = selectedNodes.has(nodeId);
          const isMainWorkflow = nodeData.data?.isMainWorkflow || false;
          
          // 检查是否可合并 (主工作流不能被选择合并)
          // 如果mergeCandidates为空（API失败），默认允许非主工作流合并
          const candidate = mergeCandidates.find(c => c.subdivision_id === nodeData.data?.subdivision_id);
          const canMerge = !isMainWorkflow && (mergeCandidates.length === 0 || candidate?.can_merge !== false);
          
          console.log(`🔍 [DEBUG] 节点 ${nodeId}:`, {
            isMainWorkflow,
            mergeMode,
            canMerge,
            candidatesCount: mergeCandidates.length,
            nodeType: nodeData.type
          });
          
          return {
            id: nodeId,
            type: nodeData.type || 'workflowTemplate',
            position: nodeData.position,
            data: {
              ...nodeData.data,
              isSelected,
              isInMergeMode: mergeMode,
              canMerge,
              onNodeClick: (clickData: any) => {
                console.log('🖱️ [WorkflowTree] 点击工作流节点:', clickData);
                onNodeClick?.(clickData);
              },
              onNodeSelection: handleNodeSelection
            }
          };
        });

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
  }, [workflowInstanceId, onNodeClick, mergeMode, selectedNodes, mergeCandidates]);

  // 执行合并 - 移动到loadSubdivisionTree之后以解决依赖问题
  const executeWorkflowMerge = useCallback(async () => {
    if (!workflowInstanceId || selectedNodes.size === 0) return;

    try {
      setMerging(true);
      console.log('🚀 [MergeMode] 开始执行工作流合并...', Array.from(selectedNodes));
      
      const response = await workflowTemplateConnectionManager.executeWorkflowMerge(
        workflowInstanceId, 
        Array.from(selectedNodes)
      );
      
      if (response.success) {
        console.log('✅ [MergeMode] 工作流合并成功:', response);
        // 重新加载subdivision树以显示合并结果
        await loadSubdivisionTree();
        
        // 重置合并状态
        setMergeMode(false);
        setSelectedNodes(new Set());
        setMergeCandidates([]);
      } else {
        console.error('❌ [MergeMode] 工作流合并失败:', response.message);
        setError(response.message || '工作流合并失败');
      }
    } catch (err: any) {
      console.error('❌ [MergeMode] 工作流合并异常:', err);
      setError(err.message || '工作流合并异常');
    } finally {
      setMerging(false);
    }
  }, [workflowInstanceId, selectedNodes, loadSubdivisionTree]);

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
          {/* 合并模式控制 */}
          <button 
            onClick={toggleMergeMode} 
            className={`merge-mode-button ${mergeMode ? 'active' : ''}`}
            style={{
              marginRight: '8px',
              padding: '6px 12px',
              backgroundColor: mergeMode ? '#ff6b35' : '#f0f0f0',
              color: mergeMode ? 'white' : '#666',
              border: 'none',
              borderRadius: '6px',
              fontSize: '12px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            {mergeMode ? '🔗 退出合并模式' : '🔗 进入合并模式'}
          </button>
          
          {/* 执行合并按钮 */}
          {mergeMode && (
            <button 
              onClick={executeWorkflowMerge}
              disabled={selectedNodes.size === 0 || merging}
              className="execute-merge-button"
              style={{
                marginRight: '8px',
                padding: '6px 12px',
                backgroundColor: selectedNodes.size > 0 ? '#52c41a' : '#d9d9d9',
                color: selectedNodes.size > 0 ? 'white' : '#999',
                border: 'none',
                borderRadius: '6px',
                fontSize: '12px',
                cursor: selectedNodes.size > 0 ? 'pointer' : 'not-allowed',
                fontWeight: 'bold'
              }}
            >
              {merging ? '🔄 合并中...' : `🚀 合并 (${selectedNodes.size})`}
            </button>
          )}
          
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