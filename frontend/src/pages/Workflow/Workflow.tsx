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
  HistoryOutlined,
  DownloadOutlined,
  UploadOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { workflowAPI, executionAPI } from '../../services/api';
import { useAuthStore } from '../../stores/authStore';
import WorkflowDesigner from '../../components/WorkflowDesigner';
import WorkflowInstanceList from '../../components/WorkflowInstanceList';
import WorkflowImportExport from '../../components/WorkflowImportExport';

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
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [designerVisible, setDesignerVisible] = useState(false);
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowItem | null>(null);
  const [instanceListVisible, setInstanceListVisible] = useState(false);
  const [createForm] = Form.useForm();

  // 导入导出相关状态
  const [importExportVisible, setImportExportVisible] = useState(false);
  const [importExportMode, setImportExportMode] = useState<'export' | 'import'>('export');
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowItem | null>(null);

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
      // 确保workflow_base_id是有效的UUID格式
      const workflowBaseId = workflow.baseId || workflow.id; // fallback to workflow.id if baseId is missing
      
      // 验证UUID格式
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
      if (!workflowBaseId || !uuidRegex.test(workflowBaseId)) {
        throw new Error(`无效的工作流ID格式: ${workflowBaseId}`);
      }
      
      // 确保workflow_instance_name不为空
      const instanceName = `${workflow.name}_执行_${Date.now()}`;
      if (!instanceName || instanceName.length === 0) {
        throw new Error('实例名称不能为空');
      }
      
      const requestData = {
        workflow_base_id: workflowBaseId,
        workflow_instance_name: instanceName,
        input_data: {},  // 添加空的input_data
        context_data: {}  // 添加空的context_data
      };
      
      console.log('发送的请求数据:', requestData);
      console.log('workflow对象:', workflow);
      console.log('workflow.baseId:', workflow.baseId);
      console.log('workflow.id:', workflow.id);
      console.log('UUID验证结果:', uuidRegex.test(workflowBaseId));
      
      await executionAPI.executeWorkflow(requestData);
      message.success('工作流执行已启动');
      loadWorkflows();
    } catch (error: any) {
      console.error('执行失败:', error);
      console.error('错误详情:', error.response?.data);
      
      // 特别展开detail数组的内容
      if (error.response?.data?.detail && Array.isArray(error.response.data.detail)) {
        console.error('Pydantic验证错误详情:');
        error.response.data.detail.forEach((item: any, index: number) => {
          console.error(`错误 ${index + 1}:`, {
            type: item.type,
            location: item.loc,
            message: item.msg,
            input: item.input
          });
        });
      }
      
      // 详细的错误信息处理
      let errorMessage = '执行工作流失败';
      if (error.response?.data?.detail) {
        if (Array.isArray(error.response.data.detail)) {
          // FastAPI验证错误格式
          const details = error.response.data.detail.map((item: any) => 
            `${item.loc?.join('.')} - ${item.msg}`
          ).join('; ');
          errorMessage = `验证错误: ${details}`;
        } else {
          errorMessage = error.response.data.detail;
        }
      } else if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      message.error(errorMessage);
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

  const handleViewInstances = (workflow: WorkflowItem) => {
    setCurrentWorkflow(workflow);
    setInstanceListVisible(true);
  };

  // 导入导出处理函数
  const handleExport = (workflow: WorkflowItem) => {
    setSelectedWorkflow(workflow);
    setImportExportMode('export');
    setImportExportVisible(true);
  };

  const handleImport = () => {
    setSelectedWorkflow(null);
    setImportExportMode('import');
    setImportExportVisible(true);
  };

  const handleImportExportClose = () => {
    setImportExportVisible(false);
    setSelectedWorkflow(null);
  };

  const handleExportSuccess = () => {
    // 导出成功后可以刷新列表或显示提示
    loadWorkflows();
  };

  const handleImportSuccess = (workflowId: string) => {
    // 导入成功后刷新工作流列表
    loadWorkflows();
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
            icon={<DownloadOutlined />}
            onClick={() => handleExport(record)}
          >
            导出
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
              <Button 
                icon={<UploadOutlined />}
                onClick={handleImport}
              >
                导入工作流
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

      {/* 导入导出模态框 */}
      <WorkflowImportExport
        visible={importExportVisible}
        mode={importExportMode}
        workflowId={selectedWorkflow?.baseId}
        workflowName={selectedWorkflow?.name}
        onClose={handleImportExportClose}
        onExportSuccess={handleExportSuccess}
        onImportSuccess={handleImportSuccess}
      />
    </div>
  );
};

export default WorkflowPage;
