import axios from 'axios';

// 创建专用的axios实例用于模板连接API
const templateConnectionAPI = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || (process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api'),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 添加认证token
templateConnectionAPI.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// API响应类型定义
interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data: T;
}

// 合并候选类型（向后兼容）
export interface MergeCandidate {
  subdivision_id: string;
  workflow_base_id: string;
  workflow_name: string;
  compatibility: number;
  merge_benefits: string[];
  merge_risks: string[];
  replaceable_node: {
    node_base_id: string;
    node_name: string;
    node_type: string;
  };
  sub_workflow_id: string;
}

// 简化的数据类型 - subdivision就是树节点
export interface SubdivisionNode {
  subdivision_id: string;
  workflow_base_id: string;
  workflow_name: string;
  status: 'completed' | 'running' | 'failed' | 'pending';
  depth: number;
  children_count: number;
  node_name: string;
  task_title: string;
}

// React Flow节点类型
export interface FlowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: SubdivisionNode & {
    label: string;
    isRoot: boolean;
  };
}

// React Flow边类型
export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  animated?: boolean;
  label?: string;
}

// 图形数据结构
export interface SubdivisionGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
  layout: {
    algorithm: string;
    max_depth: number;
    total_nodes: number;
    root_count: number;
  };
}

// API响应数据结构
export interface WorkflowConnectionResponse {
  workflow_instance_id: string;
  detailed_connection_graph: SubdivisionGraph;
  statistics: {
    total_subdivisions: number;
    root_subdivisions: number;
    max_depth: number;
    completed_workflows: number;
    running_workflows: number;
    failed_workflows: number;
  };
}

/**
 * 工作流模板连接管理器 - Linus式简化版本
 * 
 * 核心思想：
 * 1. subdivision就是树，后端已经计算好位置
 * 2. 前端只负责接收数据和显示，不搞复杂算法
 * 3. 一个类，几个方法，搞定所有功能
 */
export class WorkflowTemplateConnectionManager {
  
  /**
   * 获取工作流subdivision树数据
   */
  async getWorkflowConnections(workflowInstanceId: string): Promise<WorkflowConnectionResponse> {
    try {
      console.log('🌳 [简化] 获取subdivision树:', workflowInstanceId);
      
      // 使用正确的API端点获取subdivision数据
      const response = await templateConnectionAPI.get<ApiResponse<WorkflowConnectionResponse>>(
        `/workflow-template-connections/workflow-instances/${workflowInstanceId}/detailed-template-connections`
      );
      
      if (response.data.success) {
        const data = response.data.data;
        
        // 调试：检查返回的数据结构
        console.log('🔍 [DEBUG] 完整API响应:', response.data);
        console.log('🔍 [DEBUG] 数据结构检查:', {
          hasDetailedConnectionGraph: !!data.detailed_connection_graph,
          nodeCount: data.detailed_connection_graph?.nodes?.length || 0,
          edgeCount: data.detailed_connection_graph?.edges?.length || 0,
          firstNode: data.detailed_connection_graph?.nodes?.[0],
          statistics: data.statistics
        });
        
        // 检查是否真的是subdivision数据
        const nodes = data.detailed_connection_graph?.nodes || [];
        if (nodes.length > 0) {
          const sampleNode = nodes[0];
          console.log('🔍 [DEBUG] 样本节点字段:', Object.keys(sampleNode));
          console.log('🔍 [DEBUG] 样本节点内容:', sampleNode);
          
          // 检查subdivision特有字段 (数据在node.data中)
          const nodeData = sampleNode.data || {};
          const isSubdivisionData = nodeData.workflow_base_id || 
                                   nodeData.label || 
                                   nodeData.task_title;
          
          console.log('🔍 [DEBUG] 是subdivision数据:', isSubdivisionData);
          
          if (!isSubdivisionData) {
            console.warn('⚠️ [简化] API返回的可能不是subdivision数据，而是工作流内部节点');
            console.warn('🔍 [DEBUG] 这可能解释了为什么显示10个节点而不是4个工作流');
          }
        }
        
        console.log('✅ [简化] subdivision树数据获取成功:', {
          totalNodes: data.detailed_connection_graph?.nodes?.length || 0,
          totalEdges: data.detailed_connection_graph?.edges?.length || 0,
          maxDepth: data.statistics?.max_depth
        });
        return data;
      } else {
        throw new Error(response.data.message || '获取数据失败');
      }
    } catch (error: any) {
      console.error('❌ [简化] 获取subdivision树失败:', error);
      throw error;
    }
  }
  
