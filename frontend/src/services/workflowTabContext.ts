/**
 * 工作流Tab补全上下文管理器
 * 负责收集和管理工作流编辑时的上下文信息，用于智能补全预测
 */

import { Node, Edge } from 'reactflow';

// 用户行为模式接口
export interface UserBehaviorPattern {
  patternId: string;
  sourceNodeType: string;
  targetNodeType: string;
  frequency: number;
  successRate: number;
  contextTags: string[];
  lastUsed: Date;
}

// 节点建议接口
export interface NodeSuggestion {
  id: string;
  type: 'start' | 'processor' | 'end';
  name: string;
  description?: string;
  processor_id?: string;
  position: { x: number; y: number };
  confidence: number; // 0-1之间的置信度
  reasoning: string; // 建议理由
}

// 连接建议接口
export interface EdgeSuggestion {
  id: string;
  source_node_id: string; // 源节点ID (匹配API格式)
  target_node_id: string; // 目标节点ID (匹配API格式)
  target_node_name: string; // 目标节点名称，用于显示
  connection_type: 'normal' | 'conditional' | 'parallel'; // 匹配API格式
  confidence: number;
  reasoning: string;
  condition_config?: any;
}

// 工作流上下文接口
export interface WorkflowContext {
  // 当前工作流状态
  currentNodes: Node[];
  currentEdges: Edge[];
  workflowId?: string;

  // 用户当前操作状态
  cursorPosition: { x: number; y: number };
  selectedNode?: Node;
  selectedEdge?: Edge;
  lastAction?: 'add_node' | 'add_edge' | 'edit_node' | 'edit_edge';

  // 任务上下文
  taskDescription?: string;
  workflowName?: string;

  // 用户行为历史
  userPatterns: UserBehaviorPattern[];
  recentActions: ActionHistory[];
}

// 操作历史接口
export interface ActionHistory {
  timestamp: Date;
  action: string;
  nodeId?: string;
  edgeId?: string;
  details: any;
}

// 补全触发条件
export interface TriggerCondition {
  type: 'node_hover' | 'empty_space_click' | 'node_connection_start' | 'task_description_change';
  position?: { x: number; y: number };
  sourceNode?: Node;
  targetArea?: 'input' | 'output';
}

export class WorkflowTabContext {
  private context: WorkflowContext;
  private listeners: Array<(context: WorkflowContext) => void> = [];
  private suggestionCache: Map<string, NodeSuggestion[]> = new Map();
  private edgeSuggestionCache: Map<string, EdgeSuggestion[]> = new Map();

  constructor(initialContext?: Partial<WorkflowContext>) {
    this.context = {
      currentNodes: [],
      currentEdges: [],
      cursorPosition: { x: 0, y: 0 },
      userPatterns: [],
      recentActions: [],
      ...initialContext
    };
  }

  // 更新上下文
  updateContext(updates: Partial<WorkflowContext>) {
    const previousContext = { ...this.context };
    this.context = { ...this.context, ...updates };

    // 记录重要的操作历史
    if (updates.currentNodes && updates.currentNodes.length !== previousContext.currentNodes.length) {
      this.addActionHistory({
        timestamp: new Date(),
        action: 'nodes_changed',
        details: {
          previousCount: previousContext.currentNodes.length,
          newCount: updates.currentNodes.length
        }
      });
    }

    // 通知监听器
    this.notifyListeners();

    // 清除相关缓存
    this.clearRelevantCache(updates);
  }

  // 获取当前上下文
  getContext(): WorkflowContext {
    return { ...this.context };
  }

  // 添加操作历史
  addActionHistory(action: ActionHistory) {
    this.context.recentActions.unshift(action);
    // 只保留最近50个操作
    if (this.context.recentActions.length > 50) {
      this.context.recentActions = this.context.recentActions.slice(0, 50);
    }
  }

  // 更新用户行为模式
  updateUserPattern(pattern: UserBehaviorPattern) {
    const existingIndex = this.context.userPatterns.findIndex(
      p => p.patternId === pattern.patternId
    );

    if (existingIndex >= 0) {
      this.context.userPatterns[existingIndex] = pattern;
    } else {
      this.context.userPatterns.push(pattern);
    }

    // 按频率和成功率排序
    this.context.userPatterns.sort((a, b) => {
      return (b.frequency * b.successRate) - (a.frequency * a.successRate);
    });
  }

