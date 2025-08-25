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

// 工作流容器节点组件 - 专门用于显示工作流模板
const WorkflowTemplateNode: React.FC<{
  data: TemplateNode;
  selected: boolean;
  enableMergeMode?: boolean;
  onMergeToggle?: (nodeId: string, candidateId?: string) => void;
  nodeId?: string;
}> = React.memo(({ data, selected, enableMergeMode = false, onMergeToggle, nodeId }) => {
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

  // 获取工作流名称 - 优先级: workflow_name > label > name
  const getWorkflowName = () => {
    // 使用类型断言来处理额外的属性
    const nodeData = data as any;
    return nodeData.workflow_name || data.label || nodeData.name || '未命名工作流';
  };

  // 处理合并选择
  const handleMergeToggle = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (onMergeToggle) {
      // 使用传入的nodeId，如果没有则使用data.id作为备选
      const actualNodeId = nodeId || data.id;
      console.log('🔧 [WorkflowTemplateNode] 合并切换调用:', { 
        actualNodeId, 
        candidateId: data.mergeCandidateId,
        nodeIdSource: nodeId ? 'props' : 'data.id'
      });
      onMergeToggle(actualNodeId, data.mergeCandidateId);
    }
  };

  // 构建节点CSS类名
  const getNodeClassNames = () => {
    let classNames = `workflow-template-node ${data.is_parent ? 'parent-workflow' : 'sub-workflow'}`;
    if (selected) classNames += ' selected';
    if (data.isMergeSelected) classNames += ' merge-selected';
    if (data.isMergePath) classNames += ' merge-path';
    if (enableMergeMode) classNames += ' merge-mode';
    return classNames;
  };

  return (
    <div className={getNodeClassNames()}>
      {/* React Flow连接点 */}
      <Handle
        type="target"
        position={Position.Top}
        id="target"
        style={{ background: '#1976d2', border: '2px solid #fff' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="source"
        style={{ background: '#1976d2', border: '2px solid #fff' }}
      />
      
      {/* 合并模式下的选择复选框 */}
      {enableMergeMode && data.mergeCandidateId && (
        <div className="merge-checkbox-container">
          <input
            type="checkbox"
            className="merge-checkbox"
            checked={data.isMergeSelected || false}
            onChange={handleMergeToggle}
            onClick={(e) => e.stopPropagation()}
            title="选择此工作流进行合并"
          />
          <span className="merge-checkbox-label">合并</span>
        </div>
      )}
      
      <div className="workflow-header">
        <div className="workflow-icon">📦</div>
        <div className="workflow-title-section">
          <h3 className="workflow-name">{getWorkflowName()}</h3>
          {data.status && (
            <div 
              className="workflow-status-indicator"
              style={{ backgroundColor: getStatusColor(data.status) }}
              title={`状态: ${data.status}`}
            ></div>
          )}
        </div>
        {data.recursion_level !== undefined && data.recursion_level > 0 && (
          <span className="recursion-level-badge" title={`嵌套层级: ${data.recursion_level}`}>
            L{data.recursion_level}
          </span>
        )}
        {enableMergeMode && data.mergeLevel !== undefined && (
          <span className="merge-level-badge" title={`合并层级: ${data.mergeLevel}`}>
            M{data.mergeLevel}
          </span>
        )}
      </div>
      
      {/* 子工作流显示来源信息 */}
      {!data.is_parent && (data as any).source_node_name && (
        <div className="workflow-source-info">
          <div className="source-info-label">来源节点:</div>
          <div className="source-node-details">
            <span className="source-node-name">{(data as any).source_node_name}</span>
            <span className="source-node-type">({(data as any).source_node_type})</span>
          </div>
        </div>
      )}
      
      {/* 工作流描述 */}
      {(data.description || data.task_description) && (
        <div className="workflow-description">
          {data.description || data.task_description}
        </div>
      )}
      
      {/* 父工作流显示连接的子工作流信息 */}
      {data.is_parent && data.connected_nodes && data.connected_nodes.length > 0 && (
        <div className="sub-workflows-info">
          <div className="info-label">包含子工作流:</div>
          <div className="sub-workflow-count">
            {data.connected_nodes.length} 个子工作流
          </div>
          {data.connected_nodes.slice(0, 2).map((node, index) => (
            <div key={index} className="sub-workflow-item">
              {node.subdivision_name}
            </div>
          ))}
          {data.connected_nodes.length > 2 && (
            <div className="more-indicator">
              还有 {data.connected_nodes.length - 2} 个...
            </div>
          )}
        </div>
      )}
      
      {/* 子工作流显示执行进度 */}
      {!data.is_parent && data.total_nodes !== undefined && (
        <div className="workflow-progress-section">
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ 
                width: `${getCompletionPercentage()}%`,
                backgroundColor: getStatusColor(data.status)
              }}
            ></div>
          </div>
          <div className="progress-text">
            进度: {data.completed_nodes}/{data.total_nodes} ({getCompletionPercentage()}%)
          </div>
        </div>
      )}
    </div>
  );
});

