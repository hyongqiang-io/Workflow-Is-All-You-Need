import React, { useState, useEffect } from 'react';
import { 
  Card, 
  List, 
  Badge, 
  Button, 
  Space, 
  Typography, 
  message,
  Modal,
  Progress,
  Tag,
  Tooltip,
  Empty,
  Row,
  Col,
  Statistic
} from 'antd';
import { 
  EyeOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ExclamationCircleOutlined,
  UserOutlined,
  ClockCircleOutlined,
  MergeOutlined,
  FolderOpenOutlined
} from '@ant-design/icons';
import { taskSubdivisionApi } from '../services/api';

const { Title, Text } = Typography;
const { confirm } = Modal;

interface SubdivisionPreviewProps {
  workflowBaseId: string;
  onAdoptSubdivision?: (subdivisionId: string) => void;
}

interface SubdivisionItem {
  subdivision_id: string;
  subdivision_name: string;
  subdivider_name: string;
  status: string;
  sub_workflow_name: string;
  total_nodes: number;
  completed_nodes: number;
  success_rate?: number;
  created_at: string;
  completed_at?: string;
}

interface WorkflowSubdivisions {
  workflow_base_id: string;
  workflow_name: string;
  subdivisions: SubdivisionItem[];
  total_count: number;
  completed_count: number;
}

