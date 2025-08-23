import { executionAPI } from './api';

// 为String添加hashCode方法的声明
declare global {
  interface String {
    hashCode(): number;
  }
}

// 实现hashCode方法
if (!String.prototype.hashCode) {
  String.prototype.hashCode = function(): number {
    let hash = 0;
    for (let i = 0; i < this.length; i++) {
      const char = this.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // 转换为32位整数
    }
    return hash;
  };
}

// API响应类型定义
interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data: T;
}

// 类型定义
export interface WorkflowTemplateConnection {
  subdivision_id: string;
  subdivision_name: string;
  subdivision_description: string;
  created_at?: string;
  
  parent_workflow: {
    workflow_base_id: string;
    workflow_name: string;
    workflow_description: string;
    connected_node: {
      node_base_id: string;
      node_name: string;
      node_type: string;
      task_title: string;
      task_description: string;
    };
  };
  
  sub_workflow: {
    workflow_base_id: string;
    workflow_name: string;
    workflow_description: string;
    instance_id?: string;
    status: string;
    started_at?: string;
    completed_at?: string;
    total_nodes: number;
    completed_nodes: number;
  };
}

export interface TemplateNode {
  id: string;
  type: 'workflow_template';
  label: string;
  description: string;
  is_parent: boolean;
  recursion_level?: number;  // 新增：递归层级
  status?: string;
  total_nodes?: number;
  completed_nodes?: number;
  completion_rate?: number;
  workflow_instance_id?: string;  // 新增：工作流实例ID
  
  // 新增：内部节点相关属性
  isInternalNode?: boolean;
  originalType?: string;
  node_type?: string;
  task_description?: string;
  parentWorkflowId?: string;
  
  connected_nodes?: Array<{
    node_base_id: string;
    node_name: string;
    node_type: string;
    subdivision_name: string;
  }>;
  // React Flow 相关属性
  position?: { x: number; y: number };
  data?: any;
}

export interface TemplateEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;     // 新增：React Flow源句柄ID
  targetHandle?: string;     // 新增：React Flow目标句柄ID
  type: 'subdivision_connection';
  label: string;
  subdivision_id: string;
  connected_node_name: string;
  task_title: string;
  created_at?: string;
  recursion_level?: number;  // 新增：递归层级
  edge_weight?: number;      // 新增：边权重
  // React Flow 相关属性
  animated?: boolean;
  style?: any;
  labelStyle?: any;
}

export interface ConnectionGraph {
  nodes: TemplateNode[];
  edges: TemplateEdge[];
  layout: {
    algorithm: string;
    direction?: string;
    node_spacing?: number;
    level_spacing?: number;
    repulsion?: number;
    attraction?: number;
    radius?: number;
    max_recursion_level?: number;    // 新增：最大递归层级
    level_node_counts?: Record<number, number>;  // 新增：每层节点数量
  };
}

export interface WorkflowTemplateConnectionData {
  workflow_instance_id: string;
  template_connections: WorkflowTemplateConnection[];
  connection_graph: ConnectionGraph;
  recursive_levels?: number;  // 新增：实际递归层级数
  statistics: {
    total_subdivisions: number;
    completed_sub_workflows: number;
    unique_parent_workflows: number;
    unique_sub_workflows: number;
    max_recursion_depth?: number;  // 新增：最大递归深度统计
  };
}

export interface SubdivisionConnectionDetail {
  subdivision_id: string;
  subdivision_name: string;
  subdivision_description: string;
  created_at?: string;
  subdivider_name: string;
  original_task: {
    task_id: string;
    task_title: string;
  };
  sub_workflow: {
    workflow_base_id: string;
    workflow_name: string;
    instance_id?: string;
    total_nodes: number;
    completed_nodes: number;
  };
  status: string;
}

