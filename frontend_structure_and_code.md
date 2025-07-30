# 人与Agent协作平台前端设计与代码文档

---

## 1. 技术栈与依赖
- React 18+
- Ant Design 5+
- react-router-dom
- reactflow
- axios
- Zustand（状态管理）

---

## 2. 目录结构建议
```text
src/
  api/           # 所有后端接口请求
  components/    # 通用组件
  pages/         # 页面
    Auth/        # 注册、登录
    Main/        # 主页面（我的、资源、代办、工作流）
    Profile/     # 个人信息/Agent信息
    Workflow/    # 工作流相关
    Agent/       # Agent管理
  store/         # 状态管理
  utils/         # 工具函数
  App.tsx        # 路由与全局布局
  main.tsx       # 入口
```

---

## 3. 路由结构
```jsx
// App.tsx 路由示例
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Auth/Login';
import Register from './pages/Auth/Register';
import MainLayout from './pages/Main/MainLayout';
import Profile from './pages/Profile/Profile';
import Resource from './pages/Main/Resource';
import Todo from './pages/Main/Todo';
import Workflow from './pages/Workflow/Workflow';
import AgentManage from './pages/Agent/AgentManage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<MainLayout />}>
          <Route path="profile" element={<Profile />} />
          <Route path="resource" element={<Resource />} />
          <Route path="todo" element={<Todo />} />
          <Route path="workflow" element={<Workflow />} />
          <Route path="agent" element={<AgentManage />} />
        </Route>
        <Route path="*" element={<Navigate to="/login" />} />
      </Routes>
    </BrowserRouter>
  );
}
```

---

## 4. 主要页面与功能说明

### 4.1 注册 Register
- 表单：用户名、邮箱、密码、确认密码
- 用户名唯一校验（接口：/api/auth/register，失败返回409）
- 注册成功自动创建Agent（后端已实现）

### 4.2 登录 Login
- 表单：用户名/邮箱、密码
- 登录校验（接口：/api/auth/login）
- 成功后跳转主页面

### 4.3 主页面 MainLayout
- 顶部导航栏（我的、资源、代办、工作流、Agent管理、退出登录）
- 子路由切换

### 4.4 我的 Profile
- 展示和编辑个人信息、Agent信息
- 保存时同步更新user和agent表

### 4.5 Resource
- 展示所有可调用的人/Agent（接口：/api/processors/available）

### 4.6 To Do（代办）
- 展示分配给自己的任务（接口：/api/execution/tasks/my）
- 任务详情、提交窗口
- 未提交退出时信息保留（前端localStorage，后端如支持草稿可切换）

### 4.7 工作流 Workflow
- 创建/编辑/渲染工作流（reactflow）
- 锁定后开始执行，节点分配、状态流转
- 节点完成后变色/点亮

### 4.8 Agent管理 AgentManage
- 一键导入多个Agent（接口：/api/processors/available 或自定义）
- Agent可绑定Tool（预留接口 /api/tools/list）

---

## 5. API接口对接说明

- 注册：POST /api/auth/register
- 登录：POST /api/auth/login
- 获取当前用户：GET /api/auth/me
- 获取所有可用Processor（人/Agent）：GET /api/processors/available
- 获取代办任务：GET /api/execution/tasks/my
- 提交任务结果：POST /api/execution/tasks/{task_id}/submit
- 创建工作流：POST /api/workflow
- 获取/编辑/渲染工作流：GET/PUT /api/workflow/{id}
- Agent导入/Tool绑定：预留接口

---

## 6. 代码骨架示例

### 6.1 注册页面 Register
```tsx
// src/pages/Auth/Register.tsx
import { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { register } from '../../api/auth';

export default function Register() {
  const [loading, setLoading] = useState(false);
  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      await register(values);
      message.success('注册成功，请登录');
      window.location.href = '/login';
    } catch (e: any) {
      if (e.response?.status === 409) {
        message.error('用户名已存在');
      } else {
        message.error('注册失败');
      }
    } finally {
      setLoading(false);
    }
  };
  return (
    <Form onFinish={onFinish} layout="vertical" style={{ maxWidth: 400, margin: 'auto', marginTop: 80 }}>
      <Form.Item name="username" label="用户名" rules={[{ required: true }]}> <Input /> </Form.Item>
      <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}> <Input /> </Form.Item>
      <Form.Item name="password" label="密码" rules={[{ required: true, min: 6 }]}> <Input.Password /> </Form.Item>
      <Form.Item name="confirm" label="确认密码" dependencies={["password"]} rules={[{ required: true }, ({ getFieldValue }) => ({ validator(_, value) { if (!value || getFieldValue('password') === value) { return Promise.resolve(); } return Promise.reject('两次输入密码不一致'); } })]}> <Input.Password /> </Form.Item>
      <Button type="primary" htmlType="submit" loading={loading} block>注册</Button>
    </Form>
  );
}
```

### 6.2 登录页面 Login
```tsx
// src/pages/Auth/Login.tsx
import { useState } from 'react';
import { Form, Input, Button, message } from 'antd';
import { login } from '../../api/auth';

export default function Login() {
  const [loading, setLoading] = useState(false);
  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const res = await login(values);
      localStorage.setItem('token', res.data.token.access_token);
      message.success('登录成功');
      window.location.href = '/';
    } catch (e: any) {
      message.error('用户名或密码错误');
    } finally {
      setLoading(false);
    }
  };
  return (
    <Form onFinish={onFinish} layout="vertical" style={{ maxWidth: 400, margin: 'auto', marginTop: 80 }}>
      <Form.Item name="username_or_email" label="用户名/邮箱" rules={[{ required: true }]}> <Input /> </Form.Item>
      <Form.Item name="password" label="密码" rules={[{ required: true }]}> <Input.Password /> </Form.Item>
      <Button type="primary" htmlType="submit" loading={loading} block>登录</Button>
    </Form>
  );
}
```

### 6.3 主页面骨架 MainLayout
```tsx
// src/pages/Main/MainLayout.tsx
import { Layout, Menu } from 'antd';
import { Outlet, useNavigate } from 'react-router-dom';

const { Header, Content, Sider } = Layout;

const menuItems = [
  { key: 'profile', label: '我的' },
  { key: 'resource', label: '资源' },
  { key: 'todo', label: '代办' },
  { key: 'workflow', label: '工作流' },
  { key: 'agent', label: 'Agent管理' },
  { key: 'logout', label: '退出登录' },
];

export default function MainLayout() {
  const navigate = useNavigate();
  const onMenuClick = ({ key }: any) => {
    if (key === 'logout') {
      localStorage.removeItem('token');
      window.location.href = '/login';
    } else {
      navigate('/' + key);
    }
  };
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider>
        <Menu theme="dark" mode="inline" items={menuItems} onClick={onMenuClick} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: 0 }} />
        <Content style={{ margin: '16px' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
```

### 6.4 其余页面与组件
- Profile、Resource、Todo、Workflow、AgentManage、reactflow流程图、任务提交、Agent导入、Tool绑定等页面和组件请见后续章节（可按需补充）。

---

## 7. 说明与后续
- 所有API请求建议用axios封装，自动带token
- 状态管理建议用Zustand或Redux Toolkit
- 任务未提交时，前端localStorage保存草稿，页面加载时自动恢复
- 工作流流程图用reactflow渲染，节点状态变更时变色
- Agent导入、Tool绑定等接口预留，后端无需改动
- UI风格可用Ant Design默认主题，支持自定义

---

> 如需生成具体页面/组件的详细代码，请继续补充需求或指定页面，我会持续在本文件内追加代码。 