import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Spin, Alert } from 'antd';

const FeishuCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const code = searchParams.get('code');
        const state = searchParams.get('state');

        if (!code) {
          setError('授权失败：未获取到授权码');
          setLoading(false);
          return;
        }

        // 发送 code 到后端换取 access_token
        const response = await fetch('/api/feishu/token', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json' 
          },
          body: JSON.stringify({ code, state }),
          credentials: 'include'
        });

        if (!response.ok) {
          throw new Error(`请求失败: ${response.status}`);
        }

        const result = await response.json();
        
        if (result.success) {
          // 登录成功，跳转到首页
          navigate('/');
        } else {
          setError(result.message || '登录失败');
        }
      } catch (err) {
        console.error('飞书登录回调处理失败:', err);
        setError(err instanceof Error ? err.message : '网络错误');
      } finally {
        setLoading(false);
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        flexDirection: 'column',
        gap: '16px'
      }}>
        <Spin size="large" />
        <div>正在处理飞书登录...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        padding: '20px'
      }}>
        <Alert
          message="登录失败"
          description={error}
          type="error"
          showIcon
          action={
            <button 
              onClick={() => navigate('/login')}
              style={{
                background: 'none',
                border: '1px solid #d9d9d9',
                borderRadius: '6px',
                padding: '4px 15px',
                cursor: 'pointer'
              }}
            >
              返回登录
            </button>
          }
        />
      </div>
    );
  }

  return null;
};

export default FeishuCallback;