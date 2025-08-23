import { useState, useCallback, useRef } from 'react';
import { message } from 'antd';

interface SubWorkflowInfo {
  has_subdivision: boolean;
  subdivision_count: number;
  subdivision_status?: 'draft' | 'running' | 'completed' | 'failed' | 'cancelled';
  is_expandable: boolean;
  expansion_level: number;
}

interface SubWorkflowDetail {
  subdivision_id: string;
  sub_workflow_instance_id?: string;
  subdivision_name: string;
  status: 'draft' | 'running' | 'completed' | 'failed' | 'cancelled';
  nodes: any[];
  edges: any[];
  total_nodes: number;
  completed_nodes: number;
  running_nodes: number;
  failed_nodes: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface ExpandedNodeState {
  isExpanded: boolean;
  isLoading: boolean;
  subWorkflowData?: SubWorkflowDetail[];
  error?: string;
}

interface UseSubWorkflowExpansionProps {
  workflowInstanceId?: string;
  onExpansionChange?: (nodeId: string, isExpanded: boolean) => void;
}

export const useSubWorkflowExpansion = ({ 
  workflowInstanceId, 
  onExpansionChange 
}: UseSubWorkflowExpansionProps = {}) => {
  // 存储每个节点的展开状态
  const [expandedNodes, setExpandedNodes] = useState<Record<string, ExpandedNodeState>>({});
  
  // 存储工作流的细分信息
  const [subdivisionInfo, setSubdivisionInfo] = useState<Record<string, SubWorkflowInfo>>({});
  
  // 加载状态
  const [isLoadingSubdivisionInfo, setIsLoadingSubdivisionInfo] = useState(false);
  
  // 缓存已加载的数据，避免重复请求
  const loadedDataCache = useRef<Record<string, SubWorkflowDetail[]>>({});

  // 加载工作流的细分信息
  const loadSubdivisionInfo = useCallback(async (instanceId: string) => {
    if (!instanceId) {
      console.log('🔍 useSubWorkflowExpansion: instanceId为空，跳过加载');
      return;
    }
    
    console.log('🔍 useSubWorkflowExpansion: 开始加载subdivision信息');
    console.log(`   - instanceId: ${instanceId}`);
    console.log(`   - API调用URL: /api/execution/workflows/${instanceId}/subdivision-info`);
    
    setIsLoadingSubdivisionInfo(true);
    try {
      // 使用动态导入来避免循环依赖，并使用已配置的api实例
      const { executionAPI } = await import('../services/api');
      
      console.log('🔍 useSubWorkflowExpansion: 使用executionAPI发送请求');
      console.log(`   - 完整请求URL: ${window.location.origin}/api/execution/workflows/${instanceId}/subdivision-info`);
      
      const axiosResponse = await executionAPI.getWorkflowSubdivisionInfo(instanceId);
      const response = axiosResponse.data; // 从axios响应中提取实际数据
      
      console.log('🔍 useSubWorkflowExpansion: API原始响应:', axiosResponse);
      console.log('🔍 useSubWorkflowExpansion: API响应数据:', response);
      console.log('🔍 useSubWorkflowExpansion: API响应数据类型:', typeof response);
      console.log('🔍 useSubWorkflowExpansion: API响应键:', Object.keys(response || {}));
      
      // 检查响应格式并适配不同的结构
      let nodeSubdivisions = {};
      
      if (response && response.success && response.data) {
        // 标准格式: {success: true, data: {...}}
        console.log('🔍 使用标准响应格式');
        console.log('🔍 response.data:', response.data);
        nodeSubdivisions = response.data.node_subdivisions || {};
        console.log('🔍 从response.data.node_subdivisions提取:', nodeSubdivisions);
      } else if (response && response.node_subdivisions) {
        // 直接数据格式: {workflow_instance_id, node_subdivisions, ...}
        console.log('🔍 使用直接数据格式');
        nodeSubdivisions = response.node_subdivisions || {};
        console.log('🔍 从response.node_subdivisions提取:', nodeSubdivisions);
      } else if (response && response.data) {
        // 检查是否数据在response.data下
        console.log('🔍 检查response.data结构:', response.data);
        if (response.data.node_subdivisions) {
          nodeSubdivisions = response.data.node_subdivisions;
          console.log('🔍 从response.data.node_subdivisions提取:', nodeSubdivisions);
        }
      } else {
        console.error('❌ useSubWorkflowExpansion: API响应格式错误:', response);
        console.error('❌ 响应结构分析:');
        console.error('   - response.success:', response?.success);
        console.error('   - response.data:', response?.data);
        console.error('   - response.node_subdivisions:', response?.node_subdivisions);
        throw new Error(response?.message || '获取细分信息失败');
      }
      
      console.log('🔍 useSubWorkflowExpansion: 解析的node_subdivisions:', nodeSubdivisions);
      console.log(`🔍 useSubWorkflowExpansion: 解析的node_subdivisions键数量: ${Object.keys(nodeSubdivisions).length}`);
      
      // 详细记录每个节点的subdivision信息
      Object.entries(nodeSubdivisions).forEach(([nodeId, info]: [string, any]) => {
        console.log(`🔍 节点 ${nodeId}:`, {
          has_subdivision: info?.has_subdivision,
          subdivision_count: info?.subdivision_count,
          is_expandable: info?.is_expandable
        });
      });
      
      setSubdivisionInfo(nodeSubdivisions);
      
      const hasSubdivisionCount = Object.values(nodeSubdivisions).filter((info: any) => info?.has_subdivision).length;
      console.log('✅ useSubWorkflowExpansion: subdivision信息加载成功，有subdivision的节点数:', hasSubdivisionCount);
      
    } catch (error) {
      console.error('❌ useSubWorkflowExpansion: 加载细分信息失败:', error);
      console.error('❌ useSubWorkflowExpansion: 错误详情:', {
        instanceId,
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : 'No stack'
      });
      message.error(`加载细分信息失败: ${error instanceof Error ? error.message : '未知错误'}`);
    } finally {
      setIsLoadingSubdivisionInfo(false);
    }
  }, []);

  // 加载节点的详细细分数据
  const loadNodeSubdivisionDetail = useCallback(async (nodeInstanceId: string): Promise<SubWorkflowDetail[]> => {
    // 检查缓存
    if (loadedDataCache.current[nodeInstanceId]) {
      return loadedDataCache.current[nodeInstanceId];
    }
    
    try {
      // 使用动态导入来避免循环依赖，并使用已配置的api实例
      const { executionAPI } = await import('../services/api');
      
      console.log('🔍 useSubWorkflowExpansion: 加载节点细分详情:', nodeInstanceId);
      
      const axiosResponse = await executionAPI.getNodeSubdivisionDetail(nodeInstanceId);
      const response = axiosResponse.data; // 从axios响应中提取实际数据
      
      console.log('🔍 loadNodeSubdivisionDetail: API响应数据:', response);
      console.log('🔍 loadNodeSubdivisionDetail: API响应键:', Object.keys(response || {}));
      
      // 检查响应格式并适配不同的结构
      let subdivisions = [];
      
      if (response && response.success && response.data) {
        // 标准格式: {success: true, data: {subdivisions: [...]}}
        console.log('🔍 使用标准响应格式获取细分详情');
        subdivisions = response.data.subdivisions || [];
      } else if (response && response.subdivisions) {
        // 直接数据格式: {subdivisions: [...]}
        console.log('🔍 使用直接数据格式获取细分详情');
        subdivisions = response.subdivisions || [];
      } else {
        console.error('❌ loadNodeSubdivisionDetail: API响应格式错误:', response);
        throw new Error(response?.message || '获取节点细分详情失败');
      }
      
      // 缓存数据
      loadedDataCache.current[nodeInstanceId] = subdivisions;
      console.log(`✅ 节点 ${nodeInstanceId} 细分详情加载成功:`, subdivisions.length, '个子工作流');
      return subdivisions;
      
    } catch (error) {
      console.error('加载节点细分详情失败:', error);
      throw error;
    }
  }, []);

  // 展开节点
  const expandNode = useCallback(async (nodeInstanceId: string) => {
    console.log(`🔄 [useSubWorkflowExpansion] 尝试展开节点:`, nodeInstanceId);
    console.log(`🔍 [useSubWorkflowExpansion] 当前subdivisionInfo状态:`, subdivisionInfo);
    console.log(`🔍 [useSubWorkflowExpansion] 当前workflowInstanceId:`, workflowInstanceId);
    
    // 检查节点是否有细分信息
    const nodeInfo = subdivisionInfo[nodeInstanceId];
    console.log(`🔍 [useSubWorkflowExpansion] 节点 ${nodeInstanceId} 的subdivision信息:`, nodeInfo);
    
    if (!nodeInfo?.has_subdivision) {
      console.warn(`⚠️ [useSubWorkflowExpansion] 节点 ${nodeInstanceId} 没有细分信息，无法展开`);
      console.warn(`   - 所有subdivisionInfo键:`, Object.keys(subdivisionInfo));
      console.warn(`   - 节点信息:`, nodeInfo);
      message.warning('该节点没有可展开的子工作流');
      return;
    }
    
    if (!nodeInfo.is_expandable) {
      console.warn(`⚠️ [useSubWorkflowExpansion] 节点 ${nodeInstanceId} 不可展开`);
      console.warn(`   - 节点细分信息:`, nodeInfo);
      message.warning('该节点的子工作流暂时不可展开');
      return;
    }
    
    // 设置加载状态
    setExpandedNodes(prev => ({
      ...prev,
      [nodeInstanceId]: {
        ...prev[nodeInstanceId],
        isLoading: true,
        error: undefined
      }
    }));

    try {
      console.log(`🔄 [useSubWorkflowExpansion] 开始加载节点 ${nodeInstanceId} 的细分详情`);
      
      // 加载节点的细分详情
      const subWorkflowData = await loadNodeSubdivisionDetail(nodeInstanceId);
      
      console.log(`✅ [useSubWorkflowExpansion] 节点 ${nodeInstanceId} 细分详情加载成功:`, subWorkflowData.length, '个子工作流');
      
      // 更新展开状态
      setExpandedNodes(prev => ({
        ...prev,
        [nodeInstanceId]: {
          isExpanded: true,
          isLoading: false,
          subWorkflowData,
          error: undefined
        }
      }));

      // 通知外部组件
      onExpansionChange?.(nodeInstanceId, true);
      
      message.success(`子工作流展开成功 (${subWorkflowData.length} 个)`);
    } catch (error) {
      console.error(`❌ [useSubWorkflowExpansion] 展开节点 ${nodeInstanceId} 失败:`, error);
      
      // 设置错误状态
      setExpandedNodes(prev => ({
        ...prev,
        [nodeInstanceId]: {
          isExpanded: false,
          isLoading: false,
          error: error instanceof Error ? error.message : '加载失败'
        }
      }));
      
      message.error(`展开子工作流失败: ${error instanceof Error ? error.message : '未知错误'}`);
    }
  }, [subdivisionInfo, loadNodeSubdivisionDetail, onExpansionChange]);

  // 收起节点
  const collapseNode = useCallback((nodeInstanceId: string) => {
    setExpandedNodes(prev => ({
      ...prev,
      [nodeInstanceId]: {
        isExpanded: false,
        isLoading: false,
        subWorkflowData: prev[nodeInstanceId]?.subWorkflowData, // 保留数据，避免重新加载
        error: undefined
      }
    }));

    // 通知外部组件
    onExpansionChange?.(nodeInstanceId, false);
  }, [onExpansionChange]);

  // 切换展开状态
  const toggleNodeExpansion = useCallback((nodeInstanceId: string) => {
    const currentState = expandedNodes[nodeInstanceId];
    
    if (currentState?.isExpanded) {
      collapseNode(nodeInstanceId);
    } else {
      expandNode(nodeInstanceId);
    }
  }, [expandedNodes, expandNode, collapseNode]);

  // 获取节点的展开状态
  const getNodeExpansionState = useCallback((nodeInstanceId: string): ExpandedNodeState => {
    return expandedNodes[nodeInstanceId] || {
      isExpanded: false,
      isLoading: false,
      subWorkflowData: undefined,
      error: undefined
    };
  }, [expandedNodes]);

  // 获取节点的细分信息
  const getNodeSubdivisionInfo = useCallback((nodeInstanceId: string): SubWorkflowInfo | undefined => {
    return subdivisionInfo[nodeInstanceId];
  }, [subdivisionInfo]);

  // 检查节点是否有细分
  const hasSubdivision = useCallback((nodeInstanceId: string): boolean => {
    const info = subdivisionInfo[nodeInstanceId];
    return info?.has_subdivision || false;
  }, [subdivisionInfo]);

  // 检查节点是否可展开
  const isExpandable = useCallback((nodeInstanceId: string): boolean => {
    const info = subdivisionInfo[nodeInstanceId];
    return info?.is_expandable || false;
  }, [subdivisionInfo]);

  // 清除缓存
  const clearCache = useCallback(() => {
    loadedDataCache.current = {};
  }, []);

  // 重新加载细分信息
  const refreshSubdivisionInfo = useCallback(() => {
    if (workflowInstanceId) {
      loadSubdivisionInfo(workflowInstanceId);
    }
  }, [workflowInstanceId, loadSubdivisionInfo]);

  // 获取所有展开的节点
  const getExpandedNodeIds = useCallback((): string[] => {
    return Object.keys(expandedNodes).filter(nodeId => 
      expandedNodes[nodeId]?.isExpanded
    );
  }, [expandedNodes]);

  // 收起所有节点
  const collapseAllNodes = useCallback(() => {
    const expandedNodeIds = getExpandedNodeIds();
    expandedNodeIds.forEach(nodeId => {
      collapseNode(nodeId);
    });
  }, [getExpandedNodeIds, collapseNode]);

  return {
    // 状态
    expandedNodes,
    subdivisionInfo,
    isLoadingSubdivisionInfo,
    
    // 方法
    loadSubdivisionInfo,
    expandNode,
    collapseNode,
    toggleNodeExpansion,
    
    // 查询方法
    getNodeExpansionState,
    getNodeSubdivisionInfo,
    hasSubdivision,
    isExpandable,
    getExpandedNodeIds,
    
    // 工具方法
    clearCache,
    refreshSubdivisionInfo,
    collapseAllNodes
  };
};