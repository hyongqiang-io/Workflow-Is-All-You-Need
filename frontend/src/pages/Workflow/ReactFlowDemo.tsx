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
  Panel,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Button, Modal, Form, Input, Select, message, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

const { Option } = Select;

// 自定义节点类型
const CustomNode = ({ data }: { data: any }) => {
  const nodeStyle = {
    padding: '10px',
    borderRadius: '8px',
    border: '2px solid #d9d9d9',
    backgroundColor: '#fff',
    minWidth: '150px',
    textAlign: 'center' as const,
  };

  const getNodeColor = (type: string) => {
    switch (type) {
      case 'start':
        return '#52c41a';
      case 'end':
        return '#ff4d4f';
      case 'processor':
        return '#1890ff';
      default:
        return '#d9d9d9';
    }
  };

  return (
    <div style={{ ...nodeStyle, borderColor: getNodeColor(data.type) }}>
      <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>{data.label}</div>
      <div style={{ fontSize: '12px', color: '#666' }}>{data.type}</div>
      {data.description && (
        <div style={{ fontSize: '10px', color: '#999', marginTop: '5px' }}>
          {data.description}
        </div>
      )}
    </div>
  );
};

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

const ReactFlowDemo: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [addNodeModalVisible, setAddNodeModalVisible] = useState(false);
  const [nodeForm] = Form.useForm();
  const { fitView } = useReactFlow();

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges]
  );

  const handleAddNode = () => {
    nodeForm.resetFields();
    setAddNodeModalVisible(true);
  };

  const handleNodeSubmit = async (values: any) => {
    try {
      const newNode: Node = {
        id: `node_${Date.now()}`,
        type: 'custom',
        position: { x: Math.random() * 400, y: Math.random() * 300 },
        data: {
          label: values.name,
          type: values.type,
          description: values.description,
        },
      };
      
      setNodes((nds) => [...nds, newNode]);
      
      // 延迟触发视图适配
      setTimeout(() => {
        fitView({ padding: 0.1, includeHiddenNodes: false });
      }, 100);
      
      message.success('节点添加成功');
      setAddNodeModalVisible(false);
      nodeForm.resetFields();
    } catch (error) {
      console.error('添加节点失败:', error);
      message.error('添加节点失败');
    }
  };

  return (
    <div style={{ width: '100%', height: '600px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
      >
        <Controls />
        <Background />
        <MiniMap />
        <Panel position="top-left">
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleAddNode}
            >
              添加节点
            </Button>
          </Space>
        </Panel>
      </ReactFlow>

      {/* 添加节点模态框 */}
      <Modal
        title="添加节点"
        open={addNodeModalVisible}
        onOk={() => nodeForm.submit()}
        onCancel={() => setAddNodeModalVisible(false)}
        destroyOnClose
      >
        <Form form={nodeForm} onFinish={handleNodeSubmit} layout="vertical">
          <Form.Item
            name="name"
            label="节点名称"
            rules={[{ required: true, message: '请输入节点名称' }]}
          >
            <Input placeholder="请输入节点名称" />
          </Form.Item>
          <Form.Item
            name="type"
            label="节点类型"
            rules={[{ required: true, message: '请选择节点类型' }]}
          >
            <Select placeholder="请选择节点类型">
              <Option value="start">开始节点</Option>
              <Option value="processor">处理器节点</Option>
              <Option value="end">结束节点</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="description"
            label="节点描述"
          >
            <Input.TextArea placeholder="请输入节点描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// 包装组件以提供ReactFlowProvider
const ReactFlowDemoWrapper: React.FC = () => {
  return (
    <div style={{ padding: '24px' }}>
      <h2>React Flow 演示</h2>
      <p>这是一个简单的React Flow演示，用于测试节点添加和显示功能。</p>
      <ReactFlowProvider>
        <ReactFlowDemo />
      </ReactFlowProvider>
    </div>
  );
};

export default ReactFlowDemoWrapper; 