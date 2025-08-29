import React, { useState, useEffect, useCallback } from 'react';
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

// =============================================================================
// 简化的数据结构定义
// =============================================================================

interface WorkflowData {
  id: string;
  name: string;
  status: 'completed' | 'running' | 'failed' | 'pending';
  description?: string;
  total_nodes?: number;
  completed_nodes?: number;
  workflow_base_id?: string;
  subdivision_id?: string;  // subdivision的唯一标识
  subdivision_name?: string; // subdivision的名称
  parent_subdivision_id?: string; // 父subdivision的ID（用于构建层级关系）
  nodeSourceType?: 'parent_workflow' | 'subdivision'; // 节点来源类型
  parentWorkflowId?: string; // 父工作流ID（用于构建树结构）
  parentNodeInfo?: {        // 父节点信息（节点级别连接）
    node_instance_id: string;
    node_base_id: string;
    node_name: string;
    node_type: string;
  };
}

interface ConnectionData {
  id: string;
  source: string;
  target: string;
  label?: string;
}

// =============================================================================
// 简化的布局算法
// =============================================================================

const calculateTreeLayout = (workflows: WorkflowData[], connections: ConnectionData[]): Map<string, { x: number; y: number }> => {
  console.log('🌳 [模板连接图] 开始计算统一树状布局:', {
    workflowsCount: workflows.length,
    connectionsCount: connections.length,
    workflows: workflows.map(w => ({ id: w.id, name: w.name, subdivisionId: w.subdivision_id })),
    connections: connections.map(c => ({ id: c.id, source: c.source, target: c.target }))
  });
  
  const positions = new Map<string, { x: number; y: number }>();
  const baseHorizontalSpacing = 400; // 基础水平间距
  const baseVerticalSpacing = 300;   // 基础垂直间距
  
  // 动态间距调整：根据层级数和节点数调整间距
  const maxExpectedLevels = 8; // 期望的最大层级数
  const dynamicVerticalSpacing = Math.max(
    200, // 最小垂直间距
    Math.min(baseVerticalSpacing, baseVerticalSpacing * (maxExpectedLevels / Math.max(1, workflows.length / 2)))
  );
  const dynamicHorizontalSpacing = Math.max(
    300, // 最小水平间距  
    Math.min(baseHorizontalSpacing, baseHorizontalSpacing * (10 / Math.max(1, workflows.length)))
  );
  
  console.log('🌳 [模板连接图] 动态间距调整:', {
    workflows: workflows.length,
    dynamicVerticalSpacing,
    dynamicHorizontalSpacing,
    baseVertical: baseVerticalSpacing,
    baseHorizontal: baseHorizontalSpacing
  });
  
  // 构建父子关系映射
  const parentChildMap = new Map<string, string[]>();
  const childParentMap = new Map<string, string>();
  
  connections.forEach(conn => {
    if (!parentChildMap.has(conn.source)) {
      parentChildMap.set(conn.source, []);
    }
    parentChildMap.get(conn.source)!.push(conn.target);
    childParentMap.set(conn.target, conn.source);
  });
  
  // 找到所有潜在根节点（没有父节点的节点）
  const potentialRoots = workflows.filter(w => !childParentMap.has(w.id));
  console.log('🌳 [模板连接图] 找到潜在根节点:', potentialRoots.map(r => ({ id: r.id, name: r.name })));
  
  // 核心改进：创建虚拟根节点，将所有真实根节点作为其子节点
  let actualRootNode: string;
  
  if (potentialRoots.length === 1) {
    // 如果只有一个根节点，直接使用它
    actualRootNode = potentialRoots[0].id;
    console.log('🌳 [模板连接图] 使用单一根节点:', actualRootNode);
  } else if (potentialRoots.length > 1) {
    // 如果有多个根节点，创建虚拟根并连接
    console.log('🌳 [模板连接图] 检测到多个根节点，创建统一树结构');
    
    // 选择第一个根节点作为主根
    actualRootNode = potentialRoots[0].id;
    
    // 将其他根节点作为第一个根节点的子节点
    const mainRootChildren = parentChildMap.get(actualRootNode) || [];
    for (let i = 1; i < potentialRoots.length; i++) {
      const otherRootId = potentialRoots[i].id;
      mainRootChildren.push(otherRootId);
      childParentMap.set(otherRootId, actualRootNode);
    }
    parentChildMap.set(actualRootNode, mainRootChildren);
    
    console.log('🌳 [模板连接图] 统一树结构创建完成，主根节点:', actualRootNode, '子节点:', mainRootChildren);
  } else {
    // 如果没有根节点（所有节点都有父节点，可能存在循环），选择第一个节点作为根
    if (workflows.length > 0) {
      actualRootNode = workflows[0].id;
      // 清除这个节点的父关系，使其成为根节点
      if (childParentMap.has(actualRootNode)) {
        const formerParent = childParentMap.get(actualRootNode)!;
        const siblings = parentChildMap.get(formerParent) || [];
        parentChildMap.set(formerParent, siblings.filter(id => id !== actualRootNode));
        childParentMap.delete(actualRootNode);
        console.log('🌳 [模板连接图] 强制指定根节点:', actualRootNode);
      }
    } else {
      console.warn('🌳 [模板连接图] 没有可用的工作流节点');
      return positions;
    }
  }
  
  // 构建统一的层级结构
  const levels: string[][] = [];
  const nodeLevels = new Map<string, number>();
  
  // BFS构建层级，从统一的根节点开始
  const queue: Array<{ nodeId: string; level: number }> = [];
  
  // 初始化统一根节点
  queue.push({ nodeId: actualRootNode, level: 0 });
  
  while (queue.length > 0) {
    const { nodeId, level } = queue.shift()!;
    
    if (nodeLevels.has(nodeId)) continue; // 避免重复处理和循环
    
    nodeLevels.set(nodeId, level);
    
    // 确保levels数组有足够的层级
    while (levels.length <= level) {
      levels.push([]);
    }
    levels[level].push(nodeId);
    
    // 添加子节点到队列
    const children = parentChildMap.get(nodeId) || [];
    children.forEach(childId => {
      if (!nodeLevels.has(childId)) {
        queue.push({ nodeId: childId, level: level + 1 });
      }
    });
  }
  
  // 确保所有工作流都被包含在树中（处理孤立节点）
  workflows.forEach(workflow => {
    if (!nodeLevels.has(workflow.id)) {
      console.log('🌳 [模板连接图] 发现孤立节点，添加到最后一层:', workflow.id);
      const lastLevel = Math.max(0, levels.length - 1);
      levels[lastLevel].push(workflow.id);
      nodeLevels.set(workflow.id, lastLevel);
    }
  });
  
  console.log('🌳 [模板连接图] 统一层级结构:', {
    levelCount: levels.length,
    totalNodes: Array.from(nodeLevels.keys()).length,
    levels: levels.map((nodes, index) => ({ level: index, nodeCount: nodes.length, nodes }))
  });
  
  // 计算每层节点的位置，使用动态间距和深层级优化
  levels.forEach((levelNodes, levelIndex) => {
    // 使用动态垂直间距，深层级适当压缩
    const levelSpacingMultiplier = levelIndex > 5 ? 0.8 : 1; // 第6层开始压缩20%
    const levelY = levelIndex * dynamicVerticalSpacing * levelSpacingMultiplier;
    
    if (levelIndex === 0) {
      // 根节点居中
      positions.set(actualRootNode, { x: 0, y: levelY });
      console.log(`🌳 [模板连接图] 统一根节点 ${actualRootNode} 位置: (0, ${levelY})`);
    } else {
      // 子节点基于父节点位置分布
      const processedNodes = new Set<string>();
      
      levelNodes.forEach(nodeId => {
        if (processedNodes.has(nodeId)) return;
        
        const parentId = childParentMap.get(nodeId);
        if (!parentId) {
          // 孤立节点，放在当前层的边缘
          const edgeX = levelNodes.length * dynamicHorizontalSpacing / 2;
          positions.set(nodeId, { x: edgeX, y: levelY });
          processedNodes.add(nodeId);
          console.log(`🌳 [模板连接图] 孤立节点 ${nodeId} 位置: (${edgeX}, ${levelY})`);
          return;
        }
        
        const parentPos = positions.get(parentId);
        if (!parentPos) return;
        
        // 获取同一父节点的所有子节点（在当前层级）
        const siblings = parentChildMap.get(parentId) || [];
        const currentSiblings = siblings.filter(siblingId => 
          nodeLevels.get(siblingId) === levelIndex && !processedNodes.has(siblingId)
        );
        
        // 计算子节点的位置，深层级适当压缩水平间距
        if (currentSiblings.length === 1) {
          // 只有一个子节点，直接放在父节点下方
          positions.set(nodeId, { x: parentPos.x, y: levelY });
          console.log(`🌳 [模板连接图] 单子节点 ${nodeId} 位置: (${parentPos.x}, ${levelY})`);
        } else {
          // 多个子节点，在父节点下方分布
          const horizontalSpacingMultiplier = levelIndex > 4 ? 0.7 : 1; // 第5层开始压缩30%
          const siblingSpacing = Math.max(
            dynamicHorizontalSpacing * horizontalSpacingMultiplier, 
            250 // 最小间距
          );
          const totalSiblingWidth = (currentSiblings.length - 1) * siblingSpacing;
          const startX = parentPos.x - totalSiblingWidth / 2;
          
          currentSiblings.forEach((siblingId, index) => {
            const x = startX + index * siblingSpacing;
            positions.set(siblingId, { x, y: levelY });
            console.log(`🌳 [模板连接图] 多子节点 ${siblingId} 位置: (${x}, ${levelY}) [${index+1}/${currentSiblings.length}] 层级${levelIndex}`);
          });
        }
        
        // 标记这些节点已处理
        currentSiblings.forEach(siblingId => processedNodes.add(siblingId));
      });
    }
  });
  
  console.log('✅ [模板连接图] 统一树状布局计算完成:', {
    positionsCount: positions.size,
    maxLevel: levels.length - 1,
    positions: Array.from(positions.entries()).map(([id, pos]) => ({ id, x: pos.x, y: pos.y }))
  });
  
  return positions;
};