  /**
   * 转换为React Flow数据格式
   * 
   * 后端已经计算好位置，前端只需要简单转换
   */
  convertToReactFlowData(graph: SubdivisionGraph): { nodes: FlowNode[]; edges: FlowEdge[] } {
    try {
      console.log('🔄 [简化] 转换React Flow数据:', {
        inputNodes: graph.nodes.length,
        inputEdges: graph.edges.length
      });
      
      // 直接使用后端计算的数据，不做复杂转换
      const flowNodes: FlowNode[] = graph.nodes.map(node => ({
        ...node,
        data: {
          ...node.data,
          label: node.data.workflow_name || node.data.node_name
        }
      }));
      
      const flowEdges: FlowEdge[] = graph.edges.map(edge => ({
        ...edge,
        type: 'smoothstep'
      }));
      
      console.log('✅ [简化] React Flow数据转换完成:', {
        outputNodes: flowNodes.length,
        outputEdges: flowEdges.length
      });
      
      return { nodes: flowNodes, edges: flowEdges };
    } catch (error) {
      console.error('❌ [简化] React Flow数据转换失败:', error);
      throw error;
    }
  }
  
  /**
   * 获取节点状态颜色
   */
  getNodeStatusColor(status: string): string {
    switch (status) {
      case 'completed': return '#22c55e';  // 绿色
      case 'running': return '#3b82f6';    // 蓝色
      case 'failed': return '#ef4444';     // 红色
      case 'pending': return '#6b7280';    // 灰色
      default: return '#6b7280';
    }
  }
  
  /**
   * 获取合并候选项
   */
  async getMergeCandidates(workflowInstanceId: string): Promise<{
    success: boolean;
    candidates?: any[];
    message?: string;
  }> {
    try {
      console.log('🔍 [API] 获取合并候选项:', workflowInstanceId);
      
      const response = await templateConnectionAPI.get(
        `/workflow-merge/${workflowInstanceId}/candidates`
      );

      console.log('📋 [API] 合并候选响应:', response.data);
      
      if (response.data.success) {
        return {
          success: true,
          candidates: response.data.candidates || [],
        };
      } else {
        return {
          success: false,
          message: response.data.message || '获取合并候选项失败'
        };
      }
      
    } catch (error: any) {
      console.error('❌ [API] 获取合并候选项失败:', error);
      return {
        success: false,
        message: error.response?.data?.detail || error.message || '获取合并候选项失败'
      };
    }
  }

  /**
   * 执行工作流合并
   */
  async executeWorkflowMerge(workflowInstanceId: string, selectedSubdivisions: string[]): Promise<{
    success: boolean;
    data?: any;
    message?: string;
  }> {
    try {
      console.log('🚀 [API] 执行工作流合并:', { workflowInstanceId, selectedSubdivisions });
      
      const response = await templateConnectionAPI.post(
        `/workflow-merge/${workflowInstanceId}/execute`,
        {
          selected_subdivisions: selectedSubdivisions,
          merge_config: {
            from_lowest_level: true,
            preserve_connections: true,
            remove_start_end_nodes: true
          }
        }
      );

      console.log('✅ [API] 合并执行响应:', response.data);
      
      if (response.data.success) {
        return {
          success: true,
          data: response.data,
        };
      } else {
        return {
          success: false,
          message: response.data.message || '工作流合并失败'
        };
      }
      
    } catch (error: any) {
      console.error('❌ [API] 工作流合并失败:', error);
      return {
        success: false,
        message: error.response?.data?.detail || error.message || '工作流合并失败'
      };
    }
  }
  
  /**
   * 格式化统计信息
   */
  formatStatistics(stats: WorkflowConnectionResponse['statistics']): string {
    const completionRate = stats.total_subdivisions > 0 
      ? Math.round((stats.completed_workflows / stats.total_subdivisions) * 100)
      : 0;
    
    return `总共 ${stats.total_subdivisions} 个subdivision，完成 ${stats.completed_workflows} 个 (${completionRate}%)，最大深度 ${stats.max_depth}`;
  }
}

// 导出单例
export const workflowTemplateConnectionManager = new WorkflowTemplateConnectionManager();