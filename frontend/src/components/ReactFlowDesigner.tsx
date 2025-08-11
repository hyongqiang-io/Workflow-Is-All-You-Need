import React, { useState, useCallback, useMemo, useEffect } from 'react';
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
  EdgeTypes,
  Panel,
  useReactFlow,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Button, Modal, Form, Input, Select, message, Card, Space, Tooltip } from 'antd';
import { PlusOutlined, SaveOutlined, PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { nodeAPI, processorAPI, executionAPI } from '../services/api';

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

interface ReactFlowDesignerProps {
  workflowId?: string;
  onSave?: (nodes: Node[], edges: Edge[]) => void;
}

const ReactFlowDesigner: React.FC<ReactFlowDesignerProps> = ({ workflowId, onSave }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [processors, setProcessors] = useState<any[]>([]);
  const [addNodeModalVisible, setAddNodeModalVisible] = useState(false);
  const [nodeForm] = Form.useForm();
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [editNodeModalVisible, setEditNodeModalVisible] = useState(false);
  const [loading, setLoading] = useState(false);

  const { getNode, getNodes, getEdges, fitView } = useReactFlow();

  // 加载处理器列表
  useEffect(() => {
    loadProcessors();
  }, []);

  const loadProcessors = async () => {
    try {
      const response = await processorAPI.getAvailableProcessors();
      if (response.data && response.data.processors) {
        setProcessors(response.data.processors);
      }
    } catch (error) {
      console.error('加载处理器失败:', error);
      message.error('加载处理器失败');
    }
  };

  const loadWorkflowData = useCallback(async () => {
    if (!workflowId) return;
    
    try {
      setLoading(true);
      const response = await nodeAPI.getWorkflowNodes(workflowId);
      if (response.data && response.data.nodes) {
        const workflowNodes = response.data.nodes.map((node: any, index: number) => ({
          id: node.node_id,
          type: 'custom',
          position: { x: 100 + index * 200, y: 100 },
          data: {
            label: node.name,
            type: node.type,
            description: node.task_description,
            nodeData: node,
          },
        }));
        setNodes(workflowNodes);
      }
    } catch (error) {
      console.error('加载工作流数据失败:', error);
      message.error('加载工作流数据失败');
    } finally {
      setLoading(false);
    }
  }, [workflowId, setNodes]);

  // 加载工作流数据
  useEffect(() => {
    if (workflowId) {
      loadWorkflowData();
    }
  }, [workflowId, loadWorkflowData]);

  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) => addEdge(params, eds));
    },
    [setEdges]
  );

  const handleAddNode = () => {
    setSelectedNode(null);
    nodeForm.resetFields();
    setAddNodeModalVisible(true);
  };

  const handleEditNode = (node: Node) => {
    setSelectedNode(node);
    nodeForm.setFieldsValue({
      name: node.data.label,
      type: node.data.type,
      description: node.data.description,
    });
    setEditNodeModalVisible(true);
  };

  const handleDeleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((node) => node.id !== nodeId));
    setEdges((eds) => eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
    message.success('节点删除成功');
  };

  const handleNodeSubmit = async (values: any) => {
    try {
      if (!workflowId) {
        message.error('请先选择工作流');
        return;
      }

      if (selectedNode) {
        // 编辑现有节点
        const updatedNode = {
          ...selectedNode,
          data: {
            ...selectedNode.data,
            label: values.name,
            type: values.type,
            description: values.description,
          },
        };
        setNodes((nds) => nds.map((node) => (node.id === selectedNode.id ? updatedNode : node)));
        message.success('节点更新成功');
      } else {
        // 添加新节点 - 需要保存到后端
        try {
          const nodeData = {
            name: values.name,
            type: values.type,
            workflow_base_id: workflowId,
            task_description: values.description, // 映射字段名
            position_x: Math.floor(Math.random() * 400),
            position_y: Math.floor(Math.random() * 300)
          };
          
          const newNodeResponse: any = await nodeAPI.createNode(nodeData);
          
          const newNode: Node = {
            id: newNodeResponse.data.node.node_id,
            type: 'custom',
            position: { x: nodeData.position_x, y: nodeData.position_y },
            data: {
              label: values.name,
              type: values.type,
              description: values.description,
              nodeData: newNodeResponse.data.node, // 保存后端返回的完整数据
            },
          };
          setNodes((nds) => [...nds, newNode]);
          
          // 延迟触发视图适配，确保节点已添加到DOM
          setTimeout(() => {
            fitView({ padding: 0.1, includeHiddenNodes: false });
          }, 100);
          
          message.success('节点添加成功');
        } catch (error) {
          console.error('创建节点失败:', error);
          message.error('创建节点失败');
          return;
        }
      }

      setAddNodeModalVisible(false);
      setEditNodeModalVisible(false);
      nodeForm.resetFields();
    } catch (error) {
      console.error('保存节点失败:', error);
      message.error('保存节点失败');
    }
  };

  const handleSaveWorkflow = async () => {
    try {
      if (!workflowId) {
        message.error('请先选择工作流');
        return;
      }

      // 保存节点到后端
      for (const node of nodes) {
        if (!node.data.nodeData) {
          // 新节点，需要保存到后端
          await nodeAPI.createNode({
            name: node.data.label,
            type: node.data.type,
            workflow_base_id: workflowId,
            description: node.data.description,
            task_description: node.data.description,
            position_x: node.position.x,
            position_y: node.position.y
          });
        }
      }

      message.success('工作流保存成功');
      if (onSave) {
        onSave(nodes, edges);
      }
    } catch (error) {
      console.error('保存工作流失败:', error);
      message.error('保存工作流失败');
    }
  };

  const handleExecuteWorkflow = async () => {
    try {
      if (!workflowId) {
        message.error('请先选择工作流');
        return;
      }

      const response = await executionAPI.executeWorkflow({
        workflow_base_id: workflowId,
        instance_name: `执行_${Date.now()}`,
        input_data: { test: 'data' },
      });

      if (response.data && response.data.success) {
        message.success('工作流执行成功');
      } else {
        message.error(response.data?.message || '工作流执行失败');
      }
    } catch (error) {
      console.error('执行工作流失败:', error);
      message.error('执行工作流失败');
    }
  };

  const onNodeDoubleClick = useCallback((event: any, node: Node) => {
    handleEditNode(node);
  }, []);

  const onNodeContextMenu = useCallback((event: any, node: Node) => {
    event.preventDefault();
    handleDeleteNode(node.id);
  }, []);

  return (
    <div style={{ width: '100%', height: '600px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        onNodeDoubleClick={onNodeDoubleClick}
        onNodeContextMenu={onNodeContextMenu}
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
            <Button
              icon={<SaveOutlined />}
              onClick={handleSaveWorkflow}
              loading={loading}
            >
              保存工作流
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={handleExecuteWorkflow}
              type="default"
            >
              执行工作流
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
            label="任务描述"
          >
            <Input.TextArea placeholder="请输入任务描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑节点模态框 */}
      <Modal
        title="编辑节点"
        open={editNodeModalVisible}
        onOk={() => nodeForm.submit()}
        onCancel={() => setEditNodeModalVisible(false)}
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
            label="任务描述"
          >
            <Input.TextArea placeholder="请输入任务描述" rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

// 包装组件以提供ReactFlowProvider
const ReactFlowDesignerWrapper: React.FC<ReactFlowDesignerProps> = (props) => {
  return (
    <ReactFlowProvider>
      <ReactFlowDesigner {...props} />
    </ReactFlowProvider>
  );
};

export default ReactFlowDesignerWrapper; 