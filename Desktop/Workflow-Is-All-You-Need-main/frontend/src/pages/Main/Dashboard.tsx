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
import { resourceAPI, agentAPI } from '../../services/api';

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
  const [recentActivities, setRecentActivities] = useState<any[]>([]);

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

      // 更新统计信息
      setStats({
        totalWorkflows: 0, // 可以从API获取
        runningWorkflows: 0,
        totalTasks: 0,
        pendingTasks: 0,
        onlineUsers: onlineResources.users?.length || 0,
        onlineAgents: agents.length || 0
      });

      // 模拟最近活动
      setRecentActivities([
        {
          id: 1,
          type: 'workflow',
          title: '数据分析工作流',
          status: 'completed',
          time: '2小时前',
          user: '张三'
        },
        {
          id: 2,
          type: 'task',
          title: '文档审核任务',
          status: 'in_progress',
          time: '1小时前',
          user: '李四'
        },
        {
          id: 3,
          type: 'agent',
          title: 'AI助手已上线',
          status: 'online',
          time: '30分钟前',
          user: '系统'
        }
      ]);

    } catch (error) {
      console.error('加载仪表板数据失败:', error);
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'workflow':
        return <BranchesOutlined style={{ color: '#1890ff' }} />;
      case 'task':
        return <CheckSquareOutlined style={{ color: '#52c41a' }} />;
      case 'agent':
        return <RobotOutlined style={{ color: '#722ed1' }} />;
      default:
        return <UserOutlined />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'in_progress':
        return 'processing';
      case 'online':
        return 'success';
      case 'failed':
        return 'error';
      default:
        return 'default';
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
              title="总工作流"
              value={stats.totalWorkflows}
              prefix={<BranchesOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="运行中"
              value={stats.runningWorkflows}
              prefix={<RocketOutlined />}
              valueStyle={{ color: '#52c41a' }}
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

      {/* 最近活动 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="最近活动" loading={loading}>
            <List
              itemLayout="horizontal"
              dataSource={recentActivities}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Avatar icon={getActivityIcon(item.type)} />}
                    title={
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>{item.title}</span>
                        <Tag color={getStatusColor(item.status)}>
                          {item.status === 'completed' ? '已完成' :
                           item.status === 'in_progress' ? '进行中' :
                           item.status === 'online' ? '在线' : item.status}
                        </Tag>
                      </div>
                    }
                    description={
                      <div>
                        <div>操作人: {item.user}</div>
                        <div style={{ color: '#999', fontSize: '12px' }}>{item.time}</div>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="系统状态" loading={loading}>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span>系统健康度</span>
                <span>95%</span>
              </div>
              <Progress percent={95} status="active" />
            </div>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span>任务完成率</span>
                <span>88%</span>
              </div>
              <Progress percent={88} />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span>资源利用率</span>
                <span>72%</span>
              </div>
              <Progress percent={72} />
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard; 