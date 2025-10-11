import React, { useState, useEffect } from 'react';
import { 
  Select, Card, Space, Typography, Tag, Button, message, 
  Divider, Row, Col, InputNumber, Switch, Input, Tooltip, Badge,
  Collapse, Form
} from 'antd';
import { 
  ToolOutlined, SettingOutlined, DeleteOutlined, InfoCircleOutlined,
  CheckCircleOutlined, ExclamationCircleOutlined
} from '@ant-design/icons';
import { mcpUserToolsAPI, agentToolsAPI } from '../services/api';

const { Text, Title } = Typography;
const { Panel } = Collapse;
const { TextArea } = Input;

interface MCPTool {
  tool_id: string;
  tool_name: string;
  tool_description?: string;
  server_name: string;
  server_url: string;
  tool_parameters: any;
  is_server_active: boolean;
  is_tool_active: boolean;
  server_status: string;
  tool_usage_count: number;
  success_rate: number;
  bound_agents_count: number;
}

interface ToolBinding {
  tool_id: string;
  tool_name: string;
  server_name: string;
  is_enabled: boolean;
  priority: number;
  max_calls_per_task: number;
  timeout_override?: number;
  custom_config: any;
}

interface AgentToolSelectorProps {
  agentId?: string; // 编辑模式时提供
  value?: ToolBinding[]; // 当前绑定的工具
  onChange?: (bindings: ToolBinding[]) => void; // 绑定变化回调
  disabled?: boolean;
  mode?: 'create' | 'edit';
}

