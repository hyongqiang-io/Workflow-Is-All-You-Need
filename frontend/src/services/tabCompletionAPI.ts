/**
 * Tab补全相关的API服务
 * 与后端Tab补全API进行交互
 */

// Tab补全API接口定义
interface NodePredictionRequest {
  context_summary: string;
  max_suggestions?: number;
  trigger_type?: string;
  cursor_position?: { x: number; y: number };
}

interface ConnectionPredictionRequest {
  context_summary: string;
  source_node_id: string;
  max_suggestions?: number;
}

interface WorkflowCompletionRequest {
  context_summary: string;
  partial_description: string;
}

interface InteractionTrackingRequest {
  workflow_id: string;
  session_id: string;
  event_type: string;
  suggestion_type?: string;
  event_data?: any;
  context_summary?: string;
}

interface UserBehaviorAnalysisRequest {
  days_back?: number;
}

class TabCompletionAPI {
  private baseURL: string;

  constructor() {
    this.baseURL = `${process.env.REACT_APP_API_BASE_URL || (process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api')}/tab-completion`;
  }

  /**
   * 获取认证头
   */
  private getAuthHeaders(): HeadersInit {
    const token = localStorage.getItem('token');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    };
  }

  /**
   * 通用API请求处理
   */
  private async makeRequest<T>(
    endpoint: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET',
    data?: any
  ): Promise<T> {
    try {
      const config: RequestInit = {
        method,
        headers: this.getAuthHeaders(),
      };

      if (data && (method === 'POST' || method === 'PUT')) {
        config.body = JSON.stringify(data);
      }

      const response = await fetch(`${this.baseURL}${endpoint}`, config);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `API请求失败: ${response.status}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error(`Tab补全API请求失败 [${endpoint}]:`, error);
      throw error;
    }
  }

  /**
   * 预测下一个节点
   */
  async predictNodes(request: NodePredictionRequest) {
    console.log('🔮 [API] 请求节点预测:', request);

    const result = await this.makeRequest('/predict-nodes', 'POST', {
      context_summary: request.context_summary,
      max_suggestions: request.max_suggestions || 3,
      trigger_type: request.trigger_type || 'empty_space_click',
      cursor_position: request.cursor_position || { x: 0, y: 0 }
    });

    console.log('🔮 [API] 节点预测结果:', result);
    return result;
  }

  /**
   * 预测连接
   */
  async predictConnections(request: ConnectionPredictionRequest) {
    console.log('🔮 [API] 请求连接预测:', request);

    const result = await this.makeRequest('/predict-connections', 'POST', {
      context_summary: request.context_summary,
      source_node_id: request.source_node_id,
      max_suggestions: request.max_suggestions || 3
    });

    console.log('🔮 [API] 连接预测结果:', result);
    return result;
  }

  /**
   * 预测工作流完整性
   */
  async predictWorkflowCompletion(request: WorkflowCompletionRequest) {
    console.log('🔮 [API] 请求工作流完整性预测:', request);

    const result = await this.makeRequest('/predict-completion', 'POST', {
      context_summary: request.context_summary,
      partial_description: request.partial_description
    });

    console.log('🔮 [API] 工作流完整性预测结果:', result);
    return result;
  }

  /**
   * 跟踪用户交互
   */
  async trackInteraction(request: InteractionTrackingRequest) {
    try {
      console.log('🔮 [API] 跟踪用户交互:', request);

      const result = await this.makeRequest('/track-interaction', 'POST', {
        workflow_id: request.workflow_id,
        session_id: request.session_id,
        event_type: request.event_type,
        suggestion_type: request.suggestion_type,
        event_data: request.event_data,
        context_summary: request.context_summary
      });

      console.log('🔮 [API] 交互跟踪结果:', result);
      return result;
    } catch (error) {
      // 交互跟踪失败不应影响主要功能
      console.warn('🔮 [API] 交互跟踪失败（不影响主功能）:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  }

  /**
   * 获取用户行为分析
   */
  async getUserBehaviorAnalysis(request: UserBehaviorAnalysisRequest = {}) {
    console.log('🔮 [API] 请求用户行为分析:', request);

    const queryParams = new URLSearchParams();
    if (request.days_back) {
      queryParams.append('days_back', request.days_back.toString());
    }

    const endpoint = `/user-behavior-analysis${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const result = await this.makeRequest(endpoint, 'GET');

    console.log('🔮 [API] 用户行为分析结果:', result);
    return result;
  }

  /**
   * 获取全局统计信息
   */
  async getGlobalStatistics(daysBack: number = 7) {
    console.log('🔮 [API] 请求全局统计信息, 天数:', daysBack);

    const result = await this.makeRequest(`/global-statistics?days_back=${daysBack}`, 'GET');

    console.log('🔮 [API] 全局统计信息结果:', result);
    return result;
  }

  /**
   * 清空预测缓存
   */
  async clearPredictionCache() {
    console.log('🔮 [API] 清空预测缓存');

    const result = await this.makeRequest('/clear-cache', 'POST');

    console.log('🔮 [API] 缓存清空结果:', result);
    return result;
  }

  /**
   * 批量跟踪交互事件（优化性能）
   */
  async batchTrackInteractions(interactions: InteractionTrackingRequest[]) {
    try {
      console.log('🔮 [API] 批量跟踪交互:', interactions.length);

      const result = await this.makeRequest('/batch-track-interactions', 'POST', {
        interactions
      });

      console.log('🔮 [API] 批量跟踪结果:', result);
      return result;
    } catch (error) {
      console.warn('🔮 [API] 批量交互跟踪失败:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  }

  /**
   * 获取建议效果统计
   */
  async getSuggestionEffectiveness(workflowId?: string, daysBack: number = 7) {
    console.log('🔮 [API] 请求建议效果统计:', { workflowId, daysBack });

    const queryParams = new URLSearchParams({ days_back: daysBack.toString() });
    if (workflowId) {
      queryParams.append('workflow_id', workflowId);
    }

    const result = await this.makeRequest(`/suggestion-effectiveness?${queryParams.toString()}`, 'GET');

    console.log('🔮 [API] 建议效果统计结果:', result);
    return result;
  }

  /**
   * 更新用户满意度反馈
   */
  async updateUserSatisfaction(interactionId: string, satisfaction: 'very_low' | 'low' | 'medium' | 'high' | 'very_high') {
    console.log('🔮 [API] 更新用户满意度:', { interactionId, satisfaction });

    const result = await this.makeRequest('/update-satisfaction', 'POST', {
      interaction_id: interactionId,
      satisfaction
    });

    console.log('🔮 [API] 满意度更新结果:', result);
    return result;
  }
}

// 创建Tab补全API实例
export const tabCompletionAPI = new TabCompletionAPI();

// 导出类型
export type {
  NodePredictionRequest,
  ConnectionPredictionRequest,
  WorkflowCompletionRequest,
  InteractionTrackingRequest,
  UserBehaviorAnalysisRequest
};