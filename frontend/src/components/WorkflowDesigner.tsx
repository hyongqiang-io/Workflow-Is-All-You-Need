import React, { useState, useCallback, useEffect, useRef } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Connection,
  useNodesState,
  useEdgesState,
  Controls,
  Background,
  MiniMap,
  NodeTypes,
  ReactFlowProvider,
  useReactFlow,
  Panel,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card, Button, Modal, Form, Input, Select, Space, message, Drawer, List, Tag, Tooltip, Badge } from 'antd';
import { PlusOutlined, SettingOutlined, PlayCircleOutlined, SaveOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { workflowAPI, nodeAPI, processorAPI, executionAPI } from '../services/api';

const { TextArea } = Input;
const { Option } = Select;

// 自定义节点类型
const CustomNode = ({ data, selected }: { data: any; selected?: boolean }) => {
  const getNodeColor = (type: string, status?: string) => {
    // 根据节点类型设置颜色
    if (type === 'start') return '#52c41a';
    if (type === 'end') return '#722ed1';
    
    // 处理器节点根据状态设置颜色
    switch (status) {
      case 'completed':
        return '#52c41a';
      case 'running':
        return '#1890ff';
      case 'failed':
        return '#ff4d4f';
      case 'pending':
        return '#faad14';
      default:
        return '#d9d9d9';
    }
  };

  const getNodeBackground = (type: string, status?: string) => {
    // 根据节点类型设置背景色
    if (type === 'start') return '#f6ffed';
    if (type === 'end') return '#f9f0ff';
    
    // 处理器节点根据状态设置背景
    switch (status) {
      case 'completed':
        return '#f6ffed';
      case 'running':
        return '#e6f7ff';
      case 'failed':
        return '#fff2f0';
      case 'pending':
        return '#fffbe6';
      default:
        return '#fafafa';
    }
  };

  const getNodeTypeText = (type: string) => {
    switch (type) {
      case 'start':
        return '开始节点';
      case 'processor':
        return '处理节点';
      case 'end':
        return '结束节点';
      default:
        return type;
    }
  };

  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '8px',
        border: `2px solid ${selected ? '#1890ff' : getNodeColor(data.type, data.status)}`,
        backgroundColor: getNodeBackground(data.type, data.status),
        minWidth: '160px',
        textAlign: 'center',
        boxShadow: selected ? '0 0 0 2px rgba(24, 144, 255, 0.2)' : '0 2px 8px rgba(0,0,0,0.1)',
        transition: 'all 0.3s ease',
        cursor: 'pointer',
        position: 'relative',
      }}
      className="react-flow__node-default"
    >
      <div style={{ fontWeight: 'bold', marginBottom: '6px', fontSize: '14px' }}>
        {data.label}
      </div>
      <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
        {getNodeTypeText(data.type)}
      </div>
      {data.status && data.type === 'processor' && (
        <Badge 
          status={data.status === 'completed' ? 'success' : 
                 data.status === 'running' ? 'processing' : 
                 data.status === 'failed' ? 'error' : 'default'} 
          text={
            <Tag color={getNodeColor(data.type, data.status)} style={{ marginTop: '4px' }}>
              {data.status === 'completed' ? '已完成' :
               data.status === 'running' ? '运行中' :
               data.status === 'failed' ? '失败' :
               data.status === 'pending' ? '待处理' : data.status}
            </Tag>
          }
        />
      )}
      {data.description && (
        <div style={{ fontSize: '11px', color: '#999', marginTop: '4px' }}>
          {data.description}
        </div>
      )}
      

      {/* 连接点 */}
      {data.type !== 'start' && (
        <Handle
          type="target"
          position={Position.Left}
          id={`${data.nodeId || 'unknown'}-target`}
          style={{
            background: '#555',
            width: '10px',
            height: '10px',
            border: '2px solid #fff',
          }}
        />
      )}
      {data.type !== 'end' && (
        <Handle
          type="source"
          position={Position.Right}
          id={`${data.nodeId || 'unknown'}-source`}
          style={{
            background: '#555',
            width: '10px',
            height: '10px',
            border: '2px solid #fff',
          }}
        />
      )}
    </div>
  );
};

const nodeTypes: NodeTypes = {
  custom: CustomNode,
};

interface WorkflowDesignerProps {
  workflowId?: string;
  onSave?: (nodes: Node[], edges: Edge[]) => void;
  onExecute?: (workflowId: string) => void;
  readOnly?: boolean;
}

