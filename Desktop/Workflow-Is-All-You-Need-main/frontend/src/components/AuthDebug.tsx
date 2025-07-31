import React, { useState } from 'react';
import { Button, Card, Typography, Space, message, Divider } from 'antd';
import { useAuthStore } from '../stores/authStore';
import { authAPI } from '../services/api';

const { Text, Title } = Typography;

const AuthDebug: React.FC = () => {
  const { user, token, isAuthenticated, login, register, logout } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [testResults, setTestResults] = useState<string[]>([]);

  const addResult = (result: string) => {
    setTestResults(prev => [...prev, `${new Date().toLocaleTimeString()}: ${result}`]);
  };

  const testBackendConnection = async () => {
    try {
      const response = await fetch('http://localhost:8000/health');
      const data = await response.text();
      addResult(`✅ 后端连接成功: ${response.status} - ${data}`);
      return true;
    } catch (error) {
      addResult(`❌ 后端连接失败: ${error}`);
      return false;
    }
  };

  const testRegisterAPI = async () => {
    setLoading(true);
    try {
      const testUser = {
        username: `testuser${Date.now()}`,
        email: `testuser${Date.now()}@example.com`,
        password: 'password123'
      };

      addResult(`🔄 测试注册: ${testUser.username}`);
      
      const response: any = await authAPI.register(testUser);
      addResult(`✅ 注册API响应: ${JSON.stringify(response)}`);
      
      // 测试登录
      addResult(`🔄 测试登录: ${testUser.username}`);
      const loginResponse: any = await authAPI.login({
        username_or_email: testUser.username,
        password: testUser.password
      });
      addResult(`✅ 登录API响应: ${JSON.stringify(loginResponse)}`);
      
      return testUser;
    } catch (error: any) {
      addResult(`❌ API测试失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const testZustandLogin = async () => {
    setLoading(true);
    try {
      const testUser = `zustandtest${Date.now()}`;
      addResult(`🔄 测试Zustand注册: ${testUser}`);
      
      await register(testUser, `${testUser}@example.com`, 'password123');
      addResult(`✅ Zustand注册成功`);
      
      addResult(`🔄 测试Zustand登录: ${testUser}`);
      await login(testUser, 'password123');
      addResult(`✅ Zustand登录成功`);
      
    } catch (error: any) {
      addResult(`❌ Zustand测试失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const clearResults = () => {
    setTestResults([]);
  };

  return (
    <Card title="🔧 认证调试工具" style={{ margin: '20px', maxWidth: '800px' }}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <div>
          <Title level={4}>当前状态</Title>
          <Text>认证状态: {isAuthenticated ? '✅ 已登录' : '❌ 未登录'}</Text><br/>
          <Text>用户: {user?.username || '无'}</Text><br/>
          <Text>Token: {token ? `${token.substring(0, 20)}...` : '无'}</Text>
        </div>

        <Divider />

        <Space wrap>
          <Button onClick={testBackendConnection} loading={loading}>
            测试后端连接
          </Button>
          <Button onClick={testRegisterAPI} loading={loading}>
            测试API注册/登录
          </Button>
          <Button onClick={testZustandLogin} loading={loading}>
            测试Zustand注册/登录
          </Button>
          <Button onClick={logout}>
            登出
          </Button>
          <Button onClick={clearResults} type="dashed">
            清空结果
          </Button>
        </Space>

        <Divider />

        <div style={{ background: '#f5f5f5', padding: '10px', borderRadius: '4px', maxHeight: '300px', overflow: 'auto' }}>
          <Title level={5}>测试结果:</Title>
          {testResults.length === 0 ? (
            <Text type="secondary">暂无测试结果</Text>
          ) : (
            testResults.map((result, index) => (
              <div key={index} style={{ marginBottom: '4px', fontSize: '12px' }}>
                {result}
              </div>
            ))
          )}
        </div>
      </Space>
    </Card>
  );
};

export default AuthDebug;