import React, { useState, useEffect } from 'react';
import { Card, Button, Table, Tag, Modal, Form, Input, Select, Space, message, Row, Col, Typography, Progress, Alert, Divider } from 'antd';
import { 
  PlayCircleOutlined, 
  StopOutlined, 
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  BugOutlined,
  RocketOutlined
} from '@ant-design/icons';
import { testAPI } from '../../services/api';

const { TextArea } = Input;
const { Option } = Select;
const { Title, Text, Paragraph } = Typography;

interface TestResult {
  test_name: string;
  success: boolean;
  message: string;
  details?: any;
  timestamp: string;
  duration?: number;
}

interface TestSuite {
  name: string;
  description: string;
  tests: string[];
  estimated_duration: number;
}

const TestRunner: React.FC = () => {
  const [testSuites, setTestSuites] = useState<TestSuite[]>([]);
  const [selectedTests, setSelectedTests] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<TestResult[]>([]);
  const [progress, setProgress] = useState(0);
  const [currentTest, setCurrentTest] = useState<string>('');
  const [summary, setSummary] = useState<any>(null);
  const [statusInterval, setStatusInterval] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    loadTestSuites();
    return () => {
      if (statusInterval) {
        clearInterval(statusInterval);
      }
    };
  }, []);

  const loadTestSuites = async () => {
    try {
      const response: any = await testAPI.getTestSuites();
      if (response && response.success && response.data && response.data.suites) {
        setTestSuites(response.data.suites);
      } else {
        message.error('加载测试套件失败');
      }
    } catch (error) {
      console.error('加载测试套件失败:', error);
      message.error('加载测试套件失败');
    }
  };

  const startStatusPolling = () => {
    const interval = setInterval(async () => {
      try {
        const response: any = await testAPI.getTestStatus();
        if (response && response.success && response.data) {
          const status = response.data;
          setRunning(status.running);
          setCurrentTest(status.current_test || '');
          setProgress(status.progress || 0);
          
          if (status.results) {
            setResults(status.results);
          }
          
          if (status.summary) {
            setSummary(status.summary);
          }
          
          // 如果测试完成，停止轮询
          if (!status.running) {
            clearInterval(interval);
            setStatusInterval(null);
          }
        }
      } catch (error) {
        console.error('获取测试状态失败:', error);
      }
    }, 1000); // 每秒轮询一次
    
    setStatusInterval(interval);
  };

  const handleRunTests = async () => {
    if (selectedTests.length === 0) {
      message.warning('请选择要运行的测试');
      return;
    }

    try {
      // 按套件分组测试
      const suites = testSuites.filter(suite => 
        suite.tests.some(test => selectedTests.includes(test))
      ).map(suite => suite.name);
      
      const individualTests = selectedTests.filter(test => 
        !testSuites.some(suite => suite.tests.includes(test))
      );

      const response: any = await testAPI.runTests({
        suites,
        tests: individualTests
      });

      if (response && response.success) {
        message.success('测试已启动');
        setRunning(true);
        setResults([]);
        setProgress(0);
        setSummary(null);
        startStatusPolling();
      } else {
        message.error(response?.message || '启动测试失败');
      }
    } catch (error: any) {
      console.error('启动测试失败:', error);
      message.error(error.response?.data?.detail || '启动测试失败');
    }
  };

  const handleRunRealTest = async (suiteName: string) => {
    try {
      const response: any = await testAPI.runRealTest(suiteName);
      if (response && response.success) {
        message.success(`真实测试 ${suiteName} 已启动`);
        setRunning(true);
        setResults([]);
        setProgress(0);
        setSummary(null);
        startStatusPolling();
      } else {
        message.error(response?.message || '启动真实测试失败');
      }
    } catch (error: any) {
      console.error('启动真实测试失败:', error);
      message.error(error.response?.data?.detail || '启动真实测试失败');
    }
  };

  const handleStopTests = async () => {
    try {
      const response: any = await testAPI.stopTests();
      if (response && response.success) {
        message.success('测试已停止');
        setRunning(false);
        setCurrentTest('');
        if (statusInterval) {
          clearInterval(statusInterval);
          setStatusInterval(null);
        }
      } else {
        message.error(response?.message || '停止测试失败');
      }
    } catch (error: any) {
      console.error('停止测试失败:', error);
      message.error(error.response?.data?.detail || '停止测试失败');
    }
  };

  const handleClearResults = async () => {
    try {
      const response: any = await testAPI.clearTestResults();
      if (response && response.success) {
        setResults([]);
        setSummary(null);
        setProgress(0);
        message.success('测试结果已清除');
      } else {
        message.error(response?.message || '清除测试结果失败');
      }
    } catch (error: any) {
      console.error('清除测试结果失败:', error);
      message.error(error.response?.data?.detail || '清除测试结果失败');
    }
  };

  const handleSelectTestSuite = (suiteName: string, checked: boolean) => {
    const suite = testSuites.find(s => s.name === suiteName);
    if (!suite) return;

    if (checked) {
      setSelectedTests(prev => [...prev, ...suite.tests]);
    } else {
      setSelectedTests(prev => prev.filter(test => !suite.tests.includes(test)));
    }
  };

  const handleSelectTest = (testName: string, checked: boolean) => {
    if (checked) {
      setSelectedTests(prev => [...prev, testName]);
    } else {
      setSelectedTests(prev => prev.filter(test => test !== testName));
    }
  };

  const getStatusColor = (success: boolean) => {
    return success ? 'success' : 'error';
  };

  const getStatusIcon = (success: boolean) => {
    return success ? <CheckCircleOutlined /> : <CloseCircleOutlined />;
  };

  const columns = [
    {
      title: '测试名称',
      dataIndex: 'test_name',
      key: 'test_name',
      render: (text: string) => (
        <Text strong>{text}</Text>
      )
    },
    {
      title: '状态',
      dataIndex: 'success',
      key: 'success',
      width: 100,
      render: (success: boolean) => (
        <Tag color={getStatusColor(success)} icon={getStatusIcon(success)}>
          {success ? '通过' : '失败'}
        </Tag>
      )
    },
    {
      title: '消息',
      dataIndex: 'message',
      key: 'message',
      render: (text: string) => (
        <Text>{text}</Text>
      )
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (duration: number) => (
        <Text type="secondary">{(duration / 1000).toFixed(1)}s</Text>
      )
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 150,
      render: (timestamp: string) => (
        <Text type="secondary" style={{ fontSize: '12px' }}>
          {new Date(timestamp).toLocaleString('zh-CN')}
        </Text>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: '24px' }}>
        <Title level={2} style={{ marginBottom: '8px' }}>
          <BugOutlined style={{ marginRight: '8px', color: '#1890ff' }} />
          测试运行器
        </Title>
        <Text type="secondary">运行后端测试套件，验证系统功能</Text>
      </div>

      <Row gutter={24}>
        {/* 左侧：测试套件选择 */}
        <Col span={12}>
          <Card title="测试套件" style={{ marginBottom: '24px' }}>
            {testSuites.map(suite => (
              <div key={suite.name} style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                  <input
                    type="checkbox"
                    checked={suite.tests.every(test => selectedTests.includes(test))}
                    onChange={(e) => handleSelectTestSuite(suite.name, e.target.checked)}
                    style={{ marginRight: '8px' }}
                  />
                  <Text strong>{suite.name}</Text>
                  <Tag color="blue" style={{ marginLeft: '8px' }}>
                    {suite.estimated_duration}s
                  </Tag>
                  <Button
                    type="link"
                    size="small"
                    icon={<RocketOutlined />}
                    onClick={() => handleRunRealTest(suite.name)}
                    disabled={running}
                    style={{ marginLeft: '8px' }}
                  >
                    真实测试
                  </Button>
                </div>
                <Paragraph type="secondary" style={{ marginLeft: '24px', marginBottom: '8px' }}>
                  {suite.description}
                </Paragraph>
                <div style={{ marginLeft: '24px' }}>
                  {suite.tests.map(test => (
                    <div key={test} style={{ marginBottom: '4px' }}>
                      <input
                        type="checkbox"
                        checked={selectedTests.includes(test)}
                        onChange={(e) => handleSelectTest(test, e.target.checked)}
                        style={{ marginRight: '8px' }}
                      />
                      <Text style={{ fontSize: '12px' }}>{test}</Text>
                    </div>
                  ))}
                </div>
                <Divider style={{ margin: '12px 0' }} />
              </div>
            ))}
          </Card>

          {/* 操作按钮 */}
          <Card>
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleRunTests}
                loading={running}
                disabled={selectedTests.length === 0}
              >
                运行测试 ({selectedTests.length})
              </Button>
              <Button
                icon={<StopOutlined />}
                onClick={handleStopTests}
                disabled={!running}
              >
                停止测试
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleClearResults}
              >
                清除结果
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 右侧：测试进度和结果 */}
        <Col span={12}>
          {/* 测试进度 */}
          {running && (
            <Card title="测试进度" style={{ marginBottom: '24px' }}>
              <Progress percent={progress} status="active" />
              <Text type="secondary">当前测试: {currentTest}</Text>
            </Card>
          )}

          {/* 测试摘要 */}
          {summary && (
            <Card title="测试摘要" style={{ marginBottom: '24px' }}>
              <Row gutter={16}>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <Title level={3} style={{ color: '#1890ff', margin: 0 }}>
                      {summary.total}
                    </Title>
                    <Text type="secondary">总测试数</Text>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <Title level={3} style={{ color: '#52c41a', margin: 0 }}>
                      {summary.passed}
                    </Title>
                    <Text type="secondary">通过</Text>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <Title level={3} style={{ color: '#ff4d4f', margin: 0 }}>
                      {summary.failed}
                    </Title>
                    <Text type="secondary">失败</Text>
                  </div>
                </Col>
                <Col span={6}>
                  <div style={{ textAlign: 'center' }}>
                    <Title level={3} style={{ color: '#722ed1', margin: 0 }}>
                      {(Number(summary?.success_rate) || 0).toFixed(1)}%
                    </Title>
                    <Text type="secondary">成功率</Text>
                  </div>
                </Col>
              </Row>
              <Divider />
              <Text type="secondary">
                总耗时: {(summary.duration / 1000).toFixed(1)} 秒
              </Text>
            </Card>
          )}

          {/* 测试结果 */}
          {results.length > 0 && (
            <Card title="测试结果">
              <Table
                columns={columns}
                dataSource={results}
                rowKey="test_name"
                pagination={false}
                size="small"
              />
            </Card>
          )}
        </Col>
      </Row>

      {/* 说明信息 */}
      <Card style={{ marginTop: '24px' }}>
        <Alert
          message="测试说明"
          description={
            <div>
              <Paragraph>
                <strong>测试套件说明：</strong>
              </Paragraph>
              <ul>
                <li><strong>comprehensive_test</strong>: 完整的工作流系统测试，包含所有核心功能</li>
                <li><strong>simple_execution_test</strong>: 简单的工作流执行测试，适合快速验证</li>
                <li><strong>test_workflow_api</strong>: 工作流API接口测试</li>
                <li><strong>test_auth</strong>: 用户认证和权限测试</li>
                <li><strong>test_processor_integration</strong>: 处理器集成测试</li>
              </ul>
              <Paragraph>
                <strong>功能说明：</strong>
              </Paragraph>
              <ul>
                <li><strong>模拟测试</strong>: 选择测试套件或单个测试，点击"运行测试"进行模拟测试</li>
                <li><strong>真实测试</strong>: 点击"真实测试"按钮运行实际的测试文件</li>
                <li><strong>实时监控</strong>: 测试运行时会实时显示进度和状态</li>
                <li><strong>结果查看</strong>: 测试完成后可以查看详细的测试结果和摘要</li>
              </ul>
            </div>
          }
          type="info"
          showIcon
        />
      </Card>
    </div>
  );
};

export default TestRunner; 