const AgentToolSelector: React.FC<AgentToolSelectorProps> = ({ 
  agentId, 
  value = [], 
  onChange, 
  disabled = false,
  mode = 'create'
}) => {
  const [availableTools, setAvailableTools] = useState<MCPTool[]>([]);
  const [selectedTools, setSelectedTools] = useState<ToolBinding[]>(value);
  const [loading, setLoading] = useState(false);

  // 加载用户可用工具
  const loadAvailableTools = async () => {
    setLoading(true);
    try {
      // console.log('🔧 [AGENT-TOOLS-DEBUG] 开始加载可用工具');
      
      const response = await mcpUserToolsAPI.getUserTools();
      // console.log('🔧 [AGENT-TOOLS-DEBUG] 原始响应:', response);
      
      // 修复：适应新的响应数据结构
      if (response && response.servers) {
        const tools: MCPTool[] = [];
        // console.log('🔧 [AGENT-TOOLS-DEBUG] 服务器数量:', response.servers.length);
        
        response.servers.forEach((server: any, serverIndex: number) => {
          // console.log(`🔧 [AGENT-TOOLS-DEBUG] 处理服务器 ${serverIndex + 1}: ${server.server_name}`);
          // console.log(`   - 服务器状态: ${server.server_status}`);
          // console.log(`   - 服务器激活: ${server.is_server_active}`);
          // console.log(`   - 工具数量: ${server.tools?.length || 0}`);
          
          server.tools?.forEach((tool: any, toolIndex: number) => {
            // console.log(`   - 工具 ${toolIndex + 1}: ${tool.tool_name}`);
            // console.log(`     * 工具激活: ${tool.is_tool_active}`);
            
            tools.push({
              ...tool,
              server_name: server.server_name,
              server_url: server.server_url,
              is_server_active: server.is_server_active, // 使用服务器提供的激活状态
              server_status: server.server_status
            });
          });
        });
        
        // console.log('🔧 [AGENT-TOOLS-DEBUG] 解析后的工具总数:', tools.length);
        // console.log('🔧 [AGENT-TOOLS-DEBUG] 工具详情:', tools);
        
        setAvailableTools(tools);
      } else {
        console.warn('🔧 [AGENT-TOOLS-DEBUG] 响应数据格式不正确:', response);
      }
    } catch (error: any) {
      console.error('🔧 [AGENT-TOOLS-DEBUG] 加载工具失败:', error);
      message.error(`加载工具失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 加载Agent已绑定的工具
  const loadAgentBindings = async () => {
    if (!agentId || mode !== 'edit') return;
    
    try {
      const response = await agentToolsAPI.getAgentTools(agentId);
      if (response && response.data && response.data.tools) {
        const bindings: ToolBinding[] = response.data.tools.map((tool: any) => ({
          tool_id: tool.tool_id,
          tool_name: tool.tool_name,
          server_name: tool.server_name,
          is_enabled: tool.is_enabled,
          priority: tool.priority,
          max_calls_per_task: tool.max_calls_per_task,
          timeout_override: tool.timeout_override,
          custom_config: tool.custom_config
        }));
        setSelectedTools(bindings);
        onChange?.(bindings);
      }
    } catch (error: any) {
      message.error(`加载Agent工具绑定失败: ${error.message}`);
    }
  };

  useEffect(() => {
    loadAvailableTools();
    loadAgentBindings();
  }, [agentId, mode]);

  useEffect(() => {
    setSelectedTools(value);
  }, [value]);

  // 添加工具绑定
  const addToolBinding = async (tool: MCPTool) => {
    const newBinding: ToolBinding = {
      tool_id: tool.tool_id,
      tool_name: tool.tool_name,
      server_name: tool.server_name,
      is_enabled: true,
      priority: 5,
      max_calls_per_task: 5,
      timeout_override: undefined,
      custom_config: {}
    };

    // 如果是编辑模式且有agentId，立即保存到后端
    if (mode === 'edit' && agentId) {
      try {
        await agentToolsAPI.bindTool(agentId, {
          tool_id: tool.tool_id,
          is_enabled: true,
          priority: 5,
          max_calls_per_task: 5,
          timeout_override: undefined,
          custom_config: {}
        });
        message.success(`工具 ${tool.tool_name} 绑定成功`);
        
        // 重新加载Agent绑定
        await loadAgentBindings();
      } catch (error: any) {
        message.error(`绑定工具失败: ${error.message}`);
        return;
      }
    } else {
      // 创建模式，只更新本地状态
      const updatedBindings = [...selectedTools, newBinding];
      setSelectedTools(updatedBindings);
      onChange?.(updatedBindings);
    }
  };

  // 移除工具绑定
  const removeToolBinding = async (toolId: string) => {
    // 如果是编辑模式且有agentId，立即从后端删除
    if (mode === 'edit' && agentId) {
      try {
        await agentToolsAPI.unbindTool(agentId, toolId);
        message.success('工具绑定已解除');
        
        // 重新加载Agent绑定
        await loadAgentBindings();
      } catch (error: any) {
        message.error(`解除工具绑定失败: ${error.message}`);
        return;
      }
    } else {
      // 创建模式，只更新本地状态
      const updatedBindings = selectedTools.filter(binding => binding.tool_id !== toolId);
      setSelectedTools(updatedBindings);
      onChange?.(updatedBindings);
    }
  };

  // 更新工具绑定配置
  const updateToolBinding = async (toolId: string, updates: Partial<ToolBinding>) => {
    // 如果是编辑模式且有agentId，立即保存到后端
    if (mode === 'edit' && agentId) {
      try {
        const updateData: any = {};
        if (updates.is_enabled !== undefined) updateData.is_enabled = updates.is_enabled;
        if (updates.priority !== undefined) updateData.priority = updates.priority;
        if (updates.max_calls_per_task !== undefined) updateData.max_calls_per_task = updates.max_calls_per_task;
        if (updates.timeout_override !== undefined) updateData.timeout_override = updates.timeout_override;
        if (updates.custom_config !== undefined) updateData.custom_config = updates.custom_config;

        await agentToolsAPI.updateToolBinding(agentId, toolId, updateData);
        message.success('工具配置已更新');
        
        // 重新加载Agent绑定以获取最新状态
        await loadAgentBindings();
      } catch (error: any) {
        message.error(`更新工具配置失败: ${error.message}`);
        return;
      }
    } else {
      // 创建模式，只更新本地状态
      const updatedBindings = selectedTools.map(binding => 
        binding.tool_id === toolId ? { ...binding, ...updates } : binding
      );
      setSelectedTools(updatedBindings);
      onChange?.(updatedBindings);
    }
  };

  // 获取工具状态标签
  const getToolStatusTag = (tool: MCPTool) => {
    if (!tool.is_server_active) {
      return <Tag color="red">服务器离线</Tag>;
    }
    if (!tool.is_tool_active) {
      return <Tag color="orange">工具禁用</Tag>;
    }
    return <Tag color="green">正常</Tag>;
  };

  // 检查工具是否已选择
  const isToolSelected = (toolId: string) => {
    return selectedTools.some(binding => binding.tool_id === toolId);
  };

  // 获取可选择的工具列表
  const selectableTools = availableTools.filter(tool => {
    const isServerActive = tool.is_server_active;
    const isToolActive = tool.is_tool_active;
    const isNotSelected = !isToolSelected(tool.tool_id);
    
    // console.log(`🔍 [FILTER-DEBUG] 工具: ${tool.tool_name}`);
    // console.log(`   - 服务器激活: ${isServerActive}`);
    // console.log(`   - 工具激活: ${isToolActive}`);
    // console.log(`   - 未选中: ${isNotSelected}`);
    // console.log(`   - 最终可选: ${isServerActive && isToolActive && isNotSelected}`);
    
    return isServerActive && isToolActive && isNotSelected;
  });
  
  // console.log('🔍 [FILTER-DEBUG] 可选工具总数:', selectableTools.length);
  // console.log('🔍 [FILTER-DEBUG] 可选工具列表:', selectableTools);

  return (
    <div>
      <div style={{ marginBottom: '16px' }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={5}>
              <ToolOutlined /> 工具绑定配置
            </Title>
          </Col>
          <Col>
            <Space>
              <Text type="secondary">
                已选择 {selectedTools.length} 个工具
              </Text>
              <Button 
                size="small"
                icon={<ToolOutlined />}
                onClick={loadAvailableTools}
                loading={loading}
              >
                刷新工具列表
              </Button>
            </Space>
          </Col>
        </Row>
      </div>

      {/* 工具选择器 */}
      <Card size="small" style={{ marginBottom: '16px' }}>
        <div style={{ marginBottom: '12px' }}>
          <Text strong>添加工具:</Text>
        </div>
        <Select
          style={{ width: '100%' }}
          placeholder="选择要绑定的工具"
          disabled={disabled || selectableTools.length === 0}
          loading={loading}
          onSelect={(toolId) => {
            const tool = availableTools.find(t => t.tool_id === toolId);
            if (tool) {
              addToolBinding(tool);
            }
          }}
          value={undefined} // 始终显示placeholder
        >
          {selectableTools.map(tool => (
            <Select.Option key={tool.tool_id} value={tool.tool_id}>
              <Space>
                <Text strong>{tool.tool_name}</Text>
                <Text type="secondary">({tool.server_name})</Text>
                {getToolStatusTag(tool)}
              </Space>
            </Select.Option>
          ))}
        </Select>
        {selectableTools.length === 0 && !loading && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            没有可用的工具，请先在"我的工具"中添加MCP服务器
          </Text>
        )}
      </Card>

      {/* 已绑定工具配置 */}
      {selectedTools.length > 0 && (
        <Card title="已绑定工具配置" size="small">
          <Collapse size="small">
            {selectedTools.map((binding, index) => {
              const tool = availableTools.find(t => t.tool_id === binding.tool_id);
              return (
                <Panel 
                  key={binding.tool_id}
                  header={
                    <Space>
                      <Badge status={binding.is_enabled ? 'success' : 'default'} />
                      <Text strong>{binding.tool_name}</Text>
                      <Text type="secondary">({binding.server_name})</Text>
                      <Tag>优先级: {binding.priority}</Tag>
                      <Tag>最大调用: {binding.max_calls_per_task}</Tag>
                    </Space>
                  }
                  extra={
                    <Space>
                      <Tooltip title="删除工具绑定">
                        <Button 
                          type="text" 
                          size="small" 
                          danger
                          icon={<DeleteOutlined />}
                          onClick={(e) => {
                            e.stopPropagation();
                            removeToolBinding(binding.tool_id);
                          }}
                          disabled={disabled}
                        />
                      </Tooltip>
                    </Space>
                  }
                >
                  <Row gutter={16}>
                    <Col span={12}>
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <div>
                          <Text strong>基本配置:</Text>
                        </div>
                        <div>
                          <Text>启用状态:</Text>
                          <Switch 
                            size="small"
                            checked={binding.is_enabled}
                            onChange={(checked) => 
                              updateToolBinding(binding.tool_id, { is_enabled: checked })
                            }
                            disabled={disabled}
                            style={{ marginLeft: '8px' }}
                          />
                        </div>
                        <div>
                          <Text>优先级 (0-100):</Text>
                          <InputNumber
                            size="small"
                            min={0}
                            max={100}
                            value={binding.priority}
                            onChange={(value) => 
                              updateToolBinding(binding.tool_id, { priority: value || 0 })
                            }
                            disabled={disabled}
                            style={{ marginLeft: '8px', width: '80px' }}
                          />
                        </div>
                        <div>
                          <Text>单任务最大调用次数:</Text>
                          <InputNumber
                            size="small"
                            min={1}
                            max={50}
                            value={binding.max_calls_per_task}
                            onChange={(value) => 
                              updateToolBinding(binding.tool_id, { max_calls_per_task: value || 1 })
                            }
                            disabled={disabled}
                            style={{ marginLeft: '8px', width: '80px' }}
                          />
                        </div>
                        <div>
                          <Text>超时时间覆盖 (秒):</Text>
                          <InputNumber
                            size="small"
                            min={1}
                            max={300}
                            value={binding.timeout_override}
                            onChange={(value) => 
                              updateToolBinding(binding.tool_id, { timeout_override: value || undefined })
                            }
                            disabled={disabled}
                            placeholder="默认"
                            style={{ marginLeft: '8px', width: '100px' }}
                          />
                        </div>
                      </Space>
                    </Col>
                    <Col span={12}>
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <div>
                          <Text strong>工具信息:</Text>
                        </div>
                        {tool && (
                          <>
                            <Text type="secondary">{tool.tool_description || '无描述'}</Text>
                            <div>
                              <Text>调用次数: {tool.tool_usage_count}</Text>
                            </div>
                            <div>
                              <Text>成功率: {(Number(tool.success_rate) || 0).toFixed(1)}%</Text>
                            </div>
                            <div>
                              <Text>绑定Agent数: {tool.bound_agents_count}</Text>
                            </div>
                          </>
                        )}
                        <div>
                          <Text strong>自定义配置:</Text>
                          <TextArea
                            size="small"
                            rows={3}
                            value={JSON.stringify(binding.custom_config, null, 2)}
                            onChange={(e) => {
                              try {
                                const config = JSON.parse(e.target.value || '{}');
                                updateToolBinding(binding.tool_id, { custom_config: config });
                              } catch (error) {
                                // 忽略JSON解析错误，用户可能正在输入
                              }
                            }}
                            disabled={disabled}
                            placeholder="{}"
                          />
                        </div>
                      </Space>
                    </Col>
                  </Row>
                </Panel>
              );
            })}
          </Collapse>
        </Card>
      )}

      {selectedTools.length === 0 && (
        <Card size="small">
          <div style={{ textAlign: 'center', padding: '20px' }}>
            <ToolOutlined style={{ fontSize: '32px', color: '#d9d9d9', marginBottom: '8px' }} />
            <div>
              <Text type="secondary">还没有绑定任何工具</Text>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                从上面的下拉框中选择工具来为Agent添加能力
              </Text>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};

export default AgentToolSelector;