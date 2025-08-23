/**
 * 工作流模板连接图组件
 * Workflow Template Connection Graph Component
 * 
 * 用于在细分预览中显示工作流模板之间的连接关系图
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  ConnectionLineType,
  MarkerType,
  Panel,
  Handle,
  Position,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './WorkflowTemplateConnectionGraph.css';

import workflowTemplateConnectionManager, {
  WorkflowTemplateConnectionData,
  ConnectionGraph,
  TemplateNode,
  TemplateEdge,
  SubdivisionConnectionDetail,
  MergeCandidate
} from '../services/workflowTemplateConnectionManager';
import { executionAPI } from '../services/api';
import WorkflowMergeModal from './WorkflowMergeModal';

// 自定义节点组件 - 使用React.memo优化重新渲染
const WorkflowTemplateNode: React.FC<{
  data: TemplateNode;
  selected: boolean;
}> = React.memo(({ data, selected }) => {
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'completed': return '#4caf50';
      case 'running': return '#ff9800';
      case 'failed': return '#f44336';
      default: return '#9e9e9e';
    }
  };

  const getCompletionPercentage = () => {
    if (data.total_nodes && data.completed_nodes !== undefined) {
      return Math.round((data.completed_nodes / data.total_nodes) * 100);
    }
    return 0;
  };

  // 检查是否是内部节点
  const isInternalNode = data.isInternalNode || data.originalType === 'internal_node';
  const nodeType = data.node_type || data.type;
  
  // 获取节点类型的显示图标
  const getNodeTypeIcon = (type: string) => {
    switch (type) {
      case 'start': return '🟢';
      case 'end': return '🔴';
      case 'processor': return '⚙️';
      case 'workflow_container': return '📦';
      default: return '🔘';
    }
  };

  return (
    <div className={`workflow-template-node ${data.is_parent ? 'parent-workflow' : 'sub-workflow'} ${isInternalNode ? 'internal-node' : ''} ${selected ? 'selected' : ''}`}>
      {/* 添加React Flow Handle组件 - 上下端连接 */}
      <Handle
        type="target"
        position={Position.Top}
        id="target"
        style={{ background: '#555' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="source"
        style={{ background: '#555' }}
      />
      
      <div className="node-header">
        <div className="node-title">
          {isInternalNode && <span className="node-type-icon">{getNodeTypeIcon(nodeType)}</span>}
          {data.label}
          {isInternalNode && (
            <span className="internal-node-badge">内部</span>
          )}
          {data.recursion_level !== undefined && data.recursion_level > 0 && (
            <span className="recursion-level-badge">L{data.recursion_level}</span>
          )}
        </div>
        {!data.is_parent && data.status && (
          <div 
            className="node-status-indicator"
            style={{ backgroundColor: getStatusColor(data.status) }}
          ></div>
        )}
      </div>
      
      {/* 内部节点显示节点类型信息 */}
      {isInternalNode && (
        <div className="node-type-info">
          <span className="node-type-label">类型: {nodeType}</span>
          {data.parentWorkflowId && (
            <span className="parent-workflow-info">属于工作流: {data.parentWorkflowId.substring(0, 8)}...</span>
          )}
        </div>
      )}
      
      <div className="node-description">
        {data.description || data.task_description}
      </div>
      
      {data.is_parent && data.connected_nodes && data.connected_nodes.length > 0 && (
        <div className="connected-nodes-info">
          <div className="info-label">细分节点:</div>
          {data.connected_nodes.slice(0, 2).map((node, index) => (
            <div key={index} className="connected-node-item">
              {node.node_name} ({node.subdivision_name})
            </div>
          ))}
          {data.connected_nodes.length > 2 && (
            <div className="more-indicator">
              还有 {data.connected_nodes.length - 2} 个...
            </div>
          )}
        </div>
      )}
      
      {!data.is_parent && data.total_nodes !== undefined && (
        <div className="sub-workflow-stats">
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ 
                width: `${getCompletionPercentage()}%`,
                backgroundColor: getStatusColor(data.status)
              }}
            ></div>
          </div>
          <div className="stats-text">
            {data.completed_nodes}/{data.total_nodes} 节点完成 ({getCompletionPercentage()}%)
          </div>
        </div>
      )}
    </div>
  );
});

// 自定义边标签组件
const SubdivisionConnectionEdge: React.FC<{
  data: TemplateEdge;
}> = ({ data }) => {
  return (
    <div className="subdivision-edge-label">
      <div className="edge-label-title">{data.label}</div>
      <div className="edge-label-detail">
        来自节点: {data.connected_node_name}
      </div>
      {data.task_title && (
        <div className="edge-label-task">
          任务: {data.task_title}
        </div>
      )}
    </div>
  );
};

// 节点类型定义 - 使用模块级别的稳定引用避免重复创建警告
const STABLE_NODE_TYPES = Object.freeze({
  workflowTemplate: WorkflowTemplateNode,
});

// 边类型定义 - 使用模块级别的稳定引用避免重复创建警告
const STABLE_EDGE_TYPES = Object.freeze({});

// 智能布局算法
const applyIntelligentLayout = (nodes: any[], edges: any[], algorithm: string) => {
  console.log('🎨 应用智能布局算法:', algorithm, '节点数:', nodes.length);
  
  const layoutedNodes = [...nodes];
  const nodeSpacing = 300; // 增加节点间距
  const levelSpacing = 200; // 增加层级间距
  
  switch (algorithm) {
    case 'hierarchical':
      return applyHierarchicalLayout(layoutedNodes, edges, nodeSpacing, levelSpacing);
    case 'tree':
      return applyTreeLayout(layoutedNodes, edges, nodeSpacing, levelSpacing);
    case 'force':
      return applyForceLayout(layoutedNodes, edges, nodeSpacing);
    case 'circular':
      return applyCircularLayout(layoutedNodes, nodeSpacing);
    case 'file_system':
      return applyFileSystemLayout(layoutedNodes, edges, nodeSpacing, levelSpacing);
    default:
      return applyHierarchicalLayout(layoutedNodes, edges, nodeSpacing, levelSpacing);
  }
};

// 层次布局 - 主工作流在上，子工作流分层显示
const applyHierarchicalLayout = (nodes: any[], edges: any[], nodeSpacing: number, levelSpacing: number) => {
  console.log('📊 应用层次布局');
  
  // 分类节点
  const workflowContainers = nodes.filter(n => n.type === 'workflow_container');
  const internalNodes = nodes.filter(n => n.type === 'internal_node');
  
  // 层级0：主工作流容器
  workflowContainers.forEach((node, index) => {
    node.position = {
      x: index * nodeSpacing,
      y: 0
    };
  });
  
  // 层级1：内部节点，根据父工作流分组
  const groupedInternalNodes = groupNodesByParent(internalNodes);
  let currentX = 0;
  
  Object.entries(groupedInternalNodes).forEach(([parentId, nodeGroup]: [string, any[]]) => {
    nodeGroup.forEach((node, index) => {
      node.position = {
        x: currentX + (index * (nodeSpacing * 0.6)),
        y: levelSpacing
      };
    });
    currentX += nodeGroup.length * (nodeSpacing * 0.6) + nodeSpacing * 0.4;
  });
  
  return nodes;
};

