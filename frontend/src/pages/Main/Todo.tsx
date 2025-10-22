import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Button, Modal, Form, Input, Select, message, Space, Collapse, Typography, Divider, Alert, Spin, Row, Col, Pagination, Checkbox, Tabs } from 'antd';
import { SaveOutlined, BranchesOutlined, EyeOutlined, SearchOutlined, ClearOutlined, DownloadOutlined, FileOutlined, RobotOutlined } from '@ant-design/icons';
import { useTaskStore } from '../../stores/taskStore';
import { useAuthStore } from '../../stores/authStore';
import { taskSubdivisionApi, executionAPI, taskAPI } from '../../services/api';
import { FileAPI } from '../../services/fileAPI';
import TaskSubdivisionModal from '../../components/TaskSubdivisionModal';
import SubdivisionResultEditModal from '../../components/SubdivisionResultEditModal';
import TaskFlowViewer from '../../components/TaskFlowViewer';
import NodeAttachmentManager from '../../components/NodeAttachmentManager';
import TaskConversationPanel from '../../components/TaskConversationPanel';
import SimulatorConversationPanel from '../../components/SimulatorConversationPanel';

const { TextArea } = Input;
const { Panel } = Collapse;
const { Text, Paragraph } = Typography;

const Todo: React.FC = () => {
  const { user } = useAuthStore();
  const {
    tasks,
    currentTask: taskStoreCurrentTask,  // 重命名避免冲突
    loading,
    error,
    loadTasks,
    getTaskDetails,
    startTask,
    submitTaskResult,
    pauseTask,
    requestHelp,
    rejectTask,
    cancelTask,
    deleteTask,
    saveTaskDraft,
    getTaskDraft
  } = useTaskStore();
  
  // 工作流实例信息缓存
  const [workflowCache, setWorkflowCache] = useState<{[key: string]: any}>({});
  
  // 筛选和搜索状态
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [workflowFilter, setWorkflowFilter] = useState<string>('all');
  const [filteredTasks, setFilteredTasks] = useState<any[]>([]);
  
  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [paginatedTasks, setPaginatedTasks] = useState<any[]>([]);
  
  const [submitModalVisible, setSubmitModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [helpModalVisible, setHelpModalVisible] = useState(false);
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [subdivisionModalVisible, setSubdivisionModalVisible] = useState(false);
  const [subdivisionResultEditVisible, setSubdivisionResultEditVisible] = useState(false);
  const [subdivisionResultData, setSubdivisionResultData] = useState<any>(null);
  const [subWorkflowViewerVisible, setSubWorkflowViewerVisible] = useState(false);
  const [currentSubWorkflowId, setCurrentSubWorkflowId] = useState<string | null>(null);
  const [currentTask, setCurrentTask] = useState<any>(null);
  const [subWorkflowsForSubmit, setSubWorkflowsForSubmit] = useState<any[]>([]);
  const [loadingSubWorkflows, setLoadingSubWorkflows] = useState(false);

  // 🆕 下游条件节点选择相关状态
  const [conditionalDownstreamNodes, setConditionalDownstreamNodes] = useState<any[]>([]);
  const [selectedDownstreamNodes, setSelectedDownstreamNodes] = useState<string[]>([]);
  const [loadingDownstreamNodes, setLoadingDownstreamNodes] = useState(false);

  const [submitForm] = Form.useForm();
  const [helpForm] = Form.useForm();
  const [rejectForm] = Form.useForm();
  const [cancelForm] = Form.useForm();

  useEffect(() => {
    if (user) {
      loadTasks();
    }
  }, [user, loadTasks]);

  // 加载工作流信息
  useEffect(() => {
    const loadWorkflowInfo = async () => {
      const workflowIds = [...new Set(tasks.map(task => task.workflow_instance_id))];
      const newWorkflowCache = { ...workflowCache };
      
      for (const workflowId of workflowIds) {
        if (!workflowCache[workflowId] && workflowId) {
          try {
            const response = await executionAPI.getWorkflowInstanceDetail(workflowId);
            const responseData = response as any;
            if (responseData && responseData.success && responseData.data) {
              // 优先使用工作流模板名称，然后是工作流名称，最后是实例名称
              const templateName = responseData.data.workflow_name || 
                                 responseData.data.name || 
                                 responseData.data.workflow_instance_name || 
                                 '未知工作流';
              newWorkflowCache[workflowId] = {
                name: templateName,
                status: responseData.data.status || '未知状态'
              };
            } else {
              newWorkflowCache[workflowId] = {
                name: '未知工作流',
                status: '未知状态'
              };
            }
          } catch (error) {
            console.warn(`加载工作流信息失败 ${workflowId}:`, error);
            newWorkflowCache[workflowId] = {
              name: '加载失败',
              status: '未知状态'
            };
          }
        }
      }
      
      if (Object.keys(newWorkflowCache).length !== Object.keys(workflowCache).length) {
        setWorkflowCache(newWorkflowCache);
      }
    };

    if (tasks.length > 0) {
      loadWorkflowInfo();
    }
  }, [tasks]);

  useEffect(() => {
    if (error) {
      message.error(error);
    }
  }, [error]);

  // 筛选和搜索逻辑
  useEffect(() => {
    let filtered = [...tasks];
    
    // 状态筛选
    if (statusFilter !== 'all') {
      filtered = filtered.filter(task => task.status.toLowerCase() === statusFilter);
    }
    
    // 工作流筛选
    if (workflowFilter !== 'all') {
      filtered = filtered.filter(task => {
        const contextWorkflow = task.context_data?.workflow;
        const cachedWorkflow = workflowCache[task.workflow_instance_id];
        const workflowName = contextWorkflow?.name || 
                           contextWorkflow?.workflow_instance_name ||
                           cachedWorkflow?.name || '';
        return workflowName === workflowFilter;
      });
    }
    
    // 搜索文本筛选
    if (searchText.trim()) {
      const searchLower = searchText.toLowerCase();
      filtered = filtered.filter(task => {
        // 搜索任务标题和描述
        const titleMatch = task.task_title?.toLowerCase().includes(searchLower);
        const descMatch = task.task_description?.toLowerCase().includes(searchLower);
        
        // 搜索工作流名称
        const contextWorkflow = task.context_data?.workflow;
        const cachedWorkflow = workflowCache[task.workflow_instance_id];
        const workflowName = contextWorkflow?.name || 
                           contextWorkflow?.workflow_instance_name ||
                           cachedWorkflow?.name || '';
        const workflowMatch = workflowName.toLowerCase().includes(searchLower);
        
        return titleMatch || descMatch || workflowMatch;
      });
    }
    
    setFilteredTasks(filtered);
    // 筛选条件变化时重置到第一页
    setCurrentPage(1);
  }, [tasks, searchText, statusFilter, workflowFilter, workflowCache]);

  // 分页逻辑
  useEffect(() => {
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    setPaginatedTasks(filteredTasks.slice(startIndex, endIndex));
  }, [filteredTasks, currentPage, pageSize]);

  // 处理分页变化
  const handlePageChange = (page: number, size?: number) => {
    setCurrentPage(page);
    if (size && size !== pageSize) {
      setPageSize(size);
      // 重置到第一页
      setCurrentPage(1);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'orange';
      case 'assigned':
        return 'cyan';
      case 'in_progress':
        return 'blue';
      case 'completed':
        return 'green';
      case 'failed':
        return 'red';
      case 'cancelled':
        return 'gray';
      case 'overdue':
        return 'volcano';
      default:
        return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return '待分配';
      case 'assigned':
        return '已分配';
      case 'in_progress':
        return '进行中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      case 'cancelled':
        return '已取消';
      case 'overdue':
        return '已逾期';
      default:
        return '未知';
    }
  };

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 3:
        return 'red';
      case 2:
        return 'orange';
      case 1:
        return 'green';
      default:
        return 'default';
    }
  };

  const getPriorityText = (priority: number) => {
    switch (priority) {
      case 3:
        return '高';
      case 2:
        return '中';
      case 1:
        return '低';
      default:
        return '未知';
    }
  };

  // 清空所有筛选
  const clearFilters = () => {
    setSearchText('');
    setStatusFilter('all');
    setWorkflowFilter('all');
    setCurrentPage(1); // 重置到第一页
  };

  // 处理文件下载（带认证）
  const handleFileDownload = async (fileId: string) => {
    try {
      await FileAPI.downloadFile(fileId);
    } catch (error) {
      console.error('文件下载失败:', error);
      message.error('文件下载失败，请稍后重试');
    }
  };

  // 检查任务是否可以拆解
  const canSubdivideTask = (task: any) => {
    const status = task.status?.toLowerCase();
    const taskType = task.task_type?.toLowerCase();
    
    // console.log('🔍 拆解检查 - 任务:', task.task_title);
    // console.log('   - 状态:', status);
    // console.log('   - 类型:', taskType);
    
    // 待分配、已分配或进行中状态的人工任务或混合任务可以拆解
    // 增加了in_progress状态，允许在执行过程中拆解任务
    const canSubdivide = (status === 'pending' || status === 'assigned' || status === 'in_progress') && 
           (taskType === 'human' || taskType === 'mixed' || taskType === 'processor');
    
    
    return canSubdivide;
  };

  // 检查任务是否有细分结果可以编辑（严格检查：基于context_data中的标记字段）
  const hasSubdivisionResult = (task: any) => {
    // 只有当任务明确标记为有参考数据且未自动提交时，才显示编辑细分结果按钮
    if (task.task_type !== 'human' || task.status?.toLowerCase() !== 'in_progress') {
      return false;
    }
    
    // 🔧 修复：优先检查output_data中的细分结果（新格式）
    const outputData = task.output_data;
    if (outputData) {
      try {
        let parsedOutput;
        if (typeof outputData === 'string') {
          parsedOutput = JSON.parse(outputData);
        } else if (typeof outputData === 'object') {
          parsedOutput = outputData;
        }
        
        // 检查新的细分结果格式
        if (parsedOutput && parsedOutput.type === 'subdivision_result' && parsedOutput.auto_submitted === false) {
          return true;
        }
      } catch (error) {
        console.warn('解析任务output_data失败:', error);
      }
    }
    
    // 回退检查：检查context_data中的具体标记字段（兼容旧格式）
    const contextData = task.context_data;
    if (contextData) {
      try {
        let parsedContext;
        if (typeof contextData === 'string') {
          parsedContext = JSON.parse(contextData);
        } else if (typeof contextData === 'object') {
          parsedContext = contextData;
        }
        
        // 只有当明确标记为参考数据且未自动提交时，才认为有细分结果
        return parsedContext && 
               parsedContext.is_reference_data === true && 
               parsedContext.auto_submitted === false;
      } catch (e) {
        // 解析失败，返回false
        return false;
      }
    }
    
    return false;
  };

  // 检查任务是否已进行拆解（有子工作流）- 基于真实数据的检测
  const hasSubWorkflow = (task: any) => {
    // 检查context_data中是否有subdivision信息（最可靠的方式）
    const contextData = task.context_data;
    if (contextData) {
      // 处理对象格式
      if (typeof contextData === 'object') {
        // 只有当任务真正被拆解并产生了子工作流实例时，才显示按钮
        if (contextData.subdivision_id && contextData.sub_workflow_instance_id) {
          return true;
        }
      }
      
      // 处理字符串格式
      if (typeof contextData === 'string') {
        try {
          const parsedContext = JSON.parse(contextData);
          // 必须同时有subdivision_id和sub_workflow_instance_id才认为有可查看的子工作流
          if (parsedContext.subdivision_id && parsedContext.sub_workflow_instance_id) {
            return true;
          }
        } catch (e) {
          // JSON解析失败，返回false
        }
      }
    }
    
    return false;
  };

  // 从任务数据中提取子工作流实例ID
  const extractSubWorkflowId = (task: any): string | null => {
    const contextData = task.context_data;
    
    // 尝试从上下文数据中提取工作流实例ID
    if (contextData && typeof contextData === 'object') {
      // 优先返回工作流实例ID，这是我们需要的
      return contextData.sub_workflow_instance_id || null;
    }
    
    // 尝试从字符串格式的上下文数据中提取
    if (typeof contextData === 'string') {
      try {
        const parsedContext = JSON.parse(contextData);
        return parsedContext.sub_workflow_instance_id || null;
      } catch (e) {
        // 如果无法解析JSON，尝试正则表达式提取工作流实例ID
        const workflowIdMatch = contextData.match(/sub_workflow_instance_id["\s]*:["\s]*([a-f0-9-]+)/i);
        if (workflowIdMatch) {
          return workflowIdMatch[1];
        }
      }
    }
    
    return null;
  };

  // 🆕 加载下游条件节点
  const loadConditionalDownstreamNodes = async (taskId: string) => {
    console.log('🔍 [DOWNSTREAM] loadConditionalDownstreamNodes函数被调用，taskId:', taskId);
    try {
      setLoadingDownstreamNodes(true);
      console.log('🔍 [DOWNSTREAM] 开始获取下游条件节点:', taskId);

      const response = await taskAPI.getConditionalDownstreamNodes(taskId);
      console.log('🔍 [DOWNSTREAM] API响应原始数据:', response);

      // 响应拦截器已处理，需要正确访问数据
      const responseData = response as any;
      console.log('🔍 [DOWNSTREAM] responseData.success:', responseData.success);
      console.log('🔍 [DOWNSTREAM] responseData.success类型:', typeof responseData.success);

      if (responseData.success) {
        const nodes = responseData.data.conditional_downstream_nodes || [];
        console.log('✅ [DOWNSTREAM] 获取到下游条件节点:', nodes);
        console.log('✅ [DOWNSTREAM] 节点数量:', nodes.length);
        console.log('✅ [DOWNSTREAM] 完整响应数据:', responseData.data);

        setConditionalDownstreamNodes(nodes);
        setSelectedDownstreamNodes([]); // 重置选择

        console.log('✅ [DOWNSTREAM] 状态已更新，conditionalDownstreamNodes长度:', nodes.length);
      } else {
        console.warn('⚠️ [DOWNSTREAM] 获取下游条件节点失败，响应:', responseData);
        setConditionalDownstreamNodes([]);
      }
    } catch (error) {
      console.error('❌ [DOWNSTREAM] 获取下游条件节点异常:', error);
      setConditionalDownstreamNodes([]);
    } finally {
      setLoadingDownstreamNodes(false);
      console.log('🔍 [DOWNSTREAM] 加载完成，设置loading为false');
    }
  };

  const handleSubmit = async (task: any) => {
    console.log('🚀 [SUBMIT] handleSubmit 被调用:');
    console.log('   - 任务:', task.task_title);
    console.log('   - 任务ID:', task.task_instance_id);
    console.log('   - 当前subWorkflowsForSubmit状态:', subWorkflowsForSubmit);

    setCurrentTask(task);
    setSubmitModalVisible(true);
    submitForm.resetFields();

    console.log('🎯 [SUBMIT] 模态框状态设置完成，开始加载草稿...');
    console.log('🎯 [SUBMIT] 当前conditionalDownstreamNodes:', conditionalDownstreamNodes);

    // 🆕 获取下游条件节点（所有任务类型都支持）
    await loadConditionalDownstreamNodes(task.task_instance_id);

    console.log('🎯 [SUBMIT] 下游节点加载完成后conditionalDownstreamNodes:', conditionalDownstreamNodes);
    
    // 加载草稿数据
    const draft = getTaskDraft(task.task_instance_id);
    if (draft) {
      submitForm.setFieldsValue(draft);
      message.info('已加载草稿数据');
    }
    
    console.log('📡 [SUBMIT] 即将调用 loadSubWorkflowsForTask...');
    // 加载相关的子工作流
    await loadSubWorkflowsForTask(task);
    console.log('✅ [SUBMIT] loadSubWorkflowsForTask 调用完成');
  };
  
  // 加载任务相关的子工作流
  const loadSubWorkflowsForTask = async (task: any) => {
    setLoadingSubWorkflows(true);
    console.log('🚀 开始加载子工作流 - 当前状态重置');
    setSubWorkflowsForSubmit([]); // 先重置状态
    
    try {
      console.log('🔍 加载任务相关的子工作流:', task.task_instance_id);
      console.log('📋 任务信息:', {
        task_title: task.task_title,
        task_instance_id: task.task_instance_id,
        task_type: task.task_type
      });
      
      // 添加任务ID验证信息，帮助用户测试正确的任务
      console.log('🆔 任务ID验证信息:');
      console.log('   当前测试的任务ID:', task.task_instance_id);
      console.log('   已知有子工作流的任务ID示例:');
      console.log('   - c97166a9-4099-48bf-9832-eb486e9a685f (有7个子工作流实例)');
      console.log('   - 0e69c924-fbe7-4be4-9514-5bbf7dc9c8d1 (有2个子工作流实例)');
      console.log('   - e4f58eae-60de-4ebb-b42f-4d5f5de76642 (有3个子工作流实例)');
      console.log('   💡 如果显示"该任务没有相关的子工作流"，请尝试上面列出的任务ID');
      
      // 获取任务的细分列表（只要有工作流实例的）
      console.log('📡 调用API: getTaskSubdivisions with withInstancesOnly=true');
      const response = await taskSubdivisionApi.getTaskSubdivisions(task.task_instance_id, true);
      console.log('📨 API原始响应:', response);
      
      // 修复：根据API拦截器的实现，response已经是解构后的业务数据
      // 但TypeScript认为它是AxiosResponse，所以需要类型断言
      const responseData = response as any;
      console.log('📊 响应数据解析:', {
        hasResponseData: !!responseData,
        isSuccess: responseData?.success,
        hasData: !!(responseData?.data),
        dataStructure: responseData?.data ? Object.keys(responseData.data) : 'no data'
      });
      
      if (responseData && responseData.success && responseData.data) {
        const subdivisions = responseData.data.subdivisions || [];
        console.log('📋 细分数据:', {
          subdivisionsCount: subdivisions.length,
          totalSubdivisions: responseData.data.total_subdivisions,
          withInstancesOnly: responseData.data.with_instances_only,
          subdivisionsSample: subdivisions.slice(0, 2).map((s: any) => ({
            name: s.subdivision_name,
            id: s.subdivision_id,
            hasWorkflowInstance: !!s.workflow_instance
          }))
        });
        
        // 直接使用已经增强的细分数据，无需再次获取详情
        const subWorkflowsWithDetails = subdivisions.map((subdivision: any) => ({
          ...subdivision,
          // 将workflow_instance信息映射到workflowDetails中，保持兼容性
          workflowDetails: {
            ...subdivision.workflow_instance,
            subdivision_id: subdivision.subdivision_id,
            subdivision_name: subdivision.subdivision_name,
            sub_workflow_instance_id: subdivision.sub_workflow_instance_id,
            sub_workflow_base_id: subdivision.sub_workflow_base_id,
            status: subdivision.workflow_instance?.status || subdivision.status,
            completed_at: subdivision.workflow_instance?.completed_at || subdivision.completed_at,
            created_at: subdivision.workflow_instance?.created_at || subdivision.subdivision_created_at
          }
        }));
        
        console.log('🎨 数据映射完成:', {
          mappedCount: subWorkflowsWithDetails.length,
          sampleData: subWorkflowsWithDetails.slice(0, 1).map((s: any) => ({
            subdivision_name: s.subdivision_name,
            status: s.status,
            workflowDetails: {
              status: s.workflowDetails?.status,
              workflow_instance_name: s.workflowDetails?.workflow_instance_name
            }
          }))
        });
        
        setSubWorkflowsForSubmit(subWorkflowsWithDetails);
        console.log('✅ 状态更新完成 - 加载到子工作流:', subWorkflowsWithDetails.length, '个（仅包含有实例的）');
        
        if (subdivisions.length === 0 && responseData.data.total_subdivisions > 0) {
          console.log(`ℹ️ 该任务有 ${responseData.data.total_subdivisions} 个细分记录，但都没有工作流实例`);
          console.log('📝 这意味着：');
          console.log('   1. 任务已经被拆解过');
          console.log('   2. 但拆解创建的工作流实例可能失败或被删除');
          console.log('   3. 或者细分状态还是created，没有转为executing');
        } else if (subdivisions.length === 0 && responseData.data.total_subdivisions === 0) {
          console.log('ℹ️ 该任务没有任何细分记录');
          console.log('📝 这意味着：');
          console.log('   1. 该任务从未被拆解过');
          console.log('   2. 如果想测试子工作流功能，请先拆解任务或选择已拆解的任务');
        }
      } else {
        console.log('❌ API响应无效，重置子工作流状态');
        setSubWorkflowsForSubmit([]);
        console.log('ℹ️ 该任务没有相关的子工作流');
      }
    } catch (error: any) {
      console.error('❌ 加载子工作流失败:', error);
      console.error('❌ 错误详情:', {
        message: error?.message,
        status: error?.response?.status,
        statusText: error?.response?.statusText,
        data: error?.response?.data
      });
      setSubWorkflowsForSubmit([]);
    } finally {
      setLoadingSubWorkflows(false);
      console.log('🏁 子工作流加载流程结束');
    }
  };
  
  // 查看子工作流详情
  const handleViewSubWorkflowDetails = (subWorkflow: any) => {
    console.log('🔍 查看子工作流详情:', subWorkflow);
    
    // 获取子工作流实例ID
    const subWorkflowId = subWorkflow.workflowDetails?.sub_workflow_instance_id || 
                         subWorkflow.sub_workflow_instance_id ||
                         subWorkflow.workflow_instance_id;
    
    if (subWorkflowId) {
      setCurrentSubWorkflowId(subWorkflowId);
      setSubWorkflowViewerVisible(true);
    } else {
      message.warning('无法找到子工作流实例ID');
    }
  };
  
  // 选择子工作流结果并填充到任务结果中
  const handleSelectSubWorkflowResult = async (subWorkflow: any) => {
    try {
      console.log('📝 选择子工作流结果:', subWorkflow);
      
      // 获取subdivision_id
      const subdivisionId = subWorkflow.subdivision_id;
      if (!subdivisionId) {
        message.error('无法获取细分ID');
        return;
      }
      
      // 1. 首先标记该subdivision为选择状态
      console.log('🎯 标记subdivision为选择状态:', subdivisionId);
      try {
        const selectResponse = await taskSubdivisionApi.selectSubdivision(subdivisionId);
        const selectResponseData = selectResponse as any;
        
        if (!selectResponseData?.success) {
          console.warn('⚠️ 标记subdivision选择状态失败，但继续处理结果选择');
        } else {
          console.log('✅ subdivision标记选择成功');
        }
      } catch (selectError: any) {
        console.warn('⚠️ 标记subdivision选择状态时出错:', selectError);
        // 不阻断流程，继续处理结果选择
      }
      
      console.log('🔍 正在获取子工作流的实际执行结果...');
      message.loading('正在获取子工作流执行结果...', 0);
      
      // 2. 获取子工作流执行结果
      const response = await taskSubdivisionApi.getSubdivisionWorkflowResults(subdivisionId);
      message.destroy(); // 销毁loading消息
      
      // 修复：根据API拦截器的实现，response已经是解构后的业务数据
      // 但TypeScript认为它是AxiosResponse，所以需要类型断言
      const responseData = response as any;
      
      if (!responseData || !responseData.success || !responseData.data) {
        message.error('获取子工作流结果失败');
        return;
      }
      
      const resultData = responseData.data;
      console.log('✅ 获取到子工作流执行结果:', resultData);
      
      // 优先使用后端格式化的结果
      let resultText = '';
      
      if (resultData.formatted_result) {
        // 使用后端格式化的完整结果
        resultText = resultData.formatted_result;
        console.log('📄 使用后端格式化的结果');
      } else if (resultData.final_output) {
        // 使用最终输出
        const finalOutput = resultData.final_output;
        const subdivisionName = resultData.subdivision_name || subWorkflow.subdivision_name || '子工作流';
        
        resultText = `=== ${subdivisionName} 执行结果 ===\n\n${finalOutput}`;
        
        // 添加执行统计信息
        if (resultData.total_tasks || resultData.completed_tasks) {
          resultText += `\n\n📊 执行统计:\n`;
          resultText += `   • 总任务数: ${resultData.total_tasks || 0}\n`;
          resultText += `   • 完成任务数: ${resultData.completed_tasks || 0}\n`;
          if (resultData.failed_tasks > 0) {
            resultText += `   • 失败任务数: ${resultData.failed_tasks}\n`;
          }
        }
        
        console.log('📄 使用最终输出构建结果');
      } else {
        // 回退到基本信息
        const subdivisionName = resultData.subdivision_name || subWorkflow.subdivision_name || '子工作流';
        const status = resultData.workflow_status || '未知';
        
        resultText = `=== ${subdivisionName} 执行结果 ===\n\n状态: ${status}\n\n`;
        
        if (resultData.total_tasks) {
          resultText += `执行统计:\n`;
          resultText += `   • 总任务数: ${resultData.total_tasks}\n`;
          resultText += `   • 完成任务数: ${resultData.completed_tasks}\n`;
          if (resultData.failed_tasks > 0) {
            resultText += `   • 失败任务数: ${resultData.failed_tasks}\n`;
          }
          resultText += '\n';
        }
        
        resultText += '请根据子工作流的执行情况补充具体的任务完成结果。';
        console.log('📄 使用基本信息构建结果');
      }
      
      // 获取当前表单的结果值
      const currentResult = submitForm.getFieldValue('result') || '';
      
      // 如果当前已有内容，询问是否要替换还是追加
      if (currentResult.trim()) {
        Modal.confirm({
          title: '填充子工作流结果',
          content: '当前任务结果框中已有内容，您希望：',
          okText: '替换当前内容',
          cancelText: '追加到当前内容',
          onOk: () => {
            submitForm.setFieldsValue({ result: resultText });
            message.success('已替换任务结果');
          },
          onCancel: () => {
            const combinedResult = currentResult + '\n\n=== 子工作流结果 ===\n' + resultText;
            submitForm.setFieldsValue({ result: combinedResult });
            message.success('已追加子工作流结果');
          }
        });
      } else {
        // 直接填充
        submitForm.setFieldsValue({ result: resultText });
        message.success('已填充子工作流结果，您可以进一步编辑');
      }
      
    } catch (error) {
      message.destroy(); // 确保销毁loading消息
      console.error('❌ 选择子工作流结果失败:', error);
      message.error('获取子工作流结果失败，请稍后重试');
    }
  };

  const handleViewDetails = async (task: any) => {
    // 调用API获取完整的任务详情（包含context_data和current_task_attachments）
    try {
      await getTaskDetails(task.task_instance_id);

      // 直接使用taskStore中的currentTask，确保获取最新的完整数据
      if (taskStoreCurrentTask && taskStoreCurrentTask.task_instance_id === task.task_instance_id) {

        // 🔍 详细调试上游上下文数据
        console.log('🔍 [详细调试] 完整任务数据:', taskStoreCurrentTask);

        // 🔍 对比调试：immediate_upstream_results vs all_upstream_results
        console.log('🆚 [数据源对比] 开始对比两种数据源...');

        if (taskStoreCurrentTask.upstream_context) {
          console.log('🔍 [详细调试] upstream_context:', taskStoreCurrentTask.upstream_context);
          if (taskStoreCurrentTask.upstream_context.immediate_upstream_results) {
            console.log('🔍 [详细调试] immediate_upstream_results:', taskStoreCurrentTask.upstream_context.immediate_upstream_results);
            Object.keys(taskStoreCurrentTask.upstream_context.immediate_upstream_results).forEach(nodeKey => {
              const nodeData = taskStoreCurrentTask.upstream_context?.immediate_upstream_results?.[nodeKey];
              if (nodeData) {
                console.log(`🟢 [IMMEDIATE] 节点 ${nodeKey}:`, nodeData);
                console.log(`🟢 [IMMEDIATE] 节点 ${nodeKey} 的attachments:`, nodeData.attachments);
                // 🔍 详细打印每个附件
                if (nodeData.attachments && nodeData.attachments.length > 0) {
                  nodeData.attachments.forEach((att: any, index: number) => {
                    console.log(`🟢 [IMMEDIATE] 附件 #${index + 1}:`, {
                      file_id: att.file_id,
                      filename: att.filename,
                      association_type: att.association_type,
                      file_size: att.file_size,
                      content_type: att.content_type
                    });
                  });
                } else {
                  console.log(`🟢 [IMMEDIATE] 节点 ${nodeKey} 无附件`);
                }
              }
            });
          }
        }

        // 🔍 对比调试：检查all_upstream_results
        if (taskStoreCurrentTask.upstream_context && taskStoreCurrentTask.upstream_context.all_upstream_results) {
          console.log('🔍 [详细调试] all_upstream_results:', taskStoreCurrentTask.upstream_context.all_upstream_results);
          Object.keys(taskStoreCurrentTask.upstream_context.all_upstream_results).forEach(nodeKey => {
            const nodeData = taskStoreCurrentTask.upstream_context?.all_upstream_results?.[nodeKey];
            if (nodeData) {
              console.log(`🟡 [ALL_UPSTREAM] 节点 ${nodeKey}:`, nodeData);
              console.log(`🟡 [ALL_UPSTREAM] 节点 ${nodeKey} 的attachments:`, nodeData.attachments);
              // 🔍 详细打印每个附件
              if (nodeData.attachments && nodeData.attachments.length > 0) {
                nodeData.attachments.forEach((att: any, index: number) => {
                  console.log(`🟡 [ALL_UPSTREAM] 附件 #${index + 1}:`, {
                    file_id: att.file_id,
                    filename: att.filename,
                    association_type: att.association_type,
                    file_size: att.file_size,
                    content_type: att.content_type
                  });
                });
              } else {
                console.log(`🟡 [ALL_UPSTREAM] 节点 ${nodeKey} 无附件`);
              }
            }
          });
        } else {
          console.log('🟡 [ALL_UPSTREAM] 未找到all_upstream_results数据');
        }

        // 解析context_data字符串为对象（如果是字符串）
        let parsedTask = { ...taskStoreCurrentTask };
        if (typeof taskStoreCurrentTask.context_data === 'string' && (taskStoreCurrentTask.context_data as string).trim()) {
          try {
            parsedTask.context_data = JSON.parse(taskStoreCurrentTask.context_data as string);
          } catch (parseError) {
            console.warn('context_data解析失败，保持原始格式', parseError);
          }
        }

        // 解析input_data字符串为对象（如果是字符串）
        if (typeof taskStoreCurrentTask.input_data === 'string' && (taskStoreCurrentTask.input_data as string).trim()) {
          try {
            parsedTask.input_data = JSON.parse(taskStoreCurrentTask.input_data as string);
          } catch (parseError) {
            console.warn('input_data解析失败，保持原始格式', parseError);
          }
        }

        setCurrentTask(parsedTask);
      } else {
        setCurrentTask(task);
      }
    } catch (error) {
      console.error('获取任务详情失败', error);
      setCurrentTask(task);
    }

    setDetailModalVisible(true);
  };

  const handleSubmitConfirm = async () => {
    try {
      // 防护检查
      if (!currentTask) {
        message.error('当前任务信息丢失，请重新打开提交窗口');
        return;
      }
      
      if (!currentTask.task_instance_id) {
        console.error('❌ currentTask缺少task_instance_id:', currentTask);
        message.error('任务ID缺失，无法提交。请刷新页面重试');
        return;
      }
      
      console.log('🔄 提交任务结果:', {
        task_instance_id: currentTask.task_instance_id,
        task_title: currentTask.task_title
      });
      
      const values = await submitForm.validateFields();
      
      // 🆕 获取附件ID列表
      const attachmentFileIds = values.attachment_file_ids || [];
      console.log('📎 提交的附件ID列表:', attachmentFileIds);

      // 🆕 获取选中的下游节点ID列表
      console.log('🔀 提交的下游节点ID列表:', selectedDownstreamNodes);

      await submitTaskResult(
        currentTask.task_instance_id,
        values.result,
        values.notes,
        attachmentFileIds,
        selectedDownstreamNodes  // 传递选中的下游节点
      );
      message.success('任务提交成功');
      setSubmitModalVisible(false);
      setCurrentTask(null);
      // 🆕 重置下游节点相关状态
      setConditionalDownstreamNodes([]);
      setSelectedDownstreamNodes([]);
      loadTasks(); // 重新加载任务列表
    } catch (error) {
      console.error('提交失败:', error);
      message.error('提交失败，请重试');
    }
  };

  const handleStartTask = async (task: any) => {
    try {
      await startTask(task.task_instance_id);
      message.success('任务已开始');
    } catch (error) {
      message.error('开始任务失败');
    }
  };

  const handlePauseTask = async (task: any) => {
    try {
      await pauseTask(task.task_instance_id, '用户手动暂停');
      message.success('任务已暂停');
      loadTasks(); // 重新加载任务列表
    } catch (error) {
      console.error('暂停任务失败:', error);
      message.error('暂停任务失败');
    }
  };

  const handleRequestHelp = (task: any) => {
    setCurrentTask(task);
    setHelpModalVisible(true);
    helpForm.resetFields();
  };

  const handleHelpSubmit = async () => {
    try {
      const values = await helpForm.validateFields();
      await requestHelp(currentTask.task_instance_id, values.help_message);
      message.success('帮助请求已提交');
      setHelpModalVisible(false);
    } catch (error) {
      console.error('提交帮助请求失败:', error);
    }
  };

  const handleSaveDraft = () => {
    submitForm.validateFields().then(values => {
      saveTaskDraft(currentTask.task_instance_id, values);
      message.success('草稿已保存');
    }).catch(() => {
      message.warning('请先填写必填字段');
    });
  };

  const handleRejectTask = (task: any) => {
    setCurrentTask(task);
    setRejectModalVisible(true);
    rejectForm.resetFields();
  };

  const handleRejectConfirm = async () => {
    try {
      const values = await rejectForm.validateFields();
      await rejectTask(currentTask.task_instance_id, values.reject_reason);
      message.success('任务已拒绝');
      setRejectModalVisible(false);
    } catch (error) {
      console.error('拒绝任务失败:', error);
    }
  };

  const handleCancelTask = (task: any) => {
    setCurrentTask(task);
    setCancelModalVisible(true);
    cancelForm.resetFields();
  };

  const handleCancelConfirm = async () => {
    try {
      const values = await cancelForm.validateFields();
      await cancelTask(currentTask.task_instance_id, values.cancel_reason || "用户取消");
      message.success('任务已取消');
      setCancelModalVisible(false);
    } catch (error) {
      console.error('取消任务失败:', error);
    }
  };

  const handleDeleteTask = async (task: any) => {
    console.log('🗑️ 点击删除任务按钮', task);
    
    try {
      console.log('🔔 准备显示确认对话框');
      
      // 临时使用原生确认对话框进行测试
      const confirmed = window.confirm(`确定要删除任务"${task.task_title}"吗？删除后将无法恢复。`);
      
      if (confirmed) {
        console.log('📝 用户确认删除，开始调用deleteTask');
        try {
          await deleteTask(task.task_instance_id);
          console.log('✅ 删除任务成功');
          message.success('任务已删除');
        } catch (error) {
          console.error('❌ 删除任务失败:', error);
          message.error('删除任务失败，请稍后再试');
        }
      } else {
        console.log('🚫 用户取消删除');
      }
    } catch (error) {
      console.error('❌ 删除任务处理失败:', error);
      message.error('删除任务失败');
    }
  };

  // 处理任务拆解
  const handleSubdivideTask = (task: any) => {
    console.log('🔀 打开任务拆解模态框', task);
    setCurrentTask(task);
    setSubdivisionModalVisible(true);
  };

  // 任务拆解成功后的回调
  const handleSubdivisionSuccess = () => {
    setSubdivisionModalVisible(false);
    setCurrentTask(null);
    loadTasks(); // 重新加载任务列表
    message.success('任务拆解成功！');
  };

  // 处理细分结果编辑
  const handleEditSubdivisionResult = (task: any) => {
    console.log('🔧 编辑细分结果，任务数据:', task);
    
    // 🔧 修复：从实际的output_data中提取细分结果
    let subdivisionResult = null;
    
    // 尝试从output_data获取（新格式）
    if (task.output_data) {
      try {
        let parsedOutput;
        if (typeof task.output_data === 'string') {
          parsedOutput = JSON.parse(task.output_data);
        } else {
          parsedOutput = task.output_data;
        }
        
        if (parsedOutput && parsedOutput.type === 'subdivision_result') {
          subdivisionResult = {
            subdivision_id: parsedOutput.subdivision_id,
            subdivision_name: `细分任务 ${parsedOutput.subdivision_id.slice(0, 8)}`,
            original_result: parsedOutput.final_output || '细分工作流执行完成',
            total_tasks: parsedOutput.execution_summary?.total_tasks || 0,
            completed_tasks: parsedOutput.execution_summary?.completed_tasks || 0,
            failed_tasks: parsedOutput.execution_summary?.failed_tasks || 0,
            execution_summary: `任务执行完成：${parsedOutput.execution_summary?.completed_tasks || 0}/${parsedOutput.execution_summary?.total_tasks || 0}`
          };
        }
      } catch (error) {
        console.warn('解析output_data失败:', error);
      }
    }
    
    // 回退：从context_data获取（兼容旧格式）
    if (!subdivisionResult && task.context_data) {
      try {
        let parsedContext;
        if (typeof task.context_data === 'string') {
          parsedContext = JSON.parse(task.context_data);
        } else {
          parsedContext = task.context_data;
        }
        
        if (parsedContext && parsedContext.execution_results) {
          const results = parsedContext.execution_results;
          subdivisionResult = {
            subdivision_id: parsedContext.subdivision_id,
            subdivision_name: `细分任务 ${parsedContext.subdivision_id?.slice(0, 8) || '未知'}`,
            original_result: results.final_output || '细分工作流执行完成',
            total_tasks: results.total_tasks || 0,
            completed_tasks: results.completed_tasks || 0,
            failed_tasks: results.failed_tasks || 0,
            execution_summary: `任务执行完成：${results.completed_tasks || 0}/${results.total_tasks || 0}`
          };
        }
      } catch (error) {
        console.warn('解析context_data失败:', error);
      }
    }
    
    // 如果都没有找到数据，使用基础信息
    if (!subdivisionResult) {
      subdivisionResult = {
        subdivision_id: 'unknown-subdivision',
        subdivision_name: '细分工作流结果',
        original_result: task.instructions || '细分工作流执行完成，详细结果请查看任务说明。',
        total_tasks: 1,
        completed_tasks: 1,
        failed_tasks: 0,
        execution_summary: '基于现有信息构建的细分结果'
      };
    }
    
    console.log('📋 提取的细分结果数据:', subdivisionResult);
    
    setCurrentTask(task);
    setSubdivisionResultData(subdivisionResult);
    setSubdivisionResultEditVisible(true);
  };

  // 提交编辑后的细分结果
  const handleSubmitEditedSubdivisionResult = async (editedResult: string, resultSummary: string) => {
    try {
      // 这里应该调用API提交编辑后的结果给原始任务
      await submitTaskResult(currentTask.task_instance_id, editedResult, resultSummary);
      message.success('细分工作流结果已成功提交给原始任务');
      setSubdivisionResultEditVisible(false);
      setSubdivisionResultData(null);
      setCurrentTask(null);
      loadTasks(); // 重新加载任务列表
    } catch (error) {
      console.error('提交编辑结果失败:', error);
      message.error('提交失败，请重试');
    }
  };

  // 处理查看子工作流进度 - 基于修复后的检测逻辑
  const handleViewSubWorkflowProgress = (task: any) => {
    console.log('🔍 查看子工作流进度', task.task_title);
    
    // 由于hasSubWorkflow已经验证了任务有sub_workflow_instance_id，直接提取即可
    const subWorkflowId = extractSubWorkflowId(task);
    
    if (subWorkflowId) {
      console.log('📊 使用子工作流ID:', subWorkflowId);
      setCurrentSubWorkflowId(subWorkflowId);
      setCurrentTask(task);
      setSubWorkflowViewerVisible(true);
    } else {
      // 理论上不应该到这里，因为hasSubWorkflow已经验证过了
      console.error('❌ 按钮显示逻辑与实际数据不一致');
      message.error('无法找到子工作流信息，数据状态异常');
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>我的待办</h2>
      
      {/* 筛选和搜索区域 */}
      <Card style={{ marginBottom: '16px' }} size="small">
        <Row gutter={16} align="middle">
          <Col span={8}>
            <Input
              placeholder="搜索任务名称或工作流..."
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              allowClear
            />
          </Col>
          <Col span={4}>
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: '100%' }}
              placeholder="按状态筛选"
            >
              <Select.Option value="all">全部状态</Select.Option>
              {/* <Select.Option value="pending">待分配</Select.Option> */}
              <Select.Option value="assigned">已分配</Select.Option>
              <Select.Option value="in_progress">进行中</Select.Option>
              <Select.Option value="completed">已完成</Select.Option>
              {/* <Select.Option value="failed">失败</Select.Option> */}
              <Select.Option value="cancelled">已取消</Select.Option>
              {/* <Select.Option value="overdue">已逾期</Select.Option> */}
            </Select>
          </Col>
          <Col span={6}>
            <Select
              value={workflowFilter}
              onChange={setWorkflowFilter}
              style={{ width: '100%' }}
              placeholder="按工作流筛选"
              showSearch
              optionFilterProp="children"
            >
              <Select.Option value="all">全部工作流</Select.Option>
              {/* 动态生成工作流选项 - 按工作流名称去重 */}
              {(() => {
                // 收集所有唯一的工作流名称
                const workflowNames = new Set<string>();
                const workflowOptions: Array<{name: string, count: number}> = [];
                
                tasks.forEach(task => {
                  const contextWorkflow = task.context_data?.workflow;
                  const cachedWorkflow = workflowCache[task.workflow_instance_id];
                  const workflowName = contextWorkflow?.name || 
                                     contextWorkflow?.workflow_instance_name ||
                                     cachedWorkflow?.name || 
                                     `工作流 ${task.workflow_instance_id?.slice(0, 8)}...`;
                  
                  if (workflowName && !workflowNames.has(workflowName)) {
                    workflowNames.add(workflowName);
                    // 计算该工作流名称的任务数量
                    const count = tasks.filter(t => {
                      const tContextWorkflow = t.context_data?.workflow;
                      const tCachedWorkflow = workflowCache[t.workflow_instance_id];
                      const tWorkflowName = tContextWorkflow?.name || 
                                           tContextWorkflow?.workflow_instance_name ||
                                           tCachedWorkflow?.name || 
                                           `工作流 ${t.workflow_instance_id?.slice(0, 8)}...`;
                      return tWorkflowName === workflowName;
                    }).length;
                    
                    workflowOptions.push({ name: workflowName, count });
                  }
                });
                
                // 按任务数量倒序排列
                return workflowOptions
                  .sort((a, b) => b.count - a.count)
                  .map(option => (
                    <Select.Option key={option.name} value={option.name}>
                      {option.name} ({option.count}个任务)
                    </Select.Option>
                  ));
              })()}
            </Select>
          </Col>
          <Col span={4}>
            <Space>
              <Button 
                icon={<ClearOutlined />} 
                onClick={clearFilters}
                disabled={searchText === '' && statusFilter === 'all' && workflowFilter === 'all'}
              >
                清空
              </Button>
            </Space>
          </Col>
          <Col span={2}>
            <div style={{ fontSize: '12px', color: '#666', textAlign: 'right' }}>
              共 {filteredTasks.length} / {tasks.length} 个任务
              <br />
              第 {Math.min((currentPage - 1) * pageSize + 1, filteredTasks.length)}-{Math.min(currentPage * pageSize, filteredTasks.length)} 条
            </div>
          </Col>
        </Row>
      </Card>
      
      <Card>
        {filteredTasks.length > 0 ? (
          <>
            <List
              loading={loading}
              dataSource={paginatedTasks}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    // PENDING/ASSIGNED状态可以开始任务
                    (item.status.toLowerCase() === 'pending' || item.status.toLowerCase() === 'assigned') && (
                      <Button 
                        key="start" 
                        type="primary" 
                        size="small"
                        onClick={() => handleStartTask(item)}
                      >
                        开始任务
                      </Button>
                    ),
                    // PENDING/ASSIGNED状态的人工任务可以拆解
                    canSubdivideTask(item) && (
                      <Button 
                        key="subdivide" 
                        type="primary"
                        size="small"
                        icon={<BranchesOutlined />}
                        onClick={() => handleSubdivideTask(item)}
                        style={{ 
                          backgroundColor: '#722ed1', 
                          borderColor: '#722ed1',
                          fontWeight: 'bold'
                        }}
                      >
                        拆解任务
                      </Button>
                    ),
                    // 有细分结果可以编辑的任务显示编辑按钮
                    // hasSubdivisionResult(item) && (
                    //   <Button 
                    //     key="edit-subdivision-result" 
                    //     type="primary"
                    //     size="small"
                    //     icon={<EditOutlined />}
                    //     onClick={() => handleEditSubdivisionResult(item)}
                    //     style={{ 
                    //       backgroundColor: '#fa8c16', 
                    //       borderColor: '#fa8c16',
                    //       fontWeight: 'bold'
                    //     }}
                    //   >
                    //     编辑细分结果
                    //   </Button>
                    // ),
                    // 有子工作流的任务显示查看进度按钮
                    hasSubWorkflow(item) && (
                      <Button 
                        key="view-sub-workflow" 
                        type="primary"
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={() => handleViewSubWorkflowProgress(item)}
                        style={{ 
                          backgroundColor: '#52c41a', 
                          borderColor: '#52c41a',
                          fontWeight: 'bold'
                        }}
                      >
                        查看子工作流进度
                      </Button>
                    ),
                    // PENDING/ASSIGNED状态可以拒绝任务
                    // (item.status.toLowerCase() === 'pending' || item.status.toLowerCase() === 'assigned') && (
                    //   <Button 
                    //     key="reject" 
                    //     danger
                    //     size="small"
                    //     onClick={() => handleRejectTask(item)}
                    //   >
                    //     拒绝任务
                    //   </Button>
                    // ),
                    // IN_PROGRESS状态可以提交结果
                    item.status.toLowerCase() === 'in_progress' && (
                      <Button 
                        key="submit" 
                        type="primary" 
                        size="small"
                        icon={<SaveOutlined />}
                        onClick={() => handleSubmit(item)}
                      >
                        提交结果
                      </Button>
                    ),
                    // IN_PROGRESS状态可以暂停任务
                    // item.status.toLowerCase() === 'in_progress' && (
                    //   <Button 
                    //     key="pause" 
                    //     size="small"
                    //     onClick={() => handlePauseTask(item)}
                    //   >
                    //     暂停任务
                    //   </Button>
                    // ),
                    // 进行中、已分配、待分配状态可以取消任务
                    (item.status.toLowerCase() === 'in_progress' || 
                     item.status.toLowerCase() === 'assigned' || 
                     item.status.toLowerCase() === 'pending') && (
                      <Button 
                        key="cancel" 
                        danger
                        size="small"
                        onClick={() => handleCancelTask(item)}
                      >
                        取消任务
                      </Button>
                    ),
                    // 已完成和已取消状态可以删除任务
                    (item.status.toLowerCase() === 'completed' || item.status.toLowerCase() === 'cancelled') && (
                      <Button 
                        key="delete" 
                        danger
                        size="small"
                        onClick={() => {
                          console.log('🔍 删除按钮被点击，任务状态:', item.status);
                          handleDeleteTask(item);
                        }}
                      >
                        删除任务
                      </Button>
                    ),
                    // 所有状态都可以查看详情
                    <Button key="view" type="link" size="small" onClick={() => handleViewDetails(item)}>
                      查看详情
                    </Button>
                  ].filter(Boolean)}
                >
                  <List.Item.Meta
                    title={
                      <div>
                        {item.task_title}
                        <Tag color={getStatusColor(item.status)} style={{ marginLeft: '8px' }}>
                          {getStatusText(item.status)}
                        </Tag>
                      </div>
                    }
                    description={
                      <div>
                        <div>{item.task_description}</div>
                        {/* 显示上游上下文信息 */}
                        {item.input_data && (item.input_data.immediate_upstream || item.input_data.workflow_global) && (
                          <div style={{ marginTop: '8px' }}>
                            <Alert
                              message="包含上游上下文数据"
                              description={`上游节点数: ${item.input_data.node_info?.upstream_node_count || 0}个`}
                              type="info"
                              showIcon
                              style={{ fontSize: '12px' }}
                            />
                          </div>
                        )}
                        <div style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
                          <Space>
                            {/* 显示工作流信息 - 优先使用context_data，然后使用缓存的信息 */}
                            {(() => {
                              const contextWorkflow = item.context_data?.workflow;
                              const cachedWorkflow = workflowCache[item.workflow_instance_id];
                              
                              if (contextWorkflow?.name || contextWorkflow?.workflow_instance_name) {
                                return (
                                  <span style={{ color: '#1890ff' }}>
                                    工作流: {contextWorkflow.name || contextWorkflow.workflow_instance_name}
                                  </span>
                                );
                              } else if (cachedWorkflow?.name) {
                                return (
                                  <span style={{ color: '#1890ff' }}>
                                    工作流: {cachedWorkflow.name}
                                  </span>
                                );
                              } else if (item.workflow_instance_id) {
                                return (
                                  <span style={{ color: '#999' }}>
                                    工作流: 加载中...
                                  </span>
                                );
                              }
                              return null;
                            })()}
                            <span>创建时间: {item.created_at}</span>
                            {item.started_at && <span>开始时间: {item.started_at}</span>}
                            {item.completed_at && <span>完成时间: {item.completed_at}</span>}
                          </Space>
                        </div>
                        {item.result_summary && (
                          <div style={{ marginTop: '8px', padding: '8px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '4px' }}>
                            <strong>提交结果:</strong> {item.result_summary}
                          </div>
                        )}
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
            {/* 分页组件 */}
            <div style={{ marginTop: '16px', textAlign: 'center' }}>
              <Pagination
                current={currentPage}
                pageSize={pageSize}
                total={filteredTasks.length}
                showSizeChanger
                showQuickJumper
                showTotal={(total, range) => 
                  `第 ${range[0]}-${range[1]} 条/共 ${total} 条`
                }
                pageSizeOptions={['10', '20', '30', '50', '100']}
                onChange={handlePageChange}
                onShowSizeChange={handlePageChange}
              />
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📋</div>
            <div style={{ fontSize: '16px', color: '#666', marginBottom: '8px' }}>
              {tasks.length === 0 ? '暂无待办任务' : '没有找到匹配的任务'}
            </div>
            {tasks.length > 0 && filteredTasks.length === 0 && (
              <div style={{ fontSize: '14px', color: '#999' }}>
                尝试调整筛选条件或清空筛选
              </div>
            )}
          </div>
        )}
      </Card>

      {/* 任务详情模态框 */}
      <Modal
        title="任务详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width="90%"
        style={{ maxWidth: '1000px', top: 20 }}
      >
        {currentTask && (
          <div>

            <Card size="small" title="基本信息" style={{ marginBottom: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <Text strong>任务标题: </Text>
                  <Text>{currentTask.task_title}</Text>
                </div>
                <div>
                  <Text strong>任务状态: </Text>
                  <Tag color={getStatusColor(currentTask.status)}>
                    {getStatusText(currentTask.status)}
                  </Tag>
                </div>
                {/* <div>
                  <Text strong>优先级: </Text>
                  <Tag color={getPriorityColor(currentTask.priority)}>
                    {getPriorityText(currentTask.priority)}
                  </Tag>
                </div> */}
                <div>
                  <Text strong>任务类型: </Text>
                  <Text>{currentTask.task_type}</Text>
                </div>
              </div>
              <Divider />
              <div>
                <Text strong>任务描述: </Text>
                <Paragraph>{currentTask.task_description}</Paragraph>
              </div>
              {currentTask.instructions && (
                <div>
                  <Text strong>执行指令: </Text>
                  <Paragraph>{currentTask.instructions}</Paragraph>
                </div>
              )}
              
              {/* 🆕 当前任务附件 */}
              {currentTask.current_task_attachments && currentTask.current_task_attachments.length > 0 && (
                <div style={{ marginTop: '16px' }}>
                  <Text strong>任务附件: </Text>
                  
                  <div style={{ marginTop: '8px' }}>
                    <List
                      size="small"
                      dataSource={currentTask.current_task_attachments}
                      renderItem={(attachment: any) => (
                        <List.Item
                          style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}
                          actions={[
                            <Button 
                              key="download"
                              type="link" 
                              size="small"
                              icon={<DownloadOutlined />}
                              onClick={() => handleFileDownload(attachment.file_id)}
                            >
                              下载
                            </Button>
                          ]}
                        >
                          <List.Item.Meta
                            avatar={<FileOutlined style={{ color: '#1890ff' }} />}
                            title={
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Text strong>{attachment.filename}</Text>
                                <Tag 
                                  color={attachment.association_type === 'task_direct' ? 'green' : 'blue'} 
                                  style={{ fontSize: '10px' }}
                                >
                                  {attachment.association_type === 'task_direct' ? '任务附件' : '节点绑定'}
                                </Tag>
                              </div>
                            }
                            description={
                              <div style={{ fontSize: '12px', color: '#666' }}>
          
                                <div>大小: {(attachment.file_size / 1024).toFixed(1)} KB </div>
                                <div>类型: {attachment.content_type}</div>
                                {/* <div>创建时间: {new Date(attachment.created_at).toLocaleString()}</div> */}
                              </div>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  </div>
                </div>
              )}
            </Card>

            {/* Simulator任务的对话界面 */}
            {currentTask.task_type === 'simulator' && currentTask.context_data?.session_id && (
              <div style={{ marginBottom: '16px' }}>
                <SimulatorConversationPanel
                  taskId={currentTask.task_instance_id}
                  sessionId={currentTask.context_data.session_id}
                  onConversationComplete={(result) => {
                    message.success('Simulator对话已完成');
                    setDetailModalVisible(false);
                    loadTasks(); // 重新加载任务列表
                  }}
                  onConversationInterrupt={() => {
                    message.info('Simulator对话已中断');
                    setDetailModalVisible(false);
                    loadTasks(); // 重新加载任务列表
                  }}
                />
              </div>
            )}

            {/* 非Simulator任务或没有会话ID的任务显示常规信息 */}
            {!(currentTask.task_type === 'simulator' && currentTask.context_data?.session_id) && (
              <>
            {/* 上下文信息 */}
            {(currentTask.context_data || currentTask.input_data) && (
              <Card size="small" title="执行上下文" style={{ marginBottom: '16px' }}>
                {/* 简化的调试信息 */}
                {/* <div style={{ background: '#f6f6f6', padding: '8px', marginBottom: '12px', fontSize: '12px', borderRadius: '4px' }}>
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <div><Text strong>任务标识:</Text> {currentTask.task_instance_id}</div>
                    <div><Text strong>节点标识:</Text> {currentTask.node_instance_id}</div>
                    <div><Text strong>工作流标识:</Text> {currentTask.workflow_instance_id}</div>
                    <div><Text strong>更新时间:</Text> {new Date().toLocaleString()}</div>
                    {currentTask.context_data && (
                      <div>
                        <Text strong>上下文状态:</Text>{' '}
                        <Tag color="green">已加载 ({typeof currentTask.context_data === 'object' ? Object.keys(currentTask.context_data).length : 0} 个字段)</Tag>
                      </div>
                    )}
                  </Space>
                </div> */}
                <Collapse size="small">
                  {/* 新的context_data字段 */}
                  {currentTask.context_data && (
                    <>
                      {currentTask.context_data.workflow && (
                        <Panel header="工作流信息" key="workflow_info">
                          <div>
                            <p><Text strong>工作流名称:</Text> {currentTask.context_data.workflow.name}</p>
                            <p><Text strong>实例名称:</Text> {currentTask.context_data.workflow.workflow_instance_name}</p>
                            <p><Text strong>状态:</Text> {currentTask.context_data.workflow.status}</p>
                            <p><Text strong>创建时间:</Text> {currentTask.context_data.workflow.created_at}</p>
                            {currentTask.context_data.workflow.input_data && Object.keys(currentTask.context_data.workflow.input_data).length > 0 && (
                              <div>
                                <Text strong>工作流输入数据:</Text>
                                <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', marginTop: '4px', maxHeight: '150px', overflow: 'auto' }}>
                                  {JSON.stringify(currentTask.context_data.workflow.input_data, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </Panel>
                      )}
                      
                    
                      
                      {/* {currentTask.context_data.current_node && (
                        <Panel 
                          header={
                            <div>
                              <Text strong>当前节点信息</Text>
                              <Tag color="processing" style={{ marginLeft: '8px' }}>正在执行</Tag>
                            </div>
                          } 
                          key="current_node_info"
                        >
                          <Card size="small" style={{ background: '#fafafa' }}>
                            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                                <div>
                                  <Text type="secondary">节点名称</Text>
                                  <div><Text strong style={{ color: '#1890ff' }}>{currentTask.context_data.current_node.name}</Text></div>
                                </div>
                                <div>
                                  <Text type="secondary">节点类型</Text>
                                  <div>
                                    <Tag color={currentTask.context_data.current_node.type === 'human' ? 'blue' : 'purple'}>
                                      {currentTask.context_data.current_node.type === 'human' ? '人工任务' : currentTask.context_data.current_node.type}
                                    </Tag>
                                  </div>
                                </div>
                                <div>
                                  <Text type="secondary">执行状态</Text>
                                  <div>
                                    <Tag color="processing">{currentTask.context_data.current_node.status}</Tag>
                                  </div>
                                </div>
                              </div>
                              
                              {currentTask.context_data.current_node.description && (
                                <div>
                                  <Text type="secondary">任务描述</Text>
                                  <Alert
                                    message={currentTask.context_data.current_node.description}
                                    type="info"
                                    showIcon={false}
                                    style={{ marginTop: '4px' }}
                                  />
                                </div>
                              )}
                              
                              {currentTask.context_data.current_node.input_data && Object.keys(currentTask.context_data.current_node.input_data).length > 0 && (
                                <div>
                                  <Text type="secondary">节点输入数据</Text>
                                  <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', marginTop: '4px', maxHeight: '150px', overflow: 'auto' }}>
                                    {JSON.stringify(currentTask.context_data.current_node.input_data, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </Space>
                          </Card>
                        </Panel>
                      )} */}
                    </>
                  )}
                  
                  {/* 🆕 直接上游上下文面板（使用immediate_upstream_results显示正确的附件数据）*/}
                  {currentTask.upstream_context && currentTask.upstream_context.immediate_upstream_results && Object.keys(currentTask.upstream_context.immediate_upstream_results).length > 0 && (
                    <Panel
                      header={
                        <div>
                          <Text strong>🔗 直接上游上下文</Text>
                          <Tag color="green" style={{ marginLeft: '8px' }}>
                            {Object.keys(currentTask.upstream_context.immediate_upstream_results).length} 个节点
                          </Tag>
                        </div>
                      }
                      key="immediate_upstream_results"
                    >
                      <Alert
                        message="🔗 直接上游执行结果"
                        description="此处显示直接影响当前任务的上游节点执行结果和提交的附件。"
                        type="success"
                        showIcon
                        style={{ marginBottom: '16px' }}
                      />
                      {Object.entries(currentTask.upstream_context.immediate_upstream_results).map(([nodeKey, nodeData]: [string, any], index: number) => (
                        <Card
                          key={nodeKey}
                          size="small"
                          title={
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <Text strong style={{ color: '#52c41a' }}>
                                {nodeData.node_name || nodeKey}
                              </Text>
                              <Tag color="green" style={{ fontSize: '10px' }}>
                                #{index + 1}
                              </Tag>
                            </div>
                          }
                          style={{ marginBottom: '12px' }}
                        >
                          <div>
                            {/* 输出数据显示 */}
                            {nodeData.output_data ? (
                              <div>
                                <Text strong style={{ color: '#1890ff' }}>输出数据:</Text>
                                <div style={{ marginTop: '8px', marginBottom: '12px' }}>
                                  {(() => {
                                    const outputData = nodeData.output_data;

                                    if (outputData.answer !== undefined) {
                                      return (
                                        <div>
                                          <Text><Text strong>answer:</Text> {outputData.answer}</Text>
                                        </div>
                                      );
                                    } else {
                                      return (
                                        <Alert
                                          message="📄 执行结果"
                                          description={
                                            <div style={{ maxHeight: '120px', overflow: 'auto' }}>
                                              <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', fontSize: '11px', margin: 0, whiteSpace: 'pre-wrap' }}>
                                                {JSON.stringify(outputData, null, 2)}
                                              </pre>
                                            </div>
                                          }
                                          type="info"
                                          showIcon
                                        />
                                      );
                                    }
                                  })()}
                                </div>
                              </div>
                            ) : (
                              <Alert
                                message="⚠️ 该节点无输出数据"
                                type="warning"
                                showIcon={false}
                                style={{ fontSize: '12px', marginBottom: '12px' }}
                              />
                            )}

                            {/* 🆕 显示节点相关附件 */}
                            {nodeData.attachments && nodeData.attachments.length > 0 && (
                              <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #f0f0f0' }}>
                                <div style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  <Text strong style={{ color: '#1890ff' }}>相关附件</Text>
                                  <Tag color="blue" style={{ fontSize: '10px' }}>
                                    {nodeData.attachments.length} 个文件
                                  </Tag>
                                </div>

                                <List
                                  size="small"
                                  dataSource={nodeData.attachments}
                                  renderItem={(attachment: any) => {
                                    // 🔍 调试：打印每个附件的数据
                                    console.log('🔍 [immediate上游调试] 节点附件数据:', nodeKey, attachment);
                                    return (
                                    <List.Item
                                      style={{ padding: '4px 0', borderBottom: '1px solid #f5f5f5' }}
                                      actions={[
                                        <Button
                                          key="download"
                                          type="link"
                                          size="small"
                                          icon={<DownloadOutlined />}
                                          style={{ fontSize: '15px' }}
                                          onClick={() => handleFileDownload(attachment.file_id)}
                                        >
                                          下载
                                        </Button>
                                      ]}
                                    >
                                      <List.Item.Meta
                                        avatar={<FileOutlined style={{ color: '#1890ff', fontSize: '12px' }} />}
                                        title={
                                          <div style={{ fontSize: '12px' }}>
                                            <Text strong>{attachment.filename}</Text>
                                            <Tag
                                              color={
                                                attachment.association_type === 'node_binding' ? 'blue' :
                                                attachment.association_type === 'task_submission' ? 'green' : 'default'
                                              }
                                              style={{ fontSize: '9px', marginLeft: '4px' }}
                                            >
                                              {attachment.association_type === 'node_binding' ? '节点绑定' :
                                               attachment.association_type === 'task_submission' ? '任务提交' : '其他'}
                                            </Tag>
                                          </div>
                                        }
                                        description={
                                          <div style={{ fontSize: '10px', color: '#666' }}>
                                            <div>大小: {(attachment.file_size / 1024).toFixed(1)} KB</div>
                                            <div>类型: {attachment.content_type}</div>
                                            {attachment.task_title && (
                                              <div>任务: {attachment.task_title}</div>
                                            )}
                                            <div>时间: {new Date(attachment.created_at).toLocaleString()}</div>
                                          </div>
                                        }
                                      />
                                    </List.Item>
                                    );
                                  }}
                                />
                              </div>
                            )}
                          </div>
                        </Card>
                      ))}
                    </Panel>
                  )}

                  {/* 🆕 全局上游上下文面板 */}
                  {currentTask.upstream_context && currentTask.upstream_context.all_upstream_results && Object.keys(currentTask.upstream_context.all_upstream_results).length > 0 && (
                    <Panel
                      header={
                        <div>
                          <Text strong>🌐 全局上游上下文</Text>
                          <Tag color="purple" style={{ marginLeft: '8px' }}>
                            {Object.keys(currentTask.upstream_context.all_upstream_results).length} 个节点
                          </Tag>
                        </div>
                      }
                      key="all_upstream_results"
                    >
                      <Alert
                        message="🌐 全局执行上下文"
                        description="此处显示工作流从开始到当前任务的所有上游节点执行结果，可帮助您了解完整的执行历史。"
                        type="info"
                        showIcon
                        style={{ marginBottom: '16px' }}
                      />
                      {Object.entries(currentTask.upstream_context.all_upstream_results)
                        .sort(([,a], [,b]) => ((a as any).execution_order || 0) - ((b as any).execution_order || 0))
                        .map(([nodeKey, nodeData]: [string, any], index: number) => (
                        <Card 
                          key={nodeKey} 
                          size="small" 
                          style={{ marginBottom: '12px', border: '1px solid #f0f0f0' }}
                          title={
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Text strong style={{ color: '#722ed1' }}>
                                  {nodeData.node_name || nodeKey}
                                </Text>
                                <Tag color="purple" style={{ fontSize: '10px' }}>#{nodeData.execution_order || index + 1}</Tag>
                              </div>
                              {nodeData.completed_at && (
                                <Text type="secondary" style={{ fontSize: '12px' }}>
                                  {new Date(nodeData.completed_at).toLocaleString()}
                                </Text>
                              )}
                            </div>
                          }
                        >
                          {/* 显示输出结果 */}
                          {nodeData.output_data && Object.keys(nodeData.output_data).length > 0 ? (
                            <div>
                              <div style={{ marginTop: '8px' }}>
                                {(() => {
                                  const outputData = nodeData.output_data;
                                  
                                  // 检查是否有嵌套的output_data结构
                                  if (outputData.output_data) {
                                    return (
                                      <div>
                                        {/* 显示具体的输出数据 */}
                                        {outputData.output_data && (
                                          <div style={{ marginTop: '8px' }}>
                                            <Text strong style={{ color: '#52c41a' }}>输出数据:</Text>
                                            <div style={{ marginTop: '4px', padding: '8px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '4px' }}>
                                              {typeof outputData.output_data === 'object' ? (
                                                Object.entries(outputData.output_data).map(([key, value]: [string, any]) => (
                                                  <div key={key} style={{ marginBottom: '4px' }}>
                                                    <Text strong>{key}: </Text>
                                                    <Text>{String(value)}</Text>
                                                  </div>
                                                ))
                                              ) : (
                                                <Text>{String(outputData.output_data)}</Text>
                                              )}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    );
                                  } else {
                                    // 简单输出数据
                                    return (
                                      <Alert
                                        message="📄 执行结果"
                                        description={
                                          <div style={{ maxHeight: '120px', overflow: 'auto' }}>
                                            <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', fontSize: '11px', margin: 0, whiteSpace: 'pre-wrap' }}>
                                              {JSON.stringify(outputData, null, 2)}
                                            </pre>
                                          </div>
                                        }
                                        type="info"
                                        showIcon
                                      />
                                    );
                                  }
                                })()}
                              </div>
                            </div>
                          ) : (
                            <Alert
                              message="⚠️ 该节点无输出数据"
                              type="warning"
                              showIcon={false}
                              style={{ fontSize: '12px' }}
                            />
                          )}
                          
                          {/* 🆕 显示节点相关附件 */}
                          {nodeData.attachments && nodeData.attachments.length > 0 && (
                            <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #f0f0f0' }}>
                              <div style={{ marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Text strong style={{ color: '#1890ff' }}>相关附件</Text>
                                <Tag color="blue" style={{ fontSize: '10px' }}>
                                  {nodeData.attachments.length} 个文件
                                </Tag>
                              </div>

                              <List
                                size="small"
                                dataSource={nodeData.attachments}
                                renderItem={(attachment: any) => {
                                  // 🔍 调试：打印每个附件的数据
                                  console.log('🔍 [前端调试] 节点附件数据:', nodeKey, attachment);
                                  return (
                                  <List.Item
                                    style={{ padding: '4px 0', borderBottom: '1px solid #f5f5f5' }}
                                    actions={[
                                      <Button 
                                        key="download"
                                        type="link" 
                                        size="small"
                                        icon={<DownloadOutlined />}
                                        style={{ fontSize: '10px' }}
                                        onClick={() => handleFileDownload(attachment.file_id)}
                                      >
                                        下载
                                      </Button>
                                    ]}
                                  >
                                    <List.Item.Meta
                                      avatar={<FileOutlined style={{ color: '#1890ff', fontSize: '12px' }} />}
                                      title={
                                        <div style={{ fontSize: '12px' }}>
                                          <Text strong>{attachment.filename}</Text>
                                          <Tag 
                                            color={
                                              attachment.association_type === 'node_binding' ? 'blue' : 
                                              attachment.association_type === 'task_submission' ? 'green' : 'default'
                                            } 
                                            style={{ fontSize: '9px', marginLeft: '4px' }}
                                          >
                                            {attachment.association_type === 'node_binding' ? '节点绑定' : 
                                             attachment.association_type === 'task_submission' ? '任务提交' : '其他'}
                                          </Tag>
                                        </div>
                                      }
                                      description={
                                        <div style={{ fontSize: '10px', color: '#666' }}>
                                          <div>大小: {(attachment.file_size / 1024).toFixed(1)} KB</div>
                                          <div>类型: {attachment.content_type}</div>
                                          {attachment.task_title && (
                                            <div>任务: {attachment.task_title}</div>
                                          )}
                                          <div>时间: {new Date(attachment.created_at).toLocaleString()}</div>
                                        </div>
                                      }
                                    />
                                  </List.Item>
                                  );
                                }}
                              />
                            </div>
                          )}
                        </Card>
                      ))}
                    </Panel>
                  )}

                  {/* 🆕 上下文附件面板 */}
                  {currentTask.context_data && currentTask.context_data.context_attachments && currentTask.context_data.context_attachments.length > 0 && (
                    <Panel 
                      header={
                        <div>
                          <Text strong>📎 上下文附件</Text>
                          <Tag color="cyan" style={{ marginLeft: '8px' }}>
                            {currentTask.context_data.context_attachments.length} 个文件
                          </Tag>
                        </div>
                      } 
                      key="context_attachments"
                    >
                      <Alert
                        message="📎 工作流相关附件"
                        description="此处显示与当前任务和工作流相关的所有附件文件，您可以下载查看。"
                        type="info"
                        showIcon
                        style={{ marginBottom: '16px' }}
                      />
                      <List
                        size="small"
                        dataSource={currentTask.context_data.context_attachments}
                        renderItem={(attachment: any) => (
                          <List.Item
                            actions={[
                              <Button 
                                key="download"
                                type="link" 
                                size="small"
                                icon={<DownloadOutlined />}
                                onClick={() => handleFileDownload(attachment.file_id)}
                              >
                                下载
                              </Button>
                            ]}
                          >
                            <List.Item.Meta
                              avatar={<FileOutlined style={{ color: '#1890ff' }} />}
                              title={
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  <Text strong>{attachment.filename}</Text>
                                  <Tag color={attachment.association_type === 'node' ? 'blue' : 'green'} style={{ fontSize: '10px' }}>
                                    {attachment.association_type === 'node' ? '节点附件' : '工作流附件'}
                                  </Tag>
                                </div>
                              }
                              description={
                                <div style={{ fontSize: '12px', color: '#666' }}>
                                  <div>大小: {(attachment.file_size / 1024).toFixed(1)} KB</div>
                                  <div>类型: {attachment.content_type}</div>
                                  <div>创建时间: {new Date(attachment.created_at).toLocaleString()}</div>
                                </div>
                              }
                            />
                          </List.Item>
                        )}
                      />
                    </Panel>
                  )}
                  
                 
                  
                  {/* 兼容旧的input_data格式 */}
                  {currentTask.input_data && (
                    <>
                      {currentTask.input_data.immediate_upstream && Object.keys(currentTask.input_data.immediate_upstream).length > 0 && (
                        <Panel header="直接上游节点结果 (兼容格式)" key="immediate_upstream">
                          <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                            {JSON.stringify(currentTask.input_data.immediate_upstream, null, 2)}
                          </pre>
                        </Panel>
                      )}
                      
                      {currentTask.input_data.workflow_global && Object.keys(currentTask.input_data.workflow_global).length > 0 && (
                        <Panel header="全局工作流上下文 (兼容格式)" key="workflow_global">
                          <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                            {JSON.stringify(currentTask.input_data.workflow_global, null, 2)}
                          </pre>
                        </Panel>
                      )}
                    </>
                  )}
                </Collapse>
                
                {/* 无上下文数据提示 */}
                {(!currentTask.context_data || (
                   Object.keys(currentTask.context_data).length === 0 || 
                   (!currentTask.context_data.upstream_outputs && !currentTask.context_data.immediate_upstream_results)
                 )) &&
                 (!currentTask.input_data || (
                   (!currentTask.input_data.immediate_upstream || Object.keys(currentTask.input_data.immediate_upstream).length === 0) &&
                   (!currentTask.input_data.workflow_global || Object.keys(currentTask.input_data.workflow_global).length === 0)
                 )) && (
                  <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                    <div style={{ fontSize: '48px', marginBottom: '16px' }}>📋</div>
                    <Alert
                      message="无上下文数据"
                      description={
                        <div>
                          <p>这个任务没有可用的上下文数据，可能的原因：</p>
                          <ul style={{ textAlign: 'left', marginTop: '8px' }}>
                            <li>这是工作流的起始任务，无需依赖上游数据</li>
                            <li>上游节点尚未完成或未产生输出数据</li>
                            <li>数据传递过程中出现问题</li>
                          </ul>
                          <p style={{ marginTop: '12px', color: '#666' }}>
                            您可以根据任务描述独立完成此任务。
                          </p>
                        </div>
                      }
                      type="info"
                      showIcon
                      style={{ textAlign: 'left' }}
                    />
                  </div>
                )}
              </Card>
            )}
              </>
            )}

            {/* 任务结果 */}
            {(currentTask.output_data || currentTask.result_summary) && (
              <Card 
                size="small" 
                title={
                  <div>
                    <Text strong>任务结果</Text>
                    <Tag color="success" style={{ marginLeft: '8px' }}>已完成</Tag>
                  </div>
                }
                style={{ marginBottom: '16px' }}
              >
                {currentTask.result_summary && (
                  <Alert
                    message="任务完成总结"
                    description={currentTask.result_summary}
                    type="success"
                    showIcon
                    style={{ marginBottom: '16px' }}
                  />
                )}
                
                {currentTask.output_data && (
                  <div>
                    <Text strong style={{ color: '#52c41a' }}>详细输出数据:</Text>
                    <div style={{ marginTop: '8px' }}>
                      {(() => {
                        try {
                          const outputData = typeof currentTask.output_data === 'string' 
                            ? JSON.parse(currentTask.output_data) 
                            : currentTask.output_data;
                          
                          // 如果有result字段，重点显示
                          if (outputData.result) {
                            return (
                              <div>
                                <Card size="small" style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
                                  <Text strong style={{ color: '#52c41a' }}>主要结果：</Text>
                                  <Paragraph style={{ marginTop: '8px', marginBottom: '0' }}>
                                    {outputData.result}
                                  </Paragraph>
                                </Card>
                                {Object.keys(outputData).length > 1 && (
                                  <details style={{ marginTop: '12px' }}>
                                    <summary style={{ cursor: 'pointer', color: '#1890ff', fontWeight: 'bold' }}>
                                      查看完整输出数据 ({Object.keys(outputData).length} 个字段)
                                    </summary>
                                    <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', marginTop: '8px', maxHeight: '200px', overflow: 'auto' }}>
                                      {JSON.stringify(outputData, null, 2)}
                                    </pre>
                                  </details>
                                )}
                              </div>
                            );
                          } else {
                            return (
                              <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                                {JSON.stringify(outputData, null, 2)}
                              </pre>
                            );
                          }
                        } catch (e) {
                          return (
                            <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                              {JSON.stringify(currentTask.output_data, null, 2)}
                            </pre>
                          );
                        }
                      })()}
                    </div>
                  </div>
                )}
              </Card>
            )}
          </div>
        )}
      </Modal>

      {/* 请求帮助模态框 */}
      <Modal
        title="请求帮助"
        open={helpModalVisible}
        onOk={handleHelpSubmit}
        onCancel={() => setHelpModalVisible(false)}
        width={500}
      >
        <Form form={helpForm} layout="vertical">
          <Form.Item
            name="help_message"
            label="帮助信息"
            rules={[{ required: true, message: '请描述您需要的帮助' }]}
          >
            <TextArea 
              rows={4} 
              placeholder="请详细描述您在执行任务过程中遇到的问题或需要的帮助...

例如：
- 不确定如何理解上游数据
- 遇到技术问题
- 需要额外的信息或资源" 
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="提交任务结果"
        open={submitModalVisible}
        onOk={handleSubmitConfirm}
        onCancel={() => {
          setSubmitModalVisible(false);
          setSubWorkflowsForSubmit([]);
          // 🆕 重置下游节点相关状态
          setConditionalDownstreamNodes([]);
          setSelectedDownstreamNodes([]);
        }}
        width={1200}  // 增大宽度以容纳AI对话面板
        footer={[
          <Button key="save-draft" onClick={handleSaveDraft}>
            保存草稿
          </Button>,
          <Button key="cancel" onClick={() => {
            setSubmitModalVisible(false);
            setSubWorkflowsForSubmit([]);
            // 🆕 重置下游节点相关状态
            setConditionalDownstreamNodes([]);
            setSelectedDownstreamNodes([]);
          }}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={handleSubmitConfirm}>
            提交结果
          </Button>,
        ]}
      >
        <div style={{ display: 'flex', gap: '16px' }}>
          {/* 左侧：任务结果表单 */}
          <div style={{ flex: 1 }}>
            <Form form={submitForm} layout="vertical">
              <Form.Item
                name="result"
                label="任务结果"
                rules={[{ required: true, message: '请输入任务结果' }]}
                extra={
                  <div>
                    {(currentTask?.input_data?.immediate_upstream ||
                     currentTask?.input_data?.workflow_global ||
                     currentTask?.context_data?.immediate_upstream_results ||
                     currentTask?.context_data?.upstream_outputs) && (
                      <div style={{ marginBottom: '4px' }}>
                        💡 您可以在"任务详情"中查看上游处理器执行结果和上下文数据
                      </div>
                    )}
                    <div style={{ color: '#1890ff', fontSize: '12px' }}>
                      🤖 右侧AI助手可以帮助您理解任务要求和分析上游数据
                    </div>
                  </div>
                }
              >
                <TextArea rows={8} placeholder="请详细描述任务完成情况...

可以参考上游上下文数据来完成任务。
您也可以从右侧子工作流结果中选择内容填充，或与AI助手对话获取帮助。" />
              </Form.Item>
              <Form.Item
                name="attachments"
                label="附件上传"
                tooltip="您可以上传与任务完成相关的文件，如截图、文档等"
              >
                <NodeAttachmentManager
                  workflowId={currentTask?.workflow_instance_id}
                  nodeId={currentTask?.node_instance_id}
                  onChange={(fileIds) => {
                    // 将文件ID存储到表单中
                    submitForm.setFieldsValue({ attachment_file_ids: fileIds });
                  }}
                />
              </Form.Item>
              <Form.Item
                name="attachment_file_ids"
                style={{ display: 'none' }}
              >
                <Input />
              </Form.Item>
              <Form.Item
                name="notes"
                label="备注"
              >
                <TextArea rows={2} placeholder="其他备注信息（可选）

可以记录使用了哪些上游数据、遇到的问题等" />
              </Form.Item>

              {/* 🆕 下游条件节点选择 */}
              {(() => {
                console.log('🎨 [RENDER] conditionalDownstreamNodes检查:', {
                  length: conditionalDownstreamNodes.length,
                  nodes: conditionalDownstreamNodes,
                  shouldShow: conditionalDownstreamNodes.length > 0,
                  loadingDownstreamNodes
                });
                return null;
              })()}
              {conditionalDownstreamNodes.length > 0 && (
                <Form.Item
                  label={
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>下游节点触发</span>
                      {loadingDownstreamNodes && <Spin size="small" />}
                    </div>
                  }
                  tooltip="选择您希望在任务完成后触发执行的下游条件节点"
                >
                  <div style={{ border: '1px solid #d9d9d9', borderRadius: '6px', padding: '12px', maxHeight: '200px', overflowY: 'auto' }}>
                    {conditionalDownstreamNodes.map((node) => (
                      <div key={node.node_instance_id} style={{ marginBottom: '8px' }}>
                        <Checkbox
                          checked={selectedDownstreamNodes.includes(node.node_instance_id)}
                          disabled={!node.can_trigger}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedDownstreamNodes([...selectedDownstreamNodes, node.node_instance_id]);
                            } else {
                              setSelectedDownstreamNodes(selectedDownstreamNodes.filter(id => id !== node.node_instance_id));
                            }
                          }}
                        >
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <Text strong style={{ color: node.can_trigger ? '#1890ff' : '#999' }}>
                                {node.name}
                              </Text>
                              <Tag
                                color={node.status === 'pending' ? 'default' : node.status === 'completed' ? 'green' : 'blue'}
                              >
                                {node.status === 'pending' ? '等待中' : node.status === 'completed' ? '已完成' : '执行中'}
                                {node.can_retrigger && ' (可重新触发)'}
                              </Tag>
                              <Tag
                                color={node.is_conditional ? 'orange' : 'blue'}
                                style={{ fontSize: '10px' }}
                              >
                                {node.is_conditional ? '条件边' : '固定边'}
                              </Tag>
                            </div>
                            <Text type="secondary" style={{ fontSize: '12px' }}>
                              {node.condition_description}
                            </Text>
                            {node.description && (
                              <Text type="secondary" style={{ fontSize: '11px' }}>
                                {node.description}
                              </Text>
                            )}
                          </div>
                        </Checkbox>
                      </div>
                    ))}

                    {conditionalDownstreamNodes.length === 0 && !loadingDownstreamNodes && (
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        暂无可触发的下游条件节点
                      </Text>
                    )}
                  </div>

                  {selectedDownstreamNodes.length > 0 && (
                    <div style={{ marginTop: '8px', padding: '8px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '4px' }}>
                      <Text style={{ fontSize: '12px', color: '#52c41a' }}>
                        已选择 {selectedDownstreamNodes.length} 个节点将在任务完成后触发执行
                      </Text>
                    </div>
                  )}
                </Form.Item>
              )}
            </Form>
          </div>

          {/* 右侧：子工作流和AI助手 */}
          <div style={{ width: '400px', borderLeft: '1px solid #f0f0f0', paddingLeft: '16px' }}>
            <Tabs
              defaultActiveKey="ai-assistant"
              size="small"
              items={[
                {
                  key: 'ai-assistant',
                  label: (
                    <span>
                      <RobotOutlined />
                      AI助手
                    </span>
                  ),
                  children: (
                    <div style={{ height: '500px' }}>
                      <TaskConversationPanel
                        taskId={currentTask?.task_instance_id || ''}
                        taskInfo={currentTask ? {
                          title: currentTask.task_title,
                          description: currentTask.task_description,
                          status: currentTask.status
                        } : undefined}
                        onSuggestionSelect={(suggestion) => {
                          // 处理AI建议点击
                          if (suggestion.includes('提交') || suggestion.includes('完成')) {
                            // 如果建议是提交任务，可以在这里做处理
                            console.log('AI建议提交任务');
                          } else if (suggestion.includes('检查') || suggestion.includes('验证')) {
                            // 如果建议是检查数据，可以切换到任务详情
                            console.log('AI建议检查数据');
                          } else {
                            // 其他建议作为消息发送给AI
                            console.log('处理AI建议:', suggestion);
                          }
                        }}
                      />
                    </div>
                  )
                },
                {
                  key: 'sub-workflows',
                  label: `子工作流 ${subWorkflowsForSubmit.length > 0 ? `(${subWorkflowsForSubmit.length})` : ''}`,
                  children: (
                    <div style={{ height: '500px', overflow: 'hidden' }}>
                      <div style={{ marginBottom: '12px' }}>
                        <Text strong style={{ fontSize: '16px' }}>相关子工作流</Text>
                        {loadingSubWorkflows && <Spin size="small" style={{ marginLeft: '8px' }} />}
                      </div>

                      {subWorkflowsForSubmit.length > 0 ? (
                        <div style={{ height: '430px', overflowY: 'auto' }}>
                          {subWorkflowsForSubmit.map((subWorkflow, index) => {

                            return (
                              <Card
                                key={subWorkflow.subdivision_id || index}
                              size="small"
                              style={{ marginBottom: '8px' }}
                              title={
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                  <Text strong style={{ fontSize: '12px' }}>
                                    {subWorkflow.subdivision_name || `子工作流 ${index + 1}`}
                                  </Text>
                                  <Tag
                                    color={
                                      // 优先使用工作流实例的状态，否则使用细分状态
                                      (subWorkflow.workflowDetails?.status || subWorkflow.status) === 'completed' ? 'green' :
                                      (subWorkflow.workflowDetails?.status || subWorkflow.status) === 'failed' ? 'red' :
                                      (subWorkflow.workflowDetails?.status || subWorkflow.status) === 'running' ? 'blue' : 'orange'
                                    }
                                    style={{ fontSize: '10px' }}
                                  >
                                    {(() => {
                                      const actualStatus = subWorkflow.workflowDetails?.status || subWorkflow.status;

                                      return actualStatus === 'completed' ? '已完成' :
                                             actualStatus === 'failed' ? '失败' :
                                             actualStatus === 'running' ? '运行中' : '进行中';
                                    })()}
                                  </Tag>
                                </div>
                              }
                              extra={
                                <Space size="small">
                                  <Button
                                    type="link"
                                    size="small"
                                    icon={<EyeOutlined />}
                                    onClick={() => handleViewSubWorkflowDetails(subWorkflow)}
                                    style={{ padding: '0 4px', fontSize: '12px' }}
                                  >
                                    查看
                                  </Button>
                                  {(() => {
                                    const actualStatus = subWorkflow.workflowDetails?.status || subWorkflow.status;
                                    return actualStatus === 'completed' && (
                                      <Button
                                        type="primary"
                                        size="small"
                                        onClick={() => handleSelectSubWorkflowResult(subWorkflow)}
                                        style={{ padding: '0 8px', fontSize: '12px' }}
                                      >
                                        选择结果
                                      </Button>
                                    );
                                  })()}
                                </Space>
                              }
                            >
                              <div style={{ fontSize: '12px' }}>
                                <div style={{ marginBottom: '4px' }}>
                                  <Text type="secondary">创建时间: </Text>
                                  <Text>
                                    {(() => {
                                      // 优先使用工作流实例的创建时间，否则使用细分创建时间
                                      const createTime = subWorkflow.workflowDetails?.created_at ||
                                                       subWorkflow.created_at ||
                                                       subWorkflow.subdivision_created_at;

                                      if (!createTime) return '未知';

                                      try {
                                        return new Date(createTime).toLocaleString();
                                      } catch (e) {
                                        console.warn('时间解析失败:', createTime, e);
                                        return '时间格式错误';
                                      }
                                    })()}
                                  </Text>
                                </div>
                                {(() => {
                                  const completedTime = subWorkflow.workflowDetails?.completed_at || subWorkflow.completed_at;
                                  return completedTime && (
                                    <div style={{ marginBottom: '4px' }}>
                                      <Text type="secondary">完成时间: </Text>
                                      <Text>
                                        {(() => {
                                          try {
                                            return new Date(completedTime).toLocaleString();
                                          } catch (e) {
                                            console.warn('完成时间解析失败:', completedTime, e);
                                            return '时间格式错误';
                                          }
                                        })()}
                                      </Text>
                                    </div>
                                  );
                                })()}
                                {subWorkflow.subdivision_description && (
                                  <div style={{ marginTop: '8px' }}>
                                    <Text type="secondary" style={{ fontSize: '11px' }}>
                                      {subWorkflow.subdivision_description}
                                    </Text>
                                  </div>
                                )}
                              </div>
                            </Card>
                            );
                          })}
                        </div>
                      ) : (
                        <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
                          {loadingSubWorkflows ? '加载中...' : (
                            <div>
                              <div>该任务没有相关的子工作流</div>
                              <div style={{ fontSize: '12px', marginTop: '8px', color: '#666' }}>
                                💡 提示：只有已拆解的任务才会显示子工作流
                              </div>
                              <div style={{ fontSize: '11px', marginTop: '4px', color: '#999' }}>
                                如需测试此功能，请选择已完成拆解的任务
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {subWorkflowsForSubmit.length > 0 && (
                        <Alert
                          message="使用提示"
                          description='点击"选择结果"可将子工作流的执行结果填充到左侧的任务结果中，您可以进一步编辑这些内容。'
                          type="info"
                          showIcon
                          style={{ marginTop: '12px', fontSize: '11px' }}
                        />
                      )}
                    </div>
                  )
                }
              ]}
            />
          </div>
        </div>
      </Modal>

      {/* 拒绝任务模态框 */}
      {/* <Modal
        title="拒绝任务"
        open={rejectModalVisible}
        onOk={handleRejectConfirm}
        onCancel={() => setRejectModalVisible(false)}
        width={500}
        okText="确认拒绝"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        <Form form={rejectForm} layout="vertical">
          <Form.Item
            name="reject_reason"
            label="拒绝原因"
            rules={[{ required: true, message: '请说明拒绝任务的原因' }]}
          >
            <TextArea 
              rows={4} 
              placeholder="请详细说明为什么要拒绝此任务...

例如：
- 任务要求不明确，需要更多信息
- 超出个人能力范围
- 时间冲突，无法按时完成
- 其他技术或资源限制"
            />
          </Form.Item>
        </Form>
      </Modal> */}

      {/* 取消任务模态框 */}
      <Modal
        title="取消任务"
        open={cancelModalVisible}
        onOk={handleCancelConfirm}
        onCancel={() => setCancelModalVisible(false)}
        width={500}
        okText="确认取消"
        okButtonProps={{ danger: true }}
        cancelText="返回"
      >
        <Form form={cancelForm} layout="vertical">
          <Form.Item
            name="cancel_reason"
            label="取消原因（可选）"
          >
            <TextArea 
              rows={3} 
              placeholder="请说明取消任务的原因（可选）...

例如：
- 任务已不再需要
- 需求发生变化
- 其他优先级任务需要处理"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 任务拆解模态框 */}
      {currentTask && (
        <TaskSubdivisionModal
          visible={subdivisionModalVisible}
          onCancel={() => {
            setSubdivisionModalVisible(false);
            setCurrentTask(null);
          }}
          onSuccess={handleSubdivisionSuccess}
          taskId={currentTask.task_instance_id}
          taskTitle={currentTask.task_title}
          taskDescription={currentTask.task_description}
          taskContext={currentTask.context_data}
          taskInputData={currentTask.input_data}
        />
      )}

      {/* 细分结果编辑模态框 */}
      {subdivisionResultData && (
        <SubdivisionResultEditModal
          visible={subdivisionResultEditVisible}
          onCancel={() => {
            setSubdivisionResultEditVisible(false);
            setSubdivisionResultData(null);
            setCurrentTask(null);
          }}
          onSubmit={handleSubmitEditedSubdivisionResult}
          subdivisionResult={subdivisionResultData}
          originalTaskTitle={currentTask?.task_title || ''}
          loading={loading}
        />
      )}

      {/* 子工作流进度查看模态框 */}
      <Modal
        title={`子工作流进度 - ${currentTask?.task_title || '未知任务'}`}
        open={subWorkflowViewerVisible}
        onCancel={() => {
          setSubWorkflowViewerVisible(false);
          setCurrentSubWorkflowId(null);
          setCurrentTask(null);
        }}
        footer={[
          <Button key="close" onClick={() => {
            setSubWorkflowViewerVisible(false);
            setCurrentSubWorkflowId(null);
            setCurrentTask(null);
          }}>
            关闭
          </Button>
        ]}
        width="95%"
        style={{ maxWidth: '1400px', top: 20 }}
        styles={{ body: { height: '80vh', overflow: 'auto', padding: '16px' } }}
      >
        {currentSubWorkflowId && user && (
          <div style={{ height: '100%' }}>
            <Alert
              message="子工作流执行状态"
              description={`正在查看任务"${currentTask?.task_title}"的子工作流执行进度。您可以实时查看各个节点的执行状态和任务分配情况。`}
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />
            <TaskFlowViewer
              workflowId={currentSubWorkflowId}
              currentUserId={user.user_id}
              disableNodeClick={true} // 禁用子工作流进度中的节点点击
              onTaskAction={(taskId, action) => {
                console.log(`子工作流任务操作: ${taskId} - ${action}`);
                // 这里可以添加子工作流任务操作的处理逻辑
                message.info(`子工作流任务${action}操作已记录`);
              }}
            />
          </div>
        )}
      </Modal>
    </div>
  );
};

export default Todo;
