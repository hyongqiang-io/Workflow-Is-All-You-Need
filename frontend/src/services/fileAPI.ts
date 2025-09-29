/**
 * 文件管理API服务
 * File Management API Service
 */

import axios from 'axios';

// 创建专用的API实例
const fileAPI = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || (process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api'),
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 添加请求拦截器
fileAPI.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 类型定义
export interface FileInfo {
  file_id: string;
  filename: string;
  original_filename: string;
  file_path: string;
  file_size: number;
  content_type: string;
  file_hash: string;
  uploaded_by: string;
  uploaded_by_name?: string;
  created_at: string;
  updated_at: string;
  download_url?: string;
}

export interface UserFileResponse {
  files: FileInfo[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FileUploadResponse {
  file_id: string;
  filename: string;
  file_size: number;
  content_type: string;
  upload_success: boolean;
  message: string;
}

export interface FileSearchParams {
  page?: number;
  page_size?: number;
  keyword?: string;
  content_type?: string;
  sort_by?: 'created_at' | 'filename' | 'file_size';
  sort_order?: 'asc' | 'desc';
}

export interface FileStatistics {
  total_files: number;
  total_size: number;
  total_size_mb: number;
  file_type_stats: Record<string, number>;
}

/**
 * 文件管理API类 - Linus式简洁设计
 */
export class FileAPI {
  
  /**
   * 获取我的文件列表
   */
  static async getMyFiles(params: FileSearchParams = {}): Promise<UserFileResponse> {
    try {
      const {
        page = 1,
        page_size = 20,
        keyword,
        content_type,
        sort_by = 'created_at',
        sort_order = 'desc'
      } = params;

      const queryParams = new URLSearchParams({
        page: page.toString(),
        page_size: page_size.toString(),
        sort_by,
        sort_order
      });

      if (keyword) {
        queryParams.append('keyword', keyword);
      }
      if (content_type) {
        queryParams.append('content_type', content_type);
      }

      const response = await fileAPI.get(`/files/user/my-files?${queryParams}`);
      // Linus式修复: 后端返回格式是 {success, message, data}，需要返回 data 字段
      return response.data.data;
    } catch (error) {
      console.error('获取我的文件失败:', error);
      throw error;
    }
  }

  /**
   * 上传单个文件 - File对象版本
   */
  static async uploadFile(
    file: File,
    options: {
      node_id?: string;
      task_instance_id?: string;
      attachment_type?: 'input' | 'output' | 'reference';
    } = {}
  ): Promise<FileUploadResponse> {
    try {
      const formData = new FormData();
      formData.append('file', file);

      if (options.node_id) {
        formData.append('node_id', options.node_id);
      }
      if (options.task_instance_id) {
        formData.append('task_instance_id', options.task_instance_id);
      }
      if (options.attachment_type) {
        formData.append('attachment_type', options.attachment_type);
      }

      const response = await fileAPI.post('/files/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data.data;
    } catch (error) {
      console.error('文件上传失败:', error);
      throw error;
    }
  }

  /**
   * 下载文件
   */
  static async downloadFile(fileId: string): Promise<void> {
    try {
      const response = await fileAPI.get(`/files/${fileId}/download`, {
        responseType: 'blob',
      });

      // 创建下载链接
      const blob = response.data as Blob;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // 尝试从响应头获取文件名
      const contentDisposition = response.headers?.['content-disposition'];
      let filename = `file_${fileId}`;
      
      if (contentDisposition) {
        const matches = contentDisposition.match(/filename="(.+)"/);
        if (matches) {
          filename = matches[1];
        }
      }
      
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('文件下载失败:', error);
      throw error;
    }
  }

  /**
   * 获取文件信息
   */
  static async getFileInfo(fileId: string): Promise<FileInfo> {
    try {
      const response = await fileAPI.get(`/files/${fileId}`);
      return response.data.data;
    } catch (error) {
      console.error('获取文件信息失败:', error);
      throw error;
    }
  }

  /**
   * 删除文件
   */
  static async deleteFile(fileId: string, hardDelete: boolean = false): Promise<void> {
    try {
      const params = hardDelete ? '?hard_delete=true' : '';
      const response = await fileAPI.delete(`/files/${fileId}${params}`);
      
      if (response.data && response.data.success === false) {
        throw new Error(response.data.message || '删除文件失败');
      }
    } catch (error) {
      console.error('删除文件失败:', error);
      throw error;
    }
  }

  /**
   * 获取文件统计信息
   */
  static async getFileStatistics(): Promise<FileStatistics> {
    try {
      const response = await fileAPI.get('/files/statistics');
      return response.data.data;
    } catch (error) {
      console.error('获取文件统计失败:', error);
      throw error;
    }
  }

  /**
   * 获取存储信息
   */
  static async getStorageInfo(): Promise<any> {
    try {
      const response = await fileAPI.get('/files/storage/info');
      return response.data.data;
    } catch (error) {
      console.error('获取存储信息失败:', error);
      throw error;
    }
  }

  /**
   * 格式化文件大小
   */
  static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * 获取文件类型图标
   */
  static getFileTypeIcon(contentType: string): string {
    const typeMap: Record<string, string> = {
      'application/pdf': '📄',
      'application/msword': '📝',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📝',
      'application/vnd.ms-excel': '📊',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '📊',
      'application/vnd.ms-powerpoint': '📽️',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': '📽️',
      'text/plain': '📄',
      'text/csv': '📊',
      'application/json': '📋',
      'image/jpeg': '🖼️',
      'image/png': '🖼️',
      'image/gif': '🖼️',
      'application/zip': '📦',
      'application/x-rar-compressed': '📦',
    };

    return typeMap[contentType] || '📎';
  }

  /**
   * 获取文件类型描述
   */
  static getFileTypeDescription(contentType: string): string {
    const typeMap: Record<string, string> = {
      'application/pdf': 'PDF文档',
      'application/msword': 'Word文档',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word文档',
      'application/vnd.ms-excel': 'Excel表格',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel表格',
      'application/vnd.ms-powerpoint': 'PowerPoint演示',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint演示',
      'text/plain': '文本文件',
      'text/csv': 'CSV文件',
      'application/json': 'JSON文件',
      'image/jpeg': 'JPEG图片',
      'image/png': 'PNG图片',
      'image/gif': 'GIF图片',
      'application/zip': 'ZIP压缩包',
      'application/x-rar-compressed': 'RAR压缩包',
    };

    return typeMap[contentType] || '未知文件类型';
  }

  /**
   * 获取节点关联的文件
   */
  static async getNodeFiles(nodeId: string): Promise<any> {
    try {
      const response = await fileAPI.get(`/files/associations/node/${nodeId}`);
      return response.data;
    } catch (error) {
      console.error('获取节点文件失败:', error);
      throw error;
    }
  }

  /**
   * 批量关联文件到节点
   */
  static async associateFilesToNode(nodeId: string, data: {
    file_ids: string[];
    attachment_type: 'input' | 'output' | 'reference' | 'template'; // 修复：使用小写
  }): Promise<any> {
    try {
      const response = await fileAPI.post(`/files/associations/node/${nodeId}`, data);
      return response.data;
    } catch (error) {
      console.error('关联文件到节点失败:', error);
      throw error;
    }
  }

  /**
   * 移除节点文件关联
   */
  static async removeNodeFileAssociation(nodeId: string, fileId: string): Promise<any> {
    try {
      const response = await fileAPI.delete(`/files/associations/node/${nodeId}/file/${fileId}`);
      return response.data;
    } catch (error) {
      console.error('移除节点文件关联失败:', error);
      throw error;
    }
  }

  /**
   * 上传文件 - FormData版本（用于NodeAttachmentManager）
   */
  static async uploadFileFormData(formData: FormData): Promise<any> {
    try {
      const response = await fileAPI.post('/files/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      console.error('文件上传失败:', error);
      throw error;
    }
  }

  /**
   * 获取用户文件 - 便捷方法
   */
  static async getUserFiles(page: number = 1, pageSize: number = 20): Promise<any> {
    try {
      const response = await this.getMyFiles({
        page,
        page_size: pageSize
      });
      return {
        success: true,
        data: response
      };
    } catch (error) {
      console.error('获取用户文件失败:', error);
      throw error;
    }
  }
}

export default FileAPI;