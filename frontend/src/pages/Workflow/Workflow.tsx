import React, { useState, useEffect } from 'react';
import { Card, Button, Table, Tag, Modal, Form, Input, Select, Space, message, Row, Col, Typography, Empty, Drawer } from 'antd';
import { 
  PlusOutlined, 
  PlayCircleOutlined, 
  EyeOutlined, 
  EditOutlined, 
  DeleteOutlined,
  BranchesOutlined,
  ReloadOutlined,
  ShareAltOutlined,
  HistoryOutlined,
  BugOutlined,
  DatabaseOutlined,
  ApiOutlined,
  ToolOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { workflowAPI, executionAPI, nodeAPI, authAPI } from '../../services/api';
import { useAuthStore } from '../../stores/authStore';
import WorkflowDesigner from '../../components/WorkflowDesigner';
import WorkflowInstanceList from '../../components/WorkflowInstanceList';

const { TextArea } = Input;
const { Option } = Select;
const { Title, Text } = Typography;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
interface WorkflowItem {
  id: string; // workflow_id (版本ID)
  baseId: string; // workflow_base_id (业务ID)
  name: string;
  description: string;
  status: 'draft' | 'active' | 'completed' | 'paused';
  version: number;
  isCurrentVersion: boolean;
  createdBy: string;
  creatorId: string;
  createdAt: string;
  updatedAt: string;
  nodeCount: number;
  executionCount: number;
}

const WorkflowPage: React.FC = () => {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [designerVisible, setDesignerVisible] = useState(false);
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowItem | null>(null);
  const [instanceListVisible, setInstanceListVisible] = useState(false);
  const [createForm] = Form.useForm();

  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    setLoading(true);
    try {
      const response: any = await workflowAPI.getWorkflows();
      
      // 检查响应格式并处理数据
      let workflowsData = [];
      if (response && response.success && response.data) {
        if (Array.isArray(response.data)) {
          workflowsData = response.data;
        } else if (response.data.workflows && Array.isArray(response.data.workflows)) {
          workflowsData = response.data.workflows;
        } else {
          console.warn('工作流数据格式异常:', response.data);
          workflowsData = [];
        }
      } else if (Array.isArray(response)) {
        // 直接返回数组的情况
        workflowsData = response;
      } else {
        console.warn('工作流API响应格式异常:', response);
        workflowsData = [];
      }
      
      // 确保每个工作流对象都有必要的字段，适配后端版本控制
      const processedWorkflows = workflowsData.map((workflow: any) => ({
        id: workflow.workflow_id || '', // 版本ID
        baseId: workflow.workflow_base_id || workflow.workflow_id || '', // 业务ID
        name: workflow.name || '未命名工作流',
        description: workflow.description || '',
        status: workflow.status || 'draft',
        version: workflow.version || 1,
        isCurrentVersion: workflow.is_current_version !== undefined ? workflow.is_current_version : true,
        createdBy: workflow.creator_name || workflow.created_by || '未知',
        creatorId: workflow.creator_id || '',
        createdAt: workflow.created_at || workflow.createdAt || '',
        updatedAt: workflow.updated_at || workflow.updatedAt || '',
        nodeCount: workflow.node_count || workflow.nodeCount || 0,
        executionCount: workflow.execution_count || workflow.executionCount || 0,
      }));
      
      setWorkflows(processedWorkflows);
    } catch (error) {
      console.error('加载工作流失败:', error);
      message.error('加载工作流失败');
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft':
        return 'default';
      case 'active':
        return 'processing';
      case 'completed':
        return 'success';
      case 'paused':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'draft':
        return '草稿';
      case 'active':
        return '运行中';
      case 'completed':
        return '已完成';
      case 'paused':
        return '已暂停';
      default:
        return '未知';
    }
  };

  const handleCreate = () => {
    setCreateModalVisible(true);
    createForm.resetFields();
  };

  const handleCreateConfirm = async () => {
    try {
      const values = await createForm.validateFields();
      console.log('工作流创建表单值:', values);
      
      // 添加creator_id字段以满足后端要求
      const { user } = useAuthStore.getState();
      if (!user || !user.user_id) {
        message.error('用户信息不完整，无法创建工作流');
        return;
      }
      
      const workflowData = {
        ...values,
        creator_id: user.user_id
      };
      
      const newWorkflow: any = await workflowAPI.createWorkflow(workflowData);
      console.log('工作流创建响应:', newWorkflow);
      
      message.success('工作流创建成功');
      setCreateModalVisible(false);
      loadWorkflows();
      
      // 自动打开设计器
      if (newWorkflow && newWorkflow.data && newWorkflow.data.workflow) {
        const workflowData = newWorkflow.data.workflow;
        setCurrentWorkflow({
          id: workflowData.workflow_id || workflowData.id,
          baseId: workflowData.workflow_base_id || workflowData.workflow_id || workflowData.id,
          name: workflowData.name,
          description: workflowData.description,
          status: 'draft' as const,
          version: 1,
          isCurrentVersion: true,
          createdBy: '当前用户',
          creatorId: workflowData.creator_id || user.user_id,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          nodeCount: 0,
          executionCount: 0,
        });
        setDesignerVisible(true);
      }
    } catch (error: any) {
      console.error('创建失败:', error);
      console.error('错误响应:', error.response?.data);
      message.error(error.response?.data?.detail || '创建工作流失败');
    }
  };

  const handleExecute = async (workflow: WorkflowItem) => {
    try {
      await executionAPI.executeWorkflow({
        workflow_base_id: workflow.baseId, // 使用workflow_base_id执行
        instance_name: `${workflow.name}_执行_${Date.now()}`
      });
      message.success('工作流执行已启动');
      loadWorkflows();
    } catch (error: any) {
      console.error('执行失败:', error);
      message.error(error.response?.data?.detail || '执行工作流失败');
    }
  };

  const handleView = (workflow: WorkflowItem) => {
    setCurrentWorkflow(workflow);
    setDesignerVisible(true);
  };

  const handleEdit = (workflow: WorkflowItem) => {
    setCurrentWorkflow(workflow);
    setDesignerVisible(true);
  };

  const handleDelete = async (workflow: WorkflowItem) => {
    try {
      await workflowAPI.deleteWorkflow(workflow.baseId); // 使用workflow_base_id删除
      message.success('工作流删除成功');
      loadWorkflows();
    } catch (error: any) {
      console.error('删除失败:', error);
      message.error(error.response?.data?.detail || '删除工作流失败');
    }
  };

  const handleWorkflowSave = async (nodes: any[], edges: any[]) => {
    if (!currentWorkflow) {
      message.error('当前工作流信息缺失');
      return;
    }

    try {
      console.log('保存工作流:', currentWorkflow.baseId);
      console.log('节点数量:', nodes.length);
      console.log('连线数量:', edges.length);
      
      // 更新工作流基本信息（节点数量等统计信息）
      const workflowUpdateData = {
        name: currentWorkflow.name,
        description: currentWorkflow.description,
        status: currentWorkflow.status,
        node_count: nodes.length
      };
      
      await workflowAPI.updateWorkflow(currentWorkflow.baseId, workflowUpdateData);
      
      message.success('工作流保存成功');
      
      // 重新加载工作流列表以更新统计信息
      await loadWorkflows();
      
      console.log('工作流保存完成');
    } catch (error: any) {
      console.error('工作流保存失败:', error);
      message.error(error.response?.data?.detail || '工作流保存失败');
    }
  };

  const handleWorkflowExecute = (workflowBaseId: string) => {
    message.success('工作流执行已启动');
    loadWorkflows();
  };

  const handleViewTaskFlow = (workflow: WorkflowItem) => {
    navigate(`/workflow/${workflow.baseId}/task-flow`); // 使用workflow_base_id
  };

  const handleViewInstances = (workflow: WorkflowItem) => {
    setCurrentWorkflow(workflow);
    setInstanceListVisible(true);
  };

  // ========== 测试函数区域 ==========
  const testBackendHealth = async () => {
    try {
      const response = await fetch('http://localhost:8001/health');
      if (response.ok) {
        const data = await response.json();
        message.success(`后端服务正常: ${data.message || '健康检查通过'}`);
        console.log('后端健康检查结果:', data);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error: any) {
      message.error(`后端服务异常: ${error.message}`);
      console.error('后端健康检查失败:', error);
    }
  };

  const testAuthAPI = async () => {
    try {
      const currentUser = await authAPI.getCurrentUser();
      message.success(`认证正常，当前用户: ${currentUser.data?.username || '未知'}`);
      console.log('当前用户信息:', currentUser);
    } catch (error: any) {
      message.error(`认证失败: ${error.response?.data?.message || error.message}`);
      console.error('认证测试失败:', error);
    }
  };

  const testNodeAPI = async () => {
    if (!workflows.length) {
      message.warning('请先创建一个工作流');
      return;
    }

    const testWorkflow = workflows[0];
    try {
      console.log('测试工作流:', testWorkflow);
      
      // 1. 获取节点列表
      const nodesResponse = await nodeAPI.getWorkflowNodes(testWorkflow.baseId);
      console.log('节点列表响应:', nodesResponse);
      
      const nodes = nodesResponse.data?.nodes || [];
      message.success(`节点API测试成功，找到 ${nodes.length} 个节点`);
      
      // 2. 如果有节点，测试节点更新
      if (nodes.length > 0) {
        const testNode = nodes[0];
        console.log('测试节点更新:', testNode);
        
        try {
          const updateData = {
            name: testNode.name,
            task_description: '测试更新 ' + new Date().toLocaleTimeString(),
            position_x: testNode.position_x || 0,
            position_y: testNode.position_y || 0
          };
          
          const updateResponse = await nodeAPI.updateNode(
            testNode.node_base_id, 
            testWorkflow.baseId, 
            updateData
          );
          console.log('节点更新响应:', updateResponse);
          message.success('节点更新测试成功');
        } catch (updateError: any) {
          console.error('节点更新测试失败:', updateError);
          message.error(`节点更新失败: ${updateError.response?.data?.message || updateError.message}`);
        }
      }
      
    } catch (error: any) {
      message.error(`节点API测试失败: ${error.response?.data?.message || error.message}`);
      console.error('节点API测试失败:', error);
    }
  };

  const testCreateNode = async () => {
    if (!workflows.length) {
      message.warning('请先创建一个工作流');
      return;
    }

    const testWorkflow = workflows[0];
    try {
      const nodeData = {
        name: `测试节点_${Date.now()}`,
        type: 'processor',
        task_description: '这是一个测试节点',
        workflow_base_id: testWorkflow.baseId,
        position_x: Math.floor(Math.random() * 300) + 100,
        position_y: Math.floor(Math.random() * 200) + 100
      };

      console.log('创建测试节点:', nodeData);
      const response = await nodeAPI.createNode(nodeData);
      console.log('节点创建响应:', response);
      
      const newNodeId = response.data?.node?.node_base_id;
      if (!newNodeId) {
        throw new Error('创建响应中没有节点ID');
      }
      
      message.success(`测试节点创建成功，ID: ${newNodeId}`);
      
      // 分阶段测试更新，增加延迟时间
      const testDelays = [500, 1000, 2000, 5000]; // 0.5s, 1s, 2s, 5s
      
      for (let i = 0; i < testDelays.length; i++) {
        const delay = testDelays[i];
        setTimeout(async () => {
          try {
            console.log(`尝试更新节点 (延迟${delay}ms):`, newNodeId);
            
            // 先检查节点是否存在
            try {
              const checkResponse = await nodeAPI.getWorkflowNodes(testWorkflow.baseId);
              const nodes = checkResponse.data?.nodes || [];
              const targetNode = nodes.find((n: any) => n.node_base_id === newNodeId);
              const nodeExists = !!targetNode;
              
              console.log(`延迟${delay}ms后节点是否存在:`, nodeExists);
              console.log('当前节点列表:', nodes.map((n: any) => ({ id: n.node_base_id, name: n.name })));
              
              if (nodeExists && targetNode) {
                console.log('找到的节点详细信息:', {
                  node_base_id: targetNode.node_base_id,
                  name: targetNode.name,
                  type: targetNode.type,
                  workflow_base_id: targetNode.workflow_base_id,
                  is_current_version: targetNode.is_current_version,
                  is_deleted: targetNode.is_deleted
                });
              }
              
              if (!nodeExists) {
                console.warn(`延迟${delay}ms后节点仍不存在于数据库中`);
                return;
              }
            } catch (checkError) {
              console.error('检查节点存在性失败:', checkError);
              return;
            }
            
            // 尝试更新
            await nodeAPI.updateNode(newNodeId, testWorkflow.baseId, {
              name: `${nodeData.name}_更新${delay}ms`,
              task_description: `更新测试 ${delay}ms延迟`,
              position_x: nodeData.position_x + (i * 10),
              position_y: nodeData.position_y + (i * 10)
            });
            
            console.log(`延迟${delay}ms的更新测试成功`);
            message.success(`延迟${delay}ms更新成功！`);
            
          } catch (updateError: any) {
            console.error(`延迟${delay}ms更新测试失败:`, updateError);
            console.error('错误详情:', {
              status: updateError.response?.status,  
              statusText: updateError.response?.statusText,
              data: updateError.response?.data
            });
          }
        }, delay);
      }
      
    } catch (error: any) {
      message.error(`创建测试节点失败: ${error.response?.data?.message || error.message}`);
      console.error('创建测试节点失败:', error);
    }
  };

  const clearConsoleAndTest = () => {
    console.clear();
    console.log('=== 开始调试测试 ===');
    console.log('当前工作流列表:', workflows);
    console.log('当前用户:', useAuthStore.getState().user);
    message.info('控制台已清空，开始调试测试');
  };

  const runFullDiagnostic = async () => {
    console.log('=== 开始完整诊断 ===');
    message.info('开始完整诊断，请查看控制台');
    
    // 1. 后端健康检查
    console.log('1. 后端健康检查...');
    await testBackendHealth();
    
    // 2. 认证测试
    console.log('2. 认证测试...');
    await testAuthAPI();
    
    // 3. 工作流API测试
    if (workflows.length > 0) {
      console.log('3. 工作流API测试...');
      await testNodeAPI();
    } else {
      console.log('3. 跳过工作流API测试（无工作流）');
    }
    
    console.log('=== 诊断完成 ===');
    message.success('完整诊断完成，请查看控制台详情');
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return '-';
    try {
      return new Date(dateString).toLocaleString('zh-CN');
    } catch {
      return dateString;
    }
  };

  const columns = [
    {
      title: '工作流名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: WorkflowItem) => (
        <div>
          <div style={{ fontWeight: 'bold', fontSize: '14px' }}>
            {text}
            {record.isCurrentVersion && <Tag color="blue" style={{ marginLeft: 8, fontSize: '12px' }}>当前版本</Tag>}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
            {record.description || '暂无描述'}
          </div>
          <div style={{ fontSize: '11px', color: '#999', marginTop: '2px' }}>
            版本 v{record.version}
          </div>
        </div>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {getStatusText(status)}
        </Tag>
      )
    },
    {
      title: '节点数',
      dataIndex: 'nodeCount',
      key: 'nodeCount',
      width: 80,
      render: (count: number) => (
        <Text strong>{count}</Text>
      )
    },
    {
      title: '执行次数',
      dataIndex: 'executionCount',
      key: 'executionCount',
      width: 100,
      render: (count: number) => (
        <Text type="secondary">{count}</Text>
      )
    },
    {
      title: '创建人',
      dataIndex: 'createdBy',
      key: 'createdBy',
      width: 100,
      render: (text: string) => (
        <Text>{text}</Text>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 150,
      render: (text: string) => (
        <Text type="secondary" style={{ fontSize: '12px' }}>
          {formatDate(text)}
        </Text>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (text: string, record: WorkflowItem) => (
        <Space size="small">
          {record.status === 'draft' && (
            <Button 
              type="primary" 
              size="small" 
              icon={<PlayCircleOutlined />}
              onClick={() => handleExecute(record)}
            >
              执行
            </Button>
          )}
          <Button 
            type="link" 
            size="small" 
            icon={<ShareAltOutlined />}
            onClick={() => handleViewTaskFlow(record)}
          >
            任务流程
          </Button>
          <Button 
            type="link" 
            size="small" 
            icon={<HistoryOutlined />}
            onClick={() => handleViewInstances(record)}
          >
            执行记录
          </Button>
          <Button 
            type="link" 
            size="small" 
            icon={<EyeOutlined />}
            onClick={() => handleView(record)}
          >
            查看
          </Button>
          <Button 
            type="link" 
            size="small" 
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Button 
            type="link" 
            size="small" 
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record)}
          >
            删除
          </Button>
        </Space>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: '24px' }}>
        <Title level={2} style={{ marginBottom: '8px' }}>
          <BranchesOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
          工作流管理
        </Title>
        <Text type="secondary">创建、管理和执行工作流</Text>
      </div>

      {/* 操作栏 */}
      <Card style={{ marginBottom: '24px' }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Text strong>工作流列表</Text>
            <Text type="secondary" style={{ marginLeft: '8px' }}>
              (共 {workflows.length} 个工作流)
            </Text>
          </Col>
          <Col>
            <Space>
              <Button 
                icon={<ReloadOutlined />} 
                onClick={loadWorkflows}
                loading={loading}
              >
                刷新
              </Button>
              <Button 
                type="primary" 
                icon={<PlusOutlined />}
                onClick={handleCreate}
              >
                创建工作流
              </Button>
              
              {/* ========== 测试按钮区域 ========== */}
              <Space.Compact>
                <Button 
                  icon={<BugOutlined />}
                  onClick={clearConsoleAndTest}
                  title="清空控制台并开始调试"
                  size="small"
                >
                  调试
                </Button>
                <Button 
                  icon={<ApiOutlined />}
                  onClick={testBackendHealth}
                  title="测试后端服务健康状态"
                  size="small"
                >
                  后端
                </Button>
                <Button 
                  icon={<DatabaseOutlined />}
                  onClick={testAuthAPI}
                  title="测试认证API"
                  size="small"
                >
                  认证
                </Button>
                <Button 
                  icon={<ToolOutlined />}
                  onClick={testNodeAPI}
                  title="测试节点API"
                  size="small"
                >
                  节点API
                </Button>
                <Button 
                  icon={<PlusOutlined />}
                  onClick={testCreateNode}
                  title="测试创建节点"
                  size="small"
                >
                  创建测试
                </Button>
              </Space.Compact>
              
              <Button 
                type="dashed"
                icon={<ToolOutlined />}
                onClick={runFullDiagnostic}
                title="运行完整系统诊断"
                size="small"
              >
                完整诊断
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>
      
      {/* 工作流表格 */}
      <Card>
        {workflows.length > 0 ? (
          <Table
            loading={loading}
            columns={columns}
            dataSource={workflows}
            rowKey="id"
            pagination={{
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条/共 ${total} 条`,
              pageSize: 10,
              pageSizeOptions: ['10', '20', '50']
            }}
          />
        ) : (
          <Empty
            description="暂无工作流"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              创建第一个工作流
            </Button>
          </Empty>
        )}
      </Card>

      {/* 创建工作流模态框 */}
      <Modal
        title="创建工作流"
        open={createModalVisible}
        onOk={handleCreateConfirm}
        onCancel={() => setCreateModalVisible(false)}
        width={600}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="工作流名称"
            rules={[{ required: true, message: '请输入工作流名称' }]}
          >
            <Input placeholder="请输入工作流名称" />
          </Form.Item>
          <Form.Item
            name="description"
            label="工作流描述"
            rules={[{ required: true, message: '请输入工作流描述' }]}
          >
            <TextArea rows={3} placeholder="请输入工作流描述" />
          </Form.Item>
          <Form.Item
            name="category"
            label="工作流分类"
          >
            <Select placeholder="请选择工作流分类">
              <Option value="approval">审批流程</Option>
              <Option value="review">审查流程</Option>
              <Option value="automation">自动化流程</Option>
              <Option value="other">其他</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 工作流设计器抽屉 */}
      <Drawer
        title={`工作流设计器 - ${currentWorkflow?.name || ''}`}
        placement="right"
        width="80%"
        open={designerVisible}
        onClose={() => setDesignerVisible(false)}
        styles={{ body: { padding: 0 } }}
      >
        <WorkflowDesigner
          workflowId={currentWorkflow?.baseId} // 传递workflow_base_id
          onSave={handleWorkflowSave}
          onExecute={handleWorkflowExecute}
          readOnly={false}
        />
      </Drawer>

      {/* 执行实例列表弹窗 */}
      <WorkflowInstanceList
        workflowBaseId={currentWorkflow?.baseId || ''}
        visible={instanceListVisible}
        onClose={() => setInstanceListVisible(false)}
      />
    </div>
  );
};

export default WorkflowPage;
