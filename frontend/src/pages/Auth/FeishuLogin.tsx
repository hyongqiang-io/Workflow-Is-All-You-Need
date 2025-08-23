import React from 'react';
import { Button, Card, Typography, Space } from 'antd';
import { MessageOutlined, LoginOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

const FeishuLogin: React.FC = () => {
  const navigate = useNavigate();

  const handleFeishuLogin = () => {
    // 直接跳转到后端的飞书登录接口
    window.location.href = '/api/feishu/login';
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
      
      <div style={{ 
        textAlign: 'center', 
        marginBottom: '30px',
        color: 'white'
      }}>
        <Title level={1} style={{ color: 'white', marginBottom: '10px' }}>
          🚀 工作流管理平台
        </Title>
        <Text style={{ fontSize: '16px', opacity: 0.9 }}>
          通过飞书一键登录，开启高效协作
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
            <MessageOutlined style={{ marginRight: '8px', color: '#00d6b9' }} />
            飞书登录
          </Title>
          <Text type="secondary">使用飞书账号快速登录系统</Text>
        </div>

        <Space direction="vertical" style={{ width: '100%' }}>
          <Button 
            type="primary" 
            size="large"
            icon={<LoginOutlined />}
            onClick={handleFeishuLogin}
            style={{ 
              height: '48px',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: '500',
              backgroundColor: '#00d6b9',
              borderColor: '#00d6b9'
            }}
            block
          >
            飞书一键登录
          </Button>
          
          <Button 
            type="default" 
            size="large"
            onClick={() => navigate('/login')}
            style={{ 
              height: '48px',
              borderRadius: '8px',
              fontSize: '16px'
            }}
            block
          >
            返回普通登录
          </Button>
        </Space>

        <div style={{ 
          marginTop: '20px', 
          padding: '12px', 
          background: '#f0f9ff', 
          borderRadius: '6px',
          border: '1px solid #bae6fd'
        }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            💡 使用飞书登录将自动创建账号，无需手动注册
          </Text>
        </div>
      </Card>

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

export default FeishuLogin;
