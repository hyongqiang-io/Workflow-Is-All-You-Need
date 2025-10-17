import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

// 页面组件
import Login from './pages/Auth/Login';
import Register from './pages/Auth/Register';
import FeishuCallback from './pages/Auth/FeishuCallback';
import FeishuLogin from './pages/Auth/FeishuLogin';
import MainLayout from './pages/Main/MainLayout';
import Dashboard from './pages/Main/Dashboard';
import Workflow from './pages/Workflow/Workflow';
import Todo from './pages/Main/Todo';
import Resource from './pages/Main/Resource';
import MyResources from './pages/Main/MyResources';
import Profile from './pages/Profile/Profile';
import TaskFlow from './pages/Workflow/TaskFlow';
import AgentManagement from './pages/Agent/AgentManagement';
import Help from './pages/Main/Help';
import WorkflowStore from './pages/Store/WorkflowStore';
import WorkflowStoreDetail from './pages/Store/WorkflowStoreDetail';

// 组件
import ProtectedRoute from './components/ProtectedRoute';

// 样式
import './App.css';

function App() {
  console.log('🔄 App组件已重新加载 - 时间:', new Date().toLocaleString());
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/feishu-login" element={<FeishuLogin />} />
          <Route path="/feishu-auto-login" element={<FeishuLogin autoLogin={true} />} />
          <Route path="/auth/feishu/callback" element={<FeishuCallback />} />
          <Route path="/" element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }>
            <Route index element={<Dashboard />} />
            <Route path="profile" element={<Profile />} />
            <Route path="resource" element={<Resource />} />
            <Route path="my-resources" element={<MyResources />} />
            <Route path="workflow" element={<Workflow />} />
            <Route path="workflow/:workflowId/task-flow" element={<TaskFlow />} />
            <Route path="todo" element={<Todo />} />
            <Route path="agent" element={<AgentManagement />} />
            <Route path="help" element={<Help />} />
            <Route path="store" element={<WorkflowStore />} />
            <Route path="store/workflow/:storeId" element={<WorkflowStoreDetail />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
