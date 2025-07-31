import React, { useState, useCallback } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  NodeTypes,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Button, Card, Space, message } from 'antd';

// 简单的测试节点
const TestNode = ({ data }: { data: any }) => {
  return (
    <div
      style={{
        padding: '10px',
        borderRadius: '8px',
        border: '2px solid #1890ff',
        backgroundColor: '#fff',
        minWidth: '120px',
        textAlign: 'center',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      }}
    >
      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
        {data.label}
      </div>
      <div style={{ fontSize: '12px', color: '#666' }}>
        {data.type}
      </div>
    </div>
  );
};

const nodeTypes: NodeTypes = {
  test: TestNode,
};

// 初始测试数据
const initialNodes: Node[] = [
  {
    id: '1',
    type: 'test',
    position: { x: 100, y: 100 },
    data: { label: '测试节点1', type: 'start' },
  },
  {
    id: '2',
    type: 'test',
    position: { x: 300, y: 100 },
    data: { label: '测试节点2', type: 'processor' },
  },
  {
    id: '3',
    type: 'test',
    position: { x: 500, y: 100 },
    data: { label: '测试节点3', type: 'end' },
  },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', type: 'smoothstep' },
  { id: 'e2-3', source: '2', target: '3', type: 'smoothstep' },
];

const ReactFlowDebug: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const addTestNode = () => {
    const newNode: Node = {
      id: `${nodes.length + 1}`,
      type: 'test',
      position: { 
        x: Math.random() * 400 + 100, 
        y: Math.random() * 300 + 100 
      },
      data: { 
        label: `测试节点${nodes.length + 1}`, 
        type: 'processor' 
      },
    };
    
    setNodes((nds) => [...nds, newNode]);
    message.success('添加测试节点成功');
  };

  const clearNodes = () => {
    setNodes([]);
    setEdges([]);
    message.info('已清空所有节点');
  };

  const resetNodes = () => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    message.info('已重置为初始状态');
  };

  return (
    <Card title="🔧 ReactFlow 调试工具" style={{ margin: '20px' }}>
      <Space style={{ marginBottom: '16px' }}>
        <Button type="primary" onClick={addTestNode}>
          添加测试节点
        </Button>
        <Button onClick={resetNodes}>
          重置节点
        </Button>
        <Button danger onClick={clearNodes}>
          清空节点
        </Button>
      </Space>
      
      <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
        当前节点数: {nodes.length} | 当前连线数: {edges.length}
      </div>
      
      <div style={{ height: '400px', width: '100%', border: '1px solid #d9d9d9' }}>
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-right"
          >
            <Controls />
            <Background color="#f5f5f5" gap={16} />
            <MiniMap />
          </ReactFlow>
        </ReactFlowProvider>
      </div>
      
      <div style={{ marginTop: '16px', fontSize: '12px', color: '#999' }}>
        如果上面的区域是空白的，说明ReactFlow存在问题。
        如果可以看到节点和网格，说明ReactFlow正常工作。
      </div>
    </Card>
  );
};

export default ReactFlowDebug;