import { useState, useCallback } from 'react';
import { message } from 'antd';
import { ConversationMessage, ConversationSession } from '../types/conversation';

interface UseTaskConversationReturn {
  messages: ConversationMessage[];
  loading: boolean;
  error: string | null;
  sendMessage: (content: string, includeContext?: boolean, contextType?: string) => Promise<void>;
  clearHistory: () => Promise<void>;
  loadHistory: () => Promise<void>;
}

export const useTaskConversation = (taskId: string): UseTaskConversationReturn => {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getAuthToken = () => {
    return localStorage.getItem('token');
  };

  const sendMessage = useCallback(async (
    content: string,
    includeContext: boolean = true,
    contextType: string = 'summary'
  ) => {
    if (!taskId || !content.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const token = getAuthToken();
      const response = await fetch(`/api/tasks/${taskId}/conversation/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: content,
          include_context: includeContext,
          context_type: contextType
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || '发送消息失败');
      }

      if (data.success) {
        // 重新加载对话历史以获取最新消息
        await loadHistory();
      } else {
        throw new Error(data.detail || '发送消息失败');
      }

    } catch (err: any) {
      console.error('发送消息失败:', err);
      setError(err.message || '发送消息失败');
      message.error(err.message || '发送消息失败');
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  const loadHistory = useCallback(async () => {
    if (!taskId) return;

    try {
      const token = getAuthToken();
      const response = await fetch(`/api/tasks/${taskId}/conversation/history`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || '获取对话历史失败');
      }

      if (data.success && data.data) {
        setMessages(data.data.messages || []);
      }

    } catch (err: any) {
      console.error('获取对话历史失败:', err);
      setError(err.message || '获取对话历史失败');
    }
  }, [taskId]);

  const clearHistory = useCallback(async () => {
    if (!taskId) return;

    try {
      const token = getAuthToken();
      const response = await fetch(`/api/tasks/${taskId}/conversation/clear`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || '清空对话历史失败');
      }

      if (data.success) {
        setMessages([]);
        message.success('对话历史已清空');
      }

    } catch (err: any) {
      console.error('清空对话历史失败:', err);
      setError(err.message || '清空对话历史失败');
      message.error(err.message || '清空对话历史失败');
    }
  }, [taskId]);

  return {
    messages,
    loading,
    error,
    sendMessage,
    clearHistory,
    loadHistory
  };
};