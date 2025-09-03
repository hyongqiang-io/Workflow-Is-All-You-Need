/**
 * 工作流验证工具函数
 * Workflow Validation Utilities
 */

import { Node, Edge } from 'reactflow';

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ValidationDetails {
  startNodes: Node[];
  endNodes: Node[];
  processorNodes: Node[];
  isolatedNodes: Node[];
  unconnectedProcessorNodes: Node[];
}

/**
 * 验证工作流的完整性
 * @param nodes 工作流节点
 * @param edges 工作流连接
 * @returns 验证结果
 */
export function validateWorkflow(nodes: Node[], edges: Edge[]): ValidationResult {
  const result: ValidationResult = {
    isValid: true,
    errors: [],
    warnings: []
  };

  // 如果没有节点，则无效
  if (!nodes || nodes.length === 0) {
    result.isValid = false;
    result.errors.push('工作流至少需要包含一个节点');
    return result;
  }

  const details = analyzeWorkflow(nodes, edges);
  
  // 获取所有参与连接的节点ID
  const connectedNodeIds = new Set<string>();
  edges.forEach(edge => {
    connectedNodeIds.add(edge.source);
    connectedNodeIds.add(edge.target);
  });
  
  // 1. 检查开始节点数量（必须有且仅有一个）
  if (details.startNodes.length === 0) {
    result.isValid = false;
    result.errors.push('工作流必须有且仅有一个开始类型节点');
  } else if (details.startNodes.length > 1) {
    result.isValid = false;
    result.errors.push(`工作流只能有一个开始节点，当前有 ${details.startNodes.length} 个`);
  }

  // 2. 检查结束节点数量（必须有且仅有一个）
  if (details.endNodes.length === 0) {
    result.isValid = false;
    result.errors.push('工作流必须有且仅有一个结束类型节点');
  } else if (details.endNodes.length > 1) {
    result.isValid = false;
    result.errors.push(`工作流只能有一个结束节点，当前有 ${details.endNodes.length} 个`);
  }

  // 3. 检查processor节点连接（所有processor节点必须前后都有连接）
  if (details.unconnectedProcessorNodes.length > 0) {
    result.isValid = false;
    const nodeNames = details.unconnectedProcessorNodes.map(node => node.data.label).join('、');
    result.errors.push(`以下processor节点缺少必要的连接：${nodeNames}`);
  }

  // 4. 检查所有节点的孤立状态（包括start和end节点）
  const allIsolatedNodes = nodes.filter(node => !connectedNodeIds.has(node.id));
  
  if (allIsolatedNodes.length > 0) {
    result.isValid = false;
    const nodeNames = allIsolatedNodes.map(node => node.data.label).join('、');
    result.errors.push(`发现孤立节点：${nodeNames}`);
  }

  // 5. 特别检查start节点连接（必须有输出连接）
  const disconnectedStartNodes = details.startNodes.filter(node => {
    return !edges.some(edge => edge.source === node.id);
  });
  if (disconnectedStartNodes.length > 0) {
    result.isValid = false;
    const nodeNames = disconnectedStartNodes.map(node => node.data.label).join('、');
    result.errors.push(`开始节点必须有输出连接：${nodeNames}`);
  }

  // 6. 特别检查end节点连接（必须有输入连接）
  const disconnectedEndNodes = details.endNodes.filter(node => {
    return !edges.some(edge => edge.target === node.id);
  });
  if (disconnectedEndNodes.length > 0) {
    result.isValid = false;
    const nodeNames = disconnectedEndNodes.map(node => node.data.label).join('、');
    result.errors.push(`结束节点必须有输入连接：${nodeNames}`);
  }

  // 7. 添加一些警告
  if (details.processorNodes.length === 0) {
    result.warnings.push('工作流没有处理器节点，可能只是一个简单的开始-结束流程');
  }

  return result;
}

/**
 * 分析工作流结构
 * @param nodes 节点列表
 * @param edges 连接列表
 * @returns 分析详情
 */
export function analyzeWorkflow(nodes: Node[], edges: Edge[]): ValidationDetails {
  const startNodes = nodes.filter(node => node.data.type === 'start');
  const endNodes = nodes.filter(node => node.data.type === 'end');
  const processorNodes = nodes.filter(node => node.data.type === 'processor');

  // 获取所有参与连接的节点ID
  const connectedNodeIds = new Set<string>();
  edges.forEach(edge => {
    connectedNodeIds.add(edge.source);
    connectedNodeIds.add(edge.target);
  });

  // 找出孤立的processor节点（不包括start和end节点，用于旧的兼容性）
  const isolatedNodes = nodes.filter(node => {
    // start节点和end节点不算在这个旧的孤立检查中
    if (node.data.type === 'start' || node.data.type === 'end') {
      return false;
    }
    return !connectedNodeIds.has(node.id);
  });

  // 找出连接不完整的processor节点（必须既有输入又有输出）
  const unconnectedProcessorNodes = processorNodes.filter(node => {
    const hasInput = edges.some(edge => edge.target === node.id);
    const hasOutput = edges.some(edge => edge.source === node.id);
    return !hasInput || !hasOutput;
  });

  return {
    startNodes,
    endNodes,
    processorNodes,
    isolatedNodes,
    unconnectedProcessorNodes
  };
}

/**
 * 获取工作流验证状态的简短描述
 * @param nodes 节点列表
 * @param edges 连接列表
 * @returns 状态描述
 */
export function getWorkflowValidationSummary(nodes: Node[], edges: Edge[]): string {
  if (!nodes || nodes.length === 0) {
    return '工作流为空';
  }

  const validation = validateWorkflow(nodes, edges);
  
  if (validation.isValid) {
    return '工作流验证通过';
  } else {
    return `发现 ${validation.errors.length} 个错误`;
  }
}

/**
 * 检查工作流是否可以保存
 * @param nodes 节点列表
 * @param edges 连接列表
 * @returns 是否可以保存
 */
export function canSaveWorkflow(nodes: Node[], edges: Edge[]): boolean {
  const validation = validateWorkflow(nodes, edges);
  return validation.isValid;
}