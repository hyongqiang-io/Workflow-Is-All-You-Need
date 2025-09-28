/**
 * 我的资源页面 - 文件管理主页面
 * My Resources Page - Main File Management Page
 */

import React, { useState } from 'react';
import { 
  Card, 
  Tabs, 
  Alert,
  Typography,
  Space,
  Button,
  Upload,
  message,
  Divider 
} from 'antd';
import {
  FileOutlined,
  UploadOutlined,
  CloudUploadOutlined,
  InfoCircleOutlined,
  SettingOutlined
} from '@ant-design/icons';
import FileList from '../../components/FileList/FileList';
import { FileAPI } from '../../services/fileAPI';
import './MyResources.css';

const { Title, Paragraph, Text } = Typography;

const MyResources: React.FC = () => {
  const [activeTab, setActiveTab] = useState('files');
  const [uploadLoading, setUploadLoading] = useState(false);

  // 批量上传处理
  const handleBatchUpload = {
    name: 'files',
    multiple: true,
    showUploadList: true,
    customRequest: async ({ file, onSuccess, onError }: any) => {
      try {
        setUploadLoading(true);
        const response = await FileAPI.uploadFile(file as File);
        message.success(`文件 ${file.name} 上传成功`);
        onSuccess?.(response);
      } catch (error) {
        console.error('文件上传失败:', error);
        message.error(`文件 ${file.name} 上传失败`);
        onError?.(error);
      } finally {
        setUploadLoading(false);
      }
    },
    beforeUpload: (file: File) => {
      const isLt100M = file.size / 1024 / 1024 < 100;
      if (!isLt100M) {
        message.error(`文件 ${file.name} 大小不能超过100MB`);
        return false;
      }
      return true;
    },
    onRemove: () => {
      // 文件上传列表移除时的处理
    }
  };

  return (
    <div className="my-resources-container">
      {/* 页面头部 */}
      <Card className="page-header-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <Title level={2} style={{ margin: 0, marginBottom: '4px' }}>
              <Space>
                <FileOutlined />
                我的文件
              </Space>
            </Title>
            <Text type="secondary">管理您上传的所有文件和附件</Text>
          </div>
          <Space>
            <Upload {...handleBatchUpload}>
              <Button 
                type="primary" 
                icon={<UploadOutlined />}
                loading={uploadLoading}
              >
                上传文件
              </Button>
            </Upload>
            <Button type="default" icon={<SettingOutlined />}>
              存储设置
            </Button>
          </Space>
        </div>
      </Card>

      {/* 使用说明 */}
      <Card style={{ marginBottom: 24 }}>
        <Alert
          message="文件管理功能说明"
          description={
            <div>
              <Paragraph>
                <Text>在这里您可以：</Text>
              </Paragraph>
              <ul>
                <li>📁 查看和管理所有已上传的文件</li>
                <li>🔍 通过文件名搜索文件，支持实时搜索</li>
                <li>🏷️ 按文件类型过滤，快速找到特定类型文件</li>
                <li>📊 按文件大小、上传时间排序</li>
                <li>⬇️ 下载文件到本地</li>
                <li>🗑️ 删除不需要的文件（请谨慎操作）</li>
                <li>📈 查看文件存储统计信息</li>
              </ul>
              <Paragraph>
                <Text type="secondary">
                  支持的文件类型：PDF、Word、Excel、PowerPoint、图片、压缩包等，单个文件最大100MB
                </Text>
              </Paragraph>
            </div>
          }
          type="info"
          icon={<InfoCircleOutlined />}
          showIcon
          closable
        />
      </Card>

      {/* 主要内容区域 */}
      <Card>
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab}
          size="large"
          items={[
            {
              key: 'files',
              label: (
                <Space>
                  <FileOutlined />
                  文件管理
                </Space>
              ),
              children: (
                <FileList 
                  showUpload={true}
                  showStatistics={true}
                  pageSize={20}
                />
              )
            },
            {
              key: 'upload',
              label: (
                <Space>
                  <CloudUploadOutlined />
                  批量上传
                </Space>
              ),
              children: (
                <div className="batch-upload-container">
                  <Title level={4}>批量文件上传</Title>
                  <Paragraph type="secondary">
                    支持同时上传多个文件，每个文件最大100MB
                  </Paragraph>
                  
                  <Upload.Dragger {...handleBatchUpload} style={{ padding: '40px' }}>
                    <p className="ant-upload-drag-icon">
                      <CloudUploadOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
                    </p>
                    <p className="ant-upload-text">
                      <Title level={4} style={{ margin: 0 }}>
                        点击或拖拽文件到此区域上传
                      </Title>
                    </p>
                    <p className="ant-upload-hint">
                      支持单个或批量上传，严禁上传公司数据或其他敏感信息
                    </p>
                    <Divider />
                    <Space direction="vertical" size="small">
                      <Text type="secondary">📄 支持文档：PDF, Word, Excel, PowerPoint</Text>
                      <Text type="secondary">🖼️ 支持图片：JPG, PNG, GIF</Text>
                      <Text type="secondary">📦 支持压缩：ZIP, RAR</Text>
                      <Text type="secondary">📝 支持文本：TXT, CSV, JSON</Text>
                    </Space>
                  </Upload.Dragger>
                </div>
              )
            }
          ]}
        />
      </Card>
    </div>
  );
};

export default MyResources;