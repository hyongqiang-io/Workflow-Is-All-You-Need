/**
 * 群组相关类型定义
 */

// 基础群组接口
export interface Group {
  group_id: string;
  group_name: string;
  description?: string;
  avatar_url?: string;
  is_public: boolean;
  creator_id: string;
  creator_name?: string;
  member_count: number;
  is_member: boolean;
  is_creator: boolean;
  created_at?: string;
  updated_at?: string;
}

// 群组创建接口
export interface GroupCreate {
  group_name: string;
  description?: string;
  avatar_url?: string;
  is_public: boolean;
}

// 群组更新接口
export interface GroupUpdate {
  group_name?: string;
  description?: string;
  avatar_url?: string;
  is_public?: boolean;
}

// 群组成员接口
export interface GroupMember {
  id: string;
  group_id: string;
  user_id: string;
  username: string;
  email: string;
  joined_at: string;
  status: string;
}

// 群组列表接口
export interface GroupList {
  groups: Group[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 群组查询参数接口
export interface GroupQuery {
  keyword?: string;
  is_public?: boolean;
  page?: number;
  page_size?: number;
}

// 群组统计信息接口
export interface GroupStats {
  total_groups: number;
  public_groups: number;
  my_groups: number;
  total_members: number;
}

// Processor的群组信息
export interface ProcessorGroupInfo {
  group_id?: string;
  group_name?: string;
  is_member: boolean;
}

// 按群组分类的Processor
export interface GroupedProcessors {
  [groupName: string]: any[];
}