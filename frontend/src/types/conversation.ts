/**
 * 人类任务AI对话相关类型定义
 */

export interface ConversationMessage {
  id: string;
  task_instance_id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  context_data?: any; // 消息发送时的任务上下文快照
  attachments?: string[]; // 消息关联的文件ID
}

export interface ConversationSession {
  task_instance_id: string;
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface TaskConversationState {
  sessions: { [taskId: string]: ConversationSession };
  currentMessages: ConversationMessage[];
  loading: boolean;
  error: string | null;
}

export interface ConversationRequest {
  task_instance_id: string;
  message: string;
  include_context?: boolean; // 是否包含任务上下文
  context_type?: 'full' | 'summary' | 'minimal'; // 上下文详细程度
}

export interface ConversationResponse {
  message_id: string;
  content: string;
  suggestions?: string[]; // AI建议的后续操作
  context_used?: any; // AI实际使用的上下文数据
}