  // 分析当前上下文，判断是否应该触发补全建议
  shouldTriggerSuggestion(trigger: TriggerCondition): boolean {
    const { currentNodes, currentEdges } = this.context;

    switch (trigger.type) {
      case 'node_hover':
        // 当用户悬停在节点上超过1秒时触发连接建议
        return true;

      case 'empty_space_click':
        // 在空白区域点击时触发节点建议
        return trigger.position ? !this.isPositionOccupied(trigger.position) : false;

      case 'node_connection_start':
        // 开始连接节点时触发目标节点建议
        return trigger.sourceNode !== undefined;

      case 'task_description_change':
        // 任务描述改变时触发工作流结构建议
        return this.context.taskDescription !== undefined && this.context.taskDescription.length > 10;

      default:
        return false;
    }
  }

  // 检查位置是否被占用
  private isPositionOccupied(position: { x: number; y: number }, threshold: number = 100): boolean {
    return this.context.currentNodes.some(node => {
      const distance = Math.sqrt(
        Math.pow(node.position.x - position.x, 2) +
        Math.pow(node.position.y - position.y, 2)
      );
      return distance < threshold;
    });
  }

  // 获取合适的节点放置位置
  getSuggestedPosition(preferredPosition?: { x: number; y: number }): { x: number; y: number } {
    if (preferredPosition && !this.isPositionOccupied(preferredPosition)) {
      return preferredPosition;
    }

    // 根据现有节点布局智能推荐位置
    if (this.context.currentNodes.length === 0) {
      return { x: 200, y: 200 };
    }

    // 找到最右边的节点，在其右侧放置新节点
    const rightmostNode = this.context.currentNodes.reduce((rightmost, node) => {
      return node.position.x > rightmost.position.x ? node : rightmost;
    });

    return {
      x: rightmostNode.position.x + 250,
      y: rightmostNode.position.y
    };
  }

  // 分析工作流模式
  analyzeWorkflowPattern(): {
    hasStartNode: boolean;
    hasEndNode: boolean;
    processorNodeCount: number;
    averageConnectionsPerNode: number;
    suggestedNextNodeType: 'start' | 'processor' | 'end' | null;
  } {
    const { currentNodes, currentEdges } = this.context;

    const startNodes = currentNodes.filter(n => n.data.type === 'start');
    const endNodes = currentNodes.filter(n => n.data.type === 'end');
    const processorNodes = currentNodes.filter(n => n.data.type === 'processor');

    const averageConnections = currentNodes.length > 0
      ? currentEdges.length / currentNodes.length
      : 0;

    let suggestedNextNodeType: 'start' | 'processor' | 'end' | null = null;

    if (startNodes.length === 0) {
      suggestedNextNodeType = 'start';
    } else if (processorNodes.length === 0) {
      suggestedNextNodeType = 'processor';
    } else if (endNodes.length === 0 && processorNodes.length > 0) {
      suggestedNextNodeType = 'end';
    } else if (processorNodes.length < 3) {
      suggestedNextNodeType = 'processor';
    }

    return {
      hasStartNode: startNodes.length > 0,
      hasEndNode: endNodes.length > 0,
      processorNodeCount: processorNodes.length,
      averageConnectionsPerNode: averageConnections,
      suggestedNextNodeType
    };
  }

  // 注册上下文变化监听器
  addListener(listener: (context: WorkflowContext) => void) {
    this.listeners.push(listener);
  }

  // 移除监听器
  removeListener(listener: (context: WorkflowContext) => void) {
    const index = this.listeners.indexOf(listener);
    if (index > -1) {
      this.listeners.splice(index, 1);
    }
  }

  // 通知所有监听器
  private notifyListeners() {
    this.listeners.forEach(listener => {
      try {
        listener(this.context);
      } catch (error) {
        console.error('WorkflowTabContext listener error:', error);
      }
    });
  }

  // 清除相关缓存
  private clearRelevantCache(updates: Partial<WorkflowContext>) {
    if (updates.currentNodes || updates.currentEdges || updates.taskDescription) {
      this.suggestionCache.clear();
      this.edgeSuggestionCache.clear();
    }
  }

  // 生成上下文摘要（用于AI预测）
  generateContextSummary(): string {
    const { currentNodes, currentEdges, taskDescription } = this.context;
    const pattern = this.analyzeWorkflowPattern();

    const summary = {
      task: taskDescription || "未指定任务",
      nodeCount: currentNodes.length,
      edgeCount: currentEdges.length,
      hasStart: pattern.hasStartNode,
      hasEnd: pattern.hasEndNode,
      processorCount: pattern.processorNodeCount,
      suggestedNext: pattern.suggestedNextNodeType,
      recentPatterns: this.context.userPatterns.slice(0, 3).map(p => ({
        from: p.sourceNodeType,
        to: p.targetNodeType,
        success: p.successRate
      }))
    };

    return JSON.stringify(summary, null, 2);
  }
}

// 全局上下文实例
export const workflowTabContext = new WorkflowTabContext();