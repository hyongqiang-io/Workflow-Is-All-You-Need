import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authAPI } from '../services/api';

interface User {
  user_id: string;
  username: string;
  email: string;
  full_name?: string;
  phone?: string;
  description?: string;
  role?: string;
  created_at: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  
  // Actions
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  getCurrentUser: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
  setUser: (user: User) => void;
  setToken: (token: string) => void;
  validateUserConsistency: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      loading: false,

      login: async (username: string, password: string) => {
        set({ loading: true });
        try {
          const response: any = await authAPI.login({ username_or_email: username, password });
          
          if (response && response.data?.token) {
            const tokenData = response.data.token;
            const access_token = tokenData.access_token;
            
            // 立即设置token以便后续API调用
            localStorage.setItem('token', access_token);
            
            let user;
            
            try {
              // 立即获取完整用户信息
              const userResponse: any = await authAPI.getCurrentUser();
              if (userResponse && userResponse.data?.user) {
                const userData = userResponse.data.user;
                user = {
                  user_id: userData.user_id,
                  username: userData.username,
                  email: userData.email || '',
                  full_name: userData.full_name || '',
                  role: userData.role || 'user',
                  created_at: userData.created_at || new Date().toISOString()
                };
              } else {
                throw new Error('无法获取完整用户信息');
              }
            } catch (userError) {
              console.warn('获取用户信息失败，使用Token中的基础信息:', userError);
              // fallback: 使用Token中的基础信息
              user = {
                user_id: tokenData.user_id,
                username: tokenData.username,
                email: tokenData.email || '',
                full_name: '',
                role: 'user',
                created_at: new Date().toISOString()
              };
            }
            
            // 验证用户ID一致性
            if (user.user_id !== tokenData.user_id) {
              throw new Error('用户身份验证失败：ID不一致');
            }
            
            set({
              user,
              token: access_token,
              isAuthenticated: true,
              loading: false,
            });
            
            console.log('✅ 登录成功，用户信息已同步:', user);
          } else {
            throw new Error(response.message || '登录响应格式错误');
          }
        } catch (error) {
          console.error('❌ 登录失败:', error);
          set({ loading: false });
          // 清理可能的残留状态
          localStorage.removeItem('token');
          throw error;
        }
      },

      register: async (username: string, email: string, password: string) => {
        set({ loading: true });
        try {
          const response: any = await authAPI.register({ username, email, password });
          
          if (response) {
            set({ loading: false });
          } else {
            throw new Error(response.message || '注册失败');
          }
        } catch (error) {
          set({ loading: false });
          throw error;
        }
      },

      logout: () => {
        localStorage.removeItem('token');
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        });
        console.log('🚪 用户已退出登录');
      },

      getCurrentUser: async () => {
        set({ loading: true });
        try {
          const response: any = await authAPI.getCurrentUser();
          
          if (response && response.data?.user) {
            const userData = response.data.user;
            const user = {
              user_id: userData.user_id,
              username: userData.username,
              email: userData.email || '',
              full_name: userData.full_name || '',
              role: userData.role || 'user',
              created_at: userData.created_at || new Date().toISOString()
            };
            
            set({
              user,
              isAuthenticated: true,
              loading: false,
            });
          } else {
            throw new Error(response.message || '获取用户信息响应格式错误');
          }
        } catch (error) {
          set({ loading: false, isAuthenticated: false });
          throw error;
        }
      },

      // 用户状态一致性验证
      validateUserConsistency: async () => {
        const localUser = get().user;
        const token = localStorage.getItem('token');
        
        if (!localUser || !token) {
          console.warn('⚠️  缺少用户信息或Token');
          return false;
        }
        
        try {
          // 验证Token格式和过期时间
          const payload = JSON.parse(atob(token.split('.')[1]));
          const now = Math.floor(Date.now() / 1000);
          
          if (payload.exp <= now) {
            console.warn('⚠️  Token已过期');
            get().logout();
            return false;
          }
          
          if (payload.sub !== localUser.user_id) {
            console.warn('⚠️  用户ID不一致，清理状态');
            get().logout();
            return false;
          }
          
          // 验证后端用户状态
          const response: any = await authAPI.getCurrentUser();
          if (response && response.data?.user) {
            const serverUser = response.data.user;
            if (serverUser.user_id !== localUser.user_id) {
              console.warn('⚠️  服务器用户信息不一致，更新本地状态');
              set({ 
                user: {
                  user_id: serverUser.user_id,
                  username: serverUser.username,
                  email: serverUser.email || '',
                  full_name: serverUser.full_name || '',
                  role: serverUser.role || 'user',
                  created_at: serverUser.created_at || new Date().toISOString()
                }
              });
            }
            
            console.log('✅ 用户状态一致性验证通过');
            return true;
          } else {
            throw new Error('服务器返回异常');
          }
          
        } catch (error) {
          console.error('❌ 用户状态验证失败:', error);
          get().logout();
          return false;
        }
      },

      // 自动登录检查（增强版）
      checkAuth: async () => {
        const token = localStorage.getItem('token');
        if (token) {
          try {
            // 先验证Token格式
            const payload = JSON.parse(atob(token.split('.')[1]));
            const now = Math.floor(Date.now() / 1000);
            
            if (payload.exp <= now) {
              console.warn('⚠️  Token已过期，清理状态');
              localStorage.removeItem('token');
              return false;
            }
            
            // 获取用户信息
            await get().getCurrentUser();
            
            // 验证一致性
            const isConsistent = await get().validateUserConsistency();
            if (isConsistent) {
              console.log('✅ 自动登录成功');
              return true;
            } else {
              console.warn('⚠️  用户状态不一致');
              return false;
            }
          } catch (error) {
            console.error('❌ 自动登录失败:', error);
            localStorage.removeItem('token');
            return false;
          }
        }
        return false;
      },

      setUser: (user: User) => {
        set({ user });
      },

      setToken: (token: string) => {
        set({ token, isAuthenticated: true });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);