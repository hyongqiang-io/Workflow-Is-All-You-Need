import React, { useState, useEffect } from 'react';
import { Card, Tabs, Typography, Spin, Alert, Button, Space } from 'antd';
import { DownloadOutlined, EyeOutlined } from '@ant-design/icons';
import MarkdownRenderer from '../../components/MarkdownRenderer';

const { Title, Paragraph, Text } = Typography;

const Help: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<'rendered' | 'raw'>('rendered');

  // 导出Markdown文档
  const exportMarkdown = () => {
    const allContent = `# Autoflow 工作流自动化平台完整使用说明

${documentationContent.overview}

---

${documentationContent.workflow}

---

${documentationContent.resource}

---

${documentationContent.tasks}`;

    const blob = new Blob([allContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'Autoflow_使用说明.md';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const documentationContent = {
    overview: `# Autoflow 工作流自动化平台使用说明

## 🚀 平台简介

**Autoflow** 是一个智能工作流自动化平台，支持 Agent 管理、人机协作和工作流的创建、执行与监控。

> ✅ **核心优势**
> - 🤖 智能 Agent 协作
> - 🔄 可视化工作流设计  
> - 📊 实时执行监控
> - 🛠️ 丰富的工具集成

---

## 📋 核心功能

### 🎯 仪表板 (Dashboard)
- **资源概览** - 查看总体资源状况
- **任务统计** - 监控待办任务数量  
- **用户分析** - 用户和 Agent 统计概览

### 🔧 资源管理
- **资源概况** - 查看所有 Agent 和用户
- **Agent 管理** - 创建、编辑和配置 Agent
- **Processor 管理** - 用户和 Agent 处理器注册
- **我的工具** - MCP 工具集成和管理

### 🌊 工作流管理  
- **工作流模板** - 创建、编辑、导入导出工作流模板
- **执行记录** - 查看工作流实例化执行情况
- **AI 生成** - 智能生成工作流模板
- **模板合并** - 支持子工作流递归合并

### ✅ 待办任务
- **任务列表** - 查看分配给自己的任务
- **执行管理** - 任务执行和结果提交
- **任务细分** - 任务细分和工作流创建
- **状态监控** - 子任务状态监控

### 👤 个人中心
- **信息管理** - 修改邮箱和个人信息
- **个人简介** - 添加个人描述

---

## 🎯 快速开始

\`\`\`mermaid
graph TD
    A[注册登录] --> B[创建 Agent]
    B --> C[注册 Processor]
    C --> D[创建工作流]
    D --> E[执行工作流]
\`\`\`

### 步骤详解

1. **注册登录** → 访问平台并创建账号
2. **创建 Agent** → 在资源管理中注册 Agent
3. **注册 Processor** → 将用户/Agent 注册为处理器
4. **创建工作流** → 设计自己的自动化流程
5. **执行工作流** → 实例化模板并监控执行

> ⚠️ **重要提醒**
> 用户和 Agent 只有被注册为 Processor 才能被工作流调用！`,

    workflow: `# 🌊 工作流管理详细指南

## 工作流模板创建

### 1. 创建流程

\`\`\`bash
# 创建工作流的基本流程
1. 点击"工作流管理" → "创建工作流"
2. 选择节点类型
3. 添加节点并连接关系  
4. 绑定 Processor
5. 保存工作流模板
\`\`\`

### 2. 节点类型

| 节点类型 | 描述 | 配置要点 |
|---------|------|----------|
| **开始节点** | 工作流入口点 | 定义输入参数和触发条件 |
| **中间节点** | 处理业务逻辑 | 绑定具体的处理器 |
| **结束节点** | 工作流出口点 | 定义输出结果和完成条件 |

### 3. 节点配置详解

#### 开始节点 🏁
- 定义输入参数和触发条件
- 设置工作流的初始状态
- 配置数据来源

#### 处理节点 ⚙️
- 绑定具体的处理器（Agent 或人工）
- 配置任务描述和执行参数
- 设置超时和重试策略

#### 结束节点 🎯
- 定义输出结果和完成条件
- 配置结果格式化
- 设置完成通知

### 4. AI 智能生成

> ✅ **AI 功能特点**
> - 🧠 自然语言描述转换为工作流
> - 🎨 智能节点布局和连接
> - 🔧 自动配置推荐

\`\`\`typescript
// AI 生成工作流示例
const workflowDescription = "创建一个数据处理工作流，包含数据收集、清洗、分析和报告生成";
const generatedWorkflow = await aiService.generateWorkflow(workflowDescription);
\`\`\`

### 5. 工作流执行

#### 执行监控 📊

- **实时状态** - 查看工作流执行状态和进度
- **节点详情** - 节点级别的执行情况
- **图形视图** - 可视化展示整个工作流状态

#### 执行控制 🎮

\`\`\`javascript
// 工作流执行控制
workflow.start();    // 启动执行
workflow.cancel();   // 取消执行
\`\`\`

---

## 📁 工作流操作

### 导入导出

- **导出格式** - JSON 格式的工作流模板
- **导入支持** - 从 JSON 文件加载工作流模板
- **版本兼容** - 支持不同版本间的模板迁移

### 模板合并

> 🔄 **合并功能**
> - 支持子工作流细分后的递归合并
> - 可以用细分工作流替代原有工作节点
> - 合并后生成新的工作流模板

### 编辑管理

- **实时编辑** - 工作流模板实时编辑
- **版本控制** - 历史版本管理和回滚
- **模板管理** - 删除不需要的模板`,

    resource: `# 🔧 资源管理详细说明

## Agent 管理

### 1. 创建 Agent

` + '```mermaid' + `
graph LR
    A[进入Agent管理] --> B[点击创建]
    B --> C[填写基本信息]
    C --> D[创建Processor]
    D --> E[配置工具]
` + '```' + `

#### 创建步骤
1. 进入"资源管理" → "Agent 管理"
2. 点击"创建单个 agent"
3. 填写 Agent 基本信息
4. 创建完成后需要创建对应的 Processor

### 2. Agent 配置

| 配置项 | 说明 | 示例 |
|-------|------|------|
| **处理能力** | 定义 Agent 的专业领域 | 数据分析、文本处理 |
| **描述属性** | Agent 的详细描述 | 专注于数据可视化的AI助手 |
| **工具集成** | 绑定的 MCP 工具 | 数据库连接器、API调用器 |

---

## 🛠️ Processor 管理

### ⚠️ 重要提醒

> **用户和 Agent 只有被注册为 Processor 才能被工作流调用！**

### 1. 创建 Processor

#### 处理器类型

- **用户处理器** 👤
  - 人工处理任务
  - 需要手动交互
  - 适合复杂决策场景

- **Agent 处理器** 🤖
  - AI 自动处理
  - 无人值守运行
  - 适合标准化流程

### 2. 绑定配置

#### 用户绑定 👥
` + '```json' + `
{
  "user_id": "user123",
  "capabilities": ["data_analysis", "report_writing"],
  "permissions": ["read", "write", "execute"],
  "status": "active"
}
` + '```' + `

#### Agent 绑定 🔗
` + '```json' + `
{
  "agent_id": "agent456",
  "call_parameters": {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "tools": ["calculator", "web_search"]
}
` + '```' + `

---

## 🔨 工具管理

### MCP 工具集成

#### 集成流程

1. **添加工具** - 在"我的工具"中添加 MCP 工具
2. **配置参数** - 设置工具参数和权限
3. **绑定 Agent** - 在 Agent 管理中添加工具
4. **验证测试** - 验证工具集成效果

#### 工具类型

| 工具类型 | 功能描述 | 使用场景 |
|---------|----------|----------|
| **数据库连接器** | 连接各类数据库 | 数据查询、更新操作 |
| **API 调用器** | 调用外部 API | 第三方服务集成 |
| **文件处理器** | 文件操作工具 | 文档生成、格式转换 |
| **计算工具** | 数学计算功能 | 数据分析、统计计算 |

### 工具配置

` + '```yaml' + `
# MCP 工具配置示例
tool_config:
  name: "database_connector"
  version: "1.0.0"
  permissions:
    - read_data
    - write_data
  parameters:
    connection_string: "postgresql://localhost:5432/mydb"
    timeout: 30
  authentication:
    type: "api_key"
    key: "` + '${API_KEY}' + `"
` + '```' + ``,

    tasks: `# ✅ 待办任务使用指南

## 📋 任务查看

### 1. 任务列表界面

\`\`\`
┌─────────────────────────────────────────┐
│ 📋 我的待办任务                          │
├─────────────────────────────────────────┤
│ 🔴 [高优先级] 数据分析报告               │
│ 🟡 [中优先级] 用户反馈处理               │
│ 🟢 [低优先级] 文档整理                   │
└─────────────────────────────────────────┘
\`\`\`

### 2. 筛选功能

| 筛选条件 | 选项 | 描述 |
|---------|------|------|
| **状态** | 待处理/进行中/已完成 | 按任务执行状态筛选 |
| **优先级** | 高/中/低 | 按任务重要性筛选 |
| **类型** | 个人任务/协作任务 | 按任务类型筛选 |
| **截止时间** | 今日/本周/本月 | 按时间期限筛选 |

### 3. 任务详情

> 📄 **任务信息包含：**
> - 任务描述和要求
> - 上下文信息和相关资料
> - 截止时间和优先级
> - 执行历史和状态记录

---

## 🎯 任务执行

### 1. 独立完成模式

\`\`\`mermaid
graph TD
    A[选择独立完成] --> B[点击开始任务]
    B --> C[按要求执行]
    C --> D[提交执行结果]
    D --> E[任务完成]
\`\`\`

#### 执行步骤
1. **任务启动** - 点击"开始任务"
2. **任务执行** - 按照任务要求进行操作
3. **结果提交** - 填写执行结果和相关信息
4. **状态更新** - 系统自动更新任务状态

### 2. 任务细分模式

#### 适用场景

> 🔍 **何时使用任务细分？**
> - 任务开始前觉得任务太复杂
> - 任务执行过程中发现需要细分
> - 需要多人协作完成的任务

#### 细分选项

- **复用工作流** 🔄
  - 选择现有的工作流模板
  - 快速启动标准化流程
  - 适合常见任务类型

- **创建新工作流** ⚡
  - 为当前任务创建专用工作流
  - 灵活定制处理步骤
  - 适合特殊需求场景

### 3. 子任务监控

#### 监控面板

\`\`\`
┌─────────────────────────────────────────┐
│ 📊 子工作流执行状态                      │
├─────────────────────────────────────────┤
│ ▶️  数据收集      [已完成] ✅           │
│ ⏸️  数据清洗      [执行中] 🔄           │
│ ⏹️  数据分析      [等待中] ⏳           │
│ ⏹️  报告生成      [等待中] ⏳           │
└─────────────────────────────────────────┘
\`\`\`

#### 监控功能
- **实时状态** - 查看子任务执行进度
- **执行日志** - 详细的执行过程记录
- **结果查看** - 子工作流的提交结果
- **异常处理** - 错误信息和处理建议

---

## 🤝 任务协作

### 1. 人机协作模式

#### 协作流程

\`\`\`javascript
// 人机协作示例
const collaborativeTask = {
  humanTasks: [
    "需求分析和确认",
    "质量检查和验收"
  ],
  agentTasks: [
    "数据处理和计算", 
    "报告自动生成"
  ],
  handoffPoints: [
    "数据处理完成后交给人工检查",
    "人工确认后自动生成最终报告"
  ]
}
\`\`\`

### 2. 任务分配策略

#### 智能分配

| 分配因素 | 权重 | 说明 |
|---------|------|------|
| **处理器能力** | 40% | 匹配任务需求和处理器专长 |
| **当前负载** | 30% | 考虑处理器当前工作量 |
| **历史表现** | 20% | 基于过往执行质量 |
| **任务优先级** | 10% | 高优先级任务优先分配 |

#### 手动调整

- **重新分配** - 管理员可手动调整任务分配
- **负载均衡** - 避免某个处理器负载过重
- **优先级调整** - 根据业务需要调整任务优先级

> 💡 **最佳实践**
> - 定期检查任务分配的合理性
> - 根据反馈调整分配策略
> - 保持人机协作的平衡`
  };

  return (
    <div style={{ padding: '24px', background: '#fff', borderRadius: '8px' }}>
      {/* 页面标题和操作按钮 */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '24px',
        borderBottom: '1px solid #f0f0f0',
        paddingBottom: '16px'
      }}>
        <Title level={2} style={{ margin: 0 }}>
          📚 使用说明
        </Title>
        
        <Space>
          <Button 
            icon={viewMode === 'rendered' ? <EyeOutlined /> : <EyeOutlined />}
            onClick={() => setViewMode(viewMode === 'rendered' ? 'raw' : 'rendered')}
            size="small"
          >
            {viewMode === 'rendered' ? '查看源码' : '渲染视图'}
          </Button>
          <Button 
            type="primary"
            icon={<DownloadOutlined />}
            onClick={exportMarkdown}
            size="small"
          >
            导出 Markdown
          </Button>
        </Space>
      </div>
      
      {/* Tab内容 */}
      <Tabs 
        defaultActiveKey="overview" 
        size="large"
        style={{ minHeight: '70vh' }}
        items={[
          {
            key: 'overview',
            label: '🏠 平台概述',
            children: (
              <Card 
                style={{ minHeight: '60vh' }}
                styles={{ body: { padding: viewMode === 'raw' ? '16px' : '32px' } }}
              >
                {viewMode === 'rendered' ? (
                  <MarkdownRenderer content={documentationContent.overview} />
                ) : (
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    backgroundColor: '#f8f9fa',
                    padding: '16px',
                    borderRadius: '6px',
                    border: '1px solid #e9ecef',
                    overflow: 'auto'
                  }}>
                    {documentationContent.overview}
                  </pre>
                )}
              </Card>
            )
          },
          {
            key: 'workflow',
            label: '🌊 工作流管理',
            children: (
              <Card 
                style={{ minHeight: '60vh' }}
                styles={{ body: { padding: viewMode === 'raw' ? '16px' : '32px' } }}
              >
                {viewMode === 'rendered' ? (
                  <MarkdownRenderer content={documentationContent.workflow} />
                ) : (
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    backgroundColor: '#f8f9fa',
                    padding: '16px',
                    borderRadius: '6px',
                    border: '1px solid #e9ecef',
                    overflow: 'auto'
                  }}>
                    {documentationContent.workflow}
                  </pre>
                )}
              </Card>
            )
          },
          {
            key: 'resource',
            label: '🔧 资源管理',
            children: (
              <Card 
                style={{ minHeight: '60vh' }}
                styles={{ body: { padding: viewMode === 'raw' ? '16px' : '32px' } }}
              >
                {viewMode === 'rendered' ? (
                  <MarkdownRenderer content={documentationContent.resource} />
                ) : (
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    backgroundColor: '#f8f9fa',
                    padding: '16px',
                    borderRadius: '6px',
                    border: '1px solid #e9ecef',
                    overflow: 'auto'
                  }}>
                    {documentationContent.resource}
                  </pre>
                )}
              </Card>
            )
          },
          {
            key: 'tasks',
            label: '✅ 待办任务',
            children: (
              <Card 
                style={{ minHeight: '60vh' }}
                styles={{ body: { padding: viewMode === 'raw' ? '16px' : '32px' } }}
              >
                {viewMode === 'rendered' ? (
                  <MarkdownRenderer content={documentationContent.tasks} />
                ) : (
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
                    fontSize: '13px',
                    lineHeight: '1.6',
                    backgroundColor: '#f8f9fa',
                    padding: '16px',
                    borderRadius: '6px',
                    border: '1px solid #e9ecef',
                    overflow: 'auto'
                  }}>
                    {documentationContent.tasks}
                  </pre>
                )}
              </Card>
            )
          }
        ]}
      />
      
      {/* 底部提示 */}
      <Alert
        style={{ marginTop: '24px' }}
        message="💡 使用提示"
        description={
          <div>
            <p>• <strong>渲染视图</strong>：以美观的格式查看文档，支持语法高亮、表格、链接等交互功能</p>
            <p>• <strong>源码模式</strong>：查看原始 Markdown 源码，便于复制和编辑</p>
            <p>• <strong>导出功能</strong>：将完整文档导出为 .md 文件，便于离线查看或分享</p>
            <p>• 如需更多帮助，请联系系统管理员或查看详细技术文档</p>
          </div>
        }
        type="info"
        showIcon
      />
    </div>
  );
};

export default Help;