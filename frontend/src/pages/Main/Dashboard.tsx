import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Button, List, Avatar, Tag, Progress, message } from 'antd';
import { 
  UserOutlined, 
  RobotOutlined, 
  BranchesOutlined, 
  CheckSquareOutlined,
  PlusOutlined,
  RocketOutlined,
  TeamOutlined,
  SettingOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { resourceAPI, agentAPI, taskAPI, workflowAPI } from '../../services/api';

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({
    totalWorkflows: 0,
    runningWorkflows: 0,
    totalTasks: 0,
    pendingTasks: 0,
    onlineUsers: 0,
    onlineAgents: 0
  });
  const [pendingTasks, setPendingTasks] = useState<any[]>([]);
  const [userWorkflows, setUserWorkflows] = useState<any[]>([]);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // 获取资源统计
      let onlineResources: any = { users: [] };
      try {
        const onlineResponse: any = await resourceAPI.getOnlineResources();
        if (onlineResponse.success) {
          onlineResources = onlineResponse.data || { users: [] };
        }
      } catch (error) {
        console.warn('获取在线资源失败:', error);
      }

      // 获取Agent统计
      let agents: any = [];
      try {
        const agentsResponse: any = await agentAPI.getAgents();
        if (agentsResponse.success && agentsResponse.data?.processors) {
          agents = agentsResponse.data.processors.filter((p: any) => p.type === 'agent');
        }
      } catch (error) {
        console.warn('获取Agent列表失败:', error);
      }

      // 获取当前用户的待办任务
      let userTasks: any[] = [];
      try {
        const tasksResponse: any = await taskAPI.getUserTasks();
        if (tasksResponse.success && tasksResponse.data) {
          // 只获取待处理的任务，最多10个
          userTasks = tasksResponse.data
            .filter((task: any) => ['pending', 'assigned', 'in_progress'].includes(task.status))
            .slice(0, 10)
            .map((task: any, index: number) => ({
              id: task.task_instance_id || index,
              title: task.task_title || '未命名任务',
              description: task.task_description || '无描述',
              status: task.status || 'pending',
              priority: task.priority || 'medium',
              workflow_name: task.workflow_name || '未知工作流',
              created_at: task.created_at,
              estimated_duration: task.estimated_duration
            }));
        }
      } catch (error) {
        console.warn('获取待办任务失败:', error);
        // 如果API调用失败，设置空数组
        userTasks = [];
      }

      // 获取当前用户的工作流
      let workflows: any[] = [];
      try {
        const workflowsResponse: any = await workflowAPI.getWorkflows();
        if (workflowsResponse.success && workflowsResponse.data) {
          let workflowsData = [];
          if (Array.isArray(workflowsResponse.data)) {
            workflowsData = workflowsResponse.data;
          } else if (workflowsResponse.data.workflows && Array.isArray(workflowsResponse.data.workflows)) {
            workflowsData = workflowsResponse.data.workflows;
          }
          
          // 只获取当前用户的工作流，最多10个
          workflows = workflowsData
            .slice(0, 10)
            .map((workflow: any) => ({
              id: workflow.workflow_id || workflow.id,
              baseId: workflow.workflow_base_id || workflow.workflow_id || workflow.id,
              name: workflow.name || '未命名工作流',
              status: workflow.status || 'draft',
              nodeCount: workflow.node_count || workflow.nodeCount || 0,
              executionCount: workflow.execution_count || workflow.executionCount || 0,
              created_at: workflow.created_at
            }));
        }
      } catch (error) {
        console.warn('获取用户工作流失败:', error);
        workflows = [];
      }

      // 更新统计信息
      setStats({
        totalWorkflows: 0, // 可以从API获取
        runningWorkflows: 0,
        totalTasks: userTasks.length,
        pendingTasks: userTasks.filter(task => task.status === 'pending').length,
        onlineUsers: onlineResources.users?.length || 0,
        onlineAgents: agents.length || 0
      });

      setPendingTasks(userTasks);
      setUserWorkflows(workflows);

    } catch (error) {
      console.error('加载仪表板数据失败:', error);
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const getTaskIcon = (priority: string) => {
    switch (priority) {
      case 'high':
        return <CheckSquareOutlined style={{ color: '#ff4d4f' }} />;
      case 'medium':
        return <CheckSquareOutlined style={{ color: '#faad14' }} />;
      case 'low':
        return <CheckSquareOutlined style={{ color: '#52c41a' }} />;
      default:
        return <CheckSquareOutlined style={{ color: '#1890ff' }} />;
    }
  };

  const getTaskStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'default';
      case 'assigned':
        return 'processing';
      case 'in_progress':
        return 'warning';
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };

  const getTaskStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '待处理';
      case 'assigned':
        return '已分配';
      case 'in_progress':
        return '进行中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      default:
        return '未知';
    }
  };

  const getPriorityText = (priority: string) => {
    switch (priority) {
      case 'high':
        return '高';
      case 'medium':
        return '中';
      case 'low':
        return '低';
      default:
        return '普通';
    }
  };

  const formatTimeAgo = (dateString: string) => {
    if (!dateString) return '未知时间';
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffHours / 24);
      
      if (diffDays > 0) {
        return `${diffDays}天前`;
      } else if (diffHours > 0) {
        return `${diffHours}小时前`;
      } else {
        const diffMins = Math.floor(diffMs / (1000 * 60));
        return diffMins > 0 ? `${diffMins}分钟前` : '刚刚';
      }
    } catch {
      return '未知时间';
    }
  };

  const quickActions = [
    {
      title: '创建工作流',
      icon: <PlusOutlined />,
      color: '#1890ff',
      action: () => navigate('/workflow')
    },
    {
      title: '查看任务',
      icon: <CheckSquareOutlined />,
      color: '#52c41a',
      action: () => navigate('/todo')
    },
    {
      title: '管理Agent',
      icon: <RobotOutlined />,
      color: '#722ed1',
      action: () => navigate('/agent')
    },
    {
      title: '资源监控',
      icon: <TeamOutlined />,
      color: '#fa8c16',
      action: () => navigate('/resource')
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* 欢迎标题 */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px' }}>
          欢迎回来，{user?.username || '用户'}！👋
        </h1>
        <p style={{ fontSize: '16px', color: '#666', margin: 0 }}>
          今天是 {new Date().toLocaleDateString('zh-CN', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            weekday: 'long'
          })}
        </p>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="我的任务"
              value={stats.totalTasks}
              prefix={<CheckSquareOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="待处理"
              value={stats.pendingTasks}
              prefix={<RocketOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="在线用户"
              value={stats.onlineUsers}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="在线Agent"
              value={stats.onlineAgents}
              prefix={<RobotOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 快速操作 */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col span={24}>
          <Card title="快速操作" extra={<SettingOutlined />}>
            <Row gutter={[16, 16]}>
              {quickActions.map((action, index) => (
                <Col xs={24} sm={12} md={6} key={index}>
                  <Button
                    type="dashed"
                    size="large"
                    icon={action.icon}
                    onClick={action.action}
                    style={{ 
                      width: '100%', 
                      height: '80px',
                      borderColor: action.color,
                      color: action.color
                    }}
                  >
                    {action.title}
                  </Button>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 最近待办 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card 
            title="最近待办" 
            loading={loading}
            extra={
              <Button 
                type="link" 
                size="small" 
                onClick={() => navigate('/todo')}
              >
                查看全部
              </Button>
            }
          >
            {pendingTasks.length > 0 ? (
              <List
                itemLayout="horizontal"
                dataSource={pendingTasks}
                renderItem={(task) => (
                  <List.Item
                    actions={[
                      <Button 
                        type="link" 
                        size="small"
                        onClick={() => navigate('/todo')}
                      >
                        处理
                      </Button>
                    ]}
                  >
                    <List.Item.Meta
                      avatar={<Avatar icon={getTaskIcon(task.priority)} />}
                      title={
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 'bold' }}>{task.title}</span>
                          <div>
                            <Tag color={getTaskStatusColor(task.status)}>
                              {getTaskStatusText(task.status)}
                            </Tag>
                            <Tag color={task.priority === 'high' ? 'red' : task.priority === 'medium' ? 'orange' : 'green'}>
                              {getPriorityText(task.priority)}优先级
                            </Tag>
                          </div>
                        </div>
                      }
                      description={
                        <div>
                          <div style={{ marginBottom: '4px' }}>
                            工作流: {task.workflow_name}
                          </div>
                          <div style={{ color: '#999', fontSize: '12px', marginBottom: '4px' }}>
                            {task.description}
                          </div>
                          <div style={{ color: '#666', fontSize: '12px' }}>
                            创建时间: {formatTimeAgo(task.created_at)}
                            {task.estimated_duration && (
                              <span style={{ marginLeft: '12px' }}>
                                预计: {task.estimated_duration}分钟
                              </span>
                            )}
                          </div>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
                <CheckSquareOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
                <div>暂无待办任务</div>
                <div style={{ fontSize: '12px', marginTop: '8px' }}>所有任务都已完成！</div>
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card 
            title="我的工作流" 
            loading={loading}
            extra={
              <Button 
                type="link" 
                size="small" 
                onClick={() => navigate('/workflow')}
              >
                查看全部
              </Button>
            }
          >
            {userWorkflows.length > 0 ? (
              <List
                itemLayout="horizontal"
                dataSource={userWorkflows}
                renderItem={(workflow) => (
                  <List.Item
                    actions={[
                      <Button 
                        type="link" 
                        size="small"
                        onClick={() => navigate('/workflow')}
                      >
                        管理
                      </Button>
                    ]}
                  >
                    <List.Item.Meta
                      avatar={
                        <Avatar 
                          icon={<BranchesOutlined />} 
                          style={{ 
                            backgroundColor: workflow.status === 'active' ? '#52c41a' : 
                                            workflow.status === 'draft' ? '#1890ff' : '#faad14' 
                          }} 
                        />
                      }
                      title={
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 'bold' }}>{workflow.name}</span>
                          <Tag color={workflow.status === 'active' ? 'green' : workflow.status === 'draft' ? 'blue' : 'orange'}>
                            {workflow.status === 'active' ? '运行中' : 
                             workflow.status === 'draft' ? '草稿' : 
                             workflow.status === 'completed' ? '已完成' : '暂停'}
                          </Tag>
                        </div>
                      }
                      description={
                        <div>
                          <div style={{ marginBottom: '4px', color: '#666' }}>
                            节点数: {workflow.nodeCount} | 执行次数: {workflow.executionCount}
                          </div>
                          <div style={{ color: '#999', fontSize: '12px' }}>
                            创建时间: {formatTimeAgo(workflow.created_at)}
                          </div>
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
                <BranchesOutlined style={{ fontSize: '48px', marginBottom: '16px' }} />
                <div>暂无工作流</div>
                <div style={{ fontSize: '12px', marginTop: '8px' }}>
                  <Button 
                    type="link" 
                    size="small"
                    onClick={() => navigate('/workflow')}
                  >
                    立即创建
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard; 