// =============================================================================
// 简化的工作流节点组件
// =============================================================================

const WorkflowNode: React.FC<{ data: WorkflowData & { nodeType?: string; isRoot?: boolean; hasChildren?: boolean; isSubdivision?: boolean; level?: number } }> = ({ data }) => {
  const getStatusColor = (status: string): string => {
    const colors = {
      completed: '#4caf50',
      running: '#ff9800', 
      failed: '#f44336',
      pending: '#9e9e9e'
    };
    return colors[status as keyof typeof colors] || colors.pending;
  };
  
  const getCompletionRate = (): number => {
    if (!data.total_nodes || !data.completed_nodes) return 0;
    return Math.round((data.completed_nodes / data.total_nodes) * 100);
  };
  
  // 根据节点类型和层级选择图标和样式
  const getNodeIcon = (): string => {
    if (data.isRoot) return '🌳'; // 根节点用树图标
    if (data.isSubdivision) {
      // 根据层级选择不同的子工作流图标
      const level = data.level || 0;
      if (level === 1) return '🔗'; // 第一层子工作流
      if (level === 2) return '📎'; // 第二层子工作流
      if (level >= 3) return '🔸'; // 更深层级子工作流
    }
    return '📦'; // 默认节点用包装图标
  };
  
  const getNodeTypeLabel = (): string => {
    if (data.isRoot) return '根工作流';
    if (data.isSubdivision) {
      const level = data.level || 0;
      if (level === 1) return '一级子工作流';
      if (level === 2) return '二级子工作流';
      if (level >= 3) return `${level}级子工作流`;
    }
    return '工作流';
  };
  
  // 根据层级获取节点边框样式
  const getNodeBorderStyle = (): React.CSSProperties => {
    const level = data.level || 0;
    if (data.isRoot) {
      return { borderColor: '#4caf50', borderWidth: '3px' };
    }
    if (data.isSubdivision) {
      if (level === 1) return { borderColor: '#ff9800', borderWidth: '3px' };
      if (level === 2) return { borderColor: '#9c27b0', borderWidth: '2px' };
      if (level >= 3) return { borderColor: '#607d8b', borderWidth: '2px', borderStyle: 'dashed' };
    }
    return { borderColor: '#1976d2', borderWidth: '2px' };
  };
  
  return (
    <div className="workflow-node" style={getNodeBorderStyle()}>
      <Handle type="target" position={Position.Top} />
      <Handle type="source" position={Position.Bottom} />
      
      <div className="node-header">
        <div className="node-icon">{getNodeIcon()}</div>
        <div className="node-title-section">
          <h3 className="node-name">{data.name}</h3>
          <div className="node-type-badge">{getNodeTypeLabel()}</div>
        </div>
        <div 
          className="status-indicator"
          style={{ backgroundColor: getStatusColor(data.status) }}
          title={`状态: ${data.status}`}
        />
      </div>
      
      {/* 层级指示器 - 深层级节点显示层级信息 */}
      {data.isSubdivision && (data.level || 0) > 0 && (
        <div className="level-indicator">
          <span className="level-badge">层级 {data.level}</span>
        </div>
      )}
      
      {/* 细分信息显示 */}
      {data.isSubdivision && data.subdivision_name && (
        <div className="subdivision-info">
          <span className="subdivision-label">细分名称:</span>
          <span className="subdivision-name">{data.subdivision_name}</span>
        </div>
      )}
      
      {data.description && (
        <div className="node-description">{data.description}</div>
      )}
      
      {data.total_nodes && (
        <div className="progress-section">
          <div className="progress-header">
            <span>执行进度</span>
            <span>{data.completed_nodes || 0}/{data.total_nodes}</span>
          </div>
          <div className="progress-bar">
            <div 
              className="progress-fill"
              style={{ 
                width: `${getCompletionRate()}%`,
                backgroundColor: getStatusColor(data.status)
              }}
            />
          </div>
          <div className="progress-text">
            完成率: {getCompletionRate()}%
          </div>
        </div>
      )}
      
      {/* 连接信息 */}
      <div className="connection-info">
        {data.hasChildren && (
          <div className="connection-indicator children">
            <span>👇 包含子工作流</span>
          </div>
        )}
        {!data.isRoot && (
          <div className="connection-indicator parent">
            <span>👆 来源于父工作流</span>
          </div>
        )}
      </div>
    </div>
  );
};

