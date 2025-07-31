-- 添加缺失的任务实例字段
-- Add missing task instance fields

-- 检查并添加 started_at 字段
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_instance' AND column_name = 'started_at'
    ) THEN
        ALTER TABLE task_instance ADD COLUMN started_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE '已添加 started_at 字段到 task_instance 表';
    ELSE
        RAISE NOTICE 'started_at 字段已存在于 task_instance 表';
    END IF;
END $$;

-- 检查并添加 assigned_at 字段
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_instance' AND column_name = 'assigned_at'
    ) THEN
        ALTER TABLE task_instance ADD COLUMN assigned_at TIMESTAMP WITH TIME ZONE;
        RAISE NOTICE '已添加 assigned_at 字段到 task_instance 表';
    ELSE
        RAISE NOTICE 'assigned_at 字段已存在于 task_instance 表';
    END IF;
END $$;

-- 检查并添加 context_data 字段（存储任务上下文信息）
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_instance' AND column_name = 'context_data'
    ) THEN
        ALTER TABLE task_instance ADD COLUMN context_data JSONB DEFAULT '{}';
        RAISE NOTICE '已添加 context_data 字段到 task_instance 表';
    ELSE
        RAISE NOTICE 'context_data 字段已存在于 task_instance 表';
    END IF;
END $$;

-- 检查并添加 actual_duration 字段
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_instance' AND column_name = 'actual_duration'
    ) THEN
        ALTER TABLE task_instance ADD COLUMN actual_duration INTEGER;
        RAISE NOTICE '已添加 actual_duration 字段到 task_instance 表';
    ELSE
        RAISE NOTICE 'actual_duration 字段已存在于 task_instance 表';
    END IF;
END $$;

-- 检查并添加 result_summary 字段
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'task_instance' AND column_name = 'result_summary'
    ) THEN
        ALTER TABLE task_instance ADD COLUMN result_summary TEXT;
        RAISE NOTICE '已添加 result_summary 字段到 task_instance 表';
    ELSE
        RAISE NOTICE 'result_summary 字段已存在于 task_instance 表';
    END IF;
END $$;

-- 显示当前task_instance表结构
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'task_instance' 
ORDER BY ordinal_position;