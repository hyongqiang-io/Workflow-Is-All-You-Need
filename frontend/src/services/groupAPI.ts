import api from './api';
import { GroupCreate, GroupUpdate, GroupQuery, GroupList, Group, GroupMember } from '../types/group';

// 群组相关API
export const groupAPI = {
  // 获取群组列表
  getGroups: async (params?: GroupQuery) => {
    console.log('🏢 [GROUP-API] 获取群组列表');
    console.log('   - 查询参数:', params);

    try {
      const response = await api.get('/groups', { params });
      console.log('✅ [GROUP-API] 获取群组列表成功:', response);

      // 包装成统一的响应格式
      return {
        success: true,
        message: '获取群组列表成功',
        data: {
          groups: Array.isArray(response.data) ? response.data : (response.data?.groups || []),
          total: response.data?.total || (Array.isArray(response.data) ? response.data.length : 0)
        }
      };
    } catch (error: any) {
      console.error('❌ [GROUP-API] 获取群组列表失败:', error);
      throw error;
    }
  },

  // 获取群组详情
  getGroup: async (groupId: string) => {
    console.log('🏢 [GROUP-API] 获取群组详情:', groupId);

    try {
      const response = await api.get(`/groups/${groupId}`);
      console.log('✅ [GROUP-API] 获取群组详情成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 获取群组详情失败:', error);
      throw error;
    }
  },

  // 创建群组
  createGroup: async (groupData: GroupCreate) => {
    console.log('🏢 [GROUP-API] 开始创建群组');
    console.log('   - 群组数据:', JSON.stringify(groupData, null, 2));

    try {
      console.log('   - 发送POST请求到 /groups');
      const response = await api.post('/groups', groupData);
      console.log('✅ [GROUP-API] 创建群组API调用成功');
      console.log('   - 响应状态:', response.status);
      console.log('   - 响应数据:', JSON.stringify(response.data, null, 2));

      // 包装成统一的响应格式
      return {
        success: true,
        message: '群组创建成功',
        data: response.data
      };
    } catch (error: any) {
      console.error('❌ [GROUP-API] 创建群组失败');
      console.error('   - 错误类型:', error.constructor.name);
      console.error('   - 错误消息:', error.message);
      if (error.response) {
        console.error('   - 响应状态:', error.response.status);
        console.error('   - 响应头:', error.response.headers);
        console.error('   - 响应数据:', JSON.stringify(error.response.data, null, 2));
      } else if (error.request) {
        console.error('   - 请求配置:', error.config);
        console.error('   - 请求详情:', error.request);
      }
      throw error;
    }
  },

  // 更新群组
  updateGroup: async (groupId: string, groupData: GroupUpdate) => {
    console.log('🏢 [GROUP-API] 更新群组:', groupId, groupData);

    try {
      const response = await api.put(`/groups/${groupId}`, groupData);
      console.log('✅ [GROUP-API] 更新群组成功:', response);

      // 包装成统一的响应格式
      return {
        success: true,
        message: '群组更新成功',
        data: response.data
      };
    } catch (error: any) {
      console.error('❌ [GROUP-API] 更新群组失败:', error);
      throw error;
    }
  },

  // 删除群组
  deleteGroup: async (groupId: string) => {
    console.log('🏢 [GROUP-API] 删除群组:', groupId);

    try {
      const response = await api.delete(`/groups/${groupId}`);
      console.log('✅ [GROUP-API] 删除群组成功:', response);

      // 包装成统一的响应格式
      return {
        success: true,
        message: '群组删除成功',
        data: response.data
      };
    } catch (error: any) {
      console.error('❌ [GROUP-API] 删除群组失败:', error);
      throw error;
    }
  },

  // 搜索群组
  searchGroups: async (keyword: string, params?: Omit<GroupQuery, 'keyword'>) => {
    console.log('🏢 [GROUP-API] 搜索群组:', keyword, params);

    try {
      const searchParams = { keyword, ...params };
      const response = await api.get('/groups/search', { params: searchParams });
      console.log('✅ [GROUP-API] 搜索群组成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 搜索群组失败:', error);
      throw error;
    }
  },

  // 加入群组
  joinGroup: async (groupId: string) => {
    console.log('🏢 [GROUP-API] 加入群组:', groupId);

    try {
      const response = await api.post(`/groups/${groupId}/join`);
      console.log('✅ [GROUP-API] 加入群组成功:', response);

      return {
        success: true,
        message: '成功加入群组',
        data: response.data
      };
    } catch (error: any) {
      console.error('❌ [GROUP-API] 加入群组失败:', error);
      throw error;
    }
  },

  // 离开群组
  leaveGroup: async (groupId: string) => {
    console.log('🏢 [GROUP-API] 离开群组:', groupId);

    try {
      const response = await api.delete(`/groups/${groupId}/leave`);
      console.log('✅ [GROUP-API] 离开群组成功:', response);

      return {
        success: true,
        message: '成功离开群组',
        data: response.data
      };
    } catch (error: any) {
      console.error('❌ [GROUP-API] 离开群组失败:', error);
      throw error;
    }
  },

  // 获取群组成员列表
  getGroupMembers: async (groupId: string, params?: { page?: number; page_size?: number }) => {
    console.log('🏢 [GROUP-API] 获取群组成员列表:', groupId, params);

    try {
      const response = await api.get(`/groups/${groupId}/members`, { params });
      console.log('✅ [GROUP-API] 获取群组成员列表成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 获取群组成员列表失败:', error);
      throw error;
    }
  },

  // 邀请成员加入群组
  inviteMember: async (groupId: string, data: { user_ids: string[] }) => {
    console.log('🏢 [GROUP-API] 邀请成员加入群组:', groupId, data);

    try {
      const response = await api.post(`/groups/${groupId}/invite`, data);
      console.log('✅ [GROUP-API] 邀请成员成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 邀请成员失败:', error);
      throw error;
    }
  },

  // 移除群组成员
  removeMember: async (groupId: string, userId: string) => {
    console.log('🏢 [GROUP-API] 移除群组成员:', groupId, userId);

    try {
      const response = await api.delete(`/groups/${groupId}/members/${userId}`);
      console.log('✅ [GROUP-API] 移除成员成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 移除成员失败:', error);
      throw error;
    }
  },

  // 获取我的群组列表
  getMyGroups: async (params?: { is_creator?: boolean; page?: number; page_size?: number }) => {
    console.log('🏢 [GROUP-API] 获取我的群组列表:', params);

    try {
      const response = await api.get('/groups/my', { params });
      console.log('✅ [GROUP-API] 获取我的群组列表成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 获取我的群组列表失败:', error);
      throw error;
    }
  },

  // 获取群组内的processor列表
  getGroupProcessors: async (groupId: string) => {
    console.log('🏢 [GROUP-API] 获取群组processor列表:', groupId);

    try {
      const response = await api.get(`/groups/${groupId}/processors`);
      console.log('✅ [GROUP-API] 获取群组processor列表成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 获取群组processor列表失败:', error);
      throw error;
    }
  },

  // 获取群组统计信息
  getGroupStats: async () => {
    console.log('🏢 [GROUP-API] 获取群组统计信息');

    try {
      const response = await api.get('/groups/stats');
      console.log('✅ [GROUP-API] 获取群组统计信息成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 获取群组统计信息失败:', error);
      throw error;
    }
  },

  // 转移群组所有权
  transferOwnership: async (groupId: string, data: { new_owner_id: string }) => {
    console.log('🏢 [GROUP-API] 转移群组所有权:', groupId, data);

    try {
      const response = await api.post(`/groups/${groupId}/transfer`, data);
      console.log('✅ [GROUP-API] 转移群组所有权成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [GROUP-API] 转移群组所有权失败:', error);
      throw error;
    }
  }
};