// 树状布局 - 根据连接关系构建树结构
const applyTreeLayout = (nodes: any[], edges: any[], nodeSpacing: number, levelSpacing: number) => {
  console.log('🌳 应用树状布局');
  
  // 构建父子关系图
  const parentChildMap = new Map();
  const childParentMap = new Map();
  
  edges.forEach(edge => {
    if (!parentChildMap.has(edge.source)) {
      parentChildMap.set(edge.source, []);
    }
    parentChildMap.get(edge.source).push(edge.target);
    childParentMap.set(edge.target, edge.source);
  });
  
  // 找到根节点（没有父节点的节点）
  const rootNodes = nodes.filter(node => !childParentMap.has(node.id));
  
  // 递归布局
  let currentY = 0;
  rootNodes.forEach((rootNode, rootIndex) => {
    layoutSubtree(rootNode, parentChildMap, nodes, rootIndex * nodeSpacing, currentY, nodeSpacing, levelSpacing);
  });
  
  return nodes;
};

// 递归布局子树
const layoutSubtree = (node: any, parentChildMap: Map<string, string[]>, allNodes: any[], startX: number, startY: number, nodeSpacing: number, levelSpacing: number) => {
  node.position = { x: startX, y: startY };
  
  const children = parentChildMap.get(node.id) || [];
  if (children.length === 0) return;
  
  const childStartX = startX - ((children.length - 1) * nodeSpacing) / 2;
  children.forEach((childId, index) => {
    const childNode = allNodes.find(n => n.id === childId);
    if (childNode) {
      layoutSubtree(childNode, parentChildMap, allNodes, childStartX + index * nodeSpacing, startY + levelSpacing, nodeSpacing, levelSpacing);
    }
  });
};

// 力导向布局 - 使用简化的力学模拟
const applyForceLayout = (nodes: any[], edges: any[], nodeSpacing: number) => {
  console.log('⚡ 应用力导向布局');
  
  // 初始化随机位置
  nodes.forEach(node => {
    node.position = {
      x: Math.random() * 800,
      y: Math.random() * 600
    };
  });
  
  // 简化的力学迭代
  for (let iter = 0; iter < 50; iter++) {
    // 排斥力
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const node1 = nodes[i];
        const node2 = nodes[j];
        const dx = node1.position.x - node2.position.x;
        const dy = node1.position.y - node2.position.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;
        
        const force = nodeSpacing * nodeSpacing / (distance * distance);
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        
        node1.position.x += fx * 0.1;
        node1.position.y += fy * 0.1;
        node2.position.x -= fx * 0.1;
        node2.position.y -= fy * 0.1;
      }
    }
    
    // 吸引力（基于连接的边）
    edges.forEach(edge => {
      const source = nodes.find(n => n.id === edge.source);
      const target = nodes.find(n => n.id === edge.target);
      if (source && target) {
        const dx = target.position.x - source.position.x;
        const dy = target.position.y - source.position.y;
        const distance = Math.sqrt(dx * dx + dy * dy) || 1;
        
        const force = distance / nodeSpacing;
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        
        source.position.x += fx * 0.05;
        source.position.y += fy * 0.05;
        target.position.x -= fx * 0.05;
        target.position.y -= fy * 0.05;
      }
    });
  }
  
  return nodes;
};

// 环形布局 - 节点分布在圆形或椭圆形上
const applyCircularLayout = (nodes: any[], nodeSpacing: number) => {
  console.log('🔄 应用环形布局');
  
  const centerX = 400;
  const centerY = 300;
  const radius = Math.max(150, nodes.length * 20);
  
  nodes.forEach((node, index) => {
    const angle = (2 * Math.PI * index) / nodes.length;
    node.position = {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle)
    };
  });
  
  return nodes;
};

// 文件系统布局 - 类似文件夹结构
const applyFileSystemLayout = (nodes: any[], edges: any[], nodeSpacing: number, levelSpacing: number) => {
  console.log('📁 应用文件系统布局');
  
  // 按节点类型分组
  const workflowContainers = nodes.filter(n => n.type === 'workflow_container');
  const internalNodes = nodes.filter(n => n.type === 'internal_node');
  
  let currentY = 0;
  
  // 主工作流在顶部
  workflowContainers.forEach((node, index) => {
    node.position = {
      x: 50,
      y: currentY
    };
    currentY += levelSpacing;
  });
  
  // 内部节点缩进显示
  internalNodes.forEach((node, index) => {
    node.position = {
      x: 250,
      y: index * (levelSpacing * 0.6)
    };
  });
  
  return nodes;
};

// 辅助函数：按父节点分组
const groupNodesByParent = (nodes: any[]): Record<string, any[]> => {
  const groups: Record<string, any[]> = {};
  
  nodes.forEach(node => {
    const parentId = node.data?.parentWorkflowId || 'default';
    if (!groups[parentId]) {
      groups[parentId] = [];
    }
    groups[parentId].push(node);
  });
  
  return groups;
};

interface Props {
  workflowInstanceId: string;
  onNodeClick?: (node: TemplateNode) => void;
  onEdgeClick?: (edge: TemplateEdge) => void;
  onMergeInitiated?: (mergePreview: any) => void;
  className?: string;
  enableMergeMode?: boolean;
}

// 合并相关接口
interface DetailedConnectionData {
  detailed_workflows: Record<string, any>;
  merge_candidates: MergeCandidate[];
  detailed_connection_graph: any;
}

