import axios from 'axios';

// 创建axios实例
const api = axios.create({
  baseURL: '/api', // 使用相对路径通过nginx代理
  timeout: 60000, // 增加到60秒，因为工作流执行可能需要更长时间
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加认证token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    console.log('🔐 [AUTH-DEBUG] 请求拦截器');
    console.log('   - URL:', config.url);
    console.log('   - Token存在:', !!token);
    
    if (token) {
      // 解析token获取用户信息
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        console.log('   - Token用户ID:', payload.user_id);
        console.log('   - Token用户名:', payload.username);
        console.log('   - Token过期时间:', new Date(payload.exp * 1000).toLocaleString());
      } catch (e) {
        console.warn('   - Token解析失败:', e);
      }
      
      config.headers.Authorization = `Bearer ${token}`;
      console.log('   - 已添加Authorization头');
    } else {
      console.warn('   - 警告: 未找到认证token');
    }
    return config;
  },
  (error) => {
    console.error('❌ [AUTH-DEBUG] 请求拦截器错误:', error);
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response) => {
    console.log('🔄 [INTERCEPTOR-DEBUG] 响应拦截器 - 成功响应');
    console.log('   - URL:', response.config.url);
    console.log('   - 方法:', response.config.method);
    console.log('   - 状态码:', response.status);
    console.log('   - 原始响应数据:', response.data);
    
    // 后端返回统一格式: { success: boolean, message: string, data: any }
    const responseData = response.data;
    
    // 如果响应包含success字段，说明是后端的统一格式
    if (typeof responseData === 'object' && responseData.hasOwnProperty('success')) {
      if (!responseData.success) {
        console.error('❌ [INTERCEPTOR-DEBUG] 业务逻辑错误');
        console.error('   - 错误信息:', responseData.message);
        console.error('   - 完整响应:', responseData);
        // 业务逻辑错误，抛出异常
        throw new Error(responseData.message || '操作失败');
      }
      console.log('✅ [INTERCEPTOR-DEBUG] 返回业务数据');
      // 返回data字段的数据
      return responseData;
    }
    
    console.log('✅ [INTERCEPTOR-DEBUG] 返回原始数据');
    // 兼容原有的直接返回数据的格式
    return responseData;
  },
  (error) => {
    console.error('❌ [INTERCEPTOR-DEBUG] 响应拦截器 - 错误响应');
    console.error('   - URL:', error.config?.url);
    console.error('   - 方法:', error.config?.method);
    console.error('   - 状态码:', error.response?.status);
    console.error('   - 错误数据:', error.response?.data);
    console.error('   - 错误信息:', error.message);
    console.error('   - 完整错误对象:', error);
    
    if (error.response?.status === 401) {
      // 未授权，跳转到登录页
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    
    // 处理后端错误响应格式
    if (error.response?.data) {
      const errorData = error.response.data;
      console.error('   - 解析后端错误数据:', errorData);
      if (errorData.message) {
        error.message = errorData.message;
        console.error('   - 设置错误信息:', errorData.message);
      }
      if (errorData.detail) {
        error.message = errorData.detail;
        console.error('   - 设置详细错误信息:', errorData.detail);
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
    api.post('/auth/register', data),

  // 用户登录
  login: (data: { username_or_email: string; password: string }) =>
    api.post('/auth/login', data),

  // 获取当前用户信息
  getCurrentUser: () => api.get('/auth/me'),

  // 修改密码
  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),

  // 退出登录
  logout: () => api.post('/auth/logout'),
};

// 用户相关API
export const userAPI = {
  // 获取用户信息
  getUser: (userId: string) => api.get(`/users/${userId}`),

  // 更新用户信息
  updateUser: (userId: string, data: any) => api.put(`/users/${userId}`, data),
};

// Agent相关API
export const agentAPI = {
  // 获取Agent列表
  getAgents: () => api.get('/processors/available-test'),

  // 获取Agent详情
  getAgent: (agentId: string) => api.get(`/processors/agents/${agentId}`),

  // 更新Agent信息
  updateAgent: (agentId: string, data: any) => api.put(`/processors/agents/${agentId}`, data),

  // 导入Agent
  importAgent: (data: FormData) => api.post('/processors/import', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // 绑定工具
  bindTools: (agentId: string, data: { tool_ids: string[] }) =>
    api.post(`/processors/agents/${agentId}/tools`, data),

  // 获取工具列表
  getTools: () => api.get('/tools/list'),

  // 创建Agent  
  createAgent: async (agentData: any) => {
    console.log('🔥 前端开始创建Agent:', agentData);
    console.log('🔥 请求URL:', '/processors/agents');
    console.log('🔥 完整URL:', window.location.origin + '/processors/agents');
    
    try {
      const response = await api.post('/processors/agents', agentData);
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
    console.log('🔥 请求URL:', `/processors/agents/${agentId}`);
    console.log('🔥 完整URL:', `${window.location.origin}/processors/agents/${agentId}`);
    
    try {
      const response = await api.delete(`/processors/agents/${agentId}`);
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
    api.get('/execution/tasks/my', { params: { status, limit } }),

  // 获取任务详情
  getTaskDetails: (taskId: string) =>
    api.get(`/execution/tasks/${taskId}`),

  // 开始任务
  startTask: (taskId: string) =>
    api.post(`/execution/tasks/${taskId}/start`),

  // 提交任务结果
  submitTaskResult: (taskId: string, data: { result_data: any; result_summary?: string }) =>
    api.post(`/execution/tasks/${taskId}/submit`, data),

  // 暂停任务
  pauseTask: (taskId: string, data: { reason?: string }) =>
    api.post(`/execution/tasks/${taskId}/pause`, data),

  // 请求帮助
  requestHelp: (taskId: string, data: { help_message: string }) =>
    api.post(`/execution/tasks/${taskId}/help`, data),

  // 拒绝任务
  rejectTask: (taskId: string, data: { reason: string }) =>
    api.post(`/execution/tasks/${taskId}/reject`, data),

  // 取消任务
  cancelTask: (taskId: string, data: { reason?: string }) =>
    api.post(`/execution/tasks/${taskId}/cancel`, data),

  // 获取任务历史
  getTaskHistory: (days: number = 30, limit: number = 100) =>
    api.get('/execution/tasks/history', { params: { days, limit } }),

  // 获取任务统计
  getTaskStatistics: () => api.get('/execution/tasks/statistics'),
};

// 工作流相关API
export const workflowAPI = {
  // 获取工作流列表
  getWorkflows: () => api.get('/workflows'),

  // 获取工作流详情
  getWorkflow: (workflowId: string) => api.get(`/workflows/${workflowId}`),

  // 创建工作流
  createWorkflow: (data: any) => api.post('/workflows', data),

  // 更新工作流
  updateWorkflow: (workflowId: string, data: any) => api.put(`/workflows/${workflowId}`, data),

  // 删除工作流
  deleteWorkflow: (workflowId: string) => api.delete(`/workflows/${workflowId}`),

  // 获取工作流版本列表
  getWorkflowVersions: (workflowBaseId: string) => api.get(`/workflows/${workflowBaseId}/versions`),

  // 发布工作流版本
  publishWorkflow: (workflowId: string, data: { version_name: string; description?: string }) =>
    api.post(`/workflows/${workflowId}/publish`, data),
};

// 节点相关API
export const nodeAPI = {
  // 获取工作流节点
  getWorkflowNodes: (workflowId: string) => api.get(`/nodes/workflow/${workflowId}`),

  // 创建节点
  createNode: (data: any) => api.post('/nodes/', data),

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
    return api.put(`/nodes/${nodeBaseId}/workflow/${workflowBaseId}`, processedData);
  },

  // 删除节点
  deleteNode: (nodeBaseId: string, workflowBaseId: string) => 
    api.delete(`/nodes/${nodeBaseId}/workflow/${workflowBaseId}`),

  // 创建节点连接
  createConnection: (data: { from_node_base_id: string; to_node_base_id: string; workflow_base_id: string }) =>
    api.post('/nodes/connections', data),

  // 删除节点连接
  deleteConnection: (data: { from_node_base_id: string; to_node_base_id: string; workflow_base_id: string }) =>
    api.delete('/nodes/connections', { data }),

  // 获取工作流连接
  getWorkflowConnections: (workflowId: string) => api.get(`/nodes/connections/workflow/${workflowId}`),
};

// 处理器相关API
export const processorAPI = {
  // 获取可用处理器
  getAvailableProcessors: () => api.get('/processors/available-test'),

  // 获取注册的处理器
  getRegisteredProcessors: () => api.get('/processors/registered'),

  // 创建处理器
  createProcessor: (data: { name: string; type: 'human' | 'agent' | 'mix'; user_id?: string; agent_id?: string }) =>
    api.post('/processors/test-create', data),

  // 获取处理器详情
  getProcessor: (processorId: string) => api.get(`/processors/${processorId}`),

  // 删除处理器
  deleteProcessor: async (processorId: string) => {
    console.log('🔥 前端开始删除处理器:', processorId);
    console.log('🔥 请求URL:', `/processors/delete/${processorId}`);
    console.log('🔥 完整URL:', `${window.location.origin}/processors/delete/${processorId}`);
    
    try {
      const response = await api.delete(`/processors/delete/${processorId}`);
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
    api.post(`/nodes/${nodeId}/processors`, data),

  // 移除节点处理器
  removeProcessor: (nodeId: string, processorId: string) =>
    api.delete(`/nodes/${nodeId}/processors/${processorId}`),
};

// 资源相关API
export const resourceAPI = {
  // 获取在线用户和Agent
  getOnlineResources: () => api.get('/execution/online-resources'),

  // 获取资源统计
  getResourceStatistics: () => api.get('/execution/resource-statistics'),
};

// 测试相关API
export const testAPI = {
  // 获取测试套件列表
  getTestSuites: () => api.get('/test/suites'),

  // 获取测试状态
  getTestStatus: () => api.get('/test/status'),

  // 运行测试
  runTests: (data: { suites?: string[]; tests?: string[] }) => 
    api.post('/test/run', data),

  // 停止测试
  stopTests: () => api.post('/test/stop'),

  // 清除测试结果
  clearTestResults: () => api.post('/test/clear'),

  // 运行真实测试
  runRealTest: (suiteName: string) => api.get(`/test/run-real/${suiteName}`),
};

// 执行相关API
export const executionAPI = {
  // 执行工作流
  executeWorkflow: (data: { workflow_base_id: string; instance_name: string; input_data?: any; context_data?: any }) =>
    api.post('/execution/workflows/execute', data),

  // 控制工作流
  controlWorkflow: (instanceId: string, data: { action: 'pause' | 'resume' | 'cancel'; reason?: string }) =>
    api.post(`/execution/workflows/${instanceId}/control`, data),

  // 获取工作流状态
  getWorkflowStatus: (instanceId: string) =>
    api.get(`/execution/workflows/${instanceId}/status`),

  // 获取工作流实例详细状态
  getWorkflowInstanceDetail: (instanceId: string) =>
    api.get(`/execution/workflows/${instanceId}/status`),

  // 获取工作流节点详细输出信息
  getWorkflowNodesDetail: (instanceId: string) =>
    api.get(`/execution/workflows/${instanceId}/nodes-detail`),

  // 获取工作流执行实例列表
  getWorkflowInstances: (workflowBaseId: string, limit: number = 20) =>
    api.get(`/execution/workflows/${workflowBaseId}/instances`, { params: { limit } }),

  // 获取工作流任务流程
  getWorkflowTaskFlow: (workflowId: string) => 
    api.get(`/execution/workflow/${workflowId}/task-flow`),

  // 获取Agent任务列表
  getPendingAgentTasks: (agentId?: string, limit: number = 50) =>
    api.get('/execution/agent-tasks/pending', { params: { agent_id: agentId, limit } }),

  // 处理Agent任务
  processAgentTask: (taskId: string) =>
    api.post(`/execution/agent-tasks/${taskId}/process`),

  // 重试Agent任务
  retryAgentTask: (taskId: string) =>
    api.post(`/execution/agent-tasks/${taskId}/retry`),

  // 取消Agent任务
  cancelAgentTask: (taskId: string) =>
    api.post(`/execution/agent-tasks/${taskId}/cancel`),

  // 获取Agent任务统计
  getAgentTaskStatistics: (agentId?: string) =>
    api.get('/execution/agent-tasks/statistics', { params: { agent_id: agentId } }),

  // 获取系统状态
  getSystemStatus: () => api.get('/execution/system/status'),

  // 删除工作流实例
  deleteWorkflowInstance: async (instanceId: string) => {
    console.log('🔥 前端开始删除工作流实例:', instanceId);
    console.log('🔥 请求URL:', `/execution/workflows/${instanceId}`);
    console.log('🔥 完整URL:', `${window.location.origin}/execution/workflows/${instanceId}`);
    
    try {
      const response = await api.delete(`/execution/workflows/${instanceId}`);
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

// MCP相关API
export const mcpAPI = {
  // 获取MCP服务器列表
  getMCPServers: () => api.get('/mcp/servers'),

  // 添加MCP服务器
  addMCPServer: (data: {
    name: string;
    url: string;
    capabilities?: string[];
    auth?: any;
    timeout?: number;
  }) => api.post('/mcp/servers', data),

  // 获取服务器状态
  getServerStatus: (serverName: string) => api.get(`/mcp/servers/${serverName}/status`),

  // 发现服务器工具
  discoverServerTools: (serverName: string) => api.get(`/mcp/servers/${serverName}/tools`),

  // 调用MCP工具
  callMCPTool: (data: {
    tool_name: string;
    server_name: string;
    arguments: any;
  }) => api.post('/mcp/tools/call', data),

  // 获取Agent工具配置
  getAgentToolConfig: (agentId: string) => api.get(`/mcp/agents/${agentId}/config`),

  // 更新Agent工具配置
  updateAgentToolConfig: (agentId: string, config: any) => api.put(`/mcp/agents/${agentId}/config`, config),

  // 获取Agent可用工具
  getAgentTools: (agentId: string) => api.get(`/mcp/agents/${agentId}/tools`),

  // 移除MCP服务器
  removeMCPServer: (serverName: string) => api.delete(`/mcp/servers/${serverName}`),

  // 手动健康检查
  healthCheckServer: (serverName: string) => api.post(`/mcp/user-tools/server/${serverName}/health-check`),

  // 刷新服务器工具
  refreshServerTools: (serverName: string) => api.post(`/mcp/servers/${serverName}/refresh-tools`),

  // MCP服务健康检查
  getMCPHealth: () => api.get('/mcp/health'),
};

// MCP用户工具管理API
export const mcpUserToolsAPI = {
  // 获取用户工具列表
  getUserTools: async (params?: { server_name?: string; tool_name?: string; is_active?: boolean }) => {
    console.log('🌐 [API-DEBUG] 调用 getUserTools');
    console.log('   - 参数:', params);
    console.log('   - URL: /mcp/user-tools');
    
    try {
      const response = await api.get('/mcp/user-tools', { params });
      console.log('✅ [API-DEBUG] getUserTools 成功');
      console.log('   - HTTP状态:', response.status);
      console.log('   - 响应数据:', response.data);
      console.log('   - 响应头:', response.headers);
      return response.data;
    } catch (error: any) {
      console.error('❌ [API-DEBUG] getUserTools 失败');
      console.error('   - 错误:', error);
      if (error.response) {
        console.error('   - HTTP状态:', error.response.status);
        console.error('   - 响应数据:', error.response.data);
      }
      throw error;
    }
  },

  // 添加MCP服务器并发现工具
  addMCPServer: async (data: {
    server_name: string;
    server_url: string;
    server_description?: string;
    auth_config?: any;
  }) => {
    console.log('🌐 [API-DEBUG] 调用 addMCPServer');
    console.log('   - 数据:', data);
    console.log('   - URL: /mcp/user-tools');
    
    try {
      const response = await api.post('/mcp/user-tools', data);
      console.log('✅ [API-DEBUG] addMCPServer 成功');
      console.log('   - HTTP状态:', response.status);
      console.log('   - 响应数据:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ [API-DEBUG] addMCPServer 失败');
      console.error('   - 错误:', error);
      if (error.response) {
        console.error('   - HTTP状态:', error.response.status);
        console.error('   - 响应数据:', error.response.data);
      }
      throw error;
    }
  },

  // 更新工具配置
  updateTool: (toolId: string, data: {
    server_description?: string;
    tool_description?: string;
    auth_config?: any;
    timeout_seconds?: number;
    is_server_active?: boolean;
    is_tool_active?: boolean;
  }) => api.put(`/mcp/user-tools/${toolId}`, data),

  // 删除工具
  deleteTool: (toolId: string) => api.delete(`/mcp/user-tools/${toolId}`),

  // 删除服务器的所有工具
  deleteServerTools: (serverName: string) => api.delete(`/mcp/user-tools/server/${serverName}`),

  // 重新发现服务器工具
  rediscoverServerTools: (serverName: string) => api.post(`/mcp/user-tools/server/${serverName}/rediscover`),

  // 测试工具调用
  testTool: (toolId: string, args: any = {}) => api.post(`/mcp/user-tools/${toolId}/test`, { arguments: args }),

  // 获取认证类型
  getAuthTypes: async () => {
    console.log('🌐 [API-DEBUG] 调用 getAuthTypes');
    console.log('   - URL: /mcp/auth-types');
    
    try {
      const response = await api.get('/mcp/auth-types');
      console.log('✅ [API-DEBUG] getAuthTypes 成功');
      console.log('   - HTTP状态:', response.status);
      console.log('   - 响应数据:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ [API-DEBUG] getAuthTypes 失败');
      console.error('   - 错误:', error);
      if (error.response) {
        console.error('   - HTTP状态:', error.response.status);
        console.error('   - 响应数据:', error.response.data);
      }
      throw error;
    }
  },

  // 获取用户工具统计
  getUserToolStats: async () => {
    console.log('🌐 [API-DEBUG] 调用 getUserToolStats');
    console.log('   - URL: /mcp/user-tools/stats');
    
    try {
      const response = await api.get('/mcp/user-tools/stats');
      console.log('✅ [API-DEBUG] getUserToolStats 成功');
      console.log('   - HTTP状态:', response.status);
      console.log('   - 响应数据:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('❌ [API-DEBUG] getUserToolStats 失败');
      console.error('   - 错误:', error);
      if (error.response) {
        console.error('   - HTTP状态:', error.response.status);
        console.error('   - 响应数据:', error.response.data);
      }
      throw error;
    }
  },
  
  // 健康检查服务器
  healthCheckServer: (serverName: string) => api.post(`/mcp/user-tools/server/${serverName}/health-check`),
};

// Agent工具绑定API
export const agentToolsAPI = {
  // 获取Agent绑定的工具
  getAgentTools: (agentId: string, params?: { is_enabled?: boolean }) =>
    api.get(`/agents/${agentId}/tools`, { params }),

  // 为Agent绑定工具
  bindTool: (agentId: string, data: {
    tool_id: string;
    is_enabled?: boolean;
    priority?: number;
    max_calls_per_task?: number;
    timeout_override?: number;
    custom_config?: any;
  }) => api.post(`/agents/${agentId}/tools`, data),

  // 批量绑定工具
  batchBindTools: (agentId: string, bindings: Array<{
    tool_id: string;
    is_enabled?: boolean;
    priority?: number;
    max_calls_per_task?: number;
    timeout_override?: number;
    custom_config?: any;
  }>) => api.post(`/agents/${agentId}/tools/batch`, { bindings }),

  // 更新工具绑定配置
  updateToolBinding: (agentId: string, toolId: string, data: {
    is_enabled?: boolean;
    priority?: number;
    max_calls_per_task?: number;
    timeout_override?: number;
    custom_config?: any;
  }) => api.put(`/agents/${agentId}/tools/${toolId}`, data),

  // 解除工具绑定
  unbindTool: (agentId: string, toolId: string) => api.delete(`/agents/${agentId}/tools/${toolId}`),

  // 获取Agent工具配置
  getAgentToolConfig: (agentId: string) => api.get(`/agents/${agentId}/tool-config`),

  // 获取Agent可用执行工具
  getAgentExecutionTools: (agentId: string) => api.get(`/agents/${agentId}/execution-tools`),

  // 获取Agent工具使用统计
  getAgentToolStats: (agentId: string) => api.get(`/agents/${agentId}/tool-stats`),

  // 获取热门工具列表
  getPopularTools: (limit: number = 10) => api.get('/tools/popular', { params: { limit } }),
};

export default api; 