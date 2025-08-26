import React, { useState, useEffect } from 'react';
import { 
  Modal, 
  Button, 
  Upload, 
  message, 
  Card, 
  Typography, 
  Descriptions, 
  Tag, 
  Alert, 
  Space, 
  Checkbox, 
  Divider,
  List,
  Input,
  Form,
  Radio
} from 'antd';
import { 
  DownloadOutlined, 
  UploadOutlined, 
  FileTextOutlined, 
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  EditOutlined
} from '@ant-design/icons';
import { workflowAPI } from '../services/api';

const { Title, Text } = Typography;
const { Dragger } = Upload;

interface WorkflowImportExportProps {
  // 导出相关
  workflowId?: string;
  workflowName?: string;
  onExportSuccess?: () => void;
  
  // 导入相关
  onImportSuccess?: (result: any) => void;
  preloadedData?: any; // AI生成的预加载数据
  hideExportSection?: boolean; // 隐藏导出部分
  
  // 界面控制 - 更新为可选，支持独立使用
  visible?: boolean;
  mode?: 'export' | 'import';
  onClose?: () => void;
}

const WorkflowImportExport: React.FC<WorkflowImportExportProps> = ({
  workflowId,
  workflowName,
  onExportSuccess,
  onImportSuccess,
  preloadedData, // 添加这个参数
  hideExportSection,
  visible,
  mode,
  onClose
}) => {
  const [loading, setLoading] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [overwriteConfirmed, setOverwriteConfirmed] = useState(false);
  // 新增状态：冲突处理方式和修改后的名称
  const [conflictResolution, setConflictResolution] = useState<'overwrite' | 'rename'>('rename');
  const [customWorkflowName, setCustomWorkflowName] = useState('');

  // 处理预加载数据
  useEffect(() => {
    if (preloadedData) {
      setPreviewData({
        name: preloadedData.name || preloadedData.workflow_name,
        description: preloadedData.description,
        nodes: preloadedData.nodes || [],
        connections: preloadedData.connections || [],
        requires_confirmation: false, // AI生成的数据通常不需要确认
        preview: {
          workflow_info: {
            name: preloadedData.name || preloadedData.workflow_name,
            description: preloadedData.description,
            export_version: preloadedData.export_version || '2.0'
          },
          nodes_count: (preloadedData.nodes || []).length,
          connections_count: (preloadedData.connections || []).length,
          validation_result: {
            valid: true,
            errors: [],
            warnings: []
          }
        }
      });
      // 设置默认名称
      setCustomWorkflowName(preloadedData.name || preloadedData.workflow_name || 'AI生成工作流');
    }
  }, [preloadedData]);

  // ============================================================================
  // 导出功能
  // ============================================================================
  
  const handleExport = async () => {
    if (!workflowId) {
      message.error('请选择要导出的工作流');
      return;
    }

    // 验证 UUID 格式
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(workflowId)) {
      message.error(`无效的工作流ID格式: ${workflowId}`);
      console.error('🚨 无效的工作流ID格式:', workflowId);
      return;
    }

    setLoading(true);
    try {
      console.log('🔄 开始导出工作流:', workflowId);
      console.log('🔍 工作流ID验证通过');
      
      const response: any = await workflowAPI.exportWorkflow(workflowId);
      
      if (response.success) {
        const { export_data, filename } = response.data;
        
        // 下载JSON文件
        workflowAPI.downloadWorkflowJSON(export_data, filename);
        
        message.success(`工作流 "${export_data.name}" 导出成功！`);
        
        if (onExportSuccess) {
          onExportSuccess();
        }
        
        if (onClose) {
          onClose();
        }
      } else {
        message.error(response.message || '导出失败');
      }
    } catch (error: any) {
      console.error('导出失败:', error);
      console.error('错误详情:', {
        url: error.config?.url,
        method: error.config?.method,
        status: error.response?.status,
        data: error.response?.data
      });
      message.error(error.message || '导出工作流失败');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================================
  // 导入功能
  // ============================================================================

  const handleFileUpload = async (file: File) => {
    console.log('📁 选择文件:', file.name);
    
    // 验证文件类型
    if (!file.name.endsWith('.json')) {
      message.error('只支持JSON格式的工作流文件');
      return false;
    }

    setImportFile(file);
    
    // 读取文件内容并预览
    try {
      const content = await readFileContent(file);
      const jsonData = JSON.parse(content);
      
      console.log('📄 文件内容:', jsonData);
      
      // 预览导入数据
      const previewResponse: any = await workflowAPI.previewImportWorkflow(jsonData);
      
      if (previewResponse.success) {
        setPreviewData(previewResponse.data);
        console.log('👀 预览数据:', previewResponse.data);
      } else {
        message.error('无法预览导入数据');
        setPreviewData(null);
      }
    } catch (error: any) {
      console.error('文件处理失败:', error);
      message.error('文件格式错误或内容无效');
      setImportFile(null);
      setPreviewData(null);
    }
    
    return false; // 阻止自动上传
  };

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = (e) => reject(e);
      reader.readAsText(file);
    });
  };

  const handleImport = async () => {
    // 如果有预加载数据，直接使用；否则需要文件
    if (!preloadedData && (!importFile || !previewData)) {
      message.error('请先选择要导入的文件');
      return;
    }

    if (!previewData) {
      message.error('数据预览失败，请重新选择文件');
      return;
    }

    // 检查冲突处理方式
    const hasConflicts = previewData.requires_confirmation;
    let shouldOverwrite = false;
    let finalImportData = null;

    if (hasConflicts) {
      if (conflictResolution === 'overwrite') {
        if (!overwriteConfirmed) {
          message.warning('请确认覆盖现有工作流');
          return;
        }
        shouldOverwrite = true;
        finalImportData = preloadedData || JSON.parse(await importFile!.text());
      } else if (conflictResolution === 'rename') {
        if (!customWorkflowName.trim()) {
          message.warning('请输入新的工作流名称');
          return;
        }
        // 创建修改名称后的导入数据
        finalImportData = preloadedData || JSON.parse(await importFile!.text());
        finalImportData.name = customWorkflowName.trim();
        shouldOverwrite = false;
      }
    } else {
      // 没有冲突，直接导入
      if (preloadedData) {
        finalImportData = {
          ...preloadedData,
          name: customWorkflowName.trim() || preloadedData.name || preloadedData.workflow_name
        };
      } else {
        finalImportData = JSON.parse(await importFile!.text());
      }
      shouldOverwrite = false;
    }

    setLoading(true);
    try {
      console.log('🔄 开始导入工作流:', finalImportData.name);
      
      let response: any;
      if (preloadedData || (hasConflicts && conflictResolution === 'rename')) {
        // 对于预加载数据或重命名情况，直接使用数据导入
        response = await workflowAPI.importWorkflow(finalImportData, shouldOverwrite);
      } else {
        // 使用原始文件导入
        response = await workflowAPI.importWorkflowFromFile(importFile!, shouldOverwrite);
      }
      
      if (response.success) {
        const { import_result } = response.data;
        
        // 构建成功消息
        let successMessage = `工作流导入成功！创建了 ${import_result.created_nodes} 个节点和 ${import_result.created_connections} 个连接`;
        
        // 如果有警告，显示警告信息
        if (import_result.warnings && import_result.warnings.length > 0) {
          console.warn('导入警告:', import_result.warnings);
          
          // 检查是否有连接相关的警告
          const connectionWarnings = import_result.warnings.filter((w: string) => 
            w.includes('连接') || w.includes('缺失')
          );
          
          if (connectionWarnings.length > 0) {
            message.warning({
              content: (
                <div>
                  <div>{successMessage}</div>
                  <div style={{ marginTop: 8, fontSize: '12px', color: '#fa8c16' }}>
                    ⚠️ 检测到连接问题，请检查工作流中的连线是否完整
                  </div>
                </div>
              ),
              duration: 6
            });
          } else {
            message.success(successMessage);
          }
        } else {
          message.success(successMessage);
        }
        
        if (onImportSuccess && import_result.workflow_id) {
          onImportSuccess(import_result.workflow_id);
        }
        
        if (onClose) {
          onClose();
        }
        
        // 重置状态
        setImportFile(null);
        setPreviewData(null);
        setOverwriteConfirmed(false);
        setConflictResolution('rename');
        setCustomWorkflowName('');
      } else {
        // 显示详细的验证错误信息
        let errorMessage = response.message || '导入失败';
        if (response.data?.errors && response.data.errors.length > 0) {
          errorMessage += '\n详细错误:\n' + response.data.errors.join('\n');
        }
        if (response.data?.warnings && response.data.warnings.length > 0) {
          errorMessage += '\n警告信息:\n' + response.data.warnings.join('\n');
        }
        
        message.error({
          content: errorMessage,
          duration: 8, // 延长显示时间以便阅读详细信息
          style: { whiteSpace: 'pre-line' } // 支持换行显示
        });
      }
    } catch (error: any) {
      console.error('导入失败:', error);
      message.error(error.message || '导入工作流失败');
    } finally {
      setLoading(false);
    }
  };

  const resetImport = () => {
    setImportFile(null);
    setPreviewData(null);
    setOverwriteConfirmed(false);
    setConflictResolution('rename');
    setCustomWorkflowName('');
  };

  // ============================================================================
  // 渲染函数
  // ============================================================================

  const renderExportContent = () => (
    <div>
      <Alert
        message="导出说明"
        description="导出的JSON文件包含工作流的结构信息（节点和连接），但不包含处理器分配信息，方便在不同环境间复用工作流模板。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
      
      <Card>
        <Descriptions column={1} bordered>
          <Descriptions.Item label="工作流名称">{workflowName || '未知'}</Descriptions.Item>
          <Descriptions.Item label="工作流ID">{workflowId || '未知'}</Descriptions.Item>
          <Descriptions.Item label="导出格式">JSON</Descriptions.Item>
          <Descriptions.Item label="包含内容">
            <Space direction="vertical">
              <Tag color="blue">工作流基本信息</Tag>
              <Tag color="green">节点结构</Tag>
              <Tag color="orange">节点连接</Tag>
              <Tag color="red">不包含处理器分配</Tag>
            </Space>
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );

  const renderImportContent = () => (
    <div>
      <Alert
        message="导入说明"
        description="导入工作流JSON文件将创建新的工作流，包含原始的节点结构，但需要重新分配处理器。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      {!previewData ? (
        <Card>
          <Dragger
            name="workflow"
            multiple={false}
            accept=".json"
            beforeUpload={handleFileUpload}
            showUploadList={false}
          >
            <p className="ant-upload-drag-icon">
              <FileTextOutlined style={{ fontSize: 48, color: '#1890ff' }} />
            </p>
            <p className="ant-upload-text">点击或拖拽JSON文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持单个JSON格式的工作流文件上传
            </p>
          </Dragger>
        </Card>
      ) : (
        <div>
          {/* 预览信息 */}
          <Card title="导入预览" style={{ marginBottom: 16 }}>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="工作流名称">
                {previewData.preview.workflow_info.name}
              </Descriptions.Item>
              <Descriptions.Item label="描述">
                {previewData.preview.workflow_info.description || '无'}
              </Descriptions.Item>
              <Descriptions.Item label="节点数量">
                <Tag color="blue">{previewData.preview.nodes_count} 个</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="连接数量">
                <Tag color="green">{previewData.preview.connections_count} 个</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="导出版本">
                <Tag color={previewData.preview.workflow_info.export_version === '2.0' ? 'orange' : 'default'}>
                  {previewData.preview.workflow_info.export_version || '1.0'}
                  {previewData.preview.workflow_info.export_version === '2.0' && ' (增强版)'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="导出时间">
                {previewData.preview.workflow_info.export_timestamp || '未知'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 验证结果 */}
          <Card title="验证结果" style={{ marginBottom: 16 }}>
            {previewData.preview.validation_result.valid ? (
              <Alert
                message="验证通过"
                type="success"
                showIcon
                icon={<CheckCircleOutlined />}
              />
            ) : (
              <Alert
                message="验证失败"
                description={
                  <List
                    size="small"
                    dataSource={previewData.preview.validation_result.errors || []}
                    renderItem={(error: string) => <List.Item>{error}</List.Item>}
                  />
                }
                type="error"
                showIcon
              />
            )}

            {previewData.preview.validation_result.warnings?.length > 0 && (
              <Alert
                message="警告信息"
                description={
                  <List
                    size="small"
                    dataSource={previewData.preview.validation_result.warnings}
                    renderItem={(warning: string) => <List.Item>{warning}</List.Item>}
                  />
                }
                type="warning"
                showIcon
                style={{ marginTop: 8 }}
              />
            )}
          </Card>

          {/* 冲突检查 */}
          {previewData.preview.conflicts && previewData.preview.conflicts.length > 0 && (
            <Card title="冲突检查" style={{ marginBottom: 16 }}>
              <Alert
                message="发现冲突"
                description={
                  <div>
                    <List
                      size="small"
                      dataSource={previewData.preview.conflicts}
                      renderItem={(conflict: string) => <List.Item>{conflict}</List.Item>}
                    />
                    <Divider />
                    
                    {/* 冲突解决方式选择 */}
                    <Text strong style={{ marginBottom: 8, display: 'block' }}>
                      选择解决方式：
                    </Text>
                    <Radio.Group 
                      value={conflictResolution}
                      onChange={(e) => {
                        setConflictResolution(e.target.value);
                        if (e.target.value === 'rename' && previewData.preview.workflow_info?.name) {
                          setCustomWorkflowName(previewData.preview.workflow_info.name + '_副本');
                        }
                      }}
                      style={{ marginBottom: 16 }}
                    >
                      <Space direction="vertical">
                        <Radio value="rename">
                          <Space>
                            <EditOutlined />
                            使用新名称导入
                          </Space>
                        </Radio>
                        <Radio value="overwrite">
                          <Space>
                            <WarningOutlined />
                            覆盖现有工作流
                          </Space>
                        </Radio>
                      </Space>
                    </Radio.Group>

                    {/* 如果选择重命名，显示名称输入框 */}
                    {conflictResolution === 'rename' && (
                      <div style={{ marginBottom: 16 }}>
                        <Text strong>新的工作流名称：</Text>
                        <Input
                          placeholder="请输入新的工作流名称"
                          value={customWorkflowName}
                          onChange={(e) => setCustomWorkflowName(e.target.value)}
                          style={{ marginTop: 8 }}
                          maxLength={100}
                          showCount
                        />
                      </div>
                    )}

                    {/* 如果选择覆盖，显示确认checkbox */}
                    {conflictResolution === 'overwrite' && (
                      <Checkbox
                        checked={overwriteConfirmed}
                        onChange={(e) => setOverwriteConfirmed(e.target.checked)}
                      >
                        我确认要覆盖现有的同名工作流
                      </Checkbox>
                    )}
                  </div>
                }
                type="warning"
                showIcon
              />
            </Card>
          )}

          {/* 重新选择文件 */}
          <Button onClick={resetImport} style={{ marginTop: 8 }}>
            重新选择文件
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <Modal
      title={
        <Space>
          {mode === 'export' ? <DownloadOutlined /> : <UploadOutlined />}
          {mode === 'export' ? '导出工作流' : '导入工作流'}
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        mode === 'export' ? (
          <Button
            key="export"
            type="primary"
            icon={<DownloadOutlined />}
            loading={loading}
            onClick={handleExport}
          >
            导出JSON文件
          </Button>
        ) : (
          <Button
            key="import"
            type="primary"
            icon={<UploadOutlined />}
            loading={loading}
            disabled={
              !previewData || 
              !previewData.preview.validation_result.valid ||
              (previewData.requires_confirmation && conflictResolution === 'overwrite' && !overwriteConfirmed) ||
              (previewData.requires_confirmation && conflictResolution === 'rename' && !customWorkflowName.trim())
            }
            onClick={handleImport}
          >
            导入工作流
          </Button>
        )
      ]}
    >
      {mode === 'export' ? renderExportContent() : renderImportContent()}
    </Modal>
  );
};

export default WorkflowImportExport;