// 扩展processor API以支持群组功能
export const processorGroupAPI = {
  // 获取按群组分类的processor列表
  getProcessorsGrouped: async () => {
    console.log('🏢 [PROCESSOR-GROUP-API] 获取分组processor列表');

    try {
      const response = await api.get('/processors/grouped');
      console.log('✅ [PROCESSOR-GROUP-API] 获取分组processor列表成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [PROCESSOR-GROUP-API] 获取分组processor列表失败:', error);
      throw error;
    }
  },

  // 创建带群组的processor
  createProcessor: async (data: {
    name: string;
    type: 'human' | 'agent' | 'mix';
    user_id?: string;
    agent_id?: string;
    group_id?: string;
  }) => {
    console.log('🏢 [PROCESSOR-GROUP-API] 创建processor:', data);

    try {
      const response = await api.post('/processors', data);
      console.log('✅ [PROCESSOR-GROUP-API] 创建processor成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [PROCESSOR-GROUP-API] 创建processor失败:', error);
      throw error;
    }
  },

  // 更新processor的群组
  updateProcessorGroup: async (processorId: string, groupId: string | null) => {
    console.log('🏢 [PROCESSOR-GROUP-API] 更新processor群组:', processorId, groupId);

    try {
      const response = await api.put(`/processors/${processorId}`, { group_id: groupId });
      console.log('✅ [PROCESSOR-GROUP-API] 更新processor群组成功:', response);
      return response;
    } catch (error: any) {
      console.error('❌ [PROCESSOR-GROUP-API] 更新processor群组失败:', error);
      throw error;
    }
  }
};

export default groupAPI;