/**
 * 幽灵连接组件
 * 显示Tab补全建议的半透明连接线，类似Cursor的ghost text效果
 */

import React from 'react';
import { getBezierPath, EdgeProps } from 'reactflow';
import { EdgeSuggestion } from '../services/workflowTabContext';

interface GhostEdgeProps extends Partial<EdgeProps> {
  suggestion: EdgeSuggestion;
  isHighlighted?: boolean;
  onAccept?: () => void;
  onReject?: () => void;
}

const GhostEdge: React.FC<GhostEdgeProps> = ({
  suggestion,
  isHighlighted = false,
  onAccept,
  onReject,
  sourceX = 0,
  sourceY = 0,
  targetX = 100,
  targetY = 100,
  sourcePosition,
  targetPosition,
}) => {
  // 根据连接类型确定样式
  const getEdgeStyle = (connectionType: string) => {
    switch (connectionType) {
      case 'conditional':
        return {
          stroke: '#faad14',
          strokeDasharray: '8,4',
          strokeWidth: 2,
        };
      case 'parallel':
        return {
          stroke: '#722ed1',
          strokeDasharray: '4,2',
          strokeWidth: 2,
        };
      default:
        return {
          stroke: '#1890ff',
          strokeDasharray: 'none',
          strokeWidth: 2,
        };
    }
  };

  const edgeStyle = getEdgeStyle(suggestion.connection_type);

  // 计算贝塞尔曲线路径
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <g className="ghost-edge">
      {/* 主连接线 */}
      <path
        d={edgePath}
        fill="none"
        style={{
          ...edgeStyle,
          opacity: isHighlighted ? 0.8 : 0.4, // Cursor风格的半透明
          transition: 'all 0.3s ease',
          cursor: 'pointer',
        }}
        strokeLinecap="round"
        onClick={onAccept}
      />

      {/* 高亮效果 */}
      {isHighlighted && (
        <path
          d={edgePath}
          fill="none"
          stroke={edgeStyle.stroke}
          strokeWidth={edgeStyle.strokeWidth + 2}
          opacity={0.2}
          strokeLinecap="round"
        />
      )}

      {/* AI建议标记 */}
      <g transform={`translate(${labelX - 15}, ${labelY - 15})`}>
        <circle
          cx="15"
          cy="15"
          r="12"
          fill="#1890ff"
          opacity={isHighlighted ? 0.9 : 0.6}
          stroke="white"
          strokeWidth="2"
        />
        <text
          x="15"
          y="19"
          textAnchor="middle"
          fontSize="8"
          fill="white"
          fontWeight="bold"
        >
          AI
        </text>
      </g>

      {/* 置信度指示器 */}
      <g transform={`translate(${labelX + 20}, ${labelY - 10})`}>
        <rect
          x="0"
          y="0"
          width="30"
          height="16"
          rx="8"
          fill="rgba(255, 255, 255, 0.9)"
          stroke={edgeStyle.stroke}
          strokeWidth="1"
          opacity={isHighlighted ? 1 : 0.7}
        />
        <text
          x="15"
          y="11"
          textAnchor="middle"
          fontSize="9"
          fill={edgeStyle.stroke}
          fontWeight="bold"
        >
          {Math.round(suggestion.confidence * 100)}%
        </text>
      </g>

      {/* 连接类型标签 */}
      {suggestion.connection_type !== 'normal' && (
        <g transform={`translate(${labelX - 25}, ${labelY + 20})`}>
          <rect
            x="0"
            y="0"
            width="50"
            height="14"
            rx="7"
            fill="rgba(0, 0, 0, 0.8)"
            opacity={isHighlighted ? 1 : 0.6}
          />
          <text
            x="25"
            y="10"
            textAnchor="middle"
            fontSize="8"
            fill="white"
          >
            {suggestion.connection_type === 'conditional' ? '条件' : '并行'}
          </text>
        </g>
      )}

      {/* 操作提示 */}
      {isHighlighted && (
        <g transform={`translate(${labelX - 40}, ${labelY + 40})`}>
          <rect
            x="0"
            y="0"
            width="80"
            height="18"
            rx="9"
            fill="rgba(0, 0, 0, 0.8)"
          />
          <text
            x="40"
            y="12"
            textAnchor="middle"
            fontSize="9"
            fill="white"
          >
            Tab接受 | Esc忽略
          </text>
        </g>
      )}

      {/* 箭头 */}
      <defs>
        <marker
          id={`ghost-arrow-${suggestion.id}`}
          markerWidth="10"
          markerHeight="10"
          refX="9"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M0,0 L0,6 L9,3 z"
            fill={edgeStyle.stroke}
            opacity={isHighlighted ? 0.8 : 0.4}
          />
        </marker>
      </defs>

      <path
        d={edgePath}
        fill="none"
        style={{
          ...edgeStyle,
          opacity: 0,
          strokeWidth: 1
        }}
        markerEnd={`url(#ghost-arrow-${suggestion.id})`}
      />
    </g>
  );
};

export default GhostEdge;