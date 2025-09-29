import React, { useState, useEffect, useMemo } from 'react';
import { Upload, Button, List, Tag, message, Space, Tooltip, Typography, Divider } from 'antd';
import { 
  CloudUploadOutlined, 
  FileOutlined, 
  DeleteOutlined, 
  DownloadOutlined,
  PlusOutlined,
  FolderOpenOutlined
} from '@ant-design/icons';
import type { UploadProps, UploadFile } from 'antd';
import { FileAPI } from '../services/fileAPI';

const { Text } = Typography;
const { Dragger } = Upload;

interface NodeAttachmentManagerProps {
  nodeId?: string;
  workflowId?: string;
  readOnly?: boolean;
  value?: string[]; // 文件ID列表
  onChange?: (fileIds: string[]) => void;
}

interface FileInfo {
  file_id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  content_type: string;
  created_at: string;
  download_url?: string;
}

const NodeAttachmentManager: React.FC<NodeAttachmentManagerProps> = ({
  nodeId,
  workflowId,
  readOnly = false,
  value = [],
  onChange
}) => {
  const [attachedFiles, setAttachedFiles] = useState<FileInfo[]>([]);
  const [allUserFiles, setAllUserFiles] = useState<FileInfo[]>([]); // 重命名为allUserFiles
  const [showUserFiles, setShowUserFiles] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);

  // 使用useMemo计算过滤后的用户文件
  const userFiles = useMemo(() => {
    return allUserFiles.filter((file: FileInfo) => !value.includes(file.file_id));
  }, [allUserFiles, value]);

  // 加载已关联的文件
  const loadAttachedFiles = async () => {
    if (!nodeId) return;
    
    try {
      const response = await FileAPI.getNodeFiles(nodeId);
      if (response.success && response.data) {
        setAttachedFiles(response.data);
        // 更新value
        const fileIds = response.data.map((f: FileInfo) => f.file_id);
        if (onChange) {
          onChange(fileIds);
        }
      }
    } catch (error) {
      console.error('加载节点文件失败:', error);
    }
  };

  // 加载用户文件列表
  const loadUserFiles = async () => {
    if (!showUserFiles) return;
    
    setLoading(true);
    try {
      const response = await FileAPI.getUserFiles(1, 50); // 获取前50个文件
      if (response.success && response.data && response.data.files) {
        // 不在这里过滤，让useMemo处理过滤逻辑
        setAllUserFiles(response.data.files);
      }
    } catch (error) {
      console.error('加载用户文件失败:', error);
      message.error('加载用户文件失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAttachedFiles();
  }, [nodeId]);

  useEffect(() => {
    loadUserFiles();
  }, [showUserFiles]); // 移除value依赖，只在showUserFiles变化时加载

  // 文件上传配置
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    showUploadList: false,
    beforeUpload: () => false, // 阻止自动上传
    onChange: async (info) => {
      if (info.fileList.length === 0) return;
      
      setUploading(true);
      try {
        for (const fileObj of info.fileList) {
          if (fileObj.originFileObj) {
            const formData = new FormData();
            formData.append('file', fileObj.originFileObj);
            if (nodeId) formData.append('node_id', nodeId);
            if (workflowId) formData.append('workflow_instance_id', workflowId);
            formData.append('attachment_type', 'input'); // 修复：使用小写

            const response = await FileAPI.uploadFileFormData(formData);
            if (response.success) {
              message.success(`${fileObj.name} 上传成功`);
              // 重新加载文件列表
              await loadAttachedFiles();
            }
          }
        }
      } catch (error) {
        console.error('文件上传失败:', error);
        message.error('文件上传失败');
      } finally {
        setUploading(false);
      }
    },
  };

  // 从用户文件中添加
  const handleAddFromUserFiles = async (fileId: string) => {
    if (!nodeId) {
      message.error('请先保存节点');
      return;
    }

    try {
      await FileAPI.associateFilesToNode(nodeId, {
        file_ids: [fileId],
        attachment_type: 'input'
      });
      message.success('文件关联成功');
      await loadAttachedFiles();
    } catch (error) {
      console.error('关联文件失败:', error);
      message.error('关联文件失败');
    }
  };

  // 移除文件关联
  const handleRemoveFile = async (fileId: string) => {
    if (!nodeId) return;

    try {
      await FileAPI.removeNodeFileAssociation(nodeId, fileId);
      message.success('文件移除成功');
      await loadAttachedFiles();
    } catch (error) {
      console.error('移除文件失败:', error);
      message.error('移除文件失败');
    }
  };

  // 下载文件
  const handleDownloadFile = (fileId: string, filename: string) => {
    window.open(`/api/files/${fileId}/download`, '_blank');
  };

  // 格式化文件大小
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // 获取文件类型标签颜色
  const getFileTypeColor = (contentType: string) => {
    if (contentType.startsWith('image/')) return 'blue';
    if (contentType.startsWith('text/')) return 'green';
    if (contentType.includes('pdf')) return 'red';
    if (contentType.includes('word') || contentType.includes('doc')) return 'purple';
    if (contentType.includes('excel') || contentType.includes('sheet')) return 'orange';
    return 'default';
  };

  return (
    <div style={{ border: '1px solid #d9d9d9', borderRadius: '6px', padding: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <Text strong>节点附件 ({attachedFiles.length})</Text>
        {!readOnly && (
          <Space>
            <Button
              size="small"
              icon={<FolderOpenOutlined />}
              onClick={() => setShowUserFiles(!showUserFiles)}
            >
              {showUserFiles ? '隐藏' : '选择已有文件'}
            </Button>
          </Space>
        )}
      </div>

      {/* 当前关联的文件列表 */}
      {attachedFiles.length > 0 && (
        <>
          <List
            size="small"
            dataSource={attachedFiles}
            renderItem={(file) => (
              <List.Item
                actions={[
                  <Tooltip title="下载">
                    <Button
                      type="text"
                      size="small"
                      icon={<DownloadOutlined />}
                      onClick={() => handleDownloadFile(file.file_id, file.original_filename)}
                    />
                  </Tooltip>,
                  !readOnly && (
                    <Tooltip title="移除">
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleRemoveFile(file.file_id)}
                      />
                    </Tooltip>
                  )
                ].filter(Boolean)}
              >
                <List.Item.Meta
                  avatar={<FileOutlined />}
                  title={
                    <Space>
                      <Text style={{ fontSize: '14px' }}>{file.original_filename}</Text>
                      <Tag color={getFileTypeColor(file.content_type)}>
                        {file.content_type.split('/')[1]?.toUpperCase() || 'FILE'}
                      </Tag>
                    </Space>
                  }
                  description={
                    <Text type="secondary" style={{ fontSize: '12px' }}>
                      {formatFileSize(file.file_size)} • {new Date(file.created_at).toLocaleString()}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
          <Divider style={{ margin: '12px 0' }} />
        </>
      )}

      {/* 从已有文件中选择 */}
      {showUserFiles && !readOnly && (
        <>
          <div style={{ marginBottom: '12px' }}>
            <Text strong style={{ fontSize: '14px' }}>从我的文件中选择:</Text>
          </div>
          <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '12px' }}>
            <List
              size="small"
              loading={loading}
              dataSource={userFiles}
              locale={{ emptyText: '没有可用的文件' }}
              renderItem={(file) => (
                <List.Item
                  actions={[
                    <Button
                      type="link"
                      size="small"
                      icon={<PlusOutlined />}
                      onClick={() => handleAddFromUserFiles(file.file_id)}
                    >
                      添加
                    </Button>
                  ]}
                >
                  <List.Item.Meta
                    avatar={<FileOutlined />}
                    title={
                      <Space>
                        <Text style={{ fontSize: '13px' }}>{file.original_filename}</Text>
                        <Tag color={getFileTypeColor(file.content_type)}>
                          {file.content_type.split('/')[1]?.toUpperCase() || 'FILE'}
                        </Tag>
                      </Space>
                    }
                    description={
                      <Text type="secondary" style={{ fontSize: '11px' }}>
                        {formatFileSize(file.file_size)}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          </div>
          <Divider style={{ margin: '12px 0' }} />
        </>
      )}

      {/* 拖拽上传区域 */}
      {!readOnly && (
        <Dragger {...uploadProps} disabled={uploading} style={{ marginBottom: 0 }}>
          <p className="ant-upload-drag-icon">
            <CloudUploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint" style={{ fontSize: '12px' }}>
            {uploading ? '上传中...' : '支持单个或批量上传，上传后自动关联到此节点'}
          </p>
        </Dragger>
      )}
    </div>
  );
};

export default NodeAttachmentManager;