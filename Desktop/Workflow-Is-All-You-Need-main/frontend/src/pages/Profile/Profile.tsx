import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Row, Col, message, Switch, Divider } from 'antd';
import { UserOutlined, RobotOutlined, SettingOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../stores/authStore';
import { userAPI } from '../../services/api';

const { TextArea } = Input;

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
  const { user, setUser, isAuthenticated, getCurrentUser } = useAuthStore();

  useEffect(() => {
    fetchUserProfile();
    fetchProcessors();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isAuthenticated]);

  const fetchUserProfile = async () => {
    console.log('🔍 开始fetchUserProfile - 当前状态:', {
      user: user,
      isAuthenticated: isAuthenticated,
      userExists: !!user,
      userIdExists: user?.user_id
    });
    
    if (!user || !user.user_id) {
      console.log('❌ 用户信息不完整，跳过加载:', user);
      // 如果当前用户信息不完整，先尝试获取当前用户信息
      if (isAuthenticated && !user) {
        console.log('🔄 尝试获取当前用户信息...');
        try {
          await getCurrentUser();
          // 获取用户信息后，用户信息应该会更新，让useEffect重新触发
          return;
        } catch (error) {
          console.error('❌ 获取当前用户信息失败:', error);
        }
      }
      setLoading(false);
      return;
    }
    
    try {
      console.log('开始获取用户资料，用户ID:', user.user_id);
      
      const response: any = await userAPI.getUser(user.user_id);
      console.log('用户信息API响应:', response);
      
      if (response && response.success && response.data) {
        // 后端直接返回用户数据，不包装在 user 字段中
        const userData = response.data;
        console.log('设置用户资料数据:', userData);
        setUserProfile(userData);
        
        // 使用实际存在的字段设置表单 - 确保所有基本字段都有值
        const formData = {
          username: userData.username || '',
          email: userData.email || '',
          terminal_endpoint: userData.terminal_endpoint || '',
          description: userData.description || '',
          role: userData.role || '',
          profile: userData.profile ? JSON.stringify(userData.profile, null, 2) : '{}',
        };
        
        console.log('设置表单数据:', formData);
        userForm.setFieldsValue(formData);
        
        // 强制表单重新渲染
        userForm.validateFields().catch(() => {});
      } else {
        console.warn('API响应格式不正确:', response);
      }
    } catch (error) {
      console.error('获取用户资料失败:', error);
      message.error('获取用户资料失败');
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
    console.log('🔍 profile字段原始值:', values.profile, '类型:', typeof values.profile);
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

      // 暂时跳过profile字段处理，避免验证错误
      // TODO: 稍后修复profile字段的JSON处理逻辑
      console.log('🚫 暂时跳过profile字段，values.profile =', values.profile);

      console.log('🚀 发送用户更新请求:', updateData);
      console.log('🔍 updateData中是否包含profile:', 'profile' in updateData);
      console.log('🔍 profile的值和类型:', updateData.profile, typeof updateData.profile);
      
      const response: any = await userAPI.updateUser(userProfile.user_id, updateData);
      console.log('用户更新响应:', response);
      console.log('响应类型检查:', {
        hasResponse: !!response,
        hasSuccessField: response && response.hasOwnProperty('success'),
        successValue: response?.success,
        responseKeys: response ? Object.keys(response) : 'null',
        responseData: response?.data
      });

      // 检查响应格式 - 后端返回的是统一的BaseResponse格式
      if (response && response.success === true) {
        console.log('✅ 进入成功分支，准备显示成功消息');
        
        // 使用服务器返回的数据更新本地状态
        if (response.data) {
          // 后端的 user.py 直接返回用户数据，不包装在 user 字段中
          const updatedUserData = response.data;
          console.log('更新的用户数据:', updatedUserData);
          setUserProfile(updatedUserData);
          // 更新全局用户状态
          setUser({
            ...user!,
            ...updatedUserData
          });
          console.log('用户资料更新成功，新数据:', updatedUserData);
        }
        
        // 强制显示成功消息
        console.log('🎉 即将显示成功消息');
        message.success('🎉 用户信息更新成功！数据已保存');
        
        // 重新获取最新数据确保同步
        setTimeout(() => {
          fetchUserProfile();
        }, 1000);
      } else {
        console.error('❌ 更新失败，响应:', response);
        message.error(response?.message || '更新失败');
      }
    } catch (error: any) {
      console.error('用户信息更新异常:', error);
      console.error('错误详情:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        headers: error.response?.headers
      });
      
      // 处理422验证错误的详细信息
      if (error.response?.status === 422) {
        console.error('🔍 完整的422错误数据:', error.response?.data);
        const detail = error.response?.data?.detail;
        
        if (Array.isArray(detail)) {
          // Pydantic验证错误格式
          console.error('📋 Pydantic验证错误列表:', detail);
          // 显示每个错误的详细信息
          detail.forEach((err, index) => {
            console.error(`错误 ${index + 1}:`, {
              字段: err.loc,
              消息: err.msg,
              类型: err.type,
              完整错误: err
            });
          });
          
          const validationErrors = detail.map((err: any) => 
            `${err.loc?.join('.')} - ${err.msg}`
          ).join('; ');
          message.error(`数据验证失败: ${validationErrors}`);
        } else if (typeof detail === 'string') {
          console.error('📋 字符串错误信息:', detail);
          message.error(`数据验证失败: ${detail}`);
        } else {
          console.error('📋 未知错误格式:', detail);
          message.error(`数据验证失败: ${JSON.stringify(detail) || '请检查输入数据格式'}`);
        }
      } else if (error.response?.status === 500) {
        console.error('🔍 500错误详情:', error.response?.data);
        message.error(`服务器内部错误: ${error.response?.data?.detail || error.message}`);
      } else {
        message.error(error.response?.data?.detail || error.message || '更新失败，请重试');
      }
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

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>个人信息管理</h2>
      
      {/* 调试信息 - 可以在修复后删除 */}
      <div style={{ 
        background: '#f0f0f0', 
        padding: '10px', 
        margin: '10px 0', 
        borderRadius: '4px',
        fontSize: '12px',
        fontFamily: 'monospace'
      }}>
        <strong>调试信息:</strong><br/>
        - 认证状态: {isAuthenticated ? '✅ 已认证' : '❌ 未认证'}<br/>
        - 用户对象: {user ? '✅ 存在' : '❌ 不存在'}<br/>
        - 用户ID: {user?.user_id || '无'}<br/>
        - 用户名: {user?.username || '无'}<br/>
        - 邮箱: {user?.email || '无'}<br/>
        - 用户资料加载状态: {userProfile ? '✅ 已加载' : '❌ 未加载'}<br/>
        - 表单当前值: {JSON.stringify(userForm.getFieldsValue())}
      </div>
      
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
                <Input placeholder="如: admin, user, developer" />
              </Form.Item>

              <Form.Item 
                name="profile" 
                label="扩展信息 (JSON格式)"
                tooltip="以JSON格式存储的扩展用户信息"
              >
                <TextArea 
                  rows={4} 
                  placeholder='{"skills": ["Python", "React"], "location": "Beijing"}' 
                  style={{ fontFamily: 'monospace' }}
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