// =============================================================================
// 简化的数据处理 - 专注核心流程：查询 → 构建 → 可视化
// =============================================================================

const processNodeMappingAPIData = (response: any): { workflows: WorkflowData[], connections: ConnectionData[] } => {
  const workflows: WorkflowData[] = [];
  const connections: ConnectionData[] = [];
  
  console.log('🔍 [模板连接图] 开始处理节点映射API响应数据:', response);
  
  try {
    // 处理新的节点映射API响应 - 修复数据提取逻辑
    console.log('🔍 [模板连接图] API响应完整结构:', {
      responseType: typeof response,
      responseKeys: Object.keys(response || {}),
      hasData: !!response?.data,
      dataType: typeof response?.data,
      dataContent: response?.data
    });
    
    // 修复数据提取 - API返回的是 {success: true, data: {...}}，前端axios已经提取了data
    const actualData = response || {};
    const templateConnections = actualData?.template_connections || [];
    const detailedWorkflows = actualData?.detailed_workflows || {};
    
    console.log('🔍 [模板连接图] 解析节点映射数据结构:', {
      hasData: !!actualData,
      templateConnectionsCount: templateConnections.length,
      detailedWorkflowsCount: Object.keys(detailedWorkflows).length,
      nodeLevelMapping: actualData.node_level_mapping,
      supportsRecursiveSubdivision: actualData.supports_recursive_subdivision,
      rawData: actualData // 添加原始数据用于调试
    });
    
    // 如果没有数据，记录详细信息用于调试
    if (templateConnections.length === 0 && Object.keys(detailedWorkflows).length === 0) {
      console.log('🔍 [模板连接图] 没有数据，记录详细调试信息:', {
        fullResponse: response,
        dataKeys: Object.keys(actualData),
        templateConnectionsType: typeof templateConnections,
        detailedWorkflowsType: typeof detailedWorkflows,
        templateConnectionsValue: templateConnections,
        detailedWorkflowsValue: detailedWorkflows
      });
    }
    // 基于subdivision实例去重，而不是工作流模板去重
    // 每个subdivision_id代表一个唯一的子工作流实例，即使它们来自同一个工作流模板
    const uniqueSubdivisions = new Map<string, WorkflowData>();
    const parentWorkflows = new Map<string, WorkflowData>();
    const nodeSubdivisionConnections: Array<{
      subdivisionId: string;
      parentWorkflowId: string;
      subWorkflowId: string; // 这里使用subdivision_id作为唯一标识
      subdivisionName: string;
      parentNodeId: string;
      parentNodeName: string;
      parentNodeType: string;
    }> = [];
    
    // 步骤1: 处理详细工作流信息 - 只添加真正的根工作流(depth=0)
    Object.entries(detailedWorkflows).forEach(([workflowId, workflowDetail]: [string, any]) => {
      console.log(`🔍 [模板连接图] 处理工作流详情: ${workflowId}`, workflowDetail);
      
      // 只添加根工作流(depth=0)到父工作流映射，避免重复
      if (workflowDetail.depth === 0 && !parentWorkflows.has(workflowId)) {
        const workflowData: WorkflowData = {
          id: workflowId,
          name: workflowDetail.workflow_name || 'Unknown Workflow',
          status: workflowDetail.status || 'pending',
          description: workflowDetail.workflow_description || '',
          total_nodes: workflowDetail.total_nodes || 0,
          completed_nodes: workflowDetail.completed_nodes || 0,
          workflow_base_id: workflowId,
          nodeSourceType: 'parent_workflow'
        };
        parentWorkflows.set(workflowId, workflowData);
        console.log(`📦 [模板连接图] 添加根工作流: ${workflowData.name} (深度: ${workflowDetail.depth})`);
      } else if (workflowDetail.depth > 0) {
        console.log(`🔄 [模板连接图] 跳过子工作流(将通过subdivision创建): ${workflowDetail.workflow_name} (深度: ${workflowDetail.depth})`);
      }
    });
    
    // 步骤2: 处理每个subdivision连接，为每个subdivision_id创建独立的子工作流节点
    templateConnections.forEach((connection: any, index: number) => {
      console.log(`🔍 [模板连接图] 处理subdivision连接 ${index + 1}:`, connection);
      
      const parentWorkflow = connection.parent_workflow;
      const subWorkflow = connection.sub_workflow;
      const parentNode = connection.parent_node;
      const subdivisionId = connection.subdivision_id;
      const subdivisionName = connection.subdivision_name;
      const parentSubdivisionId = connection.parent_subdivision_id;
      
      console.log(`🔍 [模板连接图] 连接详细信息:`, {
        subdivisionId,
        subdivisionName,
        parentSubdivisionId,
        hasSubWorkflow: !!subWorkflow?.workflow_base_id,
        subWorkflowId: subWorkflow?.workflow_base_id,
        subWorkflowName: subWorkflow?.workflow_name
      });
      
      // 不再在这里添加父工作流，因为已经在步骤1中通过depth=0筛选添加了
      
      // 为每个subdivision_id创建独立的子工作流节点（重要修复）
      if (subWorkflow?.workflow_base_id && subdivisionId) {
        // 使用subdivision_id作为唯一标识，而不是workflow_base_id
        const uniqueSubId = subdivisionId; // 每个subdivision实例都是唯一的
        
        console.log(`🔧 [模板连接图] 准备添加subdivision节点: ${uniqueSubId}`);
        
        if (!uniqueSubdivisions.has(uniqueSubId)) {
          const subData: WorkflowData = {
            id: uniqueSubId, // 关键修复：使用subdivision_id而不是workflow_base_id
            name: `${subdivisionName} (${subWorkflow.workflow_name})`, // 显示subdivision名称
            status: subWorkflow.status || 'pending',
            description: subWorkflow.workflow_description || '',
            total_nodes: subWorkflow.total_nodes,
            completed_nodes: subWorkflow.completed_nodes,
            workflow_base_id: subWorkflow.workflow_base_id, // 保留原始workflow_base_id用于引用
            nodeSourceType: 'subdivision',
            subdivision_id: subdivisionId,
            subdivision_name: subdivisionName,
            parent_subdivision_id: parentSubdivisionId, // 确保包含父subdivision ID
            parentWorkflowId: parentWorkflow?.workflow_base_id,
            parentNodeInfo: parentNode ? {
              node_instance_id: parentNode.node_instance_id,
              node_base_id: parentNode.node_base_id || parentNode.node_instance_id,
              node_name: parentNode.node_name,
              node_type: parentNode.node_type
            } : undefined
          };
          uniqueSubdivisions.set(uniqueSubId, subData);
          console.log(`📦 [模板连接图] ✅ 添加subdivision节点: ${subData.name} (ID: ${uniqueSubId}, 父级ID: ${parentSubdivisionId}, 来源节点: ${parentNode?.node_name})`);
        } else {
          console.log(`🔄 [模板连接图] Subdivision节点已存在: ${uniqueSubId}`);
        }
      } else {
        console.warn(`⚠️ [模板连接图] 无法添加subdivision节点:`, {
          hasSubWorkflow: !!subWorkflow?.workflow_base_id,
          hasSubdivisionId: !!subdivisionId,
          subWorkflow,
          subdivisionId
        });
      }
      
      // 记录节点级别的subdivision连接关系 - 使用subdivision_id作为目标
      if (parentWorkflow?.workflow_base_id && subWorkflow?.workflow_base_id && parentNode && subdivisionId) {
        nodeSubdivisionConnections.push({
          subdivisionId: subdivisionId,
          parentWorkflowId: parentWorkflow.workflow_base_id,
          subWorkflowId: subdivisionId, // 连接到subdivision实例，不是工作流模板
          subdivisionName: subdivisionName,
          parentNodeId: parentNode.node_base_id || parentNode.node_instance_id,
          parentNodeName: parentNode.node_name,
          parentNodeType: parentNode.node_type
        });
      }
    });
    
    // 步骤3: 合并所有工作流（父工作流 + subdivision实例）
    workflows.push(...Array.from(parentWorkflows.values()));
    workflows.push(...Array.from(uniqueSubdivisions.values()));
    
    // 步骤4: 基于节点级别的subdivision连接关系创建边 - 修复：只为根级subdivision创建到父工作流的连接
    nodeSubdivisionConnections.forEach(subConn => {
      // 检查这个subdivision是否是根级subdivision（没有parent_subdivision_id）
      const subdivisionConnection = templateConnections.find((tc: any) => tc.subdivision_id === subConn.subdivisionId);
      const isRootSubdivision = !subdivisionConnection?.parent_subdivision_id;
      
      // 只为根级subdivision创建到父工作流的连接
      if (isRootSubdivision) {
        const connectionData: ConnectionData = {
          id: subConn.subdivisionId,
          source: subConn.parentWorkflowId,
          target: subConn.subWorkflowId,
          label: `${subConn.parentNodeName}\n→ ${subConn.subdivisionName}`
        };
        connections.push(connectionData);
        console.log(`🔗 [模板连接图] 添加根级subdivision连接: ${subConn.parentWorkflowId}[${subConn.parentNodeName}] -> ${subConn.subWorkflowId} (${subConn.subdivisionName})`);
      } else {
        console.log(`🔄 [模板连接图] 跳过非根级subdivision的基本连接，使用层级连接: ${subConn.subdivisionName} (父级: ${subdivisionConnection?.parent_subdivision_id})`);
      }
    });
    
    // 步骤5: 处理subdivision之间的层级关系 - 新增
    // 为每个有parent_subdivision_id的subdivision创建到其父subdivision的连接
    console.log('🔗 [模板连接图] 开始处理subdivision层级关系:', {
      templateConnectionsCount: templateConnections.length,
      uniqueSubdivisionsKeys: Array.from(uniqueSubdivisions.keys()),
      templateConnections: templateConnections.map((tc: any) => ({
        subdivision_id: tc.subdivision_id,
        subdivision_name: tc.subdivision_name,
        parent_subdivision_id: tc.parent_subdivision_id
      }))
    });
    
    templateConnections.forEach((connection: any) => {
      const parentSubdivisionId = connection.parent_subdivision_id;
      if (parentSubdivisionId) {
        console.log(`🔍 [模板连接图] 检查层级关系: ${connection.subdivision_id} -> 父级: ${parentSubdivisionId}`);
        
        // 查找父subdivision对应的工作流节点
        const parentSubdivision = uniqueSubdivisions.get(parentSubdivisionId);
        const currentSubdivision = uniqueSubdivisions.get(connection.subdivision_id);
        
        console.log(`🔍 [模板连接图] 层级连接检查结果:`, {
          parentSubdivisionExists: !!parentSubdivision,
          currentSubdivisionExists: !!currentSubdivision,
          parentSubdivisionId: parentSubdivisionId,
          currentSubdivisionId: connection.subdivision_id,
          parentName: parentSubdivision?.subdivision_name,
          currentName: currentSubdivision?.subdivision_name
        });
        
        if (parentSubdivision && currentSubdivision) {
          const hierarchyConnectionData: ConnectionData = {
            id: `hierarchy_${connection.subdivision_id}`,
            source: parentSubdivisionId, // 父subdivision的ID
            target: connection.subdivision_id, // 当前subdivision的ID
            label: `细分层级\n${parentSubdivision.subdivision_name} → ${currentSubdivision.subdivision_name}`
          };
          connections.push(hierarchyConnectionData);
          console.log(`🔗 [模板连接图] ✅ 添加subdivision层级连接: ${parentSubdivisionId} -> ${connection.subdivision_id}`);
        } else {
          console.warn(`⚠️ [模板连接图] 无法建立subdivision层级连接: 父级${parentSubdivisionId}或当前${connection.subdivision_id}不存在`);
          console.warn(`⚠️ [模板连接图] 调试信息:`, {
            parentSubdivisionId,
            currentSubdivisionId: connection.subdivision_id,
            availableParentIds: Array.from(uniqueSubdivisions.keys()),
            parentSubdivisionData: parentSubdivision,
            currentSubdivisionData: currentSubdivision
          });
        }
      } else {
        console.log(`📍 [模板连接图] 根级subdivision: ${connection.subdivision_name} (${connection.subdivision_id})`);
      }
    });
    
    console.log('✅ [模板连接图] 节点映射数据处理完成:', {
      parentWorkflowsCount: parentWorkflows.size,
      subdivisionNodesCount: uniqueSubdivisions.size,
      totalWorkflowsCount: workflows.length,
      connectionsCount: connections.length,
      nodeConnections: nodeSubdivisionConnections.length,
      workflows: workflows.map(w => ({ id: w.id, name: w.name, type: w.nodeSourceType, subdivisionId: w.subdivision_id, parentSubdivisionId: w.parent_subdivision_id })),
      connections: connections.map(c => ({ id: c.id, source: c.source, target: c.target, label: c.label }))
    });
    
    // 额外的连接关系验证
    console.log('🔍 [模板连接图] 连接关系验证:');
    const parentChildMap = new Map<string, string[]>();
    const childParentMap = new Map<string, string>();
    
    connections.forEach(conn => {
      if (!parentChildMap.has(conn.source)) {
        parentChildMap.set(conn.source, []);
      }
      parentChildMap.get(conn.source)!.push(conn.target);
      childParentMap.set(conn.target, conn.source);
    });
    
    workflows.forEach(workflow => {
      const workflowId = workflow.id;
      const hasParent = childParentMap.has(workflowId);
      const hasChildren = parentChildMap.has(workflowId) && parentChildMap.get(workflowId)!.length > 0;
      
      console.log(`📋 [模板连接图] 节点 ${workflow.name} (${workflowId}):`, {
        hasParent,
        hasChildren,
        parentId: hasParent ? childParentMap.get(workflowId) : 'none',
        childrenIds: hasChildren ? parentChildMap.get(workflowId) : 'none',
        isSubdivision: !!workflow.subdivision_id,
        parentSubdivisionId: workflow.parent_subdivision_id
      });
    });
    
  } catch (error) {
    console.error('❌ [模板连接图] 处理节点映射API数据失败:', error);
    console.error('❌ [模板连接图] 原始响应数据:', response);
  }
  
  return { workflows, connections };
};

