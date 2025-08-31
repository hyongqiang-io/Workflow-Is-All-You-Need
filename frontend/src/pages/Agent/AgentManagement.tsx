import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Button, 
  Table, 
  Space, 
  Modal, 
  Form, 
  Input, 
  Select, 
  Switch,
  Tag, 
  message,
  Drawer,
  Tabs,
  Row,
  Col,
  Typography,
  Divider,
  Tooltip,
  Alert,
  Badge
} from 'antd';
import { 
  PlusOutlined, 
  EditOutlined, 
  DeleteOutlined, 
  SettingOutlined,
  RobotOutlined,
  ToolOutlined,
  SafetyOutlined,
  ReloadOutlined,
  EyeOutlined,
  ExperimentOutlined,
  ExperimentFilled,
  DatabaseOutlined
} from '@ant-design/icons';
import { mcpAPI } from '../../services/api';
import MCPToolConfig from '../../components/MCPToolConfig';

// Placeholder API functions - to be implemented
const processorAPI = {
  getAgents: async () => ({ success: false, data: { agents: [] } }),
  updateAgent: async (agentId: string, data: any) => ({ success: false }),
  createAgent: async (data: any) => ({ success: false }),
  deleteAgent: async (agentId: string) => ({ success: false }),
};

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;
const { TabPane } = Tabs;

interface AgentData {
  agent_id: string;
  agent_name: string;
  description: string;
  model_name: string;
  base_url?: string;
  api_key?: string;
  tool_config?: any;
  parameters?: any;
  is_autonomous: boolean;
  created_at: string;
  updated_at: string;
  status?: string;
}

interface MCPServer {
  name: string;
  url: string;
  status: string;
  capabilities: string[];
  tools_cached: number;
}

