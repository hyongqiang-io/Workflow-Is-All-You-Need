/**
 * 子工作流节点实例管理器
 * 统一管理主工作流下所有子工作流实例及其节点实例的详细信息
 */

import { executionAPI } from '../services/api';

export interface SubWorkflowNodeDetail {
  node_instance_id: string;
  node_name: string;
  node_type: string;
  status: string;
  // 详细信息 - 这些是之前缺失的
  retry_count: number;
  execution_duration_seconds: number;
  input_data: any;
  output_data: any;
  error_message?: string;
  // 时间信息
  created_at: string;
  started_at?: string;
  completed_at?: string;
  // 任务信息
  task_count: number;
  tasks?: any[];
  // 处理器信息
  processor_name?: string;
  processor_type?: string;
}

interface SubWorkflowInstanceDetail {
  subdivision_id: string;
  sub_workflow_instance_id: string;
  subdivision_name: string;
  status: string;
  nodes: SubWorkflowNodeDetail[];
  total_nodes: number;
  completed_nodes: number;
  running_nodes: number;
  failed_nodes: number;
}

class SubWorkflowInstanceManager {
  private static instance: SubWorkflowInstanceManager;
  private nodeDetailsCache: Map<string, SubWorkflowNodeDetail> = new Map();
  private subWorkflowDetailsCache: Map<string, SubWorkflowInstanceDetail> = new Map();
  private loadingPromises: Map<string, Promise<any>> = new Map();

  static getInstance(): SubWorkflowInstanceManager {
    if (!SubWorkflowInstanceManager.instance) {
      SubWorkflowInstanceManager.instance = new SubWorkflowInstanceManager();
    }
    return SubWorkflowInstanceManager.instance;
  }

  /**
   * 获取子工作流节点的详细信息
   * @param nodeInstanceId 节点实例ID
   * @param subWorkflowInstanceId 子工作流实例ID
   */
  async getNodeDetail(nodeInstanceId: string, subWorkflowInstanceId?: string): Promise<SubWorkflowNodeDetail | null> {
    console.log('🔍 [SubWorkflowInstanceManager] 获取节点详细信息:', nodeInstanceId, subWorkflowInstanceId);
    
    // 检查缓存
    if (this.nodeDetailsCache.has(nodeInstanceId)) {
      console.log('✅ [SubWorkflowInstanceManager] 使用缓存的节点详细信息');
      return this.nodeDetailsCache.get(nodeInstanceId)!;
    }

    // 检查是否正在加载
    const loadingKey = `node-${nodeInstanceId}`;
    if (this.loadingPromises.has(loadingKey)) {
      return await this.loadingPromises.get(loadingKey);
    }

    // 创建加载Promise
    const loadingPromise = this._loadNodeDetail(nodeInstanceId, subWorkflowInstanceId);
    this.loadingPromises.set(loadingKey, loadingPromise);

    try {
      const result = await loadingPromise;
      this.loadingPromises.delete(loadingKey);
      return result;
    } catch (error) {
      this.loadingPromises.delete(loadingKey);
      throw error;
    }
  }

  /**
   * 批量获取子工作流所有节点的详细信息
   */
  async getSubWorkflowNodesDetail(subWorkflowInstanceId: string): Promise<SubWorkflowNodeDetail[]> {
    console.log('🔍 [SubWorkflowInstanceManager] 批量获取子工作流节点详细信息:', subWorkflowInstanceId);
    
    try {
      // 首先尝试通过子工作流实例ID获取节点详细信息
      const response = await executionAPI.getWorkflowNodesDetail(subWorkflowInstanceId);
      
      if (response && (response.data?.success !== false)) {
        const nodesData = response.data?.data || response.data || response;
        
        if (nodesData && nodesData.nodes) {
          console.log('✅ [SubWorkflowInstanceManager] 获取到子工作流节点详细信息:', nodesData.nodes.length, '个节点');
          
          // 转换并缓存节点详细信息
          const nodeDetails: SubWorkflowNodeDetail[] = nodesData.nodes.map((node: any) => {
            const detail: SubWorkflowNodeDetail = {
              node_instance_id: node.node_instance_id,
              node_name: node.node_name,
              node_type: node.node_type,
              status: node.status,
              retry_count: node.retry_count || 0,
              execution_duration_seconds: node.execution_duration_seconds || 0,
              input_data: node.input_data || {},
              output_data: node.output_data || {},
              error_message: node.error_message,
              created_at: node.timestamps?.created_at || node.created_at,
              started_at: node.timestamps?.started_at || node.started_at,
              completed_at: node.timestamps?.completed_at || node.completed_at,
              task_count: node.tasks ? node.tasks.length : 0,
              tasks: node.tasks || [],
              processor_name: node.processor_name,
              processor_type: node.processor_type || node.node_type,
            };
            
            // 缓存节点详细信息
            this.nodeDetailsCache.set(node.node_instance_id, detail);
            return detail;
          });
          
          return nodeDetails;
        }
      }
      
      console.warn('⚠️ [SubWorkflowInstanceManager] 未能获取到子工作流节点详细信息');
      return [];
      
    } catch (error) {
      console.error('❌ [SubWorkflowInstanceManager] 获取子工作流节点详细信息失败:', error);
      return [];
    }
  }

