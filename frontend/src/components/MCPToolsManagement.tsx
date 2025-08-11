import React, { useState, useEffect } from 'react';
import { 
  Card, Table, Button, message, Modal, Form, Input, Select, Tag, Space, 
  Tooltip, Popconfirm, Drawer, Typography, Divider, Row, Col, Statistic,
  Badge, Switch, InputNumber, Tabs, Descriptions
} from 'antd';
import { 
  PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined, PlayCircleOutlined,
  SettingOutlined, EyeOutlined, CodeOutlined, WarningOutlined, CheckCircleOutlined,
  ClockCircleOutlined, DisconnectOutlined, ApiOutlined, HeartOutlined
} from '@ant-design/icons';
import { mcpUserToolsAPI, agentToolsAPI } from '../services/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { TabPane } = Tabs;
const { Option } = Select;

interface MCPServer {
  server_name: string;
  server_url: string;
  server_description?: string;
  server_status: string;
  tools_count: number;
  total_usage_count: number;
  tools: MCPTool[];
}

interface MCPTool {
  tool_id: string;
  tool_name: string;
  tool_description?: string;
  tool_parameters: any;
  is_tool_active: boolean;
  tool_usage_count: number;
  success_rate: number;
  bound_agents_count: number;
  last_tool_call?: string;
  created_at?: string;
}

interface MCPToolsManagement {
  onToolsUpdate?: () => void;
}