const loadWorkflowData = async (workflowInstanceId: string): Promise<{ workflows: WorkflowData[], connections: ConnectionData[] }> => {
  console.log('🚀 [模板连接图] 开始加载工作流数据, ID:', workflowInstanceId);
  
  try {
    const { default: api } = await import('../services/api');
    // 使用新的节点级别映射API
    const apiUrl = `/execution/workflows/${workflowInstanceId}/node-mapping?include_template_structure=true`;
    
    console.log('📡 [模板连接图] 发送节点映射API请求:', apiUrl);
    
    const response = await api.get(apiUrl);
    
    console.log('📡 [模板连接图] API响应状态:', {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
      hasData: !!response.data
    });
    
    console.log('📡 [模板连接图] API响应数据:', response.data);
    
    const result = processNodeMappingAPIData(response.data);
    
    console.log('✅ [模板连接图] 工作流数据加载完成:', result);
    
    return result;
  } catch (error: any) {
    console.error('❌ [模板连接图] 加载工作流数据失败:', error);
    console.error('❌ [模板连接图] 错误详情:', {
      message: error.message,
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data
    });
    throw new Error(`Failed to load workflow data: ${error.message}`);
  }
};

const convertToReactFlow = (workflows: WorkflowData[], connections: ConnectionData[]): { nodes: Node[], edges: Edge[] } => {
  console.log('🔄 [模板连接图] 开始转换为 React Flow 格式:', {
    workflowsInput: workflows.length,
    connectionsInput: connections.length
  });
  
  // 计算树状布局位置，同时获取统一树的层级信息
  const positions = calculateTreeLayout(workflows, connections);
  
  // 重新构建统一树的父子关系映射（与calculateTreeLayout中的逻辑一致）
  const parentChildMap = new Map<string, string[]>();
  const childParentMap = new Map<string, string>();
  
  connections.forEach(conn => {
    if (!parentChildMap.has(conn.source)) {
      parentChildMap.set(conn.source, []);
    }
    parentChildMap.get(conn.source)!.push(conn.target);
    childParentMap.set(conn.target, conn.source);
  });
  
  // 应用统一树逻辑（与calculateTreeLayout保持一致）
  const potentialRoots = workflows.filter(w => !childParentMap.has(w.id));
  
  if (potentialRoots.length > 1) {
    const actualRootNode = potentialRoots[0].id;
    const mainRootChildren = parentChildMap.get(actualRootNode) || [];
    
    for (let i = 1; i < potentialRoots.length; i++) {
      const otherRootId = potentialRoots[i].id;
      mainRootChildren.push(otherRootId);
      childParentMap.set(otherRootId, actualRootNode);
    }
    parentChildMap.set(actualRootNode, mainRootChildren);
  }
  
  // 使用统一树关系计算层级
  const nodeLevels = new Map<string, number>();
  const calculateNodeLevel = (nodeId: string, visited = new Set<string>()): number => {
    if (nodeLevels.has(nodeId)) return nodeLevels.get(nodeId)!;
    if (visited.has(nodeId)) return 0;
    
    visited.add(nodeId);
    const parentId = childParentMap.get(nodeId);
    const level = parentId ? calculateNodeLevel(parentId, visited) + 1 : 0;
    nodeLevels.set(nodeId, level);
    return level;
  };
  
  workflows.forEach(workflow => calculateNodeLevel(workflow.id));
  
  // 转换为React Flow节点
  const nodes: Node[] = workflows.map(workflow => {
    const position = positions.get(workflow.id) || { x: 0, y: 0 };
    const nodeLevel = nodeLevels.get(workflow.id) || 0;
    
    // 判断节点类型以应用不同样式
    // 修复：根据层级判断根节点，而不是原始连接关系
    const isRoot = nodeLevel === 0;
    const hasChildren = connections.some(c => c.source === workflow.id);
    const isSubdivision = Boolean(workflow.subdivision_id);
    
    // 优化节点名称显示 - 如果有subdivision信息，优先显示subdivision名称
    let displayName = workflow.name;
    if (isSubdivision && workflow.subdivision_name) {
      displayName = `${workflow.subdivision_name} (${workflow.name})`;
    }
    
    let nodeType = 'default';
    let borderColor = '#1976d2';
    let backgroundColor = '#f5f5f5';
    
    if (isRoot) {
      nodeType = 'root';
      borderColor = '#4caf50';
      backgroundColor = '#e8f5e9';
    } else if (isSubdivision) {
      nodeType = 'subdivision';
      // 根据层级选择不同颜色
      if (nodeLevel === 1) {
        borderColor = '#ff9800';
        backgroundColor = '#fff3e0';
      } else if (nodeLevel === 2) {
        borderColor = '#9c27b0';
        backgroundColor = '#f3e5f5';
      } else if (nodeLevel >= 3) {
        borderColor = '#607d8b';
        backgroundColor = '#eceff1';
      }
    }
    
    const node: Node = {
      id: workflow.id,
      type: 'workflowNode',
      position: position,
      data: {
        ...workflow,
        name: displayName, // 使用优化后的显示名称
        nodeType,
        isRoot,
        hasChildren,
        isSubdivision,
        level: nodeLevel // 传递层级信息
      },
      style: {
        width: 320,
        minHeight: 180,
        border: `3px solid ${borderColor}`,
        backgroundColor: backgroundColor,
        borderRadius: '12px',
        boxShadow: isRoot ? '0 4px 12px rgba(76, 175, 80, 0.2)' : 
                   nodeLevel >= 3 ? '0 2px 6px rgba(96, 125, 139, 0.15)' : '0 2px 8px rgba(0, 0, 0, 0.1)'
      }
    };
    
    console.log(`🔄 [模板连接图] 创建节点:`, {
      id: workflow.id,
      name: displayName,
      originalName: workflow.name,
      position: position,
      type: nodeType,
      level: nodeLevel,
      isRoot,
      hasChildren,
      isSubdivision
    });
    
    return node;
  });
  
  // 转换为React Flow边，添加更丰富的视觉效果
  const edges: Edge[] = connections.map((connection) => {
    const sourceNode = workflows.find(w => w.id === connection.source);
    const targetNode = workflows.find(w => w.id === connection.target);
    const targetLevel = nodeLevels.get(connection.target) || 0;
    
    // 根据目标节点层级选择边的样式
    let edgeColor = '#1976d2';
    let edgeWidth = 3;
    let isDashed = false;
    
    if (targetLevel === 1) {
      edgeColor = '#ff9800';
      edgeWidth = 3;
    } else if (targetLevel === 2) {
      edgeColor = '#9c27b0';
      edgeWidth = 2;
      isDashed = true;
    } else if (targetLevel >= 3) {
      edgeColor = '#607d8b';
      edgeWidth = 2;
      isDashed = true;
    }
    
    const edge: Edge = {
      id: connection.id,
      source: connection.source,
      target: connection.target,
      type: 'smoothstep',
      animated: true,
      style: { 
        strokeWidth: edgeWidth, 
        stroke: edgeColor,
        strokeDasharray: isDashed ? '5,5' : undefined
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edgeColor,
        width: 20,
        height: 20
      },
      label: connection.label,
      labelStyle: {
        fontSize: 12,
        fontWeight: 'bold',
        fill: edgeColor,
        background: 'white',
        padding: '2px 6px',
        borderRadius: '4px'
      },
      labelBgStyle: {
        fill: 'white',
        stroke: edgeColor,
        strokeWidth: 1,
        fillOpacity: 0.9
      },
      data: {
        ...connection,
        isSubdivision: Boolean(targetNode?.subdivision_id),
        targetLevel: targetLevel
      }
    };
    
    console.log(`🔄 [模板连接图] 创建边:`, {
      id: connection.id,
      source: connection.source,
      target: connection.target,
      targetLevel: targetLevel,
      label: connection.label,
      sourceWorkflow: sourceNode?.name,
      targetWorkflow: targetNode?.name,
      isSubdivision: Boolean(targetNode?.subdivision_id)
    });
    
    return edge;
  });
  
  const result = { nodes, edges };
  
  console.log('✅ [模板连接图] React Flow 转换完成:', {
    nodesCount: nodes.length,
    edgesCount: edges.length,
    rootNodes: nodes.filter(n => n.data.isRoot).length,
    subdivisionNodes: nodes.filter(n => n.data.isSubdivision).length,
    maxLevel: Math.max(...Array.from(nodeLevels.values())),
    nodeDetails: nodes.map(n => ({ 
      id: n.id, 
      position: n.position, 
      dataName: n.data?.name,
      type: n.data?.nodeType,
      level: n.data?.level
    })),
    edges: edges.map(e => ({ id: e.id, source: e.source, target: e.target, level: e.data?.targetLevel }))
  });
  
  return result;
};