  private async _loadNodeDetail(nodeInstanceId: string, subWorkflowInstanceId?: string): Promise<SubWorkflowNodeDetail | null> {
    try {
      // 如果有子工作流实例ID，优先获取整个子工作流的节点信息
      if (subWorkflowInstanceId) {
        const allNodes = await this.getSubWorkflowNodesDetail(subWorkflowInstanceId);
        const nodeDetail = allNodes.find(node => node.node_instance_id === nodeInstanceId);
        if (nodeDetail) {
          return nodeDetail;
        }
      }

      // 备用方案：尝试通过节点实例ID获取详细信息
      console.log('🔄 [SubWorkflowInstanceManager] 尝试通过节点实例API获取详细信息');
      
      // 这里可以添加专门的节点详细信息API调用
      // 目前使用基础信息作为回退
      const basicDetail: SubWorkflowNodeDetail = {
        node_instance_id: nodeInstanceId,
        node_name: '节点',
        node_type: 'unknown',
        status: 'unknown',
        retry_count: 0,
        execution_duration_seconds: 0,
        input_data: {},
        output_data: {},
        created_at: new Date().toISOString(),
        task_count: 0
      };
      
      // 缓存基础信息
      this.nodeDetailsCache.set(nodeInstanceId, basicDetail);
      return basicDetail;
      
    } catch (error) {
      console.error('❌ [SubWorkflowInstanceManager] 加载节点详细信息失败:', error);
      return null;
    }
  }

  /**
   * 获取子工作流实例的详细信息
   */
  async getSubWorkflowDetail(subdivisionId: string): Promise<SubWorkflowInstanceDetail | null> {
    console.log('🔍 [SubWorkflowInstanceManager] 获取子工作流详细信息:', subdivisionId);
    
    // 检查缓存
    if (this.subWorkflowDetailsCache.has(subdivisionId)) {
      return this.subWorkflowDetailsCache.get(subdivisionId)!;
    }

    try {
      // 通过subdivision详细信息API获取
      const response = await executionAPI.getNodeSubdivisionDetail(subdivisionId);
      
      if (response && response.data?.success && response.data?.data) {
        const subdivisions = response.data.data;
        
        // 处理每个subdivision
        for (const subdivision of subdivisions) {
          if (subdivision.subdivision_id === subdivisionId) {
            // 获取此subdivision的节点详细信息
            const nodeDetails = subdivision.sub_workflow_instance_id 
              ? await this.getSubWorkflowNodesDetail(subdivision.sub_workflow_instance_id)
              : [];
            
            const detail: SubWorkflowInstanceDetail = {
              subdivision_id: subdivision.subdivision_id,
              sub_workflow_instance_id: subdivision.sub_workflow_instance_id,
              subdivision_name: subdivision.subdivision_name,
              status: subdivision.status,
              nodes: nodeDetails,
              total_nodes: subdivision.total_nodes || nodeDetails.length,
              completed_nodes: subdivision.completed_nodes || nodeDetails.filter(n => n.status === 'completed').length,
              running_nodes: subdivision.running_nodes || nodeDetails.filter(n => n.status === 'running').length,
              failed_nodes: subdivision.failed_nodes || nodeDetails.filter(n => n.status === 'failed').length,
            };
            
            // 缓存详细信息
            this.subWorkflowDetailsCache.set(subdivisionId, detail);
            return detail;
          }
        }
      }
      
      return null;
      
    } catch (error) {
      console.error('❌ [SubWorkflowInstanceManager] 获取子工作流详细信息失败:', error);
      return null;
    }
  }

  /**
   * 清除缓存
   */
  clearCache() {
    this.nodeDetailsCache.clear();
    this.subWorkflowDetailsCache.clear();
    this.loadingPromises.clear();
  }

  /**
   * 清除特定节点的缓存
   */
  clearNodeCache(nodeInstanceId: string) {
    this.nodeDetailsCache.delete(nodeInstanceId);
  }
}

export const subWorkflowInstanceManager = SubWorkflowInstanceManager.getInstance();