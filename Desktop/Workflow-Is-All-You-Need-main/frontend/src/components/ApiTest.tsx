import React, { useState } from 'react';
import { Button, Card, message, Space } from 'antd';
import { authAPI } from '../services/api';

const ApiTest: React.FC = () => {
  const [loading, setLoading] = useState(false);

  const testConnection = async () => {
    setLoading(true);
    try {
      // 测试注册
      const registerData = {
        username: `testuser_${Date.now()}`,
        email: `test_${Date.now()}@example.com`,
        password: '123456'
      };
      
      console.log('测试注册:', registerData);
      const registerResponse = await authAPI.register(registerData);
      console.log('注册响应:', registerResponse);
      message.success('注册测试成功');
      
      // 测试登录
      const loginData = {
        username_or_email: registerData.username,
        password: registerData.password
      };
      
      console.log('测试登录:', loginData);
      const loginResponse = await authAPI.login(loginData);
      console.log('登录响应:', loginResponse);
      message.success('登录测试成功');
      
    } catch (error: any) {
      console.error('API测试失败:', error);
      const errorMessage = error.response?.data?.detail || 
                          error.response?.data?.message || 
                          error.message || 
                          'API测试失败';
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="API连接测试" style={{ margin: '20px' }}>
      <Space>
        <Button 
          type="primary" 
          loading={loading} 
          onClick={testConnection}
        >
          测试注册和登录
        </Button>
        <div>
          请确保后端服务运行在 http://localhost:8000
        </div>
      </Space>
    </Card>
  );
};

export default ApiTest; 