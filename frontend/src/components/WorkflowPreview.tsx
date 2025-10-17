import React, { useState, useCallback, useEffect, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  NodeTypes,
  ReactFlowProvider,
  Controls,
  Background,
  MiniMap,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card, Tag, Tooltip, Badge } from 'antd';
import {
  UserOutlined,
  RobotOutlined,
  SettingOutlined,
  NodeIndexOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  PlayCircleOutlined,
  StopOutlined
} from '@ant-design/icons';

// 工作流导出数据类型定义
interface WorkflowExport {
  name: string;
  description?: string;
  export_version: string;
  export_timestamp: string;
  nodes: any[];
  connections: any[];
  metadata?: Record<string, any>;
}

// 只读自定义节点类型（完全复制设计器的样式逻辑）
const ReadOnlyNode = ({ data }: { data: any }) => {
  // 根据processor类型获取颜色（与设计器一致）
  const getProcessorColor = (processorType: string) => {
    switch (processorType) {
      case 'human':
        return '#faad14'; // 橙色
      case 'agent':
        return '#1890ff'; // 蓝色
      case 'workflow':
        return '#52c41a'; // 绿色
      default:
        return '#d9d9d9'; // 灰色
    }
  };

  // 根据节点类型获取颜色（与设计器一致）
  const getNodeColor = (type: string, processorInfo?: any, status?: string) => {
    if (type === 'start') return '#52c41a';
    if (type === 'end') return '#722ed1';

    if (type === 'processor' && processorInfo) {
      return getProcessorColor(processorInfo.type);
    }

    if (type === 'processor') return '#CCCCCC';

    switch (status) {
      case 'completed':
        return '#52c41a';
      case 'running':
        return '#1890ff';
      case 'failed':
        return '#ff4d4f';
      case 'pending':
        return '#faad14';
      default:
        return '#d9d9d9';
    }
  };

  // 根据节点类型获取背景色（与设计器一致）
  const getNodeBackground = (type: string, processorInfo?: any, status?: string) => {
    if (type === 'start') return '#f6ffed';
    if (type === 'end') return '#f9f0ff';

    if (type === 'processor' && processorInfo) {
      switch (processorInfo.type) {
        case 'human':
          return '#fffbe6'; // 浅黄色背景 - 人工处理器
        case 'agent':
          return '#e6f7ff'; // 浅蓝色背景 - Agent处理器
        default:
          return '#CCCCCC'; // 浅灰色背景 - 未知处理器类型
      }
    }

    if (type === 'processor') {
      return '#fafafa'; // 浅灰色背景 - 未填充处理器
    }

    switch (status) {
      case 'completed':
        return '#f6ffed';
      case 'running':
        return '#e6f7ff';
      case 'failed':
        return '#fff2f0';
      case 'pending':
        return '#fffbe6';
      default:
        return '#fafafa';
    }
  };

  // 根据节点类型获取图标（与设计器一致）
  const getNodeIcon = (type: string, processorInfo?: any) => {
    if (type === 'start') return <PlayCircleOutlined />;
    if (type === 'end') return <StopOutlined />;

    if (type === 'processor' && processorInfo) {
      switch (processorInfo.type) {
        case 'human':
          return <UserOutlined />;
        case 'agent':
          return <RobotOutlined />;
        default:
          return <SettingOutlined />;
      }
    }

    return <NodeIndexOutlined />;
  };

  // 根据节点类型获取类型文本（与设计器一致）
  const getNodeTypeText = (type: string) => {
    switch (type) {
      case 'start':
        return '开始节点';
      case 'processor':
        return '处理节点';
      case 'end':
        return '结束节点';
      default:
        return type;
    }
  };

  const nodeType = data.type || 'processor';
  const processorInfo = data.processor_type ? { type: data.processor_type } : null;
  const nodeColor = getNodeColor(nodeType, processorInfo, data.status);
  const nodeBackground = getNodeBackground(nodeType, processorInfo, data.status);
  const nodeIcon = getNodeIcon(nodeType, processorInfo);
  const nodeTypeText = getNodeTypeText(nodeType);

  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '8px',
        border: `2px solid ${nodeColor}`,
        backgroundColor: nodeBackground,
        minWidth: '160px',
        textAlign: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        transition: 'all 0.3s ease',
        position: 'relative',
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: nodeColor }}
      />

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{
          color: nodeColor,
          fontSize: '20px',
          marginBottom: '8px'
        }}>
          {nodeIcon}
        </div>

        <div style={{
          fontWeight: 'bold',
          fontSize: '14px',
          marginBottom: '4px',
          color: '#262626',
          wordBreak: 'break-word'
        }}>
          {data.label || data.name || `节点 ${data.id}`}
        </div>

        <div style={{
          fontSize: '12px',
          color: '#8c8c8c',
          marginBottom: '8px'
        }}>
          {nodeTypeText}
        </div>

        {data.task_description && (
          <div style={{
            fontSize: '12px',
            color: '#595959',
            marginBottom: '8px',
            wordBreak: 'break-word',
            maxWidth: '140px',
            lineHeight: '1.4'
          }}>
            {data.task_description}
          </div>
        )}

        {processorInfo && (
          <Tag
            color={nodeColor}
            style={{
              fontSize: '11px',
              border: 'none',
              marginTop: '4px'
            }}
          >
            {processorInfo.type}
          </Tag>
        )}

        {data.status && (
          <Badge
            status={
              data.status === 'completed' ? 'success' :
              data.status === 'running' ? 'processing' :
              data.status === 'failed' ? 'error' :
              'default'
            }
            text={
              <span style={{ fontSize: '11px', color: '#8c8c8c' }}>
                {data.status}
              </span>
            }
            style={{ marginTop: '4px' }}
          />
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: nodeColor }}
      />
    </div>
  );
};

