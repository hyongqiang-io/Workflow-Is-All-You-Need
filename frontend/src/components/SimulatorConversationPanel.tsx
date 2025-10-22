import React, { useState, useEffect, useCallback } from 'react';
import { Card, Button, Input, List, Avatar, Tag, Space, Spin, message } from 'antd';
import { SendOutlined, StopOutlined, CheckOutlined } from '@ant-design/icons';
import { simulatorConversationAPI } from '../services/simulatorConversationAPI';

const { TextArea } = Input;

interface Message {
  message_id: string;
  round_number: number;
  role: 'weak_model' | 'strong_model' | 'system';
  content: string;
  metadata?: any;
  created_at: string;
}

interface Session {
  session_id: string;
  task_instance_id: string;
  weak_model: string;
  strong_model: string;
  current_round: number;
  max_rounds: number;
  status: 'active' | 'completed' | 'interrupted' | 'failed';
  final_decision?: string;
}

interface SimulatorConversationPanelProps {
  taskId: string;
  sessionId?: string;
  onConversationComplete?: (result: any) => void;
  onConversationInterrupt?: () => void;
}

const SimulatorConversationPanel: React.FC<SimulatorConversationPanelProps> = ({
  taskId,
  sessionId,
  onConversationComplete,
  onConversationInterrupt
}) => {
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [currentInput, setCurrentInput] = useState('');
  const [canContinue, setCanContinue] = useState(false);
  const [nextAction, setNextAction] = useState<string>('');

  // 加载会话数据
  const loadSession = useCallback(async () => {
    if (!sessionId) return;

    try {
      setLoading(true);
      const response = await simulatorConversationAPI.getSession(sessionId);
      setSession(response.session);
      setMessages(response.messages);
      setCanContinue(response.can_continue);
      setNextAction(response.next_action);
    } catch (error) {
      console.error('加载会话失败:', error);
      message.error('加载对话会话失败');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      loadSession();
    }
  }, [sessionId, loadSession]);

  // 发送消息
  const sendMessage = async () => {
    if (!sessionId || !currentInput.trim()) return;

    try {
      setSending(true);
      await simulatorConversationAPI.sendMessage(sessionId, {
        role: 'strong_model',
        content: currentInput.trim()
      });

      setCurrentInput('');

      // 重新加载会话，检查弱模型是否自主终止了对话
      const updatedSession = await simulatorConversationAPI.getSession(sessionId);
      setSession(updatedSession.session);
      setMessages(updatedSession.messages);
      setCanContinue(updatedSession.can_continue);
      setNextAction(updatedSession.next_action);

      // 检查是否弱模型自主终止了对话
      if (updatedSession.session.status === 'completed' &&
          updatedSession.session.final_decision === 'weak_model_terminated') {
        message.success('弱模型已自主完成任务分析并终止对话');
        onConversationComplete?.(updatedSession);
      } else if (updatedSession.session.status === 'completed' &&
          updatedSession.session.final_decision === 'consult_complete') {
        message.success('对话已完成');
        onConversationComplete?.(updatedSession);
      } else {
        message.success('消息发送成功');
      }

    } catch (error) {
      console.error('发送消息失败:', error);
      message.error('发送消息失败');
    } finally {
      setSending(false);
    }
  };

  // 提交最终决策
  const submitDecision = async () => {
    if (!sessionId || !currentInput.trim()) return;

    try {
      setSending(true);
      const result = await simulatorConversationAPI.makeDecision(sessionId, {
        decision_type: 'consult_complete',
        result_data: {
          answer: currentInput.trim(),
          timestamp: new Date().toISOString()
        },
        confidence_score: 0.9,
        decision_reasoning: '经过对话协商后的最终决策'
      });

      message.success('任务已完成');
      onConversationComplete?.(result);
    } catch (error) {
      console.error('提交决策失败:', error);
      message.error('提交决策失败');
    } finally {
      setSending(false);
    }
  };

  // 中断对话
  const interruptConversation = async () => {
    if (!sessionId) return;

    try {
      await simulatorConversationAPI.interruptSession(sessionId, '用户中断对话');
      message.info('对话已中断');
      onConversationInterrupt?.();
    } catch (error) {
      console.error('中断对话失败:', error);
      message.error('中断对话失败');
    }
  };

  // 渲染消息角色标签
  const renderRoleTag = (role: string) => {
    const roleConfig = {
      weak_model: { color: 'blue', text: '弱模型' },
      strong_model: { color: 'green', text: '强模型' },
      system: { color: 'gray', text: '系统' }
    };

    const config = roleConfig[role as keyof typeof roleConfig] || { color: 'default', text: role };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  // 渲染消息列表
  const renderMessages = () => (
    <List
      dataSource={messages}
      renderItem={(message) => {
        const isWeakModelTermination = message.role === 'weak_model' &&
          session?.status === 'completed' &&
          session?.final_decision === 'weak_model_terminated';

        return (
          <List.Item key={message.message_id}>
            <List.Item.Meta
              avatar={
                <Avatar
                  style={{
                    backgroundColor: message.role === 'weak_model' ? '#1890ff' :
                                    message.role === 'strong_model' ? '#52c41a' : '#8c8c8c'
                  }}
                >
                  {message.role === 'weak_model' ? '弱' :
                   message.role === 'strong_model' ? '强' : '系'}
                </Avatar>
              }
              title={
                <Space>
                  {renderRoleTag(message.role)}
                  <span style={{ fontSize: '12px', color: '#8c8c8c' }}>
                    第{message.round_number}轮
                  </span>
                  {isWeakModelTermination && (
                    <Tag color="orange">
                      自主终止
                    </Tag>
                  )}
                  {message.metadata?.confidence && (
                    <Tag color="blue">
                      置信度: {(message.metadata.confidence * 100).toFixed(0)}%
                    </Tag>
                  )}
                </Space>
              }
              description={
                <div>
                  <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {message.content}
                  </div>
                  {isWeakModelTermination && (
                    <div style={{
                      marginTop: '8px',
                      padding: '8px',
                      backgroundColor: '#fff7e6',
                      border: '1px solid #ffd666',
                      borderRadius: '4px',
                      fontSize: '12px'
                    }}>
                      🤖 弱模型判断已获得充分信息，自主终止对话并提交结果
                    </div>
                  )}
                </div>
              }
            />
          </List.Item>
        );
      }}
      style={{ maxHeight: '400px', overflowY: 'auto' }}
    />
  );

  // 渲染输入区域
  const renderInputArea = () => {
    if (!canContinue) {
      return (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Tag color="orange">对话已结束</Tag>
        </div>
      );
    }

    return (
      <div style={{ marginTop: '16px' }}>
        <TextArea
          value={currentInput}
          onChange={(e) => setCurrentInput(e.target.value)}
          placeholder={
            nextAction === 'wait_strong_model'
              ? '作为强模型，请输入您的回复...'
              : '请输入您的消息...'
          }
          rows={4}
          disabled={sending}
        />
        <div style={{ marginTop: '8px', textAlign: 'right' }}>
          <Space>
            <Button
              icon={<StopOutlined />}
              onClick={interruptConversation}
              disabled={sending}
            >
              中断对话
            </Button>
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={sendMessage}
              disabled={!currentInput.trim() || sending}
              loading={sending}
            >
              继续对话
            </Button>
            <Button
              type="primary"
              icon={<CheckOutlined />}
              onClick={submitDecision}
              disabled={!currentInput.trim() || sending}
              loading={sending}
              style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}
            >
              提交决策
            </Button>
          </Space>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" />
          <p style={{ marginTop: '16px' }}>加载对话会话中...</p>
        </div>
      </Card>
    );
  }

  if (!session) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <p>未找到对话会话</p>
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={
        <div>
          <span>Simulator 智能对话</span>
          <div style={{ fontSize: '12px', fontWeight: 'normal', color: '#8c8c8c' }}>
            弱模型: {session.weak_model} | 强模型: {session.strong_model} |
            轮次: {session.current_round}/{session.max_rounds}
          </div>
        </div>
      }
      extra={
        <Space>
          <Tag color={session.status === 'active' ? 'green' : 'orange'}>
            {session.status === 'active' ? '进行中' :
             session.final_decision === 'weak_model_terminated' ? '弱模型终止' :
             '已结束'}
          </Tag>
          {session.final_decision === 'weak_model_terminated' && (
            <Tag color="blue">
              智能终止
            </Tag>
          )}
        </Space>
      }
    >
      {messages.length > 0 ? renderMessages() : (
        <div style={{ textAlign: 'center', padding: '20px', color: '#8c8c8c' }}>
          对话即将开始...
        </div>
      )}
      {renderInputArea()}
    </Card>
  );
};

export default SimulatorConversationPanel;