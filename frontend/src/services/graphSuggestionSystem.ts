/**
 * 统一的图操作建议系统
 * 用操作序列代替分离的节点/边建议
 */

// 图操作类型定义
export enum GraphOperationType {
  ADD_NODE = 'add_node',
  REMOVE_NODE = 'remove_node',
  UPDATE_NODE = 'update_node',
  ADD_EDGE = 'add_edge',
  REMOVE_EDGE = 'remove_edge',
  UPDATE_EDGE = 'update_edge'
}

// 单个图操作定义
export interface GraphOperation {
  id: string;
  type: GraphOperationType;
  data: {
    // 节点操作数据
    node?: {
      id?: string;
      name?: string;
      type?: 'start' | 'processor' | 'end';
      task_description?: string;
      position?: { x: number; y: number };
      processor_id?: string;
    };
    // 边操作数据
    edge?: {
      id?: string;
      source_node_id?: string;
      target_node_id?: string;
      connection_type?: 'normal' | 'conditional' | 'parallel';
      condition_config?: any;
    };
    // 更新操作的变更数据
    updates?: {
      [key: string]: any;
    };
  };
  reasoning: string; // 该操作的理由
}

// 图建议（操作组）
export interface GraphSuggestion {
  id: string;
  name: string; // 建议名称，如"添加数据处理流程"
  description: string; // 建议描述
  operations: GraphOperation[]; // 操作序列
  confidence: number; // 整体置信度
  reasoning: string; // 整体推理
  preview?: {
    // 预览信息，帮助用户理解这组操作的效果
    nodes_to_add: number;
    edges_to_add: number;
    estimated_completion_improvement: number; // 预期的完整度提升 0-1
  };
}

// 增强的上下文信息
export interface WorkflowContext {
  // 工作流元数据
  workflow_name?: string;
  workflow_description?: string;
  workflow_id?: string;

  // 当前图状态
  current_nodes: Array<{
    id: string;
    name: string;
    type: string;
    position: { x: number; y: number };
    task_description?: string;
  }>;
  current_edges: Array<{
    id: string;
    source: string;
    target: string;
    connection_type?: string;
  }>;

  // 用户交互上下文
  cursor_position?: { x: number; y: number };
  selected_node_id?: string;
  recent_actions?: Array<{
    action: string;
    timestamp: Date;
    details?: any;
  }>;

  // 工作流分析
  completion_status: {
    has_start: boolean;
    has_end: boolean;
    node_count: number;
    edge_count: number;
    estimated_completeness: number; // 0-1
  };
}

// API请求接口
export interface GraphSuggestionRequest {
  context: WorkflowContext;
  trigger_type: 'canvas_click' | 'node_select' | 'manual_request';
  max_suggestions?: number;
}

// API响应接口
export interface GraphSuggestionResponse {
  success: boolean;
  suggestions: GraphSuggestion[];
  context_analysis?: {
    workflow_completeness: number;
    missing_components: string[];
    suggested_next_steps: string[];
  };
  message?: string;
}

// 工作流上下文管理器（重新设计）
class WorkflowContextManager {
  private context: WorkflowContext = {
    current_nodes: [],
    current_edges: [],
    completion_status: {
      has_start: false,
      has_end: false,
      node_count: 0,
      edge_count: 0,
      estimated_completeness: 0
    }
  };

  private actionHistory: Array<{
    action: string;
    timestamp: Date;
    details?: any;
  }> = [];

  // 更新工作流上下文
  updateWorkflowContext(updates: Partial<WorkflowContext>) {
    this.context = { ...this.context, ...updates };
    this.analyzeCompletionStatus();
  }

  // 更新图状态
  updateGraphState(nodes: any[], edges: any[]) {
    this.context.current_nodes = nodes.map(node => ({
      id: node.id,
      name: node.data?.label || node.data?.name || '未命名节点',
      type: node.data?.type || 'processor',
      position: node.position,
      task_description: node.data?.description || node.data?.task_description
    }));

    this.context.current_edges = edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      connection_type: edge.data?.connection_type || 'normal'
    }));

    this.analyzeCompletionStatus();
  }

  // 记录用户操作
  addAction(action: string, details?: any) {
    this.actionHistory.push({
      action,
      timestamp: new Date(),
      details
    });

    // 只保留最近20个操作
    if (this.actionHistory.length > 20) {
      this.actionHistory = this.actionHistory.slice(-20);
    }

    this.context.recent_actions = this.actionHistory;
  }

  // 分析工作流完整性
  private analyzeCompletionStatus() {
    const { current_nodes, current_edges } = this.context;

    const has_start = current_nodes.some(n => n.type === 'start');
    const has_end = current_nodes.some(n => n.type === 'end');
    const node_count = current_nodes.length;
    const edge_count = current_edges.length;

    // 简单的完整度估算算法
    let completeness = 0;
    if (has_start) completeness += 0.3;
    if (has_end) completeness += 0.3;
    if (node_count > 2) completeness += 0.2;
    if (edge_count >= node_count - 1) completeness += 0.2; // 基本连通

    this.context.completion_status = {
      has_start,
      has_end,
      node_count,
      edge_count,
      estimated_completeness: Math.min(completeness, 1.0)
    };
  }

  // 生成用于API的上下文
  getContextForAPI(): WorkflowContext {
    return { ...this.context };
  }

  // 检查是否应该触发建议
  shouldTriggerSuggestion(triggerType: string, position?: { x: number; y: number }): boolean {
    const { node_count } = this.context.completion_status;

    // 基本触发条件
    if (triggerType === 'canvas_click' && position) {
      this.context.cursor_position = position;
      return true;
    }

    if (triggerType === 'node_select') {
      return node_count > 0; // 有节点时才能选择节点触发
    }

    if (triggerType === 'manual_request') {
      return true;
    }

    return false;
  }
}

// 导出全局实例
export const workflowContextManager = new WorkflowContextManager();

// 图建议API客户端
export class GraphSuggestionAPI {
  private baseURL: string;

  constructor() {
    this.baseURL = `${process.env.REACT_APP_API_BASE_URL || (process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api')}/tab-completion`;
  }

  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('token');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    };
  }

  // 获取图操作建议
  async getGraphSuggestions(request: GraphSuggestionRequest): Promise<GraphSuggestionResponse> {
    try {
      console.log('🔮 [GRAPH-API] 请求图操作建议:', request);

      const response = await fetch(`${this.baseURL}/predict-graph-operations`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify({
          workflow_context: request.context,
          trigger_type: request.trigger_type,
          max_suggestions: request.max_suggestions || 3
        })
      });

      if (!response.ok) {
        throw new Error(`API请求失败: ${response.status}`);
      }

      const result = await response.json();
      console.log('🔮 [GRAPH-API] 图操作建议响应:', result);

      return result;
    } catch (error) {
      console.error('🔮 [GRAPH-API] 图操作建议失败:', error);
      throw error;
    }
  }

  // 跟踪操作执行
  async trackOperationExecution(suggestionId: string, operations: GraphOperation[], success: boolean) {
    try {
      await fetch(`${this.baseURL}/track-operation-execution`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify({
          suggestion_id: suggestionId,
          operations: operations,
          success: success,
          executed_at: new Date().toISOString()
        })
      });
    } catch (error) {
      console.warn('🔮 [GRAPH-API] 操作执行跟踪失败:', error);
    }
  }
}

export const graphSuggestionAPI = new GraphSuggestionAPI();