import React, { useState } from 'react';
import { Button, Input, Card, Spin, message, Space, Typography, Tag } from 'antd';
import { BulbOutlined, RobotOutlined, SendOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

interface AIWorkflowGeneratorProps {
  onWorkflowGenerated: (workflowData: any) => void;
  onImportToEditor: (workflowData: any) => void;
}


const AIWorkflowGenerator: React.FC<AIWorkflowGeneratorProps> = ({
  onWorkflowGenerated,
  onImportToEditor
}) => {
  const [taskDescription, setTaskDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedWorkflow, setGeneratedWorkflow] = useState<any>(null);


  const generateWorkflow = async () => {
    if (!taskDescription.trim()) {
      message.error('请输入任务描述');
      return;
    }

    if (taskDescription.length < 5) {
      message.error('任务描述至少需要5个字符');
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const requestData = {
        task_description: taskDescription
      };
      
      console.log('发送AI生成请求:', requestData);
      console.log('Token存在:', !!token);
      
      const response = await fetch('/api/ai-workflows/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error('详细错误信息:', errorData);
        
        // 显示更详细的错误信息
        if (response.status === 401) {
          throw new Error('用户认证失败，请重新登录');
        } else if (response.status === 400) {
          throw new Error(`请求参数错误: ${errorData.detail || '输入的任务描述格式不正确'}`);
        } else if (response.status === 500) {
          throw new Error(`AI服务暂时不可用: ${errorData.detail || '服务器内部错误'}`);
        } else {
          throw new Error(errorData.detail || `生成失败 (${response.status})`);
        }
      }

      const result = await response.json();
      const workflowData = result.workflow_data;
      
      setGeneratedWorkflow(workflowData);
      onWorkflowGenerated(workflowData);
      
      message.success({
        content: `🎉 ${result.message}`,
        duration: 3
      });

    } catch (error: any) {
      console.error('AI工作流生成失败:', error);
      message.error(`生成失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };




  const importToEditor = () => {
    if (generatedWorkflow) {
      onImportToEditor(generatedWorkflow);
      message.success('工作流已导入到编辑器，可以开始分配处理器！');
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <Card>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <RobotOutlined style={{ fontSize: '48px', color: '#1890ff', marginBottom: '16px' }} />
          <Title level={2}>AI工作流生成器</Title>
          <Paragraph type="secondary" style={{ fontSize: '16px' }}>
            描述您的任务，AI将自动为您生成完整的工作流模板
          </Paragraph>
        </div>

        <div style={{ marginBottom: '32px' }}>
          <Title level={4} style={{ marginBottom: '16px' }}>
            <BulbOutlined /> 描述您的任务
          </Title>
          <TextArea
            placeholder="例如：开发一个电商网站、制作营销视频、数据分析项目..."
            value={taskDescription}
            onChange={(e) => setTaskDescription(e.target.value)}
            rows={4}
            maxLength={1000}
            showCount
            style={{ marginBottom: '16px' }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={generateWorkflow}
            loading={loading}
            size="large"
            disabled={!taskDescription.trim() || taskDescription.length < 5}
          >
            {loading ? 'AI正在生成中...' : '生成工作流'}
          </Button>
        </div>


        {generatedWorkflow && (
          <Card
            title={
              <Space>
                <RobotOutlined style={{ color: '#52c41a' }} />
                生成结果
              </Space>
            }
            style={{ marginTop: '24px' }}
            extra={
              <Button type="primary" onClick={importToEditor}>
                导入到编辑器
              </Button>
            }
          >
            <div style={{ marginBottom: '16px' }}>
              <Title level={5} style={{ marginBottom: '8px' }}>
                📋 {generatedWorkflow.name}
              </Title>
              <Paragraph style={{ marginBottom: '16px', color: '#666' }}>
                {generatedWorkflow.description}
              </Paragraph>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
              <div>
                <Title level={5}>🔗 节点列表 ({generatedWorkflow.nodes?.length || 0})</Title>
                <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  {generatedWorkflow.nodes?.map((node: any, index: number) => (
                    <div
                      key={index}
                      style={{
                        padding: '8px 12px',
                        margin: '4px 0',
                        background: '#f5f5f5',
                        borderRadius: '6px',
                        fontSize: '14px'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text strong>{node.name}</Text>
                        <Tag
                          color={
                            node.type === 'start' ? 'green' :
                            node.type === 'end' ? 'red' : 'blue'
                          }
                        >
                          {node.type}
                        </Tag>
                      </div>
                      {node.task_description && (
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {node.task_description}
                        </Text>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <Title level={5}>🔄 连接关系 ({generatedWorkflow.connections?.length || 0})</Title>
                <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  {generatedWorkflow.connections?.map((connection: any, index: number) => (
                    <div
                      key={index}
                      style={{
                        padding: '8px 12px',
                        margin: '4px 0',
                        background: '#e6f7ff',
                        borderRadius: '6px',
                        fontSize: '14px'
                      }}
                    >
                      <Text>
                        {connection.from_node_name} → {connection.to_node_name}
                      </Text>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '16px', padding: '12px', background: '#fff7e6', borderRadius: '6px' }}>
              <Text type="warning" style={{ fontSize: '14px' }}>
                💡 提示：生成的工作流模板不包含处理器分配，导入后您可以为每个节点分配具体的处理器。
              </Text>
            </div>
          </Card>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: '16px' }}>
              <Text type="secondary">AI正在分析您的任务并生成工作流...</Text>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default AIWorkflowGenerator;