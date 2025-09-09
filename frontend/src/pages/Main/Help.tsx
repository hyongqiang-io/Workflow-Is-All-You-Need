import React, { useState, useEffect } from 'react';
import { Card, Tabs, Typography, Spin, Alert } from 'antd';

const { Title, Paragraph, Text } = Typography;
const { TabPane } = Tabs;

const Help: React.FC = () => {
  const [loading, setLoading] = useState(false);

  const documentationContent = {
    overview: `
# Autoflow 工作流自动化平台使用说明

## 平台简介

Autoflow 是一个智能工作流自动化平台，支持 Agent 管理、人机协作和工作流的创建、执行与监控。

## 核心功能

### 🎯 仪表板 (Dashboard)
- 查看总体资源状况
- 监控待办任务数量  
- 用户和 Agent 统计概览

### 🔧 资源管理
- **资源概况**：查看所有 Agent 和用户
- **Agent 管理**：创建、编辑和配置 Agent
- **Processor 管理**：用户和 Agent 处理器注册
- **我的工具**：MCP 工具集成和管理

### 🌊 工作流管理  
- **工作流模板**：创建、编辑、导入导出工作流模板
- **执行记录**：查看工作流实例化执行情况
- **AI 生成**：智能生成工作流模板
- **模板合并**：支持子工作流递归合并

### ✅ 待办任务
- 查看分配给自己的任务
- 任务执行和结果提交
- 任务细分和工作流创建
- 子任务状态监控

### 👤 个人中心
- 修改邮箱和个人信息
- 添加个人描述

## 快速开始

1. **注册登录** → 访问平台并创建账号
2. **创建 Agent** → 在资源管理中注册 Agent
3. **注册 Processor** → 将用户/Agent 注册为处理器
4. **创建工作流** → 设计自己的自动化流程
5. **执行工作流** → 实例化模板并监控执行
`,
    workflow: `
# 工作流管理详细指南

## 工作流模板创建

### 1. 创建流程
1. 点击"工作流管理" → "创建工作流"
2. 选择节点类型：
   - **开始节点**：工作流入口点
   - **中间节点**：处理业务逻辑
   - **结束节点**：工作流出口点
3. 添加节点并连接关系
4. 为处理节点绑定 Processor（Agent 或人工）
5. 保存工作流模板

### 2. 节点配置
- **开始节点**：定义输入参数和触发条件
- **处理节点**：绑定具体的处理器，配置任务描述
- **结束节点**：定义输出结果和完成条件

### 3. AI 智能生成
- 使用 AI 功能自动生成工作流模板
- 支持自然语言描述转换为工作流

### 4. 工作流执行
- **执行**：将模板实例化为具体任务
- **监控**：实时查看执行状态和进度
- **查看详情**：节点级别的执行情况
- **图形视图**：可视化展示整个工作流状态

## 工作流操作

### 导入导出
- **导出**：将工作流模板保存为 JSON 格式
- **导入**：从 JSON 文件加载工作流模板

### 模板合并
- 支持子工作流细分后的递归合并
- 可以用细分工作流替代原有工作节点
- 合并后生成新的工作流模板

### 编辑管理
- 实时编辑工作流模板
- 删除不需要的模板
- 版本控制和历史记录
`,
    resource: `
# 资源管理详细说明

## Agent 管理

### 1. 创建 Agent
1. 进入"资源管理" → "Agent 管理"
2. 点击"创建单个 agent"
3. 填写 Agent 基本信息
4. 创建完成后需要创建对应的 Processor

### 2. Agent 配置
- 配置 Agent 的处理能力
- 设置 Agent 的描述和属性
- 添加 MCP 工具集成

## Processor 管理

### ⚠️ 重要提醒
**用户和 Agent 只有被注册为 Processor 才能被工作流调用！**

### 1. 创建 Processor
1. 点击"资源管理" → "Processor 管理"
2. 选择处理器类型：
   - **用户处理器**：人工处理任务
   - **Agent 处理器**：AI 自动处理
3. 进行绑定关联

### 2. 用户绑定
- 关联用户账号到 Processor
- 设置用户的处理能力和权限
- 查看绑定状态

### 3. Agent 绑定
- 将 Agent 绑定到 Processor
- 配置 Agent 的调用参数
- 验证绑定有效性

## 工具管理

### MCP 工具集成
1. 在"我的工具"中添加 MCP 工具
2. 配置工具参数和权限
3. 在 Agent 管理中编辑 Agent，添加 MCP 工具
4. 验证工具集成效果

### 工具配置
- 设置工具的调用权限
- 配置工具参数
- 监控工具使用情况
`,
    tasks: `
# 待办任务使用指南

## 任务查看

### 1. 任务列表
- 查看分配给自己的所有任务
- 按状态、优先级筛选任务
- 查看任务详细描述

### 2. 任务详情
- 点击"查看详情"了解任务要求
- 查看任务的上下文信息
- 了解任务的截止时间和优先级

## 任务执行

### 1. 独立完成
1. 选择"独立完成"
2. 点击"开始任务"
3. 按要求执行任务
4. 完成后提交结果

### 2. 任务细分
**在以下情况可以选择拆解任务：**
- 任务开始前觉得任务太复杂
- 任务执行过程中发现需要细分

**细分选项：**
- **复用工作流**：选择现有的工作流模板
- **创建新工作流**：为当前任务创建专用工作流

### 3. 子任务监控
- 在"查看详情"中查看子工作流状态
- 监控子任务的执行进度
- 查看子工作流的提交结果

## 任务协作

### 1. 人机协作
- 人工任务和 Agent 任务的协同执行
- 任务间的依赖关系管理
- 结果传递和数据流转

### 2. 任务分配
- 根据处理器能力自动分配
- 支持手动调整任务分配
- 负载均衡和优先级管理
`
  };

  return (
    <div style={{ padding: '24px', background: '#fff', borderRadius: '8px' }}>
      <Title level={2} style={{ marginBottom: '24px', textAlign: 'center' }}>
        使用说明
      </Title>
      
      <Tabs defaultActiveKey="overview" size="large">
        <TabPane tab="平台概述" key="overview">
          <Card>
            <div style={{ whiteSpace: 'pre-line', lineHeight: '1.8' }}>
              {documentationContent.overview}
            </div>
          </Card>
        </TabPane>
        
        <TabPane tab="工作流管理" key="workflow">
          <Card>
            <div style={{ whiteSpace: 'pre-line', lineHeight: '1.8' }}>
              {documentationContent.workflow}
            </div>
          </Card>
        </TabPane>
        
        <TabPane tab="资源管理" key="resource">
          <Card>
            <div style={{ whiteSpace: 'pre-line', lineHeight: '1.8' }}>
              {documentationContent.resource}
            </div>
          </Card>
        </TabPane>
        
        <TabPane tab="待办任务" key="tasks">
          <Card>
            <div style={{ whiteSpace: 'pre-line', lineHeight: '1.8' }}>
              {documentationContent.tasks}
            </div>
          </Card>
        </TabPane>
      </Tabs>
      
      <Alert
        style={{ marginTop: '24px' }}
        message="提示"
        description="如需更多帮助，请联系系统管理员或查看详细技术文档。"
        type="info"
        showIcon
      />
    </div>
  );
};

export default Help;