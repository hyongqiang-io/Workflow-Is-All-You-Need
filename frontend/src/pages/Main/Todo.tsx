import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Button, Modal, Form, Input, Select, message, Space, Collapse, Typography, Divider, Alert, Spin } from 'antd';
import { SaveOutlined, BranchesOutlined, EditOutlined, EyeOutlined } from '@ant-design/icons';
import { useTaskStore } from '../../stores/taskStore';
import { useAuthStore } from '../../stores/authStore';
import { taskSubdivisionApi } from '../../services/api';
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

  useEffect(() => {
    if (error) {
      message.error(error);
    }
  }, [error]);

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

  // 检查任务是否有细分结果可以编辑（模拟：任务类型为human，状态为in_progress，且包含细分标识）
  const hasSubdivisionResult = (task: any) => {
    // 这里是模拟逻辑，实际应该通过API检查任务是否有细分工作流且已完成
    return task.task_type === 'human' && 
           task.status?.toLowerCase() === 'in_progress' && 
           ((task.result_summary || '').includes('细分') || 
           (task.task_title || '').includes('细分') ||
           (task.output_data || '').includes('细分工作流'));
  };

  // 检查任务是否已进行拆解（有子工作流）
  const hasSubWorkflow = (task: any) => {
    // 检查任务的上下文数据或输出数据中是否包含细分工作流信息
    // 可以通过多种方式检测：
    // 1. context_data中包含subdivision相关信息
    // 2. output_data中包含子工作流实例ID
    // 3. result_summary中提到细分工作流
    const contextData = task.context_data;
    const outputData = task.output_data;
    const resultSummary = task.result_summary || '';
    
    // 检查上下文数据中的细分信息
    if (contextData && typeof contextData === 'object') {
      if (contextData.subdivision_id || contextData.sub_workflow_instance_id) {
        return true;
      }
    }
    
    // 检查上下文数据字符串格式
    if (typeof contextData === 'string') {
      try {
        const parsedContext = JSON.parse(contextData);
        if (parsedContext.subdivision_id || parsedContext.sub_workflow_instance_id) {
          return true;
        }
      } catch (e) {
        // 解析失败，继续其他检查
      }
    }
    
    // 检查输出数据中的子工作流信息
    if (outputData && typeof outputData === 'string') {
      if (outputData.includes('子工作流') || outputData.includes('细分工作流') || 
          outputData.includes('sub_workflow') || outputData.includes('subdivision')) {
        return true;
      }
    }
    
    // 检查结果摘要
    if (resultSummary.includes('细分') || resultSummary.includes('子工作流') || 
        resultSummary.includes('拆解')) {
      return true;
    }
    
    return false;
  };

  // 从任务数据中提取子工作流ID
  const extractSubWorkflowId = (task: any): string | null => {
    const contextData = task.context_data;
    
    // 尝试从上下文数据中提取
    if (contextData && typeof contextData === 'object') {
      return contextData.sub_workflow_instance_id || contextData.subdivision_id || null;
    }
    
    // 尝试从字符串格式的上下文数据中提取
    if (typeof contextData === 'string') {
      try {
        const parsedContext = JSON.parse(contextData);
        return parsedContext.sub_workflow_instance_id || parsedContext.subdivision_id || null;
      } catch (e) {
        // 如果无法解析JSON，尝试正则表达式提取
        const workflowIdMatch = contextData.match(/sub_workflow_instance_id["\s]*:["\s]*([a-f0-9-]+)/i);
        if (workflowIdMatch) {
          return workflowIdMatch[1];
        }
        
        const subdivisionIdMatch = contextData.match(/subdivision_id["\s]*:["\s]*([a-f0-9-]+)/i);
        if (subdivisionIdMatch) {
          return subdivisionIdMatch[1];
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
      
      // 获取子工作流的执行结果
      let resultText = '';
      
      // 从不同可能的位置提取结果
      const workflowDetails = subWorkflow.workflowDetails || subWorkflow;
      
      if (workflowDetails.result_summary) {
        resultText = workflowDetails.result_summary;
      } else if (workflowDetails.output_data) {
        // 如果有输出数据，格式化显示
        try {
          const outputData = typeof workflowDetails.output_data === 'string' 
            ? JSON.parse(workflowDetails.output_data) 
            : workflowDetails.output_data;
          
          if (outputData.result) {
            resultText = outputData.result;
          } else {
            resultText = JSON.stringify(outputData, null, 2);
          }
        } catch (e) {
          resultText = workflowDetails.output_data;
        }
      } else {
        // 构造基本的结果描述
        const status = workflowDetails.status || '未知';
        const name = workflowDetails.subdivision_name || subWorkflow.subdivision_name || '子工作流';
        resultText = `=== ${name} 执行结果 ===\n\n状态: ${status}\n执行时间: ${workflowDetails.completed_at || workflowDetails.created_at || '未知'}\n\n请根据子工作流的执行情况补充具体的任务完成结果。`;
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
      console.error('❌ 选择子工作流结果失败:', error);
      message.error('获取子工作流结果失败');
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
    // 模拟细分工作流结果数据
    const mockSubdivisionResult = {
      subdivision_id: 'sub-' + Math.random().toString(36).substr(2, 9),
      subdivision_name: '数据分析细分流程',
      original_result: `=== 细分工作流执行结果 ===

📊 执行统计:
   • 总任务数: 4
   • 完成任务数: 4
   • 执行时长: 15分钟

📋 执行结果:
1. 数据加载任务: 成功加载销售数据文件 sales_q4.csv，包含 1250 条记录
2. 数据清洗任务: 清洗异常数据，移除 15 条无效记录，保留 1235 条有效记录
3. 数据分析任务: 完成销售趋势分析，识别出 Q4 季度销售额增长 18.5%
4. 报告生成任务: 生成 Excel 分析报告，包含图表和详细数据表

📝 任务详情:
   1. 数据加载
      结果: 成功加载销售数据，数据格式验证通过
   2. 数据清洗  
      结果: 清理了缺失值和异常值，数据质量提升
   3. 数据分析
      结果: 生成了销售趋势图表和关键指标分析
   4. 报告生成
      结果: 输出格式为 Excel，包含所有分析结果

✅ 细分工作流已成功完成所有任务。`,
      execution_summary: '数据分析细分流程执行完成',
      total_tasks: 4,
      completed_tasks: 4,
      execution_duration: '15分钟'
    };

    setCurrentTask(task);
    setSubdivisionResultData(mockSubdivisionResult);
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

  // 处理查看子工作流进度
  const handleViewSubWorkflowProgress = async (task: any) => {
    console.log('🔍 查看子工作流进度', task.task_title);
    
    try {
      // 首先尝试从任务上下文数据中提取子工作流ID
      let subWorkflowId = extractSubWorkflowId(task);
      
      // 如果无法从任务数据中提取，尝试通过API获取
      if (!subWorkflowId) {
        console.log('📡 尝试通过API获取子工作流信息...');
        try {
          const response = await taskSubdivisionApi.getTaskSubWorkflowInfo(task.task_instance_id);
          console.log('API响应:', response);
          
          // 处理不同的响应格式
          const responseData = response?.data || response;
          if (responseData && responseData.success && responseData.data) {
            subWorkflowId = responseData.data.sub_workflow_instance_id || responseData.data.workflow_instance_id;
            console.log('✅ 通过API获取到子工作流ID:', subWorkflowId);
          }
        } catch (apiError) {
          console.warn('⚠️ API获取子工作流信息失败:', apiError);
        }
      }
      
      if (subWorkflowId) {
        console.log('📊 找到子工作流ID:', subWorkflowId);
        setCurrentSubWorkflowId(subWorkflowId);
        setCurrentTask(task);
        setSubWorkflowViewerVisible(true);
      } else {
        console.warn('⚠️ 未找到子工作流ID');
        message.warning('无法找到子工作流信息，请确认此任务已完成拆解操作');
      }
    } catch (error) {
      console.error('❌ 查看子工作流进度失败:', error);
      message.error('获取子工作流信息失败，请稍后重试');
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>我的待办</h2>
      
      <Card>
        <List
          loading={loading}
          dataSource={tasks}
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
                hasSubdivisionResult(item) && (
                  <Button 
                    key="edit-subdivision-result" 
                    type="primary"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => handleEditSubdivisionResult(item)}
                    style={{ 
                      backgroundColor: '#fa8c16', 
                      borderColor: '#fa8c16',
                      fontWeight: 'bold'
                    }}
                  >
                    编辑细分结果
                  </Button>
                ),
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
                // IN_PROGRESS状态可以请求帮助
                item.status.toLowerCase() === 'in_progress' && (
                  <Button 
                    key="help" 
                    size="small"
                    onClick={() => handleRequestHelp(item)}
                  >
                    请求帮助
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
                    <Tag color={getPriorityColor(item.priority)}>
                      {getPriorityText(item.priority)}优先级
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
                        <span>任务ID: {item.task_instance_id}</span>
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
        width={800}
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
                <div>
                  <Text strong>优先级: </Text>
                  <Tag color={getPriorityColor(currentTask.priority)}>
                    {getPriorityText(currentTask.priority)}
                  </Tag>
                </div>
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
                <div style={{ background: '#f6f6f6', padding: '8px', marginBottom: '12px', fontSize: '12px', borderRadius: '4px' }}>
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
                </div>
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
                              <Text strong>上游节点输出</Text>
                              <Tag color="blue" style={{ marginLeft: '8px' }}>
                                {currentTask.context_data.upstream_outputs.length} 个节点
                              </Tag>
                            </div>
                          } 
                          key="upstream_outputs"
                        >
                          {currentTask.context_data.upstream_outputs.map((upstreamNode: any, index: number) => (
                            <Card 
                              key={index} 
                              size="small" 
                              style={{ marginBottom: '12px' }}
                              title={
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <Text strong style={{ color: '#1890ff' }}>{upstreamNode.node_name || `节点 ${index + 1}`}</Text>
                                  <Tag color="green">已完成</Tag>
                                </div>
                              }
                              extra={
                                upstreamNode.completed_at && (
                                  <Text type="secondary" style={{ fontSize: '12px' }}>
                                    {new Date(upstreamNode.completed_at).toLocaleString()}
                                  </Text>
                                )
                              }
                            >
                              {upstreamNode.node_description && (
                                <Alert
                                  message="节点描述"
                                  description={upstreamNode.node_description}
                                  type="info"
                                  showIcon={false}
                                  style={{ marginBottom: '12px', fontSize: '12px' }}
                                />
                              )}
                              
                              {upstreamNode.output_data && Object.keys(upstreamNode.output_data).length > 0 ? (
                                <div>
                                  <Text strong style={{ color: '#52c41a' }}>输出数据:</Text>
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
                                                message="任务结果"
                                                description={outputData.result}
                                                type="success"
                                                showIcon
                                                style={{ marginBottom: '8px' }}
                                              />
                                              {Object.keys(outputData).length > 1 && (
                                                <details>
                                                  <summary style={{ cursor: 'pointer', color: '#1890ff' }}>查看完整输出数据</summary>
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
                                  message="该节点无输出数据"
                                  type="warning"
                                  showIcon={false}
                                  style={{ fontSize: '12px' }}
                                />
                              )}
                            </Card>
                          ))}
                        </Panel>
                      )}
                      
                      {currentTask.context_data.current_node && (
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
                      )}
                    </>
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
                {(!currentTask.context_data || Object.keys(currentTask.context_data).length === 0) &&
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
                extra={currentTask?.input_data?.immediate_upstream || currentTask?.input_data?.workflow_global ? 
                  '提示：您可以在上方的"任务详情"中查看上游上下文数据' : null
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
        width={1200}
        style={{ top: 20 }}
      >
        {currentSubWorkflowId && user && (
          <div style={{ height: '70vh' }}>
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
