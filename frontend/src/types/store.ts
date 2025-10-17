/**
 * 工作流商店相关类型定义
 */

// 分类枚举
export type StoreCategory =
  | 'automation'
  | 'data_processing'
  | 'ai_ml'
  | 'business'
  | 'integration'
  | 'template'
  | 'other';

// 状态枚举
export type StoreStatus =
  | 'draft'
  | 'published'
  | 'archived'
  | 'rejected';

// 基础商店条目响应
export interface WorkflowStoreResponse {
  store_id: string;
  title: string;
  description?: string;
  category: StoreCategory;
  tags: string[];
  is_featured: boolean;
  is_free: boolean;
  price?: number;
  author_id: string;
  author_name: string;
  downloads: number;
  views: number;
  rating: number;
  rating_count: number;
  status: StoreStatus;
  published_at?: string;
  featured_at?: string;
  version: string;
  changelog?: string;
  created_at?: string;
  updated_at?: string;
  workflow_info?: {
    name?: string;
    description?: string;
    nodes_count: number;
    connections_count: number;
  };
}

// 商店条目详情
export interface WorkflowStoreDetail extends WorkflowStoreResponse {
  workflow_export_data: {
    name: string;
    description?: string;
    export_version: string;
    export_timestamp: string;
    nodes: any[];
    connections: any[];
    metadata?: Record<string, any>;
  };
}

// 商店条目创建
export interface WorkflowStoreCreate {
  title: string;
  description?: string;
  category: StoreCategory;
  tags: string[];
  is_featured: boolean;
  is_free: boolean;
  price?: number;
  workflow_base_id: string;
}

// 商店条目更新
export interface WorkflowStoreUpdate {
  title?: string;
  description?: string;
  category?: StoreCategory;
  tags?: string[];
  is_featured?: boolean;
  is_free?: boolean;
  price?: number;
  status?: StoreStatus;
  changelog?: string;
}

// 搜索查询参数
export interface WorkflowStoreQuery {
  keyword?: string;
  category?: StoreCategory;
  tags?: string[];
  author_id?: string;
  is_featured?: boolean;
  is_free?: boolean;
  min_rating?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

// 搜索结果列表
export interface WorkflowStoreList {
  items: WorkflowStoreResponse[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 评分
export interface WorkflowStoreRating {
  rating_id: string;
  store_id: string;
  user_id: string;
  user_name: string;
  rating: number;
  comment?: string;
  created_at: string;
}

// 评分创建
export interface WorkflowStoreRatingCreate {
  store_id: string;
  rating: number;
  comment?: string;
}

// 导入请求
export interface WorkflowStoreImportRequest {
  store_id: string;
  import_name?: string;
  import_description?: string;
}

// 导入结果
export interface WorkflowStoreImportResult {
  success: boolean;
  workflow_id?: string;
  workflow_base_id?: string;
  message: string;
  warnings?: string[];
  errors?: string[];
}

// 商店统计
export interface WorkflowStoreStats {
  total_workflows: number;
  total_downloads: number;
  featured_count: number;
  categories_stats: Record<string, number>;
  top_authors: Array<{
    author_id: string;
    author_name: string;
    workflow_count: number;
    total_downloads: number;
  }>;
  recent_uploads: WorkflowStoreResponse[];
}