const WorkflowTemplateConnectionGraph: React.FC<Props> = ({
  workflowInstanceId,
  onNodeClick,
  onEdgeClick,
  onMergeInitiated,
  className,
  enableMergeMode = false
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectionData, setConnectionData] = useState<WorkflowTemplateConnectionData | null>(null);
  const [layoutAlgorithm, setLayoutAlgorithm] = useState<'hierarchical' | 'force' | 'circular' | 'file_system'>('hierarchical');
  const [includePending, setIncludePending] = useState(false);
  const [maxDepth, setMaxDepth] = useState(10);
  const [selectedEdgeDetail, setSelectedEdgeDetail] = useState<SubdivisionConnectionDetail | null>(null);
  
  // 新增合并相关状态
  const [showDetailedView, setShowDetailedView] = useState(false);
  const [detailedConnectionData, setDetailedConnectionData] = useState<DetailedConnectionData | null>(null);
  const [selectedMergeCandidates, setSelectedMergeCandidates] = useState<Set<string>>(new Set());
  const [mergePreviewData, setMergePreviewData] = useState<any>(null);
  const [isLoadingMergePreview, setIsLoadingMergePreview] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);
  
  // 使用模块级别的稳定类型引用，确保在StrictMode下也不会触发警告
  const memoizedNodeTypes = useMemo(() => STABLE_NODE_TYPES, []);
  const memoizedEdgeTypes = useMemo(() => STABLE_EDGE_TYPES, []);

  // Auto-fit functionality
  const handleAutoFit = useCallback(() => {
    console.log('🔍 执行自动适应视图');
    // This will be handled by ReactFlow's fitView in the inner component
  }, []);

  // 加载详细连接图数据（用于合并功能）
  const loadDetailedConnectionGraph = useCallback(async () => {
    console.log('🔄 加载详细工作流模板连接图 - 开始');
    console.log('   - workflowInstanceId:', workflowInstanceId);
    console.log('   - maxDepth:', maxDepth);
    console.log('   - enableMergeMode:', enableMergeMode);
    console.log('   - showDetailedView:', showDetailedView);
    
    setIsLoading(true);
    setError(null);

    try {
      // 调用详细连接图API - 使用已配置的API实例
      const { default: api } = await import('../services/api');
      const apiUrl = `/workflow-merge/${workflowInstanceId}/detailed-connections?max_depth=${maxDepth}`;
      console.log('📡 发起API请求:', apiUrl);
      
      const response = await api.get(apiUrl);
      
      // 增强的响应调试
      console.log('📡 详细连接图API响应分析:');
      console.log('   - HTTP状态:', response.status);
      console.log('   - 响应存在:', !!response.data);
      console.log('   - 响应类型:', typeof response.data);
      console.log('   - 完整响应:', response.data);
      
      if (response.data) {
        console.log('   - 响应结构分析:');
        console.log('     - success字段:', response.data.success);
        console.log('     - message字段:', response.data.message);
        console.log('     - data字段存在:', !!response.data.data);
        console.log('     - 响应顶层键:', Object.keys(response.data));
        
        if (response.data.data) {
          console.log('     - data内容键:', Object.keys(response.data.data));
          console.log('     - detailed_connections存在:', !!response.data.data.detailed_connections);
          console.log('     - has_merge_candidates:', response.data.data.has_merge_candidates);
          console.log('     - merge_candidates_count:', response.data.data.merge_candidates_count);
        }
      }
      
      // 检查响应格式 - 处理两种可能的格式
      // 1. 包装的BaseResponse: { success: true, data: { detailed_connections: {...} } }
      // 2. 直接的数据: { detailed_connections: {...}, has_merge_candidates: true }
      
      let detailedData: any = null;
      let isWrappedResponse = false;
      
      if (response.data?.success && response.data?.data?.detailed_connections) {
        // 格式1: 包装的BaseResponse
        console.log('📡 检测到包装的BaseResponse格式');
        detailedData = response.data.data.detailed_connections;
        isWrappedResponse = true;
      } else if (response.data?.success && response.data?.data) {
        // 格式1.5: 包装的BaseResponse但detailed_connections在data内
        console.log('📡 检测到包装的BaseResponse格式(data内容直接为详细数据)');
        detailedData = response.data.data;
        isWrappedResponse = true;
      } else if (response.data?.detailed_connections) {
        // 格式2: 直接的数据格式
        console.log('📡 检测到直接的数据格式');
        detailedData = response.data;
        isWrappedResponse = false;
      }
      
      console.log('🔍 响应格式分析:');
      console.log('   - 是包装格式:', isWrappedResponse);
      console.log('   - detailedData存在:', !!detailedData);
      console.log('   - detailedData类型:', typeof detailedData);
      
      if (detailedData) {
        
        console.log('✅ 条件检查通过，开始处理数据');
        console.log('   - detailedData类型:', typeof detailedData);
        console.log('   - detailedData键:', Object.keys(detailedData));
        
        // 修正数据路径：数据在detailedData.detailed_connections中
        const actualData = detailedData.detailed_connections || detailedData;
        console.log('   - actualData类型:', typeof actualData);
        console.log('   - actualData键:', Object.keys(actualData));
        
        setDetailedConnectionData({
          detailed_workflows: actualData.detailed_workflows || {},
          merge_candidates: actualData.merge_candidates || [],
          detailed_connection_graph: actualData.detailed_connection_graph || { nodes: [], edges: [] }
        });

        // 记录合并候选信息 - 使用正确的数据路径
        const mergeCandidates = actualData.merge_candidates || [];
        console.log('📋 合并候选分析:');
        console.log('   - 候选数量:', mergeCandidates.length);
        if (mergeCandidates.length > 0) {
          console.log('   - 前3个候选:');
          mergeCandidates.slice(0, 3).forEach((candidate: any, index: number) => {
            console.log(`     候选${index + 1}:`);
            console.log(`       - ID: ${candidate.subdivision_id}`);
            console.log(`       - 节点名称: ${candidate.replaceable_node?.name}`);
            console.log(`       - 兼容性: ${candidate.compatibility?.is_compatible}`);
          });
        } else {
          console.log('   ❌ 没有可用的合并候选');
          console.log('   原因分析:');
          console.log('   - 可能没有已完成的任务细分');
          console.log('   - 可能当前工作流实例没有子工作流');
          console.log('   - 可能数据库中缺少相关记录');
        }

        // 如果有详细连接图数据，使用它来渲染
        if (actualData.detailed_connection_graph?.nodes) {
          console.log('🔄 开始处理详细连接图数据');
          console.log('   - 节点数量:', actualData.detailed_connection_graph.nodes.length);
          console.log('   - 边数量:', actualData.detailed_connection_graph.edges.length);
          
          // 应用智能布局算法
          const layoutedNodes = applyIntelligentLayout(
            actualData.detailed_connection_graph.nodes, 
            actualData.detailed_connection_graph.edges,
            layoutAlgorithm
          );
          
          const flowNodes = layoutedNodes.map((node: any) => ({
            id: node.id,
            type: 'workflowTemplate', // 统一使用workflowTemplate类型
            position: node.position,
            data: {
              ...node.data || node,
              label: node.label || node.data?.label || node.name || 'Unknown Node',
              isInternalNode: node.type === 'internal_node',
              parentWorkflowId: node.data?.parent_workflow_id,
              originalType: node.type // 保存原始类型信息
            },
            style: {
              width: node.type === 'workflow_container' ? 300 : 200,
              minHeight: node.type === 'workflow_container' ? 150 : 100,
              border: node.type === 'internal_node' ? '2px dashed #ccc' : '2px solid #666',
              backgroundColor: node.type === 'internal_node' ? '#f9f9f9' : '#ffffff'
            }
          }));

          // 验证和修复边数据 - 增强版本
          const validEdges = actualData.detailed_connection_graph.edges.filter((edge: any) => {
            // 基本字段验证
            if (!edge.id || !edge.source || !edge.target) {
              console.warn(`⚠️ 边缺少必需字段:`, edge);
              return false;
            }
            
            const hasValidSource = flowNodes.some((node: any) => node.id === edge.source);
            const hasValidTarget = flowNodes.some((node: any) => node.id === edge.target);
            
            if (!hasValidSource) {
              console.warn(`⚠️ 边 ${edge.id} 的源节点 ${edge.source} 不存在`);
            }
            if (!hasValidTarget) {
              console.warn(`⚠️ 边 ${edge.id} 的目标节点 ${edge.target} 不存在`);
            }
            
            return hasValidSource && hasValidTarget;
          });
          
          const flowEdges = validEdges.map((edge: any) => {
            // 确保所有必需字段都存在
            const processedEdge = {
              id: edge.id || `edge_${Date.now()}_${Math.random()}`,
              source: edge.source,
              target: edge.target,
              sourceHandle: edge.sourceHandle || 'source', // 添加默认的sourceHandle
              targetHandle: edge.targetHandle || 'target', // 添加默认的targetHandle
              type: edge.type === 'subdivision_connection' ? 'smoothstep' : 'default',
              animated: edge.type === 'subdivision_connection',
              style: {
                strokeWidth: edge.type === 'subdivision_connection' ? 3 : 2,
                stroke: edge.type === 'subdivision_connection' ? '#ff6b6b' : 
                       edge.type === 'workflow_connection' ? '#2196f3' : '#666',
                strokeDasharray: edge.type === 'subdivision_connection' ? '5,5' : undefined,
              },
              markerEnd: {
                type: MarkerType.ArrowClosed,
                color: edge.type === 'subdivision_connection' ? '#ff6b6b' : 
                       edge.type === 'workflow_connection' ? '#2196f3' : '#666',
                width: 20,
                height: 20,
              },
              label: edge.label || (edge.type === 'subdivision_connection' ? '细分连接' : ''),
              labelStyle: {
                fontSize: 12,
                fontWeight: 'bold',
                fill: edge.type === 'subdivision_connection' ? '#ff6b6b' : '#666',
                backgroundColor: 'rgba(255, 255, 255, 0.8)',
                padding: '2px 4px',
                borderRadius: '4px',
              },
              labelBgStyle: {
                fill: 'rgba(255, 255, 255, 0.9)',
                fillOpacity: 0.9,
              },
              data: edge.data || edge
            };
            
            // 验证处理后的边对象
            if (!processedEdge.source || !processedEdge.target) {
              console.error('❌ 处理后的边仍然缺少源或目标节点:', processedEdge);
            }
            
            return processedEdge;
          });
          
          console.log(`🔗 边数据处理结果:`);
          console.log(`   - 原始边数: ${actualData.detailed_connection_graph.edges.length}`);
          console.log(`   - 有效边数: ${validEdges.length}`);
          console.log(`   - 处理后边数: ${flowEdges.length}`);

          console.log(`📊 设置React Flow数据:`);
          console.log(`   - 节点数: ${flowNodes.length}`);
          console.log(`   - 边数: ${flowEdges.length}`);
          
          setNodes(flowNodes);
          setEdges(flowEdges);
        }

        console.log('✅ 详细工作流模板连接图加载成功');
        console.log(`   - 合并候选数: ${detailedData.merge_candidates?.length || 0}`);
        console.log(`   - 详细工作流数: ${Object.keys(detailedData.detailed_workflows || {}).length}`);
        
        // 检查合并按钮状态
        console.log('🔘 合并按钮状态检查:');
        console.log(`   - enableMergeMode: ${enableMergeMode}`);
        console.log(`   - 合并候选数量: ${mergeCandidates.length}`);
        console.log(`   - 当前选择数: ${selectedMergeCandidates.size}`);
        console.log(`   - 按钮应该灰色: ${selectedMergeCandidates.size === 0}`);
        
      } else {
        console.error('⚠️ 详细连接图API返回成功但数据格式不正确');
        console.error('   数据格式分析:');
        console.error('   - 响应数据:', response.data);
        console.error('   - 包装格式检查: success字段=', response.data?.success, ', data.detailed_connections=', !!response.data?.data?.detailed_connections);
        console.error('   - 直接格式检查: detailed_connections字段=', !!response.data?.detailed_connections);
        console.error('   预期格式: { detailed_connections: {...}, merge_candidates: [...] } 或包装的BaseResponse');
        setError('数据格式不正确，无法显示连接图');
      }

    } catch (err: any) {
      console.error('❌ 加载详细工作流模板连接图失败:');
      console.error('   - 错误类型:', typeof err);
      console.error('   - 错误对象:', err);
      console.error('   - 错误消息:', err.message);
      
      if (err.response) {
        console.error('   - HTTP状态:', err.response.status);
        console.error('   - 错误响应数据:', err.response.data);
        console.error('   - 错误响应头:', err.response.headers);
        
        let errorMessage = '加载详细连接图失败';
        if (err.response.status === 404) {
          errorMessage = '工作流实例不存在或无权限访问';
        } else if (err.response.status === 500) {
          errorMessage = '服务器内部错误，请稍后重试';
        } else if (err.response.data?.detail) {
          errorMessage = err.response.data.detail;
        } else if (err.response.data?.message) {
          errorMessage = err.response.data.message;
        }
        
        setError(errorMessage);
      } else if (err.request) {
        console.error('   - 请求对象:', err.request);
        setError('网络连接失败，请检查网络状态');
      } else {
        setError(err.message || '加载详细连接图失败，请刷新重试');
      }
    } finally {
      setIsLoading(false);
      console.log('🏁 详细连接图加载操作完成');
    }
  }, [workflowInstanceId, maxDepth, enableMergeMode, showDetailedView, selectedMergeCandidates, layoutAlgorithm]);

  // 处理合并候选选择
  const handleMergeCandidateToggle = useCallback((candidateId: string) => {
    console.log('🎯 合并候选选择操作:');
    console.log('   - 操作候选ID:', candidateId);
    console.log('   - 操作前已选择数量:', selectedMergeCandidates.size);
    console.log('   - 是否已选中:', selectedMergeCandidates.has(candidateId));
    
    // 找到对应的候选信息
    const candidate = detailedConnectionData?.merge_candidates?.find(c => c.subdivision_id === candidateId);
    if (candidate) {
      console.log('   - 候选信息:');
      console.log('     - 节点名称:', candidate.replaceable_node?.name);
      console.log('     - 节点类型:', candidate.replaceable_node?.type);
      console.log('     - 兼容性:', candidate.compatibility?.is_compatible);
      console.log('     - 问题数量:', candidate.compatibility?.issues?.length || 0);
    }
    
    setSelectedMergeCandidates(prev => {
      const newSet = new Set(prev);
      const wasSelected = newSet.has(candidateId);
      
      if (wasSelected) {
        newSet.delete(candidateId);
        console.log('   ✅ 已取消选择，新的选择数量:', newSet.size);
      } else {
        newSet.add(candidateId);
        console.log('   ✅ 已选择，新的选择数量:', newSet.size);
      }
      
      console.log('   - 所有已选择的候选ID:', Array.from(newSet));
      
      return newSet;
    });
  }, [selectedMergeCandidates, detailedConnectionData]);

  // 预览合并结果
  const handleMergePreview = useCallback(async () => {
    console.log('🚀 开始合并操作 - 详细检查:');
    console.log('='.repeat(50));
    
    // 1. 基础条件检查
    console.log('📋 步骤1: 基础条件检查');
    console.log('   - selectedMergeCandidates.size:', selectedMergeCandidates.size);
    console.log('   - detailedConnectionData存在:', !!detailedConnectionData);
    console.log('   - merge_candidates数量:', detailedConnectionData?.merge_candidates?.length || 0);
    console.log('   - enableMergeMode:', enableMergeMode);
    console.log('   - showDetailedView:', showDetailedView);
    console.log('   - isLoadingMergePreview:', isLoadingMergePreview);
    
    // 详细的失败原因分析
    if (selectedMergeCandidates.size === 0) {
      console.error('❌ 合并失败：没有选中的合并候选');
      console.error('   原因：用户还未在左下角的合并候选面板中选择任何候选项');
      console.error('   解决方案：请在左下角"📋 可合并的任务细分"面板中勾选至少一个候选项');
      setError('请先在左下角面板中选择要合并的任务细分');
      return;
    }
    
    if (!detailedConnectionData) {
      console.error('❌ 合并失败：详细连接数据为空');
      console.error('   原因：详细连接图数据未加载或加载失败');
      console.error('   解决方案：请刷新页面或重新切换到详细视图');
      setError('详细连接数据未加载，请重新切换到详细视图');
      return;
    }
    
    if (!detailedConnectionData.merge_candidates || detailedConnectionData.merge_candidates.length === 0) {
      console.error('❌ 合并失败：没有可用的合并候选');
      console.error('   原因：当前工作流实例没有可合并的任务细分');
      console.error('   解决方案：请选择一个包含已完成任务细分的工作流实例');
      setError('当前工作流没有可合并的任务细分');
      return;
    }

    // 2. 选中候选的详细信息
    console.log('\n📊 步骤2: 分析选中的合并候选');
    const selectedCandidates = detailedConnectionData.merge_candidates.filter(
      candidate => selectedMergeCandidates.has(candidate.subdivision_id)
    );
    
    console.log('   - 找到的选中候选数:', selectedCandidates.length);
    console.log('   - 预期的选中候选数:', selectedMergeCandidates.size);
    
    if (selectedCandidates.length !== selectedMergeCandidates.size) {
      console.error('❌ 合并失败：选中的候选ID与实际候选不匹配');
      console.error('   选中的ID:', Array.from(selectedMergeCandidates));
      console.error('   可用的候选ID:', detailedConnectionData.merge_candidates.map(c => c.subdivision_id));
      setError('选中的合并候选数据不匹配，请重新选择');
      return;
    }
    
    selectedCandidates.forEach((candidate, index) => {
      console.log(`   候选${index + 1}详情:`);
      console.log(`     - ID: ${candidate.subdivision_id}`);
      console.log(`     - 节点名称: ${candidate.replaceable_node?.name}`);
      console.log(`     - 节点类型: ${candidate.replaceable_node?.type}`);
      console.log(`     - 父工作流ID: ${candidate.parent_workflow_id}`);
      console.log(`     - 子工作流ID: ${candidate.sub_workflow_id}`);
      console.log(`     - 兼容性: ${candidate.compatibility?.is_compatible}`);
      if (candidate.compatibility?.issues?.length > 0) {
        console.log(`     - 兼容性问题: ${candidate.compatibility.issues.join(', ')}`);
      }
    });

    // 3. 获取父工作流ID
    console.log('\n🔍 步骤3: 确定父工作流ID');
    const parentWorkflowId = selectedCandidates[0]?.parent_workflow_id;
    console.log('   - 提取的父工作流ID:', parentWorkflowId);
    
    if (!parentWorkflowId) {
      console.error('❌ 合并失败：无法确定父工作流ID');
      console.error('   原因：选中的候选中没有有效的父工作流ID');
      console.error('   候选数据:', selectedCandidates);
      setError('无法确定父工作流ID，数据可能有误');
      return;
    }

    // 4. 执行合并预览API调用
    console.log('\n🌐 步骤4: 执行合并预览API调用');
    setIsLoadingMergePreview(true);
    setError(null);

    try {
      console.log('   - API端点:', `/workflow-merge/${parentWorkflowId}/merge-preview`);
      console.log('   - 请求数据:', selectedCandidates);
      
      // 调用合并预览API - 使用已配置的API实例
      const { default: api } = await import('../services/api');
      const response = await api.post(`/workflow-merge/${parentWorkflowId}/merge-preview`, 
        selectedCandidates
      );

      console.log('   ✅ API调用成功');
      console.log('   - 响应状态:', response.status);
      console.log('   - 响应数据:', response.data);

      if (response.data?.success) {
        console.log('   ✅ 合并预览生成成功');
        console.log('   - 预览数据:', response.data.data.merge_preview);
        
        setMergePreviewData(response.data.data.merge_preview);
        setShowMergeModal(true); // 打开完整的合并模态框

        // 通知父组件
        if (onMergeInitiated) {
          onMergeInitiated(response.data.data);
        }

        console.log('   🎉 合并预览完成，已打开合并模态框');
      } else {
        console.error('   ❌ 合并预览失败：API返回错误');
        console.error('   - 错误信息:', response.data?.message);
        setError(response.data?.message || '合并预览失败');
      }

    } catch (err: any) {
      console.error('❌ 合并预览API调用失败:');
      console.error('   - 错误类型:', typeof err);
      console.error('   - 错误对象:', err);
      console.error('   - 错误消息:', err.message);
      
      if (err.response) {
        console.error('   - HTTP状态:', err.response.status);
        console.error('   - 错误响应数据:', err.response.data);
        console.error('   - 响应头:', err.response.headers);
        
        // 根据不同的HTTP状态码提供具体的错误信息
        let errorMessage = '合并预览失败';
        if (err.response.status === 404) {
          errorMessage = '工作流不存在或无权限访问';
        } else if (err.response.status === 400) {
          errorMessage = err.response.data?.detail || err.response.data?.message || '请求参数错误';
        } else if (err.response.status === 500) {
          errorMessage = '服务器内部错误，请稍后重试';
        } else if (err.response.data?.detail) {
          errorMessage = err.response.data.detail;
        } else if (err.response.data?.message) {
          errorMessage = err.response.data.message;
        }
        
        setError(errorMessage);
      } else if (err.request) {
        console.error('   - 请求对象:', err.request);
        setError('网络连接失败，请检查网络状态');
      } else {
        setError(err.message || '未知错误，请稍后重试');
      }
    } finally {
      setIsLoadingMergePreview(false);
      console.log('🏁 合并预览操作完成');
    }
  }, [selectedMergeCandidates, detailedConnectionData, enableMergeMode, showDetailedView, isLoadingMergePreview, onMergeInitiated]);

  // 加载连接图数据
  const loadConnectionGraph = useCallback(async () => {
    console.log('🔄 加载工作流模板连接图:', workflowInstanceId);
    console.log('   - 切换到普通视图，清理详细数据状态');
    setIsLoading(true);
    setError(null);
    
    // 清理详细连接数据，确保不会干扰普通视图
    console.log('   - 清理 detailedConnectionData');
    setDetailedConnectionData(null);
    console.log('   - 清理 selectedMergeCandidates');
    setSelectedMergeCandidates(new Set());

    try {
      // 获取细分连接图数据
      const graphData = await workflowTemplateConnectionManager.getSubdivisionConnectionGraph(
        workflowInstanceId,
        { includePending, layoutAlgorithm, maxDepth }
      );

      // 同时获取完整的连接数据用于统计
      const fullConnectionData = await workflowTemplateConnectionManager.getTemplateConnections(
        workflowInstanceId, 
        maxDepth
      );
      setConnectionData(fullConnectionData);

      if (graphData.graph.nodes.length === 0) {
        setError('该工作流实例暂无模板连接关系');
        setNodes([]);
        setEdges([]);
        return;
      }

      // 转换为ReactFlow格式，并应用布局算法
      const rawNodes = graphData.graph.nodes.map((node: TemplateNode) => ({
        ...node,
        type: node.is_parent ? 'workflow_container' : 'internal_node'
      }));
      
      // 应用智能布局算法
      const layoutedNodes = applyIntelligentLayout(
        rawNodes,
        graphData.graph.edges,
        layoutAlgorithm
      );
      
      const flowNodes = layoutedNodes.map((node: any) => ({
        id: node.id,
        type: 'workflowTemplate',
        position: node.position,
        data: node,
        style: {
          width: 250,
          minHeight: node.is_parent ? 120 : 150,
        },
      }));

      const flowEdges = graphData.graph.edges.map((edge: TemplateEdge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle || 'source', // 添加默认的sourceHandle
        targetHandle: edge.targetHandle || 'target', // 添加默认的targetHandle
        type: 'smoothstep',
        animated: edge.type === 'subdivision_connection',
        style: {
          strokeWidth: edge.type === 'subdivision_connection' ? 3 : 2,
          stroke: edge.type === 'subdivision_connection' ? '#ff6b6b' : '#2196f3',
          strokeDasharray: edge.type === 'subdivision_connection' ? '5,5' : undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edge.type === 'subdivision_connection' ? '#ff6b6b' : '#2196f3',
          width: 20,
          height: 20,
        },
        label: edge.label || '',
        labelStyle: {
          fontSize: 11,
          fontWeight: 'bold',
          fill: edge.type === 'subdivision_connection' ? '#ff6b6b' : '#2196f3',
        },
        labelBgStyle: {
          fill: 'rgba(255, 255, 255, 0.9)',
          fillOpacity: 0.9,
        },
        data: edge,
      }));

      setNodes(flowNodes);
      setEdges(flowEdges);

      console.log('✅ 工作流模板连接图加载成功 (普通视图)');
      console.log('   - 节点数:', flowNodes.length);
      console.log('   - 边数:', flowEdges.length);
      console.log('   - detailedConnectionData已清理:', detailedConnectionData === null);
      console.log('   - selectedMergeCandidates已清理:', selectedMergeCandidates.size === 0);
      
    } catch (err) {
      console.error('❌ 加载工作流模板连接图失败:', err);
      setError(err instanceof Error ? err.message : '加载连接图失败');
    } finally {
      setIsLoading(false);
    }
  }, [workflowInstanceId, layoutAlgorithm, includePending, maxDepth, detailedConnectionData, selectedMergeCandidates]);

  // 初始加载
  // 根据是否需要合并功能来决定加载哪种数据
  useEffect(() => {
    if (workflowInstanceId) {
      console.log('🔄 [WorkflowTemplateConnectionGraph] 视图切换检查:');
      console.log('   - enableMergeMode:', enableMergeMode);
      console.log('   - showDetailedView:', showDetailedView);
      console.log('   - 当前detailedConnectionData存在:', !!detailedConnectionData);
      
      if (enableMergeMode) {
        // 合并模式下始终加载详细数据（包含merge_candidates）
        console.log('   → 加载详细数据 (合并模式)');
        loadDetailedConnectionGraph();
      } else {
        // 非合并模式下根据用户选择决定
        if (showDetailedView) {
          console.log('   → 加载详细数据 (用户选择)');
          loadDetailedConnectionGraph();
        } else {
          console.log('   → 加载普通数据 (用户选择)');
          loadConnectionGraph();
        }
      }
    }
  }, [workflowInstanceId, enableMergeMode, showDetailedView, layoutAlgorithm]);

  // 处理节点点击
  const handleNodeClick = useCallback(async (event: React.MouseEvent, node: Node) => {
    console.log('🖱️ 工作流模板连接图节点点击详情:');
    console.log('   - 节点ID:', node.id);
    console.log('   - 节点类型:', node.type);
    console.log('   - 节点数据:', node.data);
    console.log('   - 节点位置:', node.position);
    console.log('   - 是否选中:', node.selected);
    console.log('   - 节点样式:', node.style);
    
    // 检查节点是否是内部节点
    if (node.data.isInternalNode || node.data.originalType === 'internal_node') {
      console.log('   📍 这是一个内部节点');
      console.log('     - 父工作流ID:', node.data.parentWorkflowId);
      console.log('     - 节点类型:', node.data.node_type || node.data.originalType);
    } else if (node.data.originalType === 'workflow_container') {
      console.log('   📦 这是一个工作流容器节点');
      console.log('     - 工作流基础ID:', node.data.workflow_base_id);
      console.log('     - 连接的节点数:', node.data.connected_nodes?.length || 0);
    }
    
    // 在合并模式下的特殊处理
    if (enableMergeMode) {
      console.log('   🔄 合并模式下的节点选择:');
      console.log('     - 当前合并候选数:', detailedConnectionData?.merge_candidates?.length || 0);
      console.log('     - 已选择的候选数:', selectedMergeCandidates.size);
      
      // 检查这个节点是否关联到某个合并候选
      const relatedCandidates = detailedConnectionData?.merge_candidates?.filter(candidate => 
        candidate.replaceable_node?.node_base_id === node.data.node_base_id ||
        candidate.parent_workflow_id === node.data.workflow_base_id
      ) || [];
      
      if (relatedCandidates.length > 0) {
        console.log('   🎯 此节点关联的合并候选:');
        relatedCandidates.forEach((candidate, index) => {
          console.log(`     候选${index + 1}:`, candidate.subdivision_id);
          console.log(`       - 节点名称:`, candidate.replaceable_node?.name);
          console.log(`       - 兼容性:`, candidate.compatibility?.is_compatible);
        });
      } else {
        console.log('   ℹ️ 此节点没有关联的合并候选');
      }
    }
    
    if (onNodeClick) {
      onNodeClick(node.data);
    }
  }, [onNodeClick, enableMergeMode, detailedConnectionData, selectedMergeCandidates]);

  // 处理边点击
  const handleEdgeClick = useCallback(async (event: React.MouseEvent, edge: Edge) => {
    console.log('🖱️ 边点击:', edge.data);
    
    if (edge.data && edge.data.subdivision_id) {
      try {
        // 获取详细信息
        const detail = await workflowTemplateConnectionManager.getSubdivisionConnectionDetail(
          edge.data.subdivision_id
        );
        setSelectedEdgeDetail(detail);
      } catch (err) {
        console.error('获取细分连接详情失败:', err);
      }
    }
    
    if (onEdgeClick) {
      onEdgeClick(edge.data);
    }
  }, [onEdgeClick]);

  // 重新布局
  const handleRelayout = () => {
    if (enableMergeMode) {
      // 合并模式下始终加载详细数据
      loadDetailedConnectionGraph();
    } else {
      // 非合并模式下根据用户选择决定
      if (showDetailedView) {
        loadDetailedConnectionGraph();
      } else {
        loadConnectionGraph();
      }
    }
  };

  if (isLoading) {
    return (
      <div className={`workflow-template-connection-graph loading ${className || ''}`}>
        <div className="loading-spinner">
          <div className="spinner"></div>
          <div className="loading-text">正在加载工作流连接图...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`workflow-template-connection-graph error ${className || ''}`}>
        <div className="error-message">
          <div className="error-icon">⚠️</div>
          <div className="error-text">{error}</div>
          <button className="retry-button" onClick={loadConnectionGraph}>
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <WorkflowTemplateConnectionGraphInner
      {...{
        workflowInstanceId,
        onNodeClick,
        onEdgeClick,
        onMergeInitiated,
        className,
        enableMergeMode,
        nodes,
        edges,
        onNodesChange,
        onEdgesChange,
        handleNodeClick,
        handleEdgeClick,
        memoizedNodeTypes,
        memoizedEdgeTypes,
        layoutAlgorithm,
        setLayoutAlgorithm,
        maxDepth,
        setMaxDepth,
        includePending,
        setIncludePending,
        showDetailedView,
        setShowDetailedView,
        detailedConnectionData,
        selectedMergeCandidates,
        isLoadingMergePreview,
        error,
        setError,
        handleMergeCandidateToggle,
        handleMergePreview,
        handleRelayout,
        connectionData,
        showMergeModal,
        setShowMergeModal,
        mergePreviewData,
        setMergePreviewData,
        selectedEdgeDetail,
        setSelectedEdgeDetail,
        loadDetailedConnectionGraph,
        loadConnectionGraph
      }}
    />
  );
};

