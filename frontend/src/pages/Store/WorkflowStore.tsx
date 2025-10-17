import React, { useState, useEffect } from 'react';
import {
  Card,
  Row,
  Col,
  Input,
  Select,
  Button,
  Tag,
  Rate,
  Pagination,
  Spin,
  Empty,
  message,
  Modal,
  Typography,
  Space,
  Divider
} from 'antd';
import {
  SearchOutlined,
  EyeOutlined,
  DownloadOutlined,
  UserOutlined,
  StarOutlined,
  AppstoreOutlined,
  FireOutlined,
  FilterOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { storeAPI } from '../../services/storeAPI';
import type {
  WorkflowStoreResponse,
  WorkflowStoreQuery,
  StoreCategory
} from '../../types/store';

const { Search } = Input;
const { Option } = Select;
const { Title, Text, Paragraph } = Typography;

// 分类选项
const categoryOptions = [
  { value: 'automation', label: '自动化', icon: '🤖' },
  { value: 'data_processing', label: '数据处理', icon: '📊' },
  { value: 'ai_ml', label: 'AI/机器学习', icon: '🧠' },
  { value: 'business', label: '商业流程', icon: '💼' },
  { value: 'integration', label: '系统集成', icon: '🔗' },
  { value: 'template', label: '模板', icon: '📋' },
  { value: 'other', label: '其他', icon: '📦' }
];

interface WorkflowStoreProps {}

const WorkflowStore: React.FC<WorkflowStoreProps> = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [workflows, setWorkflows] = useState<WorkflowStoreResponse[]>([]);
  const [featuredWorkflows, setFeaturedWorkflows] = useState<WorkflowStoreResponse[]>([]);
  const [popularWorkflows, setPopularWorkflows] = useState<WorkflowStoreResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(12);

  // 搜索和筛选状态
  const [searchParams, setSearchParams] = useState<WorkflowStoreQuery>({
    page: 1,
    page_size: 12,
    sort_by: 'created_at',
    sort_order: 'desc'
  });

  // 初始化数据
  useEffect(() => {
    loadFeaturedWorkflows();
    loadPopularWorkflows();
    searchWorkflows();
  }, []);

  // 搜索工作流
  const searchWorkflows = async (params?: Partial<WorkflowStoreQuery>) => {
    setLoading(true);
    try {
      const queryParams = { ...searchParams, ...params };
      console.log('🔍 开始搜索工作流:', queryParams);
      const response = await storeAPI.searchWorkflows(queryParams);
      console.log('✅ 搜索工作流成功:', response);

      if (!response) {
        console.error('❌ API返回的response为空');
        setWorkflows([]);
        setTotal(0);
        setCurrentPage(1);
        return;
      }

      setWorkflows(response.items || []);
      setTotal(response.total || 0);
      setCurrentPage(response.page || 1);
    } catch (error: any) {
      console.error('❌ 搜索工作流失败:', error);
      console.error('错误详情:', error.response?.data || error.message);
      message.error(`搜索工作流失败: ${error.response?.data?.detail || error.message || '未知错误'}`);
    } finally {
      setLoading(false);
    }
  };

  // 加载推荐工作流
  const loadFeaturedWorkflows = async () => {
    try {
      const workflows = await storeAPI.getFeaturedWorkflows(6);
      setFeaturedWorkflows(workflows);
    } catch (error) {
      console.error('加载推荐工作流失败:', error);
    }
  };

  // 加载热门工作流
  const loadPopularWorkflows = async () => {
    try {
      const workflows = await storeAPI.getPopularWorkflows(6);
      setPopularWorkflows(workflows);
    } catch (error) {
      console.error('加载热门工作流失败:', error);
    }
  };

  // 处理搜索
  const handleSearch = (keyword: string) => {
    const newParams = { ...searchParams, keyword, page: 1 };
    setSearchParams(newParams);
    searchWorkflows(newParams);
  };

  // 处理分类筛选
  const handleCategoryFilter = (category: StoreCategory | undefined) => {
    const newParams = { ...searchParams, category, page: 1 };
    setSearchParams(newParams);
    searchWorkflows(newParams);
  };

  // 处理排序
  const handleSortChange = (sortBy: string) => {
    const newParams = { ...searchParams, sort_by: sortBy, page: 1 };
    setSearchParams(newParams);
    searchWorkflows(newParams);
  };

  // 处理分页
  const handlePageChange = (page: number) => {
    const newParams = { ...searchParams, page };
    setSearchParams(newParams);
    searchWorkflows(newParams);
  };

  // 查看工作流详情
  const handleViewWorkflow = (storeId: string) => {
    navigate(`/store/workflow/${storeId}`);
  };

  // 获取分类图标
  const getCategoryIcon = (category: string) => {
    const option = categoryOptions.find(opt => opt.value === category);
    return option?.icon || '📦';
  };

  // 获取分类标签
  const getCategoryLabel = (category: string) => {
    const option = categoryOptions.find(opt => opt.value === category);
    return option?.label || category;
  };

  // 渲染工作流卡片
  const renderWorkflowCard = (workflow: WorkflowStoreResponse) => (
    <Card
      key={workflow.store_id}
      hoverable
      onClick={() => handleViewWorkflow(workflow.store_id.toString())}
      cover={
        <div style={{
          height: 120,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '2em'
        }}>
          {getCategoryIcon(workflow.category)}
        </div>
      }
      actions={[
        <Space key="stats">
          <EyeOutlined /> {workflow.views}
        </Space>,
        <Space key="downloads">
          <DownloadOutlined /> {workflow.downloads}
        </Space>,
        <Space key="rating">
          <StarOutlined /> {workflow.rating.toFixed(1)}
        </Space>
      ]}
    >
      <Card.Meta
        title={
          <Space>
            {workflow.title}
            {workflow.is_featured && <Tag color="gold">推荐</Tag>}
            {workflow.is_free && <Tag color="green">免费</Tag>}
          </Space>
        }
        description={
          <div>
            <Paragraph ellipsis={{ rows: 2 }}>
              {workflow.description || '暂无描述'}
            </Paragraph>
            <div style={{ marginTop: 8 }}>
              <Tag color="blue">{getCategoryLabel(workflow.category)}</Tag>
              {workflow.tags.slice(0, 2).map(tag => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </div>
            <div style={{ marginTop: 8, color: '#666' }}>
              <UserOutlined /> {workflow.author_name}
            </div>
            <Rate disabled value={workflow.rating} style={{ fontSize: 12 }} />
            <Text type="secondary" style={{ marginLeft: 8 }}>
              ({workflow.rating_count})
            </Text>
          </div>
        }
      />
    </Card>
  );

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题 */}
      <Title level={2}>
        <AppstoreOutlined /> 工作流商店
      </Title>
      <Paragraph type="secondary">
        发现和分享优秀的工作流，提升工作效率
      </Paragraph>

      {/* 推荐工作流 */}
      {featuredWorkflows && featuredWorkflows.length > 0 && (
        <div style={{ marginBottom: 32 }}>
          <Title level={3}>
            <StarOutlined style={{ color: '#faad14' }} /> 推荐工作流
          </Title>
          <Row gutter={[16, 16]}>
            {featuredWorkflows.map(workflow => (
              <Col key={workflow.store_id} xs={24} sm={12} lg={8} xl={6}>
                {renderWorkflowCard(workflow)}
              </Col>
            ))}
          </Row>
        </div>
      )}

      {/* 热门工作流 */}
      {popularWorkflows && popularWorkflows.length > 0 && (
        <div style={{ marginBottom: 32 }}>
          <Title level={3}>
            <FireOutlined style={{ color: '#ff4d4f' }} /> 热门工作流
          </Title>
          <Row gutter={[16, 16]}>
            {popularWorkflows.map(workflow => (
              <Col key={workflow.store_id} xs={24} sm={12} lg={8} xl={6}>
                {renderWorkflowCard(workflow)}
              </Col>
            ))}
          </Row>
        </div>
      )}

      <Divider />

      {/* 搜索和筛选 */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col flex="auto">
            <Search
              placeholder="搜索工作流..."
              allowClear
              enterButton={<SearchOutlined />}
              size="large"
              onSearch={handleSearch}
            />
          </Col>
          <Col>
            <Select
              placeholder="选择分类"
              allowClear
              style={{ width: 140 }}
              value={searchParams.category}
              onChange={handleCategoryFilter}
            >
              {categoryOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  {option.icon} {option.label}
                </Option>
              ))}
            </Select>
          </Col>
          <Col>
            <Select
              value={searchParams.sort_by}
              style={{ width: 120 }}
              onChange={handleSortChange}
            >
              <Option value="created_at">最新</Option>
              <Option value="downloads">下载量</Option>
              <Option value="rating">评分</Option>
              <Option value="views">浏览量</Option>
            </Select>
          </Col>
        </Row>
      </Card>

      {/* 工作流列表 */}
      <Spin spinning={loading}>
        {workflows && workflows.length > 0 ? (
          <>
            <Row gutter={[16, 16]}>
              {workflows.map(workflow => (
                <Col key={workflow.store_id} xs={24} sm={12} lg={8} xl={6}>
                  {renderWorkflowCard(workflow)}
                </Col>
              ))}
            </Row>

            <div style={{ textAlign: 'center', marginTop: 32 }}>
              <Pagination
                current={currentPage}
                pageSize={pageSize}
                total={total}
                showSizeChanger={false}
                showQuickJumper
                showTotal={(total, range) =>
                  `第 ${range[0]}-${range[1]} 项，共 ${total} 项`
                }
                onChange={handlePageChange}
              />
            </div>
          </>
        ) : (
          <Empty
            description="暂无工作流"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
      </Spin>
    </div>
  );
};

export default WorkflowStore;