import React, { useState } from 'react';
import { Form, Input, Button, message, Card, Typography } from 'antd';
import { UserOutlined, LockOutlined, LoginOutlined } from '@ant-design/icons';
import { useAuthStore } from '../../stores/authStore';
import { useNavigate } from 'react-router-dom';
// import ReactFlowDebug from '../../components/ReactFlowDebug';

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();
  const navigate = useNavigate();

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      console.log('尝试登录:', values.username_or_email);
      await login(values.username_or_email, values.password);
      message.success('登录成功！欢迎回来！');
      // 延迟跳转，让用户看到成功消息
      setTimeout(() => {
        navigate('/');
      }, 1000);
    } catch (e: any) {
      console.error('登录失败:', e);
      const errorMessage = e.response?.data?.detail || 
                          e.response?.data?.message || 
                          e.message || 
                          '用户名或密码错误';
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column',
      justifyContent: 'center', 
      alignItems: 'center', 
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '20px'
    }}>
      {/* <ReactFlowDebug /> */}
      
      {/* 欢迎信息 */}
      <div style={{ 
        textAlign: 'center', 
        marginBottom: '30px',
        color: 'white'
      }}>
        <Title level={1} style={{ color: 'white', marginBottom: '10px' }}>
          🚀 工作流管理平台
        </Title>
        <Text style={{ fontSize: '16px', opacity: 0.9 }}>
          智能工作流，高效协作
        </Text>
      </div>

      <Card style={{ 
        width: '400px',
        borderRadius: '12px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255,255,255,0.2)'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '30px' }}>
          <Title level={2} style={{ marginBottom: '8px' }}>
            <LoginOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
            用户登录
          </Title>
          <Text type="secondary">请输入您的账号信息</Text>
        </div>

        <Form onFinish={onFinish} layout="vertical" size="large">
          <Form.Item 
            name="username_or_email" 
            label="用户名/邮箱" 
            rules={[
              { required: true, message: '请输入用户名或邮箱' },
              { type: 'string', min: 2, message: '用户名至少2个字符' }
            ]}
          >
            <Input 
              prefix={<UserOutlined style={{ color: '#bfbfbf' }} />}
              placeholder="请输入用户名或邮箱"
              autoComplete="username"
            />
          </Form.Item>
          
          <Form.Item 
            name="password" 
            label="密码" 
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' }
            ]}
          >
            <Input.Password 
              prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
              placeholder="请输入密码"
              autoComplete="current-password"
            />
          </Form.Item>
          
          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading} 
              block 
              size="large"
              style={{ 
                height: '48px',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: '500'
              }}
            >
              {loading ? '登录中...' : '立即登录'}
            </Button>
          </Form.Item>
          
          <div style={{ textAlign: 'center' }}>
            <Text type="secondary">还没有账号？</Text>
            <a 
              href="/register" 
              style={{ 
                marginLeft: '8px',
                color: '#1890ff',
                textDecoration: 'none',
                fontWeight: '500'
              }}
            >
              立即注册
            </a>
          </div>
        </Form>

        {/* 测试账号提示 */}
        <div style={{ 
          marginTop: '20px', 
          padding: '12px', 
          background: '#f6ffed', 
          borderRadius: '6px',
          border: '1px solid #b7eb8f'
        }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            💡 测试账号：testuser / testpass123
          </Text>
        </div>
      </Card>

      {/* 底部信息 */}
      <div style={{ 
        marginTop: '30px', 
        textAlign: 'center',
        color: 'white',
        opacity: 0.8
      }}>
        <Text style={{ fontSize: '14px' }}>
          © 2024 工作流管理平台 - 让工作更高效
        </Text>
      </div>
    </div>
  );
};

export default Login;
