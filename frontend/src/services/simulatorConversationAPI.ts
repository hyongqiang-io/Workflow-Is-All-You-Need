import api from './api';

export interface CreateSessionRequest {
  task_instance_id: string;
  node_instance_id: string;
  processor_id: string;
  weak_model: string;
  strong_model: string;
  max_rounds?: number;
}

export interface SendMessageRequest {
  role: 'weak_model' | 'strong_model' | 'system';
  content: string;
  metadata?: any;
}

export interface DecisionRequest {
  decision_type: 'direct_submit' | 'consult_complete' | 'max_rounds_reached';
  result_data: any;
  confidence_score?: number;
  decision_reasoning?: string;
}

export interface SessionResponse {
  session: {
    session_id: string;
    task_instance_id: string;
    node_instance_id: string;
    processor_id: string;
    weak_model: string;
    strong_model: string;
    max_rounds: number;
    current_round: number;
    status: 'active' | 'completed' | 'interrupted' | 'failed';
    final_decision?: string;
    created_at: string;
    updated_at: string;
    completed_at?: string;
  };
  messages: Array<{
    message_id: string;
    session_id: string;
    round_number: number;
    role: 'weak_model' | 'strong_model' | 'system';
    content: string;
    metadata?: any;
    created_at: string;
  }>;
  can_continue: boolean;
  next_action: string;
}

export const simulatorConversationAPI = {
  /**
   * 创建新的Simulator对话会话
   */
  async createSession(request: CreateSessionRequest) {
    const response = await api.post('/simulator/conversation/sessions', request);
    return response.data;
  },

  /**
   * 获取会话及其消息
   */
  async getSession(sessionId: string): Promise<SessionResponse> {
    const response = await api.get(`/simulator/conversation/sessions/${sessionId}`);
    return response.data;
  },

  /**
   * 发送消息到会话
   */
  async sendMessage(sessionId: string, request: SendMessageRequest) {
    const response = await api.post(`/simulator/conversation/sessions/${sessionId}/messages`, request);
    return response.data;
  },

  /**
   * 做出最终决策
   */
  async makeDecision(sessionId: string, request: DecisionRequest) {
    const response = await api.post(`/simulator/conversation/sessions/${sessionId}/decision`, request);
    return response.data;
  },

  /**
   * 中断会话
   */
  async interruptSession(sessionId: string, reason?: string) {
    const response = await api.post(`/simulator/conversation/sessions/${sessionId}/interrupt`, {
      reason: reason || '用户中断'
    });
    return response.data;
  },

  /**
   * 获取会话统计信息
   */
  async getSessionStatistics(sessionId: string) {
    const response = await api.get(`/simulator/conversation/sessions/${sessionId}/statistics`);
    return response.data;
  },

  /**
   * 根据任务实例ID获取所有相关会话
   */
  async getSessionsByTask(taskInstanceId: string) {
    const response = await api.get(`/simulator/conversation/sessions/task/${taskInstanceId}`);
    return response.data;
  },

  /**
   * 健康检查
   */
  async healthCheck() {
    const response = await api.get('/simulator/conversation/health');
    return response.data;
  }
};