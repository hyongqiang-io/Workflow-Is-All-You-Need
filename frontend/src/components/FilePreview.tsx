/**
 * 文件预览组件 - Linus式简洁设计
 * File Preview Component - Linus Style Simple Design
 */

import React, { useState, useEffect } from 'react';
import { Modal, Spin, Alert, Typography, Row, Col, Tag, Button } from 'antd';
import { DownloadOutlined, CloseOutlined } from '@ant-design/icons';
import { FileAPI, FilePreviewData, FileInfo } from '../services/fileAPI';

const { Title, Paragraph, Text } = Typography;

interface FilePreviewProps {
  file: FileInfo | null;
  visible: boolean;
  onClose: () => void;
  onDownload?: (file: FileInfo) => void;
}

const FilePreview: React.FC<FilePreviewProps> = ({
  file,
  visible,
  onClose,
  onDownload
}) => {
  const [previewData, setPreviewData] = useState<FilePreviewData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);

  // 加载预览数据
  const loadPreview = async (fileId: string) => {
    setLoading(true);
    setError(null);
    try {
      const preview = await FileAPI.previewFile(fileId);
      setPreviewData(preview);

      // 如果是PDF文件，需要获取blob URL以支持认证
      if (preview.preview_type === 'pdf_viewer') {
        await loadPDFBlob(fileId);
      }
    } catch (err: any) {
      setError(err.message || '预览加载失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载PDF的blob URL - Linus式解决认证问题
  const loadPDFBlob = async (fileId: string) => {
    try {
      const token = localStorage.getItem('token');

      // 构建完整的API URL - 修复路径问题
      const apiBaseURL = process.env.REACT_APP_API_BASE_URL ||
        (process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api');
      const fullUrl = `${apiBaseURL}/files/${fileId}/raw`;

      console.log('🔍 [PDF预览] 发起PDF获取请求:', {
        fileId,
        url: fullUrl,
        hasToken: !!token
      });

      const response = await fetch(fullUrl, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/pdf',
        },
      });

      console.log('🔍 [PDF预览] 服务器响应:', {
        status: response.status,
        statusText: response.statusText,
        contentType: response.headers.get('content-type'),
        contentLength: response.headers.get('content-length')
      });

      if (!response.ok) {
        throw new Error(`PDF获取失败: ${response.status} ${response.statusText}`);
      }

      const blob = await response.blob();
      console.log('🔍 [PDF预览] Blob创建成功:', {
        size: blob.size,
        type: blob.type
      });

      // 验证是否为PDF类型
      if (!blob.type.includes('pdf') && !blob.type.includes('application/pdf')) {
        console.warn('⚠️ [PDF预览] 响应不是PDF类型:', blob.type);
      }

      const url = URL.createObjectURL(blob);
      console.log('🔍 [PDF预览] Blob URL创建成功:', url);
      setPdfBlobUrl(url);

    } catch (err: any) {
      console.error('❌ [PDF预览] PDF blob加载失败:', err);
      setError(`PDF文件加载失败: ${err.message}`);
    }
  };

  // 当文件变化时重新加载预览
  useEffect(() => {
    if (visible && file) {
      loadPreview(file.file_id);
    } else {
      setPreviewData(null);
      setError(null);
      // 清理PDF blob URL
      if (pdfBlobUrl) {
        URL.revokeObjectURL(pdfBlobUrl);
        setPdfBlobUrl(null);
      }
    }
  }, [visible, file]);

  // 组件卸载时清理blob URL
  useEffect(() => {
    return () => {
      if (pdfBlobUrl) {
        URL.revokeObjectURL(pdfBlobUrl);
      }
    };
  }, [pdfBlobUrl]);

  // 渲染预览内容
  const renderPreviewContent = () => {
    if (loading) {
      return (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" />
          <p style={{ marginTop: '16px' }}>正在加载预览...</p>
        </div>
      );
    }

    if (error) {
      return (
        <Alert
          message="预览失败"
          description={error}
          type="error"
          showIcon
          style={{ margin: '20px 0' }}
        />
      );
    }

    if (!previewData) {
      return null;
    }

    switch (previewData.preview_type) {
      case 'text':
        return renderTextPreview();
      case 'image':
        return renderImagePreview();
      case 'pdf_viewer':
        return renderPDFViewer();
      case 'pdf_text':
      case 'office_text':
        return renderDocumentPreview();
      case 'metadata':
        return renderMetadataPreview();
      case 'error':
        return renderErrorPreview();
      default:
        return <div>不支持的预览类型</div>;
    }
  };

  const renderTextPreview = () => (
    <div style={{ padding: '16px' }}>
      <Row gutter={16} style={{ marginBottom: '16px' }}>
        <Col span={12}>
          <Text strong>编码: </Text>
          <Tag color="blue">{previewData?.encoding || '未知'}</Tag>
        </Col>
        {previewData?.truncated && (
          <Col span={12}>
            <Tag color="orange">内容已截断</Tag>
          </Col>
        )}
      </Row>
      <div
        style={{
          background: '#f5f5f5',
          padding: '16px',
          borderRadius: '4px',
          fontFamily: 'monospace',
          fontSize: '12px',
          maxHeight: '500px',
          overflow: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all'
        }}
      >
        {previewData?.content}
      </div>
    </div>
  );

  const renderImagePreview = () => (
    <div style={{ textAlign: 'center', padding: '16px' }}>
      <img
        src={`data:${previewData?.content_type};base64,${previewData?.content}`}
        alt="预览图片"
        style={{
          maxWidth: '100%',
          maxHeight: '600px',
          objectFit: 'contain',
          border: '1px solid #ddd',
          borderRadius: '4px'
        }}
      />
      {previewData?.file_size && (
        <div style={{ marginTop: '8px' }}>
          <Text type="secondary">
            文件大小: {FileAPI.formatFileSize(previewData.file_size)}
          </Text>
        </div>
      )}
    </div>
  );

  const renderPDFViewer = () => (
    <div style={{ padding: '16px', height: '600px' }}>
      <Row gutter={16} style={{ marginBottom: '16px' }}>
        <Col span={24}>
          <Text strong>PDF文档预览</Text>
          <Tag color="blue" style={{ marginLeft: '8px' }}>原生PDF查看器</Tag>
          {previewData?.file_size && (
            <Text type="secondary" style={{ marginLeft: '12px' }}>
              文件大小: {FileAPI.formatFileSize(previewData.file_size)}
            </Text>
          )}
        </Col>
      </Row>

      {pdfBlobUrl ? (
        <>
          {/* 使用带认证的blob URL - Linus式认证问题解决方案 */}
          <iframe
            src={`${pdfBlobUrl}#toolbar=1&navpanes=1&scrollbar=1&view=FitH`}
            style={{
              width: '100%',
              height: '520px',
              border: '1px solid #d9d9d9',
              borderRadius: '4px'
            }}
            title="PDF预览"
          />
          <div style={{
            marginTop: '8px',
            fontSize: '12px',
            color: '#666',
            textAlign: 'center'
          }}>
            💡 提示：如果PDF显示有问题，请尝试直接下载文件查看
          </div>
        </>
      ) : (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '520px',
          background: '#fafafa',
          border: '1px solid #e8e8e8',
          borderRadius: '4px',
          color: '#666'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📄</div>
          <div>PDF文件正在加载中...</div>
          {error && (
            <div style={{
              fontSize: '12px',
              marginTop: '8px',
              color: '#ff4d4f',
              maxWidth: '400px',
              textAlign: 'center',
              padding: '8px',
              background: '#fff2f0',
              border: '1px solid #ffccc7',
              borderRadius: '4px'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>加载失败</div>
              <div>{error}</div>
              <div style={{ marginTop: '4px', fontSize: '11px', color: '#999' }}>
                请检查浏览器控制台获取详细错误信息
              </div>
            </div>
          )}
          <div style={{ fontSize: '12px', marginTop: '8px', color: '#999' }}>
            请稍等或点击下载按钮下载文件查看
          </div>
        </div>
      )}
    </div>
  );

  const renderDocumentPreview = () => (
    <div style={{ padding: '16px' }}>
      <Row gutter={16} style={{ marginBottom: '16px' }}>
        <Col span={12}>
          <Text strong>提取方式: </Text>
          <Tag color="green">{previewData?.extractor || '文档'}</Tag>
        </Col>
        {previewData?.truncated && (
          <Col span={12}>
            <Tag color="orange">内容已截断</Tag>
          </Col>
        )}
      </Row>
      <div
        style={{
          background: '#fafafa',
          padding: '16px',
          borderRadius: '4px',
          border: '1px solid #e8e8e8',
          maxHeight: '500px',
          overflow: 'auto',
          lineHeight: '1.6'
        }}
      >
        <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0 }}>
          {previewData?.content}
        </pre>
      </div>
    </div>
  );

  const renderMetadataPreview = () => {
    const metadata = previewData?.content;
    return (
      <div style={{ padding: '16px' }}>
        <Alert
          message={metadata?.message || '此文件类型不支持内容预览'}
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
        <Row gutter={16}>
          <Col span={12}>
            <p><strong>文件名:</strong> {metadata?.filename}</p>
            <p><strong>文件类型:</strong> {metadata?.content_type}</p>
            <p><strong>文件大小:</strong> {FileAPI.formatFileSize(metadata?.file_size || 0)}</p>
          </Col>
          <Col span={12}>
            <p><strong>创建时间:</strong> {new Date(metadata?.created_time * 1000).toLocaleString()}</p>
            <p><strong>修改时间:</strong> {new Date(metadata?.modified_time * 1000).toLocaleString()}</p>
          </Col>
        </Row>
      </div>
    );
  };

  const renderErrorPreview = () => (
    <Alert
      message="预览错误"
      description={previewData?.content}
      type="error"
      showIcon
      style={{ margin: '20px 0' }}
    />
  );

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '24px' }}>
            {file ? FileAPI.getFileTypeIcon(file.content_type) : '📄'}
          </span>
          <div>
            <div>{file?.original_filename}</div>
            <div style={{ fontSize: '12px', color: '#666', fontWeight: 'normal' }}>
              {file ? FileAPI.getFileTypeDescription(file.content_type) : ''}
            </div>
          </div>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        file && onDownload && (
          <Button
            key="download"
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => onDownload(file)}
          >
            下载文件
          </Button>
        )
      ]}
      width={800}
      style={{ top: 20 }}
      bodyStyle={{ maxHeight: '70vh', overflow: 'auto' }}
    >
      {renderPreviewContent()}
    </Modal>
  );
};

export default FilePreview;