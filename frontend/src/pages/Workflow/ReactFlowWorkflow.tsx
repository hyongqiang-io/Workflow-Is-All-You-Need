import React, { useState, useEffect } from 'react';
import { Card, Select, Button, message, Space, Typography, Row, Col } from 'antd';
import { PlusOutlined, SaveOutlined } from '@ant-design/icons';
import ReactFlowDesigner from '../../components/ReactFlowDesigner';
import { workflowAPI } from '../../services/api';

const { Title, Text } = Typography;
const { Option } = Select;

const ReactFlowWorkflow: React.FC = () => {
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadWorkflows();
  }, []);

  const loadWorkflows = async () => {
    try {
      setLoading(true);
      const response = await workflowAPI.getWorkflows();
      if (response.data && response.data.workflows) {
        setWorkflows(response.data.workflows);
      }
    } catch (error) {
      console.error('加载工作流失败:', error);
      message.error('加载工作流失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWorkflow = async () => {
    try {
      const response = await workflowAPI.createWorkflow({
        name: `新工作流_${Date.now()}`,
        description: '使用React Flow创建的工作流',
      });

      if (response.data && response.data.workflow) {
        message.success('工作流创建成功');
        await loadWorkflows();
        setSelectedWorkflowId(response.data.workflow.workflow_base_id);
      }
    } catch (error) {
      console.error('创建工作流失败:', error);
      message.error('创建工作流失败');
    }
  };

  const handleSaveWorkflow = (nodes: any[], edges: any[]) => {
    console.log('保存工作流:', { nodes, edges });
    message.success('工作流保存成功');
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Row gutter={[16, 16]} align="middle">
          <Col>
            <Title level={3} style={{ margin: 0 }}>
              React Flow 工作流设计器
            </Title>
          </Col>
          <Col flex="auto">
            <Space>
              <Text>选择工作流:</Text>
              <Select
                style={{ width: 300 }}
                placeholder="请选择工作流"
                value={selectedWorkflowId}
                onChange={setSelectedWorkflowId}
                loading={loading}
              >
                {workflows.map((workflow) => (
                  <Option key={workflow.workflow_base_id} value={workflow.workflow_base_id}>
                    {workflow.name}
                  </Option>
                ))}
              </Select>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreateWorkflow}
                loading={loading}
              >
                创建新工作流
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card style={{ marginTop: '16px', minHeight: '700px' }}>
        {selectedWorkflowId ? (
          <ReactFlowDesigner
            workflowId={selectedWorkflowId}
            onSave={handleSaveWorkflow}
          />
        ) : (
          <div style={{ 
            textAlign: 'center', 
            padding: '100px 0',
            color: '#999'
          }}>
            <Text>请选择或创建一个工作流开始设计</Text>
          </div>
        )}
      </Card>
    </div>
  );
};

export default ReactFlowWorkflow; 