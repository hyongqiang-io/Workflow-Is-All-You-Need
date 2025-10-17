import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Tag,
  Rate,
  Spin,
  message,
  Modal,
  Typography,
  Space,
  Divider,
  Avatar,
  List,
  Input,
  Form,
  Tooltip
} from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  EyeOutlined,
  UserOutlined,
  StarOutlined,
  MessageOutlined,
  CalendarOutlined,
  AppstoreOutlined,
  TagOutlined,
  NodeIndexOutlined,
  BranchesOutlined,
  ExperimentOutlined
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { storeAPI } from '../../services/storeAPI';
import WorkflowPreview from '../../components/WorkflowPreview';
import type {
  WorkflowStoreDetail,
  WorkflowStoreRating,
  WorkflowStoreRatingCreate,
  WorkflowStoreImportRequest
} from '../../types/store';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface WorkflowStoreDetailProps {}

const WorkflowStoreDetailPage: React.FC<WorkflowStoreDetailProps> = () => {
  const { storeId } = useParams<{ storeId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [workflow, setWorkflow] = useState<WorkflowStoreDetail | null>(null);
  const [ratings, setRatings] = useState<WorkflowStoreRating[]>([]);
  const [ratingsLoading, setRatingsLoading] = useState(false);
  const [viewIncremented, setViewIncremented] = useState(false);

  // 评分模态框
  const [ratingModalVisible, setRatingModalVisible] = useState(false);
  const [ratingForm] = Form.useForm();

  // 导入模态框
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importForm] = Form.useForm();

  useEffect(() => {
    if (storeId) {
      loadWorkflowDetail();
      loadRatings();

      // 只在首次加载时增加浏览数
      if (!viewIncremented) {
        incrementView();
        setViewIncremented(true);
      }
    }
  }, [storeId]);

  // 增加浏览次数（单独调用）
  const incrementView = async () => {
    try {
      await storeAPI.incrementWorkflowView(storeId!);
    } catch (error: any) {
      // 404错误说明工作流不存在，不需要特别处理
      if (error?.response?.status !== 404) {
        console.error('增加浏览次数失败:', error);
      }
    }
  };

  // 加载工作流详情
  const loadWorkflowDetail = async () => {
    setLoading(true);
    try {
      const detail = await storeAPI.getWorkflowDetail(storeId!);
      setWorkflow(detail);
    } catch (error) {
      message.error('加载工作流详情失败');
      navigate('/store');
    } finally {
      setLoading(false);
    }
  };

  // 加载评分
  const loadRatings = async () => {
    setRatingsLoading(true);
    try {
      const ratingList = await storeAPI.getWorkflowRatings(storeId!, 50, 0);
      setRatings(ratingList);
    } catch (error) {
      console.error('加载评分失败:', error);
    } finally {
      setRatingsLoading(false);
    }
  };

  // 导入工作流
  const handleImport = async (values: any) => {
    setImporting(true);
    try {
      const importRequest: WorkflowStoreImportRequest = {
        store_id: workflow!.store_id,
        import_name: values.import_name,
        import_description: values.import_description
      };

      const result = await storeAPI.importWorkflow(importRequest);

      if (result.success) {
        message.success('工作流导入成功');
        setImportModalVisible(false);
        importForm.resetFields();

        // 可以跳转到工作流管理页面
        if (result.workflow_base_id) {
          navigate(`/workflow?id=${result.workflow_base_id}`);
        }
      } else {
        message.error(result.message || '导入失败');
      }
    } catch (error) {
      message.error('导入工作流失败');
    } finally {
      setImporting(false);
    }
  };

  // 提交评分
  const handleRating = async (values: any) => {
    try {
      const ratingData: WorkflowStoreRatingCreate = {
        store_id: workflow!.store_id,
        rating: values.rating,
        comment: values.comment
      };

      await storeAPI.createRating(storeId!, ratingData);
      message.success('评分提交成功');
      setRatingModalVisible(false);
      ratingForm.resetFields();
      loadRatings(); // 重新加载评分
    } catch (error) {
      message.error('提交评分失败');
    }
  };

  // 获取分类标签颜色
  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      automation: 'blue',
      data_processing: 'green',
      ai_ml: 'purple',
      business: 'orange',
      integration: 'cyan',
      template: 'geekblue',
      other: 'default'
    };
    return colors[category] || 'default';
  };

  if (loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!workflow) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Text>工作流不存在</Text>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* 返回按钮 */}
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/store')}
        style={{ marginBottom: 16 }}
      >
        返回商店
      </Button>

      <Row gutter={24}>
        {/* 左侧主要信息 */}
        <Col xs={24} lg={16}>
          <Card>
            <div style={{ marginBottom: 16 }}>
              <Title level={2}>{workflow.title}</Title>
              <Space>
                <Tag color={getCategoryColor(workflow.category)}>
                  {workflow.category}
                </Tag>
                {workflow.is_featured && <Tag color="gold">推荐</Tag>}
                {workflow.is_free && <Tag color="green">免费</Tag>}
                {!workflow.is_free && workflow.price && (
                  <Tag color="red">¥{workflow.price}</Tag>
                )}
              </Space>
            </div>

            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col>
                <Space>
                  <EyeOutlined />
                  <Text>{workflow.views} 浏览</Text>
                </Space>
              </Col>
              <Col>
                <Space>
                  <DownloadOutlined />
                  <Text>{workflow.downloads} 下载</Text>
                </Space>
              </Col>
              <Col>
                <Space>
                  <StarOutlined />
                  <Rate disabled value={workflow.rating} style={{ fontSize: 14 }} />
                  <Text>({workflow.rating_count})</Text>
                </Space>
              </Col>
            </Row>

            <Paragraph>{workflow.description}</Paragraph>

            {/* 工作流结构信息 */}
            {workflow.workflow_info && (
              <Card type="inner" title="工作流结构" style={{ marginBottom: 16 }}>
                <Row gutter={16}>
                  <Col span={12}>
                    <Space>
                      <NodeIndexOutlined />
                      <Text>{workflow.workflow_info.nodes_count} 个节点</Text>
                    </Space>
                  </Col>
                  <Col span={12}>
                    <Space>
                      <BranchesOutlined />
                      <Text>{workflow.workflow_info.connections_count} 个连接</Text>
                    </Space>
                  </Col>
                </Row>
              </Card>
            )}

            {/* 工作流预览 */}
            {workflow.workflow_export_data && (
              <Card
                type="inner"
                title={
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <ExperimentOutlined />
                    工作流预览
                  </div>
                }
                style={{ marginBottom: 16 }}
              >
                <WorkflowPreview
                  workflowData={workflow.workflow_export_data}
                  height="500px"
                  showStats={false}
                />
              </Card>
            )}

            {/* 标签 */}
            {workflow.tags && workflow.tags.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong>
                  <TagOutlined /> 标签：
                </Text>
                <div style={{ marginTop: 8 }}>
                  {workflow.tags.map(tag => (
                    <Tag key={tag}>{tag}</Tag>
                  ))}
                </div>
              </div>
            )}

            {/* 操作按钮 */}
            <div style={{ marginTop: 24 }}>
              <Space>
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  size="large"
                  onClick={() => setImportModalVisible(true)}
                >
                  导入工作流
                </Button>
                <Button
                  icon={<StarOutlined />}
                  onClick={() => setRatingModalVisible(true)}
                >
                  评分
                </Button>
              </Space>
            </div>
          </Card>

          {/* 评分和评论 */}
          <Card title="用户评价" style={{ marginTop: 24 }}>
            <Spin spinning={ratingsLoading}>
              {ratings && ratings.length > 0 ? (
                <List
                  dataSource={ratings}
                  renderItem={(rating) => (
                    <List.Item>
                      <List.Item.Meta
                        avatar={<Avatar icon={<UserOutlined />} />}
                        title={
                          <Space>
                            <Text strong>{rating.user_name}</Text>
                            <Rate disabled value={rating.rating} style={{ fontSize: 12 }} />
                            <Text type="secondary">{rating.created_at}</Text>
                          </Space>
                        }
                        description={rating.comment}
                      />
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary">暂无评价</Text>
              )}
            </Spin>
          </Card>
        </Col>

        {/* 右侧信息栏 */}
        <Col xs={24} lg={8}>
          <Card title="作者信息">
            <Space direction="vertical">
              <Space>
                <Avatar icon={<UserOutlined />} />
                <Text strong>{workflow.author_name}</Text>
              </Space>
              <Space>
                <CalendarOutlined />
                <Text type="secondary">发布于 {workflow.published_at}</Text>
              </Space>
              <Space>
                <AppstoreOutlined />
                <Text type="secondary">版本 {workflow.version}</Text>
              </Space>
            </Space>
          </Card>

          {workflow.changelog && (
            <Card title="更新日志" style={{ marginTop: 16 }}>
              <Paragraph>{workflow.changelog}</Paragraph>
            </Card>
          )}
        </Col>
      </Row>

      {/* 导入模态框 */}
      <Modal
        title="导入工作流"
        open={importModalVisible}
        onCancel={() => setImportModalVisible(false)}
        footer={null}
      >
        <Form form={importForm} onFinish={handleImport} layout="vertical">
          <Form.Item
            name="import_name"
            label="工作流名称"
            initialValue={workflow.title}
            rules={[{ required: true, message: '请输入工作流名称' }]}
          >
            <Input placeholder="输入导入后的工作流名称" />
          </Form.Item>
          <Form.Item
            name="import_description"
            label="工作流描述"
            initialValue={workflow.description}
          >
            <TextArea rows={3} placeholder="输入工作流描述" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={importing}>
                确认导入
              </Button>
              <Button onClick={() => setImportModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 评分模态框 */}
      <Modal
        title="工作流评分"
        open={ratingModalVisible}
        onCancel={() => setRatingModalVisible(false)}
        footer={null}
      >
        <Form form={ratingForm} onFinish={handleRating} layout="vertical">
          <Form.Item
            name="rating"
            label="评分"
            rules={[{ required: true, message: '请选择评分' }]}
          >
            <Rate />
          </Form.Item>
          <Form.Item
            name="comment"
            label="评论"
            rules={[{ required: false }]}
          >
            <TextArea rows={4} placeholder="分享您的使用体验..." />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                提交评分
              </Button>
              <Button onClick={() => setRatingModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default WorkflowStoreDetailPage;