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
  Panel,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Button, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

const ReactFlowTest: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([
    {
      id: '1',
      type: 'default',
      position: { x: 100, y: 100 },
      data: { label: '开始节点' },
    },
    {
      id: '2',
      type: 'default',
      position: { x: 300, y: 100 },
      data: { label: '处理器节点' },
    },
  ]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([
    { id: 'e1-2', source: '1', target: '2' },
  ]);

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges]
  );

  const addNode = () => {
    const newNode: Node = {
      id: `node_${Date.now()}`,
      type: 'default',
      position: { x: Math.random() * 400, y: Math.random() * 300 },
      data: { label: `节点 ${nodes.length + 1}` },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  return (
    <div style={{ width: '100%', height: '500px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
      >
        <Controls />
        <Background />
        <MiniMap />
        <Panel position="top-left">
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={addNode}>
              添加节点
            </Button>
          </Space>
        </Panel>
      </ReactFlow>
    </div>
  );
};

const ReactFlowTestWrapper: React.FC = () => {
  return (
    <ReactFlowProvider>
      <ReactFlowTest />
    </ReactFlowProvider>
  );
};

export default ReactFlowTestWrapper; 