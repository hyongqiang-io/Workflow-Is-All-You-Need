import React, { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { useAuthStore } from '../../stores/authStore';
import { useNavigate } from 'react-router-dom';

const Register: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const { register } = useAuthStore();
  const navigate = useNavigate();

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      console.log('尝试注册:', values.username, values.email);
      await register(values.username, values.email, values.password);
      message.success('注册成功，请登录');
      navigate('/login');
    } catch (e: any) {
      console.error('注册失败:', e);
      const errorMessage = e.response?.data?.detail || 
                          e.response?.data?.message || 
                          e.message || 
                          '注册失败';
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      minHeight: '100vh',
      background: '#f0f2f5'
    }}>
      <div style={{ 
        background: 'white', 
        padding: '40px', 
        borderRadius: '8px', 
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        width: '400px'
      }}>
        <h2 style={{ textAlign: 'center', marginBottom: '30px' }}>注册</h2>
        <Form onFinish={onFinish} layout="vertical">
          <Form.Item 
            name="username" 
            label="用户名" 
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input size="large" />
          </Form.Item>
          <Form.Item 
            name="email" 
            label="邮箱" 
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' }
            ]}
          >
            <Input size="large" />
          </Form.Item>
          <Form.Item 
            name="password" 
            label="密码" 
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6位' }
            ]}
          >
            <Input.Password size="large" />
          </Form.Item>
          <Form.Item 
            name="confirm" 
            label="确认密码" 
            dependencies={["password"]} 
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject('两次输入密码不一致');
                },
              }),
            ]}
          >
            <Input.Password size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              注册
            </Button>
          </Form.Item>
          <div style={{ textAlign: 'center' }}>
            <a href="/login">已有账号？立即登录</a>
          </div>
        </Form>
      </div>
    </div>
  );
};

export default Register;
