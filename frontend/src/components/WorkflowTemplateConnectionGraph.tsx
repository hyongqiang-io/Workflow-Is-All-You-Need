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
  Handle,
  Position,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './WorkflowTemplateConnectionGraph.css';

import workflowTemplateConnectionManager, {
  TemplateNode,
  TemplateEdge,
  SubdivisionConnectionDetail,
  MergeCandidate
} from '../services/workflowTemplateConnectionManager';
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

// 自定义边标签组件 - 仅在需要时使用

// 节点类型定义 - 使用模块级别的稳定引用避免重复创建警告
const STABLE_NODE_TYPES = Object.freeze({
  workflowTemplate: WorkflowTemplateNode,
});

// 边类型定义 - 使用模块级别的稳定引用避免重复创建警告
const STABLE_EDGE_TYPES = Object.freeze({});

// 树状布局算法 - 唯一合理的工作流布局
const applyTreeLayout = (nodes: any[], edges: any[]) => {
  console.log('🌳 应用树状布局');
  
  const layoutedNodes = [...nodes];
  const nodeSpacing = 300;
  const levelSpacing = 200;
  
  return applyTreeLayoutImpl(layoutedNodes, edges, nodeSpacing, levelSpacing);
};


// 树状布局实现 - 基于连接关系构建树结构
const applyTreeLayoutImpl = (nodes: any[], edges: any[], nodeSpacing: number, levelSpacing: number) => {
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
  const [selectedEdgeDetail, setSelectedEdgeDetail] = useState<SubdivisionConnectionDetail | null>(null);
  
  // 删除不必要的视图切换状态
  // const [showDetailedView, setShowDetailedView] = useState(false);
  const [detailedConnectionData, setDetailedConnectionData] = useState<DetailedConnectionData | null>(null);
  const [selectedMergeCandidates, setSelectedMergeCandidates] = useState<Set<string>>(new Set());
  const [mergePreviewData, setMergePreviewData] = useState<any>(null);
  const [showMergeModal, setShowMergeModal] = useState(false);
  
  // 使用模块级别的稳定类型引用，确保在StrictMode下也不会触发警告
  const memoizedNodeTypes = useMemo(() => STABLE_NODE_TYPES, []);
  const memoizedEdgeTypes = useMemo(() => STABLE_EDGE_TYPES, []);


  // 加载详细连接图数据（用于合并功能）
  const loadDetailedConnectionGraph = useCallback(async () => {
    console.log('🔄 加载详细工作流模板连接图 - 开始');
    console.log('   - workflowInstanceId:', workflowInstanceId);
    console.log('   - maxDepth: 10');
    console.log('   - enableMergeMode:', enableMergeMode);
    
    setIsLoading(true);
    setError(null);

    try {
      // 调用详细连接图API - 使用已配置的API实例
      const { default: api } = await import('../services/api');
      const apiUrl = `/workflow-merge/${workflowInstanceId}/detailed-connections?max_depth=10`;
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
          
          // 应用树状布局
          const layoutedNodes = applyTreeLayout(
            actualData.detailed_connection_graph.nodes, 
            actualData.detailed_connection_graph.edges
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
  }, [workflowInstanceId, enableMergeMode, selectedMergeCandidates]);

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

  // 初始加载
  // 合并模式下直接加载详细数据，不需要切换
  useEffect(() => {
    if (workflowInstanceId && enableMergeMode) {
      console.log('🔄 [WorkflowTemplateConnectionGraph] 合并模式加载:');
      console.log('   - enableMergeMode:', enableMergeMode);
      console.log('   → 加载详细数据 (合并模式)');
      loadDetailedConnectionGraph();
    }
  }, [workflowInstanceId, enableMergeMode]);

  // 处理节点点击
  const handleNodeClick = useCallback(async (_: React.MouseEvent, node: Node) => {
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
  const handleEdgeClick = useCallback(async (_: React.MouseEvent, edge: Edge) => {
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
          <button className="retry-button" onClick={loadDetailedConnectionGraph}>
            重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <WorkflowTemplateConnectionGraphInner
      {...{
        className,
        nodes,
        edges,
        onNodesChange,
        onEdgesChange,
        handleNodeClick,
        handleEdgeClick,
        memoizedNodeTypes,
        memoizedEdgeTypes,
        detailedConnectionData,
        selectedMergeCandidates,
        showMergeModal,
        setShowMergeModal,
        mergePreviewData,
        selectedEdgeDetail,
        setSelectedEdgeDetail,
        loadDetailedConnectionGraph,
        onMergeInitiated,
        handleMergeCandidateToggle
      }}
    />
  );
};

// Inner component that uses useReactFlow
const WorkflowTemplateConnectionGraphInner: React.FC<any> = (props) => {
  const {
    className,
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    handleNodeClick,
    handleEdgeClick,
    memoizedNodeTypes,
    memoizedEdgeTypes,
    detailedConnectionData,
    selectedMergeCandidates,
    showMergeModal,
    setShowMergeModal,
    mergePreviewData,
    selectedEdgeDetail,
    setSelectedEdgeDetail,
    loadDetailedConnectionGraph,
    onMergeInitiated,
    handleMergeCandidateToggle
  } = props;

  return (
    <div 
      className={`workflow-template-connection-graph ${className || ''}`}
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