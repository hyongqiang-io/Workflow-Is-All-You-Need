"""
任务对话数据库表结构
Task Conversation Database Schema
"""

-- 任务对话会话表
CREATE TABLE IF NOT EXISTS task_conversation_session (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_instance_id UUID NOT NULL REFERENCES task_instance(task_instance_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,

    -- 索引
    INDEX idx_task_conversation_session_task_id (task_instance_id),
    INDEX idx_task_conversation_session_user_id (user_id),
    INDEX idx_task_conversation_session_created_at (created_at)
);

-- 对话消息表
CREATE TABLE IF NOT EXISTS task_conversation_message (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES task_conversation_session(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    context_data JSONB,
    attachments JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 索引
    INDEX idx_task_conversation_message_session_id (session_id),
    INDEX idx_task_conversation_message_role (role),
    INDEX idx_task_conversation_message_created_at (created_at)
);

-- 对话统计表（用于分析）
CREATE TABLE IF NOT EXISTS task_conversation_stats (
    stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_instance_id UUID NOT NULL,
    user_id UUID NOT NULL,
    message_count INTEGER DEFAULT 0,
    first_message_at TIMESTAMP WITH TIME ZONE,
    last_message_at TIMESTAMP WITH TIME ZONE,
    context_type VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 索引
    INDEX idx_task_conversation_stats_task_id (task_instance_id),
    INDEX idx_task_conversation_stats_user_id (user_id)
);