// 新增：合并相关接口
export interface MergeCandidate {
  subdivision_id: string;
  parent_workflow_id: string;
  sub_workflow_id: string;
  replaceable_node: {
    node_base_id: string;
    name: string;
    type: string;
    task_description?: string;
  };
  compatibility: {
    is_compatible: boolean;
    issues: string[];
    recommendations: string[];
  };
  replacement_structure?: {
    start_nodes: any[];
    end_nodes: any[];
    total_nodes: number;
    total_connections: number;
  };
  merge_complexity?: 'simple' | 'complex';
}

export interface DetailedWorkflowStructure {
  workflow_base_id: string;
  nodes: Array<{
    node_id: string;
    node_base_id: string;
    name: string;
    type: string;
    task_description: string;
    position: { x: number; y: number };
    processor_id?: string;
  }>;
  connections: Array<{
    connection_id: string;
    from_node: {
      node_id: string;
      node_base_id: string;
      name: string;
    };
    to_node: {
      node_id: string;
      node_base_id: string;
      name: string;
    };
    connection_type: string;
  }>;
  node_count: number;
  connection_count: number;
}

export interface DetailedConnectionData {
  template_connections: WorkflowTemplateConnection[];
  detailed_workflows: Record<string, DetailedWorkflowStructure>;
  merge_candidates: MergeCandidate[];
  detailed_connection_graph: {
    nodes: Array<{
      id: string;
      type: string;
      label: string;
      data: any;
      position?: { x: number; y: number };
    }>;
    edges: Array<{
      id: string;
      source: string;
      target: string;
      type: string;
      label: string;
      data: any;
    }>;
    layout: any;
  };
  statistics: any;
}

export interface MergePreviewData {
  parent_workflow: {
    workflow_base_id: string;
    name: string;
    current_nodes: number;
    current_connections: number;
  };
  merge_summary: {
    total_merge_candidates: number;
    valid_merges: number;
    invalid_merges: number;
    net_nodes_change: number;
    net_connections_change: number;
  };
  merge_feasibility: {
    can_proceed: boolean;
    complexity_increase: 'low' | 'medium' | 'high';
    recommended_approach: string;
  };
  valid_merge_previews: Array<{
    candidate_id: string;
    target_node: {
      node_base_id: string;
      name: string;
      type: string;
    };
    replacement_info: {
      sub_workflow_name: string;
      nodes_to_add: number;
      connections_to_add: number;
    };
    preview: any;
  }>;
  invalid_merge_previews: Array<{
    candidate_id: string;
    error: string;
  }>;
}

export interface MergeConfig {
  new_workflow_name: string;
  new_workflow_description?: string;
  preserve_original?: boolean;
  execute_immediately?: boolean;
  notify_on_completion?: boolean;
}

export interface MergeExecutionResult {
  success: boolean;
  message: string;
  new_workflow_id?: string;
  new_workflow_name?: string;
  merge_statistics?: {
    nodes_created: number;
    connections_created: number;
    nodes_replaced: number;
    replacement_operations: number;
  };
  errors?: string[];
  warnings?: string[];
}

// 工作流模板连接管理器类
class WorkflowTemplateConnectionManager {
  private static instance: WorkflowTemplateConnectionManager;
  private connectionCache: Map<string, WorkflowTemplateConnectionData> = new Map();
  private loadingPromises: Map<string, Promise<WorkflowTemplateConnectionData>> = new Map();
  
  // 新增：合并相关缓存
  private detailedConnectionCache: Map<string, DetailedConnectionData> = new Map();
  private mergePreviewCache: Map<string, MergePreviewData> = new Map();
  private mergeLoadingPromises: Map<string, Promise<any>> = new Map();

  static getInstance(): WorkflowTemplateConnectionManager {
    if (!WorkflowTemplateConnectionManager.instance) {
      WorkflowTemplateConnectionManager.instance = new WorkflowTemplateConnectionManager();
    }
    return WorkflowTemplateConnectionManager.instance;
  }

