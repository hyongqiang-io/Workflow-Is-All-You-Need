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
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Button, Modal, Form, Input, Select, message, Space, Card, Typography } from 'antd';
import { PlusOutlined, SaveOutlined, DeleteOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

// 自定义节点组件
const CustomNode = ({ data }: { data: any }) => {
  const nodeStyle = {
    padding: '15px',
    borderRadius: '10px',
    border: '3px solid',
    backgroundColor: '#fff',
    minWidth: '180px',
    textAlign: 'center' as const,
    boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
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

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'start':
        return '▶️';
      case 'end':
        return '⏹️';
      case 'processor':
        return '⚙️';
      default:
        return '📋';
    }
  };

  return (
    <div style={{ ...nodeStyle, borderColor: getNodeColor(data.type) }}>
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      <div style={{ fontSize: '24px', marginBottom: '8px' }}>
        {getNodeIcon(data.type)}
      </div>
      <div style={{ fontWeight: 'bold', marginBottom: '5px', fontSize: '14px' }}>
        {data.label}
      </div>
      <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
        {data.type.toUpperCase()}
      </div>
      {data.description && (
        <div style={{ fontSize: '10px', color: '#999', lineHeight: '1.3' }}>
          {data.description}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

const ReactFlowExample: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([
    {
      id: 'start-1',
      type: 'custom',
      position: { x: 250, y: 50 },
      data: { 
        label: '开始', 
        type: 'start', 
        description: '工作流开始节点' 
      },
    },
  ]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [addNodeModalVisible, setAddNodeModalVisible] = useState(false);
  const [nodeForm] = Form.useForm();

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

  const handleNodeSubmit = (values: any) => {
    const newNode: Node = {
      id: `node-${Date.now()}`,
      type: 'custom',
      position: { 
        x: Math.random() * 400 + 100, 
        y: Math.random() * 300 + 100 
      },
      data: {
        label: values.name,
        type: values.type,
        description: values.description,
      },
    };
    setNodes((nds) => [...nds, newNode]);
    setAddNodeModalVisible(false);
    message.success('节点添加成功！');
  };

  const handleDeleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((node) => node.id !== nodeId));
    setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
    message.success('节点删除成功！');
  };

  const onNodeContextMenu = useCallback((event: any, node: Node) => {
    event.preventDefault();
    handleDeleteNode(node.id);
  }, []);

  const handleSaveWorkflow = () => {
    const workflowData = {
      nodes: nodes.map(node => ({
        id: node.id,
        type: node.data.type,
        name: node.data.label,
        description: node.data.description,
        position: node.position,
      })),
      edges: edges.map(edge => ({
        source: edge.source,
        target: edge.target,
      })),
    };
    
    console.log('保存工作流数据:', workflowData);
    message.success('工作流数据已保存到控制台！');
  };

  return (
    <div style={{ padding: '20px' }}>
      <Card>
        <Title level={3}>React Flow 手动添加节点示例</Title>
        <Text type="secondary">
          这是一个演示如何使用 React Flow 手动添加节点的示例。
          您可以点击"添加节点"按钮来创建新节点，拖拽节点进行连接，右键删除节点。
        </Text>
      </Card>

      <Card style={{ marginTop: '16px', height: '600px' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          onNodeContextMenu={onNodeContextMenu}
          fitView
          style={{ background: '#f5f5f5' }}
        >
          <Controls />
          <Background color="#aaa" gap={16} />
          <MiniMap 
            style={{ background: '#fff' }}
            nodeColor={(node) => {
              switch (node.data?.type) {
                case 'start': return '#52c41a';
                case 'end': return '#ff4d4f';
                case 'processor': return '#1890ff';
                default: return '#d9d9d9';
              }
            }}
          />
          <Panel position="top-left">
            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleAddNode}
              >
                添加节点
              </Button>
              <Button
                icon={<SaveOutlined />}
                onClick={handleSaveWorkflow}
              >
                保存工作流
              </Button>
            </Space>
          </Panel>
        </ReactFlow>
      </Card>

      {/* 添加节点模态框 */}
      <Modal
        title="添加新节点"
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
            <Input placeholder="例如：数据处理、用户审核" />
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
            label="任务描述"
          >
            <Input.TextArea 
              placeholder="描述这个节点的功能和作用" 
              rows={3} 
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 使用说明 */}
      <Card style={{ marginTop: '16px' }}>
        <Title level={4}>使用说明</Title>
        <ul>
          <li><strong>添加节点</strong>: 点击"添加节点"按钮，填写节点信息</li>
          <li><strong>连接节点</strong>: 从一个节点的底部拖拽到另一个节点的顶部</li>
          <li><strong>移动节点</strong>: 直接拖拽节点到新位置</li>
          <li><strong>删除节点</strong>: 右键点击节点删除</li>
          <li><strong>缩放和平移</strong>: 使用右下角的控制面板</li>
          <li><strong>保存工作流</strong>: 点击"保存工作流"查看数据</li>
        </ul>
      </Card>
    </div>
  );
};

const ReactFlowExampleWrapper: React.FC = () => {
  return (
    <ReactFlowProvider>
      <ReactFlowExample />
    </ReactFlowProvider>
  );
};

export default ReactFlowExampleWrapper; 