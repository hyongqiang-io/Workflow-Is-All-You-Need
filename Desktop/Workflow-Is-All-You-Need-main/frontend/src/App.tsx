import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

// 页面组件
import Login from './pages/Auth/Login';
import Register from './pages/Auth/Register';
import MainLayout from './pages/Main/MainLayout';
import Dashboard from './pages/Main/Dashboard';
import Workflow from './pages/Workflow/Workflow';
import ReactFlowWorkflow from './pages/Workflow/ReactFlowWorkflow';
import ReactFlowDemo from './pages/Workflow/ReactFlowDemo';
import Todo from './pages/Main/Todo';
import Resource from './pages/Main/Resource';
import Profile from './pages/Profile/Profile';
import TestRunner from './pages/Main/TestRunner';
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
          <Route path="/" element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }>
            <Route index element={<Dashboard />} />
            <Route path="profile" element={<Profile />} />
            <Route path="resource" element={<Resource />} />
            <Route path="workflow" element={<Workflow />} />
            <Route path="workflow/react-flow" element={<ReactFlowWorkflow />} />
            <Route path="workflow/react-flow-demo" element={<ReactFlowDemo />} />
            <Route path="workflow/:workflowId/task-flow" element={<TaskFlow />} />
            <Route path="todo" element={<Todo />} />
            <Route path="test-runner" element={<TestRunner />} />
          </Route>
          <Route path="*" element={<Navigate to="/login" />} />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