const MCPToolsManagement: React.FC<MCPToolsManagement> = ({ onToolsUpdate }) => {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(false);
  const [addServerModalVisible, setAddServerModalVisible] = useState(false);
  const [editToolModalVisible, setEditToolModalVisible] = useState(false);
  const [testToolModalVisible, setTestToolModalVisible] = useState(false);
  const [toolDetailsDrawerVisible, setToolDetailsDrawerVisible] = useState(false);
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null);
  const [selectedServer, setSelectedServer] = useState<MCPServer | null>(null);
  const [authTypes, setAuthTypes] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({});

  const [addServerForm] = Form.useForm();
  const [editToolForm] = Form.useForm();
  const [testToolForm] = Form.useForm();

  // 加载数据
  const loadUserTools = async () => {
    setLoading(true);
    try {
      console.log('🔍 [FRONTEND-DEBUG] 开始加载用户工具');
      console.log('   - API调用: getUserTools()');
      
      const response = await mcpUserToolsAPI.getUserTools();
      
      console.log('📊 [FRONTEND-DEBUG] API响应接收');
      console.log('   - 响应对象:', response);
      console.log('   - response.success:', response?.success);
      console.log('   - response.message:', response?.message);
      console.log('   - response.data:', response?.data);
      
      // 修复：根据实际的响应数据结构处理
      if (response) {
        // 如果响应直接包含 servers 数组（拦截器已处理过的数据）
        const servers = response.servers || [];
        console.log('📋 [FRONTEND-DEBUG] 解析服务器数据');
        console.log('   - 服务器数量:', servers.length);
        console.log('   - 服务器列表:', servers);
        
        servers.forEach((server: MCPServer, index: number) => {
          console.log(`   - 服务器 ${index + 1}: ${server.server_name}`);
          console.log(`     * 工具数量: ${server.tools_count}`);
          console.log(`     * 工具列表长度: ${server.tools?.length || 0}`);
          console.log(`     * 服务器状态: ${server.server_status}`);
        });
        
        setServers(servers);
        console.log('✅ [FRONTEND-DEBUG] 服务器数据设置完成');
      } else {
        console.warn('⚠️ [FRONTEND-DEBUG] API响应数据为空或格式不正确');
        console.warn('   - response:', response);
        setServers([]);
      }
    } catch (error: any) {
      console.error('❌ [FRONTEND-DEBUG] 加载用户工具失败');
      console.error('   - 错误类型:', error.constructor.name);
      console.error('   - 错误信息:', error.message);
      console.error('   - 完整错误:', error);
      message.error(`加载工具失败: ${error.message}`);
    } finally {
      setLoading(false);
      console.log('🏁 [FRONTEND-DEBUG] loadUserTools 函数执行完成');
    }
  };

  // 加载统计信息
  const loadStats = async () => {
    try {
      console.log('📈 [FRONTEND-DEBUG] 开始加载统计信息');
      
      const response = await mcpUserToolsAPI.getUserToolStats();
      
      console.log('📈 [FRONTEND-DEBUG] 统计API响应');
      console.log('   - 响应对象:', response);
      console.log('   - response.overview:', response?.overview);
      
      if (response) {
        // 修复：根据实际的响应数据结构处理（拦截器已处理过）
        const overview = response.overview || response || {};
        console.log('📊 [FRONTEND-DEBUG] 设置统计数据');
        console.log('   - 工具总数:', overview.total_tools);
        console.log('   - 活跃工具:', overview.active_tools);
        console.log('   - 服务器数:', overview.total_servers);
        console.log('   - 总调用次数:', overview.total_usage_count);
        
        setStats(overview);
      }
    } catch (error: any) {
      console.error('❌ [FRONTEND-DEBUG] 加载统计信息失败:', error);
      message.error(`加载统计信息失败: ${error.message}`);
    }
  };

  // 加载认证类型
  const loadAuthTypes = async () => {
    try {
      console.log('🔒 [FRONTEND-DEBUG] 开始加载认证类型');
      
      const response = await mcpUserToolsAPI.getAuthTypes();
      
      console.log('🔒 [FRONTEND-DEBUG] 认证类型API响应');
      console.log('   - 响应对象:', response);
      console.log('   - response.auth_types:', response?.auth_types);
      
      if (response) {
        // 修复：根据实际的响应数据结构处理（拦截器已处理过）
        const authTypes = response.auth_types || [];
        console.log('📋 [FRONTEND-DEBUG] 设置认证类型');
        console.log('   - 认证类型数量:', authTypes.length);
        console.log('   - 认证类型列表:', authTypes);
        
        setAuthTypes(authTypes);
      }
    } catch (error: any) {
      console.error('❌ [FRONTEND-DEBUG] 加载认证类型失败:', error);
      console.error('加载认证类型失败:', error);
    }
  };

  useEffect(() => {
    console.log('🚀 [COMPONENT-DEBUG] MCPToolsManagement 组件初始化');
    console.log('   - 开始执行 useEffect');
    
    const initializeComponent = async () => {
      console.log('⏳ [COMPONENT-DEBUG] 开始初始化组件数据');
      try {
        await loadUserTools();
        await loadStats();
        await loadAuthTypes();
        console.log('✅ [COMPONENT-DEBUG] 组件数据初始化完成');
      } catch (error) {
        console.error('❌ [COMPONENT-DEBUG] 组件初始化失败:', error);
      }
    };
    
    initializeComponent();
  }, []);

  // 添加MCP服务器
  const handleAddServer = async (values: any) => {
    try {
      console.log('➕ [FRONTEND-DEBUG] 开始添加MCP服务器');
      console.log('   - 服务器名称:', values.server_name);
      console.log('   - 服务器URL:', values.server_url);
      console.log('   - 认证类型:', values.auth_type);
      
      const serverData = {
        server_name: values.server_name,
        server_url: values.server_url,
        server_description: values.server_description,
        auth_config: values.auth_type !== 'none' ? {
          type: values.auth_type,
          ...values.auth_config
        } : { type: 'none' }
      };
      
      console.log('   - 请求数据:', serverData);
      
      const response = await mcpUserToolsAPI.addMCPServer(serverData);
      
      console.log('✅ [FRONTEND-DEBUG] 服务器添加响应');
      console.log('   - 响应:', response);
      
      message.success('MCP服务器添加成功！');
      setAddServerModalVisible(false);
      addServerForm.resetFields();
      
      console.log('🔄 [FRONTEND-DEBUG] 开始刷新数据');
      await loadUserTools();
      await loadStats();
      onToolsUpdate?.();
      console.log('✅ [FRONTEND-DEBUG] 数据刷新完成');
      
    } catch (error: any) {
      console.error('❌ [FRONTEND-DEBUG] 添加服务器失败:', error);
      message.error(`添加服务器失败: ${error.message}`);
    }
  };

  // 删除服务器
  const handleDeleteServer = async (serverName: string) => {
    try {
      await mcpUserToolsAPI.deleteServerTools(serverName);
      message.success('服务器删除成功！');
      loadUserTools();
      loadStats();
      onToolsUpdate?.();
    } catch (error: any) {
      message.error(`删除服务器失败: ${error.message}`);
    }
  };

  // 重新发现服务器工具
  const handleRediscoverTools = async (serverName: string) => {
    try {
      const response = await mcpUserToolsAPI.rediscoverServerTools(serverName);
      if (response && response.data) {
        message.success(`重新发现完成: 新增${response.data.new_tools}个工具，更新${response.data.updated_tools}个工具`);
        loadUserTools();
        loadStats();
        onToolsUpdate?.();
      }
    } catch (error: any) {
      message.error(`重新发现失败: ${error.message}`);
    }
  };

  // 健康检查服务器
  const handleHealthCheck = async (serverName: string) => {
    try {
      setLoading(true);
      message.loading({ content: '正在检查服务器健康状态...', key: 'health-check' });
      
      const response = await mcpUserToolsAPI.healthCheckServer(serverName);
      if (response?.data) {
        const { server_status, active_tools_count, total_tools_count, tools_discovered } = response.data;
        
        message.success({
          content: `健康检查完成！服务器状态: ${server_status}, 活跃工具: ${active_tools_count}/${total_tools_count}`,
          key: 'health-check',
          duration: 4
        });
        
        // 刷新数据以显示最新状态
        loadUserTools();
        loadStats();
        
        // 触发外部组件更新
        onToolsUpdate?.();
      }
    } catch (error: any) {
      message.error({
        content: `健康检查失败: ${error.message}`,
        key: 'health-check',
        duration: 4
      });
    } finally {
      setLoading(false);
    }
  };

  // 测试工具调用
  const handleTestTool = async (values: any) => {
    if (!selectedTool) return;
    
    try {
      const response = await mcpUserToolsAPI.testTool(selectedTool.tool_id, values.arguments || {});
      if (response) {
        Modal.info({
          title: '工具调用结果',
          content: (
            <div>
              <p><strong>执行时间:</strong> {response.data?.execution_time_ms}ms</p>
              <p><strong>执行结果:</strong></p>
              <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '400px', overflow: 'auto' }}>
                {JSON.stringify(response.data?.result, null, 2)}
              </pre>
            </div>
          ),
          width: 600
        });
        
        setTestToolModalVisible(false);
        testToolForm.resetFields();
        loadUserTools(); // 刷新使用统计
      }
    } catch (error: any) {
      message.error(`工具调用失败: ${error.message}`);
    }
  };

  // 工具表格列定义
  const toolColumns = [
    {
      title: '工具名称',
      dataIndex: 'tool_name',
      key: 'tool_name',
      render: (name: string, record: MCPTool) => (
        <Space>
          <Text strong>{name}</Text>
          {!record.is_tool_active && <Tag color="red">已禁用</Tag>}
        </Space>
      )
    },
    {
      title: '描述',
      dataIndex: 'tool_description',
      key: 'tool_description',
      ellipsis: true,
      render: (desc: string) => desc || '-'
    },
    {
      title: '使用统计',
      key: 'usage',
      render: (record: MCPTool) => (
        <Space direction="vertical" size="small">
          <Text>调用 {record.tool_usage_count} 次</Text>
          <Text>成功率 {(Number(record.success_rate) || 0).toFixed(1)}%</Text>
          <Text>绑定 {record.bound_agents_count} 个Agent</Text>
        </Space>
      )
    },
    {
      title: '最后调用',
      dataIndex: 'last_tool_call',
      key: 'last_tool_call',
      render: (time: string) => time ? new Date(time).toLocaleString() : '-'
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: MCPTool) => (
        <Space>
          <Tooltip title="查看详情">
            <Button 
              type="text" 
              icon={<EyeOutlined />} 
              onClick={() => {
                setSelectedTool(record);
                setToolDetailsDrawerVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="测试调用">
            <Button 
              type="text" 
              icon={<PlayCircleOutlined />} 
              onClick={() => {
                setSelectedTool(record);
                setTestToolModalVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="编辑配置">
            <Button 
              type="text" 
              icon={<EditOutlined />} 
              onClick={() => {
                setSelectedTool(record);
                setEditToolModalVisible(true);
                editToolForm.setFieldsValue({
                  tool_description: record.tool_description,
                  is_tool_active: record.is_tool_active
                });
              }}
            />
          </Tooltip>
        </Space>
      )
    }
  ];

  // 服务器状态标签
  const getServerStatusTag = (status: string) => {
    const statusConfig = {
      'healthy': { color: 'green', text: '健康' },
      'unhealthy': { color: 'orange', text: '不健康' },
      'error': { color: 'red', text: '错误' },
      'unknown': { color: 'default', text: '未知' }
    };
    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.unknown;
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  return (
    <div style={{ padding: '24px' }}>
      {/* 统计概览 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={6}>
          <Card>
            <Statistic 
              title="工具总数" 
              value={stats.total_tools || 0} 
              prefix={<ApiOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="活跃工具" 
              value={stats.active_tools || 0} 
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="服务器数" 
              value={stats.total_servers || 0} 
              prefix={<SettingOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic 
              title="总调用次数" 
              value={stats.total_usage_count || 0} 
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 操作按钮 */}
      <Row justify="space-between" style={{ marginBottom: '16px' }}>
        <Col>
          <Title level={4}>我的MCP工具</Title>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadUserTools}>
              刷新
            </Button>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setAddServerModalVisible(true)}
            >
              添加服务器
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 服务器列表 */}
      <div style={{ marginBottom: '24px' }}>
        {servers.map(server => (
          <Card 
            key={server.server_name}
            title={
              <Space>
                <Text strong>{server.server_name}</Text>
                {getServerStatusTag(server.server_status)}
                <Text type="secondary">({server.tools_count} 个工具)</Text>
              </Space>
            }
            extra={
              <Space>
                <Tooltip title="检查服务器健康状态并更新工具状态">
                  <Button 
                    size="small"
                    icon={<HeartOutlined />}
                    onClick={() => handleHealthCheck(server.server_name)}
                    loading={loading}
                  >
                    健康检查
                  </Button>
                </Tooltip>
                <Button 
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={() => handleRediscoverTools(server.server_name)}
                >
                  重新发现
                </Button>
                <Popconfirm
                  title="确认删除此服务器及其所有工具？"
                  onConfirm={() => handleDeleteServer(server.server_name)}
                  okText="确认"
                  cancelText="取消"
                >
                  <Button 
                    size="small" 
                    danger 
                    icon={<DeleteOutlined />}
                  >
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            }
            style={{ marginBottom: '16px' }}
          >
            <div style={{ marginBottom: '12px' }}>
              <Text type="secondary">{server.server_url}</Text>
              {server.server_description && (
                <>
                  <br />
                  <Text>{server.server_description}</Text>
                </>
              )}
            </div>

            <Table
              dataSource={server.tools}
              columns={toolColumns}
              rowKey="tool_id"
              size="small"
              pagination={false}
              loading={loading}
            />
          </Card>
        ))}

        {servers.length === 0 && !loading && (
          <Card>
            <div style={{ textAlign: 'center', padding: '60px' }}>
              <ApiOutlined style={{ fontSize: '48px', color: '#d9d9d9', marginBottom: '16px' }} />
              <Title level={4} type="secondary">还没有MCP工具</Title>
              <Text type="secondary">添加MCP服务器来发现可用的工具</Text>
              <br /><br />
              <Button 
                type="primary" 
                icon={<PlusOutlined />}
                onClick={() => setAddServerModalVisible(true)}
              >
                添加第一个服务器
              </Button>
            </div>
          </Card>
        )}
      </div>

      {/* 添加服务器模态框 */}
      <Modal
        title="添加MCP服务器"
        open={addServerModalVisible}
        onOk={() => addServerForm.submit()}
        onCancel={() => {
          setAddServerModalVisible(false);
          addServerForm.resetFields();
        }}
        width={600}
      >
        <Form
          form={addServerForm}
          layout="vertical"
          onFinish={handleAddServer}
        >
          <Form.Item
            name="server_name"
            label="服务器名称"
            rules={[{ required: true, message: '请输入服务器名称' }]}
          >
            <Input placeholder="例如：filesystem-server" />
          </Form.Item>

          <Form.Item
            name="server_url"
            label="服务器地址"
            rules={[{ required: true, message: '请输入服务器地址' }]}
          >
            <Input placeholder="例如：http://localhost:3001" />
          </Form.Item>

          <Form.Item name="server_description" label="服务器描述">
            <TextArea rows={2} placeholder="可选的服务器描述信息" />
          </Form.Item>

          <Form.Item name="auth_type" label="认证类型" initialValue="none">
            <Select>
              {authTypes.map(auth => (
                <Option key={auth.type} value={auth.type}>
                  {auth.name} - {auth.description}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => 
              prevValues.auth_type !== currentValues.auth_type
            }
          >
            {({ getFieldValue }) => {
              const authType = getFieldValue('auth_type');
              const authConfig = authTypes.find(auth => auth.type === authType);
              
              if (!authConfig || authConfig.fields.length === 0) return null;
              
              return (
                <Card title="认证配置" size="small">
                  {authConfig.fields.map((field: any) => (
                    <Form.Item
                      key={field.name}
                      name={['auth_config', field.name]}
                      label={field.description}
                      rules={field.required ? [{ required: true, message: `请输入${field.description}` }] : []}
                    >
                      <Input 
                        type={field.type === 'password' ? 'password' : 'text'}
                        placeholder={field.description}
                      />
                    </Form.Item>
                  ))}
                </Card>
              );
            }}
          </Form.Item>
        </Form>
      </Modal>

      {/* 工具详情抽屉 */}
      <Drawer
        title="工具详情"
        open={toolDetailsDrawerVisible}
        onClose={() => setToolDetailsDrawerVisible(false)}
        width={600}
      >
        {selectedTool && (
          <div>
            <Descriptions column={1} bordered>
              <Descriptions.Item label="工具名称">{selectedTool.tool_name}</Descriptions.Item>
              <Descriptions.Item label="描述">{selectedTool.tool_description || '-'}</Descriptions.Item>
              <Descriptions.Item label="状态">
                {selectedTool.is_tool_active ? 
                  <Tag color="green">启用</Tag> : 
                  <Tag color="red">禁用</Tag>
                }
              </Descriptions.Item>
              <Descriptions.Item label="调用次数">{selectedTool.tool_usage_count}</Descriptions.Item>
              <Descriptions.Item label="成功率">{(Number(selectedTool.success_rate) || 0).toFixed(1)}%</Descriptions.Item>
              <Descriptions.Item label="绑定Agent数">{selectedTool.bound_agents_count}</Descriptions.Item>
              <Descriptions.Item label="最后调用">
                {selectedTool.last_tool_call ? new Date(selectedTool.last_tool_call).toLocaleString() : '从未调用'}
              </Descriptions.Item>
            </Descriptions>

            <Divider orientation="left">参数定义</Divider>
            <pre style={{ 
              background: '#f5f5f5', 
              padding: '12px', 
              borderRadius: '4px',
              fontSize: '12px',
              overflow: 'auto',
              maxHeight: '300px'
            }}>
              {JSON.stringify(selectedTool.tool_parameters, null, 2)}
            </pre>
          </div>
        )}
      </Drawer>

      {/* 测试工具模态框 */}
      <Modal
        title={`测试工具: ${selectedTool?.tool_name}`}
        open={testToolModalVisible}
        onOk={() => testToolForm.submit()}
        onCancel={() => {
          setTestToolModalVisible(false);
          testToolForm.resetFields();
        }}
        width={600}
      >
        <Form
          form={testToolForm}
          layout="vertical"
          onFinish={handleTestTool}
        >
          <Form.Item name="arguments" label="调用参数 (JSON格式)">
            <TextArea 
              rows={6} 
              placeholder={`请输入JSON格式的参数，例如：\n{\n  "path": "/tmp/test.txt",\n  "content": "Hello World"\n}`}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default MCPToolsManagement;