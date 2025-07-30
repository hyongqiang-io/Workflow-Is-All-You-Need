import axios from 'axios';

// 创建axios实例
const api = axios.create({
  baseURL: 'http://localhost:8001', // 后端API地址
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加认证token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response) => {
    // 后端返回统一格式: { success: boolean, message: string, data: any }
    const responseData = response.data;
    
    // 如果响应包含success字段，说明是后端的统一格式
    if (typeof responseData === 'object' && responseData.hasOwnProperty('success')) {
      if (!responseData.success) {
        // 业务逻辑错误，抛出异常
        throw new Error(responseData.message || '操作失败');
      }
      // 返回data字段的数据
      return responseData;
    }
    
    // 兼容原有的直接返回数据的格式
    return responseData;
  },
  (error) => {
    if (error.response?.status === 401) {
      // 未授权，跳转到登录页
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    
    // 处理后端错误响应格式
    if (error.response?.data) {
      const errorData = error.response.data;
      if (errorData.message) {
        error.message = errorData.message;
      }
      if (errorData.error_code) {
        error.error_code = errorData.error_code;
      }
    }
    
    return Promise.reject(error);
  }
);

// 认证相关API
export const authAPI = {
  // 用户注册
  register: (data: { username: string; email: string; password: string }) =>
    api.post('/api/auth/register', data),

  // 用户登录
  login: (data: { username_or_email: string; password: string }) =>
    api.post('/api/auth/login', data),

  // 获取当前用户信息
  getCurrentUser: () => api.get('/api/auth/me'),

  // 修改密码
  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post('/api/auth/change-password', data),

  // 退出登录
  logout: () => api.post('/api/auth/logout'),
};

// 用户相关API
export const userAPI = {
  // 获取用户信息
  getUser: (userId: string) => api.get(`/api/users/${userId}`),

  // 更新用户信息
  updateUser: (userId: string, data: any) => api.put(`/api/users/${userId}`, data),
};

// Agent相关API
export const agentAPI = {
  // 获取Agent列表
  getAgents: () => api.get('/api/processors/available-test'),

  // 获取Agent详情
  getAgent: (agentId: string) => api.get(`/api/processors/agents/${agentId}`),

  // 更新Agent信息
  updateAgent: (agentId: string, data: any) => api.put(`/api/processors/agents/${agentId}`, data),

  // 导入Agent
  importAgent: (data: FormData) => api.post('/api/processors/import', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // 绑定工具
  bindTools: (agentId: string, data: { tool_ids: string[] }) =>
    api.post(`/api/processors/agents/${agentId}/tools`, data),

  // 获取工具列表
  getTools: () => api.get('/api/tools/list'),

  // 创建Agent  
  createAgent: async (agentData: any) => {
    console.log('🔥 前端开始创建Agent:', agentData);
    console.log('🔥 请求URL:', '/api/processors/agents');
    console.log('🔥 完整URL:', 'http://localhost:8001/api/processors/agents');
    
    try {
      const response = await api.post('/api/processors/agents', agentData);
      console.log('✅ Agent创建请求成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ Agent创建请求失败:', error);
      if (error.response) {
        console.error('❌ 错误响应状态:', error.response.status);
        console.error('❌ 错误响应数据:', error.response.data);
        console.error('❌ 错误响应头:', error.response.headers);
      }
      if (error.request) {
        console.error('❌ 请求对象:', error.request);
      }
      throw error;
    }
  },

  // 删除Agent
  deleteAgent: async (agentId: string) => {
    console.log('🔥 前端开始删除Agent:', agentId);
    console.log('🔥 请求URL:', `/api/processors/agents/${agentId}`);
    console.log('🔥 完整URL:', `http://localhost:8001/api/processors/agents/${agentId}`);
    
    try {
      const response = await api.delete(`/api/processors/agents/${agentId}`);
      console.log('✅ Agent删除请求成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ Agent删除请求失败:', error);
      if (error.response) {
        console.error('❌ 错误响应状态:', error.response.status);
        console.error('❌ 错误响应数据:', error.response.data);
        console.error('❌ 错误响应头:', error.response.headers);
      }
      if (error.request) {
        console.error('❌ 请求对象:', error.request);
      }
      throw error;
    }
  },
};

// 任务相关API
export const taskAPI = {
  // 获取用户任务列表
  getUserTasks: (status?: string, limit: number = 50) =>
    api.get('/api/execution/tasks/my', { params: { status, limit } }),

  // 获取任务详情
  getTaskDetails: (taskId: string) =>
    api.get(`/api/execution/tasks/${taskId}`),

  // 开始任务
  startTask: (taskId: string) =>
    api.post(`/api/execution/tasks/${taskId}/start`),

  // 提交任务结果
  submitTaskResult: (taskId: string, data: { result_data: any; result_summary?: string }) =>
    api.post(`/api/execution/tasks/${taskId}/submit`, data),

  // 暂停任务
  pauseTask: (taskId: string, data: { reason?: string }) =>
    api.post(`/api/execution/tasks/${taskId}/pause`, data),

  // 请求帮助
  requestHelp: (taskId: string, data: { help_message: string }) =>
    api.post(`/api/execution/tasks/${taskId}/help`, data),

  // 拒绝任务
  rejectTask: (taskId: string, data: { reason: string }) =>
    api.post(`/api/execution/tasks/${taskId}/reject`, data),

  // 取消任务
  cancelTask: (taskId: string, data: { reason?: string }) =>
    api.post(`/api/execution/tasks/${taskId}/cancel`, data),

  // 获取任务历史
  getTaskHistory: (days: number = 30, limit: number = 100) =>
    api.get('/api/execution/tasks/history', { params: { days, limit } }),

  // 获取任务统计
  getTaskStatistics: () => api.get('/api/execution/tasks/statistics'),
};

// 工作流相关API
export const workflowAPI = {
  // 获取工作流列表
  getWorkflows: () => api.get('/api/workflows'),

  // 获取工作流详情
  getWorkflow: (workflowId: string) => api.get(`/api/workflows/${workflowId}`),

  // 创建工作流
  createWorkflow: (data: any) => api.post('/api/workflows', data),

  // 更新工作流
  updateWorkflow: (workflowId: string, data: any) => api.put(`/api/workflows/${workflowId}`, data),

  // 删除工作流
  deleteWorkflow: (workflowId: string) => api.delete(`/api/workflows/${workflowId}`),

  // 获取工作流版本列表
  getWorkflowVersions: (workflowBaseId: string) => api.get(`/api/workflows/${workflowBaseId}/versions`),

  // 发布工作流版本
  publishWorkflow: (workflowId: string, data: { version_name: string; description?: string }) =>
    api.post(`/api/workflows/${workflowId}/publish`, data),
};

// 节点相关API
export const nodeAPI = {
  // 获取工作流节点
  getWorkflowNodes: (workflowId: string) => api.get(`/api/nodes/workflow/${workflowId}`),

  // 创建节点
  createNode: (data: any) => api.post('/api/nodes/', data),

  // 更新节点
  updateNode: (nodeBaseId: string, workflowBaseId: string, data: any) => {
    // 数据预处理，确保数据格式正确
    const processedData = {
      name: data.name || '未命名节点',
      task_description: data.task_description || '',
      position_x: data.position_x || 0,
      position_y: data.position_y || 0,
      processor_id: data.processor_id || null  // 确保processor_id被包含
    };
    
    // 确保name不为空字符串
    if (typeof processedData.name === 'string' && processedData.name.trim() === '') {
      processedData.name = '未命名节点';
    }
    
    console.log('API发送节点更新数据:', processedData);
    return api.put(`/api/nodes/${nodeBaseId}/workflow/${workflowBaseId}`, processedData);
  },

  // 删除节点
  deleteNode: (nodeBaseId: string, workflowBaseId: string) => 
    api.delete(`/api/nodes/${nodeBaseId}/workflow/${workflowBaseId}`),

  // 创建节点连接
  createConnection: (data: { from_node_base_id: string; to_node_base_id: string; workflow_base_id: string }) =>
    api.post('/api/nodes/connections', data),

  // 删除节点连接
  deleteConnection: (data: { from_node_base_id: string; to_node_base_id: string; workflow_base_id: string }) =>
    api.delete('/api/nodes/connections', { data }),

  // 获取工作流连接
  getWorkflowConnections: (workflowId: string) => api.get(`/api/nodes/connections/workflow/${workflowId}`),
};

// 处理器相关API
export const processorAPI = {
  // 获取可用处理器
  getAvailableProcessors: () => api.get('/api/processors/available-test'),

  // 获取注册的处理器
  getRegisteredProcessors: () => api.get('/api/processors/registered'),

  // 创建处理器
  createProcessor: (data: { name: string; type: 'human' | 'agent' | 'mix'; user_id?: string; agent_id?: string }) =>
    api.post('/api/processors/test-create', data),

  // 获取处理器详情
  getProcessor: (processorId: string) => api.get(`/api/processors/${processorId}`),

  // 删除处理器
  deleteProcessor: async (processorId: string) => {
    console.log('🔥 前端开始删除处理器:', processorId);
    console.log('🔥 请求URL:', `/api/processors/delete/${processorId}`);
    console.log('🔥 完整URL:', `http://localhost:8001/api/processors/delete/${processorId}`);
    
    try {
      const response = await api.delete(`/api/processors/delete/${processorId}`);
      console.log('✅ 删除请求成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ 删除请求失败:', error);
      if (error.response) {
        console.error('❌ 错误响应状态:', error.response.status);
        console.error('❌ 错误响应数据:', error.response.data);
        console.error('❌ 错误响应头:', error.response.headers);
      }
      if (error.request) {
        console.error('❌ 请求对象:', error.request);
      }
      throw error;
    }
  },

  // 分配处理器到节点
  assignProcessor: (nodeId: string, data: { processor_id: string }) =>
    api.post(`/api/nodes/${nodeId}/processors`, data),

  // 移除节点处理器
  removeProcessor: (nodeId: string, processorId: string) =>
    api.delete(`/api/nodes/${nodeId}/processors/${processorId}`),
};

// 资源相关API
export const resourceAPI = {
  // 获取在线用户和Agent
  getOnlineResources: () => api.get('/api/execution/online-resources'),

  // 获取资源统计
  getResourceStatistics: () => api.get('/api/execution/resource-statistics'),
};

// 测试相关API
export const testAPI = {
  // 获取测试套件列表
  getTestSuites: () => api.get('/api/test/suites'),

  // 获取测试状态
  getTestStatus: () => api.get('/api/test/status'),

  // 运行测试
  runTests: (data: { suites?: string[]; tests?: string[] }) => 
    api.post('/api/test/run', data),

  // 停止测试
  stopTests: () => api.post('/api/test/stop'),

  // 清除测试结果
  clearTestResults: () => api.post('/api/test/clear'),

  // 运行真实测试
  runRealTest: (suiteName: string) => api.get(`/api/test/run-real/${suiteName}`),
};

// 执行相关API
export const executionAPI = {
  // 执行工作流
  executeWorkflow: (data: { workflow_base_id: string; instance_name: string; input_data?: any; context_data?: any }) =>
    api.post('/api/execution/workflows/execute', data),

  // 控制工作流
  controlWorkflow: (instanceId: string, data: { action: 'pause' | 'resume' | 'cancel'; reason?: string }) =>
    api.post(`/api/execution/workflows/${instanceId}/control`, data),

  // 获取工作流状态
  getWorkflowStatus: (instanceId: string) =>
    api.get(`/api/execution/workflows/${instanceId}/status`),

  // 获取工作流实例详细状态
  getWorkflowInstanceDetail: (instanceId: string) =>
    api.get(`/api/execution/workflows/${instanceId}/status`),

  // 获取工作流节点详细输出信息
  getWorkflowNodesDetail: (instanceId: string) =>
    api.get(`/api/execution/workflows/${instanceId}/nodes-detail`),

  // 获取工作流执行实例列表
  getWorkflowInstances: (workflowBaseId: string, limit: number = 20) =>
    api.get(`/api/execution/workflows/${workflowBaseId}/instances`, { params: { limit } }),

  // 获取工作流任务流程
  getWorkflowTaskFlow: (workflowId: string) => 
    api.get(`/api/execution/workflow/${workflowId}/task-flow`),

  // 获取Agent任务列表
  getPendingAgentTasks: (agentId?: string, limit: number = 50) =>
    api.get('/api/execution/agent-tasks/pending', { params: { agent_id: agentId, limit } }),

  // 处理Agent任务
  processAgentTask: (taskId: string) =>
    api.post(`/api/execution/agent-tasks/${taskId}/process`),

  // 重试Agent任务
  retryAgentTask: (taskId: string) =>
    api.post(`/api/execution/agent-tasks/${taskId}/retry`),

  // 取消Agent任务
  cancelAgentTask: (taskId: string) =>
    api.post(`/api/execution/agent-tasks/${taskId}/cancel`),

  // 获取Agent任务统计
  getAgentTaskStatistics: (agentId?: string) =>
    api.get('/api/execution/agent-tasks/statistics', { params: { agent_id: agentId } }),

  // 获取系统状态
  getSystemStatus: () => api.get('/api/execution/system/status'),

  // 删除工作流实例
  deleteWorkflowInstance: async (instanceId: string) => {
    console.log('🔥 前端开始删除工作流实例:', instanceId);
    console.log('🔥 请求URL:', `/api/execution/workflows/${instanceId}`);
    console.log('🔥 完整URL:', `http://localhost:8001/api/execution/workflows/${instanceId}`);
    
    try {
      const response = await api.delete(`/api/execution/workflows/${instanceId}`);
      console.log('✅ 工作流实例删除请求成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ 工作流实例删除请求失败:', error);
      if (error.response) {
        console.error('❌ 错误响应状态:', error.response.status);
        console.error('❌ 错误响应数据:', error.response.data);
        console.error('❌ 错误响应头:', error.response.headers);
      }
      if (error.request) {
        console.error('❌ 请求对象:', error.request);
      }
      throw error;
    }
  },
};

export default api; 