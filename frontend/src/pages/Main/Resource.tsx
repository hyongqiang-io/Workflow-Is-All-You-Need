import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Card, List, Avatar, Tag, Input, Select, Row, Col, Button, message, Statistic, Typography, Empty,
  Tabs, Table, Modal, Form, Upload, Space, Descriptions, Divider, Tooltip, Checkbox
} from 'antd';
import { 
  UserOutlined, 
  RobotOutlined, 
  SearchOutlined, 
  FilterOutlined,
  ReloadOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  SettingOutlined,
  DeleteOutlined,
  ToolOutlined,
  EyeOutlined,
  EditOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { resourceAPI, agentAPI, processorAPI } from '../../services/api';
import MCPToolsManagement from '../../components/MCPToolsManagement';
import AgentToolSelector from '../../components/AgentToolSelector';

const { Search } = Input;
const { Option } = Select;
const { Title, Text } = Typography;
const { TextArea } = Input;

interface ResourceItem {
  id: string;
  name: string;
  type: 'human' | 'agent';
  status: 'online' | 'offline' | 'busy';
  description: string;
  capabilities: string[];
  avatar?: string;
  // Agent特有属性
  tools?: string[];
  config?: any;
  agent_type?: 'custom' | 'imported';
  created_at?: string;
  last_used?: string;
}

interface Tool {
  id: string;
  name: string;
  description: string;
  category: string;
  status: 'available' | 'in_use' | 'deprecated';
}

interface Processor {
  processor_id: string;
  name: string;
  type: 'human' | 'agent' | 'mix';
  version: number;
  created_at: string;
  user_id?: string;
  agent_id?: string;
  username?: string;
  user_email?: string;
  agent_name?: string;
  agent_description?: string;
}

const Resource: React.FC = () => {
  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [processors, setProcessors] = useState<Processor[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'human' | 'agent'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'online' | 'offline' | 'busy'>('all');
  const [activeTab, setActiveTab] = useState('overview');
  
  // Agent管理相关状态
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [toolModalVisible, setToolModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<ResourceItem | null>(null);
  const [importForm] = Form.useForm();
  const [toolForm] = Form.useForm();
  const [editForm] = Form.useForm();
  
  // Processor管理相关状态
  const [createProcessorModalVisible, setCreateProcessorModalVisible] = useState(false);
  const [deleteProcessorModalVisible, setDeleteProcessorModalVisible] = useState(false);
  const [processorToDelete, setProcessorToDelete] = useState<Processor | null>(null);
  const [createProcessorForm] = Form.useForm();

  // Agent删除相关状态
  const [deleteAgentModalVisible, setDeleteAgentModalVisible] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState<ResourceItem | null>(null);

  // Agent创建相关状态
  const [createAgentModalVisible, setCreateAgentModalVisible] = useState(false);
  const [createAgentForm] = Form.useForm();
  const [toolBindings, setToolBindings] = useState<any[]>([]);  // 新Agent的工具绑定
  const [editToolBindings, setEditToolBindings] = useState<any[]>([]);  // 编辑Agent的工具绑定

  // 使用 useMemo 优化过滤计算，避免无限重渲染
  const filteredResources = useMemo(() => {
    let filtered = resources;

    // 按类型过滤
    if (typeFilter !== 'all') {
      filtered = filtered.filter(resource => resource.type === typeFilter);
    }

    // 按状态过滤
    if (statusFilter !== 'all') {
      filtered = filtered.filter(resource => resource.status === statusFilter);
    }

    // 按搜索文本过滤
    if (searchText) {
      filtered = filtered.filter(resource =>
        resource.name.toLowerCase().includes(searchText.toLowerCase()) ||
        resource.description.toLowerCase().includes(searchText.toLowerCase()) ||
        (Array.isArray(resource.capabilities) && resource.capabilities.some((cap: string) => cap.toLowerCase().includes(searchText.toLowerCase())))
      );
    }

    return filtered;
  }, [resources, searchText, typeFilter, statusFilter]);

  const loadResources = useCallback(async () => {
    setLoading(true);
    try {
      // 获取在线资源
      let onlineResources: any = { users: [] };
      try {
        const onlineResponse: any = await resourceAPI.getOnlineResources();
        if (onlineResponse.success) {
          onlineResources = onlineResponse.data || { users: [] };
        }
      } catch (error) {
        console.warn('获取在线资源失败:', error);
      }
      
      // 获取所有Agent
      let agents: any = [];
      try {
        const agentsResponse: any = await agentAPI.getAgents();
        if (agentsResponse.success && agentsResponse.data?.processors) {
          agents = agentsResponse.data.processors.filter((p: any) => p.type === 'agent');
        }
      } catch (error) {
        console.warn('获取Agent列表失败:', error);
      }
      
      // 合并资源数据，只处理一次 capabilities
      const allResources: ResourceItem[] = [
        // 在线用户
        ...(Array.isArray(onlineResources.users) ? onlineResources.users : []).map((user: any) => ({
          id: user.user_id,
          name: user.username,
          type: 'human' as const,
          status: user.status || 'online' as const,
          description: user.full_name || user.description || '用户',
          capabilities: Array.isArray(user.capabilities) ? user.capabilities : [],
        })),
        // Agent
        ...(Array.isArray(agents) ? agents : []).map((agent: any) => ({
          id: agent.id || agent.agent_id || agent.processor_id,
          name: agent.name,
          type: 'agent' as const,
          status: agent.status || 'online',
          description: agent.description || 'AI助手',
          capabilities: Array.isArray(agent.capabilities) ? agent.capabilities : [],
          tools: Array.isArray(agent.tools) ? agent.tools : [],
          config: agent.config,
          agent_type: agent.type || 'imported',
          created_at: agent.created_at,
          last_used: agent.last_used,
        })),
      ];
      
      setResources(allResources);
      
      // 显示统计信息
      const onlineUsers = allResources.filter(r => r.type === 'human' && r.status === 'online').length;
      const onlineAgents = allResources.filter(r => r.type === 'agent' && r.status === 'online').length;
      message.success(`资源加载完成！在线用户: ${onlineUsers} 个, 在线Agent: ${onlineAgents} 个`);
    } catch (error) {
      console.error('加载资源失败:', error);
      message.error('加载资源失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTools = useCallback(async () => {
    try {
      const response: any = await agentAPI.getTools();
      if (response.success && Array.isArray(response.data)) {
        setTools(response.data);
      } else {
        // 使用模拟数据
        const mockTools: Tool[] = [
          {
            id: '1',
            name: '文本分析工具',
            description: '用于文本情感分析和关键词提取',
            category: '文本处理',
            status: 'available'
          },
          {
            id: '2',
            name: '数据可视化工具',
            description: '生成各种图表和数据可视化',
            category: '数据分析',
            status: 'available'
          },
          {
            id: '3',
            name: '图像识别API',
            description: '识别图像中的物体和场景',
            category: '图像处理',
            status: 'available'
          }
        ];
        setTools(mockTools);
      }
    } catch (error) {
      console.error('加载工具失败:', error);
      setTools([]);
    }
  }, []);

  const loadProcessors = useCallback(async () => {
    try {
      const response: any = await processorAPI.getRegisteredProcessors();
      if (response.success && Array.isArray(response.data.processors)) {
        setProcessors(response.data.processors);
      }
    } catch (error) {
      console.error('加载处理器失败:', error);
      setProcessors([]);
    }
  }, []);

  // 初始化数据加载
  useEffect(() => {
    loadResources();
    loadTools();
    loadProcessors();
  }, [loadResources, loadTools, loadProcessors]);

  // Agent管理相关方法
  // 使用 useCallback 优化事件处理函数
  const handleImportAgent = useCallback(() => {
    setImportModalVisible(true);
    importForm.resetFields();
  }, [importForm]);

  const handleImportConfirm = useCallback(async () => {
    try {
      const values = await importForm.validateFields();
      
      const formData = new FormData();
      if (values.agentFile?.fileList?.[0]) {
        formData.append('file', values.agentFile.fileList[0].originFileObj);
      }
      if (values.description) {
        formData.append('description', values.description);
      }
      
      await agentAPI.importAgent(formData);
      message.success('Agent导入成功');
      setImportModalVisible(false);
      loadResources();
    } catch (error: any) {
      console.error('导入失败:', error);
      message.error(error.response?.data?.detail || '导入失败');
    }
  }, [importForm, loadResources]);

  const handleBindTools = useCallback((agent: ResourceItem) => {
    setSelectedAgent(agent);
    setToolModalVisible(true);
    // 不再使用旧的表单，工具绑定将通过AgentToolSelector组件处理
  }, []);

  const handleBindToolsConfirm = useCallback(async () => {
    // 工具绑定现在直接通过AgentToolSelector组件处理
    // 这里只需要关闭模态框
    setToolModalVisible(false);
    message.success('工具绑定已保存');
    loadResources();
  }, [loadResources]);

  const handleViewAgent = useCallback((agent: ResourceItem) => {
    setSelectedAgent(agent);
    setDetailModalVisible(true);
  }, []);

  const handleEditAgent = useCallback((agent: ResourceItem) => {
    setSelectedAgent(agent);
    setEditModalVisible(true);
    setEditToolBindings([]); // 重置编辑工具绑定
    
    // 处理配置字段 - 如果是对象，转换为JSON字符串
    let configValue = agent.config || {};
    if (typeof configValue === 'object' && configValue !== null) {
      configValue = JSON.stringify(configValue, null, 2);
    }
    
    editForm.setFieldsValue({
      name: agent.name,
      description: agent.description,
      capabilities: agent.capabilities || [],
      config: configValue
    });
  }, [editForm]);

  const handleEditConfirm = useCallback(async () => {
    try {
      const values = await editForm.validateFields();
      if (!selectedAgent || !selectedAgent.id) {
        message.error('Agent信息不完整，请重试');
        return;
      }
      
      console.log('开始更新Agent，ID:', selectedAgent.id);
      // 处理配置字段 - 如果是字符串，尝试解析为JSON
      let toolConfig = values.config;
      if (typeof values.config === 'string' && values.config.trim()) {
        try {
          toolConfig = JSON.parse(values.config);
        } catch (e) {
          message.error('配置信息格式错误，请输入有效的JSON格式');
          return;
        }
      }
      
      console.log('更新数据:', {
        agent_name: values.name,
        description: values.description,
        capabilities: values.capabilities,
        tool_config: toolConfig
      });
      
      const response = await agentAPI.updateAgent(selectedAgent.id, {
        agent_name: values.name,
        description: values.description,
        capabilities: values.capabilities,
        tool_config: toolConfig
      });
      
      console.log('Agent更新响应:', response);
      
      if (response && response.data && response.data.success) {
        // 如果工具绑定有变化，同步更新工具绑定
        if (editToolBindings.length > 0) {
          try {
            console.log('🔥 开始同步工具绑定变化...');
            // 导入agentToolsAPI
            const { agentToolsAPI } = await import('../../services/api');
            
            // 批量绑定工具（这会覆盖现有绑定）
            await agentToolsAPI.batchBindTools(selectedAgent.id, editToolBindings);
            console.log('✅ 工具绑定同步成功');
            message.success(`Agent更新成功，工具绑定已同步`);
          } catch (toolError: any) {
            console.error('❌ 工具绑定同步失败:', toolError);
            message.warning('Agent更新成功，但工具绑定同步失败: ' + toolError.message);
          }
        } else {
          message.success('Agent更新成功');
        }
        
        setEditModalVisible(false);
        setEditToolBindings([]);  // 清空编辑工具绑定
        loadResources();
      } else {
        message.error(response?.data?.message || '更新Agent失败');
      }
    } catch (error: any) {
      console.error('更新失败:', error);
      message.error(error.response?.data?.detail || '更新Agent失败');
    }
  }, [editForm, selectedAgent, loadResources, editToolBindings]);

  const handleDeleteAgent = useCallback((agent: ResourceItem) => {
    console.log('🔥 准备删除Agent:', agent);
    console.log('🔥 Agent ID:', agent.id);
    console.log('🔥 Agent Name:', agent.name);
    
    setAgentToDelete(agent);
    setDeleteAgentModalVisible(true);
  }, []);

  const confirmDeleteAgent = useCallback(async () => {
    if (!agentToDelete) return;
    
    try {
      console.log('🔥 用户确认删除，开始调用API...');
      await agentAPI.deleteAgent(agentToDelete.id);
      message.success('Agent删除成功');
      setDeleteAgentModalVisible(false);
      setAgentToDelete(null);
      loadResources();
    } catch (error: any) {
      console.error('❌ Agent删除失败:', error);
      message.error(error.response?.data?.detail || '删除Agent失败');
    }
  }, [agentToDelete, loadResources]);

  const cancelDeleteAgent = useCallback(() => {
    console.log('🔥 用户取消删除操作');
    setDeleteAgentModalVisible(false);
    setAgentToDelete(null);
  }, []);

  const handleCreateAgent = useCallback(() => {
    console.log('🔥 准备创建新Agent');
    setCreateAgentModalVisible(true);
    createAgentForm.resetFields();
    setToolBindings([]);  // 重置工具绑定
  }, [createAgentForm]);

  const confirmCreateAgent = useCallback(async () => {
    try {
      console.log('🔥 开始验证Agent创建表单...');
      const values = await createAgentForm.validateFields();
      console.log('🔥 表单验证通过，Agent数据:', values);
      
      // 处理tool_config和parameters，将字符串转换为JSON对象
      const agentData = {
        ...values,
        tool_config: values.tool_config ? JSON.parse(values.tool_config) : null,
        parameters: values.parameters ? JSON.parse(values.parameters) : null,
        is_autonomous: values.is_autonomous || false
      };
      
      console.log('🔥 处理后的Agent数据:', agentData);
      
      // 创建Agent
      const response = await agentAPI.createAgent(agentData);
      const createdAgent = response.data;
      
      // 如果有工具绑定，创建Agent后立即绑定工具
      if (toolBindings.length > 0 && createdAgent?.agent_id) {
        console.log('🔥 开始绑定工具到新创建的Agent...');
        try {
          // 导入agentToolsAPI
          const { agentToolsAPI } = await import('../../services/api');
          
          // 批量绑定工具
          await agentToolsAPI.batchBindTools(createdAgent.agent_id, toolBindings);
          console.log('✅ 工具绑定成功');
          message.success(`Agent创建成功，已绑定 ${toolBindings.length} 个工具`);
        } catch (toolError: any) {
          console.error('❌ 工具绑定失败:', toolError);
          message.warning('Agent创建成功，但工具绑定失败: ' + toolError.message);
        }
      } else {
        message.success('Agent创建成功');
      }
      
      setCreateAgentModalVisible(false);
      createAgentForm.resetFields();
      setToolBindings([]);  // 清空工具绑定
      loadResources();
    } catch (error: any) {
      console.error('❌ Agent创建失败:', error);
      if (error.name === 'SyntaxError') {
        message.error('JSON格式错误，请检查工具配置和参数配置');
      } else {
        message.error(error.response?.data?.detail || '创建Agent失败');
      }
    }
  }, [createAgentForm, loadResources, toolBindings]);

  const cancelCreateAgent = useCallback(() => {
    console.log('🔥 用户取消创建Agent');
    setCreateAgentModalVisible(false);
    createAgentForm.resetFields();
    setToolBindings([]);  // 清空工具绑定
  }, [createAgentForm]);

  // Processor管理相关方法
  const handleCreateProcessor = useCallback(() => {
    setCreateProcessorModalVisible(true);
    createProcessorForm.resetFields();
  }, [createProcessorForm]);

  const handleCreateProcessorConfirm = useCallback(async () => {
    try {
      console.log('开始验证表单字段...');
      const values = await createProcessorForm.validateFields();
      console.log('表单验证通过，值为:', values);
      
      const requestData: any = {
        name: values.name,
        type: values.type
      };

      // 根据类型设置相应的ID
      if (values.type === 'human' && values.user_id) {
        requestData.user_id = values.user_id;
      } else if (values.type === 'agent' && values.agent_id) {
        requestData.agent_id = values.agent_id;
      } else if (values.type === 'mix' && values.user_id && values.agent_id) {
        requestData.user_id = values.user_id;
        requestData.agent_id = values.agent_id;
      }

      console.log('准备发送请求，数据为:', requestData);
      const response: any = await processorAPI.createProcessor(requestData);
      console.log('API响应:', response);
      
      if (response && response.success) {
        message.success('处理器创建成功');
        setCreateProcessorModalVisible(false);
        loadProcessors();
      } else {
        console.error('创建失败，响应:', response);
        message.error(response?.message || '创建处理器失败');
      }
    } catch (error: any) {
      console.error('创建处理器失败:', error);
      if (error.response) {
        console.error('错误响应状态:', error.response.status);
        console.error('错误响应数据:', error.response.data);
        console.error('错误响应头:', error.response.headers);
        
        let errorMessage = '创建处理器失败';
        if (error.response.data?.message) {
          errorMessage = error.response.data.message;
        } else if (error.response.data?.detail) {
          errorMessage = error.response.data.detail;
        } else if (error.response.status === 405) {
          errorMessage = 'API接口方法不允许，请检查后端服务';
        } else if (error.response.status === 422) {
          errorMessage = '请求数据格式错误，请检查输入参数';
        }
        
        message.error(errorMessage);
      } else {
        console.error('网络错误:', error.message);
        message.error(error.message || '网络连接失败');
      }
    }
  }, [createProcessorForm, loadProcessors]);

  const handleDeleteProcessor = useCallback((processor: Processor) => {
    console.log('handleDeleteProcessor called with:', processor);
    setProcessorToDelete(processor);
    setDeleteProcessorModalVisible(true);
  }, []);

  const handleDeleteProcessorConfirm = useCallback(async () => {
    if (!processorToDelete) return;
    
    try {
      console.log('Deleting processor:', processorToDelete.processor_id);
      await processorAPI.deleteProcessor(processorToDelete.processor_id);
      message.success('处理器删除成功');
      setDeleteProcessorModalVisible(false);
      setProcessorToDelete(null);
      loadProcessors();
    } catch (error: any) {
      console.error('Delete processor error:', error);
      message.error(error.response?.data?.detail || '删除处理器失败');
    }
  }, [processorToDelete, loadProcessors]);

  const handleDeleteProcessorCancel = useCallback(() => {
    setDeleteProcessorModalVisible(false);
    setProcessorToDelete(null);
  }, []);

  // 使用 useCallback 优化工具函数
  const getStatusColor = useCallback((status: string) => {
    switch (status) {
      case 'online':
        return 'success';
      case 'offline':
        return 'default';
      case 'busy':
        return 'warning';
      default:
        return 'default';
    }
  }, []);

  const getStatusText = useCallback((status: string) => {
    switch (status) {
      case 'online':
        return '在线';
      case 'offline':
        return '离线';
      case 'busy':
        return '忙碌';
      default:
        return status;
    }
  }, []);

  const getResourceIcon = useCallback((type: string) => {
    return type === 'human' ? <UserOutlined /> : <RobotOutlined />;
  }, []);

  const getResourceColor = useCallback((type: string) => {
    return type === 'human' ? '#1890ff' : '#722ed1';
  }, []);

  // 使用 useMemo 优化统计计算
  const stats = useMemo(() => ({
    total: resources.length,
    online: resources.filter(r => r.status === 'online').length,
    humans: resources.filter(r => r.type === 'human').length,
    agents: resources.filter(r => r.type === 'agent').length,
  }), [resources]);

  // 使用 useMemo 优化 Agent 列表
  const agentList = useMemo(() => 
    resources.filter(r => r.type === 'agent'), 
    [resources]
  );

  // 使用 useMemo 优化Tabs配置
  const tabItems = useMemo(() => [
    {
      key: 'overview',
      label: <span><TeamOutlined />资源概览</span>,
      children: (
        <div>
          {/* 搜索和过滤 */}
          <div style={{ marginBottom: '16px' }}>
            <Row gutter={[16, 16]} align="middle">
              <Col xs={24} sm={12} md={8}>
                <Search
                  placeholder="搜索资源名称、描述或能力"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  prefix={<SearchOutlined />}
                  allowClear
                />
              </Col>
              <Col xs={24} sm={12} md={4}>
                <Select
                  value={typeFilter}
                  onChange={setTypeFilter}
                  style={{ width: '100%' }}
                  placeholder="资源类型"
                >
                  <Option value="all">全部类型</Option>
                  <Option value="human">用户</Option>
                  <Option value="agent">Agent</Option>
                </Select>
              </Col>
              <Col xs={24} sm={12} md={4}>
                <Select
                  value={statusFilter}
                  onChange={setStatusFilter}
                  style={{ width: '100%' }}
                  placeholder="状态"
                >
                  <Option value="all">全部状态</Option>
                  <Option value="online">在线</Option>
                  <Option value="offline">离线</Option>
                  <Option value="busy">忙碌</Option>
                </Select>
              </Col>
              <Col xs={24} sm={12} md={8}>
                <Button
                  type="primary"
                  icon={<ReloadOutlined />}
                  onClick={loadResources}
                  loading={loading}
                  style={{ marginRight: '8px' }}
                >
                  刷新
                </Button>
                <Button
                  icon={<FilterOutlined />}
                  onClick={() => {
                    setSearchText('');
                    setTypeFilter('all');
                    setStatusFilter('all');
                  }}
                >
                  重置过滤
                </Button>
              </Col>
            </Row>
          </div>

          {/* 资源列表 */}
          <div>
            <Title level={4} style={{ marginBottom: '16px' }}>
              资源列表 ({filteredResources.length})
            </Title>
            {filteredResources.length > 0 ? (
              <List
                grid={{ gutter: 16, xs: 1, sm: 2, md: 2, lg: 3, xl: 4, xxl: 4 }}
                dataSource={filteredResources.filter(r => !!r && typeof r === 'object')}
                renderItem={(resource) => {
                  if (!resource) return null;
                  const safeCapabilities = Array.isArray(resource.capabilities) ? resource.capabilities : [];
                  return (
                    <List.Item>
                      <Card
                        hoverable
                        style={{ 
                          height: '200px',
                          border: `2px solid ${resource.status === 'online' ? '#f6ffed' : '#fff2e8'}`,
                          overflow: 'hidden'
                        }}
                        styles={{
                          body: {
                            padding: '16px',
                            height: '100%',
                            display: 'flex',
                            flexDirection: 'column',
                            overflow: 'hidden'
                          }
                        }}
                        actions={resource.type === 'agent' ? [
                          <Tooltip title="查看详情">
                            <EyeOutlined onClick={() => handleViewAgent(resource)} />
                          </Tooltip>,
                          <Tooltip title="绑定工具">
                            <SettingOutlined onClick={() => handleBindTools(resource)} />
                          </Tooltip>
                        ] : []}
                      >
                        <List.Item.Meta
                          avatar={
                            <Avatar 
                              size={48}
                              icon={getResourceIcon(resource.type)}
                              style={{ backgroundColor: getResourceColor(resource.type) }}
                            />
                          }
                          title={
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 'bold' }}>{resource.name}</span>
                              <Tag color={getStatusColor(resource.status)}>
                                {getStatusText(resource.status)}
                              </Tag>
                            </div>
                          }
                          description={
                            <div style={{ height: '100px', overflow: 'hidden' }}>
                              <div style={{ 
                                marginBottom: '8px',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                lineHeight: '1.4',
                                maxHeight: '2.8em',
                                minHeight: '2.8em'
                              }}>
                                <Text type="secondary" title={resource.description}>
                                  {resource.description || '暂无描述'}
                                </Text>
                              </div>
                              <div style={{ marginBottom: '8px' }}>
                                <Text strong>类型: </Text>
                                <Tag color={resource.type === 'human' ? 'blue' : 'purple'}>
                                  {resource.type === 'human' ? '用户' : 'Agent'}
                                </Tag>
                              </div>
                              {safeCapabilities.length > 0 && (
                                <div style={{ 
                                  overflow: 'hidden',
                                  maxHeight: '32px'
                                }}>
                                  <Text strong>能力: </Text>
                                  <div style={{ 
                                    marginTop: '4px',
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    gap: '4px',
                                    overflow: 'hidden'
                                  }}>
                                    {safeCapabilities.slice(0, 2).map((cap: string, index: number) => (
                                      <Tag 
                                        key={index} 
                                        style={{ 
                                          marginBottom: '0',
                                          maxWidth: '60px',
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          whiteSpace: 'nowrap',
                                          fontSize: '12px'
                                        }}
                                        title={cap}
                                      >
                                        {cap}
                                      </Tag>
                                    ))}
                                    {safeCapabilities.length > 2 && (
                                      <Tag style={{ marginBottom: '0', fontSize: '12px' }}>
                                        +{safeCapabilities.length - 2}
                                      </Tag>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>
                          }
                        />
                      </Card>
                    </List.Item>
                  );
                }}
              />
            ) : (
              <Empty
                description="暂无资源"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            )}
          </div>
        </div>
      )
    },
    {
      key: 'agents',
      label: <span><RobotOutlined />Agent管理</span>,
      children: (
        <Table
          loading={loading}
          columns={[
            {
              title: 'Agent名称',
              dataIndex: 'name',
              key: 'name',
              render: (text: string, record: ResourceItem) => (
                <div>
                  <div style={{ fontWeight: 'bold' }}>
                    <RobotOutlined style={{ marginRight: '8px', color: '#722ed1' }} />
                    {text}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>{record.description}</div>
                </div>
              )
            },
            {
              title: '类型',
              dataIndex: 'agent_type',
              key: 'agent_type',
              width: 100,
              render: (type: string) => (
                <Tag color={type === 'custom' ? 'blue' : 'green'}>
                  {type === 'custom' ? '自定义' : '导入'}
                </Tag>
              )
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              width: 100,
              render: (status: string) => (
                <Tag color={getStatusColor(status)}>
                  {getStatusText(status)}
                </Tag>
              )
            },
            {
              title: '能力',
              dataIndex: 'capabilities',
              key: 'capabilities',
              render: (capabilities: string[]) => (
                <div>
                  {(Array.isArray(capabilities) ? capabilities : []).slice(0, 2).map((capability, index) => (
                    <Tag key={index} style={{ marginBottom: '4px' }}>
                      {capability}
                    </Tag>
                  ))}
                  {capabilities && capabilities.length > 2 && (
                    <Tag>+{capabilities.length - 2}</Tag>
                  )}
                </div>
              )
            },
            {
              title: '工具',
              dataIndex: 'tools',
              key: 'tools',
              render: (tools: string[]) => (
                <div>
                  {(Array.isArray(tools) ? tools : []).slice(0, 2).map((tool, index) => (
                    <Tag key={index} color="purple" style={{ marginBottom: '4px' }}>
                      <ToolOutlined style={{ marginRight: '4px' }} />
                      {tool}
                    </Tag>
                  ))}
                  {tools && tools.length > 2 && (
                    <Tag color="purple">+{tools.length - 2}</Tag>
                  )}
                </div>
              )
            },
            {
              title: '创建时间',
              dataIndex: 'created_at',
              key: 'created_at',
              width: 120,
              render: (date: string) => date ? new Date(date).toLocaleDateString() : '-'
            },
            {
              title: '操作',
              key: 'action',
              width: 220,
              render: (text: string, record: ResourceItem) => (
                <Space>
                  <Tooltip title="查看详情">
                    <Button 
                      type="link" 
                      size="small" 
                      icon={<EyeOutlined />}
                      onClick={() => handleViewAgent(record)}
                    />
                  </Tooltip>
                  <Tooltip title="编辑Agent">
                    <Button 
                      type="link" 
                      size="small" 
                      icon={<EditOutlined />}
                      onClick={() => handleEditAgent(record)}
                    />
                  </Tooltip>
                  <Tooltip title="绑定工具">
                    <Button 
                      type="link" 
                      size="small" 
                      icon={<SettingOutlined />}
                      onClick={() => handleBindTools(record)}
                    />
                  </Tooltip>
                  <Tooltip title="删除Agent">
                    <Button 
                      type="link" 
                      size="small" 
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleDeleteAgent(record)}
                    />
                  </Tooltip>
                </Space>
              )
            }
          ]}
          dataSource={agentList}
          rowKey="id"
          pagination={{
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条/共 ${total} 条`
          }}
        />
      )
    },
    {
      key: 'processors',
      label: <span><ToolOutlined />Processor管理</span>,
      children: (
        <Table
          loading={loading}
          columns={[
            {
              title: 'Processor名称',
              dataIndex: 'name',
              key: 'name',
              render: (text: string, record: any) => (
                <div>
                  <div style={{ fontWeight: 'bold' }}>
                    <ToolOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
                    {text}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666' }}>
                    版本: v{record.version}
                  </div>
                </div>
              )
            },
            {
              title: '类型',
              dataIndex: 'type',
              key: 'type',
              width: 100,
              render: (type: string) => {
                const typeConfig = {
                  human: { color: 'blue', text: '用户' },
                  agent: { color: 'purple', text: 'Agent' },
                  mix: { color: 'orange', text: '混合' }
                };
                const config = typeConfig[type as keyof typeof typeConfig] || { color: 'default', text: type };
                return (
                  <Tag color={config.color}>
                    {config.text}
                  </Tag>
                );
              }
            },
            {
              title: '关联用户',
              key: 'user_info',
              render: (text: string, record: any) => (
                record.user_id ? (
                  <div>
                    <div>{record.username || 'Unknown'}</div>
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      {record.user_email || ''}
                    </div>
                  </div>
                ) : '-'
              )
            },
            {
              title: '关联Agent',
              key: 'agent_info',
              render: (text: string, record: any) => (
                record.agent_id ? (
                  <div>
                    <div>{record.agent_name || 'Unknown'}</div>
                    <div style={{ fontSize: '12px', color: '#666' }}>
                      {record.agent_description || ''}
                    </div>
                  </div>
                ) : '-'
              )
            },
            {
              title: '创建时间',
              dataIndex: 'created_at',
              key: 'created_at',
              width: 120,
              render: (date: string) => date ? new Date(date).toLocaleDateString() : '-'
            },
            {
              title: '操作',
              key: 'action',
              width: 100,
              render: (text: string, record: any) => (
                <Space>
                  <Tooltip title="删除处理器">
                    <Button 
                      type="link" 
                      size="small" 
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('Delete button clicked, record:', record);
                        handleDeleteProcessor(record);
                      }}
                    />
                  </Tooltip>
                </Space>
              )
            }
          ]}
          dataSource={processors}
          rowKey="processor_id"
          pagination={{
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条/共 ${total} 条`
          }}
        />
      )
    },
    {
      key: 'tools',
      label: <span><ToolOutlined />我的工具</span>,
      children: (
        <MCPToolsManagement onToolsUpdate={loadResources} />
      )
    }
  ], [searchText, typeFilter, statusFilter, filteredResources, loading, agentList, processors, loadResources, handleViewAgent, handleBindTools, handleEditAgent, handleDeleteAgent, handleDeleteProcessor, getResourceIcon, getResourceColor, getStatusColor, getStatusText]);


  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: '24px' }}>
        <Title level={2} style={{ marginBottom: '8px' }}>
          <TeamOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
          资源管理
        </Title>
        <Text type="secondary">管理和监控系统中的用户和Agent资源</Text>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总资源"
              value={stats.total}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="在线资源"
              value={stats.online}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="用户"
              value={stats.humans}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Agent"
              value={stats.agents}
              prefix={<RobotOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 标签页内容 */}
      <Card>
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab}
          items={tabItems}
          tabBarExtraContent={
            activeTab === 'agents' ? (
              <Space>
                <Button 
                  type="default" 
                  icon={<UploadOutlined />}
                  onClick={handleImportAgent}
                  size="small"
                >
                  导入Agent
                </Button>
                <Button 
                  type="primary" 
                  onClick={handleCreateAgent}
                  size="small"
                >
                  创建Agent
                </Button>
              </Space>
            ) : activeTab === 'processors' ? (
              <Button 
                type="primary" 
                icon={<ToolOutlined />}
                onClick={handleCreateProcessor}
                size="small"
              >
                创建Processor
              </Button>
            ) : null
          }
        />
      </Card>

      {/* 导入Agent模态框 */}
      <Modal
        title="导入Agent"
        open={importModalVisible}
        onOk={handleImportConfirm}
        onCancel={() => setImportModalVisible(false)}
        width={600}
      >
        <Form form={importForm} layout="vertical">
          <Form.Item
            name="agentFile"
            label="Agent配置文件"
            rules={[{ required: true, message: '请选择Agent配置文件' }]}
          >
            <Upload.Dragger
              name="file"
              multiple={false}
              accept=".json,.yaml,.yml"
              beforeUpload={() => false}
            >
              <p className="ant-upload-drag-icon">
                <UploadOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">支持 JSON、YAML 格式的Agent配置文件</p>
            </Upload.Dragger>
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea rows={3} placeholder="请输入Agent描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 绑定工具模态框 */}
      <Modal
        title={`为 ${selectedAgent?.name} 绑定工具`}
        open={toolModalVisible}
        onOk={handleBindToolsConfirm}
        onCancel={() => setToolModalVisible(false)}
        width={1000}
        okText="保存绑定"
        cancelText="取消"
      >
        <AgentToolSelector
          agentId={selectedAgent?.id}
          mode="edit"
        />
      </Modal>

      {/* Agent详情模态框 */}
      <Modal
        title={`Agent详情 - ${selectedAgent?.name}`}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {selectedAgent && (
          <div>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="Agent名称">{selectedAgent.name}</Descriptions.Item>
              <Descriptions.Item label="Agent类型">
                <Tag color={selectedAgent.agent_type === 'custom' ? 'blue' : 'green'}>
                  {selectedAgent.agent_type === 'custom' ? '自定义' : '导入'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={getStatusColor(selectedAgent.status)}>
                  {getStatusText(selectedAgent.status)}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {selectedAgent.created_at ? new Date(selectedAgent.created_at).toLocaleString() : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="最后使用" span={2}>
                {selectedAgent.last_used ? new Date(selectedAgent.last_used).toLocaleString() : '从未使用'}
              </Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>
                {selectedAgent.description || '暂无描述'}
              </Descriptions.Item>
            </Descriptions>
            
            <Divider orientation="left">能力</Divider>
            <div>
              {selectedAgent.capabilities && selectedAgent.capabilities.length > 0 ? (
                selectedAgent.capabilities.map((capability, index) => (
                  <Tag key={index} style={{ marginBottom: '8px' }}>
                    {capability}
                  </Tag>
                ))
              ) : (
                <Text type="secondary">暂无能力标签</Text>
              )}
            </div>
            
            <Divider orientation="left">绑定工具</Divider>
            <div>
              {selectedAgent.tools && selectedAgent.tools.length > 0 ? (
                selectedAgent.tools.map((tool, index) => (
                  <Tag key={index} color="purple" style={{ marginBottom: '8px' }}>
                    <ToolOutlined style={{ marginRight: '4px' }} />
                    {tool}
                  </Tag>
                ))
              ) : (
                <Text type="secondary">未绑定任何工具</Text>
              )}
            </div>
            
            {selectedAgent.config && (
              <div>
                <Divider orientation="left">配置信息</Divider>
                <pre style={{ 
                  background: '#f5f5f5', 
                  padding: '12px', 
                  borderRadius: '4px',
                  maxHeight: '200px',
                  overflow: 'auto'
                }}>
                  {JSON.stringify(selectedAgent.config, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 编辑Agent模态框 */}
      <Modal
        title={`编辑Agent - ${selectedAgent?.name}`}
        open={editModalVisible}
        onOk={handleEditConfirm}
        onCancel={() => setEditModalVisible(false)}
        width={800}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="name"
            label="Agent名称"
            rules={[
              { required: true, message: '请输入Agent名称' },
              { min: 2, message: '名称至少2个字符' }
            ]}
          >
            <Input placeholder="请输入Agent名称" />
          </Form.Item>
          
          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea 
              rows={3} 
              placeholder="请输入Agent描述（可选）" 
            />
          </Form.Item>
          
          <Form.Item
            name="capabilities"
            label="能力标签"
          >
            <Select
              mode="tags"
              placeholder="请输入能力标签，按回车添加"
              style={{ width: '100%' }}
              open={false}
            />
          </Form.Item>
          
          <Form.Item
            name="config"
            label="配置信息"
          >
            <TextArea 
              rows={6} 
              placeholder="请输入JSON格式的配置信息（可选）" 
            />
          </Form.Item>
          
          {/* 工具绑定编辑器 */}
          <Form.Item
            label="工具绑定"
            help="管理Agent可使用的MCP工具"
          >
            <AgentToolSelector
              agentId={selectedAgent?.id}
              value={editToolBindings}
              onChange={setEditToolBindings}
              mode="edit"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 创建Processor模态框 */}
      <Modal
        title="创建Processor"
        open={createProcessorModalVisible}
        onOk={handleCreateProcessorConfirm}
        onCancel={() => setCreateProcessorModalVisible(false)}
        width={600}
      >
        <Form form={createProcessorForm} layout="vertical">
          <Form.Item
            name="name"
            label="Processor名称"
            rules={[
              { required: true, message: '请输入Processor名称' },
              { min: 2, message: '名称至少2个字符' }
            ]}
          >
            <Input placeholder="请输入Processor名称" />
          </Form.Item>
          
          <Form.Item
            name="type"
            label="处理器类型"
            rules={[{ required: true, message: '请选择处理器类型' }]}
          >
            <Select placeholder="请选择处理器类型">
              <Option value="human">用户处理器</Option>
              <Option value="agent">Agent处理器</Option>
              <Option value="mix">混合处理器</Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => 
              prevValues.type !== currentValues.type
            }
          >
            {({ getFieldValue }) => {
              const processorType = getFieldValue('type');
              
              return (
                <>
                  {(processorType === 'human' || processorType === 'mix') && (
                    <Form.Item
                      name="user_id"
                      label="关联用户"
                      rules={processorType === 'human' || processorType === 'mix' ? [{ required: true, message: '请选择关联用户' }] : []}
                    >
                      <Select 
                        placeholder="请选择关联用户"
                        showSearch
                        filterOption={(input, option) =>
                          String(option?.children || '').toLowerCase().includes(input.toLowerCase())
                        }
                      >
                        {resources
                          .filter(r => r.type === 'human')
                          .map(user => (
                            <Option key={user.id} value={user.id}>
                              {user.name} ({user.description})
                            </Option>
                          ))
                        }
                      </Select>
                    </Form.Item>
                  )}

                  {(processorType === 'agent' || processorType === 'mix') && (
                    <Form.Item
                      name="agent_id"
                      label="关联Agent"
                      rules={processorType === 'agent' || processorType === 'mix' ? [{ required: true, message: '请选择关联Agent' }] : []}
                    >
                      <Select 
                        placeholder="请选择关联Agent"
                        showSearch
                        filterOption={(input, option) =>
                          String(option?.children || '').toLowerCase().includes(input.toLowerCase())
                        }
                      >
                        {resources
                          .filter(r => r.type === 'agent')
                          .map(agent => (
                            <Option key={agent.id} value={agent.id}>
                              {agent.name} ({agent.description})
                            </Option>
                          ))
                        }
                      </Select>
                    </Form.Item>
                  )}
                </>
              );
            }}
          </Form.Item>
        </Form>
      </Modal>

      {/* 删除Processor确认模态框 */}
      <Modal
        title="确认删除处理器"
        open={deleteProcessorModalVisible}
        onOk={handleDeleteProcessorConfirm}
        onCancel={handleDeleteProcessorCancel}
        okText="确认删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
        width={500}
      >
        <div>
          <p>确定要删除处理器 <strong>"{processorToDelete?.name}"</strong> 吗？</p>
          <p style={{ color: '#ff4d4f', marginBottom: 0 }}>
            <ExclamationCircleOutlined style={{ marginRight: '8px' }} />
            此操作不可撤销，请谨慎操作。
          </p>
        </div>
      </Modal>

      {/* 删除Agent确认模态框 */}
      <Modal
        title="确认删除Agent"
        open={deleteAgentModalVisible}
        onOk={confirmDeleteAgent}
        onCancel={cancelDeleteAgent}
        okText="确认删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
        width={500}
      >
        <div>
          <p>确定要删除Agent <strong>"{agentToDelete?.name}"</strong> 吗？</p>
          <p style={{ color: '#ff4d4f', marginBottom: 0 }}>
            <ExclamationCircleOutlined style={{ marginRight: '8px' }} />
            此操作不可撤销，请谨慎操作。
          </p>
        </div>
      </Modal>

      {/* 创建Agent模态框 */}
      <Modal
        title="创建新Agent"
        open={createAgentModalVisible}
        onOk={confirmCreateAgent}
        onCancel={cancelCreateAgent}
        okText="创建Agent"
        cancelText="取消"
        width={600}
        destroyOnHidden
      >
        <Form
          form={createAgentForm}
          layout="vertical"
          requiredMark={false}
        >
          <Form.Item
            name="agent_name"
            label="Agent名称"
            rules={[
              { required: true, message: '请输入Agent名称' },
              { min: 1, max: 255, message: 'Agent名称长度应在1-255字符之间' }
            ]}
          >
            <Input placeholder="请输入Agent名称，如：GPT-4助手" />
          </Form.Item>

          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea 
              rows={3} 
              placeholder="请输入Agent的描述信息"
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="base_url"
                label="基础URL"
              >
                <Input placeholder="如：https://api.openai.com/v1" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="model_name"
                label="模型名称"
              >
                <Input placeholder="如：gpt-4, gpt-3.5-turbo" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="api_key"
            label="API密钥"
          >
            <Input.Password placeholder="请输入API密钥" />
          </Form.Item>

          <Form.Item
            name="tool_config"
            label="工具配置"
            help="JSON格式的工具配置，例如：{&quot;tools&quot;: [&quot;calculator&quot;, &quot;search&quot;]}"
          >
            <TextArea 
              rows={3} 
              placeholder='{"tools": ["calculator", "search"]}'
            />
          </Form.Item>

          {/* 新的工具绑定选择器 */}
          <Form.Item
            label="工具绑定"
            help="选择并配置Agent可使用的MCP工具"
          >
            <AgentToolSelector
              value={toolBindings}
              onChange={setToolBindings}
              mode="create"
            />
          </Form.Item>

          <Form.Item
            name="parameters"
            label="参数配置"
            help="JSON格式的参数配置，例如：{&quot;temperature&quot;: 0.7, &quot;max_tokens&quot;: 1000}"
          >
            <TextArea 
              rows={3} 
              placeholder='{"temperature": 0.7, "max_tokens": 1000}'
            />
          </Form.Item>

          <Form.Item
            name="is_autonomous"
            valuePropName="checked"
          >
            <Checkbox>允许Agent自主执行任务</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default React.memo(Resource);