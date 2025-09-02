import { create } from 'zustand';
import { taskAPI } from '../services/api';

interface Task {
  task_instance_id: string;
  task_title: string;
  task_description: string;
  status: 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  priority: number;
  assigned_user_id: string;
  assigned_agent_id?: string;
  workflow_instance_id: string;
  node_instance_id: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  input_data?: {
    immediate_upstream?: any;
    workflow_global?: any;
    node_info?: {
      node_instance_id: string;
      upstream_node_count: number;
    };
  };
  output_data?: any;
  context_data?: {
    workflow?: any;
    current_node?: any;
    upstream_outputs?: Array<{
      node_name: string;
      node_description?: string;
      node_instance_id: string;
      output_data: any;
      completed_at?: string;
    }>;
    context_generated_at?: string;
  };
  result_summary?: string;
  estimated_duration?: number;
  actual_duration?: number;
  instructions?: string;
  task_type?: string;
}

interface TaskState {
  tasks: Task[];
  currentTask: Task | null;
  loading: boolean;
  error: string | null;
  
  // Actions
  loadTasks: (status?: string) => Promise<void>;
  getTaskDetails: (taskId: string) => Promise<void>;
  startTask: (taskId: string) => Promise<void>;
  submitTaskResult: (taskId: string, resultData: any, summary?: string) => Promise<void>;
  pauseTask: (taskId: string, reason?: string) => Promise<void>;
  requestHelp: (taskId: string, helpMessage: string) => Promise<void>;
  rejectTask: (taskId: string, reason: string) => Promise<void>;
  cancelTask: (taskId: string, reason?: string) => Promise<void>;
  deleteTask: (taskId: string) => Promise<void>;
  saveTaskDraft: (taskId: string, draftData: any) => void;
  getTaskDraft: (taskId: string) => any;
  clearTaskDraft: (taskId: string) => void;
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  currentTask: null,
  loading: false,
  error: null,

  loadTasks: async (status?: string) => {
    set({ loading: true, error: null });
    try {
      // 不传递limit参数，让后端返回所有任务
      const response: any = await taskAPI.getUserTasks(status);
      
      // 检查响应格式并处理数据
      let tasksData = [];
      if (response && response.success && response.data) {
        if (Array.isArray(response.data)) {
          tasksData = response.data;
        } else if (response.data.tasks && Array.isArray(response.data.tasks)) {
          tasksData = response.data.tasks;
        } else {
          console.warn('任务数据格式异常:', response.data);
          tasksData = [];
        }
      } else if (Array.isArray(response)) {
        // 直接返回数组的情况
        tasksData = response;
      } else {
        console.warn('任务API响应格式异常:', response);
        tasksData = [];
      }
      
      // 确保每个任务对象都有必要的字段
      const processedTasks = tasksData.map((task: any) => ({
        task_instance_id: task.task_instance_id || task.id || '',
        task_title: task.task_title || task.title || '未命名任务',
        task_description: task.task_description || task.description || '',
        status: task.status || 'pending',
        priority: task.priority || 1,
        assigned_user_id: task.assigned_user_id || task.user_id || '',
        assigned_agent_id: task.assigned_agent_id || task.agent_id,
        workflow_instance_id: task.workflow_instance_id || task.workflow_id || '',
        node_instance_id: task.node_instance_id || task.node_id || '',
        created_at: task.created_at || task.createdAt || '',
        started_at: task.started_at || task.startedAt,
        completed_at: task.completed_at || task.completedAt,
        input_data: task.input_data || task.inputData || {},
        output_data: task.output_data || task.outputData,
        context_data: task.context_data || {},
        result_summary: task.result_summary || task.resultSummary,
        estimated_duration: task.estimated_duration || task.estimatedDuration,
        actual_duration: task.actual_duration || task.actualDuration,
        instructions: task.instructions,
        task_type: task.task_type || task.type,
      }));
      
      set({ tasks: processedTasks, loading: false });
    } catch (error: any) {
      console.error('加载任务失败:', error);
      set({ 
        error: error.response?.data?.detail || '加载任务失败', 
        loading: false,
        tasks: []
      });
    }
  },

  getTaskDetails: async (taskId: string) => {
    set({ loading: true, error: null });
    try {
      console.log('🔍 TaskStore: 开始获取任务详情', taskId);
      const response: any = await taskAPI.getTaskDetails(taskId);
      console.log('📡 TaskStore: API响应', response);
      
      if (response.success && response.data) {
        console.log('✅ TaskStore: 任务详情获取成功');
        console.log('📊 TaskStore: context_data检查', response.data.context_data);
        
        // 更新任务列表中对应的任务（如果存在）
        const currentTasks = get().tasks;
        const updatedTasks = currentTasks.map(task => 
          task.task_instance_id === taskId ? { ...task, ...response.data } : task
        );
        
        set({ 
          currentTask: response.data, 
          tasks: updatedTasks,
          loading: false 
        });
      } else if (response && !response.success) {
        console.error('❌ TaskStore: API返回错误', response.message);
        set({ 
          currentTask: null, 
          loading: false,
          error: response.message || '获取任务详情失败'
        });
      } else {
        console.error('❌ TaskStore: 响应格式异常', response);
        set({ currentTask: null, loading: false });
      }
    } catch (error: any) {
      console.error('❌ TaskStore: 获取任务详情异常', error);
      set({ 
        error: error.response?.data?.detail || error.message || '获取任务详情失败', 
        loading: false 
      });
    }
  },

