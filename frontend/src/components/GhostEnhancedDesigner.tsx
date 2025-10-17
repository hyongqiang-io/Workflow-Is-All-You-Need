/**
 * 幽灵编辑增强的工作流设计器
 * 集成新的统一图操作建议系统
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { ReactFlowProvider, useReactFlow } from 'reactflow';
import { Switch } from 'antd';
import WorkflowDesigner from './WorkflowDesigner';
import { useGhostEditing } from '../hooks/useGhostEditing';
import { workflowContextManager } from '../services/graphSuggestionSystem';
import { nodeAPI } from '../services/api';

interface GhostEnhancedDesignerProps {
  workflowId?: string;
  workflowName?: string;
  workflowDescription?: string;
  onSave?: (nodes: any[], edges: any[]) => void;
  onExecute?: (workflowId: string) => void;
  readOnly?: boolean;
}

// 内部组件，需要在ReactFlowProvider内部使用
const GhostEnhancedDesignerInner: React.FC<GhostEnhancedDesignerProps> = ({
  workflowId,
  workflowName,
  workflowDescription,
  onSave,
  onExecute,
  readOnly = false
}) => {
  const { screenToFlowPosition, getViewport } = useReactFlow();

  // WorkflowDesigner的ref
  const workflowDesignerRef = useRef<any>(null);

  // 本地状态（与WorkflowDesigner同步）
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [ghostEnabled, setGhostEnabled] = useState(true);

  // 主动获取WorkflowDesigner的状态
  const syncWorkflowState = useCallback(async () => {
    if (workflowDesignerRef.current?.getWorkflowState) {
      try {
        const currentState = workflowDesignerRef.current.getWorkflowState();
        console.log('🔮 [GHOST-ENHANCED] 同步到最新状态:', {
          nodeCount: currentState.nodes.length,
          edgeCount: currentState.edges.length,
          nodes: currentState.nodes.map((n: any) => ({ id: n.id, label: n.data?.label, type: n.data?.type })),
          edges: currentState.edges.map((e: any) => ({ id: e.id, source: e.source, target: e.target }))
        });
        setNodes(currentState.nodes);
        setEdges(currentState.edges);
      } catch (error) {
        console.warn('🔮 [GHOST-ENHANCED] 无法获取WorkflowDesigner状态:', error);
      }
    }
  }, []);

  // 定期同步状态
  useEffect(() => {
    const interval = setInterval(syncWorkflowState, 1000);
    return () => clearInterval(interval);
  }, [syncWorkflowState]);

  // 组件挂载后立即同步一次
  useEffect(() => {
    const timer = setTimeout(syncWorkflowState, 500);
    return () => clearTimeout(timer);
  }, [syncWorkflowState]);

  // 节点创建处理
  const handleNodeCreate = useCallback(async (nodeData: any) => {
    try {
      console.log('🔮 [GHOST-ENHANCED] 🚀 开始创建节点:', {
        name: nodeData.name,
        type: nodeData.type,
        position: { x: nodeData.position_x, y: nodeData.position_y },
        workflowId: workflowId,
        processor_id: nodeData.processor_id
      });

      if (!workflowId) {
        throw new Error('工作流ID不存在');
      }

      // 调用后端API创建节点
      const response = await nodeAPI.createNode({
        ...nodeData,
        workflow_base_id: workflowId
      });

      console.log('🔮 [GHOST-ENHANCED] ✅ 节点创建响应:', {
        status: response?.status,
        statusText: response?.statusText,
        nodeId: response?.data?.node?.node_base_id,
        nodeName: response?.data?.node?.name,
        responseData: response?.data
      });

      // 刷新WorkflowDesigner状态
      if (workflowDesignerRef.current?.refreshWorkflow) {
        await workflowDesignerRef.current.refreshWorkflow();
        console.log('🔮 [GHOST-ENHANCED] ✅ 已刷新WorkflowDesigner状态');
      }

      return response;
    } catch (error) {
      console.error('🔮 [GHOST-ENHANCED] ❌ 节点创建失败:', {
        error: error instanceof Error ? error.message : String(error),
        nodeData: nodeData,
        workflowId: workflowId
      });
      throw error;
    }
  }, [workflowId]);

  // 连接创建处理
  const handleConnectionCreate = useCallback(async (connectionData: any) => {
    try {
      console.log('🔮 [GHOST-ENHANCED] 🚀 开始创建连接:', {
        fromNodeId: connectionData.from_node_base_id,
        toNodeId: connectionData.to_node_base_id,
        connectionType: connectionData.connection_type,
        workflowId: connectionData.workflow_base_id
      });

      // 调用后端API创建连接
      const response = await nodeAPI.createConnection(connectionData);

      console.log('🔮 [GHOST-ENHANCED] ✅ 连接创建响应:', {
        status: response?.status,
        statusText: response?.statusText,
        connectionId: response?.data?.id,
        responseData: response?.data
      });

      // 刷新WorkflowDesigner状态
      if (workflowDesignerRef.current?.refreshWorkflow) {
        await workflowDesignerRef.current.refreshWorkflow();
        console.log('🔮 [GHOST-ENHANCED] ✅ 已刷新WorkflowDesigner状态');
      }

      return response;
    } catch (error) {
      console.error('🔮 [GHOST-ENHANCED] ❌ 连接创建失败:', {
        error: error instanceof Error ? error.message : String(error),
        connectionData: connectionData
      });
      throw error;
    }
  }, []);

  // 幽灵编辑Hook
  const {
    ghostState,
    triggerGhostSuggestion,
    acceptGhostEdit,
    rejectGhostEdit,
    clearGhostState,
    isGhostActive,
    currentSuggestion
  } = useGhostEditing({
    workflowId,
    workflowName,
    workflowDescription,
    nodes,
    edges,
    setNodes,
    setEdges,
    onNodeCreate: handleNodeCreate,
    onConnectionCreate: handleConnectionCreate
  });

  // 处理画布点击事件
  const handleCanvasClick = useCallback((event: React.MouseEvent) => {
    if (readOnly || !workflowId || !ghostEnabled) return;

    // 检查是否点击在空白区域
    const target = event.target as HTMLElement;
    const isCanvasClick = target.classList.contains('react-flow__pane') ||
                         target.classList.contains('react-flow__viewport');

    if (isCanvasClick) {
      // 转换为流坐标
      const flowPosition = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY
      });

      console.log('🔮 [GHOST-ENHANCED] 画布点击触发幽灵建议:', flowPosition);

      // 触发幽灵建议
      triggerGhostSuggestion('canvas_click', flowPosition);
    }
  }, [readOnly, workflowId, ghostEnabled, triggerGhostSuggestion, screenToFlowPosition]);

  // 处理节点选择事件
  const handleNodeSelect = useCallback((nodeId: string) => {
    if (readOnly || !workflowId || !ghostEnabled) return;

    console.log('🔮 [GHOST-ENHANCED] 节点选择触发幽灵建议:', nodeId);

    // 触发基于节点的幽灵建议
    triggerGhostSuggestion('node_select', undefined, nodeId);
  }, [readOnly, workflowId, ghostEnabled, triggerGhostSuggestion]);

  // 同步WorkflowDesigner的节点和边状态
  const handleWorkflowSave = useCallback((newNodes: any[], newEdges: any[]) => {
    console.log('🔮 [GHOST-ENHANCED] 同步节点和边状态');
    setNodes(newNodes);
    setEdges(newEdges);
    onSave?.(newNodes, newEdges);
  }, [onSave]);

  // 渲染幽灵节点和边（叠加在WorkflowDesigner上）
  const renderGhostElements = () => {
    if (!isGhostActive || !ghostState.ghostNodes.length && !ghostState.ghostEdges.length) {
      return null;
    }

    // 复用CustomNode的样式计算函数
    const getNodeColor = (type: string, processorInfo?: any, status?: string) => {
      if (type === 'start') return '#52c41a';
      if (type === 'end') return '#722ed1';

      if (type === 'processor' && processorInfo) {
        switch (processorInfo.type) {
          case 'human':
            return '#faad14';
          case 'agent':
            return '#1890ff';
          default:
            return '#808080';
        }
      }

      if (type === 'processor') {
        return '#808080';
      }

      switch (status) {
        case 'completed':
          return '#52c41a';
        case 'running':
          return '#1890ff';
        case 'failed':
          return '#ff4d4f';
        case 'pending':
          return '#faad14';
        default:
          return '#d9d9d9';
      }
    };

    const getNodeBackground = (type: string, processorInfo?: any, status?: string) => {
      if (type === 'start') return '#f6ffed';
      if (type === 'end') return '#f9f0ff';

      if (type === 'processor' && processorInfo) {
        switch (processorInfo.type) {
          case 'human':
            return '#fffbe6';
          case 'agent':
            return '#e6f7ff';
          default:
            return '#CCCCCC';
        }
      }

      if (type === 'processor') {
        return '#CCCCCC';
      }

      switch (status) {
        case 'completed':
          return '#f6ffed';
        case 'running':
          return '#e6f7ff';
        case 'failed':
          return '#fff2f0';
        case 'pending':
          return '#fffbe6';
        default:
          return '#fafafa';
      }
    };

    const getNodeTypeText = (type: string) => {
      switch (type) {
        case 'start':
          return '开始节点';
        case 'processor':
          return '处理节点';
        case 'end':
          return '结束节点';
        default:
          return type;
      }
    };

    return (
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 1000
        }}
      >
        {/* 幽灵节点渲染 - 使用与CustomNode一致的样式 */}
        {ghostState.ghostNodes.map(node => {
          const nodeType = node.data.type || 'processor';
          const borderColor = getNodeColor(nodeType);
          const backgroundColor = getNodeBackground(nodeType);

          return (
            <div
              key={node.id}
              style={{
                position: 'absolute',
                left: node.position.x,
                top: node.position.y,
                padding: '12px',
                borderRadius: '8px',
                border: `2px dashed ${borderColor}`,
                backgroundColor: backgroundColor,
                minWidth: '160px',
                textAlign: 'center',
                opacity: 0.6, // 幽灵效果
                boxShadow: '0 4px 12px rgba(24, 144, 255, 0.2)',
                animation: 'ghost-pulse 2s infinite',
                fontSize: '14px',
                fontWeight: 'bold',
                color: borderColor,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              {/* 节点标题 */}
              <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '14px' }}>
                {node.data.label}
              </div>
              {/* 节点类型 */}
              <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                {getNodeTypeText(nodeType)}
              </div>
              {/* 描述 */}
              {node.data.description && (
                <div style={{ fontSize: '11px', color: '#999', marginTop: '4px' }}>
                  {node.data.description}
                </div>
              )}
              {/* AI标识 */}
              <div
                style={{
                  position: 'absolute',
                  top: '-8px',
                  right: '-8px',
                  backgroundColor: '#1890ff',
                  color: 'white',
                  borderRadius: '50%',
                  width: '18px',
                  height: '18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '9px',
                  fontWeight: 'bold'
                }}
              >
                AI
              </div>
            </div>
          );
        })}

        {/* 建议提示框 */}
        {currentSuggestion && (
          <div
            style={{
              position: 'fixed',
              bottom: 20,
              left: '50%',
              transform: 'translateX(-50%)',
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              color: 'white',
              padding: '12px 16px',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: 'bold',
              zIndex: 2000,
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
              animation: 'slideInUp 0.3s ease'
            }}
          >
            🔮 {currentSuggestion.name} - 按Tab接受，按Esc拒绝
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      {/* 控制面板 */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          zIndex: 1500,
          backgroundColor: 'white',
          padding: '8px 12px',
          borderRadius: '6px',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '12px'
        }}
      >
        {/* <span>🔮 幽灵编辑</span>
        <Switch
          size="small"
          checked={ghostEnabled}
          onChange={setGhostEnabled}
        />
        {isGhostActive && (
          <span style={{ color: '#1890ff', fontWeight: 'bold' }}>
            ● 激活中
          </span>
        )} */}
      </div>

      {/* 原始WorkflowDesigner */}
      <div
        onClick={handleCanvasClick}
        style={{ height: '100%', width: '100%' }}
      >
        <WorkflowDesigner
          ref={workflowDesignerRef}
          workflowId={workflowId}
          onSave={handleWorkflowSave}
          onExecute={onExecute}
          readOnly={readOnly}
        />
      </div>

      {/* 幽灵元素叠加层 */}
      {renderGhostElements()}

      {/* 添加CSS动画 */}
      <style>
        {`
          @keyframes ghost-pulse {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 0.7; }
          }

          @keyframes slideInUp {
            from {
              opacity: 0;
              transform: translateX(-50%) translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateX(-50%) translateY(0);
            }
          }

          /* 增强幽灵节点样式 */
          .ghost-node {
            background: linear-gradient(135deg, rgba(24, 144, 255, 0.1), rgba(24, 144, 255, 0.2));
            backdrop-filter: blur(4px);
            box-shadow: 0 4px 12px rgba(24, 144, 255, 0.2);
          }
        `}
      </style>
    </div>
  );
};

// 主组件：包装ReactFlowProvider
const GhostEnhancedDesigner: React.FC<GhostEnhancedDesignerProps> = (props) => {
  return (
    <ReactFlowProvider>
      <GhostEnhancedDesignerInner {...props} />
    </ReactFlowProvider>
  );
};

export default GhostEnhancedDesigner;