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
  Col
} from 'antd';
import { 
  BranchesOutlined,
  SaveOutlined,
  WarningOutlined
} from '@ant-design/icons';
import { taskSubdivisionApi, workflowAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import WorkflowDesigner from './WorkflowDesigner';
import type { Node, Edge } from 'reactflow';

const { TextArea } = Input;
const { Text } = Typography;

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
  const [subdivisionWorkflowId, setSubdivisionWorkflowId] = useState<string | null>(null);
  const [creatingWorkflow, setCreatingWorkflow] = useState(false);
  // 处理工作流设计器的保存回调
  const handleWorkflowSave = (nodes: Node[], edges: Edge[]) => {
    setWorkflowNodes(nodes);
    setWorkflowEdges(edges);
    console.log('🔄 工作流设计已更新:', { nodeCount: nodes.length, edgeCount: edges.length });
  };

  // 创建细分工作流用于任务细分设计
  const createSubdivisionWorkflow = useCallback(async () => {
    const { user } = useAuthStore.getState();
    if (!user || !user.user_id) {
      message.error('用户信息不完整，无法创建细分工作流');
      return null;
    }

    // 🔧 添加重复调用保护
    if (creatingWorkflow || subdivisionWorkflowId) {
      console.log('🛡️ 防止重复创建工作流:', { creatingWorkflow, subdivisionWorkflowId });
      return subdivisionWorkflowId;
    }

    try {
      setCreatingWorkflow(true);
      console.log('🔄 创建任务细分工作流...');

      const subdivisionWorkflowData = {
        name: `[细分] ${taskTitle}_${Date.now()}`,
        description: `从任务"${taskTitle}"细分而来的工作流`,
        category: 'subdivision',
        creator_id: user.user_id
      };

      console.log('📋 工作流创建参数:', subdivisionWorkflowData);

      const response: any = await workflowAPI.createWorkflow(subdivisionWorkflowData);
      console.log('✅ 细分工作流创建成功:', response);

      // 提取工作流ID
      let workflowId = null;
      if (response && response.data && response.data.workflow) {
        workflowId = response.data.workflow.workflow_base_id || response.data.workflow.workflow_id;
      }

      console.log('🔧 工作流ID提取结果:', {
        responseExists: !!response,
        dataExists: !!(response && response.data),
        workflowExists: !!(response && response.data && response.data.workflow),
        extractedId: workflowId
      });

      if (workflowId) {
        setSubdivisionWorkflowId(workflowId);
        console.log('✅ 细分工作流ID设置为:', workflowId);
        return workflowId;
      } else {
        console.error('❌ 无法提取工作流ID，响应结构:', JSON.stringify(response, null, 2));
        throw new Error('无法获取工作流ID');
      }

    } catch (error: any) {
      console.error('❌ 创建细分工作流失败:', error);
      message.error('创建细分工作流失败: ' + (error.message || '未知错误'));
      return null;
    } finally {
      setCreatingWorkflow(false);
    }
  }, [taskTitle, creatingWorkflow, subdivisionWorkflowId]); // 添加更多依赖

  // 更新工作流名称为用户填写的细分名称
  const updateWorkflowName = async (workflowId: string, newName: string) => {
    try {
      console.log('🔧 更新工作流名称:', { workflowId, newName });
      await workflowAPI.updateWorkflow(workflowId, { name: newName });
      console.log('✅ 工作流名称更新成功');
    } catch (error: any) {
      console.error('❌ 更新工作流名称失败:', error);
      // 这里不抛出错误，因为这不是关键功能
    }
  };

  // 当模态框打开时创建细分工作流
  useEffect(() => {
    if (visible && !subdivisionWorkflowId && !creatingWorkflow) {
      createSubdivisionWorkflow();
    }
  }, [visible, subdivisionWorkflowId, creatingWorkflow, createSubdivisionWorkflow]);

  // 重置状态当模态框关闭时
  useEffect(() => {
    if (!visible) {
      setSubdivisionWorkflowId(null);
      setWorkflowNodes([]);
      setWorkflowEdges([]);
      form.resetFields();
    }
  }, [visible, form]);

  const handleSubmit = async (values: any) => {
    try {
      setLoading(true);

      // 🔧 关键检查：验证前端预创建的工作流ID
      if (!subdivisionWorkflowId) {
        console.error('❌ 致命错误：subdivisionWorkflowId 为空！');
        console.error('   当前状态:', {
          subdivisionWorkflowId,
          creatingWorkflow,
          visible
        });
        message.error('工作流模板创建失败，请重新打开细分界面');
        return;
      }

      console.log('✅ 工作流ID验证通过:', subdivisionWorkflowId);

      // 🔧 新增：在提交时更新工作流名称为用户填写的细分名称
      if (values.subdivision_name && values.subdivision_name.trim()) {
        await updateWorkflowName(subdivisionWorkflowId, values.subdivision_name.trim());
      }

      // 验证工作流设计
      if (workflowNodes.length === 0) {
        message.error('请先设计子工作流结构');
        return;
      }

      // 构建子工作流数据
      const subWorkflowData = {
        nodes: workflowNodes.map((node, index) => ({
          node_base_id: node.id,
          name: node.data?.label || `节点_${index + 1}`,
          type: node.data?.type || 'processor',
          task_description: node.data?.description || '',
          position_x: node.position.x,
          position_y: node.position.y,
          processor_id: node.data?.processor_id || null, // 添加processor_id字段
          creator_id: 'current_user', // 将由后端自动设置
        })),
        connections: workflowEdges.map((edge) => ({
          from_node_id: edge.source,
          to_node_id: edge.target,
          connection_type: 'normal'
        }))
      };

      const subdivisionData = {
        subdivision_name: values.subdivision_name,
        subdivision_description: values.subdivision_description || '',
        sub_workflow_base_id: subdivisionWorkflowId, // 🔧 确保传递已创建的工作流ID
        sub_workflow_data: subWorkflowData,
        execute_immediately: values.execute_immediately !== false,
        // 添加任务上下文信息传递
        task_context: {
          original_task_title: values.task_title || taskTitle,
          original_task_description: values.task_description || taskDescription,
          task_context_data: values.task_context || taskContext,
          task_input_data: values.task_input_data || taskInputData
        }
      };

      console.log('🔄 提交任务细分数据:', subdivisionData);
      console.log('🔧 关键参数验证:', {
        subdivision_name: subdivisionData.subdivision_name,
        sub_workflow_base_id: subdivisionData.sub_workflow_base_id,
        nodes_count: subdivisionData.sub_workflow_data.nodes.length,
        connections_count: subdivisionData.sub_workflow_data.connections.length
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
        {/* 任务信息编辑区域 */}
        <Card 
          title="任务信息传递设置" 
          size="small" 
          style={{ marginBottom: 16 }}
          extra={<Text type="secondary">这些信息将传递给子工作流的开始节点</Text>}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="task_title"
                label="任务标题"
                rules={[{ required: true, message: '请输入任务标题' }]}
                extra="将作为子工作流的主要标识"
              >
                <Input placeholder="请输入传递给子工作流的任务标题" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="task_description"
                label="任务描述"
                extra="详细说明任务的要求和目标"
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
                extra="提供任务执行所需的背景信息"
              >
                <TextArea 
                  rows={3} 
                  placeholder="请输入任务的上下文信息，如：项目背景、相关数据、前置条件等..." 
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="task_input_data"
                label="输入数据"
                extra="提供任务执行所需的具体输入数据"
              >
                <TextArea 
                  rows={3} 
                  placeholder="请输入任务的输入数据，如：具体参数、文件路径、数据格式要求等..." 
                />
              </Form.Item>
            </Col>
          </Row>
        </Card>

        {/* 细分工作流配置区域 */}
        <Card 
          title="细分工作流配置" 
          size="small" 
          style={{ marginBottom: 16 }}
          extra={<Text type="secondary">配置细分工作流的基本信息</Text>}
        >
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              name="subdivision_name"
              label="细分工作流名称"
              rules={[{ required: true, message: '请输入细分工作流名称' }]}
            >
              <Input placeholder="如：详细数据处理流程" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              name="execute_immediately"
              label="创建后立即执行"
              valuePropName="checked"
              extra="启用后将自动执行细分工作流并提交结果给原始任务"
            >
              <Switch 
                checkedChildren="立即执行" 
                unCheckedChildren="稍后执行" 
                disabled={false}
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

        <Divider orientation="left">
          <Space>
            <BranchesOutlined />
            子工作流设计
          </Space>
        </Divider>

        {/* 工作流设计器 */}
        <div style={{ height: '500px', border: '1px solid #d9d9d9', borderRadius: '6px' }}>
          {creatingWorkflow ? (
            <div style={{ 
              height: '100%', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              flexDirection: 'column',
              color: '#666'
            }}>
              <div style={{ marginBottom: 16 }}>正在创建细分工作流...</div>
              <div style={{ fontSize: '12px' }}>请稍候，正在为任务细分准备设计环境</div>
            </div>
          ) : subdivisionWorkflowId ? (
            <WorkflowDesigner
              workflowId={subdivisionWorkflowId}
              onSave={handleWorkflowSave}
              readOnly={false}
            />
          ) : (
            <div style={{ 
              height: '100%', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              flexDirection: 'column',
              color: '#999'
            }}>
              <div style={{ marginBottom: 16 }}>工作流设计器准备中...</div>
              <div style={{ fontSize: '12px' }}>如果长时间无响应，请尝试重新打开</div>
            </div>
          )}
        </div>

        <div style={{ marginTop: 16, padding: '12px', backgroundColor: '#f0f2f5', borderRadius: '6px' }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            💡 提示：
            <br />
            • 使用上方的可视化设计器来创建子工作流
            <br />
            • 添加节点并连接它们来定义任务执行顺序
            <br />
            • 每个节点代表一个具体的子任务
            <br />
            • 当前设计包含 <Text strong>{workflowNodes.length}</Text> 个节点和 <Text strong>{workflowEdges.length}</Text> 个连接
          </Text>
        </div>

        <div style={{ textAlign: 'right', marginTop: 24 }}>
          <Space>
            <Button onClick={onCancel}>
              取消
            </Button>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading}
              icon={<SaveOutlined />}
              disabled={workflowNodes.length === 0 || !subdivisionWorkflowId || creatingWorkflow}
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