// =============================================================================
// 简化的主组件
// =============================================================================

interface Props {
  workflowInstanceId: string;
  onNodeClick?: (workflow: WorkflowData) => void;
  onEdgeClick?: (connection: ConnectionData) => void;
  className?: string;
}

const WorkflowNodeWrapper: React.FC<any> = React.memo(({ data }) => {
  return <WorkflowNode data={data} />;
});

const NODE_TYPES = Object.freeze({
  workflowNode: WorkflowNodeWrapper,
});

const WorkflowTemplateConnectionGraph: React.FC<Props> = ({
  workflowInstanceId,
  onNodeClick,
  onEdgeClick,
  className
}) => {
  console.log('🎯 [模板连接图] 组件初始化, props:', {
    workflowInstanceId,
    hasOnNodeClick: !!onNodeClick,
    hasOnEdgeClick: !!onEdgeClick,
    className
  });
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  const loadData = useCallback(async () => {
    console.log('📊 [模板连接图] 开始 loadData 函数');
    setIsLoading(true);
    setError(null);
    
    try {
      const { workflows, connections } = await loadWorkflowData(workflowInstanceId);
      
      console.log('📊 [模板连接图] loadWorkflowData 返回结果:', {
        workflowsCount: workflows.length,
        connectionsCount: connections.length
      });
      
      const { nodes: flowNodes, edges: flowEdges } = convertToReactFlow(workflows, connections);
      
      console.log('📊 [模板连接图] convertToReactFlow 返回结果:', {
        flowNodesCount: flowNodes.length,
        flowEdgesCount: flowEdges.length
      });
      
      console.log('📊 [模板连接图] 设置 React Flow 状态...');
      setNodes(flowNodes);
      setEdges(flowEdges);
      
      console.log('✅ [模板连接图] loadData 完成，状态已更新');
      
    } catch (err: any) {
      console.error('❌ [模板连接图] loadData 失败:', err);
      setError(err.message || '加载失败');
    } finally {
      setIsLoading(false);
      console.log('📊 [模板连接图] loadData 结束，loading状态已清除');
    }
  }, [workflowInstanceId]);
  
  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    console.log('🖱️ [模板连接图] 节点被点击:', node);
    onNodeClick?.(node.data);
  }, [onNodeClick]);
  
  const handleEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    console.log('🖱️ [模板连接图] 边被点击:', edge);
    onEdgeClick?.(edge.data);
  }, [onEdgeClick]);
  
  useEffect(() => {
    console.log('🔄 [模板连接图] useEffect 触发，开始加载数据');
    loadData();
  }, [loadData]);
  
  // 监听状态变化
  useEffect(() => {
    console.log('📊 [模板连接图] React Flow 节点状态更新:', {
      nodesCount: nodes.length,
      nodes: nodes.map(n => ({ id: n.id, type: n.type, position: n.position }))
    });
  }, [nodes]);
  
  useEffect(() => {
    console.log('📊 [模板连接图] React Flow 边状态更新:', {
      edgesCount: edges.length,
      edges: edges.map(e => ({ id: e.id, source: e.source, target: e.target }))
    });
  }, [edges]);
  
  console.log('🎯 [模板连接图] 组件渲染状态:', {
    isLoading,
    error,
    nodesCount: nodes.length,
    edgesCount: edges.length
  });
  
  if (isLoading) {
    console.log('⏳ [模板连接图] 渲染加载状态');
    return (
      <div className={`workflow-template-connection-graph loading ${className || ''}`}>
        <div className="loading-spinner">
          <div className="spinner"></div>
          <div className="loading-text">加载工作流关系图...</div>
        </div>
      </div>
    );
  }
  
  if (error) {
    console.log('❌ [模板连接图] 渲染错误状态:', error);
    return (
      <div className={`workflow-template-connection-graph error ${className || ''}`}>
        <div className="error-message">
          <div className="error-icon">⚠️</div>
          <div className="error-text">{error}</div>
          <button className="retry-button" onClick={loadData}>重试</button>
        </div>
      </div>
    );
  }
  
  console.log('✅ [模板连接图] 渲染正常状态的 React Flow');
  
  return (
    <div 
      className={`workflow-template-connection-graph ${className || ''}`}
      style={{ width: '100%', height: '500px' }}
      data-layout="tree"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        nodeTypes={NODE_TYPES}
        connectionLineType={ConnectionLineType.SmoothStep}
        fitView
        fitViewOptions={{ 
          padding: 0.15,
          minZoom: 0.3,
          maxZoom: 1.2,
          duration: 1000
        }}
        minZoom={0.2}
        maxZoom={1.8}
        defaultViewport={{ x: 0, y: 0, zoom: 0.6 }}
        attributionPosition="bottom-left"
      >
        <Background 
          color="#4caf50" 
          gap={20} 
          size={1}
        />
        <Controls 
          showZoom={true}
          showFitView={true}
          showInteractive={false}
          position="top-left"
        />
      </ReactFlow>
    </div>
  );
};

// =============================================================================
// Provider包装
// =============================================================================

const WorkflowTemplateConnectionGraphWithProvider: React.FC<Props> = (props) => {
  return (
    <ReactFlowProvider>
      <WorkflowTemplateConnectionGraph {...props} />
    </ReactFlowProvider>
  );
};

export default WorkflowTemplateConnectionGraphWithProvider;