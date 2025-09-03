import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Button, Modal, Form, Input, Select, message, Space, Collapse, Typography, Divider, Alert, Spin, Row, Col, Pagination } from 'antd';
import { SaveOutlined, BranchesOutlined, EditOutlined, EyeOutlined, SearchOutlined, FilterOutlined, ClearOutlined } from '@ant-design/icons';
import { useTaskStore } from '../../stores/taskStore';
import { useAuthStore } from '../../stores/authStore';
import { taskSubdivisionApi, executionAPI } from '../../services/api';
import TaskSubdivisionModal from '../../components/TaskSubdivisionModal';
import SubdivisionResultEditModal from '../../components/SubdivisionResultEditModal';
import TaskFlowViewer from '../../components/TaskFlowViewer';

const { TextArea } = Input;
const { Panel } = Collapse;
const { Text, Paragraph } = Typography;

const Todo: React.FC = () => {
  const { user } = useAuthStore();
  const { 
    tasks, 
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

  // 检查任务是否可以拆解
  const canSubdivideTask = (task: any) => {
    const status = task.status?.toLowerCase();
    const taskType = task.task_type?.toLowerCase();
    
    console.log('🔍 拆解检查 - 任务:', task.task_title);
    console.log('   - 状态:', status);
    console.log('   - 类型:', taskType);
    
    // 待分配、已分配或进行中状态的人工任务或混合任务可以拆解
    // 增加了in_progress状态，允许在执行过程中拆解任务
    const canSubdivide = (status === 'pending' || status === 'assigned' || status === 'in_progress') && 
           (taskType === 'human' || taskType === 'mixed' || taskType === 'processor');
    
    console.log('   - 是否可拆解:', canSubdivide);
    
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

  const handleSubmit = async (task: any) => {
    console.log('🚀 [SUBMIT] handleSubmit 被调用:');
    console.log('   - 任务:', task.task_title);
    console.log('   - 任务ID:', task.task_instance_id);
    console.log('   - 当前subWorkflowsForSubmit状态:', subWorkflowsForSubmit);
    
    setCurrentTask(task);
    setSubmitModalVisible(true);
    submitForm.resetFields();
    
    console.log('🎯 [SUBMIT] 模态框状态设置完成，开始加载草稿...');
    
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
      
      console.log('🔍 正在获取子工作流的实际执行结果...');
      message.loading('正在获取子工作流执行结果...', 0);
      
      // 调用新的API端点获取完整的子工作流执行结果
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
    console.log('🔍 前端: 查看任务详情', task.task_instance_id);
    
    // 调用API获取完整的任务详情（包含context_data）
    try {
      console.log('📡 前端: 调用getTaskDetails API');
      await getTaskDetails(task.task_instance_id);
      console.log('✅ 前端: 任务详情获取成功');
      
      // 使用从store获取的最新任务数据
      const updatedTask = tasks.find(t => t.task_instance_id === task.task_instance_id);
      if (updatedTask) {
        console.log('🔄 前端: 更新当前任务数据');
        console.log('📊 前端: 最新context_data', updatedTask.context_data);
        
        // 解析context_data字符串为对象（如果是字符串）
        let parsedTask = { ...updatedTask };
        if (typeof updatedTask.context_data === 'string' && (updatedTask.context_data as string).trim()) {
          try {
            parsedTask.context_data = JSON.parse(updatedTask.context_data as string);
            console.log('✅ 前端: context_data解析成功', parsedTask.context_data);
          } catch (parseError) {
            console.warn('⚠️ 前端: context_data解析失败，保持原始格式', parseError);
          }
        }
        
        // 解析input_data字符串为对象（如果是字符串）
        if (typeof updatedTask.input_data === 'string' && (updatedTask.input_data as string).trim()) {
          try {
            parsedTask.input_data = JSON.parse(updatedTask.input_data as string);
            console.log('✅ 前端: input_data解析成功', parsedTask.input_data);
          } catch (parseError) {
            console.warn('⚠️ 前端: input_data解析失败，保持原始格式', parseError);
          }
        }
        
        setCurrentTask(parsedTask);
      } else {
        setCurrentTask(task);
      }
    } catch (error) {
      console.error('❌ 前端: 获取任务详情失败', error);
      setCurrentTask(task);
    }
    
    setDetailModalVisible(true);
  };

  const handleSubmitConfirm = async () => {
    try {
      const values = await submitForm.validateFields();
      await submitTaskResult(currentTask.task_instance_id, values.result, values.notes);
      message.success('任务提交成功');
      setSubmitModalVisible(false);
    } catch (error) {
      console.error('提交失败:', error);
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
                    (item.status.toLowerCase() === 'pending' || item.status.toLowerCase() === 'assigned') && (
                      <Button 
                        key="reject" 
                        danger
                        size="small"
                        onClick={() => handleRejectTask(item)}
                      >
                        拒绝任务
                      </Button>
                    ),
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
                    item.status.toLowerCase() === 'in_progress' && (
                      <Button 
                        key="pause" 
                        size="small"
                        onClick={() => handlePauseTask(item)}
                      >
                        暂停任务
                      </Button>
                    ),
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
            </Card>

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
                      
                      {currentTask.context_data.upstream_outputs && currentTask.context_data.upstream_outputs.length > 0 && (
                        <Panel 
                          header={
                            <div>
                              <Text strong>上游处理器执行结果</Text>
                              <Tag color="blue" style={{ marginLeft: '8px' }}>
                                {currentTask.context_data.upstream_outputs.length} 个处理器节点
                              </Tag>
                              <Tag color="green" style={{ marginLeft: '4px' }}>
                                已完成
                              </Tag>
                            </div>
                          } 
                          key="upstream_outputs"
                        >
                          {currentTask.context_data.upstream_outputs.map((upstreamNode: any, index: number) => (
                            <Card 
                              key={index} 
                              size="small" 
                              style={{ marginBottom: '12px', border: '1px solid #e6f7ff' }}
                              title={
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Text strong style={{ color: '#1890ff' }}>
                                      🔧 {upstreamNode.node_name || `处理器节点 ${index + 1}`}
                                    </Text>
                                    {upstreamNode.processor_type && (
                                      <Tag color={upstreamNode.processor_type === 'human' ? 'blue' : upstreamNode.processor_type === 'agent' ? 'purple' : 'orange'}>
                                        {upstreamNode.processor_type === 'human' ? '人工处理器' : 
                                         upstreamNode.processor_type === 'agent' ? 'AI代理' : 
                                         upstreamNode.processor_type || '处理器'}
                                      </Tag>
                                    )}
                                  </div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                    <Tag color="green">✅ 执行完成</Tag>
                                  </div>
                                </div>
                              }
                              extra={
                                upstreamNode.completed_at && (
                                  <Text type="secondary" style={{ fontSize: '12px' }}>
                                    完成时间: {new Date(upstreamNode.completed_at).toLocaleString()}
                                  </Text>
                                )
                              }
                            >
                              {upstreamNode.node_description && (
                                <Alert
                                  message="处理器任务说明"
                                  description={upstreamNode.node_description}
                                  type="info"
                                  showIcon
                                  icon={<span>📋</span>}
                                  style={{ marginBottom: '12px', fontSize: '12px' }}
                                />
                              )}
                              
                              {/* 显示处理器执行信息 */}
                              {(upstreamNode.processor_name || upstreamNode.assigned_user || upstreamNode.assigned_agent) && (
                                <div style={{ marginBottom: '12px', padding: '8px', background: '#f9f9f9', borderRadius: '4px', fontSize: '12px' }}>
                                  <Text strong style={{ color: '#666' }}>处理器执行信息：</Text>
                                  <div style={{ marginTop: '4px' }}>
                                    {upstreamNode.processor_name && (
                                      <div>📝 处理器名称: {upstreamNode.processor_name}</div>
                                    )}
                                    {upstreamNode.assigned_user && (
                                      <div>👤 执行人员: {upstreamNode.assigned_user}</div>
                                    )}
                                    {upstreamNode.assigned_agent && (
                                      <div>🤖 执行代理: {upstreamNode.assigned_agent}</div>
                                    )}
                                    {upstreamNode.execution_duration && (
                                      <div>⏱️ 执行时长: {upstreamNode.execution_duration}</div>
                                    )}
                                  </div>
                                </div>
                              )}
                              
                              {upstreamNode.output_data && Object.keys(upstreamNode.output_data).length > 0 ? (
                                <div>
                                  {/* <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                    <Text strong style={{ color: '#52c41a' }}>🎯 处理器执行结果:</Text>
                                    <Tag color="cyan">可用于下游任务</Tag>
                                  </div> */}
                                  <div style={{ marginTop: '8px' }}>
                                    {(() => {
                                      try {
                                        const outputData = typeof upstreamNode.output_data === 'string' 
                                          ? JSON.parse(upstreamNode.output_data) 
                                          : upstreamNode.output_data;
                                        
                                        // 如果输出数据有result字段，特别显示
                                        if (outputData.result) {
                                          return (
                                            <div>
                                              <Alert
                                                message="✅ 处理器执行结果"
                                                description={
                                                  <div>
                                                    <div style={{ marginBottom: '8px', fontWeight: 'bold', color: '#52c41a' }}>
                                                      {outputData.result}
                                                    </div>
                                                    {outputData.summary && (
                                                      <div style={{ fontSize: '12px', color: '#666', fontStyle: 'italic' }}>
                                                        摘要: {outputData.summary}
                                                      </div>
                                                    )}
                                                  </div>
                                                }
                                                type="success"
                                                showIcon
                                                style={{ marginBottom: '8px' }}
                                              />
                                              {Object.keys(outputData).length > 1 && (
                                                <details>
                                                  <summary style={{ cursor: 'pointer', color: '#1890ff', fontSize: '12px' }}>
                                                    🔍 查看详细输出数据 ({Object.keys(outputData).filter(key => !['result', 'summary'].includes(key)).length + 2} 个字段)
                                                  </summary>
                                                  <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', marginTop: '8px', maxHeight: '150px', overflow: 'auto' }}>
                                                    {JSON.stringify(outputData, null, 2)}
                                                  </pre>
                                                </details>
                                              )}
                                            </div>
                                          );
                                        } else {
                                          return (
                                            <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', maxHeight: '150px', overflow: 'auto' }}>
                                              {JSON.stringify(outputData, null, 2)}
                                            </pre>
                                          );
                                        }
                                      } catch (e) {
                                        return (
                                          <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', maxHeight: '150px', overflow: 'auto' }}>
                                            {JSON.stringify(upstreamNode.output_data, null, 2)}
                                          </pre>
                                        );
                                      }
                                    })()}
                                  </div>
                                </div>
                              ) : (
                                <Alert
                                  message="⚠️ 该处理器节点无输出数据"
                                  description="该处理器执行完成但未产生输出数据，这可能是正常的（如删除、清理类任务）"
                                  type="warning"
                                  showIcon={false}
                                  style={{ fontSize: '12px' }}
                                />
                              )}
                            </Card>
                          ))}
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
                  
                  {/* 兼容旧的格式：支持context_data中的immediate_upstream_results */}
                  {currentTask.context_data && currentTask.context_data.immediate_upstream_results && Object.keys(currentTask.context_data.immediate_upstream_results).length > 0 && (
                    <Panel 
                      header={
                        <div>
                          <Text strong>上游处理器执行结果</Text>
                          <Tag color="blue" style={{ marginLeft: '8px' }}>
                            {Object.keys(currentTask.context_data.immediate_upstream_results).length} 个处理器节点
                          </Tag>
                        </div>
                      } 
                      key="immediate_upstream_results"
                    >
                      {Object.entries(currentTask.context_data.immediate_upstream_results).map(([nodeName, nodeData]: [string, any], index: number) => (
                        <Card 
                          key={index} 
                          size="small" 
                          style={{ marginBottom: '12px', border: '1px solid #e6f7ff' }}
                          title={
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <Text strong style={{ color: '#1890ff' }}>
                                  🔧 {nodeData.node_name || nodeName}
                                </Text>
                                <Tag color="green">已完成</Tag>
                              </div>
                            </div>
                          }
                        >
                          {/* 显示处理器执行信息
                          <div style={{ marginBottom: '12px', padding: '8px', background: '#f9f9f9', borderRadius: '4px', fontSize: '12px' }}>
                            <Text strong style={{ color: '#666' }}>节点执行信息：</Text>
                            <div style={{ marginTop: '4px' }}>
                              <div>📝 节点名称: {nodeData.node_name || nodeName}</div>
                              <div>📊 执行状态: {nodeData.status || '已完成'}</div>
                              {nodeData.node_instance_id && (
                                <div>🆔 节点实例: {nodeData.node_instance_id}</div>
                              )}
                            </div>
                          </div> */}
                          
                          {/* 显示输出结果 */}
                          {nodeData.output_data && Object.keys(nodeData.output_data).length > 0 ? (
                            <div>
                              {/* <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                <Text strong style={{ color: '#52c41a' }}>🎯 处理器执行结果:</Text>
                                <Tag color="cyan">可用于下游任务</Tag>
                              </div> */}
                              <div style={{ marginTop: '8px' }}>
                                {(() => {
                                  const outputData = nodeData.output_data;
                                  
                                  // 检查是否有嵌套的output_data结构
                                  if (outputData.output_data) {
                                    return (
                                      <div>
                                        <Alert
                                          message="✅ 处理器执行结果"
                                          description={
                                            <div>
                                              <div style={{ marginBottom: '8px', fontWeight: 'bold', color: '#52c41a' }}>
                                                {outputData.message || '任务完成'}
                                              </div>
                                              <div style={{ fontSize: '12px', color: '#666' }}>
                                                任务类型: {outputData.task_type || 'unknown'}
                                              </div>
                                              <div style={{ fontSize: '12px', color: '#666' }}>
                                                完成时间: {outputData.completed_at ? new Date(outputData.completed_at).toLocaleString() : '未知'}
                                              </div>
                                            </div>
                                          }
                                          type="success"
                                          showIcon
                                          style={{ marginBottom: '8px' }}
                                        />
                                        {/* 显示具体的输出数据 */}
                                        {outputData.output_data && (
                                          <div style={{ marginTop: '8px' }}>
                                            <Text strong style={{ color: '#52c41a' }}>具体输出结果:</Text>
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
                                        <details style={{ marginTop: '8px' }}>
                                          <summary style={{ cursor: 'pointer', color: '#1890ff', fontSize: '12px' }}>
                                            🔍 查看完整数据结构
                                          </summary>
                                          <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', marginTop: '8px', maxHeight: '150px', overflow: 'auto', fontSize: '11px' }}>
                                            {JSON.stringify(outputData, null, 2)}
                                          </pre>
                                        </details>
                                      </div>
                                    );
                                  } else {
                                    // 简单输出数据
                                    return (
                                      <Alert
                                        message="📄 执行结果"
                                        description={
                                          <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', maxHeight: '150px', overflow: 'auto', fontSize: '11px', margin: 0, whiteSpace: 'pre-wrap' }}>
                                            {JSON.stringify(outputData, null, 2)}
                                          </pre>
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
                        </Card>
                      ))}
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
        }}
        width={900}
        footer={[
          <Button key="save-draft" onClick={handleSaveDraft}>
            保存草稿
          </Button>,
          <Button key="cancel" onClick={() => {
            setSubmitModalVisible(false);
            setSubWorkflowsForSubmit([]);
          }}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={handleSubmitConfirm}>
            提交结果
          </Button>,
        ]}
      >
        {(() => {
          console.log('🎨 [UI渲染] 提交任务结果模态框渲染:');
          console.log('   - submitModalVisible:', submitModalVisible);
          console.log('   - currentTask:', currentTask?.task_instance_id);
          console.log('   - subWorkflowsForSubmit初始状态:', subWorkflowsForSubmit);
          console.log('   - loadingSubWorkflows:', loadingSubWorkflows);
          return null;
        })()}
        <div style={{ display: 'flex', gap: '16px' }}>
          {/* 左侧：任务结果表单 */}
          <div style={{ flex: 1 }}>
            <Form form={submitForm} layout="vertical">
              <Form.Item
                name="result"
                label="任务结果"
                rules={[{ required: true, message: '请输入任务结果' }]}
                extra={
                  (currentTask?.input_data?.immediate_upstream || 
                   currentTask?.input_data?.workflow_global ||
                   currentTask?.context_data?.immediate_upstream_results ||
                   currentTask?.context_data?.upstream_outputs) ? 
                    '提示：您可以在上方的"任务详情"中查看上游处理器执行结果和上下文数据' : null
                }
              >
                <TextArea rows={8} placeholder="请详细描述任务完成情况...

可以参考上游上下文数据来完成任务。
您也可以从右侧的子工作流结果中选择内容填充。" />
              </Form.Item>
              <Form.Item
                name="attachments"
                label="附件"
              >
                <Input placeholder="附件链接（可选）" />
              </Form.Item>
              <Form.Item
                name="notes"
                label="备注"
              >
                <TextArea rows={2} placeholder="其他备注信息（可选）

可以记录使用了哪些上游数据、遇到的问题等" />
              </Form.Item>
            </Form>
          </div>
          
          {/* 右侧：子工作流列表 */}
          <div style={{ width: '350px', borderLeft: '1px solid #f0f0f0', paddingLeft: '16px' }}>
            <div style={{ marginBottom: '12px' }}>
              <Text strong style={{ fontSize: '16px' }}>相关子工作流</Text>
              {loadingSubWorkflows && <Spin size="small" style={{ marginLeft: '8px' }} />}
            </div>
            
            {/* 添加详细的UI调试日志 */}
            {(() => {
              console.log('🎨 [UI渲染] 子工作流区域渲染检查:');
              console.log('   - subWorkflowsForSubmit:', subWorkflowsForSubmit);
              console.log('   - subWorkflowsForSubmit类型:', typeof subWorkflowsForSubmit);
              console.log('   - subWorkflowsForSubmit.length:', subWorkflowsForSubmit?.length);
              console.log('   - Array.isArray(subWorkflowsForSubmit):', Array.isArray(subWorkflowsForSubmit));
              console.log('   - loadingSubWorkflows:', loadingSubWorkflows);
              console.log('   - 显示条件 (length > 0):', subWorkflowsForSubmit?.length > 0);
              
              if (subWorkflowsForSubmit?.length > 0) {
                console.log('   ✅ 应该显示子工作流列表');
                console.log('   📋 子工作流预览:', subWorkflowsForSubmit.slice(0, 2).map((sub: any, idx: number) => ({
                  index: idx,
                  name: sub?.subdivision_name,
                  id: sub?.subdivision_id,
                  status: sub?.status,
                  hasWorkflowDetails: !!sub?.workflowDetails
                })));
              } else {
                console.log('   ❌ 将显示空状态消息');
                console.log('   原因分析:');
                if (subWorkflowsForSubmit === null || subWorkflowsForSubmit === undefined) {
                  console.log('     - subWorkflowsForSubmit 是 null/undefined');
                } else if (!Array.isArray(subWorkflowsForSubmit)) {
                  console.log('     - subWorkflowsForSubmit 不是数组');
                } else if (subWorkflowsForSubmit.length === 0) {
                  console.log('     - subWorkflowsForSubmit 是空数组');
                }
              }
              
              return null; // 这个函数只用于日志，不返回UI元素
            })()}
            
            {subWorkflowsForSubmit.length > 0 ? (
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {(() => {
                  console.log('🎨 [UI渲染] 开始渲染子工作流卡片列表:');
                  console.log('   - 将渲染', subWorkflowsForSubmit.length, '个卡片');
                  return null;
                })()}
                {subWorkflowsForSubmit.map((subWorkflow, index) => {
                  console.log(`🎨 [UI渲染] 渲染卡片 ${index + 1}:`, {
                    subdivision_name: subWorkflow?.subdivision_name,
                    subdivision_id: subWorkflow?.subdivision_id,
                    status: subWorkflow?.status,
                    hasWorkflowDetails: !!subWorkflow?.workflowDetails,
                    workflowDetailsKeys: subWorkflow?.workflowDetails ? Object.keys(subWorkflow.workflowDetails) : []
                  });
                  
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
                            console.log(`🎨 [UI渲染] 卡片状态显示: ${subWorkflow.subdivision_name}`, {
                              subdivisionStatus: subWorkflow.status,
                              workflowInstanceStatus: subWorkflow.workflowDetails?.status,
                              actualStatusUsed: actualStatus
                            });
                            
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
                            
                            console.log(`🎨 [UI渲染] 时间显示: ${subWorkflow.subdivision_name}`, {
                              workflowInstanceCreatedAt: subWorkflow.workflowDetails?.created_at,
                              subdivisionCreatedAt: subWorkflow.created_at,
                              subdivisionCreatedAtAlt: subWorkflow.subdivision_created_at,
                              finalTimeUsed: createTime
                            });
                            
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
                {(() => {
                  console.log('🎨 [UI渲染] 显示空状态区域:');
                  console.log('   - loadingSubWorkflows:', loadingSubWorkflows);
                  console.log('   - subWorkflowsForSubmit:', subWorkflowsForSubmit);
                  console.log('   - 空状态原因:', 
                    loadingSubWorkflows ? '正在加载中' : 
                    !subWorkflowsForSubmit ? 'subWorkflowsForSubmit为空' :
                    !Array.isArray(subWorkflowsForSubmit) ? 'subWorkflowsForSubmit不是数组' :
                    subWorkflowsForSubmit.length === 0 ? 'subWorkflowsForSubmit是空数组' : '未知原因'
                  );
                  return null;
                })()}
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
        </div>
      </Modal>

      {/* 拒绝任务模态框 */}
      <Modal
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
      </Modal>

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
