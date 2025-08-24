/**
 * 工作流布局和连接工具函数
 * 修复节点ID映射问题和连接逻辑
 */

interface WorkflowNode {
  id: string;
  node_instance_id?: string;
  node_id?: string;
  name: string;
  node_name?: string;
  type: string;
  node_type?: string;
  status: string;
  created_at?: string;
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

/**
 * 验证和修复边数据中的ID映射问题
 */
export const validateAndFixEdges = (nodes: any[], edges: any[]): WorkflowEdge[] => {
  // 创建节点ID映射表 - 支持多种ID格式
  const nodeIdMap = new Map<string, string>();
  
  nodes.forEach(node => {
    const primaryId = node.node_instance_id || node.id;
    
    // 建立各种可能的ID映射关系
    if (node.node_instance_id) nodeIdMap.set(node.node_instance_id, primaryId);
    if (node.id && node.id !== primaryId) nodeIdMap.set(node.id, primaryId);
    if (node.node_id) nodeIdMap.set(node.node_id, primaryId);
  });
  
  // 修复边数据
  const fixedEdges: WorkflowEdge[] = [];
  
  edges.forEach(edge => {
    const sourceId = nodeIdMap.get(edge.source) || edge.source;
    const targetId = nodeIdMap.get(edge.target) || edge.target;
    
    // 验证修复后的ID是否存在
    const sourceExists = nodes.some(n => (n.node_instance_id || n.id) === sourceId);
    const targetExists = nodes.some(n => (n.node_instance_id || n.id) === targetId);
    
    if (sourceExists && targetExists) {
      fixedEdges.push({
        id: edge.id || `${sourceId}-${targetId}`,
        source: sourceId,
        target: targetId,
        label: edge.label
      });
    } else {
      console.warn(`跳过无效边: ${edge.source} -> ${edge.target} (修复后: ${sourceId} -> ${targetId})`);
    }
  });
  
  return fixedEdges;
};

/**
 * 智能生成缺失的连接 - 基于节点类型和时间
 */
export const generateMissingConnections = (nodes: any[]): WorkflowEdge[] => {
  if (nodes.length <= 1) return [];
  
  console.log('🔗 [连接生成] 开始智能生成连接，节点数:', nodes.length);
  
  // 按执行逻辑排序节点
  const sortedNodes = [...nodes].sort((a, b) => {
    // 1. 按类型排序 - 支持多种字段名
    const typeOrder = { start: 0, process: 1, human: 1, ai: 1, processor: 1, decision: 2, end: 3 };
    
    // 兼容不同的类型字段名
    const aType = (a.node_type || a.type || 'process').toLowerCase();
    const bType = (b.node_type || b.type || 'process').toLowerCase();
    
    const aOrder = typeOrder[aType as keyof typeof typeOrder] ?? 1;
    const bOrder = typeOrder[bType as keyof typeof typeOrder] ?? 1;
    
    console.log(`🔍 [连接生成] 节点排序: ${a.node_name || a.name}(${aType}:${aOrder}) vs ${b.node_name || b.name}(${bType}:${bOrder})`);
    
    if (aOrder !== bOrder) return aOrder - bOrder;
    
    // 2. 按创建时间排序
    if (a.created_at && b.created_at) {
      const timeA = new Date(a.created_at).getTime();
      const timeB = new Date(b.created_at).getTime();
      console.log(`⏰ [连接生成] 时间排序: ${a.node_name}(${timeA}) vs ${b.node_name}(${timeB})`);
      return timeA - timeB;
    }
    
    // 3. 如果有开始时间，也参考
    if (a.start_at && b.start_at) {
      const startA = new Date(a.start_at).getTime();
      const startB = new Date(b.start_at).getTime();
      console.log(`🚀 [连接生成] 开始时间排序: ${a.node_name}(${startA}) vs ${b.node_name}(${startB})`);
      return startA - startB;
    }
    
    // 4. 按名称排序
    const nameA = (a.node_name || a.name || '').toLowerCase();
    const nameB = (b.node_name || b.name || '').toLowerCase();
    return nameA.localeCompare(nameB);
  });
  
  console.log('📋 [连接生成] 排序后的节点顺序:', sortedNodes.map(n => `${n.node_name || n.name}(${n.node_type || n.type})`));
  
  // 生成顺序连接
  const generatedEdges: WorkflowEdge[] = [];
  for (let i = 0; i < sortedNodes.length - 1; i++) {
    const source = sortedNodes[i].node_instance_id || sortedNodes[i].id;
    const target = sortedNodes[i + 1].node_instance_id || sortedNodes[i + 1].id;
    
    if (source && target) {
      generatedEdges.push({
        id: `generated-${source}-${target}`,
        source,
        target,
        label: '智能连接'
      });
      
      console.log(`➡️ [连接生成] 生成连接: ${sortedNodes[i].node_name} -> ${sortedNodes[i + 1].node_name}`);
    }
  }
  
  console.log('✅ [连接生成] 生成完成，连接数:', generatedEdges.length);
  return generatedEdges;
};

/**
 * 基于连接关系的智能布局算法 - 连接优先版本
 */
export const calculateDependencyBasedLayout = (
  nodes: any[], 
  edges: WorkflowEdge[]
): Record<string, { x: number; y: number }> => {
  const positions: Record<string, { x: number; y: number }> = {};
  
  if (nodes.length === 0) return positions;
  
  console.log('📐 [布局算法] 开始基于连接关系的布局计算，节点数:', nodes.length, '边数:', edges.length);
  
  // **核心修复：优先基于连接关系排列**
  if (edges.length > 0) {
    // 有连接关系时，严格按照连接关系排列
    return layoutByConnections(nodes, edges);
  } else {
    // 无连接关系时，才考虑节点类型和时间
    return layoutByNodeAttributes(nodes);
  }
};

/**
 * 基于连接关系的布局 - 连接关系为第一优先级
 */
const layoutByConnections = (nodes: any[], edges: WorkflowEdge[]): Record<string, { x: number; y: number }> => {
  console.log('🔗 [布局算法] 使用连接关系优先布局');
  
  // 构建依赖图
  const dependents = new Map<string, string[]>();
  const dependencies = new Map<string, string[]>();
  const nodeIdMap = new Map<string, any>();
  
  // 初始化节点映射
  nodes.forEach(node => {
    const nodeId = node.node_instance_id || node.id;
    dependents.set(nodeId, []);
    dependencies.set(nodeId, []);
    nodeIdMap.set(nodeId, node);
  });
  
  // **关键：严格按照边的连接关系构建依赖**
  edges.forEach(edge => {
    if (dependents.has(edge.source) && dependencies.has(edge.target)) {
      dependents.get(edge.source)!.push(edge.target);
      dependencies.get(edge.target)!.push(edge.source);
      console.log(`🔗 [连接优先] 添加连接依赖: ${edge.source} -> ${edge.target}`);
    } else {
      console.warn(`⚠️ [连接优先] 跳过无效连接: ${edge.source} -> ${edge.target}`);
    }
  });
  
  // 使用拓扑排序严格按照连接关系排列
  const sortedLevels = topologicalSortWithLevels(nodes, dependents, dependencies, nodeIdMap);
  
  // 布局参数
  const levelSpacing = 300; // 层级间距（水平）
  const nodeSpacing = 120;  // 同层节点间距（垂直）
  const startX = 100;
  const startY = 100;
  
  console.log('📊 [连接优先] 拓扑排序结果:', sortedLevels.map((level, idx) => ({
    level: idx,
    nodes: level.map(id => nodeIdMap.get(id)?.node_name || id)
  })));
  
  // 基于连接关系的层级布局
  const positions: Record<string, { x: number; y: number }> = {};
  
  sortedLevels.forEach((levelNodes, level) => {
    const x = startX + level * levelSpacing;
    
    // 垂直居中排列同层节点
    const totalHeight = (levelNodes.length - 1) * nodeSpacing;
    const centerY = startY + 200;
    const firstNodeY = centerY - totalHeight / 2;
    
    levelNodes.forEach((nodeId, index) => {
      const y = Math.max(50, firstNodeY + index * nodeSpacing);
      positions[nodeId] = { x, y };
      
      const node = nodeIdMap.get(nodeId);
      console.log(`📍 [连接优先] 节点位置: ${node?.node_name} -> (${x}, ${y}) [Level ${level}]`);
    });
  });
  
  return positions;
};

/**
 * 拓扑排序生成层级 - 严格按照连接关系
 */
const topologicalSortWithLevels = (
  nodes: any[],
  dependents: Map<string, string[]>,
  dependencies: Map<string, string[]>,
  nodeIdMap: Map<string, any>
): string[][] => {
  const inDegree = new Map<string, number>();
  const levels: string[][] = [];
  
  // 计算入度 - 基于实际连接关系
  nodes.forEach(node => {
    const nodeId = node.node_instance_id || node.id;
    inDegree.set(nodeId, dependencies.get(nodeId)?.length || 0);
  });
  
  console.log('📊 [拓扑排序] 节点入度（基于连接）:', Array.from(inDegree.entries()).map(([id, degree]) => 
    `${nodeIdMap.get(id)?.node_name}:${degree}`
  ));
  
  const queue: string[] = [];
  const processed = new Set<string>();
  
  // 找到所有入度为0的节点（真正的起始节点）
  inDegree.forEach((degree, nodeId) => {
    if (degree === 0) {
      queue.push(nodeId);
      console.log(`🚀 [拓扑排序] 发现起始节点: ${nodeIdMap.get(nodeId)?.node_name}`);
    }
  });
  
  let currentLevel = 0;
  
  // 层级式拓扑排序
  while (queue.length > 0) {
    const levelSize = queue.length;
    const currentLevelNodes: string[] = [];
    
    console.log(`🔄 [拓扑排序] 处理Level ${currentLevel}，节点数: ${levelSize}`);
    
    for (let i = 0; i < levelSize; i++) {
      const nodeId = queue.shift()!;
      processed.add(nodeId);
      currentLevelNodes.push(nodeId);
      
      // 处理当前节点的所有后继节点
      const successors = dependents.get(nodeId) || [];
      successors.forEach(successor => {
        const newInDegree = (inDegree.get(successor) || 0) - 1;
        inDegree.set(successor, newInDegree);
        
        if (newInDegree === 0 && !processed.has(successor)) {
          queue.push(successor);
          console.log(`➡️ [拓扑排序] 节点就绪: ${nodeIdMap.get(successor)?.node_name} (Level ${currentLevel + 1})`);
        }
      });
    }
    
    if (currentLevelNodes.length > 0) {
      levels.push(currentLevelNodes);
      console.log(`✅ [拓扑排序] Level ${currentLevel} 完成:`, 
        currentLevelNodes.map(id => nodeIdMap.get(id)?.node_name || id));
    }
    
    currentLevel++;
  }
  
  // 处理孤立节点或循环依赖
  const unprocessed = nodes.filter(node => {
    const nodeId = node.node_instance_id || node.id;
    return !processed.has(nodeId);
  });
  
  if (unprocessed.length > 0) {
    console.warn('⚠️ [拓扑排序] 发现未处理节点（孤立或循环依赖）:', 
      unprocessed.map(n => n.node_name || n.name));
    
    levels.push(unprocessed.map(n => n.node_instance_id || n.id));
  }
  
  return levels;
};

/**
 * 基于节点属性的布局 - 仅在无连接关系时使用
 */
const layoutByNodeAttributes = (nodes: any[]): Record<string, { x: number; y: number }> => {
  console.log('📝 [布局算法] 无连接关系，使用节点属性排序');
  
  const positions: Record<string, { x: number; y: number }> = {};
  
  // 按节点属性排序（仅作为fallback）
  const sortedNodes = [...nodes].sort((a, b) => {
    // 1. 优先按执行时间排序
    if (a.started_at && b.started_at) {
      return new Date(a.started_at).getTime() - new Date(b.started_at).getTime();
    }
    
    if (a.created_at && b.created_at) {
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    }
    
    // 2. 其次按节点类型
    const typeOrder = { start: 0, process: 1, human: 1, ai: 1, processor: 1, decision: 2, end: 3 };
    const aType = (a.node_type || a.type || 'process').toLowerCase();
    const bType = (b.node_type || b.type || 'process').toLowerCase();
    const aOrder = typeOrder[aType as keyof typeof typeOrder] ?? 1;
    const bOrder = typeOrder[bType as keyof typeof typeOrder] ?? 1;
    
    if (aOrder !== bOrder) return aOrder - bOrder;
    
    // 3. 最后按名称
    const nameA = (a.node_name || a.name || '').toLowerCase();
    const nameB = (b.node_name || b.name || '').toLowerCase();
    return nameA.localeCompare(nameB);
  });
  
  console.log('📋 [属性排序] 排序结果:', sortedNodes.map(n => n.node_name || n.name));
  
  // 简单的水平排列
  sortedNodes.forEach((node, index) => {
    const nodeId = node.node_instance_id || node.id;
    positions[nodeId] = {
      x: 100 + index * 250,
      y: 200
    };
    
    console.log(`📍 [属性排序] 节点位置: ${node.node_name} -> (${100 + index * 250}, 200)`);
  });
  
  return positions;
};

/**
 * 获取节点的状态颜色
 */
export const getNodeStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    pending: '#faad14',
    waiting: '#1890ff', 
    running: '#1890ff',
    in_progress: '#1890ff',
    completed: '#52c41a',
    failed: '#ff4d4f',
    cancelled: '#8c8c8c',
    blocked: '#ff7a45',
    error: '#ff4d4f'
  };
  
  return colorMap[status] || '#d9d9d9';
};

