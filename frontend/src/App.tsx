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
import Profile from './pages/Profile/Profile';
import TaskFlow from './pages/Workflow/TaskFlow';

// 组件
import ProtectedRoute from './components/ProtectedRoute';

// 样式
import './App.css';

function App() {
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
            <Route path="workflow" element={<Workflow />} />
            <Route path="workflow/:workflowId/task-flow" element={<TaskFlow />} />
            <Route path="todo" element={<Todo />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
