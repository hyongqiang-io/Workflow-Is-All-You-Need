/**
 * 幽灵建议管理器
 * 统一管理和显示所有的Tab补全建议（节点和连接）
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Node, Edge, useReactFlow } from 'reactflow';
import { message } from 'antd';
import GhostNode from './GhostNode';
import GhostEdge from './GhostEdge';
import {
  NodeSuggestion,
  EdgeSuggestion,
  TriggerCondition,
  workflowTabContext
} from '../services/workflowTabContext';

interface GhostSuggestionManagerProps {
  workflowId?: string;
  onNodeAccepted?: (suggestion: NodeSuggestion) => void;
  onEdgeAccepted?: (suggestion: EdgeSuggestion) => void;
  onSuggestionRejected?: (suggestionId: string, type: 'node' | 'edge') => void;
}

const GhostSuggestionManager: React.FC<GhostSuggestionManagerProps> = ({
  workflowId,
  onNodeAccepted,
  onEdgeAccepted,
  onSuggestionRejected
}) => {
  const { getNodes, getEdges, screenToFlowPosition } = useReactFlow();

  // 建议状态
  const [nodeSuggestions, setNodeSuggestions] = useState<NodeSuggestion[]>([]);
  const [edgeSuggestions, setEdgeSuggestions] = useState<EdgeSuggestion[]>([]);
  const [highlightedSuggestion, setHighlightedSuggestion] = useState<string | null>(null);
  const [currentTrigger, setCurrentTrigger] = useState<TriggerCondition | null>(null);

  // 预测API调用
  const [isLoading, setIsLoading] = useState(false);

  // 监听上下文变化
  useEffect(() => {
    const handleContextChange = async (context: any) => {
      // 当工作流状态发生变化时，清除过时的建议
      setNodeSuggestions([]);
      setEdgeSuggestions([]);
      setHighlightedSuggestion(null);
    };

    workflowTabContext.addListener(handleContextChange);

    return () => {
      workflowTabContext.removeListener(handleContextChange);
    };
  }, []);

  // 触发节点建议
  const triggerNodeSuggestions = useCallback(async (trigger: TriggerCondition) => {
    if (isLoading) return;

    try {
      setIsLoading(true);
      setCurrentTrigger(trigger);

      // 更新上下文
      const nodes = getNodes();
      const edges = getEdges();
      workflowTabContext.updateContext({
        currentNodes: nodes,
        currentEdges: edges,
        cursorPosition: trigger.position || { x: 0, y: 0 }
      });

      // 生成上下文摘要
      const contextSummary = workflowTabContext.generateContextSummary();

      // 调用预测API
      const response = await fetch('/api/tab-completion/predict-nodes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          context_summary: contextSummary,
          max_suggestions: 3,
          trigger_type: trigger.type,
          cursor_position: trigger.position || { x: 0, y: 0 }
        })
      });

      if (!response.ok) {
        throw new Error(`预测失败: ${response.status}`);
      }

      const result = await response.json();
      if (result.success) {
        const suggestions = result.suggestions.map((s: any, index: number) => ({
          ...s,
          position: trigger.position ?
            screenToFlowPosition(trigger.position) :
            workflowTabContext.getSuggestedPosition()
        }));

        setNodeSuggestions(suggestions);

        // 高亮第一个建议
        if (suggestions.length > 0) {
          setHighlightedSuggestion(suggestions[0].id);
        }

        console.log('🔮 [GHOST] 节点建议已生成:', suggestions);
      }
    } catch (error) {
      console.error('🔮 [GHOST] 节点建议失败:', error);
      message.error('获取智能建议失败');
    } finally {
      setIsLoading(false);
    }
  }, [getNodes, getEdges, screenToFlowPosition, isLoading]);

  // 触发连接建议
  const triggerEdgeSuggestions = useCallback(async (trigger: TriggerCondition) => {
    if (isLoading || !trigger.sourceNode) return;

    try {
      setIsLoading(true);
      setCurrentTrigger(trigger);

      // 更新上下文
      const nodes = getNodes();
      const edges = getEdges();
      workflowTabContext.updateContext({
        currentNodes: nodes,
        currentEdges: edges,
        selectedNode: trigger.sourceNode
      });

      // 生成上下文摘要
      const contextSummary = workflowTabContext.generateContextSummary();

      // 调用预测API
      const response = await fetch('/api/tab-completion/predict-connections', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          context_summary: contextSummary,
          source_node_id: trigger.sourceNode.id,
          max_suggestions: 3
        })
      });

      if (!response.ok) {
        throw new Error(`预测失败: ${response.status}`);
      }

      const result = await response.json();
      if (result.success) {
        setEdgeSuggestions(result.suggestions);

        // 高亮第一个建议
        if (result.suggestions.length > 0) {
          setHighlightedSuggestion(result.suggestions[0].id);
        }

        console.log('🔮 [GHOST] 连接建议已生成:', result.suggestions);
      }
    } catch (error) {
      console.error('🔮 [GHOST] 连接建议失败:', error);
      message.error('获取连接建议失败');
    } finally {
      setIsLoading(false);
    }
  }, [getNodes, getEdges, isLoading]);

  // 接受节点建议
  const acceptNodeSuggestion = useCallback((suggestion: NodeSuggestion) => {
    console.log('🔮 [GHOST] 接受节点建议:', suggestion.name);

    // 记录用户交互
    workflowTabContext.addActionHistory({
      timestamp: new Date(),
      action: 'accept_node_suggestion',
      details: {
        suggestionId: suggestion.id,
        suggestionName: suggestion.name,
        confidence: suggestion.confidence,
        trigger: currentTrigger?.type
      }
    });

    // 清除建议
    setNodeSuggestions([]);
    setHighlightedSuggestion(null);
    setCurrentTrigger(null);

    // 回调外部处理
    onNodeAccepted?.(suggestion);

    message.success(`已添加节点: ${suggestion.name}`);
  }, [currentTrigger, onNodeAccepted]);

  // 接受连接建议
  const acceptEdgeSuggestion = useCallback((suggestion: EdgeSuggestion) => {
    console.log('🔮 [GHOST] 接受连接建议:', suggestion.target_node_name);

    // 记录用户交互
    workflowTabContext.addActionHistory({
      timestamp: new Date(),
      action: 'accept_edge_suggestion',
      details: {
        suggestionId: suggestion.id,
        connectionType: suggestion.connection_type,
        confidence: suggestion.confidence,
        trigger: currentTrigger?.type
      }
    });

    // 清除建议
    setEdgeSuggestions([]);
    setHighlightedSuggestion(null);
    setCurrentTrigger(null);

    // 回调外部处理
    onEdgeAccepted?.(suggestion);

    message.success(`已创建连接: ${suggestion.connection_type}`);
  }, [currentTrigger, onEdgeAccepted]);

  // 拒绝建议
  const rejectSuggestion = useCallback((suggestionId: string, type: 'node' | 'edge') => {
    console.log('🔮 [GHOST] 拒绝建议:', suggestionId, type);

    // 记录用户交互
    workflowTabContext.addActionHistory({
      timestamp: new Date(),
      action: 'reject_suggestion',
      details: {
        suggestionId,
        type,
        trigger: currentTrigger?.type
      }
    });

    // 清除建议
    if (type === 'node') {
      setNodeSuggestions([]);
    } else {
      setEdgeSuggestions([]);
    }
    setHighlightedSuggestion(null);
    setCurrentTrigger(null);

    // 回调外部处理
    onSuggestionRejected?.(suggestionId, type);
  }, [currentTrigger, onSuggestionRejected]);

  // 键盘导航
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const allSuggestions = [...nodeSuggestions, ...edgeSuggestions];
      if (allSuggestions.length === 0) return;

      const currentIndex = allSuggestions.findIndex(s => s.id === highlightedSuggestion);

      switch (event.key) {
        case 'Tab':
          event.preventDefault();
          // 接受当前高亮的建议
          if (highlightedSuggestion) {
            const suggestion = allSuggestions.find(s => s.id === highlightedSuggestion);
            if (suggestion) {
              if ('type' in suggestion) {
                acceptNodeSuggestion(suggestion as NodeSuggestion);
              } else {
                acceptEdgeSuggestion(suggestion as EdgeSuggestion);
              }
            }
          }
          break;

        case 'Escape':
          event.preventDefault();
          // 清除所有建议
          setNodeSuggestions([]);
          setEdgeSuggestions([]);
          setHighlightedSuggestion(null);
          setCurrentTrigger(null);
          break;

        case 'ArrowDown':
          event.preventDefault();
          // 切换到下一个建议
          const nextIndex = Math.min(currentIndex + 1, allSuggestions.length - 1);
          setHighlightedSuggestion(allSuggestions[nextIndex]?.id || null);
          break;

        case 'ArrowUp':
          event.preventDefault();
          // 切换到上一个建议
          const prevIndex = Math.max(currentIndex - 1, 0);
          setHighlightedSuggestion(allSuggestions[prevIndex]?.id || null);
          break;

        default:
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [nodeSuggestions, edgeSuggestions, highlightedSuggestion, acceptNodeSuggestion, acceptEdgeSuggestion]);

  // 渲染幽灵节点
  const renderGhostNodes = () => {
    return nodeSuggestions.map((suggestion) => (
      <GhostNode
        key={`ghost-${suggestion.id}`}
        suggestion={suggestion}
        isHighlighted={highlightedSuggestion === suggestion.id}
        onAccept={() => acceptNodeSuggestion(suggestion)}
        onReject={() => rejectSuggestion(suggestion.id, 'node')}
      />
    ));
  };

  // 渲染幽灵连接
  const renderGhostEdges = () => {
    return edgeSuggestions.map((suggestion) => (
      <GhostEdge
        key={`ghost-edge-${suggestion.id}`}
        suggestion={suggestion}
        isHighlighted={highlightedSuggestion === suggestion.id}
        onAccept={() => acceptEdgeSuggestion(suggestion)}
        onReject={() => rejectSuggestion(suggestion.id, 'edge')}
      />
    ));
  };

  // 暴露触发方法给父组件 (暂时注释，未使用)
  /*
  React.useImperativeHandle(React.useRef(), () => ({
    triggerNodeSuggestions,
    triggerEdgeSuggestions,
    clearSuggestions: () => {
      setNodeSuggestions([]);
      setEdgeSuggestions([]);
      setHighlightedSuggestion(null);
      setCurrentTrigger(null);
    }
  }));
  */

  return (
    <>
      {/* 渲染幽灵节点和边将在ReactFlow内部处理 */}
      {/* 这里主要是为了暴露管理接口 */}
    </>
  );
};

// 创建自定义节点类型映射
export const ghostNodeTypes = {
  ghost: GhostNode
};

// 创建自定义边类型映射
export const ghostEdgeTypes = {
  ghost: GhostEdge
};

export default GhostSuggestionManager;