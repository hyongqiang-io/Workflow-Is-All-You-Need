import React, { useState } from 'react';
import {
  Modal,
  Form,
  Input,
  Select,
  Tag,
  Button,
  Switch,
  InputNumber,
  message,
  Space,
  Typography
} from 'antd';
import {
  AppstoreOutlined,
  TagOutlined,
  DollarOutlined,
  InfoCircleOutlined
} from '@ant-design/icons';
import { storeAPI } from '../services/storeAPI';
import type { StoreCategory, WorkflowStoreCreate } from '../types/store';

const { TextArea } = Input;
const { Option } = Select;
const { Text } = Typography;

// 分类选项
const categoryOptions = [
  { value: 'automation', label: '自动化', icon: '🤖', description: '自动化业务流程和任务' },
  { value: 'data_processing', label: '数据处理', icon: '📊', description: '数据分析、转换和处理' },
  { value: 'ai_ml', label: 'AI/机器学习', icon: '🧠', description: 'AI模型训练和机器学习流程' },
  { value: 'business', label: '商业流程', icon: '💼', description: '业务流程和企业管理' },
  { value: 'integration', label: '系统集成', icon: '🔗', description: '系统间数据集成和同步' },
  { value: 'template', label: '模板', icon: '📋', description: '通用工作流模板' },
  { value: 'other', label: '其他', icon: '📦', description: '其他类型的工作流' }
];

interface PublishWorkflowModalProps {
  visible: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  workflowBaseId: string;
  workflowName: string;
  workflowDescription?: string;
}

const PublishWorkflowModal: React.FC<PublishWorkflowModalProps> = ({
  visible,
  onCancel,
  onSuccess,
  workflowBaseId,
  workflowName,
  workflowDescription
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [inputTag, setInputTag] = useState('');

  // 添加标签
  const addTag = () => {
    if (inputTag && !tags.includes(inputTag)) {
      setTags([...tags, inputTag]);
      setInputTag('');
    }
  };

  // 移除标签
  const removeTag = (tag: string) => {
    setTags(tags.filter(t => t !== tag));
  };

  // 处理提交
  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      const storeData: WorkflowStoreCreate = {
        title: values.title,
        description: values.description,
        category: values.category as StoreCategory,
        tags: tags,
        is_featured: false, // 默认不推荐，由管理员设置
        is_free: values.is_free,
        price: values.is_free ? undefined : values.price,
        workflow_base_id: workflowBaseId
      };

      const result = await storeAPI.publishWorkflow(workflowBaseId, storeData);

      message.success('工作流发布成功！');
      form.resetFields();
      setTags([]);
      onSuccess();

    } catch (error: any) {
      console.error('发布工作流失败:', error);
      if (error.response?.status === 409) {
        message.error('该工作流已发布到商店');
      } else if (error.response?.status === 403) {
        message.error('无权限发布此工作流');
      } else {
        message.error(error.response?.data?.detail || '发布工作流失败');
      }
    } finally {
      setLoading(false);
    }
  };

  // 重置表单
  const handleCancel = () => {
    form.resetFields();
    setTags([]);
    onCancel();
  };

  return (
    <Modal
      title={
        <Space>
          <AppstoreOutlined />
          发布工作流到商店
        </Space>
      }
      open={visible}
      onCancel={handleCancel}
      footer={null}
      width={600}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          title: workflowName,
          description: workflowDescription,
          is_free: true,
          category: 'template'
        }}
      >
        <Form.Item
          name="title"
          label="标题"
          rules={[
            { required: true, message: '请输入标题' },
            { max: 255, message: '标题不能超过255个字符' }
          ]}
        >
          <Input placeholder="输入商店中显示的工作流标题" />
        </Form.Item>

        <Form.Item
          name="description"
          label="描述"
          rules={[
            { max: 2000, message: '描述不能超过2000个字符' }
          ]}
        >
          <TextArea
            rows={4}
            placeholder="详细描述这个工作流的功能和使用场景..."
          />
        </Form.Item>

        <Form.Item
          name="category"
          label="分类"
          rules={[{ required: true, message: '请选择分类' }]}
        >
          <Select placeholder="选择工作流分类">
            {categoryOptions.map(option => (
              <Option key={option.value} value={option.value}>
                <Space>
                  <span>{option.icon}</span>
                  <span>{option.label}</span>
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    {option.description}
                  </Text>
                </Space>
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="标签">
          <div>
            <Space wrap>
              {tags.map(tag => (
                <Tag
                  key={tag}
                  closable
                  onClose={() => removeTag(tag)}
                >
                  {tag}
                </Tag>
              ))}
            </Space>
            <div style={{ marginTop: 8 }}>
              <Input
                value={inputTag}
                onChange={(e) => setInputTag(e.target.value)}
                onPressEnter={addTag}
                placeholder="输入标签后按回车添加"
                style={{ width: '200px' }}
                suffix={
                  <Button
                    type="text"
                    size="small"
                    icon={<TagOutlined />}
                    onClick={addTag}
                    disabled={!inputTag || tags.includes(inputTag)}
                  />
                }
              />
            </div>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              添加相关标签帮助用户更好地发现您的工作流
            </Text>
          </div>
        </Form.Item>

        <Form.Item
          name="is_free"
          label="定价"
          valuePropName="checked"
        >
          <Switch
            checkedChildren="免费"
            unCheckedChildren="付费"
          />
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prevValues, currentValues) =>
            prevValues.is_free !== currentValues.is_free
          }
        >
          {({ getFieldValue }) =>
            !getFieldValue('is_free') ? (
              <Form.Item
                name="price"
                label="价格"
                rules={[
                  { required: true, message: '请设置价格' },
                  { type: 'number', min: 0.01, message: '价格必须大于0' }
                ]}
              >
                <InputNumber
                  min={0.01}
                  step={0.01}
                  precision={2}
                  style={{ width: '100%' }}
                  prefix={<DollarOutlined />}
                  placeholder="设置工作流价格"
                />
              </Form.Item>
            ) : null
          }
        </Form.Item>

        <div style={{
          background: '#f6f8fa',
          padding: '12px',
          borderRadius: '6px',
          marginBottom: '16px'
        }}>
          <Space>
            <InfoCircleOutlined style={{ color: '#1890ff' }} />
            <Text type="secondary" style={{ fontSize: '12px' }}>
              发布后的工作流将经过审核才能在商店中显示。您可以随时在"我的发布"中管理已发布的工作流。
            </Text>
          </Space>
        </div>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={loading}>
              发布到商店
            </Button>
            <Button onClick={handleCancel}>
              取消
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default PublishWorkflowModal;