// 节点类型定义
const nodeTypes: NodeTypes = {
  custom: ReadOnlyNode,
};

interface WorkflowPreviewProps {
  workflowData: WorkflowExport;
  height?: string | number;
  showStats?: boolean;
}

const WorkflowPreview: React.FC<WorkflowPreviewProps> = ({
  workflowData,
  height = '400px',
  showStats = true
}) => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  // 转换工作流数据为ReactFlow格式
  useEffect(() => {
    if (!workflowData) return;

    // 转换节点
    const flowNodes: Node[] = (workflowData.nodes || []).map((node: any) => ({
      id: node.node_id || node.id || `node-${Math.random()}`,
      type: 'custom',
      position: {
        x: node.position_x || Math.random() * 300,
        y: node.position_y || Math.random() * 300
      },
      data: {
        id: node.node_id || node.id,
        label: node.name || node.node_name || '未命名节点',
        name: node.name || node.node_name || '未命名节点',
        description: node.description,
        task_description: node.task_description,
        type: node.type || 'processor',
        processor_type: node.processor_type || 'unknown',
        processor_id: node.processor_id,
        status: node.status,
        ...node
      },
    }));

    // 创建节点名称到ID的映射，用于连接转换
    const nodeNameToId: Record<string, string> = {};
    flowNodes.forEach(node => {
      const nodeName = node.data.name || node.data.label;
      if (nodeName) {
        nodeNameToId[nodeName] = node.id;
      }
    });

    // 转换连接为边
    const flowEdges: Edge[] = (workflowData.connections || []).map((conn: any) => {
      // 导出数据使用 from_node_name 和 to_node_name，需要转换为 node id
      const sourceId = nodeNameToId[conn.from_node_name] || conn.source_node_id || conn.from_node_id;
      const targetId = nodeNameToId[conn.to_node_name] || conn.target_node_id || conn.to_node_id;

      return {
        id: conn.connection_id || conn.id || `edge-${Math.random()}`,
        source: sourceId,
        target: targetId,
        type: 'smoothstep',
        animated: false,
        style: {
          strokeWidth: 2,
          stroke: '#1890ff'
        },
        label: conn.condition_description || conn.name || '',
        labelStyle: {
          fontSize: 12,
          fontWeight: 'bold',
          fill: '#262626'
        },
        labelBgStyle: {
          fill: 'white',
          fillOpacity: 0.8,
          stroke: '#d9d9d9',
          strokeWidth: 1,
          rx: 4,
          ry: 4
        }
      };
    }).filter(edge => edge.source && edge.target); // 过滤掉无效的连接

    console.log('🔍 Preview Debug Info:');
    console.log('- 原始节点数量:', workflowData.nodes?.length || 0);
    console.log('- 转换后节点数量:', flowNodes.length);
    console.log('- 原始连接数量:', workflowData.connections?.length || 0);
    console.log('- 转换后边数量:', flowEdges.length);
    console.log('- 节点名称映射:', nodeNameToId);

    if (workflowData.connections?.length > 0) {
      console.log('- 连接详情:', workflowData.connections.map(conn => ({
        from: conn.from_node_name,
        to: conn.to_node_name,
        description: conn.condition_description
      })));
    }

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [workflowData]);

  // 计算统计信息
  const stats = useMemo(() => {
    const nodeCount = nodes.length;
    const edgeCount = edges.length;
    const nodeTypes = nodes.reduce((acc: Record<string, number>, node) => {
      const type = node.data.processor_type || 'unknown';
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    }, {});

    return { nodeCount, edgeCount, nodeTypes };
  }, [nodes, edges]);

  return (
    <div style={{ width: '100%' }}>
      {showStats && (
        <Card
          size="small"
          style={{ marginBottom: '16px' }}
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <NodeIndexOutlined />
              工作流结构
            </div>
          }
        >
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            <Tooltip title="节点总数">
              <Tag icon={<NodeIndexOutlined />} color="blue">
                {stats.nodeCount} 个节点
              </Tag>
            </Tooltip>
            <Tooltip title="连接总数">
              <Tag icon={<BranchesOutlined />} color="green">
                {stats.edgeCount} 个连接
              </Tag>
            </Tooltip>
            {Object.entries(stats.nodeTypes).map(([type, count]) => (
              <Tag
                key={type}
                icon={type === 'human' ? <UserOutlined /> :
                      type === 'agent' ? <RobotOutlined /> :
                      <SettingOutlined />}
                color={type === 'human' ? 'orange' :
                       type === 'agent' ? 'blue' :
                       'default'}
              >
                {count} {type}
              </Tag>
            ))}
          </div>
        </Card>
      )}

      <div style={{
        height,
        width: '100%',
        border: '1px solid #d9d9d9',
        borderRadius: '6px',
        backgroundColor: '#fafafa'
      }}>
        <ReactFlowProvider>
          <ReactFlow
            style={{ width: '100%', height: '100%' }}
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.1, minZoom: 0.3, maxZoom: 1.5 }}
            attributionPosition="bottom-left"
            proOptions={{ hideAttribution: true }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={true}
            selectNodesOnDrag={false}
            defaultEdgeOptions={{
              type: 'smoothstep',
              animated: false,
              style: { strokeWidth: 2 }
            }}
          >
            <Controls showInteractive={false} />
            <Background />
            <MiniMap
              nodeColor={(node) => {
                const type = node.data?.processor_type || 'unknown';
                switch (type) {
                  case 'human': return '#faad14';
                  case 'agent': return '#1890ff';
                  case 'workflow': return '#52c41a';
                  default: return '#d9d9d9';
                }
              }}
              maskColor="rgba(255, 255, 255, 0.2)"
            />
          </ReactFlow>
        </ReactFlowProvider>
      </div>

      {nodes.length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '32px',
          color: '#999',
          backgroundColor: '#fafafa',
          border: '1px dashed #d9d9d9',
          borderRadius: '6px'
        }}>
          <ExclamationCircleOutlined style={{ fontSize: '24px', marginBottom: '8px' }} />
          <div>暂无工作流数据</div>
        </div>
      )}
    </div>
  );
};

export default WorkflowPreview;