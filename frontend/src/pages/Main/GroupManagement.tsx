/**
 * 群组管理页面
 * Group Management Page
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Card, List, Avatar, Tag, Input, Select, Row, Col, Button, message, Statistic, Typography, Empty,
  Tabs, Table, Modal, Form, Space, Descriptions, Divider, Tooltip, Switch, Badge
} from 'antd';
import {
  TeamOutlined,
  UserOutlined,
  SearchOutlined,
  FilterOutlined,
  ReloadOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  UserAddOutlined,
  UserDeleteOutlined,
  SettingOutlined,
  CrownOutlined,
  GroupOutlined,
  GlobalOutlined,
  LockOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { groupAPI, processorGroupAPI } from '../../services/groupAPI';
import { useAuthStore } from '../../stores/authStore';
import { Group, GroupCreate, GroupUpdate, GroupMember, GroupQuery, GroupedProcessors } from '../../types/group';

const { Search } = Input;
const { Option } = Select;
const { Title, Text } = Typography;
const { TextArea } = Input;

const GroupManagement: React.FC = () => {
  const { user: currentUser } = useAuthStore();
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupMembers, setGroupMembers] = useState<{ [key: string]: GroupMember[] }>({});
  const [groupProcessors, setGroupProcessors] = useState<{ [key: string]: any[] }>({});
  const [groupedProcessors, setGroupedProcessors] = useState<GroupedProcessors>({});
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [visibilityFilter, setVisibilityFilter] = useState<'all' | 'public' | 'private'>('all');
  const [membershipFilter, setMembershipFilter] = useState<'all' | 'my' | 'joined'>('all');
  const [activeTab, setActiveTab] = useState('overview');

  // Modal状态
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [membersModalVisible, setMembersModalVisible] = useState(false);
  const [processorsModalVisible, setProcessorsModalVisible] = useState(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);

  // 选中的群组和表单
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [groupToDelete, setGroupToDelete] = useState<Group | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  // 过滤后的群组列表
  const filteredGroups = useMemo(() => {
    let filtered = groups;

    // 按可见性过滤
    if (visibilityFilter !== 'all') {
      filtered = filtered.filter(group =>
        visibilityFilter === 'public' ? group.is_public : !group.is_public
      );
    }

    // 按成员关系过滤
    if (membershipFilter !== 'all') {
      if (membershipFilter === 'my') {
        filtered = filtered.filter(group => group.is_creator);
      } else if (membershipFilter === 'joined') {
        filtered = filtered.filter(group => group.is_member && !group.is_creator);
      }
    }

    // 按搜索文本过滤
    if (searchText) {
      filtered = filtered.filter(group =>
        group.group_name.toLowerCase().includes(searchText.toLowerCase()) ||
        (group.description && group.description.toLowerCase().includes(searchText.toLowerCase()))
      );
    }

    return filtered;
  }, [groups, searchText, visibilityFilter, membershipFilter]);

  // 统计信息
  const stats = useMemo(() => ({
    total: groups.length,
    public: groups.filter(g => g.is_public).length,
    private: groups.filter(g => !g.is_public).length,
    my: groups.filter(g => g.is_creator).length,
    joined: groups.filter(g => g.is_member).length,
    totalMembers: groups.reduce((sum, g) => sum + g.member_count, 0)
  }), [groups]);

  // 加载群组列表
  const loadGroups = useCallback(async () => {
    setLoading(true);
    try {
      const response: any = await groupAPI.getGroups();
      if (response && response.success) {
        setGroups(response.data.groups || []);
      }
    } catch (error) {
      console.error('加载群组列表失败:', error);
      message.error('加载群组列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // 加载按群组分类的processor列表
  const loadGroupedProcessors = useCallback(async () => {
    try {
      const response: any = await processorGroupAPI.getProcessorsGrouped();
      if (response && response.success) {
        setGroupedProcessors(response.data || {});
      }
    } catch (error) {
      console.error('加载分组processor失败:', error);
    }
  }, []);

  // 加载群组成员
  const loadGroupMembers = useCallback(async (groupId: string) => {
    try {
      const response: any = await groupAPI.getGroupMembers(groupId);
      console.log('群组成员API响应:', response);

      // 后端直接返回成员数组，而不是包装格式
      const members = Array.isArray(response.data) ? response.data : (response.data?.members || []);

      setGroupMembers(prev => ({
        ...prev,
        [groupId]: members
      }));
    } catch (error) {
      console.error('加载群组成员失败:', error);
    }
  }, []);

  // 加载群组processors
  const loadGroupProcessors = useCallback(async (groupId: string) => {
    try {
      const response: any = await groupAPI.getGroupProcessors(groupId);
      console.log('群组processors API响应:', response);

      // 后端直接返回processors数组，而不是包装格式
      const processors = Array.isArray(response.data) ? response.data : (response.data?.processors || []);

      setGroupProcessors(prev => ({
        ...prev,
        [groupId]: processors
      }));
    } catch (error) {
      console.error('加载群组processors失败:', error);
    }
  }, []);

  // 初始化数据
  useEffect(() => {
    loadGroups();
    loadGroupedProcessors();
  }, [loadGroups, loadGroupedProcessors]);

  // 创建群组
  const handleCreateGroup = useCallback(() => {
    setCreateModalVisible(true);
    createForm.resetFields();
  }, [createForm]);

  const confirmCreateGroup = useCallback(async () => {
    try {
      console.log('开始创建群组 - 验证表单字段');
      const values = await createForm.validateFields();
      console.log('表单验证成功，群组数据:', values);

      console.log('调用群组API创建群组');
      const response: any = await groupAPI.createGroup(values);
      console.log('群组API响应:', response);

      if (response && response.success) {
        console.log('群组创建成功');
        message.success('群组创建成功');
        setCreateModalVisible(false);
        createForm.resetFields();
        loadGroups();
      } else {
        console.error('群组创建失败，后端返回错误:', response);
        message.error(response?.message || '创建群组失败');
      }
    } catch (error: any) {
      console.error('群组创建异常:', error);
      console.error('错误详情:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      });

      if (error.response?.data?.detail) {
        message.error(error.response.data.detail);
      } else {
        message.error(error.response?.data?.detail || '创建群组失败');
      }
    }
  }, [createForm, loadGroups]);

  // 编辑群组
  const handleEditGroup = useCallback((group: Group) => {
    setSelectedGroup(group);
    setEditModalVisible(true);
    editForm.setFieldsValue({
      group_name: group.group_name,
      description: group.description,
      is_public: group.is_public
    });
  }, [editForm]);

  const confirmEditGroup = useCallback(async () => {
    if (!selectedGroup) return;

    try {
      const values = await editForm.validateFields();
      const response: any = await groupAPI.updateGroup(selectedGroup.group_id, values);

      if (response && response.success) {
        message.success('群组更新成功');
        setEditModalVisible(false);
        setSelectedGroup(null);
        loadGroups();
      } else {
        message.error(response?.message || '更新群组失败');
      }
    } catch (error: any) {
      console.error('更新群组失败:', error);
      message.error(error.response?.data?.detail || '更新群组失败');
    }
  }, [selectedGroup, editForm, loadGroups]);

  // 查看群组详情
  const handleViewGroup = useCallback((group: Group) => {
    setSelectedGroup(group);
    setDetailModalVisible(true);
    loadGroupMembers(group.group_id);
    loadGroupProcessors(group.group_id);
  }, [loadGroupMembers, loadGroupProcessors]);

  // 查看群组成员
  const handleViewMembers = useCallback((group: Group) => {
    setSelectedGroup(group);
    setMembersModalVisible(true);
    loadGroupMembers(group.group_id);
  }, [loadGroupMembers]);

  // 查看群组processors
  const handleViewProcessors = useCallback((group: Group) => {
    setSelectedGroup(group);
    setProcessorsModalVisible(true);
    loadGroupProcessors(group.group_id);
  }, [loadGroupProcessors]);

  // 加入群组
  const handleJoinGroup = useCallback(async (group: Group) => {
    try {
      const response: any = await groupAPI.joinGroup(group.group_id);
      if (response && response.success) {
        message.success('成功加入群组');
        loadGroups();
      } else {
        message.error(response?.message || '加入群组失败');
      }
    } catch (error: any) {
      console.error('加入群组失败:', error);
      message.error(error.response?.data?.detail || '加入群组失败');
    }
  }, [loadGroups]);

  // 离开群组
  const handleLeaveGroup = useCallback(async (group: Group) => {
    try {
      const response: any = await groupAPI.leaveGroup(group.group_id);
      if (response && response.success) {
        message.success('成功离开群组');
        loadGroups();
      } else {
        message.error(response?.message || '离开群组失败');
      }
    } catch (error: any) {
      console.error('离开群组失败:', error);
      message.error(error.response?.data?.detail || '离开群组失败');
    }
  }, [loadGroups]);

  // 删除群组
  const handleDeleteGroup = useCallback((group: Group) => {
    setGroupToDelete(group);
    setDeleteModalVisible(true);
  }, []);

  const confirmDeleteGroup = useCallback(async () => {
    if (!groupToDelete) return;

    try {
      const response: any = await groupAPI.deleteGroup(groupToDelete.group_id);
      if (response && response.success) {
        message.success('群组删除成功');
        setDeleteModalVisible(false);
        setGroupToDelete(null);
        loadGroups();
      } else {
        message.error(response?.message || '删除群组失败');
      }
    } catch (error: any) {
      console.error('删除群组失败:', error);
      message.error(error.response?.data?.detail || '删除群组失败');
    }
  }, [groupToDelete, loadGroups]);

  // 工具函数
  const getGroupIcon = useCallback((group: Group) => {
    if (group.is_creator) return <CrownOutlined style={{ color: '#faad14' }} />;
    if (group.is_member) return <TeamOutlined style={{ color: '#52c41a' }} />;
    return <GroupOutlined style={{ color: '#1890ff' }} />;
  }, []);

  const getVisibilityIcon = useCallback((isPublic: boolean) => {
    return isPublic ? <GlobalOutlined style={{ color: '#52c41a' }} /> : <LockOutlined style={{ color: '#fa8c16' }} />;
  }, []);

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: '24px' }}>
        <Title level={2} style={{ marginBottom: '8px' }}>
          <TeamOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
          群组管理
        </Title>
        <Text type="secondary">创建和管理项目群组，组织团队协作</Text>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总群组"
              value={stats.total}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="我创建的"
              value={stats.my}
              prefix={<CrownOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="已加入的"
              value={stats.joined}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总成员数"
              value={stats.totalMembers}
              prefix={<UserAddOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 主要内容区域 */}
      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'overview',
              label: <span><TeamOutlined />群组概览</span>,
              children: (
                <div>
                  {/* 搜索和过滤 */}
                  <div style={{ marginBottom: '16px' }}>
                    <Row gutter={[16, 16]} align="middle">
                      <Col xs={24} sm={12} md={8}>
                        <Search
                          placeholder="搜索群组名称或描述"
                          value={searchText}
                          onChange={(e) => setSearchText(e.target.value)}
                          prefix={<SearchOutlined />}
                          allowClear
                        />
                      </Col>
                      <Col xs={24} sm={12} md={4}>
                        <Select
                          value={visibilityFilter}
                          onChange={setVisibilityFilter}
                          style={{ width: '100%' }}
                          placeholder="可见性"
                        >
                          <Option value="all">全部</Option>
                          <Option value="public">公开群组</Option>
                          <Option value="private">私有群组</Option>
                        </Select>
                      </Col>
                      <Col xs={24} sm={12} md={4}>
                        <Select
                          value={membershipFilter}
                          onChange={setMembershipFilter}
                          style={{ width: '100%' }}
                          placeholder="成员关系"
                        >
                          <Option value="all">全部群组</Option>
                          <Option value="my">我创建的</Option>
                          <Option value="joined">已加入的</Option>
                        </Select>
                      </Col>
                      <Col xs={24} sm={12} md={8}>
                        <Button
                          type="primary"
                          icon={<ReloadOutlined />}
                          onClick={loadGroups}
                          loading={loading}
                          style={{ marginRight: '8px' }}
                        >
                          刷新
                        </Button>
                        <Button
                          icon={<FilterOutlined />}
                          onClick={() => {
                            setSearchText('');
                            setVisibilityFilter('all');
                            setMembershipFilter('all');
                          }}
                        >
                          重置过滤
                        </Button>
                      </Col>
                    </Row>
                  </div>

                  {/* 群组列表 */}
                  <div>
                    <Title level={4} style={{ marginBottom: '16px' }}>
                      群组列表 ({filteredGroups.length})
                    </Title>
                    {filteredGroups.length > 0 ? (
                      <List
                        grid={{ gutter: 16, xs: 1, sm: 2, md: 2, lg: 3, xl: 4, xxl: 4 }}
                        dataSource={filteredGroups}
                        renderItem={(group) => {
                          // 构建 actions 数组
                          const actions = [
                            <Tooltip title="查看详情" key="view">
                              <EyeOutlined onClick={() => handleViewGroup(group)} />
                            </Tooltip>,
                            group.is_creator ? (
                              <Tooltip title="编辑群组" key="edit">
                                <EditOutlined onClick={() => handleEditGroup(group)} />
                              </Tooltip>
                            ) : group.is_member ? (
                              <Tooltip title="离开群组" key="leave">
                                <UserDeleteOutlined onClick={() => handleLeaveGroup(group)} />
                              </Tooltip>
                            ) : (
                              <Tooltip title="加入群组" key="join">
                                <UserAddOutlined onClick={() => handleJoinGroup(group)} />
                              </Tooltip>
                            ),
                            group.is_creator && (
                              <Tooltip title="删除群组" key="delete">
                                <DeleteOutlined onClick={() => handleDeleteGroup(group)} />
                              </Tooltip>
                            )
                          ].filter(Boolean);

                          return (
                          <List.Item>
                            <Card
                              hoverable
                              style={{
                                height: '280px',
                                border: `2px solid ${group.is_member ? '#f6ffed' : '#fff2e8'}`
                              }}
                              styles={{
                                body: {
                                  padding: '16px',
                                  height: 'calc(100% - 57px)',
                                  display: 'flex',
                                  flexDirection: 'column'
                                }
                              }}
                              actions={actions}
                            >
                              <List.Item.Meta
                                avatar={
                                  <Avatar
                                    size={48}
                                    icon={getGroupIcon(group)}
                                    style={{
                                      backgroundColor: group.is_creator ? '#fff7e6' : group.is_member ? '#f6ffed' : '#f0f0f0',
                                      border: '1px solid #d9d9d9'
                                    }}
                                  />
                                }
                                title={
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontWeight: 'bold', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                      {group.group_name}
                                    </span>
                                    <div style={{ display: 'flex', gap: '4px' }}>
                                      {getVisibilityIcon(group.is_public)}
                                      {group.is_creator && <Badge status="warning" title="创建者" />}
                                      {group.is_member && !group.is_creator && <Badge status="success" title="成员" />}
                                    </div>
                                  </div>
                                }
                                description={
                                  <div style={{ height: '140px', overflow: 'hidden' }}>
                                    <div style={{
                                      marginBottom: '8px',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                      display: '-webkit-box',
                                      WebkitLineClamp: 2,
                                      WebkitBoxOrient: 'vertical',
                                      lineHeight: '1.4',
                                      maxHeight: '2.8em'
                                    }}>
                                      <Text type="secondary" title={group.description}>
                                        {group.description || '暂无描述'}
                                      </Text>
                                    </div>
                                    <div style={{ marginBottom: '8px' }}>
                                      <Text strong>可见性: </Text>
                                      <Tag color={group.is_public ? 'green' : 'orange'}>
                                        {group.is_public ? '公开' : '私有'}
                                      </Tag>
                                    </div>
                                    <div style={{ marginBottom: '8px' }}>
                                      <Text strong>成员: </Text>
                                      <Tag color="blue">{group.member_count} 人</Tag>
                                    </div>
                                    <div>
                                      <Text strong>创建者: </Text>
                                      <Text>{group.creator_name || '未知'}</Text>
                                    </div>
                                  </div>
                                }
                              />
                            </Card>
                          </List.Item>
                        );
                        }}
                      />
                    ) : (
                      <Empty
                        description="暂无群组"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                      />
                    )}
                  </div>
                </div>
              )
            },
            {
              key: 'processors',
              label: <span><SettingOutlined />分组Processors</span>,
              children: (
                <div>
                  <Title level={4} style={{ marginBottom: '16px' }}>
                    按群组分类的Processors
                  </Title>
                  {Object.keys(groupedProcessors).length > 0 ? (
                    Object.entries(groupedProcessors).map(([groupName, processors]) => (
                      <Card
                        key={groupName}
                        title={
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <TeamOutlined />
                            <span>{groupName}</span>
                            <Badge count={processors.length} style={{ backgroundColor: '#52c41a' }} />
                          </div>
                        }
                        style={{ marginBottom: '16px' }}
                        size="small"
                      >
                        <List
                          grid={{ gutter: 8, xs: 1, sm: 2, md: 3, lg: 4 }}
                          dataSource={processors}
                          renderItem={(processor) => (
                            <List.Item>
                              <Card
                                size="small"
                                title={processor.name}
                                extra={
                                  <Tag color={processor.type === 'human' ? 'blue' : 'purple'}>
                                    {processor.type === 'human' ? '用户' : 'Agent'}
                                  </Tag>
                                }
                              >
                                <Text type="secondary" style={{ fontSize: '12px' }}>
                                  {processor.username || processor.agent_name || '未知'}
                                </Text>
                              </Card>
                            </List.Item>
                          )}
                        />
                      </Card>
                    ))
                  ) : (
                    <Empty description="暂无分组Processors" />
                  )}
                </div>
              )
            }
          ]}
          tabBarExtraContent={
            activeTab === 'overview' && (
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreateGroup}
              >
                创建群组
              </Button>
            )
          }
        />
      </Card>

      {/* 创建群组模态框 */}
      <Modal
        title="创建新群组"
        open={createModalVisible}
        onOk={confirmCreateGroup}
        onCancel={() => setCreateModalVisible(false)}
        width={600}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="group_name"
            label="群组名称"
            rules={[
              { required: true, message: '请输入群组名称' },
              { min: 1, max: 255, message: '群组名称长度应在1-255字符之间' }
            ]}
          >
            <Input placeholder="请输入群组名称" />
          </Form.Item>

          <Form.Item
            name="description"
            label="群组描述"
          >
            <TextArea
              rows={3}
              placeholder="请输入群组描述（可选）"
            />
          </Form.Item>

          <Form.Item
            name="is_public"
            label="可见性"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch
              checkedChildren="公开"
              unCheckedChildren="私有"
              style={{ width: '60px' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑群组模态框 */}
      <Modal
        title={`编辑群组 - ${selectedGroup?.group_name}`}
        open={editModalVisible}
        onOk={confirmEditGroup}
        onCancel={() => setEditModalVisible(false)}
        width={600}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item
            name="group_name"
            label="群组名称"
            rules={[
              { required: true, message: '请输入群组名称' },
              { min: 1, max: 255, message: '群组名称长度应在1-255字符之间' }
            ]}
          >
            <Input placeholder="请输入群组名称" />
          </Form.Item>

          <Form.Item
            name="description"
            label="群组描述"
          >
            <TextArea
              rows={3}
              placeholder="请输入群组描述（可选）"
            />
          </Form.Item>

          <Form.Item
            name="is_public"
            label="可见性"
            valuePropName="checked"
          >
            <Switch
              checkedChildren="公开"
              unCheckedChildren="私有"
              style={{ width: '60px' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 群组详情模态框 */}
      <Modal
        title={`群组详情 - ${selectedGroup?.group_name}`}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {selectedGroup && (
          <div>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="群组名称">{selectedGroup.group_name}</Descriptions.Item>
              <Descriptions.Item label="可见性">
                <Tag color={selectedGroup.is_public ? 'green' : 'orange'}>
                  {selectedGroup.is_public ? '公开群组' : '私有群组'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="成员数量">{selectedGroup.member_count} 人</Descriptions.Item>
              <Descriptions.Item label="创建者">{selectedGroup.creator_name || '未知'}</Descriptions.Item>
              <Descriptions.Item label="我的角色">
                <Tag color={selectedGroup.is_creator ? 'gold' : selectedGroup.is_member ? 'green' : 'default'}>
                  {selectedGroup.is_creator ? '创建者' : selectedGroup.is_member ? '成员' : '非成员'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {selectedGroup.created_at ? new Date(selectedGroup.created_at).toLocaleString() : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="群组描述" span={2}>
                {selectedGroup.description || '暂无描述'}
              </Descriptions.Item>
            </Descriptions>

            <Divider />

            <Row gutter={16}>
              <Col span={12}>
                <Button
                  type="primary"
                  icon={<UserOutlined />}
                  onClick={() => handleViewMembers(selectedGroup)}
                  block
                >
                  查看成员 ({selectedGroup.member_count})
                </Button>
              </Col>
              <Col span={12}>
                <Button
                  type="default"
                  icon={<SettingOutlined />}
                  onClick={() => handleViewProcessors(selectedGroup)}
                  block
                >
                  查看Processors
                </Button>
              </Col>
            </Row>
          </div>
        )}
      </Modal>

      {/* 群组成员模态框 */}
      <Modal
        title={`群组成员 - ${selectedGroup?.group_name}`}
        open={membersModalVisible}
        onCancel={() => setMembersModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setMembersModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={700}
      >
        {selectedGroup ? (
          groupMembers[selectedGroup.group_id] ? (
            <List
              dataSource={groupMembers[selectedGroup.group_id]}
              renderItem={(member) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<Avatar icon={<UserOutlined />} />}
                    title={member.username}
                    description={
                      <div>
                        <div>{member.email}</div>
                        <div style={{ marginTop: '4px' }}>
                          <Tag color="blue">加入时间: {new Date(member.joined_at).toLocaleDateString()}</Tag>
                          <Tag color={member.status === 'active' ? 'green' : 'orange'}>
                            {member.status === 'active' ? '活跃' : '非活跃'}
                          </Tag>
                        </div>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          ) : (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Empty description="正在加载成员列表..." />
            </div>
          )
        ) : null}
      </Modal>

      {/* 群组Processors模态框 */}
      <Modal
        title={`群组Processors - ${selectedGroup?.group_name}`}
        open={processorsModalVisible}
        onCancel={() => setProcessorsModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setProcessorsModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {selectedGroup ? (
          groupProcessors[selectedGroup.group_id] ? (
            <List
              grid={{ gutter: 16, xs: 1, sm: 2, md: 2 }}
              dataSource={groupProcessors[selectedGroup.group_id]}
              renderItem={(processor) => (
                <List.Item>
                  <Card
                    size="small"
                    title={processor.name}
                    extra={
                      <Tag color={processor.type === 'human' ? 'blue' : 'purple'}>
                        {processor.type === 'human' ? '用户' : 'Agent'}
                      </Tag>
                    }
                  >
                    <div>
                      <Text strong>关联实体: </Text>
                      <Text>{processor.username || processor.agent_name || '未知'}</Text>
                    </div>
                    <div style={{ marginTop: '8px' }}>
                      <Text strong>创建时间: </Text>
                      <Text>{processor.created_at ? new Date(processor.created_at).toLocaleDateString() : '-'}</Text>
                    </div>
                  </Card>
                </List.Item>
              )}
            />
          ) : (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <Empty description="正在加载Processors列表..." />
            </div>
          )
        ) : null}
      </Modal>

      {/* 删除群组确认模态框 */}
      <Modal
        title="确认删除群组"
        open={deleteModalVisible}
        onOk={confirmDeleteGroup}
        onCancel={() => setDeleteModalVisible(false)}
        okText="确认删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
        width={500}
      >
        <div>
          <p>确定要删除群组 <strong>"{groupToDelete?.group_name}"</strong> 吗？</p>
          <p style={{ color: '#ff4d4f', marginBottom: 0 }}>
            <ExclamationCircleOutlined style={{ marginRight: '8px' }} />
            此操作不可撤销，群组内的所有数据将被清除。
          </p>
        </div>
      </Modal>
    </div>
  );
};

export default React.memo(GroupManagement);