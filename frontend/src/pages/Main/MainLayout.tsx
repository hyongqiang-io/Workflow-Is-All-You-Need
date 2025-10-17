import React, { useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import {
  UserOutlined,
  TeamOutlined,
  CheckSquareOutlined,
  BranchesOutlined,
  LogoutOutlined,
  SettingOutlined,
  DashboardOutlined,
  QuestionCircleOutlined,
  FileTextOutlined,
  AppstoreOutlined
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;

const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, logout, getCurrentUser } = useAuthStore();

  useEffect(() => {
    // 获取当前用户信息
    if (!user && isAuthenticated) {
      getCurrentUser().catch(() => {
        navigate('/login');
      });
    }
  }, [user, isAuthenticated, navigate, getCurrentUser]);

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '仪表板',
    },
    {
      key: '/workflow',
      icon: <BranchesOutlined />,
      label: '工作流管理',
    },
    {
      key: '/store',
      icon: <AppstoreOutlined />,
      label: '工作流商店',
    },
    {
      key: '/todo',
      icon: <CheckSquareOutlined />,
      label: '待办任务',
    },
    {
      key: '/my-resources',
      icon: <FileTextOutlined />,
      label: '我的文件',
    },
    {
      key: '/resource',
      icon: <TeamOutlined />,
      label: '资源管理',
    },
    {
      key: '/help',
      icon: <QuestionCircleOutlined />,
      label: '使用说明',
    },
    {
      key: '/profile',
      icon: <UserOutlined />,
      label: '个人中心',
    },
  ];

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout();
      navigate('/login');
    } else if (key === 'profile') {
      navigate('/profile');
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={220} theme="dark" style={{ boxShadow: '2px 0 8px rgba(0,0,0,0.15)' }}>
        <div style={{ 
          height: '64px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          color: 'white',
          fontSize: '18px',
          fontWeight: 'bold',
          borderBottom: '1px solid rgba(255,255,255,0.1)'
        }}>
          <BranchesOutlined style={{ marginRight: '8px' }} />
          工作流平台
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          style={{ 
            height: 'calc(100vh - 64px)', 
            borderRight: 0,
            paddingTop: '16px'
          }}
          items={menuItems}
          onClick={handleMenuClick}
          theme="dark"
        />
      </Sider>
      <Layout>
        <Header style={{ 
          background: '#fff', 
          padding: '0 24px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0,21,41,.08)',
          height: '64px'
        }}>
          <div style={{ fontSize: '16px', fontWeight: '500', color: '#1890ff' }}>
            {menuItems.find(item => item.key === location.pathname)?.label || '仪表板'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Dropdown
              menu={{
                items: userMenuItems,
                onClick: handleUserMenuClick,
              }}
              placement="bottomRight"
            >
              <div style={{ 
                cursor: 'pointer', 
                display: 'flex', 
                alignItems: 'center',
                padding: '8px 12px',
                borderRadius: '6px',
                transition: 'background-color 0.3s'
              }}>
                <Avatar 
                  icon={<UserOutlined />} 
                  style={{ backgroundColor: '#1890ff' }}
                />
                <span style={{ marginLeft: '8px', color: '#333' }}>
                  {user?.username || '用户'}
                </span>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content style={{ 
          margin: '24px', 
          padding: '0',
          background: '#f0f2f5',
          borderRadius: '8px',
          minHeight: 'calc(100vh - 112px)'
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
