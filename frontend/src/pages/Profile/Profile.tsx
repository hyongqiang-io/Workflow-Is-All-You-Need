import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Row, Col, message, Switch, Divider, Statistic, Avatar, Typography, Space, Tag } from 'antd';
import { UserOutlined, RobotOutlined, SettingOutlined, CalendarOutlined, MailOutlined, CheckCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../stores/authStore';
import { userAPI } from '../../services/api';

const { TextArea } = Input;
const { Title, Text } = Typography;

// 根据真实数据库结构定义接口
interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  terminal_endpoint?: string;
  profile?: Record<string, any>;
  description?: string;
  role?: string;
  status: boolean;
  created_at: string;
  updated_at: string;
}

interface ProcessorAgent {
  id: string;
  name: string;
  type: string;
  entity_type: string;
  entity_id: string;
  description?: string;
  capabilities?: string[];
  status: boolean;
}

const Profile: React.FC = () => {
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [processors, setProcessors] = useState<ProcessorAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [userLoading, setUserLoading] = useState(false);
  const [userForm] = Form.useForm();
  const { user, setUser, getCurrentUser } = useAuthStore();

  useEffect(() => {
    fetchUserProfile();
    fetchProcessors();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchUserProfile = async () => {
    // 首先确保有登录用户信息
    if (!user || !user.user_id) {
      console.log('用户信息不完整，尝试获取当前用户信息:', user);
      try {
        // 如果没有用户信息，尝试从认证服务获取
        await getCurrentUser();
        // 获取成功后，user会被更新，我们可以继续
      } catch (error) {
        console.error('无法获取当前用户信息:', error);
        message.error('请重新登录');
        setLoading(false);
        return;
      }
    }

    // 再次检查user是否已更新
    const currentUser = useAuthStore.getState().user;
    if (!currentUser || !currentUser.user_id) {
      console.error('仍然无法获取用户信息');
      message.error('用户信息获取失败，请重新登录');
      setLoading(false);
      return;
    }
    
    try {
      console.log('开始获取用户详细资料，用户ID:', currentUser.user_id);
      
      const response: any = await userAPI.getUser(currentUser.user_id);
      console.log('用户详细信息API响应:', response);
      
      if (response && response.success !== false && response.data) {
        const userData = response.data;
        console.log('设置用户资料数据:', userData);
        setUserProfile(userData);
        
        // 使用实际存在的字段设置表单
        userForm.setFieldsValue({
          username: userData.username || currentUser.username || '',
          email: userData.email || currentUser.email || '',
          terminal_endpoint: userData.terminal_endpoint || '',
          description: userData.description || '',
          role: userData.role || currentUser.role || '',
          profile: userData.profile ? JSON.stringify(userData.profile, null, 2) : '',
        });
      } else {
        // 如果API调用失败，使用authStore中的基础信息
        console.log('API调用失败，使用基础用户信息');
        const basicUserData: UserProfile = {
          user_id: currentUser.user_id,
          username: currentUser.username,
          email: currentUser.email,
          role: currentUser.role || undefined,
          status: true,
          created_at: currentUser.created_at,
          updated_at: currentUser.created_at,
          description: '',
          terminal_endpoint: '',
          profile: undefined
        };
        
        setUserProfile(basicUserData);
        userForm.setFieldsValue({
          username: currentUser.username || '',
          email: currentUser.email || '',
          terminal_endpoint: '',
          description: '',
          role: currentUser.role || '',
          profile: '',
        });
        
        message.warning('使用基础用户信息，部分功能可能受限');
      }
    } catch (error) {
      console.error('获取用户资料失败:', error);
      message.error('获取用户资料失败');
      
      // 出错时，至少显示基础信息
      const currentUser = useAuthStore.getState().user;
      if (currentUser) {
        const basicUserData: UserProfile = {
          user_id: currentUser.user_id,
          username: currentUser.username,
          email: currentUser.email,
          role: currentUser.role || undefined,
          status: true,
          created_at: currentUser.created_at,
          updated_at: currentUser.created_at,
          description: '',
          terminal_endpoint: '',
          profile: undefined
        };
        
        setUserProfile(basicUserData);
        userForm.setFieldsValue({
          username: currentUser.username || '',
          email: currentUser.email || '',
          terminal_endpoint: '',
          description: '',
          role: currentUser.role || '',
          profile: '',
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchProcessors = async () => {
    try {
      // 使用现有的processors API获取Agent信息
      const response = await fetch('/api/processors/available', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('Processors API响应:', data);
        
        if (data.success && data.data && data.data.processors) {
          // 筛选出Agent类型的处理器
          const agentProcessors = data.data.processors.filter((p: any) => 
            p.entity_type === 'agent' || p.type === 'agent'
          );
          console.log('Agent处理器:', agentProcessors);
          setProcessors(agentProcessors);
        }
      }
    } catch (error) {
      console.error('获取处理器信息失败:', error);
    }
  };

  const handleUserUpdate = async (values: any) => {
    if (!userProfile || !userProfile.user_id) {
      message.error('用户信息不完整，请刷新页面重试');
      return;
    }

    console.log('开始更新用户信息，表单值:', values);
    console.log('用户ID:', userProfile.user_id);
    setUserLoading(true);

    try {
      // 准备更新数据 - 只包含数据库中实际存在的字段
      const updateData: any = {
        username: values.username,
        email: values.email,
        description: values.description,
      };

      // 可选字段
      if (values.terminal_endpoint) {
        updateData.terminal_endpoint = values.terminal_endpoint;
      }

      // 处理profile JSON
      if (values.profile) {
        try {
          updateData.profile = JSON.parse(values.profile);
        } catch (e) {
          message.error('Profile JSON格式不正确');
          setUserLoading(false);
          return;
        }
      }

      console.log('发送用户更新请求:', updateData);
      const response: any = await userAPI.updateUser(userProfile.user_id, updateData);
      console.log('用户更新响应:', response);
      console.log('响应类型检查:', {
        hasResponse: !!response,
        hasSuccessField: response && response.hasOwnProperty('success'),
        successValue: response?.success,
        responseKeys: response ? Object.keys(response) : 'null'
      });

      // 确保成功消息显示 - 简化条件判断
      if (response && (response.success === true || response.success === undefined)) {
        console.log('✅ 进入成功分支，准备显示成功消息');
        
        // 使用服务器返回的数据更新本地状态
        if (response.data) {
          setUserProfile(response.data);
          // 更新全局用户状态
          setUser({
            ...user!,
            username: response.data.username,
            email: response.data.email,
            role: response.data.role
          });
          console.log('用户资料更新成功，新数据:', response.data);
        }
        
        // 强制显示成功消息
        console.log('🎉 即将显示成功消息');
        message.success({
          content: '用户信息更新成功！',
          duration: 3,
          icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
        });
        
        // 重新获取最新数据确保同步
        setTimeout(() => {
          fetchUserProfile();
        }, 1000);
      } else {
        console.error('❌ 更新失败，响应:', response);
        message.error({
          content: response?.message || '更新失败，请检查网络连接',
          duration: 4,
        });
      }
    } catch (error: any) {
      console.error('用户信息更新异常:', error);
      message.error(error.response?.data?.detail || error.message || '更新失败，请重试');
    } finally {
      setUserLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <div>加载中...</div>
      </div>
    );
  }

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await Promise.all([fetchUserProfile(), fetchProcessors()]);
      message.success('信息已刷新');
    } catch (error) {
      message.error('刷新失败');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <Title level={2} style={{ margin: 0 }}>个人信息管理</Title>
        <Button 
          icon={<ReloadOutlined />} 
          onClick={handleRefresh}
          loading={loading}
        >
          刷新信息
        </Button>
      </div>
      
      {/* 用户概览卡片 */}
      {userProfile && (
        <Card style={{ marginBottom: '24px' }}>
          <Row align="middle">
            <Col span={4}>
              <Avatar 
                size={80} 
                icon={<UserOutlined />} 
                style={{ 
                  backgroundColor: '#1890ff',
                  fontSize: '32px'
                }}
              />
            </Col>
            <Col span={12}>
              <Space direction="vertical" size="small">
                <Title level={3} style={{ margin: 0 }}>
                  {userProfile.username}
                </Title>
                <Space>
                  <MailOutlined style={{ color: '#666' }} />
                  <Text type="secondary">{userProfile.email}</Text>
                </Space>
                <Space>
                  <CalendarOutlined style={{ color: '#666' }} />
                  <Text type="secondary">
                    加入时间: {new Date(userProfile.created_at).toLocaleDateString('zh-CN')}
                  </Text>
                </Space>
                {userProfile.role && (
                  <Tag color={userProfile.role === 'admin' ? 'red' : 'blue'}>
                    {userProfile.role.toUpperCase()}
                  </Tag>
                )}
              </Space>
            </Col>
            <Col span={8}>
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="账户状态"
                    value={userProfile.status ? '正常' : '禁用'}
                    prefix={<CheckCircleOutlined style={{ color: userProfile.status ? '#52c41a' : '#f5222d' }} />}
                    valueStyle={{ color: userProfile.status ? '#52c41a' : '#f5222d' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="关联Agent"
                    value={processors.length}
                    prefix={<RobotOutlined />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
              </Row>
            </Col>
          </Row>
        </Card>
      )}
      
      <Row gutter={24}>
        {/* 用户信息编辑 */}
        <Col span={16}>
          <Card title={
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <UserOutlined style={{ marginRight: '8px' }} />
              <span>用户基本信息</span>
            </div>
          }>
            <Form 
              form={userForm} 
              layout="vertical" 
              onFinish={handleUserUpdate}
            >
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item 
                    name="username" 
                    label="用户名" 
                    rules={[{ required: true, message: '请输入用户名' }]}
                  >
                    <Input prefix={<UserOutlined />} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item 
                    name="email" 
                    label="邮箱" 
                    rules={[
                      { required: true, message: '请输入邮箱' },
                      { type: 'email', message: '请输入有效的邮箱地址' }
                    ]}
                  >
                    <Input />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item 
                name="terminal_endpoint" 
                label="终端端点"
                tooltip="用于系统连接的终端地址"
              >
                <Input placeholder="请输入终端端点地址" />
              </Form.Item>
              
              <Form.Item 
                name="description" 
                label="个人描述"
              >
                <TextArea rows={3} placeholder="请输入个人描述" />
              </Form.Item>

              <Form.Item 
                name="role" 
                label="用户角色"
                tooltip="用户在系统中的角色"
              >
                <Input 
                  placeholder="如: admin, user, developer" 
                  addonBefore="Role"
                />
              </Form.Item>

              <Form.Item 
                name="profile" 
                label="扩展信息 (JSON格式)"
                tooltip="以JSON格式存储的扩展用户信息"
                rules={[
                  {
                    validator: (_, value) => {
                      if (!value || value.trim() === '') {
                        return Promise.resolve();
                      }
                      try {
                        JSON.parse(value);
                        return Promise.resolve();
                      } catch (error) {
                        return Promise.reject(new Error('请输入有效的JSON格式'));
                      }
                    }
                  }
                ]}
              >
                <TextArea 
                  rows={4} 
                  placeholder='{"skills": ["Python", "React"], "location": "Beijing", "department": "IT"}' 
                  style={{ fontFamily: 'Monaco, Consolas, "Courier New", monospace', fontSize: '13px' }}
                />
              </Form.Item>
              
              <Form.Item>
                <Button 
                  type="primary" 
                  htmlType="submit"
                  loading={userLoading}
                  size="large"
                  style={{ width: '100%' }}
                >
                  {userLoading ? '保存中...' : '保存用户信息'}
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>
        
        {/* 系统信息和Agent信息 */}
        <Col span={8}>
          {/* 系统状态 */}
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <SettingOutlined style={{ marginRight: '8px' }} />
                <span>系统状态</span>
              </div>
            }
            style={{ marginBottom: '16px' }}
          >
            {userProfile && (
              <div>
                <p><strong>账户状态:</strong> 
                  <Switch 
                    checked={userProfile.status} 
                    disabled 
                    style={{ marginLeft: '8px' }}
                  />
                  {userProfile.status ? '激活' : '禁用'}
                </p>
                <p><strong>创建时间:</strong><br/>
                  {new Date(userProfile.created_at).toLocaleString('zh-CN')}
                </p>
                <p><strong>更新时间:</strong><br/>
                  {new Date(userProfile.updated_at).toLocaleString('zh-CN')}
                </p>
              </div>
            )}
          </Card>

          {/* Agent信息展示 */}
          <Card 
            title={
              <div style={{ display: 'flex', alignItems: 'center' }}>
                <RobotOutlined style={{ marginRight: '8px' }} />
                <span>关联的Agent</span>
              </div>
            }
          >
            {processors.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
                <RobotOutlined style={{ fontSize: '24px', marginBottom: '8px' }} />
                <p>暂无关联的Agent</p>
                <p style={{ fontSize: '12px' }}>
                  注意: Agent管理功能需要独立的API支持
                </p>
              </div>
            ) : (
              <div>
                {processors.map((processor, index) => (
                  <div 
                    key={processor.id} 
                    style={{ 
                      padding: '8px', 
                      border: '1px solid #d9d9d9', 
                      borderRadius: '4px',
                      marginBottom: index < processors.length - 1 ? '8px' : '0'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                      <RobotOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
                      <strong>{processor.name}</strong>
                    </div>
                    {processor.description && (
                      <p style={{ margin: '4px 0', fontSize: '12px', color: '#666' }}>
                        {processor.description}
                      </p>
                    )}
                    <div style={{ fontSize: '11px', color: '#999' }}>
                      ID: {processor.entity_id}
                    </div>
                    <div style={{ fontSize: '11px', color: '#999' }}>
                      状态: {processor.status ? '激活' : '禁用'}
                    </div>
                  </div>
                ))}
                <Divider style={{ margin: '12px 0' }} />
                <div style={{ fontSize: '12px', color: '#666', textAlign: 'center' }}>
                  💡 Agent编辑功能需要后端API支持<br/>
                  当前只能查看关联的Agent信息
                </div>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Profile;