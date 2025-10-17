/**
 * 幽灵节点组件
 * 显示Tab补全建议的半透明节点，类似Cursor的ghost text效果
 */

import React from 'react';
import { Handle, Position } from 'reactflow';
import { Tag, Tooltip } from 'antd';
import { BulbOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';
import { NodeSuggestion } from '../services/workflowTabContext';

interface GhostNodeProps {
  suggestion: NodeSuggestion;
  isHighlighted?: boolean;
  onAccept?: () => void;
  onReject?: () => void;
}

const GhostNode: React.FC<GhostNodeProps> = ({
  suggestion,
  isHighlighted = false,
  onAccept,
  onReject
}) => {
  const getNodeColor = (type: string) => {
    switch (type) {
      case 'start':
        return '#52c41a';
      case 'end':
        return '#722ed1';
      case 'processor':
        return '#1890ff';
      default:
        return '#d9d9d9';
    }
  };

  const getNodeBackground = (type: string) => {
    switch (type) {
      case 'start':
        return '#f6ffed';
      case 'end':
        return '#f9f0ff';
      case 'processor':
        return '#e6f7ff';
      default:
        return '#fafafa';
    }
  };

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'start':
        return <BulbOutlined />;
      case 'end':
        return <BulbOutlined />;
      case 'processor':
        return <RobotOutlined />;
      default:
        return <UserOutlined />;
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return '#52c41a';
    if (confidence >= 0.5) return '#faad14';
    return '#ff4d4f';
  };

  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '8px',
        border: `2px dashed ${getNodeColor(suggestion.type)}`,
        backgroundColor: getNodeBackground(suggestion.type),
        minWidth: '160px',
        textAlign: 'center',
        opacity: isHighlighted ? 0.9 : 0.5, // Cursor风格的半透明效果
        transition: 'all 0.3s ease',
        cursor: 'pointer',
        position: 'relative',
        boxShadow: isHighlighted
          ? '0 4px 12px rgba(24, 144, 255, 0.3)'
          : '0 2px 8px rgba(0,0,0,0.1)',
        transform: isHighlighted ? 'scale(1.02)' : 'scale(1)',
      }}
      className="ghost-node"
      onClick={onAccept}
      onKeyDown={(e) => {
        if (e.key === 'Tab') {
          e.preventDefault();
          onAccept?.();
        } else if (e.key === 'Escape') {
          e.preventDefault();
          onReject?.();
        }
      }}
      tabIndex={0}
    >
      {/* 建议标记 */}
      <div
        style={{
          position: 'absolute',
          top: '-8px',
          right: '-8px',
          backgroundColor: '#1890ff',
          color: 'white',
          borderRadius: '50%',
          width: '20px',
          height: '20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '10px',
          fontWeight: 'bold'
        }}
      >
        AI
      </div>

      {/* 节点图标和标题 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '6px' }}>
        <span style={{ marginRight: '6px', fontSize: '14px' }}>
          {getNodeIcon(suggestion.type)}
        </span>
        <div style={{ fontWeight: 'bold', fontSize: '14px' }}>
          {suggestion.name}
        </div>
      </div>

      {/* 节点类型 */}
      <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
        {suggestion.type === 'start' ? '开始节点' :
         suggestion.type === 'end' ? '结束节点' : '处理节点'}
      </div>

      {/* 描述 */}
      {suggestion.description && (
        <div style={{ fontSize: '11px', color: '#999', marginBottom: '8px' }}>
          {suggestion.description}
        </div>
      )}

      {/* 置信度和操作提示 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Tooltip title={`置信度: ${(suggestion.confidence * 100).toFixed(0)}%`}>
          <Tag
            color={getConfidenceColor(suggestion.confidence)}
            style={{ margin: 0, fontSize: '10px' }}
          >
            {(suggestion.confidence * 100).toFixed(0)}%
          </Tag>
        </Tooltip>

        <div style={{ fontSize: '10px', color: '#999' }}>
          Tab接受 | Esc忽略
        </div>
      </div>

      {/* 建议理由 */}
      {suggestion.reasoning && (
        <Tooltip title={suggestion.reasoning}>
          <div style={{
            fontSize: '10px',
            color: '#666',
            marginTop: '4px',
            fontStyle: 'italic',
            maxWidth: '140px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}>
            💡 {suggestion.reasoning}
          </div>
        </Tooltip>
      )}

      {/* 连接点 */}
      {suggestion.type !== 'start' && (
        <Handle
          type="target"
          position={Position.Left}
          id={`${suggestion.id}-target`}
          style={{
            background: '#555',
            width: '8px',
            height: '8px',
            border: '2px solid #fff',
            opacity: 0.7
          }}
        />
      )}
      {suggestion.type !== 'end' && (
        <Handle
          type="source"
          position={Position.Right}
          id={`${suggestion.id}-source`}
          style={{
            background: '#555',
            width: '8px',
            height: '8px',
            border: '2px solid #fff',
            opacity: 0.7
          }}
        />
      )}
    </div>
  );
};

export default GhostNode;