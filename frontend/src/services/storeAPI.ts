/**
 * 工作流商店API服务
 */

import api from './api';
import type {
  WorkflowStoreResponse,
  WorkflowStoreDetail,
  WorkflowStoreQuery,
  WorkflowStoreList,
  WorkflowStoreCreate,
  WorkflowStoreUpdate,
  WorkflowStoreRating,
  WorkflowStoreRatingCreate,
  WorkflowStoreImportRequest,
  WorkflowStoreImportResult,
  WorkflowStoreStats,
  StoreCategory
} from '../types/store';

export const storeAPI = {
  /**
   * 搜索商店工作流
   */
  async searchWorkflows(params: WorkflowStoreQuery): Promise<WorkflowStoreList> {
    const queryParams = new URLSearchParams();

    if (params.keyword) queryParams.append('keyword', params.keyword);
    if (params.category) queryParams.append('category', params.category);
    if (params.tags && params.tags.length > 0) {
      queryParams.append('tags', params.tags.join(','));
    }
    if (params.author_id) queryParams.append('author_id', params.author_id.toString());
    if (params.is_featured !== undefined) queryParams.append('is_featured', params.is_featured.toString());
    if (params.is_free !== undefined) queryParams.append('is_free', params.is_free.toString());
    if (params.min_rating !== undefined) queryParams.append('min_rating', params.min_rating.toString());
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    if (params.page) queryParams.append('page', params.page.toString());
    if (params.page_size) queryParams.append('page_size', params.page_size.toString());

    try {
      console.log('🔍 [API] 准备发起请求:', `/store/workflows?${queryParams.toString()}`);
      const response = await api.get(`/store/workflows?${queryParams.toString()}`);
      console.log('🔍 [API] 收到axios响应对象:', response);
      console.log('🔍 [API] response.status:', response.status);
      console.log('🔍 [API] response.statusText:', response.statusText);
      console.log('🔍 [API] response.data:', response.data);
      console.log('🔍 [API] response.data类型:', typeof response.data);

      if (response.data) {
        console.log('🔍 [API] response.data键:', Object.keys(response.data));
      }

      // axios响应对象，数据在.data属性中
      return response.data as WorkflowStoreList;
    } catch (error) {
      console.error('❌ [API] searchWorkflows调用失败:', error);
      throw error;
    }
  },

  /**
   * 获取工作流详情
   */
  async getWorkflowDetail(storeId: string): Promise<WorkflowStoreDetail> {
    const response = await api.get(`/store/workflows/${storeId}`);
    return response.data;
  },

  /**
   * 获取推荐工作流
   */
  async getFeaturedWorkflows(limit: number = 10): Promise<WorkflowStoreResponse[]> {
    const response = await api.get(`/store/featured?limit=${limit}`);
    return response.data;
  },

  /**
   * 获取热门工作流
   */
  async getPopularWorkflows(limit: number = 10): Promise<WorkflowStoreResponse[]> {
    const response = await api.get(`/store/popular?limit=${limit}`);
    return response.data;
  },

  /**
   * 获取我发布的工作流
   */
  async getMyWorkflows(): Promise<WorkflowStoreResponse[]> {
    const response = await api.get('/store/my-workflows');
    return response.data;
  },

  /**
   * 发布工作流到商店
   */
  async publishWorkflow(workflowBaseId: string, storeData: WorkflowStoreCreate): Promise<{ store_id: string }> {
    const response = await api.post('/store/publish', storeData);
    return response.data.data;
  },

  /**
   * 更新商店工作流
   */
  async updateWorkflow(storeId: string, updateData: WorkflowStoreUpdate): Promise<void> {
    await api.put(`/store/workflows/${storeId}`, updateData);
  },

  /**
   * 删除商店工作流
   */
  async deleteWorkflow(storeId: string): Promise<void> {
    await api.delete(`/store/workflows/${storeId}`);
  },

  /**
   * 导入工作流
   */
  async importWorkflow(importRequest: WorkflowStoreImportRequest): Promise<WorkflowStoreImportResult> {
    const response = await api.post('/store/import', importRequest);
    // 现在API返回BaseResponse格式，实际数据在data字段中
    return response.data.data as WorkflowStoreImportResult;
  },

  /**
   * 创建评分
   */
  async createRating(storeId: string, ratingData: WorkflowStoreRatingCreate): Promise<{ rating_id: string }> {
    const response = await api.post(`/store/workflows/${storeId}/ratings`, ratingData);
    return response.data.data;
  },

  /**
   * 获取工作流评分
   */
  async getWorkflowRatings(storeId: string, limit: number = 50, offset: number = 0): Promise<WorkflowStoreRating[]> {
    const response = await api.get(`/store/workflows/${storeId}/ratings?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  /**
   * 获取商店统计信息
   */
  async getStoreStats(): Promise<WorkflowStoreStats> {
    const response = await api.get('/store/stats');
    return response.data;
  },

  /**
   * 增加工作流浏览次数
   */
  async incrementWorkflowView(storeId: string): Promise<boolean> {
    try {
      const response = await api.put(`/store/workflows/${storeId}/view`);
      return response.data?.success || false;
    } catch (error) {
      console.error('增加浏览次数失败:', error);
      return false;
    }
  }
};