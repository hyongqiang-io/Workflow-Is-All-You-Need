/**
 * 文件列表组件 - 支持分页、搜索、排序
 * File List Component - Support Pagination, Search, Sorting
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Input,
  Select,
  Button,
  Space,
  Tooltip,
  Modal,
  message,
  Tag,
  Upload,
  Card,
  Row,
  Col,
  Statistic,
  Dropdown,
  MenuProps
} from 'antd';
import {
  SearchOutlined,
  DownloadOutlined,
  DeleteOutlined,
  UploadOutlined,
  ReloadOutlined,
  EyeOutlined,
  MoreOutlined,
  FileOutlined,
  FolderOutlined
} from '@ant-design/icons';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { FileAPI, FileInfo, FileSearchParams, FileStatistics } from '../../services/fileAPI';
import FilePreview from '../FilePreview';
import './FileList.css';

const { Search } = Input;
const { Option } = Select;

interface FileListProps {
  showUpload?: boolean;
  showStatistics?: boolean;
  pageSize?: number;
}

const FileList: React.FC<FileListProps> = ({
  showUpload = true,
  showStatistics = true,
  pageSize = 20
}) => {
  // 状态管理
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [statistics, setStatistics] = useState<FileStatistics | null>(null);
  
  // 搜索和过滤状态
  const [searchParams, setSearchParams] = useState<FileSearchParams>({
    page: 1,
    page_size: pageSize,
    sort_by: 'created_at',
    sort_order: 'desc'
  });
  
  // 模态框状态
  const [previewModal, setPreviewModal] = useState<{
    visible: boolean;
    file: FileInfo | null;
  }>({ visible: false, file: null });

  // 预览文件 - 使用新的预览组件
  const handlePreview = (file: FileInfo) => {
    setPreviewModal({ visible: true, file });
  };

  // 关闭预览
  const handleClosePreview = () => {
    setPreviewModal({ visible: false, file: null });
  };

  // 加载文件列表
  const loadFiles = useCallback(async (params: FileSearchParams) => {
    setLoading(true);
    try {
      const response = await FileAPI.getMyFiles(params);
      setFiles(response.files);
      setTotal(response.total);
      setCurrentPage(response.page);
    } catch (error) {
      console.error('加载文件列表失败:', error);
      message.error('加载文件列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // 加载统计信息
  const loadStatistics = useCallback(async () => {
    if (!showStatistics) return;
    
    try {
      const stats = await FileAPI.getFileStatistics();
      setStatistics(stats);
    } catch (error) {
      console.error('加载统计信息失败:', error);
      // 设置默认统计信息，避免渲染错误
      setStatistics({
        total_files: 0,
        total_size: 0,
        total_size_mb: 0,
        file_type_stats: {}
      });
    }
  }, [showStatistics]);

  // 初始化加载
  useEffect(() => {
    loadFiles(searchParams);
    loadStatistics();
  }, [loadFiles, loadStatistics, searchParams]);

  // 搜索处理
  const handleSearch = (value: string) => {
    const newParams = {
      ...searchParams,
      page: 1,
      keyword: value || undefined
    };
    setSearchParams(newParams);
    loadFiles(newParams);
  };

  // 文件类型过滤
  const handleContentTypeFilter = (value: string) => {
    const newParams = {
      ...searchParams,
      page: 1,
      content_type: value || undefined
    };
    setSearchParams(newParams);
    loadFiles(newParams);
  };

  // 排序处理
  const handleTableChange = (pagination: TablePaginationConfig, filters: any, sorter: any) => {
    const newParams = {
      ...searchParams,
      page: pagination.current || 1,
      page_size: pagination.pageSize || pageSize,
    };

    // 处理排序
    if (sorter.field) {
      newParams.sort_by = sorter.field;
      newParams.sort_order = sorter.order === 'ascend' ? 'asc' : 'desc';
    }

    setSearchParams(newParams);
    loadFiles(newParams);
  };

  // 下载文件
  const handleDownload = async (file: FileInfo) => {
    try {
      await FileAPI.downloadFile(file.file_id);
      message.success(`开始下载 ${file.original_filename}`);
    } catch (error) {
      message.error('文件下载失败');
    }
  };

  // 删除文件
  const handleDelete = (file: FileInfo) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除文件 "${file.original_filename}" 吗？此操作不可撤销。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await FileAPI.deleteFile(file.file_id);
          message.success('文件删除成功');
          loadFiles(searchParams);
          loadStatistics();
        } catch (error) {
          message.error('文件删除失败');
        }
      }
    });
  };

  // 文件上传
  const handleUpload = {
    name: 'file',
    showUploadList: false,
    customRequest: async ({ file, onSuccess, onError }: any) => {
      try {
        const response = await FileAPI.uploadFile(file as File);
        message.success(`文件 ${file.name} 上传成功`);
        onSuccess?.(response);
        loadFiles(searchParams);
        loadStatistics();
      } catch (error) {
        console.error('文件上传失败:', error);
        message.error(`文件 ${file.name} 上传失败`);
        onError?.(error);
      }
    },
    beforeUpload: (file: File) => {
      const isLt100M = file.size / 1024 / 1024 < 100;
      if (!isLt100M) {
        message.error('文件大小不能超过100MB');
        return false;
      }
      return true;
    }
  };

  // 操作菜单
  const getActionMenu = (file: FileInfo): MenuProps['items'] => [
    {
      key: 'preview',
      icon: <EyeOutlined />,
      label: '查看详情',
      onClick: () => handlePreview(file)
    },
    {
      key: 'download',
      icon: <DownloadOutlined />,
      label: '下载文件',
      onClick: () => handleDownload(file)
    },
    {
      type: 'divider'
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除文件',
      danger: true,
      onClick: () => handleDelete(file)
    }
  ];

  // 表格列定义
  const columns: ColumnsType<FileInfo> = [
    {
      title: '文件名',
      dataIndex: 'original_filename',
      key: 'filename',
      sorter: true,
      sortOrder: searchParams.sort_by === 'filename' 
        ? (searchParams.sort_order === 'asc' ? 'ascend' : 'descend') 
        : undefined,
      render: (filename: string, record: FileInfo) => (
        <Space>
          <span style={{ fontSize: '16px' }}>
            {FileAPI.getFileTypeIcon(record.content_type)}
          </span>
          <Tooltip title={filename}>
            <span 
              className="file-name-link"
              onClick={() => handlePreview(record)}
            >
              {filename.length > 30 ? `${filename.substring(0, 30)}...` : filename}
            </span>
          </Tooltip>
        </Space>
      )
    },
    {
      title: '类型',
      dataIndex: 'content_type',
      key: 'content_type',
      width: 120,
      render: (contentType: string) => (
        <Tag color="blue">{FileAPI.getFileTypeDescription(contentType)}</Tag>
      )
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      sorter: true,
      sortOrder: searchParams.sort_by === 'file_size' 
        ? (searchParams.sort_order === 'asc' ? 'ascend' : 'descend') 
        : undefined,
      render: (size: number) => FileAPI.formatFileSize(size)
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      sorter: true,
      sortOrder: searchParams.sort_by === 'created_at' 
        ? (searchParams.sort_order === 'asc' ? 'ascend' : 'descend') 
        : undefined,
      render: (date: string) => new Date(date).toLocaleString()
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record: FileInfo) => (
        <Space>
          <Tooltip title="下载文件">
            <Button
              type="text"
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(record)}
            />
          </Tooltip>
          <Tooltip title="查看详情">
            <Button
              type="text"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handlePreview(record)}
            />
          </Tooltip>
          <Dropdown
            menu={{ items: getActionMenu(record) }}
            trigger={['click']}
            placement="bottomRight"
          >
            <Button
              type="text"
              size="small"
              icon={<MoreOutlined />}
            />
          </Dropdown>
        </Space>
      )
    }
  ];

  return (
    <div className="file-list-container">
      {/* 统计信息卡片 */}
      {showStatistics && statistics && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="文件总数"
                value={statistics.total_files}
                prefix={<FileOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总存储空间"
                value={statistics.total_size_mb}
                precision={2}
                suffix="MB"
                prefix={<FolderOutlined />}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card>
              <div>
                <h4>文件类型分布</h4>
                <Space wrap>
                  {statistics.file_type_stats && Object.entries(statistics.file_type_stats).slice(0, 5).map(([type, count]) => (
                    <Tag key={type} color="processing">
                      {FileAPI.getFileTypeDescription(type)}: {count}
                    </Tag>
                  ))}
                </Space>
              </div>
            </Card>
          </Col>
        </Row>
      )}

      {/* 操作工具栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space>
              <Search
                placeholder="搜索文件名..."
                allowClear
                style={{ width: 300 }}
                onSearch={handleSearch}
                enterButton={<SearchOutlined />}
              />
              <Select
                placeholder="选择文件类型"
                allowClear
                style={{ width: 200 }}
                onChange={handleContentTypeFilter}
              >
                {statistics?.file_type_stats && Object.keys(statistics.file_type_stats).map(type => (
                  <Option key={type} value={type}>
                    {FileAPI.getFileTypeDescription(type)}
                  </Option>
                ))}
              </Select>
            </Space>
          </Col>
          <Col>
            <Space>
              {showUpload && (
                <Upload {...handleUpload}>
                  <Button type="primary" icon={<UploadOutlined />}>
                    上传文件
                  </Button>
                </Upload>
              )}
              <Button
                icon={<ReloadOutlined />}
                onClick={() => {
                  loadFiles(searchParams);
                  loadStatistics();
                }}
              >
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 文件列表表格 */}
      <Table
        columns={columns}
        dataSource={files}
        rowKey="file_id"
        loading={loading}
        pagination={{
          current: currentPage,
          total: total,
          pageSize: searchParams.page_size,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) =>
            `第 ${range[0]}-${range[1]} 条，共 ${total} 条记录`,
          pageSizeOptions: ['10', '20', '50', '100']
        }}
        onChange={handleTableChange}
        scroll={{ x: 800 }}
      />

      {/* 文件预览模态框 - 使用新的预览组件 */}
      <FilePreview
        file={previewModal.file}
        visible={previewModal.visible}
        onClose={handleClosePreview}
        onDownload={handleDownload}
      />
    </div>
  );
};

export default FileList;