// 创建一个包装组件来处理合并模式的props传递
const WorkflowTemplateNodeWrapper: React.FC<any> = React.memo((nodeProps) => {
  // 从节点数据中获取合并相关的props
  const enableMergeMode = nodeProps.data?.enableMergeMode || false;
  const onMergeToggle = nodeProps.data?.onMergeToggle;
  
  // 创建一个包装的onMergeToggle函数，确保nodeId正确传递
  const wrappedOnMergeToggle = React.useCallback((nodeId: string, candidateId?: string) => {
    if (onMergeToggle) {
      // 如果没有传入nodeId，使用当前节点的ID
      const actualNodeId = nodeId || nodeProps.id;
      console.log('🔧 [Wrapper] 合并切换调用:', { actualNodeId, candidateId, originalNodeId: nodeId });
      onMergeToggle(actualNodeId, candidateId);
    }
  }, [onMergeToggle, nodeProps.id]);
  
  return (
    <WorkflowTemplateNode
      data={nodeProps.data}
      selected={nodeProps.selected}
      enableMergeMode={enableMergeMode}
      onMergeToggle={wrappedOnMergeToggle}
      nodeId={nodeProps.id}
    />
  );
});

WorkflowTemplateNodeWrapper.displayName = 'WorkflowTemplateNodeWrapper';