const getStatusConfig = (status: string) => {
  switch (status) {
    case 'completed':
      return { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' };
    case 'executing':
      return { color: 'processing', icon: <LoadingOutlined />, text: '执行中' };
    case 'failed':
      return { color: 'error', icon: <ExclamationCircleOutlined />, text: '失败' };
    case 'created':
    default:
      return { color: 'default', icon: <ClockCircleOutlined />, text: '已创建' };
  }
};

const WorkflowSubdivisionPreview: React.FC<SubdivisionPreviewProps> = ({
  workflowBaseId,
  onAdoptSubdivision
}) => {
  const [loading, setLoading] = useState(false);
  const [subdivisions, setSubdivisions] = useState<WorkflowSubdivisions | null>(null);

  const loadSubdivisions = async () => {
    try {
      setLoading(true);
      console.log('🔄 加载工作流细分预览:', workflowBaseId);
      
      const response = await taskSubdivisionApi.getWorkflowSubdivisions(workflowBaseId);
      
      if (response?.data?.success && response?.data?.data) {
        setSubdivisions(response.data.data);
        console.log('✅ 细分预览加载成功:', response.data.data);
      } else if (response?.data) {
        // 如果response.data直接是数据
        setSubdivisions(response.data);
        console.log('✅ 细分预览加载成功:', response.data);
      } else {
        console.warn('⚠️ 细分预览响应格式异常:', response);
        setSubdivisions(null);
      }
    } catch (error: any) {
      console.error('❌ 加载细分预览失败:', error);
      if (error.message?.includes('不存在')) {
        setSubdivisions({
          workflow_base_id: workflowBaseId,
          workflow_name: '未知工作流',
          subdivisions: [],
          total_count: 0,
          completed_count: 0
        });
      } else {
        message.error('加载细分预览失败');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (workflowBaseId) {
      loadSubdivisions();
    }
  }, [workflowBaseId]);

  const handleAdoptClick = (subdivision: SubdivisionItem) => {
    if (subdivision.status !== 'completed') {
      message.warning('只能采纳已完成的细分');
      return;
    }

    confirm({
      title: '确认采纳子工作流',
      icon: <MergeOutlined />,
      content: (
        <div>
          <p>您确定要将 <strong>{subdivision.subdivision_name}</strong> 采纳到原工作流中吗？</p>
          <p><Text type="secondary">
            细分者: {subdivision.subdivider_name} | 
            节点数: {subdivision.total_nodes} | 
            成功率: {subdivision.success_rate ? `${subdivision.success_rate.toFixed(1)}%` : 'N/A'}
          </Text></p>
          <p><Text type="warning">注意：采纳后将在原工作流中添加相应的节点。</Text></p>
        </div>
      ),
      okText: '确认采纳',
      cancelText: '取消',
      onOk: () => {
        if (onAdoptSubdivision) {
          onAdoptSubdivision(subdivision.subdivision_id);
        }
      }
    });
  };

  const renderSubdivisionItem = (item: SubdivisionItem) => {
    const statusConfig = getStatusConfig(item.status);
    const progressPercent = item.total_nodes > 0 ? 
      Math.round((item.completed_nodes / item.total_nodes) * 100) : 0;

    return (
      <List.Item
        key={item.subdivision_id}
        actions={[
          <Tooltip title="查看详情">
            <Button 
              type="text" 
              icon={<EyeOutlined />} 
              onClick={() => {
                // TODO: 实现查看详情功能
                message.info('细分详情功能开发中');
              }}
            />
          </Tooltip>,
          item.status === 'completed' && (
            <Tooltip title="采纳到原工作流">
              <Button 
                type="primary" 
                size="small"
                icon={<MergeOutlined />}
                onClick={() => handleAdoptClick(item)}
              >
                采纳
              </Button>
            </Tooltip>
          )
        ].filter(Boolean)}
      >
        <List.Item.Meta
          avatar={
            <Badge 
              status={statusConfig.color as any} 
              dot 
              style={{ marginTop: 8 }}
            />
          }
          title={
            <Space>
              <Text strong>{item.subdivision_name}</Text>
              <Tag color={statusConfig.color} icon={statusConfig.icon}>
                {statusConfig.text}
              </Tag>
            </Space>
          }
          description={
            <div>
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Space>
                  <UserOutlined />
                  <Text type="secondary">细分者: {item.subdivider_name}</Text>
                  <ClockCircleOutlined />
                  <Text type="secondary">
                    创建于: {new Date(item.created_at).toLocaleDateString()}
                  </Text>
                </Space>
                
                <Space>
                  <Text type="secondary">子工作流: {item.sub_workflow_name}</Text>
                  <Text type="secondary">•</Text>
                  <Text type="secondary">节点数: {item.total_nodes}</Text>
                  <Text type="secondary">•</Text>
                  <Text type="secondary">已完成: {item.completed_nodes}</Text>
                </Space>

                {item.status === 'executing' || item.status === 'completed' ? (
                  <Progress 
                    percent={progressPercent} 
                    size="small" 
                    status={item.status === 'completed' ? 'success' : 'active'}
                    format={(percent) => `${percent}% (${item.completed_nodes}/${item.total_nodes})`}
                  />
                ) : null}

                {item.success_rate !== undefined && item.status === 'completed' && (
                  <Space>
                    <Text type="secondary">成功率:</Text>
                    <Tag color={item.success_rate >= 80 ? 'green' : item.success_rate >= 60 ? 'orange' : 'red'}>
                      {item.success_rate.toFixed(1)}%
                    </Tag>
                  </Space>
                )}
              </Space>
            </div>
          }
        />
      </List.Item>
    );
  };

  if (loading) {
    return (
      <Card loading={loading}>
        <div style={{ textAlign: 'center', padding: 40 }}>
          <LoadingOutlined style={{ fontSize: 24 }} />
          <p>加载细分预览...</p>
        </div>
      </Card>
    );
  }

  if (!subdivisions) {
    return (
      <Card>
        <Empty 
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="加载细分预览失败"
        />
      </Card>
    );
  }

  return (
    <Card 
      title={
        <Space>
          <BranchesOutlined />
          <span>工作流细分预览</span>
          <Text type="secondary">({subdivisions.workflow_name})</Text>
        </Space>
      }
      extra={
        <Button 
          type="text" 
          icon={<FolderOpenOutlined />}
          onClick={loadSubdivisions}
        >
          刷新
        </Button>
      }
    >
      {subdivisions.total_count > 0 && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Statistic 
              title="总细分数" 
              value={subdivisions.total_count} 
              prefix={<BranchesOutlined />}
            />
          </Col>
          <Col span={8}>
            <Statistic 
              title="已完成" 
              value={subdivisions.completed_count} 
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Col>
          <Col span={8}>
            <Statistic 
              title="完成率" 
              value={subdivisions.total_count > 0 ? 
                Math.round((subdivisions.completed_count / subdivisions.total_count) * 100) : 0
              } 
              suffix="%" 
              prefix={<Progress type="circle" size={16} />}
            />
          </Col>
        </Row>
      )}

      {subdivisions.subdivisions.length > 0 ? (
        <List
          dataSource={subdivisions.subdivisions}
          renderItem={renderSubdivisionItem}
          pagination={subdivisions.subdivisions.length > 10 ? {
            pageSize: 10,
            showSizeChanger: false,
            showQuickJumper: true
          } : false}
        />
      ) : (
        <Empty 
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Space direction="vertical">
              <Text>该工作流暂无相关细分</Text>
              <Text type="secondary">当执行者对任务进行细分时，您可以在这里查看和采纳</Text>
            </Space>
          }
        />
      )}
    </Card>
  );
};

export default WorkflowSubdivisionPreview;