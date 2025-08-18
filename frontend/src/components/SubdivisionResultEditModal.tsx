import React, { useState, useEffect } from 'react';
import { 
  Modal, 
  Form, 
  Input, 
  Button, 
  message,
  Card,
  Typography,
  Space,
  Alert,
  Divider
} from 'antd';
import { 
  EditOutlined,
  SaveOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface SubdivisionResultEditModalProps {
  visible: boolean;
  onCancel: () => void;
  onSubmit: (editedResult: string, resultSummary: string) => void;
  subdivisionResult: {
    subdivision_id: string;
    subdivision_name: string;
    original_result: string;
    execution_summary?: string;
    total_tasks?: number;
    completed_tasks?: number;
    execution_duration?: string;
  };
  originalTaskTitle: string;
  loading?: boolean;
}

const SubdivisionResultEditModal: React.FC<SubdivisionResultEditModalProps> = ({
  visible,
  onCancel,
  onSubmit,
  subdivisionResult,
  originalTaskTitle,
  loading = false
}) => {
  const [form] = Form.useForm();
  const [previewMode, setPreviewMode] = useState(false);

  useEffect(() => {
    if (visible && subdivisionResult) {
      // 当模态框打开时，设置初始值
      form.setFieldsValue({
        edited_result: subdivisionResult.original_result || '',
        result_summary: generateDefaultSummary()
      });
    }
  }, [visible, subdivisionResult, form]);

  const generateDefaultSummary = () => {
    if (!subdivisionResult) return '';
    
    const parts = [
      `细分工作流 "${subdivisionResult.subdivision_name}" 执行完成`,
    ];
    
    if (subdivisionResult.total_tasks) {
      parts.push(`共完成 ${subdivisionResult.completed_tasks || 0}/${subdivisionResult.total_tasks} 个任务`);
    }
    
    if (subdivisionResult.execution_duration) {
      parts.push(`执行耗时: ${subdivisionResult.execution_duration}`);
    }
    
    return parts.join(' | ');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      await onSubmit(values.edited_result, values.result_summary);
      message.success('细分工作流结果已提交');
    } catch (error) {
      console.error('提交失败:', error);
    }
  };

  const handlePreview = () => {
    form.validateFields().then(values => {
      setPreviewMode(!previewMode);
    }).catch(() => {
      message.warning('请先完成必填字段');
    });
  };

  const renderPreviewContent = () => {
    const values = form.getFieldsValue();
    return (
      <div>
        <Alert
          message="提交预览"
          description="这就是将要提交给原始任务的内容"
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
        
        <Card size="small" title="结果摘要" style={{ marginBottom: '12px' }}>
          <Text>{values.result_summary || '无摘要'}</Text>
        </Card>
        
        <Card size="small" title="详细结果">
          <div style={{ 
            background: '#f5f5f5', 
            padding: '12px', 
            borderRadius: '4px',
            whiteSpace: 'pre-wrap',
            maxHeight: '300px',
            overflow: 'auto'
          }}>
            {values.edited_result || '无内容'}
          </div>
        </Card>
      </div>
    );
  };

  return (
    <Modal
      title={
        <Space>
          <EditOutlined />
          <span>编辑细分工作流结果</span>
        </Space>
      }
      open={visible}
      onCancel={onCancel}
      width={800}
      style={{ top: 20 }}
      footer={[
        <Button key="preview" onClick={handlePreview}>
          {previewMode ? '返回编辑' : '预览结果'}
        </Button>,
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button 
          key="submit" 
          type="primary" 
          loading={loading}
          onClick={handleSubmit}
          icon={<SaveOutlined />}
        >
          提交结果
        </Button>,
      ]}
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <Alert
          message={`正在编辑任务"${originalTaskTitle}"的细分工作流结果`}
          description={`细分名称: ${subdivisionResult?.subdivision_name || '未知'}`}
          type="success"
          showIcon
          icon={<CheckCircleOutlined />}
        />
      </div>

      {!previewMode ? (
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            edited_result: subdivisionResult?.original_result || '',
            result_summary: generateDefaultSummary()
          }}
        >
          {/* 原始结果展示 */}
          <Card 
            size="small" 
            title={
              <Space>
                <InfoCircleOutlined />
                <span>原始细分工作流结果</span>
              </Space>
            }
            style={{ marginBottom: '16px', backgroundColor: '#fafafa' }}
          >
            <div style={{ 
              maxHeight: '150px', 
              overflow: 'auto',
              padding: '8px',
              background: '#fff',
              border: '1px solid #e8e8e8',
              borderRadius: '4px'
            }}>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                以下是细分工作流自动生成的原始结果，您可以基于此内容进行编辑和完善：
              </Text>
              <pre style={{ 
                marginTop: '8px', 
                marginBottom: '0',
                fontSize: '13px',
                whiteSpace: 'pre-wrap'
              }}>
                {subdivisionResult?.original_result || '无原始结果'}
              </pre>
            </div>
          </Card>

          <Divider orientation="left">编辑结果内容</Divider>

          {/* 编辑区域 */}
          <Form.Item
            name="edited_result"
            label="任务结果"
            rules={[{ required: true, message: '请输入或编辑任务结果' }]}
            extra="您可以基于上方的原始结果进行编辑、补充或重新组织"
          >
            <TextArea 
              rows={8} 
              placeholder="请编辑任务结果内容...

您可以：
- 直接使用上方的原始结果
- 对原始结果进行编辑和完善
- 重新组织结果的表达方式
- 添加您的分析和见解"
            />
          </Form.Item>

          <Form.Item
            name="result_summary"
            label="结果摘要"
            rules={[{ required: true, message: '请输入结果摘要' }]}
            extra="简要概括细分工作流的执行情况和主要成果"
          >
            <Input 
              placeholder="例如：数据分析细分流程执行完成 | 共完成 4/4 个任务 | 生成销售分析报告"
            />
          </Form.Item>
        </Form>
      ) : (
        renderPreviewContent()
      )}
    </Modal>
  );
};

export default SubdivisionResultEditModal;