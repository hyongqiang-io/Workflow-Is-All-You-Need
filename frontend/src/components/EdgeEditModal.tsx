import React, { useState, useEffect } from 'react';
import { Modal, Form, Select, Input, Card, Row, Col, message } from 'antd';
import { Edge } from 'reactflow';

const { TextArea } = Input;
const { Option } = Select;

interface EdgeEditModalProps {
  visible: boolean;
  edge: Edge | null;
  onSave: (edgeData: any) => Promise<void>;
  onCancel: () => void;
}

const EdgeEditModal: React.FC<EdgeEditModalProps> = ({
  visible,
  edge,
  onSave,
  onCancel,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  // 实时监听表单中的connection_type值变化
  const watchedConnectionType = Form.useWatch('connection_type', form);

  // 获取边数据中的connection_type作为备选
  const edgeConnectionType = edge?.data?.connection_type;

  // 根据当前表单中的connection_type值决定是否显示条件描述
  // 如果表单中还没有值，则使用边数据中的值
  const currentConnectionType = watchedConnectionType || edgeConnectionType || 'normal';
  const shouldShowDescription = currentConnectionType === 'conditional';

  // 调试信息
  console.log('EdgeEditModal render:', {
    visible,
    watchedConnectionType,
    edgeConnectionType,
    currentConnectionType,
    shouldShowDescription,
    edgeData: edge?.data
  });

  useEffect(() => {
    if (visible && edge) {
      // 解析边的数据
      const edgeData = edge.data || {};
      const connectionType = edgeData.connection_type || 'normal';
      const conditionConfig = edgeData.condition_config || {};

      // 设置表单初始值 - 使用延时确保Form完全渲染
      const formValues = {
        connection_type: connectionType,
        description: conditionConfig.description || '',
      };

      // 立即设置一次
      form.setFieldsValue(formValues);

      // 延时再设置一次，确保Form字段已渲染
      setTimeout(() => {
        form.setFieldsValue(formValues);
      }, 200);

    } else if (visible) {
      // 新边或没有边数据时的默认值
      const defaultValues = {
        connection_type: 'normal',
        description: '',
      };

      setTimeout(() => {
        form.setFieldsValue(defaultValues);
      }, 200);
    }

    // 当模态框关闭时重置状态
    if (!visible) {
      form.resetFields();
    }
  }, [visible, edge, form]);

  const handleSave = async () => {
    try {
      setLoading(true);
      const values = await form.validateFields();

      // 构建条件配置
      let conditionConfig = null;
      if (values.connection_type === 'conditional') {
        conditionConfig = {
          description: values.description || '',
        };
      }

      // 构建边数据
      const edgeData = {
        id: edge?.id,
        source: edge?.source,
        target: edge?.target,
        connection_type: values.connection_type,
        condition_config: conditionConfig,
      };

      await onSave(edgeData);
      message.success('边配置保存成功');
      onCancel();
    } catch (error) {
      console.error('保存边配置失败:', error);
      message.error('保存边配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleConnectionTypeChange = (value: string) => {
    if (value === 'normal') {
      // 清除条件描述
      form.setFieldsValue({
        description: '',
      });
    }
  };

  if (!edge) return null;

  return (
    <Modal
      title="编辑连接"
      open={visible}
      onOk={handleSave}
      onCancel={onCancel}
      confirmLoading={loading}
      width={600}
      forceRender
    >
      <Form
        form={form}
        layout="vertical"
        preserve={false}
      >
        <Card size="small" title="连接设置" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="源节点">
                <Input value={edge.source} disabled />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="目标节点">
                <Input value={edge.target} disabled />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="connection_type"
            label="连接类型"
            rules={[{ required: true, message: '请选择连接类型' }]}
          >
            <Select onChange={handleConnectionTypeChange}>
              <Option value="normal">固定边（无条件）</Option>
              <Option value="conditional">条件边（需要满足条件）</Option>
            </Select>
          </Form.Item>

          {shouldShowDescription && (
            <Form.Item
              name="description"
              label="条件描述"
              tooltip="简要描述这个条件的作用"
              rules={[{ required: true, message: '请输入条件描述' }]}
            >
              <TextArea
                rows={3}
                placeholder="例如: 当任务执行成功时..."
              />
            </Form.Item>
          )}
        </Card>
      </Form>
    </Modal>
  );
};

export default EdgeEditModal;