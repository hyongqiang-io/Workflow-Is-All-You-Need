/**
 * Tab补全建议框组件
 * 显示智能建议的弹出框，类似IDE的代码补全
 */

import React, { forwardRef } from 'react';
import { List, Tag, Tooltip, Spin } from 'antd';
import { BulbOutlined, RobotOutlined, LinkOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { NodeSuggestion, EdgeSuggestion } from '../services/workflowTabContext';

interface TabSuggestionBoxProps {
  suggestions: (NodeSuggestion | EdgeSuggestion)[];
  highlightedIndex: number;
  isLoading: boolean;
  position: { x: number; y: number } | null;
  onAccept: (index: number) => void;
  onReject: () => void;
}

const TabSuggestionBox = forwardRef<HTMLDivElement, TabSuggestionBoxProps>(({
  suggestions,
  highlightedIndex,
  isLoading,
  position,
  onAccept,
  onReject
}, ref) => {
  if (!position || (!isLoading && suggestions.length === 0)) {
    return null;
  }

  const isNodeSuggestion = (suggestion: NodeSuggestion | EdgeSuggestion): suggestion is NodeSuggestion => {
    return 'type' in suggestion;
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return '#52c41a';
    if (confidence >= 0.5) return '#faad14';
    return '#ff4d4f';
  };

  const getSuggestionIcon = (suggestion: NodeSuggestion | EdgeSuggestion) => {
    if (isNodeSuggestion(suggestion)) {
      switch (suggestion.type) {
        case 'start':
          return <BulbOutlined style={{ color: '#52c41a' }} />;
        case 'end':
          return <CheckCircleOutlined style={{ color: '#722ed1' }} />;
        case 'processor':
          return <RobotOutlined style={{ color: '#1890ff' }} />;
        default:
          return <BulbOutlined />;
      }
    } else {
      return <LinkOutlined style={{ color: '#faad14' }} />;
    }
  };

  return (
    <div
      ref={ref}
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y + 20,
        zIndex: 2000,
        backgroundColor: 'white',
        border: '1px solid #d9d9d9',
        borderRadius: '8px',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.15)',
        minWidth: '300px',
        maxWidth: '450px',
        maxHeight: '300px',
        overflow: 'hidden'
      }}
    >
      {/* 头部 */}
      <div style={{
        padding: '8px 12px',
        backgroundColor: '#f5f5f5',
        borderBottom: '1px solid #e8e8e8',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <span style={{ fontSize: '12px', color: '#666', fontWeight: 'bold' }}>
          <RobotOutlined /> AI智能建议
        </span>
        <div style={{ fontSize: '10px', color: '#999' }}>
          Tab接受 | Esc取消 | ↑↓选择
        </div>
      </div>

      {/* 内容区域 */}
      <div style={{ maxHeight: '240px', overflow: 'auto' }}>
        {isLoading ? (
          <div style={{ padding: '20px', textAlign: 'center' }}>
            <Spin size="small" />
            <div style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
              正在生成智能建议...
            </div>
          </div>
        ) : (
          <List
            size="small"
            dataSource={suggestions}
            renderItem={(suggestion, index) => {
              const isHighlighted = index === highlightedIndex;
              const isNode = isNodeSuggestion(suggestion);

              return (
                <List.Item
                  style={{
                    padding: '8px 12px',
                    backgroundColor: isHighlighted ? '#e6f7ff' : 'transparent',
                    cursor: 'pointer',
                    borderLeft: isHighlighted ? '3px solid #1890ff' : '3px solid transparent',
                    transition: 'all 0.2s ease'
                  }}
                  onClick={() => onAccept(index)}
                  onMouseEnter={() => {
                    // 鼠标悬停时也更新高亮状态
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', width: '100%' }}>
                    {/* 图标 */}
                    <div style={{ marginRight: '8px', marginTop: '2px' }}>
                      {getSuggestionIcon(suggestion)}
                    </div>

                    {/* 主要内容 */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        marginBottom: '4px'
                      }}>
                        <span style={{
                          fontWeight: 'bold',
                          fontSize: '13px',
                          marginRight: '8px'
                        }}>
                          {isNode ? suggestion.name : `连接到 ${suggestion.target_node_name}`}
                        </span>

                        <Tag
                          color={getConfidenceColor(suggestion.confidence)}
                          style={{ fontSize: '10px' }}
                        >
                          {Math.round(suggestion.confidence * 100)}%
                        </Tag>
                      </div>

                      {/* 类型信息 */}
                      <div style={{ marginBottom: '4px' }}>
                        {isNode ? (
                          <Tag color="blue">
                            {suggestion.type === 'start' ? '开始节点' :
                             suggestion.type === 'end' ? '结束节点' : '处理节点'}
                          </Tag>
                        ) : (
                          <Tag color="orange">
                            {suggestion.connection_type === 'conditional' ? '条件连接' :
                             suggestion.connection_type === 'parallel' ? '并行连接' : '普通连接'}
                          </Tag>
                        )}
                      </div>

                      {/* 描述 */}
                      {((isNode && suggestion.description) || (!isNode && suggestion.reasoning)) && (
                        <div style={{
                          fontSize: '11px',
                          color: '#666',
                          lineHeight: '1.4',
                          marginBottom: '2px'
                        }}>
                          {isNode ? suggestion.description : suggestion.reasoning}
                        </div>
                      )}

                      {/* 建议理由 */}
                      {suggestion.reasoning && (
                        <Tooltip title={suggestion.reasoning}>
                          <div style={{
                            fontSize: '10px',
                            color: '#999',
                            fontStyle: 'italic',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap'
                          }}>
                            💡 {suggestion.reasoning}
                          </div>
                        </Tooltip>
                      )}
                    </div>

                    {/* 快捷键提示 */}
                    {isHighlighted && (
                      <div style={{
                        fontSize: '10px',
                        color: '#1890ff',
                        fontWeight: 'bold',
                        marginLeft: '8px'
                      }}>
                        Tab
                      </div>
                    )}
                  </div>
                </List.Item>
              );
            }}
          />
        )}
      </div>

      {/* 底部提示 */}
      {!isLoading && suggestions.length > 0 && (
        <div style={{
          padding: '6px 12px',
          backgroundColor: '#fafafa',
          borderTop: '1px solid #e8e8e8',
          fontSize: '10px',
          color: '#999',
          textAlign: 'center'
        }}>
          共 {suggestions.length} 个建议 | 基于AI智能分析生成
        </div>
      )}
    </div>
  );
});

TabSuggestionBox.displayName = 'TabSuggestionBox';

export default TabSuggestionBox;