const WorkflowDesigner: React.FC<WorkflowDesignerProps> = ({
  workflowId,
  onSave,
  onExecute,
  readOnly = false,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [nodeModalVisible, setNodeModalVisible] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [processors, setProcessors] = useState<any[]>([]);
  const [nodeForm] = Form.useForm();
  const [executionStatus, setExecutionStatus] = useState<any>(null);
  const [statusUpdateInterval, setStatusUpdateInterval] = useState<NodeJS.Timeout | null>(null);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadProcessors();
    if (workflowId) {
      loadWorkflow();
    }
    
    // 清理定时器
    return () => {
      if (statusUpdateInterval) {
        clearInterval(statusUpdateInterval);
      }
    };
  }, [workflowId]);

  // 实时状态更新
  useEffect(() => {
    if (executionStatus && executionStatus.status === 'running') {
      const interval = setInterval(async () => {
        try {
          const status: any = await executionAPI.getWorkflowStatus(executionStatus.instance_id);
          setExecutionStatus(status);
          
          // 更新节点状态
          if (status.nodes) {
            setNodes(prevNodes => 
              prevNodes.map(node => {
                const statusNode = status.nodes.find((n: any) => n.node_id === node.data.nodeId);
                if (statusNode) {
                  return {
                    ...node,
                    data: {
                      ...node.data,
                      status: statusNode.status
                    }
                  };
                }
                return node;
              })
            );
          }
          
          // 如果执行完成，停止更新
          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(interval);
          }
        } catch (error) {
          console.error('获取执行状态失败:', error);
        }
      }, 2000); // 每2秒更新一次
      
      setStatusUpdateInterval(interval);
    }
  }, [executionStatus]);

  const loadProcessors = async () => {
    try {
      // 优先获取已注册的处理器（这些有真正的处理器名称）
      const registeredResponse: any = await processorAPI.getRegisteredProcessors();
      console.log('已注册处理器API响应:', registeredResponse);
      
      let processorsData = [];
      
      // 处理已注册处理器数据
      if (registeredResponse && registeredResponse.data && registeredResponse.data.processors) {
        processorsData = registeredResponse.data.processors.map((processor: any) => ({
          processor_id: processor.processor_id,
          name: processor.name, // 这是真正的处理器名称
          type: processor.type,
          entity_type: processor.type,
          description: processor.username ? `用户: ${processor.username}` : 
                      processor.agent_name ? `Agent: ${processor.agent_name}` : 
                      processor.name,
          username: processor.username,
          agent_name: processor.agent_name,
          user_email: processor.user_email,
          agent_description: processor.agent_description
        }));
      }
      
      // 如果没有已注册的处理器，则获取可用的用户和Agent作为备选
      if (processorsData.length === 0) {
        console.log('没有已注册处理器，获取可用处理器作为备选');
        const availableResponse: any = await processorAPI.getAvailableProcessors();
        console.log('可用处理器API响应:', availableResponse);
        
        if (availableResponse && availableResponse.data) {
          let availableData = [];
          if (Array.isArray(availableResponse.data)) {
            availableData = availableResponse.data;
          } else if (availableResponse.data.processors && Array.isArray(availableResponse.data.processors)) {
            availableData = availableResponse.data.processors;
          }
          
          // 格式化可用处理器数据，给它们一个更清晰的名称
          processorsData = availableData.map((processor: any) => ({
            processor_id: processor.id,
            name: processor.type === 'agent' ? 
                  `${processor.name.replace('Agent: ', '')} 处理器` : 
                  `${processor.name.replace('用户: ', '')} 处理器`,
            type: processor.type,
            entity_type: processor.entity_type,
            description: processor.description,
            capabilities: processor.capabilities || []
          }));
        }
      }
      
      console.log('最终处理器数据:', processorsData);
      
      // 如果仍然没有处理器数据，使用默认处理器
      if (!processorsData || processorsData.length === 0) {
        console.log('使用默认处理器数据');
        processorsData = [
          { processor_id: 'fallback-gpt4', name: 'GPT-4 处理器', type: 'agent' },
          { processor_id: 'fallback-claude', name: 'Claude 处理器', type: 'agent' },
          { processor_id: 'fallback-human', name: '人工处理器', type: 'human' },
        ];
      }
      
      setProcessors(processorsData);
    } catch (error) {
      console.error('加载处理器失败:', error);
      // API失败时使用默认处理器
      const fallbackProcessors = [
        { processor_id: 'fallback-gpt4', name: 'GPT-4 处理器', type: 'agent' },
        { processor_id: 'fallback-claude', name: 'Claude 处理器', type: 'agent' },
        { processor_id: 'fallback-human', name: '人工处理器', type: 'human' },
      ];
      setProcessors(fallbackProcessors);
      console.log('使用fallback处理器数据');
    }
  };

  const loadWorkflow = async () => {
    if (!workflowId) return;
    
    try {
      // 加载工作流节点
      const response: any = await nodeAPI.getWorkflowNodes(workflowId);
      console.log('节点API响应:', response);
      
      // 处理响应数据
      let workflowNodes = [];
      if (response && response.success && response.data && response.data.nodes) {
        workflowNodes = response.data.nodes;
      } else if (Array.isArray(response)) {
        workflowNodes = response;
      } else {
        console.warn('节点API响应格式异常:', response);
        workflowNodes = [];
      }
      
      console.log('处理后的节点数据:', workflowNodes);
      
      // 过滤掉已删除的节点
      const activeNodes = workflowNodes.filter((node: any) => !node.is_deleted);
      console.log('过滤删除节点后的数据:', activeNodes);
      
      // 转换为ReactFlow节点
      const flowNodes: Node[] = activeNodes.map((node: any, index: number) => ({
        id: node.node_base_id || node.node_id,
        type: 'custom',
        position: { 
          x: node.position_x || 200 * (index + 1), 
          y: node.position_y || 100 * (index + 1) 
        },
        data: {
          label: node.name || '未命名节点',
          type: node.type || 'processor',
          status: node.status || 'pending',
          nodeId: node.node_base_id || node.node_id,
          description: node.task_description || node.description,
          processor_id: node.processor_id || '',
        },
      }));
      
      console.log('转换后的ReactFlow节点:', flowNodes);
      
      // 🔍 DEBUG: 检查processor_id是否正确加载
      console.log('🔍 DEBUG: 检查processor_id加载情况:');
      activeNodes.forEach((node: any, index: number) => {
        console.log(`节点 ${index + 1}: ${node.name} (${node.type})`);
        console.log(`  - processor_id: ${node.processor_id || '未设置'}`);
        console.log(`  - is_deleted: ${node.is_deleted}`);
        console.log(`  - 完整数据:`, node);
      });
      
      setNodes(flowNodes);
      
      // 加载节点连接
      try {
        const connectionResponse: any = await nodeAPI.getWorkflowConnections(workflowId);
        console.log('🔗 连接API响应:', connectionResponse);
        console.log('📋 响应详情:');
        console.log('  - success:', connectionResponse?.success);
        console.log('  - data:', connectionResponse?.data);
        console.log('  - connections:', connectionResponse?.data?.connections);
        
        let connections = [];
        if (connectionResponse && connectionResponse.success && connectionResponse.data && connectionResponse.data.connections) {
          connections = connectionResponse.data.connections;
          console.log('✅ 使用标准格式的连接数据');
        } else if (Array.isArray(connectionResponse)) {
          connections = connectionResponse;
          console.log('✅ 使用数组格式的连接数据');
        } else {
          console.log('❌ 未识别的连接数据格式');
        }
        
        console.log('🔄 处理后的连接数据:', connections);
        console.log('📊 连接数据详情:');
        connections.forEach((conn: any, index: number) => {
          console.log(`  连接 ${index + 1}:`, {
            from_node_base_id: conn.from_node_base_id,
            to_node_base_id: conn.to_node_base_id,
            from_node_name: conn.from_node_name,
            to_node_name: conn.to_node_name,
            connection_type: conn.connection_type,
            full_data: conn
          });
        });
        
        const flowEdges: Edge[] = connections.map((conn: any, index: number) => ({
          id: conn.connection_id || `e${index}`,
          source: conn.from_node_base_id,
          target: conn.to_node_base_id,
          type: 'smoothstep',
          sourceHandle: `${conn.from_node_base_id}-source`,
          targetHandle: `${conn.to_node_base_id}-target`,
        }));
        
        console.log('⚡ 转换后的ReactFlow边:', flowEdges);
        console.log('📏 ReactFlow边详情:');
        flowEdges.forEach((edge: Edge, index: number) => {
          console.log(`  边 ${index + 1}:`, {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            sourceHandle: edge.sourceHandle,
            targetHandle: edge.targetHandle
          });
        });
        
        setEdges(flowEdges);
      } catch (connectionError: any) {
        console.warn('加载连接数据失败:', connectionError);
        console.error('连接错误详情:', connectionError.response?.data);
        
        // 错误：删除自动创建默认连接的逻辑，改为设置空连接
        setEdges([]);
        
        // 如果是权限问题，显示相应提示
        if (connectionError.response?.status === 403) {
          console.warn('无权访问工作流连接数据');
        } else if (connectionError.response?.status === 422) {
          console.warn('连接数据格式问题 - 422错误详情:', connectionError.response?.data?.detail);
          if (Array.isArray(connectionError.response?.data?.detail)) {
            connectionError.response.data.detail.forEach((err: any, index: number) => {
              console.error(`422错误 ${index + 1}:`, err);
            });
          }
        } else {
          console.warn('其他连接加载错误:', connectionError.message);
        }
      }
      
    } catch (error) {
      console.error('加载工作流失败:', error);
      message.error('加载工作流失败');
    }
  };

  const onConnect = useCallback(
    async (params: Connection) => {
      if (!workflowId || !params.source || !params.target) {
        return;
      }
      
      try {
        const sourceNode = nodes.find(n => n.id === params.source);
        const targetNode = nodes.find(n => n.id === params.target);
        
        if (!sourceNode || !targetNode) {
          message.error('连接的节点信息不完整');
          return;
        }
        
        // 创建连接时确保Handle ID正确
        const newEdge = {
          ...params,
          id: `${params.source}-${params.target}`,
          type: 'smoothstep',
          sourceHandle: params.sourceHandle || `${params.source}-source`,
          targetHandle: params.targetHandle || `${params.target}-target`
        };
        setEdges((eds) => addEdge(newEdge, eds));
        
        // 尝试保存到后端
        try {
          const connectionData = {
            from_node_base_id: sourceNode.data.nodeId || sourceNode.id,
            to_node_base_id: targetNode.data.nodeId || targetNode.id,
            workflow_base_id: workflowId,
            connection_type: 'normal'
          };
          
          console.log('创建连接数据:', connectionData);
          
          const response: any = await nodeAPI.createConnection(connectionData);
          console.log('连接创建响应:', response);
          
          message.success('连接创建并保存成功');
        } catch (saveError) {
          console.warn('连接保存到后端失败，但本地显示正常:', saveError);
          message.warning('连接已创建，但保存到服务器失败');
        }
      } catch (error: any) {
        console.error('创建连接失败:', error);
        message.error(error.response?.data?.detail || '创建连接失败');
      }
    },
    [setEdges, nodes, workflowId]
  );

  const addNode = () => {
    setSelectedNode(null);
    nodeForm.resetFields();
    setNodeModalVisible(true);
  };

  const editNode = (node: Node) => {
    console.log('🔍 DEBUG: 编辑节点时的数据:');
    console.log('  - 节点ID:', node.id);
    console.log('  - 节点名称:', node.data.label);
    console.log('  - 节点类型:', node.data.type);
    console.log('  - processor_id:', node.data.processor_id);
    console.log('  - 完整node.data:', node.data);
    
    setSelectedNode(node);
    const formValues = {
      name: node.data.label,
      type: node.data.type,
      description: node.data.description || '',
      processor_id: node.data.processor_id || '',
    };
    
    console.log('🔍 DEBUG: 设置到表单的值:', formValues);
    nodeForm.setFieldsValue(formValues);
    setNodeModalVisible(true);
  };

  const handleNodeSave = async (values: any) => {
    console.log('🔍 DEBUG: 保存节点数据:', values);
    console.log('🔍 DEBUG: 选中的节点:', selectedNode);
    console.log('🔍 DEBUG: 工作流ID:', workflowId);
    
    // 🔍 DEBUG: 检查选择的processor信息
    if (values.processor_id) {
      const selectedProcessor = processors.find(p => 
        (p.processor_id || p.id) === values.processor_id
      );
      console.log('🔍 DEBUG: 选择的processor信息:');
      console.log('  - processor_id:', values.processor_id);
      console.log('  - 找到的processor:', selectedProcessor);
      console.log('  - 当前所有processors:', processors);
    }
    
    if (!workflowId) {
      message.error('请先保存工作流');
      return;
    }

    try {
      if (selectedNode) {
        console.log('更新现有节点...');
        // 先更新本地状态（立即反馈给用户）
        setNodes(prevNodes =>
          prevNodes.map(node =>
            node.id === selectedNode.id
              ? {
                  ...node,
                  data: {
                    ...node.data,
                    label: values.name,
                    type: values.type,
                    description: values.description,
                    processor_id: values.processor_id,
                  },
                }
              : node
          )
        );
        
        // 尝试更新后端
        try {
          const nodeData = {
            ...values,
            task_description: values.description,
            position_x: selectedNode.position.x,
            position_y: selectedNode.position.y
          };
          
          console.log('调用更新API:', nodeData);
          const response: any = await nodeAPI.updateNode(
            selectedNode.data.nodeId,
            workflowId,
            nodeData
          );
          console.log('🔍 DEBUG: 节点更新响应:', response);
          
          // 🔍 DEBUG: 检查API返回的processor_id
          if (response && response.data && response.data.node) {
            console.log('🔍 DEBUG: API返回的节点数据:');
            console.log('  - processor_id:', response.data.node.processor_id);
            console.log('  - 完整节点数据:', response.data.node);
          }
          
          message.success('节点更新成功');
        } catch (updateError) {
          console.warn('后端更新失败，但本地已更新:', updateError);
          message.warning('节点已更新，但服务器同步失败');
        }
      } else {
        // 创建新节点
        const nodeData = {
          ...values,
          workflow_base_id: workflowId,
          task_description: values.description,
          position_x: Math.floor(Math.random() * 400) + 100,
          position_y: Math.floor(Math.random() * 300) + 100
        };
        
        console.log('创建节点数据:', nodeData);
        
        const response: any = await nodeAPI.createNode(nodeData);
        console.log('节点创建响应:', response);
        
        // 处理响应数据
        let newNodeData = null;
        if (response && response.success && response.data && response.data.node) {
          newNodeData = response.data.node;
        } else if (response && response.node_id) {
          newNodeData = response;
        }
        
        if (newNodeData) {
          // 添加到ReactFlow
          const flowNode: Node = {
            id: newNodeData.node_base_id || newNodeData.node_id,
            type: 'custom',
            position: { 
              x: newNodeData.position_x || nodeData.position_x, 
              y: newNodeData.position_y || nodeData.position_y 
            },
            data: {
              label: values.name,
              type: values.type,
              status: 'pending',
              nodeId: newNodeData.node_base_id || newNodeData.node_id,
              description: values.description,
              processor_id: values.processor_id,
            },
          };
          
          console.log('添加到ReactFlow的节点:', flowNode);
          setNodes((nds) => [...nds, flowNode]);
          
          // 给新创建的节点添加一个标记，表示刚刚创建
          flowNode.data.justCreated = true;
          setTimeout(() => {
            // 500ms后移除标记
            setNodes(prevNodes => 
              prevNodes.map(n => 
                n.id === flowNode.id 
                  ? { ...n, data: { ...n.data, justCreated: false } }
                  : n
              )
            );
          }, 1000);
          
          message.success('节点创建成功');
        } else {
          throw new Error('创建节点响应数据异常');
        }
      }
      
      // 关闭modal并重置状态
      setNodeModalVisible(false);
      setSelectedNode(null);
      nodeForm.resetFields();
      console.log('节点保存完成，modal已关闭');
    } catch (error: any) {
      console.error('保存节点失败:', error);
      message.error(error.response?.data?.detail || error.message || '保存节点失败');
    }
  };

  const handleSave = async () => {
    if (!workflowId) {
      message.error('工作流ID不存在，无法保存');
      return;
    }

    const loadingMessage = message.loading('正在保存工作流...', 0);
    
    try {
      console.log('开始保存工作流...');
      console.log('工作流ID:', workflowId);
      console.log('节点数量:', nodes.length);
      console.log('连线数量:', edges.length);
      
      let savedCount = 0;
      let failedCount = 0;
      
      // 保存节点位置和状态到后端
      for (const node of nodes) {
        if (node.data.nodeId) {
          try {
            // 如果是刚创建的节点，额外等待一下确保数据库事务完成
            if (node.data.justCreated) {
              console.log('检测到刚创建的节点，等待数据库同步:', node.data.label);
              await new Promise(resolve => setTimeout(resolve, 1000));
            }
            const nodeData = {
              name: node.data.label || node.data.nodeId.toString().substring(0, 8),
              type: node.data.type, // 添加节点类型
              task_description: node.data.description || '',
              position_x: Math.round(node.position.x),
              position_y: Math.round(node.position.y)
            };
            
            // 确保name字段不为空字符串
            if (!nodeData.name || nodeData.name.trim() === '') {
              nodeData.name = `节点_${node.data.type}`;
            }
            
            console.log('保存节点:', node.data.label, nodeData);
            
            // 添加重试机制处理并发问题
            let retryCount = 0;
            const maxRetries = 3;
            let result = null;
            
            while (retryCount < maxRetries) {
              try {
                result = await nodeAPI.updateNode(node.data.nodeId, workflowId, nodeData);
                savedCount++;
                console.log('节点保存成功:', node.data.label, result);
                break;
              } catch (retryError: any) {
                retryCount++;
                console.warn(`节点保存重试 ${retryCount}/${maxRetries}:`, retryError.response?.status);
                
                // 如果是404错误且还有重试次数，等待后重试
                if (retryError.response?.status === 404 && retryCount < maxRetries) {
                  await new Promise(resolve => setTimeout(resolve, 500)); // 等待500ms
                  continue;
                }
                
                // 达到最大重试次数或其他错误，抛出异常
                throw retryError;
              }
            }
          } catch (nodeError: any) {
            // 404错误不计入失败，可能是新创建的节点还未同步
            if (nodeError.response?.status === 404) {
              console.warn('节点可能是新创建的，跳过位置更新:', node.data.label);
              savedCount++; // 不计入失败
            } else {
              failedCount++;
              console.error('节点保存失败:', node.data.label, nodeError);
              console.error('错误详情:', nodeError.response?.data);
              
              // 记录具体的错误信息用于调试
              if (nodeError.response?.status === 422) {
                console.error('422错误详情:', {
                  nodeId: node.data.nodeId,
                  nodeLabel: node.data.label,
                  nodeType: node.data.type,
                  requestData: {
                    name: node.data.label || node.data.nodeId.toString().substring(0, 8),
                    type: node.data.type,
                    task_description: node.data.description || '',
                    position_x: Math.round(node.position.x),
                    position_y: Math.round(node.position.y)
                  },
                  errorResponse: nodeError.response?.data
                });
              }
            }
          }
        }
      }
      
      loadingMessage();
      
      if (failedCount > 0) {
        message.warning(`部分节点保存失败：${savedCount} 个成功，${failedCount} 个失败`);
      } else if (savedCount > 0) {
        message.success(`节点保存成功：共 ${savedCount} 个节点`);
      }
      
      // 调用外部保存回调
      if (onSave) {
        console.log('调用外部保存回调...');
        await onSave(nodes, edges);
      }
      
    } catch (error: any) {
      loadingMessage();
      console.error('保存工作流失败:', error);
      message.error(error.response?.data?.detail || error.message || '保存工作流失败');
    }
  };

  const handleExecute = async () => {
    if (!workflowId) {
      message.error('请先保存工作流');
      return;
    }

    try {
      console.log('执行工作流请求:', {
        workflow_base_id: workflowId,
        input_data: {},
        instance_name: `执行_${Date.now()}`
      });
      
      const result: any = await executionAPI.executeWorkflow({
        workflow_base_id: workflowId,
        input_data: {},
        instance_name: `执行_${Date.now()}`
      });
      
      console.log('执行工作流响应:', result);
      setExecutionStatus(result);
      message.success('工作流开始执行');
      
      if (onExecute) {
        onExecute(workflowId);
      }
    } catch (error: any) {
      console.error('执行工作流失败:', error);
      console.error('错误响应:', error.response?.data);
      message.error(error.response?.data?.detail || '执行工作流失败');
    }
  };

  const handleDeleteNode = useCallback(async (nodeId: string) => {
    console.log('开始删除节点:', nodeId);
    try {
      const node = nodes.find(n => n.id === nodeId);
      console.log('找到节点:', node);
      if (!node) {
        console.error('找不到要删除的节点:', nodeId);
        message.error('找不到要删除的节点');
        return;
      }
      
      // 调用后端删除API
      if (workflowId && node.data.nodeId) {
        console.log('调用后端删除API...');
        await nodeAPI.deleteNode(node.data.nodeId, workflowId);
        message.success('节点删除成功');
        
        // 删除成功后重新加载工作流数据
        console.log('重新加载工作流数据...');
        await loadWorkflow();
      } else {
        console.log('缺少必要参数，workflowId:', workflowId, 'nodeId:', node.data.nodeId);
        message.error('删除失败：缺少必要参数');
      }
    } catch (error: any) {
      console.error('删除节点失败:', error);
      message.error('删除节点失败');
    }
  }, [nodes, workflowId, loadWorkflow]);

  const handleDeleteEdge = useCallback(async (edgeId: string) => {
    try {
      const edge = edges.find(e => e.id === edgeId);
      if (!edge) {
        message.error('找不到要删除的连接');
        return;
      }
      
      console.log('删除连接:', edge);
      
      // 先从本地删除（即使后端失败也能看到效果）
      setEdges(prevEdges => prevEdges.filter(e => e.id !== edgeId));
      
      // 尝试从后端删除
      try {
        const sourceNode = nodes.find(n => n.id === edge.source);
        const targetNode = nodes.find(n => n.id === edge.target);
        
        console.log('源节点:', sourceNode);
        console.log('目标节点:', targetNode);
        
        if (workflowId && sourceNode && targetNode && sourceNode.data.nodeId && targetNode.data.nodeId) {
          const deleteData = {
            from_node_base_id: sourceNode.data.nodeId,
            to_node_base_id: targetNode.data.nodeId,
            workflow_base_id: workflowId
          };
          
          console.log('删除连接请求数据:', deleteData);
          
          const response = await nodeAPI.deleteConnection(deleteData);
          console.log('删除连接响应:', response);
          message.success('连接删除成功');
        } else {
          console.log('缺少必要信息，仅本地删除');
          console.log('workflowId:', workflowId);
          console.log('sourceNode.data.nodeId:', sourceNode?.data?.nodeId);
          console.log('targetNode.data.nodeId:', targetNode?.data?.nodeId);
          message.success('连接已删除（仅本地）');
        }
      } catch (deleteError: any) {
        console.warn('后端删除连接失败，但本地已删除:', deleteError);
        console.error('删除错误详情:', deleteError.response?.data);
        // 即使后端删除失败，本地已经删除了，所以还是提示成功
        message.success('连接已删除');
      }
    } catch (error: any) {
      console.error('删除连接失败:', error);
      message.error('删除连接失败');
    }
  }, [edges, setEdges, nodes, workflowId]);

  const onNodeDoubleClick = (event: any, node: Node) => {
    console.log('双击节点事件触发:', node, event);
    if (!readOnly) {
      // 如果按住Shift键，则删除节点
      if (event.shiftKey) {
        console.log('Shift+双击删除节点:', node.id);
        handleDeleteNode(node.id);
      } else {
        console.log('编辑节点:', node.id);
        editNode(node);
      }
    }
  };

  const onNodeContextMenu = useCallback((event: any, node: Node) => {
    console.log('节点右键菜单触发:', node);
    console.log('readOnly状态:', readOnly);
    
    if (!readOnly) {
      event.preventDefault();
      event.stopPropagation();
      
      if (window.confirm(`确定要删除节点 "${node.data.label}" 吗？`)) {
        console.log('确认删除节点:', node.id);
        handleDeleteNode(node.id);
      }
    }
  }, [readOnly, handleDeleteNode]);

  const onEdgeContextMenu = useCallback((event: any, edge: Edge) => {
    console.log('连线右键菜单触发:', edge);
    if (!readOnly) {
      event.preventDefault();
      event.stopPropagation();
      
      if (window.confirm('确定要删除这个连接吗？')) {
        console.log('确认删除连线:', edge.id);
        handleDeleteEdge(edge.id);
      }
    }
  }, [readOnly, handleDeleteEdge]);

  // 键盘删除功能
  const onNodesDelete = useCallback((deletedNodes: Node[]) => {
    console.log('键盘删除节点触发:', deletedNodes);
    console.log('readOnly状态:', readOnly);
    if (!readOnly) {
      deletedNodes.forEach(node => {
        console.log('键盘删除节点:', node.id);
        handleDeleteNode(node.id);
      });
    }
  }, [readOnly, handleDeleteNode]);

  const onEdgesDelete = useCallback((deletedEdges: Edge[]) => {
    console.log('键盘删除连线触发:', deletedEdges);
    if (!readOnly) {
      deletedEdges.forEach(edge => {
        console.log('键盘删除连线:', edge.id);
        handleDeleteEdge(edge.id);
      });
    }
  }, [readOnly, handleDeleteEdge]);


  // 手动键盘事件监听（备用方案）
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      console.log('键盘事件:', event.key, event.code);
      if (event.key === 'Delete' && !readOnly) {
        console.log('Delete键按下，检查选中元素...');
        const selectedNodes = nodes.filter(n => n.selected);
        const selectedEdges = edges.filter(e => e.selected);
        console.log('选中的节点:', selectedNodes);
        console.log('选中的边:', selectedEdges);
        
        if (selectedNodes.length > 0 || selectedEdges.length > 0) {
          event.preventDefault();
          selectedNodes.forEach(node => handleDeleteNode(node.id));
          selectedEdges.forEach(edge => handleDeleteEdge(edge.id));
        }
      }
    };

    // 监听document而不是ReactFlow元素
    document.addEventListener('keydown', handleKeyDown);
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [readOnly, nodes, edges, handleDeleteNode, handleDeleteEdge]);

  return (
    <ReactFlowProvider>
      <div style={{ height: '100vh', width: '100%', minHeight: '600px' }} ref={reactFlowWrapper}>
        <Card
          title={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>工作流设计器</span>
              {executionStatus && (
                <Tag color={executionStatus.status === 'running' ? 'processing' : 
                           executionStatus.status === 'completed' ? 'success' : 
                           executionStatus.status === 'failed' ? 'error' : 'default'}>
                  {executionStatus.status === 'running' ? '执行中' :
                   executionStatus.status === 'completed' ? '已完成' :
                   executionStatus.status === 'failed' ? '执行失败' : executionStatus.status}
                </Tag>
              )}
            </div>
          }
          extra={
            <Space>
              {!readOnly && (
                <>
                  <Tooltip title="添加节点">
                    <Button icon={<PlusOutlined />} onClick={addNode}>
                      添加节点
                    </Button>
                  </Tooltip>
                  <Tooltip title="保存工作流">
                    <Button icon={<SaveOutlined />} onClick={handleSave}>
                      保存
                    </Button>
                  </Tooltip>
                </>
              )}
              <Tooltip title="执行工作流">
                <Button 
                  type="primary" 
                  icon={<PlayCircleOutlined />} 
                  onClick={handleExecute}
                  disabled={!workflowId || (executionStatus && executionStatus.status === 'running')}
                  loading={executionStatus && executionStatus.status === 'running'}
                >
                  执行
                </Button>
              </Tooltip>
              {executionStatus && (
                <Tooltip title="刷新状态">
                  <Button 
                    icon={<ReloadOutlined />} 
                    onClick={() => {
                      if (statusUpdateInterval) {
                        clearInterval(statusUpdateInterval);
                      }
                      setExecutionStatus(null);
                    }}
                  >
                    停止监控
                  </Button>
                </Tooltip>
              )}
            </Space>
          }
        >
          {/* 统计信息 */}
          <div style={{ padding: '8px', background: '#f9f9f9', fontSize: '12px', marginBottom: '8px', borderRadius: '4px' }}>
            <span>节点: {nodes.length}</span>
            <span style={{ marginLeft: '16px' }}>连线: {edges.length}</span>
            {workflowId && <span style={{ marginLeft: '16px', color: '#52c41a' }}>已连接</span>}
            <span style={{ marginLeft: '16px', color: readOnly ? '#ff4d4f' : '#52c41a' }}>
              {readOnly ? '只读模式' : '编辑模式'}
            </span>
          </div>
          
          <div style={{ height: '500px', width: '100%', border: '1px solid #d9d9d9', borderRadius: '6px' }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              onNodeDoubleClick={onNodeDoubleClick}
              onNodeContextMenu={onNodeContextMenu}
              onEdgeContextMenu={onEdgeContextMenu}
              onNodesDelete={onNodesDelete}
              onEdgesDelete={onEdgesDelete}
              fitView
              fitViewOptions={{ padding: 0.1, minZoom: 0.5, maxZoom: 2 }}
              deleteKeyCode="Delete"
              selectNodesOnDrag={false}
              attributionPosition="bottom-left"
            >
            <Controls />
            <Background />
            <MiniMap />
            <Panel position="top-left">
              <div style={{ background: 'white', padding: '8px', borderRadius: '4px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
                <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                  双击节点编辑 | 右键删除 | Delete键删除选中
                </div>
                {!readOnly && (
                  <Space size="small">
                    <Button 
                      size="small" 
                      icon={<DeleteOutlined />} 
                      danger
                      onClick={() => {
                        console.log('删除按钮点击');
                        const selectedNodes = nodes.filter(n => n.selected);
                        const selectedEdges = edges.filter(e => e.selected);
                        console.log('选中的节点:', selectedNodes);
                        console.log('选中的边:', selectedEdges);
                        
                        if (selectedNodes.length > 0 || selectedEdges.length > 0) {
                          Modal.confirm({
                            title: '批量删除',
                            content: `确定要删除 ${selectedNodes.length} 个节点和 ${selectedEdges.length} 个连接吗？`,
                            onOk: () => {
                              console.log('确认批量删除');
                              selectedNodes.forEach(node => handleDeleteNode(node.id));
                              selectedEdges.forEach(edge => handleDeleteEdge(edge.id));
                            }
                          });
                        } else {
                          message.info('请先选择要删除的元素');
                        }
                      }}
                    >
                      删除选中
                    </Button>
                  </Space>
                )}
              </div>
            </Panel>
            </ReactFlow>
          </div>
        </Card>
      </div>

      {/* 节点编辑模态框 */}
      <Modal
        title={selectedNode ? '编辑节点' : '添加节点'}
        open={nodeModalVisible}
        onOk={() => nodeForm.submit()}
        onCancel={() => setNodeModalVisible(false)}
        width={600}
      >
        <Form form={nodeForm} layout="vertical" onFinish={handleNodeSave}>
          <Form.Item
            name="name"
            label="节点名称"
            rules={[{ required: true, message: '请输入节点名称' }]}
          >
            <Input placeholder="请输入节点名称" />
          </Form.Item>
          
          <Form.Item
            name="type"
            label="节点类型"
            rules={[{ required: true, message: '请选择节点类型' }]}
          >
            <Select placeholder="请选择节点类型">
              <Option value="start">开始节点</Option>
              <Option value="processor">处理器节点</Option>
              <Option value="end">结束节点</Option>
            </Select>
          </Form.Item>
          
          <Form.Item
            name="description"
            label="任务描述"
          >
            <TextArea rows={3} placeholder="请输入任务描述" />
          </Form.Item>
          
          <Form.Item
            name="processor_id"
            label="处理器"
            dependencies={['type']}
            extra={!Array.isArray(processors) || processors.length === 0 ? "暂无可用处理器，将使用默认处理器" : null}
          >
            <Select 
              placeholder="请选择处理器"
              disabled={nodeForm.getFieldValue('type') !== 'processor'}
              allowClear
              showSearch
              filterOption={(input, option) => {
                const childrenStr = option?.children?.toString().toLowerCase();
                return childrenStr ? childrenStr.includes(input.toLowerCase()) : false;
              }}
            >
              {/* 默认处理器选项 */}
              <Option value="default-agent">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>默认AI处理器</span>
                  <Tag color="blue">agent</Tag>
                </div>
              </Option>
              <Option value="default-human">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>默认人工处理器</span>
                  <Tag color="green">human</Tag>
                </div>
              </Option>
              
              {/* 从API加载的处理器 */}
              {Array.isArray(processors) && processors.map((processor, index) => {
                const processorType = processor.type || processor.entity_type || 'unknown';
                const processorName = processor.name || processor.agent_name || processor.username || '未命名处理器';
                const processorValue = processor.processor_id || processor.id;
                
                // 🔍 DEBUG: 输出processor选项信息
                console.log(`🔍 DEBUG: Processor选项 ${index + 1}:`, {
                  name: processorName,
                  value: processorValue,
                  processor_id: processor.processor_id,
                  id: processor.id,
                  type: processorType,
                  fullData: processor
                });
                
                const getTypeColor = (type: string) => {
                  switch (type.toLowerCase()) {
                    case 'agent': return 'blue';
                    case 'human': return 'green';
                    case 'mix': return 'orange';
                    default: return 'default';
                  }
                };
                
                return (
                  <Option key={processorValue} value={processorValue}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {processorName}
                      </span>
                      <Tag color={getTypeColor(processorType)}>
                        {processorType}
                      </Tag>
                    </div>
                  </Option>
                );
              })}
              
              {/* 静态备选处理器 */}
              <Option value="gpt-4">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>GPT-4处理器</span>
                  <Tag color="blue">agent</Tag>
                </div>
              </Option>
              <Option value="claude">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Claude处理器</span>
                  <Tag color="blue">agent</Tag>
                </div>
              </Option>
              <Option value="human-review">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>人工审核</span>
                  <Tag color="green">human</Tag>
                </div>
              </Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </ReactFlowProvider>
  );
};

export default WorkflowDesigner; 