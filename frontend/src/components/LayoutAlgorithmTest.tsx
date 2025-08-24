import React, { useState, useEffect } from 'react';
import { Card, Button, Space } from 'antd';
import ReactFlow, { 
  Node, 
  Edge, 
  Controls, 
  Background, 
  MiniMap 
} from 'reactflow';
import 'reactflow/dist/style.css';
import { 
  validateAndFixEdges, 
  generateMissingConnections, 
  calculateDependencyBasedLayout,
  getNodeStatusColor
} from '../utils/workflowLayoutUtils';

const LayoutAlgorithmTest: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  
  // 测试数据1: 简单线性流程
  const createLinearFlow = () => {
    const testNodes = [
      { node_instance_id: 'start-1', node_name: '开始', node_type: 'start', status: 'completed' },
      { node_instance_id: 'process-1', node_name: '处理步骤1', node_type: 'process', status: 'completed' },
      { node_instance_id: 'process-2', node_name: '处理步骤2', node_type: 'process', status: 'running' },
      { node_instance_id: 'end-1', node_name: '结束', node_type: 'end', status: 'pending' }
    ];
    
    const testEdges = [
      { id: 'e1', source: 'start-1', target: 'process-1' },
      { id: 'e2', source: 'process-1', target: 'process-2' },
      { id: 'e3', source: 'process-2', target: 'end-1' }
    ];
    
    updateFlow(testNodes, testEdges);
  };
  
  // 测试数据2: 分支流程
  const createBranchFlow = () => {
    const testNodes = [
      { node_instance_id: 'start-1', node_name: '开始', node_type: 'start', status: 'completed' },
      { node_instance_id: 'decision-1', node_name: '决策点', node_type: 'decision', status: 'completed' },
      { node_instance_id: 'branch-a', node_name: '分支A', node_type: 'process', status: 'running' },
      { node_instance_id: 'branch-b', node_name: '分支B', node_type: 'process', status: 'pending' },
      { node_instance_id: 'merge-1', node_name: '合并', node_type: 'process', status: 'pending' },
      { node_instance_id: 'end-1', node_name: '结束', node_type: 'end', status: 'pending' }
    ];
    
    const testEdges = [
      { id: 'e1', source: 'start-1', target: 'decision-1' },
      { id: 'e2', source: 'decision-1', target: 'branch-a' },
      { id: 'e3', source: 'decision-1', target: 'branch-b' },
      { id: 'e4', source: 'branch-a', target: 'merge-1' },
      { id: 'e5', source: 'branch-b', target: 'merge-1' },
      { id: 'e6', source: 'merge-1', target: 'end-1' }
    ];
    
    updateFlow(testNodes, testEdges);
  };
  
  // 测试数据4: 连接关系优先测试（与类型顺序相反）
  const createConnectionPriorityTest = () => {
    const testNodes = [
      { node_instance_id: 'end-node', node_name: '结束节点', node_type: 'end', status: 'pending' },
      { node_instance_id: 'start-node', node_name: '开始节点', node_type: 'start', status: 'completed' },
      { node_instance_id: 'middle-node', node_name: '中间节点', node_type: 'process', status: 'running' },
    ];
    
    // 重要：连接关系与节点类型顺序相反，应该按连接关系排列
    const testEdges = [
      { id: 'e1', source: 'start-node', target: 'middle-node' },
      { id: 'e2', source: 'middle-node', target: 'end-node' },
    ];
    
    console.log('🧪 测试连接优先级：节点类型顺序 vs 连接关系顺序');
    console.log('   - 如果按类型排序: start -> process -> end');
    console.log('   - 如果按连接排序: start-node -> middle-node -> end-node');
    console.log('   - 期望结果: 严格按照连接关系排列');
    
    updateFlow(testNodes, testEdges);
  };

  // 测试数据3: 无边数据测试（自动生成连接）
  const createNoEdgesFlow = () => {
    const testNodes = [
      { node_instance_id: 'task-node', node_name: '任务节点', node_type: 'process', status: 'completed' },
      { node_instance_id: 'start-node', node_name: '开始节点', node_type: 'start', status: 'completed' },
      { node_instance_id: 'end-node', node_name: '结束节点', node_type: 'end', status: 'pending' },
    ];
    
    const testEdges: any[] = []; // 无边数据，测试自动生成
    
    console.log('🧪 测试无边数据情况：');
    console.log('   - 应该按节点类型和时间生成智能连接');
    console.log('   - 期望顺序: start -> process -> end');
    
    updateFlow(testNodes, testEdges);
  };

  // 测试数据5: 复杂连接关系测试
  const createComplexConnectionTest = () => {
    const testNodes = [
      { node_instance_id: 'A', node_name: 'Node A', node_type: 'process', status: 'completed' },
      { node_instance_id: 'B', node_name: 'Node B', node_type: 'process', status: 'completed' },
      { node_instance_id: 'C', node_name: 'Node C', node_type: 'process', status: 'running' },
      { node_instance_id: 'D', node_name: 'Node D', node_type: 'process', status: 'pending' },
      { node_instance_id: 'E', node_name: 'Node E', node_type: 'process', status: 'pending' },
    ];
    
    // 复杂的依赖关系: A -> C, B -> C, C -> D, C -> E
    const testEdges = [
      { id: 'e1', source: 'A', target: 'C' },
      { id: 'e2', source: 'B', target: 'C' },
      { id: 'e3', source: 'C', target: 'D' },
      { id: 'e4', source: 'C', target: 'E' },
    ];
    
    console.log('🧪 测试复杂连接关系：');
    console.log('   - Level 0: A, B (并行起始)');
    console.log('   - Level 1: C (合并点)');
    console.log('   - Level 2: D, E (并行结束)');
    
    updateFlow(testNodes, testEdges);
  };
  
  const updateFlow = (testNodes: any[], testEdges: any[]) => {
    console.log('🧪 [测试] 开始布局算法测试');
    console.log('   - 节点数量:', testNodes.length);
    console.log('   - 边数量:', testEdges.length);
    
    // 验证和修复边数据
    const validatedEdges = validateAndFixEdges(testNodes, testEdges);
    console.log('✅ [测试] 边验证完成，有效边:', validatedEdges.length);
    
    // 如果没有有效边，生成默认连接
    const finalEdges = validatedEdges.length > 0 ? 
      validatedEdges : 
      generateMissingConnections(testNodes);
    
    console.log('🎯 [测试] 最终边数据:', finalEdges.length);
    
    // 计算布局
    const positions = calculateDependencyBasedLayout(testNodes, finalEdges);
    console.log('📐 [测试] 布局计算完成');
    
    // 转换为ReactFlow格式
    const flowNodes: Node[] = testNodes.map((node, index) => ({
      id: node.node_instance_id,
      type: 'default',
      position: positions[node.node_instance_id] || { x: index * 200, y: 100 },
      data: { 
        label: (
          <div style={{ textAlign: 'center', padding: '8px' }}>
            <div style={{ fontWeight: 'bold', fontSize: '12px' }}>{node.node_name}</div>
            <div style={{ 
              fontSize: '10px', 
              color: getNodeStatusColor(node.status),
              marginTop: '4px',
              padding: '2px 6px',
              borderRadius: '3px',
              backgroundColor: `${getNodeStatusColor(node.status)}20`
            }}>
              {node.status}
            </div>
          </div>
        )
      },
      style: {
        background: '#fff',
        border: `2px solid ${getNodeStatusColor(node.status)}`,
        borderRadius: '8px',
        width: 120,
        fontSize: '11px'
      }
    }));
    
    const flowEdges: Edge[] = finalEdges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      style: { stroke: '#1890ff', strokeWidth: 2 },
      label: edge.label,
      labelStyle: { fontSize: '10px', fill: '#666' }
    }));
    
    setNodes(flowNodes);
    setEdges(flowEdges);
    
    console.log('🎨 [测试] ReactFlow数据更新完成');
  };
  
  useEffect(() => {
    createLinearFlow(); // 默认加载线性流程
  }, []);
  
  return (
    <div style={{ padding: '24px' }}>
      <Card title="布局算法测试页面" style={{ marginBottom: '16px' }}>
        <Space>
          <Button onClick={createLinearFlow} type="primary">
            测试线性流程
          </Button>
          <Button onClick={createBranchFlow}>
            测试分支流程
          </Button>
          <Button onClick={createNoEdgesFlow}>
            测试自动生成连接
          </Button>
          <Button onClick={createConnectionPriorityTest} style={{ backgroundColor: '#52c41a', borderColor: '#52c41a', color: 'white' }}>
            🎯 连接优先级测试
          </Button>
          <Button onClick={createComplexConnectionTest} style={{ backgroundColor: '#722ed1', borderColor: '#722ed1', color: 'white' }}>
            复杂连接测试
          </Button>
          <Button onClick={() => { setNodes([]); setEdges([]); }}>
            清空
          </Button>
        </Space>
        <div style={{ marginTop: '16px', fontSize: '12px', color: '#666' }}>
          <p><strong>测试说明：</strong></p>
          <ul>
            <li><strong>线性流程</strong>：测试基本的从左到右布局</li>
            <li><strong>分支流程</strong>：测试分支和合并的布局</li>
            <li><strong>自动生成连接</strong>：测试无边数据时的智能连接生成</li>
            <li><strong>🎯 连接优先级测试</strong>：验证连接关系优先于节点类型的关键测试</li>
            <li><strong>复杂连接测试</strong>：测试多层依赖关系的拓扑排序</li>
          </ul>
          <p style={{ marginTop: '12px', fontSize: '11px', color: '#999' }}>
            <strong>关键测试：</strong>连接优先级测试验证算法是否正确按照用户要求"优先按照连接顺序排列"
          </p>
        </div>
      </Card>
      
      <Card title="布局结果">
        <div style={{ height: '600px', width: '100%' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            fitViewOptions={{ padding: 0.1 }}
          >
            <Controls />
            <Background />
            <MiniMap />
          </ReactFlow>
        </div>
      </Card>
    </div>
  );
};

export default LayoutAlgorithmTest;