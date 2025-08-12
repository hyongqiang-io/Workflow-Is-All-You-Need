import React, { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import { useAuthStore } from '../stores/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, loading, checkAuth } = useAuthStore();
  const [isChecking, setIsChecking] = useState(true);
  const location = useLocation();

  useEffect(() => {
    const verifyAuth = async () => {
      console.log('ProtectedRoute: 开始验证身份', { isAuthenticated });
      
      if (!isAuthenticated) {
        try {
          // 添加超时处理
          const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('认证检查超时')), 10000)
          );
          
          const authPromise = checkAuth();
          const isAuth = await Promise.race([authPromise, timeoutPromise]);
          
          console.log('ProtectedRoute: 认证检查结果', isAuth);
          setIsChecking(false);
        } catch (error) {
          console.error('ProtectedRoute: 认证检查失败', error);
          setIsChecking(false);
        }
      } else {
        console.log('ProtectedRoute: 已认证，跳过检查');
        setIsChecking(false);
      }
    };

    verifyAuth();
  }, [isAuthenticated, checkAuth]);

  if (loading || isChecking) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh' 
      }}>
        <Spin size="large" spinning={true}>
          <div style={{ padding: '20px' }}>正在验证身份...</div>
        </Spin>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute; 