/**
 * 格式化持续时间
 */
export const formatDuration = (seconds?: number): string => {
  if (!seconds) return '-';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
};

/**
 * 简化的拓扑排序实现
 */
export const simpleTopologicalSort = (nodes: any[], edges: WorkflowEdge[]): any[] => {
  const inDegree = new Map<string, number>();
  const graph = new Map<string, string[]>();
  const nodeMap = new Map<string, any>();
  
  // 初始化
  nodes.forEach(node => {
    const nodeId = node.node_instance_id || node.id;
    inDegree.set(nodeId, 0);
    graph.set(nodeId, []);
    nodeMap.set(nodeId, node);
  });
  
  // 构建图
  edges.forEach(edge => {
    if (graph.has(edge.source) && inDegree.has(edge.target)) {
      graph.get(edge.source)!.push(edge.target);
      inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
    }
  });
  
  // Kahn算法
  const queue: string[] = [];
  const result: any[] = [];
  
  inDegree.forEach((degree, nodeId) => {
    if (degree === 0) {
      queue.push(nodeId);
    }
  });
  
  while (queue.length > 0) {
    const nodeId = queue.shift()!;
    const node = nodeMap.get(nodeId);
    if (node) {
      result.push(node);
    }
    
    graph.get(nodeId)?.forEach(targetId => {
      const newDegree = (inDegree.get(targetId) || 0) - 1;
      inDegree.set(targetId, newDegree);
      if (newDegree === 0) {
        queue.push(targetId);
      }
    });
  }
  
  // 添加剩余节点（处理环形依赖）
  nodes.forEach(node => {
    const nodeId = node.node_instance_id || node.id;
    if (!result.find(n => (n.node_instance_id || n.id) === nodeId)) {
      result.push(node);
    }
  });
  
  return result;
};