// Inner component that uses useReactFlow
const WorkflowTemplateConnectionGraphInner: React.FC<any> = (props) => {
  const { fitView } = useReactFlow();
  const {
    workflowInstanceId,
    className,
    layoutAlgorithm,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    handleNodeClick,
    handleEdgeClick,
    memoizedNodeTypes,
    memoizedEdgeTypes,
    setLayoutAlgorithm,
    maxDepth,
    setMaxDepth,
    includePending,
    setIncludePending,
    enableMergeMode,
    showDetailedView,
    setShowDetailedView,
    detailedConnectionData,
    selectedMergeCandidates,
    isLoadingMergePreview,
    error,
    setError,
    handleMergeCandidateToggle,
    handleMergePreview,
    handleRelayout,
    connectionData,
    showMergeModal,
    setShowMergeModal,
    mergePreviewData,
    setMergePreviewData,
    selectedEdgeDetail,
    setSelectedEdgeDetail,
    loadDetailedConnectionGraph,
    loadConnectionGraph,
    onMergeInitiated
  } = props;

  // Auto-fit functionality using useReactFlow
  const handleAutoFit = useCallback(() => {
    console.log('🔍 执行自动适应视图');
    fitView({ 
      padding: 0.1,
      includeHiddenNodes: false,
      minZoom: 0.2,
      maxZoom: 1.5,
      duration: 800
    });
  }, [fitView]);

  return (
    <div 
      className={`workflow-template-connection-graph ${className || ''}`} 
      data-layout={layoutAlgorithm}
      style={{ width: '100%', height: '500px' }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        nodeTypes={memoizedNodeTypes}
        edgeTypes={memoizedEdgeTypes}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
        fitViewOptions={{ 
          padding: 0.1,
          includeHiddenNodes: false,
          minZoom: 0.2,
          maxZoom: 1.5,
          duration: 800
        }}
        minZoom={0.1}
        maxZoom={2}
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      >
        <Background color="#f5f5f5" gap={16} />
        <Controls />
        
        <Panel position="top-left">
          <div className="graph-controls">
            {enableMergeMode && (
              <div className="control-group merge-header">
                <h4 style={{ margin: '0 0 8px 0', color: '#1976d2', fontSize: '14px' }}>
                  🔄 工作流合并操作
                </h4>
                <p style={{ margin: '0 0 12px 0', fontSize: '12px', color: '#666' }}>
                  在此界面选择要合并的任务细分，将子工作流整合到主工作流中
                </p>
              </div>
            )}
            
            <div className="control-group">
              <label>递归深度:</label>
              <input
                type="number"
                min="1"
                max="20"
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value) || 10)}
              />
            </div>
            
            <div className="control-group">
              <label>布局算法:</label>
              <select 
                value={layoutAlgorithm} 
                onChange={(e) => setLayoutAlgorithm(e.target.value as any)}
              >
                <option value="hierarchical">层次布局</option>
                <option value="tree">树状布局</option>
                <option value="force">力导向布局</option>
                <option value="circular">环形布局</option>
                <option value="file_system">文件系统布局</option>
              </select>
            </div>
            
            {!enableMergeMode && (
              <div className="control-group">
                <label>
                  <input
                    type="checkbox"
                    checked={includePending}
                    onChange={(e) => setIncludePending(e.target.checked)}
                  />
                  包含未完成的子工作流
                </label>
              </div>
            )}
            
            {!enableMergeMode && (
              <div className="control-group">
                <label>
                  <input
                    type="checkbox"
                    checked={showDetailedView}
                    onChange={(e) => setShowDetailedView(e.target.checked)}
                  />
                  显示详细内部节点
                </label>
              </div>
            )}
            
            {enableMergeMode && (
              <>
                
                {/* 合并操作说明 */}
                <div className="merge-status-info" style={{ 
                  fontSize: '12px', 
                  color: '#666', 
                  margin: '8px 0',
                  padding: '8px',
                  backgroundColor: '#f5f5f5',
                  borderRadius: '4px'
                }}>
                  <div>🔄 工作流合并操作</div>
                  <div>• 合并模式: {enableMergeMode ? '✅ 已启用' : '❌ 未启用'}</div>
                  <div>• 可用候选: {detailedConnectionData?.merge_candidates?.length || 0} 个</div>
                  <div>• 加载状态: {isLoadingMergePreview ? '🔄 加载中' : '✅ 就绪'}</div>
                  {error && <div style={{ color: '#f44336' }}>• 错误: {error}</div>}
                </div>
                
                <button 
                  className="merge-preview-button"
                  onClick={() => {
                    console.log('🔘 打开合并操作界面');
                    console.log('   - enableMergeMode:', enableMergeMode);
                    console.log('   - detailedConnectionData存在:', !!detailedConnectionData);
                    console.log('   - merge_candidates数量:', detailedConnectionData?.merge_candidates?.length || 0);
                    
                    // 检查基本条件
                    if (!enableMergeMode) {
                      setError('合并模式未启用');
                      return;
                    }
                    
                    if (!detailedConnectionData) {
                      setError('详细连接数据未加载，请稍候');
                      return;
                    }
                    
                    if ((detailedConnectionData?.merge_candidates?.length || 0) === 0) {
                      setError('当前工作流实例没有可合并的任务细分');
                      return;
                    }
                    
                    // 直接打开合并模态框，让用户在其中选择候选项
                    console.log('✅ 打开合并操作界面');
                    setShowMergeModal(true);
                    
                    // 设置符合WorkflowMergeModal期望格式的预览数据
                    // 从合并候选中提取正确的父工作流base_id（而不是实例ID）
                    const parentWorkflowBaseId = detailedConnectionData?.merge_candidates?.[0]?.parent_workflow_id || workflowInstanceId;
                    console.log('🔧 修正工作流ID映射:');
                    console.log('   - workflowInstanceId (实例ID):', workflowInstanceId);
                    console.log('   - parentWorkflowBaseId (基础ID):', parentWorkflowBaseId);
                    
                    setMergePreviewData({
                      parent_workflow: {
                        workflow_base_id: parentWorkflowBaseId,
                        name: '当前工作流实例',
                        current_nodes: detailedConnectionData?.detailed_connection_graph?.nodes?.length || 0,
                        current_connections: detailedConnectionData?.detailed_connection_graph?.edges?.length || 0
                      },
                      merge_summary: {
                        total_merge_candidates: detailedConnectionData?.merge_candidates?.length || 0,
                        valid_merges: detailedConnectionData?.merge_candidates?.filter((c: any) => c.compatibility?.is_compatible).length || 0,
                        invalid_merges: detailedConnectionData?.merge_candidates?.filter((c: any) => !c.compatibility?.is_compatible).length || 0,
                        net_nodes_change: 0, // 这将在用户选择候选后计算
                        net_connections_change: 0
                      },
                      merge_feasibility: {
                        can_proceed: (detailedConnectionData?.merge_candidates?.length || 0) > 0,
                        complexity_increase: 'low',
                        recommended_approach: '选择兼容的任务细分进行合并'
                      },
                      valid_merge_previews: detailedConnectionData?.merge_candidates?.filter((c: any) => c.compatibility?.is_compatible) || [],
                      invalid_merge_previews: detailedConnectionData?.merge_candidates?.filter((c: any) => !c.compatibility?.is_compatible) || []
                    });
                  }}
                  disabled={isLoadingMergePreview || !detailedConnectionData || (detailedConnectionData?.merge_candidates?.length || 0) === 0}
                  style={{
                    opacity: isLoadingMergePreview || !detailedConnectionData || (detailedConnectionData?.merge_candidates?.length || 0) === 0 ? 0.6 : 1,
                    cursor: isLoadingMergePreview || !detailedConnectionData || (detailedConnectionData?.merge_candidates?.length || 0) === 0 ? 'not-allowed' : 'pointer'
                  }}
                  title={
                    isLoadingMergePreview ? '正在加载，请稍候' :
                    !detailedConnectionData ? '详细连接数据未加载' :
                    (detailedConnectionData?.merge_candidates?.length || 0) === 0 ? '当前工作流没有可合并的任务细分' :
                    `打开合并操作界面 (${detailedConnectionData?.merge_candidates?.length || 0} 个候选)`
                  }
                >
                  {isLoadingMergePreview ? '🔄 加载中...' : 
                   !detailedConnectionData ? '⏳ 等待数据' :
                   (detailedConnectionData?.merge_candidates?.length || 0) === 0 ? '⚠️ 无可合并项' : 
                   `🚀 打开合并操作 (${detailedConnectionData?.merge_candidates?.length || 0})`}
                </button>
                
                {/* 详细的操作指导 */}
                {selectedMergeCandidates.size === 0 && (detailedConnectionData?.merge_candidates?.length || 0) > 0 && (
                  <div style={{ 
                    fontSize: '12px', 
                    color: '#ff9800', 
                    margin: '8px 0',
                    padding: '8px',
                    backgroundColor: '#fff3e0',
                    borderRadius: '4px',
                    border: '1px solid #ffcc02'
                  }}>
                    💡 操作提示: 点击此按钮将打开合并操作界面，您可以在其中选择要合并的候选项并配置合并参数。
                  </div>
                )}
                
                {(detailedConnectionData?.merge_candidates?.length || 0) === 0 && showDetailedView && (
                  <div style={{ 
                    fontSize: '12px', 
                    color: '#f44336', 
                    margin: '8px 0',
                    padding: '8px',
                    backgroundColor: '#ffebee',
                    borderRadius: '4px',
                    border: '1px solid #f44336'
                  }}>
                    ⚠️ 当前工作流实例没有可合并的任务细分。请选择一个包含已完成子工作流的实例。
                  </div>
                )}
              </>
            )}
            
            <button className="relayout-button" onClick={handleRelayout}>
              重新布局
            </button>
            
            <button className="auto-fit-button" onClick={handleAutoFit}>
              🔍 自动适应视图
            </button>
          </div>
        </Panel>
        
        <Panel position="top-right">
          <div className="graph-stats">
            {connectionData && (
              <>
                <div className="stat-item">
                  <span className="stat-label">总连接数:</span>
                  <span className="stat-value">{connectionData.statistics.total_subdivisions}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">已完成子工作流:</span>
                  <span className="stat-value">{connectionData.statistics.completed_sub_workflows}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">子工作流模板数:</span>
                  <span className="stat-value">{connectionData.statistics.unique_sub_workflows}</span>
                </div>
                {connectionData.statistics.max_recursion_depth !== undefined && (
                  <div className="stat-item">
                    <span className="stat-label">最大嵌套层级:</span>
                    <span className="stat-value">L{connectionData.statistics.max_recursion_depth}</span>
                  </div>
                )}
              </>
            )}
          </div>
        </Panel>
      </ReactFlow>

      {/* 工作流合并模态框 */}
      {showMergeModal && mergePreviewData && detailedConnectionData && (
        <WorkflowMergeModal
          isOpen={showMergeModal}
          onClose={() => setShowMergeModal(false)}
          mergePreviewData={mergePreviewData}
          selectedCandidates={detailedConnectionData.merge_candidates.filter(
            (candidate: MergeCandidate) => selectedMergeCandidates.has(candidate.subdivision_id)
          )}
          allCandidates={detailedConnectionData.merge_candidates}
          onCandidateToggle={handleMergeCandidateToggle}
          onMergeExecuted={(result) => {
            console.log('🎉 合并执行完成:', result);
            setShowMergeModal(false);
            // 合并完成后始终刷新详细连接图数据以显示最新状态
            loadDetailedConnectionGraph();
            // 通知父组件
            if (onMergeInitiated) {
              onMergeInitiated(result);
            }
          }}
        />
      )}
      {/* 边详情弹窗 */}
      {selectedEdgeDetail && (
        <div className="edge-detail-modal" onClick={() => setSelectedEdgeDetail(null)}>
          <div className="edge-detail-content" onClick={(e) => e.stopPropagation()}>
            <div className="edge-detail-header">
              <h3>细分连接详情</h3>
              <button 
                className="close-button" 
                onClick={() => setSelectedEdgeDetail(null)}
              >
                ×
              </button>
            </div>
            <div className="edge-detail-body">
              <div className="detail-section">
                <h4>细分信息</h4>
                <div className="detail-item">
                  <span className="detail-label">细分名称:</span>
                  <span className="detail-value">{selectedEdgeDetail.subdivision_name}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">细分描述:</span>
                  <span className="detail-value">{selectedEdgeDetail.subdivision_description}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">细分者:</span>
                  <span className="detail-value">{selectedEdgeDetail.subdivider_name}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">创建时间:</span>
                  <span className="detail-value">
                    {selectedEdgeDetail.created_at ? new Date(selectedEdgeDetail.created_at).toLocaleString() : '未知'}
                  </span>
                </div>
              </div>
              
              <div className="detail-section">
                <h4>原始任务</h4>
                <div className="detail-item">
                  <span className="detail-label">任务标题:</span>
                  <span className="detail-value">{selectedEdgeDetail.original_task.task_title}</span>
                </div>
              </div>
              
              <div className="detail-section">
                <h4>子工作流</h4>
                <div className="detail-item">
                  <span className="detail-label">工作流名称:</span>
                  <span className="detail-value">{selectedEdgeDetail.sub_workflow.workflow_name}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">节点进度:</span>
                  <span className="detail-value">
                    {selectedEdgeDetail.sub_workflow.completed_nodes}/{selectedEdgeDetail.sub_workflow.total_nodes}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">状态:</span>
                  <span className={`detail-value status-${selectedEdgeDetail.status}`}>
                    {selectedEdgeDetail.status}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// 包装组件提供ReactFlowProvider
const WorkflowTemplateConnectionGraphWithProvider: React.FC<Props> = (props) => {
  return (
    <ReactFlowProvider>
      <WorkflowTemplateConnectionGraph {...props} />
    </ReactFlowProvider>
  );
};

export default WorkflowTemplateConnectionGraphWithProvider;