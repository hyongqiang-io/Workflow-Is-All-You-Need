/**
 * Tab补全增强的WorkflowDesigner包装器
 * 为现有的WorkflowDesigner添加智能Tab补全功能
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { ReactFlowProvider, useReactFlow } from 'reactflow';
import { message } from 'antd';
import WorkflowDesigner from './WorkflowDesigner';
import TabSuggestionBox from './TabSuggestionBox';
import { useTabCompletion } from '../hooks/useTabCompletion';
import {
  NodeSuggestion,
  EdgeSuggestion,
  workflowTabContext
} from '../services/workflowTabContext';
import { nodeAPI } from '../services/api';

interface TabCompletionEnhancedDesignerProps {
  workflowId?: string;
  onSave?: (nodes: any[], edges: any[]) => void;
  onExecute?: (workflowId: string) => void;
  readOnly?: boolean;
}

// 内部组件，需要在ReactFlowProvider内部使用
const EnhancedDesignerInner: React.FC<TabCompletionEnhancedDesignerProps> = ({
  workflowId,
  onSave,
  onExecute,
  readOnly = false
}) => {
  const { screenToFlowPosition, getViewport } = useReactFlow();

  // 使用ref来引用WorkflowDesigner的状态操作函数
  const workflowDesignerRef = useRef<any>(null);

  // 本地状态用于Tab补全系统
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);

  // 节点创建处理函数声明
  const handleNodeCreate = useCallback(async (nodeData: any) => {
    try {
      console.log('🔮 [ENHANCED] 创建节点:', nodeData);

      if (!workflowId) {
        throw new Error('工作流ID不存在');
      }

      // 调用后端API创建节点
      const response = await nodeAPI.createNode({
        ...nodeData,
        workflow_base_id: workflowId
      });

      console.log('🔮 [ENHANCED] 节点创建响应:', response);

      // 关键修复：直接调用WorkflowDesigner的刷新方法
      if (workflowDesignerRef.current?.refreshWorkflow) {
        await workflowDesignerRef.current.refreshWorkflow();
        console.log('🔮 [ENHANCED] 已刷新WorkflowDesigner状态');
      }

      return response;
    } catch (error) {
      console.error('🔮 [ENHANCED] 节点创建失败:', error);
      throw error;
    }
  }, [workflowId]);

  // 连接创建处理函数声明
  const handleConnectionCreate = useCallback(async (connectionData: any) => {
    try {
      console.log('🔮 [ENHANCED] 创建连接:', connectionData);

      // 调用后端API创建连接
      const response = await nodeAPI.createConnection(connectionData);

      console.log('🔮 [ENHANCED] 连接创建响应:', response);

      // 关键修复：直接调用WorkflowDesigner的刷新方法
      if (workflowDesignerRef.current?.refreshWorkflow) {
        await workflowDesignerRef.current.refreshWorkflow();
        console.log('🔮 [ENHANCED] 已刷新WorkflowDesigner状态');
      }

      return response;
    } catch (error) {
      console.error('🔮 [ENHANCED] 连接创建失败:', error);
      throw error;
    }
  }, []);

  // Tab补全hook - 现在在回调函数声明之后
  const {
    tabState,
    suggestionBoxRef,
    triggerNodeSuggestions,
    triggerEdgeSuggestions,
    acceptSuggestion,
    rejectSuggestions,
    isNodeSuggestion
  } = useTabCompletion({
    workflowId,
    nodes,
    edges,
    setNodes,
    setEdges,
    onNodeCreate: handleNodeCreate,
    onConnectionCreate: handleConnectionCreate
  });

  // 会话管理
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
  const [triggerCount, setTriggerCount] = useState(0);

  // 处理画布点击事件
  const handleCanvasClick = useCallback((event: React.MouseEvent) => {
    if (readOnly || !workflowId) return;

    // 检查是否点击在空白区域
    const target = event.target as HTMLElement;
    const isCanvasClick = target.classList.contains('react-flow__pane') ||
                         target.classList.contains('react-flow__viewport');

    if (isCanvasClick) {
      const position = { x: event.clientX, y: event.clientY };
      console.log('🔮 [ENHANCED] 画布点击触发建议:', position);

      // 记录触发事件
      setTriggerCount(prev => prev + 1);

      // 触发节点建议
      triggerNodeSuggestions(position);

      // 记录用户行为
      trackInteraction('trigger_activated', {
        trigger_type: 'canvas_click',
        position,
        trigger_count: triggerCount + 1
      });
    }
  }, [readOnly, workflowId, triggerNodeSuggestions, triggerCount]);

  // 处理节点悬停事件
  const handleNodeHover = useCallback((node: any, event: React.MouseEvent) => {
    if (readOnly || !workflowId) return;

    // 延迟触发，避免过于频繁
    setTimeout(() => {
      if (node.data.type !== 'end') {
        console.log('🔮 [ENHANCED] 节点悬停触发连接建议:', node.data.label);
        triggerEdgeSuggestions(node);
      }
    }, 1000);
  }, [readOnly, workflowId, triggerEdgeSuggestions]);

  // 跟踪用户交互
  const trackInteraction = useCallback(async (eventType: string, data: any) => {
    try {
      if (!workflowId) return;

      const contextSummary = workflowTabContext.generateContextSummary();

      // 发送到后端跟踪API（稍后实现）
      await fetch('/api/tab-completion/track-interaction', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          workflow_id: workflowId,
          session_id: sessionId,
          event_type: eventType,
          event_data: data,
          context_summary: contextSummary
        })
      });
    } catch (error) {
      console.warn('🔮 [ENHANCED] 交互跟踪失败:', error);
    }
  }, [workflowId, sessionId]);

  // 处理建议接受
  const handleSuggestionAccept = useCallback(async (index: number) => {
    const suggestion = tabState.currentSuggestions[index];
    if (!suggestion) return;

    try {
      console.log('🔮 [ENHANCED] 接受建议:', suggestion);

      // 跟踪接受事件
      await trackInteraction('suggestion_accepted', {
        suggestion_id: suggestion.id,
        suggestion_type: isNodeSuggestion(suggestion) ? 'node' : 'edge',
        confidence: suggestion.confidence,
        suggestion_index: index,
        total_suggestions: tabState.currentSuggestions.length
      });

      // 执行接受逻辑
      await acceptSuggestion(index);

      message.success(`建议已应用: ${isNodeSuggestion(suggestion) ? (suggestion as NodeSuggestion).name : '连接'}`);
    } catch (error) {
      console.error('🔮 [ENHANCED] 接受建议失败:', error);
      message.error('应用建议失败');
    }
  }, [tabState.currentSuggestions, acceptSuggestion, trackInteraction, isNodeSuggestion]);

  // 处理建议拒绝
  const handleSuggestionReject = useCallback(async () => {
    try {
      console.log('🔮 [ENHANCED] 拒绝建议');

      // 跟踪拒绝事件
      await trackInteraction('suggestion_rejected', {
        rejected_count: tabState.currentSuggestions.length,
        rejection_method: 'manual'
      });

      rejectSuggestions();
    } catch (error) {
      console.error('🔮 [ENHANCED] 拒绝建议失败:', error);
    }
  }, [tabState.currentSuggestions, rejectSuggestions, trackInteraction]);

  // 更新上下文管理器
  useEffect(() => {
    if (nodes.length > 0 || edges.length > 0) {
      workflowTabContext.updateContext({
        currentNodes: nodes,
        currentEdges: edges,
        workflowId
      });
    }
  }, [nodes, edges, workflowId]);

  // 会话开始/结束跟踪
  useEffect(() => {
    if (workflowId) {
      // 会话开始
      trackInteraction('session_started', {
        initial_node_count: nodes.length,
        initial_edge_count: edges.length
      });

      // 会话结束清理
      return () => {
        trackInteraction('session_ended', {
          final_node_count: nodes.length,
          final_edge_count: edges.length,
          total_triggers: triggerCount
        });
      };
    }
  }, [workflowId]);

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      {/* 原始WorkflowDesigner */}
      <div
        onClick={handleCanvasClick}
        style={{ height: '100%', width: '100%' }}
      >
        <WorkflowDesigner
          ref={workflowDesignerRef}
          workflowId={workflowId}
          onSave={(newNodes, newEdges) => {
            setNodes(newNodes);
            setEdges(newEdges);
            onSave?.(newNodes, newEdges);
          }}
          onExecute={onExecute}
          readOnly={readOnly}
        />
      </div>

      {/* Tab补全建议框 */}
      <TabSuggestionBox
        ref={suggestionBoxRef}
        suggestions={tabState.currentSuggestions}
        highlightedIndex={tabState.highlightedIndex}
        isLoading={tabState.isLoading}
        position={tabState.triggerPosition}
        onAccept={handleSuggestionAccept}
        onReject={handleSuggestionReject}
      />

      {/* 调试信息（开发模式） */}
      {process.env.NODE_ENV === 'development' && tabState.isActive && (
        <div style={{
          position: 'fixed',
          top: '10px',
          right: '10px',
          padding: '8px',
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          color: 'white',
          fontSize: '12px',
          borderRadius: '4px',
          zIndex: 3000
        }}>
          <div>🔮 Tab补全调试</div>
          <div>建议数量: {tabState.currentSuggestions.length}</div>
          <div>高亮索引: {tabState.highlightedIndex}</div>
          <div>会话触发: {triggerCount}</div>
          <div>加载状态: {tabState.isLoading ? '是' : '否'}</div>
        </div>
      )}
    </div>
  );
};

// 主组件，提供ReactFlow上下文
const TabCompletionEnhancedDesigner: React.FC<TabCompletionEnhancedDesignerProps> = (props) => {
  return (
    <ReactFlowProvider>
      <EnhancedDesignerInner {...props} />
    </ReactFlowProvider>
  );
};

export default TabCompletionEnhancedDesigner;