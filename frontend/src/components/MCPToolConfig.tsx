import React, { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Select,
  Switch,
  InputNumber,
  Button,
  Space,
  Table,
  Modal,
  Input,
  Tag,
  Divider,
  Alert,
  Tabs,
  Row,
  Col,
  Typography,
  message,
  Tooltip,
  Badge,
  List,
  Empty
} from 'antd';
import {
  SettingOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { mcpAPI } from '../services/api';

// API response interfaces
interface ApiResponse<T = any> {
  success: boolean;
  data: T;
  message?: string;
}

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;

interface MCPServer {
  name: string;
  url: string;
  capabilities: string[];
  auth: {
    type: 'none' | 'bearer' | 'api_key' | 'basic';
    token?: string;
    key?: string;
    username?: string;
    password?: string;
  };
  timeout: number;
  enabled: boolean;
}

interface MCPTool {
  name: string;
  description: string;
  server_name: string;
  parameters?: any;
}

interface MCPToolConfigProps {
  agentId: string;
  onConfigUpdated: () => void;
}

const MCPToolConfig: React.FC<MCPToolConfigProps> = ({ agentId, onConfigUpdated }) => {
  // 状态管理
  const [loading, setLoading] = useState(false);
  const [serverModalVisible, setServerModalVisible] = useState(false);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [currentServer, setCurrentServer] = useState<MCPServer | null>(null);
  const [form] = Form.useForm();
  const [testForm] = Form.useForm();
  
  // 数据状态
  const [toolConfig, setToolConfig] = useState<any>({
    mcp_servers: [],
    tool_selection: 'auto',
    max_tool_calls: 5,
    timeout: 60,
    allowed_tools: [],
    blocked_tools: []
  });
  
  const [availableTools, setAvailableTools] = useState<MCPTool[]>([]);
  const [serverStatuses, setServerStatuses] = useState<Record<string, any>>({});

  // 加载配置数据
  useEffect(() => {
    loadToolConfig();
    loadAvailableTools();
  }, [agentId]);

  const loadToolConfig = async () => {
    setLoading(true);
    try {
      const response = await mcpAPI.getAgentToolConfig(agentId);
      if (response && response.data) {
        setToolConfig(response.data);
        // 加载服务器状态
        await loadServerStatuses((response.data as any)?.mcp_servers || []);
      }
    } catch (error) {
      console.error('加载工具配置失败:', error);
      message.error('加载工具配置失败');
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableTools = async () => {
    try {
      const response = await mcpAPI.getAgentTools(agentId);
      if (response && response.data?.tools) {
        setAvailableTools(response.data.tools);
      }
    } catch (error) {
      console.error('加载可用工具失败:', error);
    }
  };

  const loadServerStatuses = async (servers: MCPServer[]) => {
    const statuses: Record<string, any> = {};
    
    for (const server of servers) {
      try {
        const response = await mcpAPI.getServerStatus(server.name);
        if (response && response.data) {
          statuses[server.name] = response.data;
        } else {
          statuses[server.name] = { status: 'unknown', error: 'No response data' };
        }
      } catch (error: any) {
        statuses[server.name] = { status: 'error', error: error.message };
      }
    }
    
    setServerStatuses(statuses);
  };

  // 保存工具配置
  const saveToolConfig = async (newConfig: any) => {
    try {
      await mcpAPI.updateAgentToolConfig(agentId, newConfig);
      setToolConfig(newConfig);
      message.success('工具配置保存成功');
      onConfigUpdated();
      // 重新加载工具和状态
      await loadAvailableTools();
      await loadServerStatuses(newConfig.mcp_servers || []);
    } catch (error: any) {
      console.error('保存工具配置失败:', error);
      message.error(error.message || '保存工具配置失败');
    }
  };

  // 添加/编辑服务器
  const handleServerSubmit = async (values: any) => {
    const serverData: MCPServer = {
      name: values.name,
      url: values.url,
      capabilities: values.capabilities || [],
      auth: {
        type: values.auth_type,
        token: values.auth_token,
        key: values.auth_key,
        username: values.auth_username,
        password: values.auth_password
      },
      timeout: values.timeout || 30,
      enabled: values.enabled !== false
    };

    const updatedServers = currentServer
      ? toolConfig.mcp_servers.map((s: MCPServer) => 
          s.name === currentServer.name ? serverData : s
        )
      : [...(toolConfig.mcp_servers || []), serverData];

    const newConfig = { ...toolConfig, mcp_servers: updatedServers };
    await saveToolConfig(newConfig);
    
    setServerModalVisible(false);
    setCurrentServer(null);
    form.resetFields();
  };

  // 删除服务器
  const handleDeleteServer = (serverName: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除MCP服务器 "${serverName}" 吗？`,
      onOk: async () => {
        const updatedServers = toolConfig.mcp_servers.filter(
          (s: MCPServer) => s.name !== serverName
        );
        const newConfig = { ...toolConfig, mcp_servers: updatedServers };
        await saveToolConfig(newConfig);
      }
    });
  };

  // 测试工具
  const handleTestTool = async (values: any) => {
    try {
      const response = await mcpAPI.callMCPTool({
        tool_name: values.tool_name,
        server_name: values.server_name,
        arguments: JSON.parse(values.arguments || '{}')
      });
      
      // Response is already processed by axios interceptor
      message.success('工具调用成功');
      Modal.info({
        title: '工具调用结果',
        content: (
          <div>
            <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px' }}>
              {JSON.stringify(response, null, 2)}
            </pre>
          </div>
        ),
        width: 600
      });
    } catch (error: any) {
      message.error(`工具调用失败: ${error.message}`);
    }
  };

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'unhealthy':
        return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
      case 'error':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
    }
  };

  // 服务器表格列定义
  const serverColumns = [
    {
      title: '服务器名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <DatabaseOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
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
      key: 'status',
      width: 100,
      render: (_: any, record: MCPServer) => {
        const status = serverStatuses[record.name];
        const statusText = status?.status || 'unknown';
        return (
          <Tooltip title={status?.error || '状态正常'}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              {getStatusIcon(statusText)}
              <span style={{ marginLeft: '4px', fontSize: '12px' }}>
                {statusText === 'healthy' ? '正常' : 
                 statusText === 'unhealthy' ? '异常' : 
                 statusText === 'error' ? '错误' : '未知'}
              </span>
            </div>
          </Tooltip>
        );
      }
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (enabled: boolean, record: MCPServer) => (
        <Switch 
          checked={enabled} 
          size="small"
          onChange={(checked) => {
            const updatedServers = toolConfig.mcp_servers.map((s: MCPServer) => 
              s.name === record.name ? { ...s, enabled: checked } : s
            );
            saveToolConfig({ ...toolConfig, mcp_servers: updatedServers });
          }}
        />
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: MCPServer) => (
        <Space size="small">
          <Tooltip title="编辑服务器">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                setCurrentServer(record);
                form.setFieldsValue({
                  name: record.name,
                  url: record.url,
                  capabilities: record.capabilities,
                  auth_type: record.auth.type,
                  auth_token: record.auth.token,
                  auth_key: record.auth.key,
                  auth_username: record.auth.username,
                  auth_password: record.auth.password,
                  timeout: record.timeout,
                  enabled: record.enabled
                });
                setServerModalVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="删除服务器">
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => handleDeleteServer(record.name)}
            />
          </Tooltip>
        </Space>
      )
    }
  ];

  // 工具表格列定义  
  const toolColumns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <ToolOutlined style={{ marginRight: '8px', color: '#722ed1' }} />
          <span style={{ fontWeight: 'bold' }}>{text}</span>
        </div>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => (
        <Text ellipsis style={{ maxWidth: '200px' }}>{text || '无描述'}</Text>
      )
    },
    {
      title: '服务器',
      dataIndex: 'server_name',
      key: 'server_name',
      render: (text: string) => (
        <Tag color="blue">{text}</Tag>
      )
    },
    {
      title: '状态',
      key: 'tool_status',
      render: (_: any, record: MCPTool) => {
        const isAllowed = toolConfig.allowed_tools.length === 0 || 
                         toolConfig.allowed_tools.includes(record.name);
        const isBlocked = toolConfig.blocked_tools.includes(record.name);
        
        if (isBlocked) {
          return <Tag color="red">已禁用</Tag>;
        } else if (isAllowed) {
          return <Tag color="green">可用</Tag>;
        } else {
          return <Tag color="orange">受限</Tag>;
        }
      }
    }
  ];

  return (
    <div>
      <Alert
        message="MCP工具配置"
        description="配置Model Context Protocol工具服务器，为Agent提供外部工具调用能力。请确保MCP服务器正常运行。"
        type="info"
        showIcon
        style={{ marginBottom: '16px' }}
      />

      <Tabs
        defaultActiveKey="servers"
        items={[
          {
            key: 'servers',
            label: (
              <span>
                <DatabaseOutlined />
                MCP服务器 ({toolConfig.mcp_servers?.length || 0})
              </span>
            ),
            children: (
              <div>
                <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                  <div>
                    <Text strong>配置的MCP服务器</Text>
                  </div>
                  <Space>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={() => {
                        loadToolConfig();
                        loadAvailableTools();
                      }}
                    >
                      刷新状态
                    </Button>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => {
                        setCurrentServer(null);
                        form.resetFields();
                        setServerModalVisible(true);
                      }}
                    >
                      添加服务器
                    </Button>
                  </Space>
                </div>

                <Table
                  columns={serverColumns}
                  dataSource={toolConfig.mcp_servers}
                  rowKey="name"
                  size="small"
                  pagination={false}
                  loading={loading}
                />
              </div>
            )
          },
          {
            key: 'tools',
            label: (
              <span>
                <ToolOutlined />
                可用工具 ({availableTools.length})
              </span>
            ),
            children: (
              <div>
                <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                  <div>
                    <Text strong>发现的工具</Text>
                    <Text type="secondary" style={{ marginLeft: '8px' }}>
                      来自配置的MCP服务器
                    </Text>
                  </div>
                  <Space>
                    <Button
                      icon={<ExperimentOutlined />}
                      onClick={() => {
                        testForm.resetFields();
                        setTestModalVisible(true);
                      }}
                    >
                      测试工具
                    </Button>
                  </Space>
                </div>

                <Table
                  columns={toolColumns}
                  dataSource={availableTools}
                  rowKey="name"
                  size="small"
                  pagination={false}
                />
              </div>
            )
          },
          {
            key: 'settings',
            label: (
              <span>
                <SettingOutlined />
                高级设置
              </span>
            ),
            children: (
              <Card size="small">
                <Form
                  layout="vertical"
                  initialValues={toolConfig}
                  onValuesChange={(changedValues, allValues) => {
                    const newConfig = { ...toolConfig, ...allValues };
                    saveToolConfig(newConfig);
                  }}
                >
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="tool_selection"
                        label="工具选择模式"
                      >
                        <Select>
                          <Option value="auto">自动选择</Option>
                          <Option value="manual">手动选择</Option>
                          <Option value="disabled">禁用工具</Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="max_tool_calls"
                        label="最大工具调用次数"
                      >
                        <InputNumber min={1} max={20} />
                      </Form.Item>
                    </Col>
                  </Row>
                  
                  <Form.Item
                    name="timeout"
                    label="工具调用超时时间(秒)"
                  >
                    <InputNumber min={10} max={300} />
                  </Form.Item>
                  
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="allowed_tools"
                        label="允许的工具"
                      >
                        <Select
                          mode="multiple"
                          placeholder="留空表示允许所有工具"
                          allowClear
                        >
                          {availableTools.map(tool => (
                            <Option key={tool.name} value={tool.name}>
                              {tool.name}
                            </Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="blocked_tools"
                        label="禁用的工具"
                      >
                        <Select
                          mode="multiple"
                          placeholder="选择要禁用的工具"
                          allowClear
                        >
                          {availableTools.map(tool => (
                            <Option key={tool.name} value={tool.name}>
                              {tool.name}
                            </Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                  </Row>
                </Form>
              </Card>
            )
          }
        ]}
      />

      {/* 服务器配置模态框 */}
      <Modal
        title={currentServer ? '编辑MCP服务器' : '添加MCP服务器'}
        open={serverModalVisible}
        onCancel={() => {
          setServerModalVisible(false);
          setCurrentServer(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleServerSubmit}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="服务器名称"
                rules={[{ required: true, message: '请输入服务器名称' }]}
              >
                <Input placeholder="例如: filesystem" disabled={!!currentServer} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="url"
                label="服务器URL"
                rules={[{ required: true, message: '请输入服务器URL' }]}
              >
                <Input placeholder="http://localhost:3001" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="capabilities"
            label="服务器能力"
          >
            <Select
              mode="tags"
              placeholder="输入服务器提供的能力"
            />
          </Form.Item>

          <Divider>认证设置</Divider>

          <Form.Item
            name="auth_type"
            label="认证类型"
            initialValue="none"
          >
            <Select>
              <Option value="none">无认证</Option>
              <Option value="bearer">Bearer Token</Option>
              <Option value="api_key">API Key</Option>
              <Option value="basic">Basic认证</Option>
            </Select>
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.auth_type !== cur.auth_type}>
            {({ getFieldValue }) => {
              const authType = getFieldValue('auth_type');
              
              if (authType === 'bearer') {
                return (
                  <Form.Item name="auth_token" label="Bearer Token">
                    <Input.Password placeholder="输入Bearer Token" />
                  </Form.Item>
                );
              }
              
              if (authType === 'api_key') {
                return (
                  <Form.Item name="auth_key" label="API Key">
                    <Input.Password placeholder="输入API Key" />
                  </Form.Item>
                );
              }
              
              if (authType === 'basic') {
                return (
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name="auth_username" label="用户名">
                        <Input placeholder="输入用户名" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name="auth_password" label="密码">
                        <Input.Password placeholder="输入密码" />
                      </Form.Item>
                    </Col>
                  </Row>
                );
              }
              
              return null;
            }}
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="timeout"
                label="超时时间(秒)"
                initialValue={30}
              >
                <InputNumber min={5} max={120} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="enabled"
                label="启用"
                valuePropName="checked"
                initialValue={true}
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 工具测试模态框 */}
      <Modal
        title="测试MCP工具"
        open={testModalVisible}
        onCancel={() => {
          setTestModalVisible(false);
          testForm.resetFields();
        }}
        onOk={() => testForm.submit()}
        width={600}
      >
        <Form
          form={testForm}
          layout="vertical"
          onFinish={handleTestTool}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="tool_name"
                label="工具名称"
                rules={[{ required: true, message: '请选择工具' }]}
              >
                <Select placeholder="选择要测试的工具">
                  {availableTools.map(tool => (
                    <Option key={tool.name} value={tool.name}>
                      {tool.name} ({tool.server_name})
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="server_name"
                label="服务器名称"
                rules={[{ required: true, message: '请选择服务器' }]}
              >
                <Select placeholder="选择服务器">
                  {toolConfig.mcp_servers?.map((server: MCPServer) => (
                    <Option key={server.name} value={server.name}>
                      {server.name}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="arguments"
            label="工具参数 (JSON格式)"
          >
            <TextArea
              rows={6}
              placeholder='{"key": "value"}'
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default MCPToolConfig;