# 人类任务执行完整指南

## 🎯 概述

本指南详细介绍了工作流框架中人类用户如何执行任务的完整流程，包括API调用、数据结构和最佳实践。

## 📋 完整执行流程

### 1. 用户登录和认证

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "analyst@company.com",
  "password": "your_password"
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user_info": {
      "user_id": "uuid",
      "username": "analyst@company.com",
      "role": "user"
    }
  }
}
```

### 2. 获取分配的任务列表

```http
GET /api/execution/tasks/my?status=assigned&limit=20
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "success": true,
  "data": [
    {
      "task_instance_id": "task-uuid-1",
      "task_title": "用户行为数据分析任务",
      "task_description": "分析Q1用户行为数据，识别关键趋势",
      "status": "assigned",
      "priority": 2,
      "priority_label": "中优先级",
      "estimated_duration": 120,
      "created_at": "2024-01-15T14:30:00Z",
      "assigned_at": "2024-01-15T14:35:00Z",
      "estimated_deadline": "2024-01-15T16:35:00Z"
    }
  ],
  "message": "获取任务列表成功"
}
```

### 3. 查看任务详情和上下文

这是关键步骤！用户点击任务后看到完整的任务信息：

```http
GET /api/execution/tasks/{task_id}
Authorization: Bearer <access_token>
```

**完整响应结构**:
```json
{
  "success": true,
  "data": {
    // ===== 任务基本信息 =====
    "task_instance_id": "task-uuid-1",
    "task_title": "用户行为数据分析任务",
    "task_description": "分析Q1用户行为数据，识别关键趋势和模式，为产品优化提供数据支持",
    "instructions": "请基于上游节点提供的数据完成以下分析：\n1. 分析用户行为趋势\n2. 识别关键用户群体\n3. 提出改进建议",
    "status": "assigned",
    "priority": 2,
    "priority_label": "中优先级",
    "estimated_duration": 120,
    "estimated_deadline": "2024-01-15T16:35:00Z",
    
    // ===== 时间信息 =====
    "created_at": "2024-01-15T14:30:00Z",
    "assigned_at": "2024-01-15T14:35:00Z",
    "started_at": null,
    "completed_at": null,
    
    // ===== 工作流上下文 =====
    "workflow_context": {
      "workflow_name": "Q1用户行为分析工作流",
      "workflow_description": "分析第一季度用户行为数据的完整工作流",
      "workflow_version": 1,
      "instance_name": "2024年Q1用户行为分析实例",
      "instance_description": "第一季度用户行为深度分析",
      "workflow_input_data": {
        "analysis_period": "2024-Q1",
        "target_segments": ["新用户", "活跃用户", "流失用户"],
        "data_sources": ["web_logs", "app_logs", "user_profiles"]
      },
      "workflow_context_data": {
        "analyst_team": "数据科学团队",
        "stakeholders": ["产品经理", "运营团队"],
        "report_deadline": "2024-01-20T18:00:00Z"
      }
    },
    
    // ===== 节点上下文 =====
    "node_context": {
      "node_name": "数据分析处理节点",
      "node_description": "对预处理后的数据进行深度分析和洞察提取",
      "node_type": "PROCESSOR",
      "node_instance_id": "node-instance-uuid"
    },
    
    // ===== 处理器信息 =====
    "processor_context": {
      "processor_name": "高级数据分析师",
      "processor_type": "human",
      "processor_description": "需要具备数据分析和统计学背景的专业人员"
    },
    
    // ===== 上游节点数据（核心信息）=====
    "upstream_context": {
      "immediate_upstream_results": {
        "data-collection-node-uuid": {
          "node_name": "数据收集节点",
          "output_data": {
            "raw_data_path": "/data/user_behavior_2024q1.csv",
            "total_records": 150000,
            "data_quality_metrics": {
              "completeness": 0.98,
              "accuracy": 0.95,
              "consistency": 0.93
            },
            "collection_summary": "成功收集15万条用户行为记录，数据质量优秀"
          },
          "completed_at": "2024-01-15T14:00:00Z",
          "summary": "收集了15万条用户行为记录，数据质量良好"
        },
        "data-preprocessing-node-uuid": {
          "node_name": "数据预处理节点",
          "output_data": {
            "cleaned_data_path": "/data/cleaned_user_behavior_2024q1.csv",
            "records_after_cleaning": 145000,
            "removed_duplicates": 3000,
            "filled_missing_values": 2000,
            "outliers_removed": 500,
            "cleaning_report": {
              "duplicate_rate": 0.02,
              "missing_value_rate": 0.013,
              "outlier_rate": 0.003
            }
          },
          "completed_at": "2024-01-15T14:20:00Z",
          "summary": "数据清洗完成，保留14.5万有效记录，质量显著提升"
        }
      },
      "upstream_node_count": 2,
      "workflow_global_data": {
        "execution_path": ["start_node", "data_collection_node", "data_preprocessing_node"],
        "global_data": {
          "project_id": "PROJ_2024_Q1_001",
          "department": "产品数据部",
          "budget_allocated": 50000,
          "timeline": "2024-01-15 to 2024-01-30"
        },
        "execution_start_time": "2024-01-15T13:30:00Z"
      },
      "workflow_execution_path": ["start_node", "data_collection_node", "data_preprocessing_node"],
      "workflow_start_time": "2024-01-15T13:30:00Z",
      "has_upstream_data": true
    },
    
    // ===== 其他信息 =====
    "assigned_user_id": "user-uuid",
    "retry_count": 0
  },
  "message": "获取任务详情成功"
}
```

### 4. 开始执行任务

用户查看完任务详情后，点击"开始任务"：

```http
POST /api/execution/tasks/{task_id}/start
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid-1",
    "status": "in_progress",
    "started_at": "2024-01-15T15:00:00Z",
    "message": "任务已开始执行"
  }
}
```

### 5. 提交任务结果

用户基于上游数据完成分析后，提交结果：

```http
POST /api/execution/tasks/{task_id}/submit
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "result_data": {
    "user_behavior_analysis": {
      "total_users_analyzed": 145000,
      "analysis_summary": "基于Q1用户行为数据的深度分析结果",
      "key_findings": [
        "移动端用户占比达到72%，较去年同期增长15%",
        "用户活跃时间集中在晚上8-10点，周末活跃度提升25%",
        "新用户7日留存率为47%，略高于行业均值45%",
        "付费转化率为13.5%，同比增长8%"
      ],
      "user_segments": {
        "high_value_users": {
          "count": 18500,
          "percentage": 0.128,
          "characteristics": "高频使用，多次付费，平均会话时长12分钟",
          "retention_rate": 0.87,
          "revenue_contribution": 0.65
        },
        "active_users": {
          "count": 72500,
          "percentage": 0.50,
          "characteristics": "定期使用，偶尔付费，平均会话时长8分钟",
          "retention_rate": 0.68,
          "revenue_contribution": 0.28
        },
        "casual_users": {
          "count": 54000,
          "percentage": 0.372,
          "characteristics": "低频使用，很少付费，平均会话时长5分钟",
          "retention_rate": 0.31,
          "revenue_contribution": 0.07
        }
      },
      "behavioral_patterns": {
        "peak_usage_hours": ["20:00-22:00", "12:00-13:00", "18:00-19:00"],
        "popular_features": [
          {"feature": "内容浏览", "usage_rate": 0.95},
          {"feature": "社交互动", "usage_rate": 0.68},
          {"feature": "购买功能", "usage_rate": 0.24}
        ],
        "user_journey_insights": {
          "average_steps_to_conversion": 5.2,
          "most_common_exit_point": "支付页面",
          "successful_conversion_path": "首页->产品页->详情页->购物车->支付"
        }
      },
      "key_metrics": {
        "daily_active_users": 8500,
        "monthly_active_users": 42000,
        "session_duration_avg": 8.7,
        "bounce_rate": 0.23,
        "conversion_rate": 0.135,
        "churn_rate": 0.142,
        "customer_satisfaction_score": 4.2
      },
      "trend_analysis": {
        "growth_trends": {
          "user_acquisition_rate": "+12% MoM",
          "engagement_rate": "+8% MoM",
          "revenue_per_user": "+15% MoM"
        },
        "seasonal_patterns": [
          "周末活跃度比工作日高25%",
          "月初用户付费意愿更强",
          "节假日前用户活跃度显著提升"
        ]
      },
      "recommendations": [
        {
          "priority": "high",
          "category": "用户体验优化",
          "action": "优化移动端界面设计和交互流程",
          "rationale": "移动端用户占主体且增长迅速",
          "expected_impact": "预计提升整体DAU 10-15%，用户满意度提升0.3分",
          "implementation_timeline": "2-3周",
          "resources_needed": ["UI/UX设计师", "前端开发工程师"]
        },
        {
          "priority": "high",
          "action": "设计个性化晚间推送策略",
          "rationale": "用户晚间活跃度最高，是推送的黄金时间",
          "expected_impact": "预计提升用户参与度12-18%，推送点击率提升至8%",
          "implementation_timeline": "1-2周",
          "resources_needed": ["数据科学家", "产品经理", "后端开发"]
        },
        {
          "priority": "medium",
          "action": "优化新用户引导流程",
          "rationale": "新用户留存率有进一步提升空间",
          "expected_impact": "预计新用户7日留存率提升至55%",
          "implementation_timeline": "3-4周",
          "resources_needed": ["产品设计师", "用户研究员"]
        },
        {
          "priority": "medium",
          "action": "改进支付流程，减少支付页面流失",
          "rationale": "支付页面是主要流失点，优化后可显著提升转化",
          "expected_impact": "预计整体转化率提升至16%",
          "implementation_timeline": "2-3周",
          "resources_needed": ["支付系统工程师", "UI设计师"]
        }
      ],
      "visualization_suggestions": [
        {
          "chart_type": "热力图",
          "title": "用户活跃时间分布热力图",
          "description": "显示24小时内用户活跃度变化",
          "data_source": "hourly_activity_data"
        },
        {
          "chart_type": "漏斗图",
          "title": "用户转化路径漏斗图",
          "description": "展示从访问到付费的转化过程",
          "data_source": "conversion_funnel_data"
        },
        {
          "chart_type": "桑基图",
          "title": "用户行为流转桑基图",
          "description": "可视化用户在不同功能间的流转",
          "data_source": "user_flow_data"
        },
        {
          "chart_type": "趋势图",
          "title": "用户留存率趋势图",
          "description": "显示不同时期用户留存情况",
          "data_source": "retention_trend_data"
        }
      ]
    },
    "data_quality_assessment": {
      "source_data_quality": {
        "completeness_score": 0.95,
        "accuracy_score": 0.92,
        "consistency_score": 0.89,
        "timeliness_score": 0.96
      },
      "analysis_confidence": {
        "overall_confidence": 0.91,
        "statistical_significance": 0.95,
        "sample_representativeness": 0.88
      },
      "limitations_and_caveats": [
        "部分新用户（约8%）缺少完整的行为轨迹数据",
        "地理位置信息缺失率约12%，可能影响地域分析准确性",
        "节假日数据样本相对较少，季节性分析需要更多历史数据"
      ],
      "data_sources_used": [
        "用户行为日志（覆盖率98%）",
        "用户画像数据（覆盖率85%）",
        "交易记录（覆盖率100%）",
        "客服反馈数据（覆盖率45%）"
      ]
    },
    "methodology": {
      "analysis_approach": "基于描述性统计、群组分析和行为路径分析的综合方法",
      "statistical_methods": [
        "群组分析（Cohort Analysis）",
        "漏斗分析（Funnel Analysis）",
        "RFM分析（Recency, Frequency, Monetary）",
        "A/B测试结果分析"
      ],
      "tools_and_technologies": [
        "Python (Pandas, NumPy, Scikit-learn)",
        "SQL查询和数据处理",
        "Matplotlib和Seaborn可视化",
        "Jupyter Notebook分析环境"
      ],
      "validation_methods": [
        "交叉验证统计结果",
        "与历史数据对比验证",
        "业务逻辑一致性检查"
      ]
    },
    "next_steps": {
      "immediate_actions": [
        "将分析结果提交给产品团队review",
        "准备面向管理层的汇报PPT",
        "与设计和开发团队讨论优化方案的可行性"
      ],
      "follow_up_analysis": [
        "进行用户细分的深度分析",
        "分析不同渠道用户的行为差异",
        "建立用户价值预测模型"
      ],
      "monitoring_recommendations": [
        "建立关键指标的实时监控dashboard",
        "设置用户行为异常检测警报",
        "定期（每月）更新用户分群分析"
      ]
    },
    "analysis_metadata": {
      "analyst_name": "高级数据分析师",
      "analysis_start_time": "2024-01-15T15:00:00Z",
      "analysis_completion_time": "2024-01-15T16:45:00Z",
      "total_analysis_duration_minutes": 105,
      "data_processing_time_minutes": 25,
      "analysis_and_insights_time_minutes": 60,
      "report_writing_time_minutes": 20,
      "code_version": "analysis_v2.1.3",
      "environment": "production_data_warehouse"
    }
  },
  "result_summary": "完成了2024年Q1用户行为数据的全面深度分析。通过对14.5万用户的行为数据进行综合分析，识别出三个主要用户群体，发现了移动端用户增长、晚间活跃高峰、支付流程优化等关键洞察。提出了4项高中优先级的改进建议，预期可带来10-18%的关键指标提升。分析结果具有91%的置信度，为产品优化和用户增长策略提供了强有力的数据支撑。"
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid-1",
    "status": "completed",
    "completed_at": "2024-01-15T16:45:00Z",
    "actual_duration": 105,
    "message": "任务结果已成功提交"
  }
}
```

## 🔄 工作流自动推进

任务提交后，系统会自动：

1. **更新任务状态**为 `completed`
2. **保存分析结果**到 `output_data` 字段
3. **检查下游节点**的依赖条件
4. **自动创建下游任务**，并将当前任务的结果作为上游数据传递

例如，下游可能创建的任务：
- **报告生成任务**: 基于分析结果生成正式报告
- **可视化任务**: 制作图表和仪表板
- **决策支持任务**: 基于建议制定具体执行计划

## 📊 关键特性

### ✅ **严格的依赖等待**
- 用户只能看到直接上游节点（一阶）的输出数据
- 必须等待所有上游节点完成才能开始执行

### ✅ **丰富的上下文信息**
- **任务基本信息**: 标题、描述、指令、优先级
- **工作流背景**: 工作流名称、实例信息、全局数据
- **上游数据**: 前序节点的具体输出结果
- **执行指导**: 明确的任务要求和期望

### ✅ **智能数据处理**  
- **权限验证**: 确保用户只能访问自己的任务
- **数据摘要**: 自动提取上游数据的关键信息
- **时间追踪**: 详细记录任务执行时间

### ✅ **自动工作流推进**
- 任务完成后自动触发下游节点
- 结果数据自动传递给下游任务
- 无需人工干预的流程推进

## 🎯 最佳实践

### 对于用户：
1. **仔细查看上游数据**：充分理解前序节点提供的信息
2. **遵循任务指令**：按照 `instructions` 字段的要求执行
3. **提供结构化结果**：使用清晰的JSON结构组织分析结果
4. **编写详细总结**：在 `result_summary` 中提供简洁但全面的总结

### 对于开发者：
1. **确保数据完整性**：上游节点应提供充分的输出数据
2. **设计清晰的任务描述**：让用户明确知道期望的输出
3. **合理设置优先级**：帮助用户合理安排工作顺序
4. **监控任务执行**：及时发现和处理异常情况

这样的设计确保了用户能够基于完整的上下文信息高质量地完成任务，同时保证了工作流的连续性和数据的有效传递！