const AgentManagement: React.FC = () => {
  // 状态管理
  const [agents, setAgents] = useState<AgentData[]>([]);
  const [mcpServers, setMCPServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [toolConfigVisible, setToolConfigVisible] = useState(false);
  const [testToolsVisible, setTestToolsVisible] = useState(false);
  const [currentAgent, setCurrentAgent] = useState<AgentData | null>(null);
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('agents');

  useEffect(() => {
    loadAgents();
    loadMCPServers();
  }, []);

  // 加载Agent列表
  const loadAgents = async () => {
    setLoading(true);
    try {
      const response = await processorAPI.getAgents();
      if (response.success && response.data?.agents) {
        setAgents(response.data.agents);
      } else {
        setAgents([]);
      }
    } catch (error) {
      console.error('加载Agent列表失败:', error);
      message.error('加载Agent列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载MCP服务器列表
  const loadMCPServers = async () => {
    try {
      const response = await mcpAPI.getMCPServers();
      // Response is processed by axios interceptor, data field is extracted
      if (response && (response as any).servers) {
        setMCPServers((response as any).servers);
      }
    } catch (error) {
      console.error('加载MCP服务器失败:', error);
    }
  };

  // 创建/编辑Agent
  const handleSubmit = async (values: any) => {
    try {
      const agentData = {
        agent_name: values.agent_name,
        description: values.description,
        model_name: values.model_name || 'gpt-3.5-turbo',
        base_url: values.base_url,
        api_key: values.api_key,
        parameters: {
          temperature: values.temperature || 0.7,
          max_tokens: values.max_tokens || 2000,
          ...values.parameters
        },
        is_autonomous: values.is_autonomous || false,
      };

      if (currentAgent) {
        // 更新Agent
        await processorAPI.updateAgent(currentAgent.agent_id, agentData);
        message.success('Agent更新成功');
      } else {
        // 创建Agent
        await processorAPI.createAgent(agentData);
        message.success('Agent创建成功');
      }

      setModalVisible(false);
      setCurrentAgent(null);
      form.resetFields();
      loadAgents();
    } catch (error: any) {
      console.error('保存Agent失败:', error);
      message.error(error.message || '保存Agent失败');
    }
  };

  // 删除Agent
  const handleDelete = async (agent: AgentData) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除Agent "${agent.agent_name}" 吗？此操作不可撤销。`,
      okText: '删除',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await processorAPI.deleteAgent(agent.agent_id);
          message.success('Agent删除成功');
          loadAgents();
        } catch (error: any) {
          console.error('删除Agent失败:', error);
          message.error(error.message || '删除Agent失败');
        }
      },
    });
  };

  // 编辑Agent
  const handleEdit = (agent: AgentData) => {
    setCurrentAgent(agent);
    form.setFieldsValue({
      agent_name: agent.agent_name,
      description: agent.description,
      model_name: agent.model_name,
      base_url: agent.base_url,
      api_key: agent.api_key,
      temperature: agent.parameters?.temperature || 0.7,
      max_tokens: agent.parameters?.max_tokens || 2000,
      is_autonomous: agent.is_autonomous,
    });
    setModalVisible(true);
  };

  // 配置工具
  const handleConfigureTools = (agent: AgentData) => {
    setCurrentAgent(agent);
    setToolConfigVisible(true);
  };

  // 测试工具
  const handleTestTools = (agent: AgentData) => {
    setCurrentAgent(agent);
    setTestToolsVisible(true);
  };

  // Agent表格列定义
  const agentColumns = [
    {
      title: 'Agent名称',
      dataIndex: 'agent_name',
      key: 'agent_name',
      render: (text: string, record: AgentData) => (
        <div>
          <div style={{ fontWeight: 'bold', fontSize: '14px', display: 'flex', alignItems: 'center' }}>
            <RobotOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
            {text}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
            {record.description || '暂无描述'}
          </div>
        </div>
      )
    },
    {
      title: '模型',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 150,
      render: (text: string) => (
        <Tag color="blue">{text}</Tag>
      )
    },
    {
      title: '工具配置',
      key: 'tools',
      width: 120,
      render: (_: any, record: AgentData) => {
        const toolConfig = record.tool_config || {};
        const serverCount = toolConfig.mcp_servers?.length || 0;
        const isEnabled = toolConfig.tool_selection !== 'disabled';
        
        return (
          <div>
            {serverCount > 0 ? (
              <Badge count={serverCount} size="small">
                <Tag color={isEnabled ? "green" : "orange"}>
                  <ToolOutlined /> {isEnabled ? '已配置' : '已禁用'}
                </Tag>
              </Badge>
            ) : (
              <Tag color="default">
                <ToolOutlined /> 未配置
              </Tag>
            )}
          </div>
        );
      }
    },
    {
      title: '状态',
      dataIndex: 'is_autonomous',
      key: 'status',
      width: 100,
      render: (isAutonomous: boolean) => (
        <Tag color={isAutonomous ? 'green' : 'blue'}>
          {isAutonomous ? '自主运行' : '按需执行'}
        </Tag>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (text: string) => (
        <span style={{ fontSize: '12px', color: '#666' }}>
          {text ? new Date(text).toLocaleString() : '-'}
        </span>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: AgentData) => (
        <Space size="small">
          <Tooltip title="编辑Agent">
            <Button 
              type="link" 
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            >
              编辑
            </Button>
          </Tooltip>
          <Tooltip title="配置工具">
            <Button 
              type="link" 
              size="small"
              icon={<SettingOutlined />}
              onClick={() => handleConfigureTools(record)}
            >
              工具配置
            </Button>
          </Tooltip>
          <Tooltip title="测试工具">
            <Button 
              type="link" 
              size="small"
              icon={<ExperimentFilled />}
              onClick={() => handleTestTools(record)}
            >
              测试
            </Button>
          </Tooltip>
          <Tooltip title="删除Agent">
            <Button 
              type="link" 
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDelete(record)}
            >
              删除
            </Button>
          </Tooltip>
        </Space>
      )
    }
  ];

  // MCP服务器表格列定义
  const serverColumns = [
    {
      title: '服务器名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <DatabaseOutlined style={{ marginRight: '8px', color: '#52c41a' }} />
          <span style={{ fontWeight: 'bold' }}>{text}</span>
        </div>
      )
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      render: (text: string) => (
        <Text code style={{ fontSize: '12px' }}>{text}</Text>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={status === 'healthy' ? 'green' : status === 'unhealthy' ? 'red' : 'orange'}>
          {status === 'healthy' ? '正常' : status === 'unhealthy' ? '异常' : '未知'}
        </Tag>
      )
    },
    {
      title: '能力',
      dataIndex: 'capabilities',
      key: 'capabilities',
      render: (capabilities: string[]) => (
        <div>
          {capabilities.slice(0, 3).map(cap => (
            <Tag key={cap}>{cap}</Tag>
          ))}
          {capabilities.length > 3 && (
            <Tag>+{capabilities.length - 3}</Tag>
          )}
        </div>
      )
    },
    {
      title: '缓存工具',
      dataIndex: 'tools_cached',
      key: 'tools_cached',
      width: 100,
      render: (count: number) => (
        <Badge count={count} size="small" />
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Title level={2} style={{ marginBottom: '8px' }}>
          <RobotOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
          Agent处理器管理
        </Title>
        <Paragraph type="secondary">
          管理AI Agent处理器，配置MCP工具集成，增强Agent的处理能力
        </Paragraph>
      </div>

      <Card>
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab}
          items={[
            {
              key: 'agents',
              label: (
                <span>
                  <RobotOutlined />
                  Agent管理 ({agents.length})
                </span>
              ),
              children: (
                <div>
                  <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <Text strong>Agent处理器列表</Text>
                      <Text type="secondary" style={{ marginLeft: '8px' }}>
                        共 {agents.length} 个Agent
                      </Text>
                    </div>
                    <Space>
                      <Button 
                        icon={<ReloadOutlined />} 
                        onClick={() => { loadAgents(); loadMCPServers(); }}
                        loading={loading}
                      >
                        刷新
                      </Button>
                      <Button 
                        type="primary" 
                        icon={<PlusOutlined />}
                        onClick={() => {
                          setCurrentAgent(null);
                          form.resetFields();
                          setModalVisible(true);
                        }}
                      >
                        创建Agent
                      </Button>
                    </Space>
                  </div>

                  <Table
                    columns={agentColumns}
                    dataSource={agents}
                    rowKey="agent_id"
                    loading={loading}
                    pagination={{
                      showSizeChanger: true,
                      showQuickJumper: true,
                      showTotal: (total, range) => 
                        `第 ${range[0]}-${range[1]} 条/共 ${total} 条`,
                    }}
                  />
                </div>
              )
            },
            {
              key: 'servers',
              label: (
                <span>
                  <DatabaseOutlined />
                  MCP服务器 ({mcpServers.length})
                </span>
              ),
              children: (
                <div>
                  <Alert
                    message="MCP服务器管理"
                    description="管理Model Context Protocol服务器，为Agent提供外部工具调用能力。添加和配置服务器后，可以在Agent工具配置中选择使用。"
                    type="info"
                    showIcon
                    style={{ marginBottom: '16px' }}
                  />

                  <Table
                    columns={serverColumns}
                    dataSource={mcpServers}
                    rowKey="name"
                    pagination={false}
                  />
                </div>
              )
            }
          ]}
        />
      </Card>

      {/* Agent创建/编辑模态框 */}
      <Modal
        title={currentAgent ? '编辑Agent' : '创建Agent'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          setCurrentAgent(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="agent_name"
                label="Agent名称"
                rules={[{ required: true, message: '请输入Agent名称' }]}
              >
                <Input placeholder="请输入Agent名称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="model_name"
                label="AI模型"
                rules={[{ required: true, message: '请选择AI模型' }]}
              >
                <Select placeholder="请选择AI模型">
                  <Option value="gpt-3.5-turbo">GPT-3.5 Turbo</Option>
                  <Option value="gpt-4">GPT-4</Option>
                  <Option value="gpt-4-turbo">GPT-4 Turbo</Option>
                  <Option value="claude-3-sonnet">Claude 3 Sonnet</Option>
                  <Option value="claude-3-opus">Claude 3 Opus</Option>
                  <Option value="Pro/deepseek-ai/DeepSeek-V3">DeepSeek V3</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="description"
            label="描述"
          >
            <TextArea rows={3} placeholder="请输入Agent描述" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="base_url"
                label="API Base URL"
              >
                <Input placeholder="https://api.openai.com/v1" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="api_key"
                label="API Key"
              >
                <Input.Password placeholder="请输入API密钥" />
              </Form.Item>
            </Col>
          </Row>

          <Divider>高级设置</Divider>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="temperature"
                label="Temperature"
              >
                <Select defaultValue={0.7}>
                  <Option value={0.1}>0.1 (更确定性)</Option>
                  <Option value={0.3}>0.3</Option>
                  <Option value={0.5}>0.5</Option>
                  <Option value={0.7}>0.7 (默认)</Option>
                  <Option value={0.9}>0.9</Option>
                  <Option value={1.0}>1.0 (更创造性)</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="max_tokens"
                label="最大Token数"
              >
                <Select defaultValue={2000}>
                  <Option value={1000}>1000</Option>
                  <Option value={2000}>2000</Option>
                  <Option value={4000}>4000</Option>
                  <Option value={8000}>8000</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="is_autonomous"
            label="运行模式"
            valuePropName="checked"
          >
            <Switch 
              checkedChildren="自主运行" 
              unCheckedChildren="按需执行" 
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* MCP工具配置抽屉 */}
      <Drawer
        title={
          <div>
            <ToolOutlined style={{ marginRight: '8px' }} />
            MCP工具配置 - {currentAgent?.agent_name}
          </div>
        }
        width={800}
        open={toolConfigVisible}
        onClose={() => {
          setToolConfigVisible(false);
          setCurrentAgent(null);
        }}
        extra={
          <Button onClick={() => loadAgents()}>
            <ReloadOutlined /> 刷新
          </Button>
        }
      >
        {currentAgent && (
          <MCPToolConfig 
            agentId={currentAgent.agent_id}
            onConfigUpdated={loadAgents}
          />
        )}
      </Drawer>

      {/* 工具测试抽屉 */}
      <Drawer
        title={
          <div>
            <ExperimentFilled style={{ marginRight: '8px' }} />
            工具测试 - {currentAgent?.agent_name}
          </div>
        }
        width={600}
        open={testToolsVisible}
        onClose={() => {
          setTestToolsVisible(false);
          setCurrentAgent(null);
        }}
      >
        {currentAgent && (
          <div>
            <Alert
              message="工具测试功能"
              description="在这里可以测试Agent配置的MCP工具，验证工具调用是否正常工作。"
              type="info"
              showIcon
              style={{ marginBottom: '16px' }}
            />
            <Text type="secondary">测试功能正在开发中...</Text>
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default AgentManagement;