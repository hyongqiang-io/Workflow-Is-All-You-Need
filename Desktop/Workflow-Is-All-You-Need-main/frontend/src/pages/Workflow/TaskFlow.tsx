import React, { useState, useEffect } from 'react';
import { Card, Button, Select, Space, Typography, message, Row, Col, Statistic, Progress } from 'antd';
import { 
  EyeOutlined, 
  PlayCircleOutlined, 
  PauseCircleOutlined,
  ReloadOutlined,
  UserOutlined,
  RobotOutlined
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import TaskFlowViewer from '../../components/TaskFlowViewer';

const { Title, Text } = Typography;
const { Option } = Select;

const TaskFlow: React.FC = () => {
  const { workflowId } = useParams<{ workflowId: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [workflowInfo, setWorkflowInfo] = useState<any>(null);

  useEffect(() => {
    if (workflowId) {
      loadWorkflowInfo();
    }
  }, [workflowId]);

  const loadWorkflowInfo = async () => {
    setLoading(true);
    try {
      // 模拟加载工作流信息
      const mockWorkflowInfo = {
        id: workflowId,
        name: '示例工作流',
        description: '这是一个示例工作流，用于演示任务流程可视化功能',
        status: 'active',
        creator: {
          id: 'creator-1',
          name: '张三'
        },
        created_at: '2024-01-15T10:00:00Z',
        total_tasks: 5,
        completed_tasks: 1,
        in_progress_tasks: 1,
        pending_tasks: 3,
        progress_percentage: 20
      };
      
      setWorkflowInfo(mockWorkflowInfo);
    } catch (error) {
      console.error('加载工作流信息失败:', error);
      message.error('加载工作流信息失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTaskAction = async (taskId: string, action: 'start' | 'complete' | 'pause') => {
    try {
      // 模拟API调用
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      let actionText = '';
      switch (action) {
        case 'start':
          actionText = '开始';
          break;
        case 'complete':
          actionText = '完成';
          break;
        case 'pause':
          actionText = '暂停';
          break;
      }
      
      message.success(`任务${actionText}成功`);
      
      // 重新加载工作流信息
      loadWorkflowInfo();
    } catch (error) {
      console.error('任务操作失败:', error);
      message.error('任务操作失败');
    }
  };

  const handleBackToWorkflows = () => {
    navigate('/workflow');
  };

  if (!workflowId) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <Text type="secondary">工作流ID无效</Text>
        </div>
      </Card>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题和操作 */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={2} style={{ marginBottom: '8px' }}>
              <EyeOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
              任务流程视图
            </Title>
            <Text type="secondary">
              查看工作流的任务分配和执行状态
            </Text>
          </div>
          <Space>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={loadWorkflowInfo}
              loading={loading}
            >
              刷新
            </Button>
            <Button 
              icon={<EyeOutlined />}
              onClick={handleBackToWorkflows}
            >
              返回工作流列表
            </Button>
          </Space>
        </div>
      </div>

      {/* 工作流统计信息 */}
      {workflowInfo && (
        <Card style={{ marginBottom: '24px' }}>
          <Row gutter={24}>
            <Col span={6}>
              <Statistic
                title="总任务数"
                value={workflowInfo.total_tasks}
                prefix={<UserOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="已完成"
                value={workflowInfo.completed_tasks}
                valueStyle={{ color: '#52c41a' }}
                prefix={<PlayCircleOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="进行中"
                value={workflowInfo.in_progress_tasks}
                valueStyle={{ color: '#1890ff' }}
                prefix={<PlayCircleOutlined />}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="待处理"
                value={workflowInfo.pending_tasks}
                valueStyle={{ color: '#faad14' }}
                prefix={<PauseCircleOutlined />}
              />
            </Col>
          </Row>
          <div style={{ marginTop: '16px' }}>
            <Text type="secondary">整体进度</Text>
            <Progress 
              percent={workflowInfo.progress_percentage} 
              status="active"
              strokeColor={{
                '0%': '#108ee9',
                '100%': '#87d068',
              }}
            />
          </div>
        </Card>
      )}

      {/* 任务流程可视化 */}
      <TaskFlowViewer
        workflowId={workflowId}
        currentUserId={user?.user_id || 'current-user'}
        onTaskAction={handleTaskAction}
      />

      {/* 使用说明 */}
      <Card style={{ marginTop: '24px' }}>
        <Title level={4}>使用说明</Title>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <div>
            <Title level={5}>创建者视图</Title>
            <ul>
              <li>可以看到完整的工作流程图</li>
              <li>所有任务节点都会高亮显示</li>
              <li>可以监控整个工作流的执行状态</li>
              <li>可以查看每个任务的详细信息</li>
            </ul>
          </div>
          <div>
            <Title level={5}>执行者视图</Title>
            <ul>
              <li>分配给您的任务会高亮显示</li>
              <li>可以直接在节点上操作任务</li>
              <li>在下方可以看到您的任务列表</li>
              <li>可以开始、完成或暂停任务</li>
            </ul>
          </div>
        </div>
        <div style={{ marginTop: '16px' }}>
          <Title level={5}>节点类型说明</Title>
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <UserOutlined style={{ color: '#1890ff' }} />
              <Text>人工任务</Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <RobotOutlined style={{ color: '#722ed1' }} />
              <Text>AI任务</Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <PlayCircleOutlined style={{ color: '#52c41a' }} />
              <Text>开始节点</Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <PauseCircleOutlined style={{ color: '#ff4d4f' }} />
              <Text>结束节点</Text>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default TaskFlow; 