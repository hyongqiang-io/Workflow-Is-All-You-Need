import React, { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, List, Avatar, Typography, Space, Tooltip, Switch, Divider, Alert, Tag } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, ClearOutlined, SettingOutlined, BulbOutlined } from '@ant-design/icons';
import { useTaskConversation } from '../hooks/useTaskConversation';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface TaskConversationPanelProps {
  taskId: string;
  taskInfo?: {
    title: string;
    description: string;
    status: string;
  };
  onSuggestionSelect?: (suggestion: string) => void;
  className?: string;
}

const TaskConversationPanel: React.FC<TaskConversationPanelProps> = ({
  taskId,
  taskInfo,
  onSuggestionSelect,
  className
}) => {
  const [inputMessage, setInputMessage] = useState('');
  const [includeContext, setIncludeContext] = useState(true);
  const [contextType, setContextType] = useState<'full' | 'summary' | 'minimal'>('summary');
  const [showSettings, setShowSettings] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    loading,
    error,
    sendMessage,
    clearHistory,
    loadHistory
  } = useTaskConversation(taskId);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 加载历史消息
  useEffect(() => {
    if (taskId) {
      loadHistory();
    }
  }, [taskId, loadHistory]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || loading) return;

    try {
      await sendMessage(inputMessage, includeContext, contextType);
      setInputMessage('');
    } catch (error) {
      console.error('发送消息失败:', error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    if (onSuggestionSelect) {
      onSuggestionSelect(suggestion);
    } else {
      // 默认行为：将建议作为新消息发送
      setInputMessage(suggestion);
    }
  };

  const renderMessage = (message: any, index: number) => {
    const isUser = message.role === 'user';
    const suggestions = message.suggestions || [];

    return (
      <div key={message.id || index} style={{ marginBottom: '16px' }}>
        <div style={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          alignItems: 'flex-start',
          gap: '8px'
        }}>
          {!isUser && (
            <Avatar
              size="small"
              icon={<RobotOutlined />}
              style={{ backgroundColor: '#1890ff', flexShrink: 0 }}
            />
          )}

          <div style={{
            maxWidth: '80%',
            background: isUser ? '#1890ff' : '#f6f6f6',
            color: isUser ? 'white' : 'black',
            padding: '12px 16px',
            borderRadius: '12px',
            borderTopRightRadius: isUser ? '4px' : '12px',
            borderTopLeftRadius: isUser ? '12px' : '4px'
          }}>
            <Paragraph
              style={{
                margin: 0,
                color: isUser ? 'white' : 'inherit',
                whiteSpace: 'pre-wrap'
              }}
            >
              {message.content}
            </Paragraph>

            {/* 显示消息时间 */}
            <div style={{
              fontSize: '11px',
              opacity: 0.7,
              marginTop: '4px',
              textAlign: isUser ? 'right' : 'left'
            }}>
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          </div>

          {isUser && (
            <Avatar
              size="small"
              icon={<UserOutlined />}
              style={{ backgroundColor: '#52c41a', flexShrink: 0 }}
            />
          )}
        </div>

        {/* 显示AI建议 */}
        {!isUser && suggestions.length > 0 && (
          <div style={{
            marginTop: '8px',
            marginLeft: isUser ? '0' : '36px',
            marginRight: isUser ? '36px' : '0'
          }}>
            <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              <BulbOutlined /> AI建议：
            </div>
            <Space wrap size="small">
              {suggestions.map((suggestion: string, idx: number) => (
                <Tag
                  key={idx}
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleSuggestionClick(suggestion)}
                >
                  {suggestion}
                </Tag>
              ))}
            </Space>
          </div>
        )}
      </div>
    );
  };

  return (
    <Card
      className={className}
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <RobotOutlined /> AI助手
            {taskInfo && (
              <Text type="secondary" style={{ marginLeft: '8px', fontSize: '12px' }}>
                {taskInfo.title}
              </Text>
            )}
          </div>
          <Space>
            <Tooltip title="设置">
              <Button
                type="text"
                size="small"
                icon={<SettingOutlined />}
                onClick={() => setShowSettings(!showSettings)}
              />
            </Tooltip>
            <Tooltip title="清空对话">
              <Button
                type="text"
                size="small"
                icon={<ClearOutlined />}
                onClick={clearHistory}
                disabled={loading || messages.length === 0}
              />
            </Tooltip>
          </Space>
        </div>
      }
      size="small"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      bodyStyle={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        padding: '12px'
      }}
    >
      {/* 设置面板 */}
      {showSettings && (
        <div style={{ marginBottom: '12px' }}>
          <Alert
            message="对话设置"
            description={
              <div style={{ marginTop: '8px' }}>
                <div style={{ marginBottom: '8px' }}>
                  <Switch
                    size="small"
                    checked={includeContext}
                    onChange={setIncludeContext}
                  />
                  <span style={{ marginLeft: '8px' }}>包含任务上下文</span>
                </div>
                {includeContext && (
                  <div>
                    <Text style={{ fontSize: '12px' }}>上下文详细程度：</Text>
                    <div style={{ marginTop: '4px' }}>
                      <Space>
                        <Button
                          size="small"
                          type={contextType === 'minimal' ? 'primary' : 'default'}
                          onClick={() => setContextType('minimal')}
                        >
                          简要
                        </Button>
                        <Button
                          size="small"
                          type={contextType === 'summary' ? 'primary' : 'default'}
                          onClick={() => setContextType('summary')}
                        >
                          摘要
                        </Button>
                        <Button
                          size="small"
                          type={contextType === 'full' ? 'primary' : 'default'}
                          onClick={() => setContextType('full')}
                        >
                          完整
                        </Button>
                      </Space>
                    </div>
                  </div>
                )}
              </div>
            }
            type="info"
            showIcon={false}
            style={{ fontSize: '12px' }}
          />
          <Divider style={{ margin: '12px 0' }} />
        </div>
      )}

      {/* 消息列表 */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        marginBottom: '12px',
        maxHeight: '300px', // 在500px容器中为消息列表预留合适高度
        minHeight: '200px'
      }}>
        {error && (
          <Alert
            message="对话错误"
            description={error}
            type="error"
            closable
            style={{ marginBottom: '12px' }}
          />
        )}

        {messages.length === 0 && !loading && (
          <div style={{
            textAlign: 'center',
            padding: '40px 20px',
            color: '#999'
          }}>
            <RobotOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
            <div style={{ fontSize: '14px' }}>
              您好！我是您的AI助手，可以帮助您：
            </div>
            <div style={{ fontSize: '12px', marginTop: '8px' }}>
              • 理解任务要求和上下文数据<br />
              • 分析上游节点的输出结果<br />
              • 提供任务执行建议<br />
              • 协助完成任务内容
            </div>
            <div style={{ fontSize: '12px', marginTop: '12px', color: '#1890ff' }}>
              请随时向我提问！
            </div>
          </div>
        )}

        {messages.map(renderMessage)}

        {loading && (
          <div style={{
            display: 'flex',
            justifyContent: 'flex-start',
            alignItems: 'center',
            gap: '8px',
            marginBottom: '16px'
          }}>
            <Avatar
              size="small"
              icon={<RobotOutlined />}
              style={{ backgroundColor: '#1890ff' }}
            />
            <div style={{
              background: '#f6f6f6',
              padding: '12px 16px',
              borderRadius: '12px',
              borderTopLeftRadius: '4px'
            }}>
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <TextArea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入您的问题...（Shift+Enter换行，Enter发送）"
            rows={2}
            disabled={loading}
            style={{ flex: 1 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSendMessage}
            disabled={!inputMessage.trim() || loading}
            style={{ alignSelf: 'flex-end' }}
          >
            发送
          </Button>
        </div>

        {includeContext && (
          <div style={{
            fontSize: '11px',
            color: '#999',
            marginTop: '4px',
            textAlign: 'center'
          }}>
            上下文模式：{contextType === 'full' ? '完整' : contextType === 'summary' ? '摘要' : '简要'}
          </div>
        )}
      </div>

      {/* 内联CSS样式 */}
      <style>
        {`
          .typing-indicator {
            display: flex;
            gap: 4px;
            align-items: center;
          }

          .typing-indicator span {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #1890ff;
            opacity: 0.4;
            animation: typing 1.4s infinite ease-in-out;
          }

          .typing-indicator span:nth-child(1) {
            animation-delay: -0.32s;
          }

          .typing-indicator span:nth-child(2) {
            animation-delay: -0.16s;
          }

          @keyframes typing {
            0%, 80%, 100% {
              transform: scale(0.8);
              opacity: 0.4;
            }
            40% {
              transform: scale(1);
              opacity: 1;
            }
          }
        `}
      </style>
    </Card>
  );
};

export default TaskConversationPanel;