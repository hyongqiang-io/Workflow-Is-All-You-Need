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
      if (!isAuthenticated) {
        try {
          const isAuth = await checkAuth();
          if (!isAuth) {
            setIsChecking(false);
          } else {
            setIsChecking(false);
          }
        } catch (error) {
          setIsChecking(false);
        }
      } else {
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