  startTask: async (taskId: string) => {
    set({ loading: true, error: null });
    try {
      await taskAPI.startTask(taskId);
      // 重新加载任务列表以更新状态
      await get().loadTasks();
      set({ loading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '开始任务失败', 
        loading: false 
      });
    }
  },

  submitTaskResult: async (taskId: string, resultData: any, summary?: string) => {
    set({ loading: true, error: null });
    try {
      await taskAPI.submitTaskResult(taskId, { result_data: resultData, result_summary: summary });
      // 清除草稿
      get().clearTaskDraft(taskId);
      // 重新加载任务列表
      await get().loadTasks();
      set({ loading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '提交任务失败', 
        loading: false 
      });
    }
  },

  pauseTask: async (taskId: string, reason?: string) => {
    set({ loading: true, error: null });
    try {
      await taskAPI.pauseTask(taskId, { reason });
      await get().loadTasks();
      set({ loading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '暂停任务失败', 
        loading: false 
      });
    }
  },

  requestHelp: async (taskId: string, helpMessage: string) => {
    set({ loading: true, error: null });
    try {
      await taskAPI.requestHelp(taskId, { help_message: helpMessage });
      set({ loading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '请求帮助失败', 
        loading: false 
      });
    }
  },

  rejectTask: async (taskId: string, reason: string) => {
    set({ loading: true, error: null });
    try {
      await taskAPI.rejectTask(taskId, { reason });
      await get().loadTasks();
      set({ loading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '拒绝任务失败', 
        loading: false 
      });
    }
  },

  cancelTask: async (taskId: string, reason?: string) => {
    set({ loading: true, error: null });
    try {
      await taskAPI.cancelTask(taskId, { reason });
      await get().loadTasks();
      set({ loading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '取消任务失败', 
        loading: false 
      });
    }
  },

  // 草稿保存功能 - 使用localStorage
  saveTaskDraft: (taskId: string, draftData: any) => {
    try {
      const key = `task_draft_${taskId}`;
      localStorage.setItem(key, JSON.stringify({
        data: draftData,
        timestamp: new Date().toISOString()
      }));
    } catch (error) {
      console.error('保存草稿失败:', error);
    }
  },

  getTaskDraft: (taskId: string) => {
    try {
      const key = `task_draft_${taskId}`;
      const draft = localStorage.getItem(key);
      if (draft) {
        const parsed = JSON.parse(draft);
        // 检查草稿是否在24小时内
        const draftTime = new Date(parsed.timestamp);
        const now = new Date();
        const hoursDiff = (now.getTime() - draftTime.getTime()) / (1000 * 60 * 60);
        
        if (hoursDiff < 24) {
          return parsed.data;
        } else {
          // 删除过期草稿
          localStorage.removeItem(key);
        }
      }
      return null;
    } catch (error) {
      console.error('获取草稿失败:', error);
      return null;
    }
  },

  deleteTask: async (taskId: string) => {
    console.log('🚀 taskStore.deleteTask 开始执行:', taskId);
    set({ loading: true, error: null });
    
    try {
      const token = localStorage.getItem('token');
      console.log('🔐 获取到token:', token ? '有token' : '无token');
      
      const url = `/api/execution/tasks/${taskId}`;
      console.log('📡 准备发送DELETE请求到:', url);
      
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      console.log('📨 收到响应，状态码:', response.status);
      
      const data = await response.json();
      console.log('📄 响应数据:', data);
      
      if (response.ok && data.success) {
        console.log('✅ 删除请求成功，开始更新本地任务列表');
        // 从任务列表中移除已删除的任务
        const currentTasks = get().tasks;
        console.log('📝 当前任务数量:', currentTasks.length);
        const updatedTasks = currentTasks.filter(task => task.task_instance_id !== taskId);
        console.log('📝 更新后任务数量:', updatedTasks.length);
        set({ tasks: updatedTasks, loading: false });
        
        // 清除相关的草稿
        get().clearTaskDraft(taskId);
        console.log('🧹 已清除草稿数据');
      } else {
        console.error('❌ 删除请求失败:', data);
        throw new Error(data.detail || '删除任务失败');
      }
    } catch (error: any) {
      console.error('❌ deleteTask 异常:', error);
      set({ error: error.message || '删除任务失败', loading: false });
      throw error;
    }
  },

  clearTaskDraft: (taskId: string) => {
    try {
      const key = `task_draft_${taskId}`;
      localStorage.removeItem(key);
    } catch (error) {
      console.error('清除草稿失败:', error);
    }
  },
})); 