  /**
   * 获取工作流实例的模板连接图数据
   */
  async getTemplateConnections(workflowInstanceId: string, maxDepth: number = 10): Promise<WorkflowTemplateConnectionData> {
    console.log('🔍 [WorkflowTemplateConnectionManager] 获取模板连接图:', workflowInstanceId, '递归深度:', maxDepth);
    
    // 包含递归深度的缓存键
    const cacheKey = `${workflowInstanceId}_depth_${maxDepth}`;
    
    // 检查缓存
    if (this.connectionCache.has(cacheKey)) {
      console.log('✅ [WorkflowTemplateConnectionManager] 使用缓存的连接图数据');
      return this.connectionCache.get(cacheKey)!;
    }

    // 检查是否正在加载
    if (this.loadingPromises.has(cacheKey)) {
      return await this.loadingPromises.get(cacheKey)!;
    }

    // 创建加载Promise
    const loadingPromise = this._loadTemplateConnections(workflowInstanceId, maxDepth);
    this.loadingPromises.set(cacheKey, loadingPromise);

    try {
      const result = await loadingPromise;
      this.loadingPromises.delete(cacheKey);
      return result;
    } catch (error) {
      this.loadingPromises.delete(cacheKey);
      throw error;
    }
  }

  /**
   * 获取细分连接图数据（专门用于图形可视化）
   */
  async getSubdivisionConnectionGraph(
    workflowInstanceId: string,
    options: {
      includePending?: boolean;
      layoutAlgorithm?: 'hierarchical' | 'force' | 'circular' | 'file_system';
      maxDepth?: number;
    } = {}
  ): Promise<{ graph: ConnectionGraph; metadata: any }> {
    console.log('🎨 [WorkflowTemplateConnectionManager] 获取细分连接图数据:', workflowInstanceId, options);
    
    try {
      const { 
        includePending = false, 
        layoutAlgorithm = 'hierarchical',
        maxDepth = 10 
      } = options;
      
      const response = await executionAPI.getSubdivisionConnectionGraph(
        workflowInstanceId,
        includePending,
        layoutAlgorithm,
        maxDepth
      );
      
      // 响应拦截器已经处理了响应格式，直接检查success和data字段
      if (response && (response as any).success && (response as any).data) {
        const data = (response as any).data;
        // 增强图形数据用于可视化
        const enhancedGraph = this._enhanceGraphForVisualization(data.graph);
        
        return {
          graph: enhancedGraph,
          metadata: data.metadata
        };
      } else {
        throw new Error('获取细分连接图数据失败');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 获取细分连接图数据失败:', error);
      throw error;
    }
  }

  /**
   * 获取单个细分连接的详细信息
   */
  async getSubdivisionConnectionDetail(subdivisionId: string): Promise<SubdivisionConnectionDetail> {
    console.log('🔍 [WorkflowTemplateConnectionManager] 获取细分连接详情:', subdivisionId);
    
    try {
      const response = await executionAPI.getSubdivisionConnectionDetail(subdivisionId);
      
      if (response && (response as any).success && (response as any).data) {
        return (response as any).data;
      } else {
        throw new Error('获取细分连接详情失败');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 获取细分连接详情失败:', error);
      throw error;
    }
  }

  /**
   * 获取工作流模板的连接摘要
   */
  async getWorkflowTemplateConnectionSummary(workflowBaseId: string): Promise<any> {
    console.log('📊 [WorkflowTemplateConnectionManager] 获取工作流模板连接摘要:', workflowBaseId);
    
    try {
      const response = await executionAPI.getWorkflowTemplateConnectionSummary(workflowBaseId);
      
      if (response && (response as any).success && (response as any).data) {
        return (response as any).data;
      } else {
        throw new Error('获取工作流模板连接摘要失败');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 获取工作流模板连接摘要失败:', error);
      throw error;
    }
  }

  /**
   * 获取详细的工作流模板连接数据（用于合并功能）
   */
  async getDetailedWorkflowConnections(workflowInstanceId: string, maxDepth: number = 10): Promise<DetailedConnectionData> {
    console.log('🔍 [WorkflowTemplateConnectionManager] 获取详细工作流连接:', workflowInstanceId, '深度:', maxDepth);
    
    // 包含递归深度的缓存键
    const cacheKey = `detailed_${workflowInstanceId}_depth_${maxDepth}`;
    
    // 检查缓存
    if (this.detailedConnectionCache.has(cacheKey)) {
      console.log('✅ [WorkflowTemplateConnectionManager] 使用缓存的详细连接数据');
      return this.detailedConnectionCache.get(cacheKey)!;
    }

    // 检查是否正在加载
    if (this.mergeLoadingPromises.has(cacheKey)) {
      return await this.mergeLoadingPromises.get(cacheKey)!;
    }

    // 创建加载Promise
    const loadingPromise = this._loadDetailedConnections(workflowInstanceId, maxDepth);
    this.mergeLoadingPromises.set(cacheKey, loadingPromise);

    try {
      const result = await loadingPromise;
      this.mergeLoadingPromises.delete(cacheKey);
      return result;
    } catch (error) {
      this.mergeLoadingPromises.delete(cacheKey);
      throw error;
    }
  }

  /**
   * 预览工作流合并结果
   */
  async previewWorkflowMerge(parentWorkflowId: string, selectedCandidates: MergeCandidate[]): Promise<MergePreviewData> {
    console.log('🔍 [WorkflowTemplateConnectionManager] 预览工作流合并:', parentWorkflowId, '候选数:', selectedCandidates.length);
    
    // 生成预览缓存键
    const candidateIds = selectedCandidates.map(c => c.subdivision_id).sort().join(',');
    const cacheKey = `preview_${parentWorkflowId}_${candidateIds}`;
    
    // 检查缓存（预览数据缓存时间较短）
    if (this.mergePreviewCache.has(cacheKey)) {
      console.log('✅ [WorkflowTemplateConnectionManager] 使用缓存的合并预览');
      return this.mergePreviewCache.get(cacheKey)!;
    }

    try {
      // 调用API获取预览数据
      const { default: api } = await import('./api');
      const response = await api.post(`/workflow-merge/${parentWorkflowId}/merge-preview`, selectedCandidates);
      
      if (response.data?.success && response.data?.data?.merge_preview) {
        const previewData = response.data.data.merge_preview;
        
        // 缓存预览数据（5分钟过期）
        this.mergePreviewCache.set(cacheKey, previewData);
        setTimeout(() => {
          this.mergePreviewCache.delete(cacheKey);
        }, 5 * 60 * 1000); // 5分钟
        
        console.log('✅ [WorkflowTemplateConnectionManager] 合并预览获取成功');
        return previewData;
      } else {
        throw new Error('获取合并预览数据失败');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 预览工作流合并失败:', error);
      throw error;
    }
  }

  /**
   * 执行工作流合并
   */
  async executeWorkflowMerge(
    parentWorkflowId: string, 
    selectedMerges: any[], 
    mergeConfig: MergeConfig
  ): Promise<MergeExecutionResult> {
    console.log('🔄 [WorkflowTemplateConnectionManager] 执行工作流合并:', {
      parentWorkflowId,
      mergesCount: selectedMerges.length,
      config: mergeConfig
    });

    try {
      // 调用API执行合并
      const { default: api } = await import('./api');
      const response = await api.post(`/workflow-merge/${parentWorkflowId}/execute-merge`, {
        selected_merges: selectedMerges,
        merge_config: mergeConfig
      });
      
      if (response.data?.success) {
        const executionResult = response.data.data;
        
        // 清除相关缓存（因为数据已经改变）
        this._clearMergeRelatedCache(parentWorkflowId);
        
        console.log('✅ [WorkflowTemplateConnectionManager] 工作流合并执行成功');
        return executionResult;
      } else {
        throw new Error(response.data?.message || '合并执行失败');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 执行工作流合并失败:', error);
      throw error;
    }
  }

  /**
   * 获取合并兼容性检查
   */
  async getMergeCompatibility(workflowBaseId: string, candidateIds: string[]): Promise<any> {
    console.log('🔍 [WorkflowTemplateConnectionManager] 获取合并兼容性:', workflowBaseId, candidateIds);
    
    try {
      const { default: api } = await import('./api');
      const response = await api.get(`/workflow-merge/${workflowBaseId}/merge-compatibility`, {
        params: { candidate_ids: candidateIds.join(',') }
      });
      
      if (response.data?.success) {
        return response.data.data;
      } else {
        throw new Error('获取合并兼容性数据失败');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 获取合并兼容性失败:', error);
      throw error;
    }
  }

  /**
   * 私有方法：加载详细连接数据
   */
  private async _loadDetailedConnections(workflowInstanceId: string, maxDepth: number): Promise<DetailedConnectionData> {
    try {
      const { default: api } = await import('./api');
      const response = await api.get(`/workflow-merge/${workflowInstanceId}/detailed-connections`, {
        params: { max_depth: maxDepth }
      });
      
      // 处理两种可能的响应格式
      let detailedData: DetailedConnectionData | null = null;
      
      if (response.data?.success && response.data?.data?.detailed_connections) {
        // 格式1: 包装的BaseResponse
        console.log('📡 [WorkflowTemplateConnectionManager] 检测到包装的BaseResponse格式');
        detailedData = response.data.data.detailed_connections;
      } else if (response.data?.success && response.data?.data) {
        // 格式1.5: 包装的BaseResponse但detailed_connections在data内
        console.log('📡 [WorkflowTemplateConnectionManager] 检测到包装的BaseResponse格式(data内容直接为详细数据)');
        detailedData = response.data.data;
      } else if (response.data?.detailed_connections) {
        // 格式2: 直接的数据格式
        console.log('📡 [WorkflowTemplateConnectionManager] 检测到直接的数据格式');
        detailedData = response.data;
      }
      
      if (detailedData) {
        // 缓存数据
        const cacheKey = `detailed_${workflowInstanceId}_depth_${maxDepth}`;
        this.detailedConnectionCache.set(cacheKey, detailedData);
        
        console.log('✅ [WorkflowTemplateConnectionManager] 详细连接数据加载成功');
        console.log('   - 合并候选数:', detailedData.merge_candidates?.length || 0);
        console.log('   - 详细工作流数:', Object.keys(detailedData.detailed_workflows || {}).length);
        
        return detailedData;
      } else {
        console.error('❌ [WorkflowTemplateConnectionManager] API响应格式不正确:');
        console.error('   - 响应数据:', response.data);
        console.error('   - 包装格式检查: success字段=', response.data?.success, ', data.detailed_connections=', !!response.data?.data?.detailed_connections);
        console.error('   - 直接格式检查: detailed_connections字段=', !!response.data?.detailed_connections);
        throw new Error('API响应格式不正确，无法解析详细连接数据');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 加载详细连接数据失败:', error);
      throw error;
    }
  }

  /**
   * 私有方法：清除合并相关缓存
   */
  private _clearMergeRelatedCache(workflowId?: string): void {
    if (workflowId) {
      // 清除特定工作流的缓存
      const keysToDelete: string[] = [];
      
      // 清除详细连接缓存
      for (const key of Array.from(this.detailedConnectionCache.keys())) {
        if (key.includes(workflowId)) {
          keysToDelete.push(key);
        }
      }
      keysToDelete.forEach(key => this.detailedConnectionCache.delete(key));
      
      // 清除合并预览缓存
      const previewKeysToDelete: string[] = [];
      for (const key of Array.from(this.mergePreviewCache.keys())) {
        if (key.includes(workflowId)) {
          previewKeysToDelete.push(key);
        }
      }
      previewKeysToDelete.forEach(key => this.mergePreviewCache.delete(key));
      
      console.log('🧹 [WorkflowTemplateConnectionManager] 已清除工作流合并相关缓存:', workflowId);
    } else {
      // 清除所有合并相关缓存
      this.detailedConnectionCache.clear();
      this.mergePreviewCache.clear();
      this.mergeLoadingPromises.clear();
      console.log('🧹 [WorkflowTemplateConnectionManager] 已清除所有合并相关缓存');
    }
  }

  private async _loadTemplateConnections(workflowInstanceId: string, maxDepth: number = 10): Promise<WorkflowTemplateConnectionData> {
    try {
      const response = await executionAPI.getWorkflowTemplateConnections(workflowInstanceId, maxDepth);
      
      if (response && (response as any).success && (response as any).data) {
        const connectionData: WorkflowTemplateConnectionData = (response as any).data;
        
        // 缓存数据（包含递归深度）
        const cacheKey = `${workflowInstanceId}_depth_${maxDepth}`;
        this.connectionCache.set(cacheKey, connectionData);
        console.log('✅ [WorkflowTemplateConnectionManager] 模板连接数据加载成功，找到', 
                   connectionData.statistics.total_subdivisions, '个连接关系，递归深度', maxDepth);
        
        return connectionData;
      } else {
        throw new Error('获取模板连接数据失败');
      }
    } catch (error) {
      console.error('❌ [WorkflowTemplateConnectionManager] 加载模板连接数据失败:', error);
      throw error;
    }
  }

  /**
   * 增强图形数据用于可视化
   */
  private _enhanceGraphForVisualization(graph: ConnectionGraph): ConnectionGraph {
    const enhancedNodes = graph.nodes.map((node, index) => {
      // 为节点添加位置信息
      const position = this._calculateNodePosition(node, index, graph.layout, graph.nodes.length);
      
      // 为节点添加样式数据
      const enhancedNode: TemplateNode = {
        ...node,
        position,
        data: {
          ...node,
          // 添加用于React Flow的数据
          className: this._getNodeClassName(node),
          style: this._getNodeStyle(node)
        }
      };
      
      return enhancedNode;
    });

    const enhancedEdges = graph.edges.map(edge => ({
      ...edge,
      animated: true,  // 添加动画效果
      style: {
        strokeWidth: 2,
        stroke: '#666'
      },
      labelStyle: {
        fontSize: 12,
        fontWeight: 'bold'
      }
    }));

    return {
      ...graph,
      nodes: enhancedNodes,
      edges: enhancedEdges
    };
  }

  /**
   * 计算节点位置
   */
  private _calculateNodePosition(node: TemplateNode, index: number, layout: any, totalNodes: number = 1): { x: number; y: number } {
    const { algorithm, node_spacing = 180, level_spacing = 120 } = layout;

    switch (algorithm) {
      case 'tree':
        return this._calculateTreePosition(node, layout);
      
      case 'file_system':
        return this._calculateFileSystemPosition(node, layout);
      
      case 'recursive_hierarchical':
        return this._calculateRecursiveHierarchicalPosition(node, layout);
        
      case 'hierarchical':
        return {
          x: index * node_spacing,
          y: node.is_parent ? 0 : level_spacing
        };
      
      case 'force':
        // 简单的力导向布局初始位置
        return {
          x: Math.random() * 400,
          y: Math.random() * 300
        };
      
      case 'circular':
        const radius = layout.radius || 200;
        const angle = (2 * Math.PI * index) / totalNodes;
        return {
          x: radius * Math.cos(angle),
          y: radius * Math.sin(angle)
        };
      
      default:
        return {
          x: index * 200,
          y: node.is_parent ? 0 : 150
        };
    }
  }

  /**
   * 树状布局位置计算
   */
  private _calculateTreePosition(node: TemplateNode, layout: any): { x: number; y: number } {
    const { node_spacing = 250, level_spacing = 150, tree_layout_data } = layout;
    
    if (!tree_layout_data || !tree_layout_data.node_positions) {
      // 如果没有树状布局数据，回退到简单布局
      return {
        x: (node.recursion_level || 0) * node_spacing,
        y: 0
      };
    }
    
    const nodePosition = tree_layout_data.node_positions[node.id];
    if (!nodePosition) {
      // 如果节点位置数据不存在，使用默认位置
      return {
        x: (node.recursion_level || 0) * node_spacing,
        y: 0
      };
    }
    
    const level = nodePosition.level;
    const indexInLevel = nodePosition.index_in_level;
    const totalInLevel = nodePosition.total_in_level;
    const children = nodePosition.children || [];
    
    // 计算Y坐标（垂直层级）
    const y = level * level_spacing;
    
    // 计算X坐标（树状分布）
    let x = 0;
    
    if (level === 0) {
      // 根节点居中
      x = indexInLevel * node_spacing;
    } else {
      // 子节点基于父节点位置分布
      const parentId = nodePosition.parent;
      if (parentId && tree_layout_data.node_positions[parentId]) {
        const parentPosition = tree_layout_data.node_positions[parentId];
        const parentLevel = parentPosition.level;
        const parentIndexInLevel = parentPosition.index_in_level;
        
        // 父节点的X坐标
        const parentX = parentLevel === 0 ? 
          parentIndexInLevel * node_spacing : 
          this._getParentXPosition(parentId, tree_layout_data, node_spacing);
        
        // 子节点在父节点周围分布
        const siblingCount = parentPosition.children.length;
        const siblingIndex = parentPosition.children.indexOf(node.id);
        
        if (siblingCount === 1) {
          // 单个子节点直接在父节点下方
          x = parentX;
        } else {
          // 多个子节点左右分布
          const spreadWidth = Math.min(siblingCount * node_spacing, node_spacing * 3);
          const startX = parentX - spreadWidth / 2;
          x = startX + (siblingIndex * spreadWidth) / (siblingCount - 1);
        }
      } else {
        // 没有父节点信息，使用层级索引
        x = indexInLevel * node_spacing;
      }
    }
    
    return { x, y };
  }

  /**
   * 递归获取父节点的X坐标
   */
  private _getParentXPosition(nodeId: string, treeLayoutData: any, nodeSpacing: number): number {
    const nodePosition = treeLayoutData.node_positions[nodeId];
    if (!nodePosition) return 0;
    
    if (nodePosition.level === 0) {
      // 根节点
      return nodePosition.index_in_level * nodeSpacing;
    } else {
      // 递归获取父节点位置
      const parentId = nodePosition.parent;
      if (parentId) {
        return this._getParentXPosition(parentId, treeLayoutData, nodeSpacing);
      }
      return nodePosition.index_in_level * nodeSpacing;
    }
  }

  /**
   * 文件系统式位置计算
   */
  private _calculateFileSystemPosition(node: TemplateNode, layout: any): { x: number; y: number } {
    const { node_spacing = 180, level_spacing = 150 } = layout;
    const recursionLevel = node.recursion_level || 0;
    const levelNodeCounts = layout.level_node_counts || {};
    
    // X坐标：基于递归层级，每层向右偏移
    const x = recursionLevel * node_spacing;
    
    // Y坐标：同一层级的节点按顺序垂直排列
    let yIndex = 0;
    
    // 计算当前节点在同一层级中的位置索引
    // 这里需要一个全局的节点索引计算，暂时使用简单的方法
    if (layout.nodePositionMap && layout.nodePositionMap[node.id]) {
      yIndex = layout.nodePositionMap[node.id].yIndex;
    } else {
      // 如果没有预计算的位置映射，使用节点ID的hash值作为fallback
      yIndex = Math.abs(node.id.hashCode() || 0) % (levelNodeCounts[recursionLevel] || 1);
    }
    
    const y = yIndex * level_spacing;
    
    return { x, y };
  }

  /**
   * 递归层级布局位置计算
   */
  private _calculateRecursiveHierarchicalPosition(node: TemplateNode, layout: any): { x: number; y: number } {
    const { node_spacing = 180, level_spacing = 120 } = layout;
    const recursionLevel = node.recursion_level || 0;
    const levelNodeCounts = layout.level_node_counts || {};
    
    // 层级化布局：每层从左到右，顶层在上方
    const nodesInLevel = levelNodeCounts[recursionLevel] || 1;
    const levelStartX = recursionLevel * node_spacing;
    
    // 在同一层级中的位置
    let nodeIndexInLevel = 0;
    if (layout.nodePositionMap && layout.nodePositionMap[node.id]) {
      nodeIndexInLevel = layout.nodePositionMap[node.id].indexInLevel;
    }
    
    return {
      x: levelStartX + (nodeIndexInLevel * (node_spacing * 0.6)),
      y: recursionLevel * level_spacing
    };
  }

  /**
   * 获取节点样式类名
   */
  private _getNodeClassName(node: TemplateNode): string {
    let className = 'workflow-template-node';
    
    if (node.is_parent) {
      className += ' parent-workflow';
    } else {
      className += ' sub-workflow';
      
      // 根据状态添加样式
      switch (node.status) {
        case 'completed':
          className += ' completed';
          break;
        case 'running':
          className += ' running';
          break;
        case 'failed':
          className += ' failed';
          break;
        default:
          className += ' pending';
      }
    }
    
    return className;
  }

  /**
   * 获取节点样式
   */
  private _getNodeStyle(node: TemplateNode): any {
    const baseStyle = {
      padding: '10px',
      borderRadius: '8px',
      border: '2px solid',
      minWidth: '120px',
      textAlign: 'center'
    };

    if (node.is_parent) {
      return {
        ...baseStyle,
        backgroundColor: '#e3f2fd',
        borderColor: '#2196f3',
        color: '#1976d2'
      };
    } else {
      // 子工作流根据状态设置颜色
      switch (node.status) {
        case 'completed':
          return {
            ...baseStyle,
            backgroundColor: '#e8f5e8',
            borderColor: '#4caf50',
            color: '#2e7d32'
          };
        case 'running':
          return {
            ...baseStyle,
            backgroundColor: '#fff3e0',
            borderColor: '#ff9800',
            color: '#f57c00'
          };
        case 'failed':
          return {
            ...baseStyle,
            backgroundColor: '#ffebee',
            borderColor: '#f44336',
            color: '#d32f2f'
          };
        default:
          return {
            ...baseStyle,
            backgroundColor: '#f5f5f5',
            borderColor: '#9e9e9e',
            color: '#424242'
          };
      }
    }
  }

  /**
   * 清除缓存
   */
  clearCache(): void {
    this.connectionCache.clear();
    this.loadingPromises.clear();
    this.detailedConnectionCache.clear();
    this.mergePreviewCache.clear();
    this.mergeLoadingPromises.clear();
    console.log('🧹 [WorkflowTemplateConnectionManager] 所有缓存已清除');
  }

  /**
   * 清除特定工作流实例的缓存
   */
  clearWorkflowCache(workflowInstanceId: string): void {
    // 清除基础连接缓存
    const keysToDelete: string[] = [];
    for (const key of Array.from(this.connectionCache.keys())) {
      if (key.includes(workflowInstanceId)) {
        keysToDelete.push(key);
      }
    }
    keysToDelete.forEach(key => {
      this.connectionCache.delete(key);
      this.loadingPromises.delete(key);
    });

    // 清除合并相关缓存
    this._clearMergeRelatedCache(workflowInstanceId);
    
    console.log('🧹 [WorkflowTemplateConnectionManager] 已清除工作流缓存:', workflowInstanceId);
  }
}

// 导出单例实例
export const workflowTemplateConnectionManager = WorkflowTemplateConnectionManager.getInstance();
export default workflowTemplateConnectionManager;