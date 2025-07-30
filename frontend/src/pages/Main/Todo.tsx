import React, { useState, useEffect } from 'react';
import { Card, List, Tag, Button, Modal, Form, Input, Select, DatePicker, message, Space, Badge, Collapse, Typography, Divider, Alert } from 'antd';
import { CheckCircleOutlined, ClockCircleOutlined, ExclamationCircleOutlined, EditOutlined, SaveOutlined, InfoCircleOutlined, UpOutlined, DownOutlined } from '@ant-design/icons';
import { useTaskStore } from '../../stores/taskStore';
import { useAuthStore } from '../../stores/authStore';

const { TextArea } = Input;
const { Option } = Select;
const { Panel } = Collapse;
const { Text, Paragraph } = Typography;

const Todo: React.FC = () => {
  const { user } = useAuthStore();
  const { 
    tasks, 
    loading, 
    error,
    loadTasks, 
    startTask, 
    submitTaskResult,
    pauseTask,
    requestHelp,
    rejectTask,
    cancelTask,
    saveTaskDraft,
    getTaskDraft,
    clearTaskDraft
  } = useTaskStore();
  
  const [submitModalVisible, setSubmitModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [helpModalVisible, setHelpModalVisible] = useState(false);
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [currentTask, setCurrentTask] = useState<any>(null);
  const [submitForm] = Form.useForm();
  const [helpForm] = Form.useForm();
  const [rejectForm] = Form.useForm();
  const [cancelForm] = Form.useForm();

  useEffect(() => {
    if (user) {
      loadTasks();
    }
  }, [user, loadTasks]);

  useEffect(() => {
    if (error) {
      message.error(error);
    }
  }, [error]);

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'orange';
      case 'assigned':
        return 'cyan';
      case 'in_progress':
        return 'blue';
      case 'completed':
        return 'green';
      case 'failed':
        return 'red';
      case 'cancelled':
        return 'gray';
      case 'overdue':
        return 'volcano';
      default:
        return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status.toLowerCase()) {
      case 'pending':
        return '待分配';
      case 'assigned':
        return '已分配';
      case 'in_progress':
        return '进行中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      case 'cancelled':
        return '已取消';
      case 'overdue':
        return '已逾期';
      default:
        return '未知';
    }
  };

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 3:
        return 'red';
      case 2:
        return 'orange';
      case 1:
        return 'green';
      default:
        return 'default';
    }
  };

  const getPriorityText = (priority: number) => {
    switch (priority) {
      case 3:
        return '高';
      case 2:
        return '中';
      case 1:
        return '低';
      default:
        return '未知';
    }
  };

  const handleSubmit = (task: any) => {
    setCurrentTask(task);
    setSubmitModalVisible(true);
    submitForm.resetFields();
    
    // 加载草稿数据
    const draft = getTaskDraft(task.task_instance_id);
    if (draft) {
      submitForm.setFieldsValue(draft);
      message.info('已加载草稿数据');
    }
  };

  const handleViewDetails = async (task: any) => {
    setCurrentTask(task);
    setDetailModalVisible(true);
  };

  const handleSubmitConfirm = async () => {
    try {
      const values = await submitForm.validateFields();
      await submitTaskResult(currentTask.task_instance_id, values.result, values.notes);
      message.success('任务提交成功');
      setSubmitModalVisible(false);
    } catch (error) {
      console.error('提交失败:', error);
    }
  };

  const handleStartTask = async (task: any) => {
    try {
      await startTask(task.task_instance_id);
      message.success('任务已开始');
    } catch (error) {
      message.error('开始任务失败');
    }
  };

  const handlePauseTask = async (task: any) => {
    try {
      await pauseTask(task.task_instance_id, '用户手动暂停');
      message.success('任务已暂停');
      loadTasks(); // 重新加载任务列表
    } catch (error) {
      console.error('暂停任务失败:', error);
      message.error('暂停任务失败');
    }
  };

  const handleRequestHelp = (task: any) => {
    setCurrentTask(task);
    setHelpModalVisible(true);
    helpForm.resetFields();
  };

  const handleHelpSubmit = async () => {
    try {
      const values = await helpForm.validateFields();
      await requestHelp(currentTask.task_instance_id, values.help_message);
      message.success('帮助请求已提交');
      setHelpModalVisible(false);
    } catch (error) {
      console.error('提交帮助请求失败:', error);
    }
  };

  const handleSaveDraft = () => {
    submitForm.validateFields().then(values => {
      saveTaskDraft(currentTask.task_instance_id, values);
      message.success('草稿已保存');
    }).catch(() => {
      message.warning('请先填写必填字段');
    });
  };

  const handleRejectTask = (task: any) => {
    setCurrentTask(task);
    setRejectModalVisible(true);
    rejectForm.resetFields();
  };

  const handleRejectConfirm = async () => {
    try {
      const values = await rejectForm.validateFields();
      await rejectTask(currentTask.task_instance_id, values.reject_reason);
      message.success('任务已拒绝');
      setRejectModalVisible(false);
    } catch (error) {
      console.error('拒绝任务失败:', error);
    }
  };

  const handleCancelTask = (task: any) => {
    setCurrentTask(task);
    setCancelModalVisible(true);
    cancelForm.resetFields();
  };

  const handleCancelConfirm = async () => {
    try {
      const values = await cancelForm.validateFields();
      await cancelTask(currentTask.task_instance_id, values.cancel_reason || "用户取消");
      message.success('任务已取消');
      setCancelModalVisible(false);
    } catch (error) {
      console.error('取消任务失败:', error);
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: '24px' }}>我的待办</h2>
      
      <Card>
        <List
          loading={loading}
          dataSource={tasks}
          renderItem={(item) => (
            <List.Item
              actions={[
                // PENDING/ASSIGNED状态可以开始任务
                (item.status.toLowerCase() === 'pending' || item.status.toLowerCase() === 'assigned') && (
                  <Button 
                    key="start" 
                    type="primary" 
                    size="small"
                    onClick={() => handleStartTask(item)}
                  >
                    开始任务
                  </Button>
                ),
                // PENDING/ASSIGNED状态可以拒绝任务
                (item.status.toLowerCase() === 'pending' || item.status.toLowerCase() === 'assigned') && (
                  <Button 
                    key="reject" 
                    danger
                    size="small"
                    onClick={() => handleRejectTask(item)}
                  >
                    拒绝任务
                  </Button>
                ),
                // IN_PROGRESS状态可以提交结果
                item.status.toLowerCase() === 'in_progress' && (
                  <Button 
                    key="submit" 
                    type="primary" 
                    size="small"
                    icon={<SaveOutlined />}
                    onClick={() => handleSubmit(item)}
                  >
                    提交结果
                  </Button>
                ),
                // IN_PROGRESS状态可以暂停任务
                item.status.toLowerCase() === 'in_progress' && (
                  <Button 
                    key="pause" 
                    size="small"
                    onClick={() => handlePauseTask(item)}
                  >
                    暂停任务
                  </Button>
                ),
                // IN_PROGRESS状态可以请求帮助
                item.status.toLowerCase() === 'in_progress' && (
                  <Button 
                    key="help" 
                    size="small"
                    onClick={() => handleRequestHelp(item)}
                  >
                    请求帮助
                  </Button>
                ),
                // 进行中、已分配、待分配状态可以取消任务
                (item.status.toLowerCase() === 'in_progress' || 
                 item.status.toLowerCase() === 'assigned' || 
                 item.status.toLowerCase() === 'pending') && (
                  <Button 
                    key="cancel" 
                    danger
                    size="small"
                    onClick={() => handleCancelTask(item)}
                  >
                    取消任务
                  </Button>
                ),
                // 所有状态都可以查看详情
                <Button key="view" type="link" size="small" onClick={() => handleViewDetails(item)}>
                  查看详情
                </Button>
              ].filter(Boolean)}
            >
              <List.Item.Meta
                title={
                  <div>
                    {item.task_title}
                    <Tag color={getStatusColor(item.status)} style={{ marginLeft: '8px' }}>
                      {getStatusText(item.status)}
                    </Tag>
                    <Tag color={getPriorityColor(item.priority)}>
                      {getPriorityText(item.priority)}优先级
                    </Tag>
                  </div>
                }
                description={
                  <div>
                    <div>{item.task_description}</div>
                    {/* 显示上游上下文信息 */}
                    {item.input_data && (item.input_data.immediate_upstream || item.input_data.workflow_global) && (
                      <div style={{ marginTop: '8px' }}>
                        <Alert
                          message="包含上游上下文数据"
                          description={`上游节点数: ${item.input_data.node_info?.upstream_node_count || 0}个`}
                          type="info"
                          showIcon
                          style={{ fontSize: '12px' }}
                        />
                      </div>
                    )}
                    <div style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
                      <Space>
                        <span>任务ID: {item.task_instance_id}</span>
                        <span>创建时间: {item.created_at}</span>
                        {item.started_at && <span>开始时间: {item.started_at}</span>}
                        {item.completed_at && <span>完成时间: {item.completed_at}</span>}
                      </Space>
                    </div>
                    {item.result_summary && (
                      <div style={{ marginTop: '8px', padding: '8px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '4px' }}>
                        <strong>提交结果:</strong> {item.result_summary}
                      </div>
                    )}
                  </div>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      {/* 任务详情模态框 */}
      <Modal
        title="任务详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {currentTask && (
          <div>
            <Card size="small" title="基本信息" style={{ marginBottom: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <Text strong>任务标题: </Text>
                  <Text>{currentTask.task_title}</Text>
                </div>
                <div>
                  <Text strong>任务状态: </Text>
                  <Tag color={getStatusColor(currentTask.status)}>
                    {getStatusText(currentTask.status)}
                  </Tag>
                </div>
                <div>
                  <Text strong>优先级: </Text>
                  <Tag color={getPriorityColor(currentTask.priority)}>
                    {getPriorityText(currentTask.priority)}
                  </Tag>
                </div>
                <div>
                  <Text strong>任务类型: </Text>
                  <Text>{currentTask.task_type}</Text>
                </div>
              </div>
              <Divider />
              <div>
                <Text strong>任务描述: </Text>
                <Paragraph>{currentTask.task_description}</Paragraph>
              </div>
              {currentTask.instructions && (
                <div>
                  <Text strong>执行指令: </Text>
                  <Paragraph>{currentTask.instructions}</Paragraph>
                </div>
              )}
            </Card>

            {/* 上下文信息 */}
            {(currentTask.context_data || currentTask.input_data) && (
              <Card size="small" title="执行上下文" style={{ marginBottom: '16px' }}>
                <Collapse size="small">
                  {/* 新的context_data字段 */}
                  {currentTask.context_data && (
                    <>
                      {currentTask.context_data.workflow && (
                        <Panel header="工作流信息" key="workflow_info">
                          <div>
                            <p><Text strong>工作流名称:</Text> {currentTask.context_data.workflow.name}</p>
                            <p><Text strong>实例名称:</Text> {currentTask.context_data.workflow.instance_name}</p>
                            <p><Text strong>状态:</Text> {currentTask.context_data.workflow.status}</p>
                            <p><Text strong>创建时间:</Text> {currentTask.context_data.workflow.created_at}</p>
                            {currentTask.context_data.workflow.input_data && Object.keys(currentTask.context_data.workflow.input_data).length > 0 && (
                              <div>
                                <Text strong>工作流输入数据:</Text>
                                <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', marginTop: '4px', maxHeight: '150px', overflow: 'auto' }}>
                                  {JSON.stringify(currentTask.context_data.workflow.input_data, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </Panel>
                      )}
                      
                      {currentTask.context_data.upstream_outputs && currentTask.context_data.upstream_outputs.length > 0 && (
                        <Panel header="上游节点输出" key="upstream_outputs">
                          {currentTask.context_data.upstream_outputs.map((upstreamNode: any, index: number) => (
                            <div key={index} style={{ marginBottom: '12px', paddingBottom: '12px', borderBottom: index < currentTask.context_data.upstream_outputs.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                              <div style={{ marginBottom: '8px' }}>
                                <Text strong>{upstreamNode.node_name}</Text>
                                <span style={{ marginLeft: '8px', fontSize: '12px', color: '#666' }}>
                                  完成时间: {upstreamNode.completed_at ? new Date(upstreamNode.completed_at).toLocaleString() : '未知'}
                                </span>
                              </div>
                              {upstreamNode.output_data && Object.keys(upstreamNode.output_data).length > 0 ? (
                                <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', maxHeight: '150px', overflow: 'auto' }}>
                                  {JSON.stringify(upstreamNode.output_data, null, 2)}
                                </pre>
                              ) : (
                                <Text type="secondary">该节点无输出数据</Text>
                              )}
                            </div>
                          ))}
                        </Panel>
                      )}
                      
                      {currentTask.context_data.current_node && (
                        <Panel header="当前节点信息" key="current_node_info">
                          <div>
                            <p><Text strong>节点名称:</Text> {currentTask.context_data.current_node.name}</p>
                            <p><Text strong>节点类型:</Text> {currentTask.context_data.current_node.type}</p>
                            <p><Text strong>节点描述:</Text> {currentTask.context_data.current_node.description}</p>
                            <p><Text strong>状态:</Text> {currentTask.context_data.current_node.status}</p>
                            {currentTask.context_data.current_node.input_data && Object.keys(currentTask.context_data.current_node.input_data).length > 0 && (
                              <div>
                                <Text strong>节点输入数据:</Text>
                                <pre style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', marginTop: '4px', maxHeight: '150px', overflow: 'auto' }}>
                                  {JSON.stringify(currentTask.context_data.current_node.input_data, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </Panel>
                      )}
                    </>
                  )}
                  
                  {/* 兼容旧的input_data格式 */}
                  {currentTask.input_data && (
                    <>
                      {currentTask.input_data.immediate_upstream && Object.keys(currentTask.input_data.immediate_upstream).length > 0 && (
                        <Panel header="直接上游节点结果 (兼容格式)" key="immediate_upstream">
                          <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                            {JSON.stringify(currentTask.input_data.immediate_upstream, null, 2)}
                          </pre>
                        </Panel>
                      )}
                      
                      {currentTask.input_data.workflow_global && Object.keys(currentTask.input_data.workflow_global).length > 0 && (
                        <Panel header="全局工作流上下文 (兼容格式)" key="workflow_global">
                          <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                            {JSON.stringify(currentTask.input_data.workflow_global, null, 2)}
                          </pre>
                        </Panel>
                      )}
                    </>
                  )}
                </Collapse>
                
                {/* 无上下文数据提示 */}
                {(!currentTask.context_data || Object.keys(currentTask.context_data).length === 0) &&
                 (!currentTask.input_data || (
                   (!currentTask.input_data.immediate_upstream || Object.keys(currentTask.input_data.immediate_upstream).length === 0) &&
                   (!currentTask.input_data.workflow_global || Object.keys(currentTask.input_data.workflow_global).length === 0)
                 )) && (
                  <Alert
                    message="无上下文数据"
                    description="这个任务没有可用的上下文数据，可能是工作流的起始任务或数据收集失败。"
                    type="info"
                    showIcon
                  />
                )}
              </Card>
            )}

            {/* 任务结果 */}
            {currentTask.output_data && (
              <Card size="small" title="任务结果">
                <div>
                  {currentTask.result_summary && (
                    <div style={{ marginBottom: '12px' }}>
                      <Text strong>结果摘要: </Text>
                      <Paragraph>{currentTask.result_summary}</Paragraph>
                    </div>
                  )}
                  
                  {currentTask.output_data && (
                    <div>
                      <Text strong>输出数据: </Text>
                      <pre style={{ background: '#f5f5f5', padding: '12px', borderRadius: '4px', maxHeight: '200px', overflow: 'auto' }}>
                        {JSON.stringify(currentTask.output_data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </Card>
            )}
          </div>
        )}
      </Modal>

      {/* 请求帮助模态框 */}
      <Modal
        title="请求帮助"
        open={helpModalVisible}
        onOk={handleHelpSubmit}
        onCancel={() => setHelpModalVisible(false)}
        width={500}
      >
        <Form form={helpForm} layout="vertical">
          <Form.Item
            name="help_message"
            label="帮助信息"
            rules={[{ required: true, message: '请描述您需要的帮助' }]}
          >
            <TextArea 
              rows={4} 
              placeholder="请详细描述您在执行任务过程中遇到的问题或需要的帮助...

例如：
- 不确定如何理解上游数据
- 遇到技术问题
- 需要额外的信息或资源" 
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="提交任务结果"
        open={submitModalVisible}
        onOk={handleSubmitConfirm}
        onCancel={() => setSubmitModalVisible(false)}
        width={600}
        footer={[
          <Button key="save-draft" onClick={handleSaveDraft}>
            保存草稿
          </Button>,
          <Button key="cancel" onClick={() => setSubmitModalVisible(false)}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={handleSubmitConfirm}>
            提交结果
          </Button>,
        ]}
      >
        <Form form={submitForm} layout="vertical">
          <Form.Item
            name="result"
            label="任务结果"
            rules={[{ required: true, message: '请输入任务结果' }]}
            extra={currentTask?.input_data?.immediate_upstream || currentTask?.input_data?.workflow_global ? 
              '提示：您可以在上方的“任务详情”中查看上游上下文数据' : null
            }
          >
            <TextArea rows={6} placeholder="请详细描述任务完成情况...

可以参考上游上下文数据来完成任务。" />
          </Form.Item>
          <Form.Item
            name="attachments"
            label="附件"
          >
            <Input placeholder="附件链接（可选）" />
          </Form.Item>
          <Form.Item
            name="notes"
            label="备注"
          >
            <TextArea rows={3} placeholder="其他备注信息（可选）

可以记录使用了哪些上游数据、遇到的问题等" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 拒绝任务模态框 */}
      <Modal
        title="拒绝任务"
        open={rejectModalVisible}
        onOk={handleRejectConfirm}
        onCancel={() => setRejectModalVisible(false)}
        width={500}
        okText="确认拒绝"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        <Form form={rejectForm} layout="vertical">
          <Form.Item
            name="reject_reason"
            label="拒绝原因"
            rules={[{ required: true, message: '请说明拒绝任务的原因' }]}
          >
            <TextArea 
              rows={4} 
              placeholder="请详细说明为什么要拒绝此任务...

例如：
- 任务要求不明确，需要更多信息
- 超出个人能力范围
- 时间冲突，无法按时完成
- 其他技术或资源限制"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 取消任务模态框 */}
      <Modal
        title="取消任务"
        open={cancelModalVisible}
        onOk={handleCancelConfirm}
        onCancel={() => setCancelModalVisible(false)}
        width={500}
        okText="确认取消"
        okButtonProps={{ danger: true }}
        cancelText="返回"
      >
        <Form form={cancelForm} layout="vertical">
          <Form.Item
            name="cancel_reason"
            label="取消原因（可选）"
          >
            <TextArea 
              rows={3} 
              placeholder="请说明取消任务的原因（可选）...

例如：
- 任务已不再需要
- 需求发生变化
- 其他优先级任务需要处理"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Todo;
