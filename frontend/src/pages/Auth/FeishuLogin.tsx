import React, { useEffect } from 'react';
import { Button, Card, Typography, Space, message } from 'antd';
import { MessageOutlined, LoginOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

const FeishuLogin: React.FC<{ autoLogin?: boolean }> = ({ autoLogin = false }) => {
  const navigate = useNavigate();

  // 检测是否在飞书客户端内
  const isInFeishuClient = () => {
    // 检测飞书客户端环境
    const userAgent = navigator.userAgent.toLowerCase();
    const isFeishu = userAgent.includes('feishu') || userAgent.includes('lark');
    
    // 检测飞书WebView环境
    const isFeishuWebView = window.location.href.includes('feishu.cn') || 
                           window.location.href.includes('larksuite.com');
    
    // 检测飞书客户端特有的全局变量
    const hasFeishuGlobal = typeof (window as any).tt !== 'undefined' || 
                           typeof (window as any).feishu !== 'undefined';
    
    // 检测URL参数中的飞书标识
    const urlParams = new URLSearchParams(window.location.search);
    const isFeishuParam = urlParams.get('from') === 'feishu' || 
                          urlParams.get('source') === 'feishu';
    
    return isFeishu || isFeishuWebView || hasFeishuGlobal || isFeishuParam;
  };

  // 自动登录处理
  useEffect(() => {
    // 如果是自动登录模式或在飞书客户端内，自动跳转到登录
    if (autoLogin || isInFeishuClient()) {
      const messageText = autoLogin ? '飞书客户端自动登录模式' : '检测到飞书客户端，正在自动登录...';
      message.info(messageText);
      // 延迟一下让用户看到提示
      setTimeout(() => {
        handleFeishuLogin();
      }, 1000);
    }
  }, [autoLogin]);

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
