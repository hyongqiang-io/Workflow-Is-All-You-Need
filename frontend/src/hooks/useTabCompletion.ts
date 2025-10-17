/**
 * Tab补全增强的工作流设计器Hook
 * 为WorkflowDesigner添加智能Tab补全功能
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { Node, Edge, useReactFlow } from 'reactflow';
import { message } from 'antd';
import {
  NodeSuggestion,
  EdgeSuggestion,
  TriggerCondition,
  workflowTabContext
} from '../services/workflowTabContext';

interface UseTabCompletionProps {
  workflowId?: string;
  nodes: Node[];
  edges: Edge[];
  setNodes: (nodes: Node[] | ((nodes: Node[]) => Node[])) => void;
  setEdges: (edges: Edge[] | ((edges: Edge[]) => Edge[])) => void;
  onNodeCreate?: (nodeData: any) => Promise<any>;
  onConnectionCreate?: (connectionData: any) => Promise<any>;
}

interface TabCompletionState {
  isActive: boolean;
  currentSuggestions: (NodeSuggestion | EdgeSuggestion)[];
  highlightedIndex: number;
  triggerPosition: { x: number; y: number } | null;
  isLoading: boolean;
}

export const useTabCompletion = ({
  workflowId,
  nodes,
  edges,
  setNodes,
  setEdges,
  onNodeCreate,
  onConnectionCreate
}: UseTabCompletionProps) => {
  const { screenToFlowPosition, getViewport } = useReactFlow();

  // Tab补全状态
  const [tabState, setTabState] = useState<TabCompletionState>({
    isActive: false,
    currentSuggestions: [],
    highlightedIndex: 0,
    triggerPosition: null,
    isLoading: false
  });

  // 候选框引用
  const suggestionBoxRef = useRef<HTMLDivElement>(null);

  // 更新上下文
  useEffect(() => {
    workflowTabContext.updateContext({
      currentNodes: nodes,
      currentEdges: edges,
      workflowId
    });
  }, [nodes, edges, workflowId]);

  // 触发节点建议
  const triggerNodeSuggestions = useCallback(async (position: { x: number; y: number }) => {
    if (tabState.isLoading) return;

    try {
      setTabState(prev => ({ ...prev, isLoading: true, triggerPosition: position }));

      // 检查是否应该触发建议
      const trigger: TriggerCondition = {
        type: 'empty_space_click',
        position
      };

      if (!workflowTabContext.shouldTriggerSuggestion(trigger)) {
        setTabState(prev => ({ ...prev, isLoading: false }));
        return;
      }

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
          trigger_type: 'empty_space_click',
          cursor_position: position
        })
      });

      if (!response.ok) {
        throw new Error(`预测失败: ${response.status}`);
      }

      const result = await response.json();
      if (result.success && result.suggestions.length > 0) {
        // 转换建议格式并计算位置
        const suggestions: NodeSuggestion[] = result.suggestions.map((s: any) => ({
          ...s,
          position: screenToFlowPosition(position)
        }));

        setTabState(prev => ({
          ...prev,
          isActive: true,
          currentSuggestions: suggestions,
          highlightedIndex: 0,
          isLoading: false
        }));

        console.log('🔮 [TAB] 节点建议已激活:', suggestions);
      } else {
        setTabState(prev => ({ ...prev, isLoading: false }));
      }
    } catch (error) {
      console.error('🔮 [TAB] 节点建议失败:', error);
      message.error('获取智能建议失败');
      setTabState(prev => ({ ...prev, isLoading: false }));
    }
  }, [tabState.isLoading, screenToFlowPosition]);

  // 触发连接建议
  const triggerEdgeSuggestions = useCallback(async (sourceNode: Node) => {
    if (tabState.isLoading) return;

    try {
      setTabState(prev => ({ ...prev, isLoading: true }));

      // 生成上下文摘要
      workflowTabContext.updateContext({ selectedNode: sourceNode });
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
          source_node_id: sourceNode.id,
          max_suggestions: 3
        })
      });

      if (!response.ok) {
        throw new Error(`预测失败: ${response.status}`);
      }

      const result = await response.json();
      if (result.success && result.suggestions.length > 0) {
        setTabState(prev => ({
          ...prev,
          isActive: true,
          currentSuggestions: result.suggestions,
          highlightedIndex: 0,
          isLoading: false
        }));

        console.log('🔮 [TAB] 连接建议已激活:', result.suggestions);
      } else {
        setTabState(prev => ({ ...prev, isLoading: false }));
      }
    } catch (error) {
      console.error('🔮 [TAB] 连接建议失败:', error);
      message.error('获取连接建议失败');
      setTabState(prev => ({ ...prev, isLoading: false }));
    }
  }, [tabState.isLoading]);

  // 接受建议
  const acceptSuggestion = useCallback(async (index?: number) => {
    const suggestionIndex = index !== undefined ? index : tabState.highlightedIndex;
    const suggestion = tabState.currentSuggestions[suggestionIndex];

    if (!suggestion) return;

    try {
      if ('type' in suggestion) {
        // 节点建议
        const nodeSuggestion = suggestion as NodeSuggestion;
        console.log('🔮 [TAB] 接受节点建议:', {
          name: nodeSuggestion.name,
          type: nodeSuggestion.type,
          position: nodeSuggestion.position,
          processor_id: nodeSuggestion.processor_id
        });

        // 创建新节点数据
        const nodeData = {
          name: nodeSuggestion.name,
          type: nodeSuggestion.type,
          task_description: nodeSuggestion.description || '',
          position_x: nodeSuggestion.position.x,
          position_y: nodeSuggestion.position.y,
          processor_id: nodeSuggestion.processor_id || ''
        };

        // 如果有外部创建回调，使用它
        let nodeResponse = null;
        if (onNodeCreate && workflowId) {
          nodeResponse = await onNodeCreate({
            ...nodeData,
            workflow_base_id: workflowId
          });
        }

        // 检查是否成功创建了节点
        if (!nodeResponse?.data?.node?.node_base_id) {
          throw new Error('节点创建失败：未返回有效的node_base_id');
        }

        const nodeBaseId = nodeResponse.data.node.node_base_id;

        // 添加到本地状态
        const newNode: Node = {
          id: nodeBaseId,
          type: 'custom',
          position: nodeSuggestion.position,
          data: {
            label: nodeSuggestion.name,
            type: nodeSuggestion.type,
            description: nodeSuggestion.description,
            nodeId: nodeBaseId,
            processor_id: nodeSuggestion.processor_id || '',
            status: 'pending'
          }
        };

        setNodes(prevNodes => [...prevNodes, newNode]);

        console.log('🔮 [TAB] ✅ 节点创建完成:', {
          nodeId: nodeBaseId,
          label: nodeSuggestion.name,
          type: nodeSuggestion.type,
          position: nodeSuggestion.position,
          apiResponse: nodeResponse
        });

        // 记录用户行为
        workflowTabContext.addActionHistory({
          timestamp: new Date(),
          action: 'accept_node_suggestion',
          nodeId: newNode.id,
          details: {
            suggestionId: nodeSuggestion.id,
            confidence: nodeSuggestion.confidence,
            reasoning: nodeSuggestion.reasoning
          }
        });

        message.success(`已添加节点: ${nodeSuggestion.name}`);

      } else {
        // 连接建议
        const edgeSuggestion = suggestion as EdgeSuggestion;
        console.log('🔮 [TAB] 接受连接建议:', {
          targetNodeName: edgeSuggestion.target_node_name,
          sourceNodeId: edgeSuggestion.source_node_id,
          targetNodeId: edgeSuggestion.target_node_id,
          connectionType: edgeSuggestion.connection_type
        });

        // 实现连接创建逻辑
        try {
          // 找到源节点和目标节点
          const sourceNode = nodes.find(n => n.id === edgeSuggestion.source_node_id);
          const targetNode = nodes.find(n =>
            n.data.nodeId === edgeSuggestion.target_node_id ||
            n.id === edgeSuggestion.target_node_id
          );

          if (!sourceNode) {
            throw new Error(`源节点未找到: ${edgeSuggestion.source_node_id}`);
          }

          if (!targetNode) {
            // 如果目标节点不存在，可能需要先创建目标节点
            console.warn('🔮 [TAB] 目标节点不存在，可能需要先创建:', edgeSuggestion.target_node_id);
            message.warning('目标节点不存在，请先创建目标节点');
            return;
          }

          // 获取真实的UUID
          const sourceNodeId = sourceNode.data.nodeId || sourceNode.id;
          const targetNodeId = targetNode.data.nodeId || targetNode.id;

          // 验证UUID格式
          const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
          if (!uuidRegex.test(sourceNodeId)) {
            throw new Error(`源节点ID不是有效的UUID: ${sourceNodeId}`);
          }
          if (!uuidRegex.test(targetNodeId)) {
            throw new Error(`目标节点ID不是有效的UUID: ${targetNodeId}`);
          }

          // 创建连接数据
          const connectionData = {
            from_node_base_id: sourceNodeId,
            to_node_base_id: targetNodeId,
            workflow_base_id: workflowId,
            connection_type: edgeSuggestion.connection_type,
            condition_config: edgeSuggestion.condition_config || null
          };

          console.log('🔮 [TAB] 创建连接数据:', connectionData);

          // 如果有外部创建回调，使用它
          let connectionResponse = null;
          if (onConnectionCreate && workflowId) {
            console.log('🔮 [TAB] 🚀 调用API创建连接...');
            connectionResponse = await onConnectionCreate(connectionData);
            console.log('🔮 [TAB] ✅ 连接API调用成功:', connectionResponse);
          }

          // 创建本地边对象
          const newEdge = {
            id: `${sourceNode.id}-${targetNode.id}`,
            source: sourceNode.id,
            target: targetNode.id,
            type: 'smoothstep',
            sourceHandle: `${sourceNode.id}-source`,
            targetHandle: `${targetNode.id}-target`,
            data: {
              connection_type: edgeSuggestion.connection_type,
              condition_config: edgeSuggestion.condition_config,
              confidence: edgeSuggestion.confidence,
              reasoning: edgeSuggestion.reasoning
            }
          };

          // 添加到本地状态
          setEdges(prevEdges => [...prevEdges, newEdge]);

          console.log('🔮 [TAB] ✅ 连接创建完成:', {
            edgeId: newEdge.id,
            sourceNodeLabel: sourceNode.data.label,
            targetNodeLabel: targetNode.data.label,
            connectionType: edgeSuggestion.connection_type,
            apiResponse: connectionResponse
          });

          // 记录用户行为
          workflowTabContext.addActionHistory({
            timestamp: new Date(),
            action: 'accept_edge_suggestion',
            details: {
              suggestionId: edgeSuggestion.id,
              sourceNodeId: sourceNode.id,
              targetNodeId: targetNode.id,
              connectionType: edgeSuggestion.connection_type,
              confidence: edgeSuggestion.confidence,
              reasoning: edgeSuggestion.reasoning
            }
          });

          message.success(`已创建连接: ${sourceNode.data.label} -> ${targetNode.data.label}`);

        } catch (connectionError) {
          console.error('🔮 [TAB] 连接创建失败:', connectionError);
          const errorMessage = connectionError instanceof Error ? connectionError.message : String(connectionError);
          message.error(`连接创建失败: ${errorMessage}`);
          throw connectionError;
        }
      }

      // 清除Tab状态
      setTabState({
        isActive: false,
        currentSuggestions: [],
        highlightedIndex: 0,
        triggerPosition: null,
        isLoading: false
      });

    } catch (error) {
      console.error('🔮 [TAB] 接受建议失败:', error);
      message.error('应用建议失败');
    }
  }, [tabState, setNodes, setEdges, onNodeCreate, onConnectionCreate, workflowId, nodes]);

  // 拒绝建议
  const rejectSuggestions = useCallback(() => {
    console.log('🔮 [TAB] 拒绝建议');

    // 记录用户行为
    workflowTabContext.addActionHistory({
      timestamp: new Date(),
      action: 'reject_suggestions',
      details: {
        suggestionsCount: tabState.currentSuggestions.length,
        highlightedIndex: tabState.highlightedIndex
      }
    });

    // 清除Tab状态
    setTabState({
      isActive: false,
      currentSuggestions: [],
      highlightedIndex: 0,
      triggerPosition: null,
      isLoading: false
    });
  }, [tabState]);

  // 键盘事件处理
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!tabState.isActive) return;

    switch (event.key) {
      case 'Tab':
        event.preventDefault();
        acceptSuggestion();
        break;

      case 'Escape':
        event.preventDefault();
        rejectSuggestions();
        break;

      case 'ArrowDown':
        event.preventDefault();
        setTabState(prev => ({
          ...prev,
          highlightedIndex: Math.min(prev.highlightedIndex + 1, prev.currentSuggestions.length - 1)
        }));
        break;

      case 'ArrowUp':
        event.preventDefault();
        setTabState(prev => ({
          ...prev,
          highlightedIndex: Math.max(prev.highlightedIndex - 1, 0)
        }));
        break;

      case 'Enter':
        event.preventDefault();
        acceptSuggestion();
        break;

      default:
        break;
    }
  }, [tabState.isActive, acceptSuggestion, rejectSuggestions]);

  // 注册键盘事件
  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // 点击外部区域关闭建议
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (tabState.isActive &&
          suggestionBoxRef.current &&
          !suggestionBoxRef.current.contains(event.target as Element)) {
        rejectSuggestions();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [tabState.isActive, rejectSuggestions]);

  return {
    // 状态
    tabState,
    suggestionBoxRef,

    // 方法
    triggerNodeSuggestions,
    triggerEdgeSuggestions,
    acceptSuggestion,
    rejectSuggestions,

    // 工具方法
    isNodeSuggestion: (suggestion: NodeSuggestion | EdgeSuggestion): suggestion is NodeSuggestion => {
      return 'type' in suggestion;
    }
  };
};