// 节点类型定义 - 使用模块级别的稳定引用避免重复创建警告
const STABLE_NODE_TYPES = Object.freeze({
  workflowTemplate: WorkflowTemplateNodeWrapper,
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
  const [showMergeModal, setShowMergeModal] = useState(false);
  
  // 新增：合并相关状态
  const [mergeSelectedNodes, setMergeSelectedNodes] = useState<Set<string>>(new Set());
  const [mergePathNodes, setMergePathNodes] = useState<Set<string>>(new Set());
  
  // 使用模块级别的稳定类型引用，确保在StrictMode下也不会触发警告
  const memoizedEdgeTypes = useMemo(() => STABLE_EDGE_TYPES, []);

  // 智能合并选择逻辑：计算从根节点到选中节点的所有路径
  const calculateMergePaths = useCallback((targetNodeId: string, allEdges: any[]) => {
    console.log('🧠 计算合并路径:', targetNodeId);
    
    const pathNodes = new Set<string>();
    const visitedNodes = new Set<string>();
    
    // 构建邻接列表（上游节点）
    const upstreamMap = new Map<string, string[]>();
    allEdges.forEach((edge: any) => {
      if (!upstreamMap.has(edge.target)) {
        upstreamMap.set(edge.target, []);
      }
      upstreamMap.get(edge.target)?.push(edge.source);
    });
    
    // 递归查找所有上游节点
    const findUpstreamNodes = (nodeId: string, level: number = 0) => {
      if (visitedNodes.has(nodeId)) return;
      visitedNodes.add(nodeId);
      pathNodes.add(nodeId);
      
      console.log(`  层级${level}: 节点${nodeId}`);
      
      const upstreamNodes = upstreamMap.get(nodeId) || [];
      upstreamNodes.forEach(upstreamNodeId => {
        findUpstreamNodes(upstreamNodeId, level + 1);
      });
    };
    
    findUpstreamNodes(targetNodeId);
    console.log('  计算的路径节点:', Array.from(pathNodes));
    return pathNodes;
  }, []);

  // 处理合并节点选择切换
  const handleMergeNodeToggle = useCallback((nodeId: string, candidateId?: string) => {
    console.log('🎯 合并节点选择切换:', { nodeId, candidateId });
    
    setMergeSelectedNodes(prevSelected => {
      const newSelected = new Set(prevSelected);
      const wasSelected = newSelected.has(nodeId);
      
      if (wasSelected) {
        // 取消选择：移除节点和相关路径
        newSelected.delete(nodeId);
        console.log('  ❌ 取消选择节点:', nodeId);
      } else {
        // 选择节点：添加节点并计算路径
        newSelected.add(nodeId);
        console.log('  ✅ 选择节点:', nodeId);
        
        // 智能选择：自动选择所有前置工作流
        const mergePaths = calculateMergePaths(nodeId, edges);
        mergePaths.forEach(pathNodeId => {
          if (pathNodeId !== nodeId) {
            newSelected.add(pathNodeId);
            console.log('    ➕ 自动选择前置节点:', pathNodeId);
          }
        });
        
        // 更新路径高亮
        setMergePathNodes(mergePaths);
      }
      
      // 更新合并候选选择状态（与现有逻辑兼容）
      if (candidateId) {
        setSelectedMergeCandidates(prevCandidates => {
          const newCandidates = new Set(prevCandidates);
          if (wasSelected) {
            newCandidates.delete(candidateId);
          } else {
            newCandidates.add(candidateId);
          }
          return newCandidates;
        });
      }
      
      console.log('  最终选择的节点数量:', newSelected.size);
      return newSelected;
    });
  }, [edges, calculateMergePaths]);


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
        
        // 修正数据路径：根据日志显示，数据直接在detailedData中
        const actualData = detailedData.detailed_connections || detailedData;
        console.log('   - actualData类型:', typeof actualData);
        console.log('   - actualData键:', Object.keys(actualData));
        
        // 确保从正确的数据源获取合并候选
        const mergeCandidates = actualData.merge_candidates || detailedData.merge_candidates || [];
        console.log('   - 合并候选数据源检查:', {
          'actualData.merge_candidates': actualData.merge_candidates?.length || 0,
          'detailedData.merge_candidates': detailedData.merge_candidates?.length || 0,
          'final_count': mergeCandidates.length
        });
        
        setDetailedConnectionData({
          detailed_workflows: actualData.detailed_workflows || detailedData.detailed_workflows || {},
          merge_candidates: mergeCandidates,
          detailed_connection_graph: actualData.detailed_connection_graph || detailedData.detailed_connection_graph || { nodes: [], edges: [] }
        });
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
          
          // 🎯 只保留工作流容器节点，过滤掉内部节点
          const workflowContainerNodes = actualData.detailed_connection_graph.nodes.filter((node: any) => {
            const isWorkflowContainer = node.type === 'workflow_container';
            console.log(`   - 节点 ${node.label || node.name}: type=${node.type}, isWorkflowContainer=${isWorkflowContainer}`);
            return isWorkflowContainer;
          });
          
          console.log('🎯 过滤后的工作流容器节点数量:', workflowContainerNodes.length);
          
          // 🎯 构建工作流容器间的连接关系
          // 分析原始边数据，创建从父工作流容器到子工作流容器的连接
          const workflowConnections: any[] = [];
          const workflowContainerIds = new Set(workflowContainerNodes.map((node: any) => node.id));
          
          console.log('🔍 分析原始边数据以构建工作流容器间连接:');
          
          // 创建节点ID到工作流容器的映射
          const nodeIdToWorkflowContainer = new Map();
          
          actualData.detailed_connection_graph.nodes.forEach((node: any) => {
            if (node.data?.parent_workflow_id) {
              // 找到这个节点所属的工作流容器
              const parentWorkflowContainer = workflowContainerNodes.find((wf: any) => 
                wf.id === node.data.parent_workflow_id || 
                wf.data?.workflow_base_id === node.data.parent_workflow_id ||
                wf.data?.workflow_instance_id === node.data.parent_workflow_id
              );
              if (parentWorkflowContainer) {
                nodeIdToWorkflowContainer.set(node.id, parentWorkflowContainer.id);
                console.log(`   - 节点 ${node.id} 属于工作流容器 ${parentWorkflowContainer.id}`);
              }
            }
          });
          
          // 分析原始边，构建工作流容器间的连接
          actualData.detailed_connection_graph.edges.forEach((edge: any) => {
            const sourceNodeId = edge.source;
            const targetNodeId = edge.target;
            
            console.log(`   - 分析边: ${sourceNodeId} -> ${targetNodeId}`);
            
            // 如果目标是工作流容器，源是内部节点
            if (workflowContainerIds.has(targetNodeId)) {
              // 找到源节点所属的工作流容器
              const sourceWorkflowContainer = nodeIdToWorkflowContainer.get(sourceNodeId);
              if (sourceWorkflowContainer && sourceWorkflowContainer !== targetNodeId) {
                // 创建工作流容器间的连接
                const workflowConnection = {
                  id: `workflow_connection_${sourceWorkflowContainer}_${targetNodeId}_${sourceNodeId}`,
                  source: sourceWorkflowContainer,
                  target: targetNodeId,
                  type: 'subdivision_connection',
                  label: '子工作流引用',
                  data: {
                    connection_type: 'workflow_reference',
                    source_node_id: sourceNodeId, // 保存原始源节点ID，用于显示来源信息
                    ...edge.data
                  }
                };
                workflowConnections.push(workflowConnection);
                console.log(`   ✅ 创建工作流连接: ${sourceWorkflowContainer} -> ${targetNodeId}`);
                console.log(`      原始源节点: ${sourceNodeId}`);
              }
            }
          });
          
          console.log('🎯 构建的工作流容器间连接数量:', workflowConnections.length);
          
          // 应用树状布局（只对工作流容器）
          const layoutedNodes = applyTreeLayout(workflowContainerNodes, workflowConnections);
          
          // 🎯 识别父子工作流关系
          const childWorkflowIds = new Set(workflowConnections.map((conn: any) => conn.target));
          const parentWorkflowIds = new Set(workflowConnections.map((conn: any) => conn.source));
          
          console.log('🏗️ 工作流层级关系分析:');
          console.log(`   - 子工作流ID: ${Array.from(childWorkflowIds)}`);
          console.log(`   - 父工作流ID: ${Array.from(parentWorkflowIds)}`);
          
          // 为每个工作流收集来源节点信息
          const workflowSourceInfo = new Map();
          workflowConnections.forEach((conn: any) => {
            const targetWorkflowId = conn.target;
            const sourceNodeId = conn.data?.source_node_id;
            
            if (sourceNodeId) {
              // 找到源节点的信息
              const sourceNode = actualData.detailed_connection_graph.nodes.find((node: any) => node.id === sourceNodeId);
              if (sourceNode) {
                workflowSourceInfo.set(targetWorkflowId, {
                  source_node_name: sourceNode.label || sourceNode.name,
                  source_node_type: sourceNode.type,
                  source_workflow_id: conn.source
                });
                console.log(`   - 子工作流 ${targetWorkflowId} 来源于节点: ${sourceNode.label || sourceNode.name}`);
              }
            }
          });
          
          const flowNodes = layoutedNodes.map((node: any) => {
            // 判断是否为父工作流（有子工作流指向它的，或者不在子工作流列表中）
            const isParentWorkflow = parentWorkflowIds.has(node.id) && !childWorkflowIds.has(node.id);
            const isChildWorkflow = childWorkflowIds.has(node.id);
            
            // 获取来源信息
            const sourceInfo = workflowSourceInfo.get(node.id);
            
            // 查找关联的合并候选
            const relatedCandidate = mergeCandidates.find((candidate: any) => 
              candidate.parent_workflow_id === (node.data as any)?.workflow_base_id ||
              candidate.sub_workflow_id === (node.data as any)?.workflow_base_id
            );
            
            // 确定合并相关状态
            const isMergeSelected = mergeSelectedNodes.has(node.id);
            const isMergePath = mergePathNodes.has(node.id);
            const mergeLevel = isMergePath ? 
              Array.from(mergePathNodes).indexOf(node.id) : undefined;
            
            console.log(`   - 工作流 ${node.id}: 父工作流=${isParentWorkflow}, 子工作流=${isChildWorkflow}`);
            console.log(`     合并状态: selected=${isMergeSelected}, path=${isMergePath}, level=${mergeLevel}`);
            if (sourceInfo) {
              console.log(`     来源节点: ${sourceInfo.source_node_name} (${sourceInfo.source_node_type})`);
            }
            if (relatedCandidate) {
              console.log(`     关联合并候选: ${relatedCandidate.subdivision_id}`);
            }
            
            return {
              id: node.id,
              type: 'workflowTemplate',
              position: node.position,
              data: {
                ...node.data || node,
                // 优先使用工作流的真实名称，而不是节点标签
                label: node.data?.workflow_name || node.data?.name || node.label || node.name || 'Unknown Workflow',
                isInternalNode: false, // 工作流容器不是内部节点
                is_parent: isParentWorkflow, // 正确标识父子关系
                parentWorkflowId: node.data?.parent_workflow_id,
                originalType: node.type,
                // 工作流容器的额外信息 - 使用any类型避免类型检查
                workflow_base_id: (node.data as any)?.workflow_base_id || (node as any)?.workflow_base_id,
                workflow_name: (node.data as any)?.workflow_name || (node.data as any)?.name || (node as any)?.name,
                connected_nodes: (node.data as any)?.connected_nodes || (node as any)?.connected_nodes || [],
                // 添加来源节点信息
                source_node_name: sourceInfo?.source_node_name,
                source_node_type: sourceInfo?.source_node_type,
                source_workflow_id: sourceInfo?.source_workflow_id,
                // 合并相关属性
                isMergeSelected,
                isMergePath,
                mergeLevel,
                mergeCandidateId: relatedCandidate?.subdivision_id,
                // 添加合并模式的props，通过节点数据传递给包装组件
                enableMergeMode: enableMergeMode,
                onMergeToggle: handleMergeNodeToggle
              },
              style: {
                width: 320,  // 工作流容器统一宽度
                minHeight: isParentWorkflow ? 200 : 180,  // 父工作流稍微高一些
                border: `2px solid ${
                  isMergeSelected ? '#4caf50' : 
                  isMergePath ? '#ff9800' : 
                  isParentWorkflow ? '#1976d2' : '#7b1fa2'
                }`,
                backgroundColor: 
                  isMergeSelected ? '#e8f5e8' :
                  isMergePath ? '#fff3e0' :
                  isParentWorkflow ? '#e3f2fd' : '#f3e5f5',
                borderRadius: '8px',
                opacity: enableMergeMode && !isMergeSelected && !isMergePath && relatedCandidate ? 0.7 : 1,
                transition: 'all 0.3s ease'
              }
            };
          });

          // 验证和修复工作流连接边数据
          const validEdges = workflowConnections.filter((edge: any) => {
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
        memoizedEdgeTypes,
        detailedConnectionData,
        selectedMergeCandidates,
        showMergeModal,
        setShowMergeModal,
        selectedEdgeDetail,
        setSelectedEdgeDetail,
        loadDetailedConnectionGraph,
        onMergeInitiated,
        handleMergeCandidateToggle,
        // 新增的合并相关props
        enableMergeMode,
        mergeSelectedNodes,
        mergePathNodes,
        handleMergeNodeToggle,
        workflowInstanceId
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
    memoizedEdgeTypes,
    detailedConnectionData,
    selectedMergeCandidates,
    showMergeModal,
    setShowMergeModal,
    selectedEdgeDetail,
    setSelectedEdgeDetail,
    loadDetailedConnectionGraph,
    onMergeInitiated,
    handleMergeCandidateToggle,
    enableMergeMode,
    mergeSelectedNodes,
    mergePathNodes,
    workflowInstanceId
  } = props;

  // 直接使用稳定的节点类型引用，不再需要动态创建
  return (
    <div 
      className={`workflow-template-connection-graph ${className || ''}`}
      style={{ width: '100%', height: '500px' }}
      data-layout="tree"
      data-merge-mode={enableMergeMode ? "true" : "false"}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        nodeTypes={STABLE_NODE_TYPES}
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

      {/* 合并模式控制面板 */}
      {enableMergeMode && (
        <div className="merge-control-panel">
          <div className="control-group merge-header">
            <h4>🔀 工作流合并模式</h4>
            <p>选择子工作流将自动选择所有前置工作流</p>
          </div>
          
          <div className="merge-status-info">
            <div>已选择工作流: {mergeSelectedNodes.size} 个</div>
            <div>路径高亮节点: {Array.from(mergePathNodes || new Set()).length} 个</div>
            <div>合并候选: {detailedConnectionData?.merge_candidates?.length || 0} 个</div>
            <div>可执行合并: {selectedMergeCandidates.size > 0 ? '是' : '否'}</div>
          </div>
          
          <button 
            className="merge-preview-button"
            disabled={selectedMergeCandidates.size === 0}
            onClick={() => setShowMergeModal(true)}
          >
            {selectedMergeCandidates.size === 0 ? '请选择要合并的工作流' : `开始合并 (${selectedMergeCandidates.size}个)`}
          </button>
          
          {selectedMergeCandidates.size === 0 && detailedConnectionData?.merge_candidates?.length === 0 && (
            <div className="merge-no-candidates-warning">
              ⚠️ 没有可用的合并候选。可能原因：
              <br />• 没有已完成的任务细分
              <br />• 当前工作流实例没有子工作流
            </div>
          )}
          
          <div className="merge-operation-tip">
            💡 提示：点击子工作流的合并复选框将自动选择所有前置工作流，形成完整的合并路径。
          </div>
        </div>
      )}

      {/* 工作流合并模态框 */}
      {showMergeModal && detailedConnectionData && (() => {
        // 从合并候选中获取正确的父工作流基础ID
        const firstCandidate = detailedConnectionData.merge_candidates[0];
        const parentWorkflowBaseId = firstCandidate?.parent_workflow_id || workflowInstanceId || 'unknown';
        
        console.log('🔍 [合并模态框] 工作流ID检查:', {
          'workflowInstanceId': workflowInstanceId,
          'firstCandidate.parent_workflow_id': firstCandidate?.parent_workflow_id,
          'selected_parentWorkflowBaseId': parentWorkflowBaseId,
          'detailedConnectionData.detailed_workflows': Object.keys(detailedConnectionData.detailed_workflows || {})
        });
        
        return (
          <WorkflowMergeModal
            isOpen={showMergeModal}
            onClose={() => setShowMergeModal(false)}
            mergePreviewData={{
              parent_workflow: {
                workflow_base_id: parentWorkflowBaseId,
                name: '当前工作流',
                current_nodes: 0,
                current_connections: 0
              },
              merge_summary: {
                total_merge_candidates: detailedConnectionData.merge_candidates.length,
                valid_merges: selectedMergeCandidates.size,
                invalid_merges: 0,
                net_nodes_change: selectedMergeCandidates.size * 3, // 估算
                net_connections_change: selectedMergeCandidates.size * 2 // 估算
              },
              merge_feasibility: {
                can_proceed: selectedMergeCandidates.size > 0,
                complexity_increase: selectedMergeCandidates.size > 2 ? 'high' : 'medium',
                recommended_approach: '直接合并到新工作流'
              },
              valid_merge_previews: Array.from(selectedMergeCandidates).map((candidateId) => {
                const candidateIdStr = candidateId as string;
                const candidate = detailedConnectionData.merge_candidates.find((c: MergeCandidate) => c.subdivision_id === candidateIdStr);
                return {
                  candidate_id: candidateIdStr,
                  target_node: candidate?.replaceable_node || { node_base_id: '', name: 'Unknown', type: 'unknown' },
                  replacement_info: {
                    sub_workflow_name: `子工作流_${candidateIdStr.slice(0, 8)}`,
                    nodes_to_add: 3,
                    connections_to_add: 2
                  }
                };
              }),
              invalid_merge_previews: []
            }}
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
      )})()}
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