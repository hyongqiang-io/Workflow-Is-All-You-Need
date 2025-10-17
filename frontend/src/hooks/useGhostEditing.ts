/**
 * 幽灵编辑模式的图操作建议系统
 * 直接在画布上渲染半透明的预览效果
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Node, Edge, useReactFlow } from 'reactflow';
import { message } from 'antd';
import {
  GraphSuggestion,
  GraphOperation,
  GraphOperationType,
  WorkflowContext,
  workflowContextManager,
  graphSuggestionAPI
} from '../services/graphSuggestionSystem';

// 幽灵元素的样式定义
const GHOST_STYLE = {
  opacity: 0.5,
  filter: 'brightness(1.2)',
  animation: 'ghost-pulse 2s infinite',
  border: '2px dashed #1890ff'
};

// 幽灵状态管理
interface GhostState {
  isActive: boolean;
  suggestion: GraphSuggestion | null;
  ghostNodes: Node[];
  ghostEdges: Edge[];
  isLoading: boolean;
  isExecuting: boolean;
}

export const useGhostEditing = ({
  workflowId,
  workflowName,
  workflowDescription,
  nodes,
  edges,
  setNodes,
  setEdges,
  onNodeCreate,
  onConnectionCreate
}: {
  workflowId?: string;
  workflowName?: string;
  workflowDescription?: string;
  nodes: Node[];
  edges: Edge[];
  setNodes: (nodes: Node[] | ((nodes: Node[]) => Node[])) => void;
  setEdges: (edges: Edge[] | ((edges: Edge[]) => Edge[])) => void;
  onNodeCreate?: (nodeData: any) => Promise<any>;
  onConnectionCreate?: (connectionData: any) => Promise<any>;
}) => {
  const { screenToFlowPosition, getViewport } = useReactFlow();

  // 幽灵状态
  const [ghostState, setGhostState] = useState<GhostState>({
    isActive: false,
    suggestion: null,
    ghostNodes: [],
    ghostEdges: [],
    isLoading: false,
    isExecuting: false
  });

  // 会话管理
  const [sessionId] = useState(() => `ghost_session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);

  // 更新工作流上下文
  useEffect(() => {
    workflowContextManager.updateWorkflowContext({
      workflow_id: workflowId,
      workflow_name: workflowName,
      workflow_description: workflowDescription
    });
    workflowContextManager.updateGraphState(nodes, edges);
  }, [workflowId, workflowName, workflowDescription, nodes, edges]);

  // 触发幽灵编辑建议
  const triggerGhostSuggestion = useCallback(async (
    triggerType: 'canvas_click' | 'node_select' | 'manual_request',
    position?: { x: number; y: number },
    selectedNodeId?: string
  ) => {
    if (ghostState.isLoading) return;

    try {
      setGhostState(prev => ({ ...prev, isLoading: true }));

      // 检查是否应该触发
      if (!workflowContextManager.shouldTriggerSuggestion(triggerType, position)) {
        setGhostState(prev => ({ ...prev, isLoading: false }));
        return;
      }

      // 更新上下文
      const context: WorkflowContext = {
        ...workflowContextManager.getContextForAPI(),
        cursor_position: position,
        selected_node_id: selectedNodeId
      };

      // 调用API获取图操作建议
      const response = await graphSuggestionAPI.getGraphSuggestions({
        context,
        trigger_type: triggerType,
        max_suggestions: 1 // 幽灵模式只显示最佳建议
      });

      if (response.success && response.suggestions.length > 0) {
        const bestSuggestion = response.suggestions[0];
        console.log('🔮 [GHOST] 收到图操作建议:', bestSuggestion);

        // 验证建议的完整性
        if (!validateSuggestion(bestSuggestion)) {
          console.warn('🔮 [GHOST] ⚠️ 建议验证失败，跳过处理:', bestSuggestion);
          setGhostState(prev => ({ ...prev, isLoading: false }));
          return;
        }

        // 生成幽灵节点和边
        const { ghostNodes, ghostEdges } = generateGhostElements(
          bestSuggestion,
          nodes,
          edges,
          position
        );

        setGhostState({
          isActive: true,
          suggestion: bestSuggestion,
          ghostNodes,
          ghostEdges,
          isLoading: false,
          isExecuting: false
        });

        // 记录触发事件
        workflowContextManager.addAction('ghost_suggestion_shown', {
          suggestion_id: bestSuggestion.id,
          trigger_type: triggerType,
          operations_count: bestSuggestion.operations.length
        });

        console.log('🔮 [GHOST] 幽灵编辑已激活');
      } else {
        console.log('🔮 [GHOST] 没有收到有效建议或API调用失败');
        setGhostState(prev => ({ ...prev, isLoading: false }));
      }
    } catch (error) {
      console.error('🔮 [GHOST] 幽灵建议失败:', error);
      setGhostState(prev => ({ ...prev, isLoading: false }));
    }
  }, [ghostState.isLoading, nodes, edges]);

  // 接受幽灵编辑 (Tab键)
  const acceptGhostEdit = useCallback(async () => {
    if (!ghostState.isActive || !ghostState.suggestion || ghostState.isExecuting) {
      return;
    }

    // 立即开始清理UI，提供即时反馈
    setGhostState(prev => ({
      ...prev,
      isExecuting: true,
      // 立即隐藏幽灵节点，提供即时反馈
      ghostNodes: [],
      ghostEdges: []
    }));

    try {
      console.log('🔮 [GHOST] 接受幽灵编辑:', ghostState.suggestion.name);

      // 再次验证建议（防御性编程）
      if (!validateSuggestion(ghostState.suggestion)) {
        console.error('🔮 [GHOST] ❌ 执行前最终验证失败，拒绝执行');
        throw new Error('建议验证失败，无法执行');
      }

      // 执行操作序列
      const operations = ghostState.suggestion.operations;
      const executionResults: any[] = [];
      const nodeIdMapping = new Map<string, string>(); // 临时ID -> 真实ID的映射

      for (const operation of operations) {
        try {
          console.log('🔮 [GHOST] 🚀 执行操作:', {
            id: operation.id,
            type: operation.type,
            data: operation.data
          });

          const result = await executeGraphOperation(
            operation,
            workflowId,
            nodes, // 传递当前节点列表
            onNodeCreate,
            onConnectionCreate,
            nodeIdMapping // 传递ID映射
          );
          executionResults.push({ operation: operation.id, success: true, result });

          // 如果是节点创建，记录ID映射
          if (operation.type === GraphOperationType.ADD_NODE && result?.data?.node?.node_base_id) {
            const tempId = operation.data.node?.id || `temp_${Date.now()}`;
            const realId = result.data.node.node_base_id;
            nodeIdMapping.set(tempId, realId);
            console.log('🔮 [GHOST] 📝 记录节点ID映射:', { tempId, realId });
          }

          console.log('🔮 [GHOST] ✅ 操作执行成功:', {
            operationId: operation.id,
            result: result,
            details: operation.type === GraphOperationType.ADD_NODE
              ? `节点 "${operation.data.node?.name}" 已创建，ID: ${result?.data?.node?.node_base_id}`
              : `连接已创建: ${operation.data.edge?.source_node_id} -> ${operation.data.edge?.target_node_id}`
          });
        } catch (opError) {
          console.error('🔮 [GHOST] ❌ 操作执行失败:', {
            operationId: operation.id,
            type: operation.type,
            error: opError instanceof Error ? opError.message : String(opError),
            data: operation.data
          });
          executionResults.push({ operation: operation.id, success: false, error: opError });
        }
      }

      // 检查是否所有操作都成功
      const allSuccessful = executionResults.every(r => r.success);

      if (allSuccessful) {
        // 记录成功 - 不需要手动更新本地状态，因为API调用会触发数据刷新
        workflowContextManager.addAction('ghost_edit_accepted', {
          suggestion_id: ghostState.suggestion.id,
          operations_executed: operations.length
        });

        console.log('🔮 [GHOST] ✅ 所有操作执行成功，等待数据刷新');

        // 跟踪执行结果
        await graphSuggestionAPI.trackOperationExecution(
          ghostState.suggestion.id,
          operations,
          true
        );

        message.success(`✨ 已应用编辑: ${ghostState.suggestion.name}`);
      } else {
        message.error('部分操作执行失败');
      }

    } catch (error) {
      console.error('🔮 [GHOST] 接受编辑失败:', error);
      message.error('应用编辑失败');

      // 跟踪失败
      if (ghostState.suggestion) {
        await graphSuggestionAPI.trackOperationExecution(
          ghostState.suggestion.id,
          ghostState.suggestion.operations,
          false
        );
      }
    } finally {
      // 无论成功还是失败都要清除幽灵状态
      console.log('🔮 [GHOST] 清除幽灵状态');
      clearGhostState();
    }
  }, [ghostState, setNodes, setEdges, workflowId, onNodeCreate, onConnectionCreate]);

  // 拒绝幽灵编辑 (Esc键)
  const rejectGhostEdit = useCallback(async () => {
    if (!ghostState.isActive || !ghostState.suggestion) return;

    console.log('🔮 [GHOST] 拒绝幽灵编辑:', ghostState.suggestion.name);

    // 立即清理幽灵状态，提供即时反馈
    clearGhostState();

    // 记录拒绝
    workflowContextManager.addAction('ghost_edit_rejected', {
      suggestion_id: ghostState.suggestion.id,
      reason: 'user_esc_key'
    });
  }, [ghostState]);

  // 清除幽灵状态
  const clearGhostState = useCallback(() => {
    setGhostState({
      isActive: false,
      suggestion: null,
      ghostNodes: [],
      ghostEdges: [],
      isLoading: false,
      isExecuting: false
    });
  }, []);

  // 键盘事件处理
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!ghostState.isActive) return;

    switch (event.key) {
      case 'Tab':
        event.preventDefault();
        acceptGhostEdit();
        break;

      case 'Escape':
        event.preventDefault();
        rejectGhostEdit();
        break;

      default:
        break;
    }
  }, [ghostState.isActive, acceptGhostEdit, rejectGhostEdit]);

  // 注册键盘事件
  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return {
    // 状态
    ghostState,

    // 方法
    triggerGhostSuggestion,
    acceptGhostEdit,
    rejectGhostEdit,
    clearGhostState,

    // 计算属性
    isGhostActive: ghostState.isActive,
    currentSuggestion: ghostState.suggestion
  };
};

// 验证建议的完整性和有效性
function validateSuggestion(suggestion: GraphSuggestion): boolean {
  console.log('🔮 [VALIDATE] 开始验证建议:', suggestion?.name || 'unnamed');

  // 基本字段验证
  if (!suggestion || typeof suggestion !== 'object') {
    console.warn('🔮 [VALIDATE] ❌ 建议对象为空或格式错误');
    return false;
  }

  if (!suggestion.id || !suggestion.name) {
    console.warn('🔮 [VALIDATE] ❌ 建议缺少ID或名称');
    return false;
  }

  if (!suggestion.operations || !Array.isArray(suggestion.operations)) {
    console.warn('🔮 [VALIDATE] ❌ 建议缺少操作列表或格式错误');
    return false;
  }

  if (suggestion.operations.length === 0) {
    console.warn('🔮 [VALIDATE] ❌ 建议操作列表为空');
    return false;
  }

  // 验证每个操作
  for (let i = 0; i < suggestion.operations.length; i++) {
    const operation = suggestion.operations[i];

    if (!operation || typeof operation !== 'object') {
      console.warn(`🔮 [VALIDATE] ❌ 操作${i+1}为空或格式错误`);
      return false;
    }

    if (!operation.id || !operation.type || !operation.data) {
      console.warn(`🔮 [VALIDATE] ❌ 操作${i+1}缺少必需字段: ${JSON.stringify({
        hasId: !!operation.id,
        hasType: !!operation.type,
        hasData: !!operation.data
      })}`);
      return false;
    }

    // 验证操作类型
    const validTypes = [
      GraphOperationType.ADD_NODE,
      GraphOperationType.ADD_EDGE,
      GraphOperationType.REMOVE_NODE,
      GraphOperationType.REMOVE_EDGE,
      GraphOperationType.UPDATE_NODE,
      GraphOperationType.UPDATE_EDGE
    ];

    if (!validTypes.includes(operation.type)) {
      console.warn(`🔮 [VALIDATE] ❌ 操作${i+1}类型无效: ${operation.type}`);
      return false;
    }

    // 根据操作类型进行具体验证
    if (operation.type === GraphOperationType.ADD_NODE) {
      if (!operation.data.node || typeof operation.data.node !== 'object') {
        console.warn(`🔮 [VALIDATE] ❌ 添加节点操作${i+1}缺少node数据`);
        return false;
      }

      const nodeData = operation.data.node;
      if (!nodeData.name || !nodeData.type) {
        console.warn(`🔮 [VALIDATE] ❌ 添加节点操作${i+1}的节点缺少名称或类型:`, {
          name: nodeData.name,
          type: nodeData.type
        });
        return false;
      }

      const validNodeTypes = ['start', 'processor', 'end'];
      if (!validNodeTypes.includes(nodeData.type)) {
        console.warn(`🔮 [VALIDATE] ❌ 添加节点操作${i+1}的节点类型无效: ${nodeData.type}`);
        return false;
      }

    } else if (operation.type === GraphOperationType.ADD_EDGE) {
      if (!operation.data.edge || typeof operation.data.edge !== 'object') {
        console.warn(`🔮 [VALIDATE] ❌ 添加连接操作${i+1}缺少edge数据`);
        return false;
      }

      const edgeData = operation.data.edge;
      if (!edgeData.source_node_id || !edgeData.target_node_id) {
        console.warn(`🔮 [VALIDATE] ❌ 添加连接操作${i+1}缺少源或目标节点ID:`, {
          source: edgeData.source_node_id,
          target: edgeData.target_node_id
        });
        return false;
      }

      // 检查连接类型
      const validConnectionTypes = ['normal', 'conditional', 'parallel'];
      if (edgeData.connection_type && !validConnectionTypes.includes(edgeData.connection_type)) {
        console.warn(`🔮 [VALIDATE] ❌ 添加连接操作${i+1}的连接类型无效: ${edgeData.connection_type}`);
        return false;
      }
    }

    console.log(`🔮 [VALIDATE] ✅ 操作${i+1}验证通过: ${operation.type}`);
  }

  // 验证置信度
  if (typeof suggestion.confidence !== 'number' || suggestion.confidence < 0 || suggestion.confidence > 1) {
    console.warn(`🔮 [VALIDATE] ❌ 建议置信度无效: ${suggestion.confidence}`);
    return false;
  }

  console.log(`🔮 [VALIDATE] ✅ 建议验证通过: ${suggestion.name} (${suggestion.operations.length}个操作)`);
  return true;
}

// 生成幽灵元素
function generateGhostElements(
  suggestion: GraphSuggestion,
  currentNodes: Node[],
  currentEdges: Edge[],
  cursorPosition?: { x: number; y: number }
): { ghostNodes: Node[]; ghostEdges: Edge[] } {
  const ghostNodes: Node[] = [];
  const ghostEdges: Edge[] = [];
  const nodeIdMap = new Map<string, string>(); // 操作中的ID -> 实际生成的ID

  // 基准位置：光标位置或画布中心
  const basePosition = cursorPosition || { x: 300, y: 200 };
  let nodePositionOffset = 0;

  suggestion.operations.forEach((operation, index) => {
    switch (operation.type) {
      case GraphOperationType.ADD_NODE:
        if (operation.data.node) {
          const nodeData = operation.data.node;
          const ghostNodeId = `ghost_node_${Date.now()}_${index}`;

          nodeIdMap.set(nodeData.id || ghostNodeId, ghostNodeId);

          const ghostNode: Node = {
            id: ghostNodeId,
            type: 'custom',
            position: nodeData.position || {
              x: basePosition.x + nodePositionOffset,
              y: basePosition.y
            },
            data: {
              label: nodeData.name || '新节点',
              type: nodeData.type || 'processor',
              description: nodeData.task_description,
              processor_id: nodeData.processor_id,
              status: 'ghost', // 特殊状态标记
              isGhost: true
            },
            style: GHOST_STYLE
          };

          ghostNodes.push(ghostNode);
          nodePositionOffset += 200; // 水平排列新节点
        }
        break;

      case GraphOperationType.ADD_EDGE:
        if (operation.data.edge) {
          const edgeData = operation.data.edge;

          // 智能解析源节点和目标节点ID
          const sourceId = resolveNodeId(edgeData.source_node_id!, currentNodes, nodeIdMap);
          const targetId = resolveNodeId(edgeData.target_node_id!, currentNodes, nodeIdMap);

          console.log('🔮 [GHOST] 解析连接节点ID:', {
            原始源ID: edgeData.source_node_id,
            解析后源ID: sourceId,
            原始目标ID: edgeData.target_node_id,
            解析后目标ID: targetId
          });

          if (sourceId && targetId) {
            const ghostEdge: Edge = {
              id: `ghost_edge_${Date.now()}_${index}`,
              source: sourceId,
              target: targetId,
              type: 'smoothstep',
              data: {
                connection_type: edgeData.connection_type,
                condition_config: edgeData.condition_config,
                isGhost: true
              },
              style: {
                ...GHOST_STYLE,
                strokeDasharray: '5,5' // 虚线效果
              }
            };

            ghostEdges.push(ghostEdge);
          } else {
            console.warn('🔮 [GHOST] ⚠️ 无法解析连接的节点ID:', {
              源节点: edgeData.source_node_id,
              目标节点: edgeData.target_node_id,
              可用节点: currentNodes.map(n => ({ id: n.id, label: n.data?.label }))
            });
          }
        }
        break;

      // 其他操作类型的处理...
      default:
        console.log('🔮 [GHOST] 暂不支持的操作类型:', operation.type);
        break;
    }
  });

  return { ghostNodes, ghostEdges };
}

// 智能解析节点ID：处理多种引用格式
function resolveNodeId(
  nodeReference: string,
  currentNodes: Node[],
  nodeIdMap: Map<string, string>
): string | null {
  // 1. 首先检查是否已经在临时ID映射中
  if (nodeIdMap.has(nodeReference)) {
    return nodeIdMap.get(nodeReference)!;
  }

  // 2. 检查是否已经是有效的UUID
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  if (uuidRegex.test(nodeReference)) {
    // 验证这个UUID确实存在于当前节点中
    const existingNode = currentNodes.find(n => n.id === nodeReference);
    return existingNode ? nodeReference : null;
  }

  // 3. 尝试通过节点名称匹配（AI可能使用了描述性名称）
  const nodeByName = currentNodes.find(n =>
    n.data?.label === nodeReference ||
    n.data?.name === nodeReference
  );
  if (nodeByName) {
    return nodeByName.id;
  }

  // 4. 尝试通过节点类型匹配（如"开始节点"、"结束节点"等）
  const typeMapping: { [key: string]: string } = {
    '开始节点': 'start',
    '结束节点': 'end',
    'start': 'start',
    'end': 'end',
    'Start': 'start',
    'End': 'end'
  };

  const targetType = typeMapping[nodeReference] || nodeReference;
  const nodeByType = currentNodes.find(n =>
    n.data?.type === targetType ||
    n.type === targetType
  );
  if (nodeByType) {
    return nodeByType.id;
  }

  // 5. 尝试通过序号匹配（如"节点1"、"节点2"）
  const numberMatch = nodeReference.match(/节点(\d+)/);
  if (numberMatch) {
    const nodeIndex = parseInt(numberMatch[1]) - 1; // 转为0基索引
    if (nodeIndex >= 0 && nodeIndex < currentNodes.length) {
      return currentNodes[nodeIndex].id;
    }
  }

  console.warn('🔮 [RESOLVE] 无法解析节点引用:', {
    reference: nodeReference,
    availableNodes: currentNodes.map(n => ({
      id: n.id,
      label: n.data?.label,
      type: n.data?.type,
      name: n.data?.name
    }))
  });

  return null;
}

// 执行单个图操作
async function executeGraphOperation(
  operation: GraphOperation,
  workflowId: string | undefined,
  currentNodes: Node[], // 当前节点列表，用于ID解析
  onNodeCreate?: (nodeData: any) => Promise<any>,
  onConnectionCreate?: (connectionData: any) => Promise<any>,
  nodeIdMapping?: Map<string, string> // 临时ID到真实ID的映射
): Promise<any> {
  switch (operation.type) {
    case GraphOperationType.ADD_NODE:
      if (!onNodeCreate || !workflowId || !operation.data.node) {
        throw new Error('无法创建节点：缺少必要参数或回调');
      }

      return await onNodeCreate({
        ...operation.data.node,
        workflow_base_id: workflowId
      });

    case GraphOperationType.ADD_EDGE:
      if (!onConnectionCreate || !workflowId || !operation.data.edge) {
        throw new Error('无法创建连接：缺少必要参数或回调');
      }

      // 使用智能解析获取真实的节点ID
      const sourceNodeId = resolveNodeId(
        operation.data.edge.source_node_id!,
        currentNodes,
        nodeIdMapping || new Map()
      );
      const targetNodeId = resolveNodeId(
        operation.data.edge.target_node_id!,
        currentNodes,
        nodeIdMapping || new Map()
      );

      console.log('🔮 [EXECUTE] 智能解析连接节点ID:', {
        原始源ID: operation.data.edge.source_node_id,
        解析后源ID: sourceNodeId,
        原始目标ID: operation.data.edge.target_node_id,
        解析后目标ID: targetNodeId,
        可用节点: currentNodes.map(n => ({ id: n.id, label: n.data?.label, type: n.data?.type }))
      });

      if (!sourceNodeId) {
        throw new Error(`无法解析源节点ID: ${operation.data.edge.source_node_id}`);
      }
      if (!targetNodeId) {
        throw new Error(`无法解析目标节点ID: ${operation.data.edge.target_node_id}`);
      }

      // 验证解析后的ID确实是UUID格式
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (!uuidRegex.test(sourceNodeId)) {
        throw new Error(`解析后的源节点ID不是有效的UUID: ${sourceNodeId}`);
      }
      if (!uuidRegex.test(targetNodeId)) {
        throw new Error(`解析后的目标节点ID不是有效的UUID: ${targetNodeId}`);
      }

      return await onConnectionCreate({
        from_node_base_id: sourceNodeId,
        to_node_base_id: targetNodeId,
        workflow_base_id: workflowId,
        connection_type: operation.data.edge.connection_type,
        condition_config: operation.data.edge.condition_config
      });

    default:
      throw new Error(`不支持的操作类型: ${operation.type}`);
  }
}