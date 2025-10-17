"""
用户交互跟踪数据库表结构
Database schema for user interaction tracking
"""

# 用户交互日志表
USER_INTERACTION_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS `user_interaction_logs` (
    `interaction_id` VARCHAR(36) PRIMARY KEY COMMENT '交互记录唯一标识',
    `user_id` VARCHAR(36) NOT NULL COMMENT '用户ID',
    `workflow_id` VARCHAR(36) NULL COMMENT '工作流ID',
    `session_id` VARCHAR(36) NOT NULL COMMENT '会话ID',

    `event_type` ENUM(
        'suggestion_shown',
        'suggestion_accepted',
        'suggestion_rejected',
        'suggestion_ignored',
        'trigger_activated',
        'session_started',
        'session_ended'
    ) NOT NULL COMMENT '交互事件类型',

    `suggestion_type` ENUM('node', 'edge', 'workflow_completion') NULL COMMENT '建议类型',

    `suggestion_data` JSON NULL COMMENT '建议详细数据',
    `context_data` JSON NULL COMMENT '上下文数据',
    `metadata` JSON NULL COMMENT '额外元数据',

    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',

    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_workflow_id` (`workflow_id`),
    INDEX `idx_session_id` (`session_id`),
    INDEX `idx_event_type` (`event_type`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_user_event_time` (`user_id`, `event_type`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户Tab补全交互日志表';
"""

# 用户行为模式表（预计算的分析结果）
USER_BEHAVIOR_PATTERNS_TABLE = """
CREATE TABLE IF NOT EXISTS `user_behavior_patterns` (
    `pattern_id` VARCHAR(36) PRIMARY KEY COMMENT '模式记录唯一标识',
    `user_id` VARCHAR(36) NOT NULL COMMENT '用户ID',

    `analysis_period_start` TIMESTAMP NOT NULL COMMENT '分析期间开始时间',
    `analysis_period_end` TIMESTAMP NOT NULL COMMENT '分析期间结束时间',

    -- 统计数据
    `total_events` INT DEFAULT 0 COMMENT '总事件数',
    `suggestions_shown` INT DEFAULT 0 COMMENT '显示建议数',
    `suggestions_accepted` INT DEFAULT 0 COMMENT '接受建议数',
    `suggestions_rejected` INT DEFAULT 0 COMMENT '拒绝建议数',
    `acceptance_rate` DECIMAL(5,4) DEFAULT 0.0000 COMMENT '接受率',

    -- 偏好数据
    `preferred_suggestion_type` ENUM('node', 'edge', 'mixed') DEFAULT 'mixed' COMMENT '偏好的建议类型',
    `confidence_threshold` DECIMAL(4,3) DEFAULT 0.500 COMMENT '置信度阈值偏好',
    `confidence_sensitivity` ENUM('low', 'medium', 'high') DEFAULT 'medium' COMMENT '置信度敏感度',

    -- 使用模式
    `most_active_hour` TINYINT DEFAULT 10 COMMENT '最活跃时间（小时）',
    `avg_session_length_minutes` DECIMAL(8,2) DEFAULT 0.00 COMMENT '平均会话长度（分钟）',
    `workflow_complexity_preference` ENUM('simple', 'medium', 'complex') DEFAULT 'medium' COMMENT '工作流复杂度偏好',

    -- 分析结果
    `behavior_score` DECIMAL(5,4) DEFAULT 0.0000 COMMENT '行为评分（0-1）',
    `engagement_level` ENUM('low', 'medium', 'high') DEFAULT 'medium' COMMENT '参与度级别',
    `recommendations` JSON NULL COMMENT '个性化推荐',

    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',

    UNIQUE KEY `unique_user_period` (`user_id`, `analysis_period_start`, `analysis_period_end`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_analysis_period` (`analysis_period_start`, `analysis_period_end`),
    INDEX `idx_acceptance_rate` (`acceptance_rate`),
    INDEX `idx_behavior_score` (`behavior_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户行为模式分析表';
"""

# 建议效果跟踪表
SUGGESTION_EFFECTIVENESS_TABLE = """
CREATE TABLE IF NOT EXISTS `suggestion_effectiveness` (
    `effectiveness_id` VARCHAR(36) PRIMARY KEY COMMENT '效果记录唯一标识',
    `suggestion_id` VARCHAR(36) NOT NULL COMMENT '建议ID（来源于交互日志）',
    `user_id` VARCHAR(36) NOT NULL COMMENT '用户ID',
    `workflow_id` VARCHAR(36) NULL COMMENT '工作流ID',

    `suggestion_type` ENUM('node', 'edge', 'workflow_completion') NOT NULL COMMENT '建议类型',
    `suggestion_confidence` DECIMAL(4,3) NOT NULL COMMENT '建议置信度',
    `suggestion_reasoning` TEXT NULL COMMENT '建议理由',

    `user_action` ENUM('accepted', 'rejected', 'ignored', 'modified') NOT NULL COMMENT '用户操作',
    `action_timestamp` TIMESTAMP NOT NULL COMMENT '操作时间',
    `time_to_decision_seconds` INT DEFAULT 0 COMMENT '决策时间（秒）',

    -- 上下文信息
    `workflow_node_count` INT DEFAULT 0 COMMENT '工作流节点数量',
    `workflow_edge_count` INT DEFAULT 0 COMMENT '工作流连接数量',
    `workflow_complexity_score` DECIMAL(4,3) DEFAULT 0.000 COMMENT '工作流复杂度分数',

    -- 效果评估
    `effectiveness_score` DECIMAL(4,3) NULL COMMENT '效果评分（后续计算）',
    `user_satisfaction` ENUM('very_low', 'low', 'medium', 'high', 'very_high') NULL COMMENT '用户满意度（可选）',

    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',

    INDEX `idx_suggestion_id` (`suggestion_id`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_workflow_id` (`workflow_id`),
    INDEX `idx_suggestion_type` (`suggestion_type`),
    INDEX `idx_user_action` (`user_action`),
    INDEX `idx_confidence` (`suggestion_confidence`),
    INDEX `idx_effectiveness_score` (`effectiveness_score`),
    INDEX `idx_action_timestamp` (`action_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='建议效果跟踪表';
"""

# 全局统计表
GLOBAL_TAB_COMPLETION_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS `global_tab_completion_stats` (
    `stat_id` VARCHAR(36) PRIMARY KEY COMMENT '统计记录唯一标识',
    `stat_date` DATE NOT NULL COMMENT '统计日期',

    -- 基础统计
    `total_interactions` INT DEFAULT 0 COMMENT '总交互数',
    `unique_users` INT DEFAULT 0 COMMENT '独立用户数',
    `unique_workflows` INT DEFAULT 0 COMMENT '独立工作流数',

    -- 建议统计
    `total_suggestions_shown` INT DEFAULT 0 COMMENT '总建议显示数',
    `total_suggestions_accepted` INT DEFAULT 0 COMMENT '总建议接受数',
    `total_suggestions_rejected` INT DEFAULT 0 COMMENT '总建议拒绝数',
    `global_acceptance_rate` DECIMAL(5,4) DEFAULT 0.0000 COMMENT '全局接受率',

    -- 分类统计
    `node_suggestions_shown` INT DEFAULT 0 COMMENT '节点建议显示数',
    `node_suggestions_accepted` INT DEFAULT 0 COMMENT '节点建议接受数',
    `edge_suggestions_shown` INT DEFAULT 0 COMMENT '连接建议显示数',
    `edge_suggestions_accepted` INT DEFAULT 0 COMMENT '连接建议接受数',

    -- 质量指标
    `avg_confidence_accepted` DECIMAL(4,3) DEFAULT 0.000 COMMENT '被接受建议的平均置信度',
    `avg_confidence_rejected` DECIMAL(4,3) DEFAULT 0.000 COMMENT '被拒绝建议的平均置信度',
    `avg_decision_time_seconds` DECIMAL(8,2) DEFAULT 0.00 COMMENT '平均决策时间（秒）',

    -- 系统性能
    `avg_prediction_time_ms` DECIMAL(8,2) DEFAULT 0.00 COMMENT '平均预测时间（毫秒）',
    `prediction_success_rate` DECIMAL(5,4) DEFAULT 0.0000 COMMENT '预测成功率',

    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',

    UNIQUE KEY `unique_stat_date` (`stat_date`),
    INDEX `idx_stat_date` (`stat_date`),
    INDEX `idx_acceptance_rate` (`global_acceptance_rate`),
    INDEX `idx_unique_users` (`unique_users`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tab补全全局统计表';
"""

# 用户会话表
USER_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS `user_tab_completion_sessions` (
    `session_id` VARCHAR(36) PRIMARY KEY COMMENT '会话唯一标识',
    `user_id` VARCHAR(36) NOT NULL COMMENT '用户ID',
    `workflow_id` VARCHAR(36) NULL COMMENT '工作流ID',

    `session_start` TIMESTAMP NOT NULL COMMENT '会话开始时间',
    `session_end` TIMESTAMP NULL COMMENT '会话结束时间',
    `session_duration_seconds` INT NULL COMMENT '会话持续时间（秒）',

    -- 会话统计
    `total_triggers` INT DEFAULT 0 COMMENT '触发次数',
    `total_suggestions_shown` INT DEFAULT 0 COMMENT '显示建议总数',
    `total_suggestions_accepted` INT DEFAULT 0 COMMENT '接受建议总数',
    `total_suggestions_rejected` INT DEFAULT 0 COMMENT '拒绝建议总数',
    `session_acceptance_rate` DECIMAL(5,4) DEFAULT 0.0000 COMMENT '会话接受率',

    -- 会话特征
    `initial_workflow_nodes` INT DEFAULT 0 COMMENT '初始工作流节点数',
    `final_workflow_nodes` INT DEFAULT 0 COMMENT '最终工作流节点数',
    `nodes_added_via_suggestions` INT DEFAULT 0 COMMENT '通过建议添加的节点数',

    `user_agent` TEXT NULL COMMENT '用户代理信息',
    `ip_address` VARCHAR(45) NULL COMMENT 'IP地址',

    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',

    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_workflow_id` (`workflow_id`),
    INDEX `idx_session_start` (`session_start`),
    INDEX `idx_session_duration` (`session_duration_seconds`),
    INDEX `idx_acceptance_rate` (`session_acceptance_rate`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户Tab补全会话表';
"""

# 所有表的创建脚本列表
ALL_TAB_COMPLETION_TABLES = [
    USER_INTERACTION_LOGS_TABLE,
    USER_BEHAVIOR_PATTERNS_TABLE,
    SUGGESTION_EFFECTIVENESS_TABLE,
    GLOBAL_TAB_COMPLETION_STATS_TABLE,
    USER_SESSIONS_TABLE
]

# 表结构说明
TABLE_DESCRIPTIONS = {
    'user_interaction_logs': """
    用户交互日志表 - 核心表
    记录用户与Tab补全系统的所有交互事件，包括建议显示、接受、拒绝等。
    支持实时分析和历史回溯。
    """,

    'user_behavior_patterns': """
    用户行为模式表 - 分析表
    存储基于交互日志预计算的用户行为分析结果，包括偏好、使用模式等。
    定期更新，支持个性化推荐。
    """,

    'suggestion_effectiveness': """
    建议效果跟踪表 - 评估表
    跟踪每个建议的具体效果，包括用户反应、决策时间、满意度等。
    用于评估和优化AI预测模型。
    """,

    'global_tab_completion_stats': """
    全局统计表 - 汇总表
    按日期汇总全局Tab补全使用统计，包括接受率、用户数、性能指标等。
    用于系统监控和产品决策。
    """,

    'user_tab_completion_sessions': """
    用户会话表 - 会话表
    记录用户完整的Tab补全使用会话，从开始到结束的完整过程。
    用于会话级别的分析和用户体验优化。
    """
}

def get_create_table_sql():
    """获取所有表的创建SQL"""
    return ALL_TAB_COMPLETION_TABLES

def get_table_descriptions():
    """获取表结构说明"""
    return TABLE_DESCRIPTIONS