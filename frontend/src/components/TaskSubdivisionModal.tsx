import React, { useState, useEffect, useCallback } from 'react';
import { 
  Modal, 
  Form, 
  Input, 
  Button, 
  message,
  Switch,
  Card,
  Space,
  Typography,
  Divider,
  Row,
  Col,
  Select,
  Radio
} from 'antd';
import { 
  BranchesOutlined,
  SaveOutlined,
  WarningOutlined,
  FolderOpenOutlined,
  PlusOutlined
} from '@ant-design/icons';
import { taskSubdivisionApi, workflowAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import WorkflowDesigner from './WorkflowDesigner';
import type { Node, Edge } from 'reactflow';

const { TextArea } = Input;
const { Text } = Typography;
const { Option } = Select;

interface TaskSubdivisionModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  taskId: string;
  taskTitle: string;
  taskDescription?: string;
  taskContext?: string;
  taskInputData?: string;
}

const TaskSubdivisionModal: React.FC<TaskSubdivisionModalProps> = ({
  visible,
  onCancel,
  onSuccess,
  taskId,
  taskTitle,
  taskDescription = '',
  taskContext = '',
  taskInputData = ''
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [workflowNodes, setWorkflowNodes] = useState<Node[]>([]);
  const [workflowEdges, setWorkflowEdges] = useState<Edge[]>([]);
  
  // 新增状态：工作流选择模式
  const [workflowSelectionMode, setWorkflowSelectionMode] = useState<'existing' | 'create'>('create');
  const [existingWorkflows, setExistingWorkflows] = useState<any[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [loadingWorkflows, setLoadingWorkflows] = useState(false);
  
  // 新工作流创建相关状态
  const [newWorkflowId, setNewWorkflowId] = useState<string | null>(null);
  const [creatingWorkflow, setCreatingWorkflow] = useState(false);

  // 加载用户的现有工作流
  const loadExistingWorkflows = useCallback(async () => {
    const { user } = useAuthStore.getState();
    if (!user?.user_id) return;

    try {
      setLoadingWorkflows(true);
      // 调用API获取用户的工作流列表
      const response = await workflowAPI.getUserWorkflows(user.user_id);
      if (response?.data?.workflows) {
        setExistingWorkflows(response.data.workflows);
        console.log('✅ 加载用户工作流列表成功:', response.data.workflows.length, '个');
      }
    } catch (error: any) {
      console.error('❌ 加载用户工作流列表失败:', error);
      message.error('加载工作流列表失败');
    } finally {
      setLoadingWorkflows(false);
    }
  }, []);

  // 创建新工作流模板（仅在需要时创建）
  const createNewWorkflowTemplate = useCallback(async (workflowName: string) => {
    const { user } = useAuthStore.getState();
    if (!user?.user_id) {
      message.error('用户信息不完整');
      return null;
    }

    if (creatingWorkflow || newWorkflowId) {
      console.log('🛡️ 防止重复创建工作流');
      return newWorkflowId;
    }

    try {
      setCreatingWorkflow(true);
      console.log('🔄 创建新工作流模板:', workflowName);

      const workflowData = {
        name: workflowName,
        description: `任务细分工作流模板 - ${workflowName}`,
        category: 'subdivision',
        creator_id: user.user_id
      };

      const response: any = await workflowAPI.createWorkflow(workflowData);
      
      let workflowId = null;
      if (response?.data?.workflow) {
        workflowId = response.data.workflow.workflow_base_id || response.data.workflow.workflow_id;
      }

      if (workflowId) {
        setNewWorkflowId(workflowId);
        console.log('✅ 新工作流模板创建成功:', workflowId);
        return workflowId;
      } else {
        throw new Error('无法获取工作流ID');
      }

    } catch (error: any) {
      console.error('❌ 创建工作流模板失败:', error);
      message.error('创建工作流模板失败: ' + (error.message || '未知错误'));
      return null;
    } finally {
      setCreatingWorkflow(false);
    }
  }, [creatingWorkflow, newWorkflowId]);

  // 处理工作流设计器的保存回调
  const handleWorkflowSave = (nodes: Node[], edges: Edge[]) => {
    setWorkflowNodes(nodes);
    setWorkflowEdges(edges);
    console.log('🔄 工作流设计已更新:', { nodeCount: nodes.length, edgeCount: edges.length });
  };

  // 当模态框打开时加载现有工作流列表
  useEffect(() => {
    if (visible) {
      loadExistingWorkflows();
    }
  }, [visible, loadExistingWorkflows]);

  // 重置状态当模态框关闭时
  useEffect(() => {
    if (!visible) {
      setWorkflowSelectionMode('create');
      setSelectedWorkflowId(null);
      setNewWorkflowId(null);
      setWorkflowNodes([]);
      setWorkflowEdges([]);
      setExistingWorkflows([]);
      form.resetFields();
    }
  }, [visible, form]);

  // 处理工作流选择模式变化
  const handleSelectionModeChange = (mode: 'existing' | 'create') => {
    setWorkflowSelectionMode(mode);
    setSelectedWorkflowId(null);
    setNewWorkflowId(null);
    setWorkflowNodes([]);
    setWorkflowEdges([]);
  };

  const handleSubmit = async (values: any) => {
    try {
      setLoading(true);

      let templateId: string | null = null;
      let subWorkflowData = {};

      // 根据选择模式确定使用的工作流模板
      if (workflowSelectionMode === 'existing') {
        // 使用现有工作流
        if (!selectedWorkflowId) {
          message.error('请选择一个现有工作流');
          return;
        }
        templateId = selectedWorkflowId;
        console.log('🔄 使用现有工作流模板:', templateId);
        
      } else {
        // 创建新工作流
        if (workflowNodes.length === 0) {
          message.error('请先设计子工作流结构');
          return;
        }

        // 创建工作流模板（如果还没创建）
        templateId = newWorkflowId || await createNewWorkflowTemplate(values.subdivision_name);
        
        if (!templateId) {
          message.error('工作流模板创建失败');
          return;
        }

        // 构建工作流数据（用于创建节点）
        subWorkflowData = {
          nodes: workflowNodes.map((node, index) => ({
            node_base_id: node.id,
            name: node.data?.label || `节点_${index + 1}`,
            type: node.data?.type || 'processor',
            task_description: node.data?.description || '',
            position_x: node.position.x,
            position_y: node.position.y,
            processor_id: node.data?.processor_id || null,
          })),
          connections: workflowEdges.map((edge) => ({
            from_node_id: edge.source,
            to_node_id: edge.target,
            connection_type: 'normal'
          }))
        };
      }

      // 构建细分请求数据
      const subdivisionData = {
        subdivision_name: values.subdivision_name,
        subdivision_description: values.subdivision_description || '',
        sub_workflow_base_id: templateId, // 🔧 明确指定使用的模板ID
        sub_workflow_data: subWorkflowData, // 只有创建新模板时才有数据
        execute_immediately: values.execute_immediately !== false,
        task_context: {
          original_task_title: values.task_title || taskTitle,
          original_task_description: values.task_description || taskDescription,
          task_context_data: values.task_context || taskContext,
          task_input_data: values.task_input_data || taskInputData
        }
      };

      console.log('🔄 提交任务细分数据:', {
        mode: workflowSelectionMode,
        templateId,
        subdivision_name: subdivisionData.subdivision_name,
        execute_immediately: subdivisionData.execute_immediately,
        has_workflow_data: Object.keys(subWorkflowData).length > 0
      });

      await taskSubdivisionApi.createTaskSubdivision(taskId, subdivisionData);
      
      message.success('任务细分创建成功！');
      form.resetFields();
      setWorkflowNodes([]);
      setWorkflowEdges([]);
      onSuccess();
      
    } catch (error: any) {
      console.error('创建任务细分失败:', error);
      message.error(error.message || '创建任务细分失败');
    } finally {
      setLoading(false);
    }
  };

  const getWorkflowDesigner = () => {
    if (workflowSelectionMode === 'existing') {
      return (
        <div style={{ 
          height: '500px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          border: '1px solid #d9d9d9', 
          borderRadius: '6px',
          backgroundColor: '#fafafa'
        }}>
          <div style={{ textAlign: 'center', color: '#666' }}>
            <FolderOpenOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
            <div>使用现有工作流模板</div>
            <div style={{ fontSize: '12px', marginTop: '8px' }}>
              {selectedWorkflowId ? `已选择模板: ${selectedWorkflowId}` : '请在上方选择一个工作流模板'}
            </div>
          </div>
        </div>
      );
    }

    // 创建模式
    if (creatingWorkflow) {
      return (
        <div style={{ 
          height: '500px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          flexDirection: 'column',
          color: '#666',
          border: '1px solid #d9d9d9', 
          borderRadius: '6px'
        }}>
          <div style={{ marginBottom: 16 }}>正在创建工作流模板...</div>
          <div style={{ fontSize: '12px' }}>请稍候，正在准备设计环境</div>
        </div>
      );
    }

    if (newWorkflowId) {
      return (
        <div style={{ height: '500px', border: '1px solid #d9d9d9', borderRadius: '6px' }}>
          <WorkflowDesigner
            workflowId={newWorkflowId}
            onSave={handleWorkflowSave}
            readOnly={false}
          />
        </div>
      );
    }

    return (
      <div style={{ 
        height: '500px', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        flexDirection: 'column',
        color: '#999',
        border: '1px solid #d9d9d9', 
        borderRadius: '6px'
      }}>
        <PlusOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
        <div style={{ marginBottom: 16 }}>工作流设计器准备中...</div>
        <div style={{ fontSize: '12px' }}>填写细分名称后将自动创建工作流模板</div>
      </div>
    );
  };

  return (
    <Modal
      title={
        <Space>
          <BranchesOutlined />
          <span>细分任务: {taskTitle}</span>
        </Space>
      }
      open={visible}
      onCancel={onCancel}
      width={1200}
      style={{ top: 20 }}
      footer={null}
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <Card size="small" style={{ backgroundColor: '#f9f9f9' }}>
          <Text type="secondary">
            <WarningOutlined /> 当前将要细分的任务: {taskTitle}
          </Text>
        </Card>
      </div>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          execute_immediately: true,
          task_title: taskTitle,
          task_description: taskDescription,
          task_context: taskContext,
          task_input_data: taskInputData
        }}
      >
        {/* 任务信息传递设置 */}
        <Card 
          title="任务信息传递设置" 
          size="small" 
          style={{ marginBottom: 16 }}
          extra={<Text type="secondary">这些信息将传递给子工作流</Text>}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="task_title"
                label="任务标题"
                rules={[{ required: true, message: '请输入任务标题' }]}
              >
                <Input placeholder="请输入传递给子工作流的任务标题" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="task_description"
                label="任务描述"
              >
                <Input placeholder="请输入任务的详细描述" />
              </Form.Item>
            </Col>
          </Row>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="task_context"
                label="任务上下文"
              >
                <TextArea 
                  rows={3} 
                  placeholder="请输入任务的上下文信息..." 
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="task_input_data"
                label="输入数据"
              >
                <TextArea 
                  rows={3} 
                  placeholder="请输入任务的输入数据..." 
                />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        {/* 细分工作流配置 */}
        <Card 
          title="细分工作流配置" 
          size="small" 
          style={{ marginBottom: 16 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="subdivision_name"
                label="细分工作流名称"
                rules={[{ required: true, message: '请输入细分工作流名称' }]}
                extra={workflowSelectionMode === 'create' ? "将作为新工作流模板的名称" : "细分任务的标识名称"}
              >
                <Input 
                  placeholder="如：详细数据处理流程" 
                  onChange={(e) => {
                    // 如果是创建模式且有名称，自动创建工作流模板
                    if (workflowSelectionMode === 'create' && e.target.value && !newWorkflowId && !creatingWorkflow) {
                      createNewWorkflowTemplate(e.target.value);
                    }
                  }}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="execute_immediately"
                label="创建后立即执行"
                valuePropName="checked"
                extra="启用后将自动执行细分工作流并提交结果"
              >
                <Switch 
                  checkedChildren="立即执行" 
                  unCheckedChildren="稍后执行" 
                  defaultChecked={true}
                />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="subdivision_description"
            label="细分说明"
          >
            <TextArea 
              rows={3} 
              placeholder="说明为什么要细分这个任务，以及细分后的预期效果..." 
            />
          </Form.Item>
        </Card>

        {/* 工作流选择模式 */}
        <Card 
          title="工作流模板选择" 
          size="small" 
          style={{ marginBottom: 16 }}
        >
          <Radio.Group 
            value={workflowSelectionMode} 
            onChange={(e) => handleSelectionModeChange(e.target.value)}
            style={{ marginBottom: 16 }}
          >
            <Radio.Button value="existing">
              <FolderOpenOutlined /> 使用现有工作流
            </Radio.Button>
            <Radio.Button value="create">
              <PlusOutlined /> 创建新工作流
            </Radio.Button>
          </Radio.Group>

          {workflowSelectionMode === 'existing' && (
            <Form.Item
              label="选择工作流模板"
              extra="选择一个现有的工作流作为细分模板"
            >
              <Select
                placeholder="请选择一个工作流模板"
                loading={loadingWorkflows}
                value={selectedWorkflowId}
                onChange={setSelectedWorkflowId}
                showSearch
                filterOption={(input, option) => {
                  if (!option || !option.children) return false;
                  const children = option.children;
                  return String(children).toLowerCase().includes(input.toLowerCase());
                }}
              >
                {existingWorkflows.map(workflow => (
                  <Option key={workflow.workflow_base_id} value={workflow.workflow_base_id}>
                    {workflow.name} ({workflow.status})
                  </Option>
                ))}
              </Select>
            </Form.Item>
          )}
        </Card>

        <Divider orientation="left">
          <Space>
            <BranchesOutlined />
            {workflowSelectionMode === 'existing' ? '工作流模板预览' : '工作流设计'}
          </Space>
        </Divider>

        {/* 工作流设计器或预览 */}
        {getWorkflowDesigner()}

        <div style={{ marginTop: 16, padding: '12px', backgroundColor: '#f0f2f5', borderRadius: '6px' }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            💡 提示：<br />
            {workflowSelectionMode === 'existing' ? (
              <>• 使用现有工作流模板可以复用之前设计好的流程<br />
              • 选择的模板将被用作细分工作流的基础结构</>
            ) : (
              <>• 使用设计器创建新的工作流模板<br />
              • 当前设计包含 <Text strong>{workflowNodes.length}</Text> 个节点和 <Text strong>{workflowEdges.length}</Text> 个连接</>
            )}
          </Text>
        </div>

        <div style={{ textAlign: 'right', marginTop: 24 }}>
          <Space>
            <Button onClick={onCancel}>取消</Button>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading}
              icon={<SaveOutlined />}
              disabled={
                workflowSelectionMode === 'existing' 
                  ? !selectedWorkflowId 
                  : (workflowNodes.length === 0 || !newWorkflowId || creatingWorkflow)
              }
            >
              创建细分
            </Button>
          </Space>
        </div>
      </Form>
    </Modal>
  );
};

export default TaskSubdivisionModal;