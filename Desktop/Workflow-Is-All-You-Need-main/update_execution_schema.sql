-- 更新执行实例相关表结构，添加缺失的字段

-- 1. 为工作流实例表添加缺失的字段
ALTER TABLE workflow_instance 
ADD COLUMN IF NOT EXISTS instance_id UUID;

ALTER TABLE workflow_instance 
ADD COLUMN IF NOT EXISTS executor_id UUID;

-- 2. 为任务实例表添加缺失的字段
ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS task_instance_id UUID;

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS task_type VARCHAR(20) DEFAULT 'human' CHECK (task_type IN ('human', 'agent', 'mixed'));

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS assigned_agent_id UUID;

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS task_title VARCHAR(255);

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS instructions TEXT;

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS workflow_context JSONB;

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS result_summary TEXT;

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS actual_duration INTEGER;

ALTER TABLE task_instance 
ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 1;

-- 3. 更新现有记录的缺失字段（如果表中已有数据）
UPDATE workflow_instance 
SET instance_id = workflow_instance_id 
WHERE instance_id IS NULL;

UPDATE workflow_instance 
SET executor_id = trigger_user_id 
WHERE executor_id IS NULL;

UPDATE task_instance 
SET task_instance_id = task_id 
WHERE task_instance_id IS NULL;

UPDATE task_instance 
SET task_title = COALESCE(task_description, 'Task')
WHERE task_title IS NULL;

-- 4. 为新字段添加索引
CREATE INDEX IF NOT EXISTS idx_workflow_instance_instance_id ON workflow_instance(instance_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_executor_id ON workflow_instance(executor_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_task_instance_id ON task_instance(task_instance_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_task_type ON task_instance(task_type);
CREATE INDEX IF NOT EXISTS idx_task_instance_assigned_agent ON task_instance(assigned_agent_id);

-- 5. 添加外键约束（如果agent表存在）
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent') THEN
        ALTER TABLE task_instance 
        ADD CONSTRAINT fk_ti_agent 
        FOREIGN KEY (assigned_agent_id) REFERENCES agent(agent_id);
    END IF;
END
$$;

-- 6. 更新视图以包含新字段
CREATE OR REPLACE VIEW workflow_execution AS
SELECT 
    workflow_instance_id as execution_id,
    instance_id,
    workflow_id as workflow_base_id,
    (SELECT version FROM "workflow" w WHERE w.workflow_id = wi.workflow_id) as workflow_version,
    trigger_user_id as executor_user_id,
    executor_id,
    workflow_instance_name as instance_name,
    status,
    start_at as start_time,
    completed_at as end_time,
    error_message,
    retry_count,
    '{}' as input_data,  -- 简化的JSON
    created_at,
    updated_at
FROM workflow_instance wi;

-- 7. 创建任务实例完整视图
CREATE OR REPLACE VIEW task_execution AS
SELECT 
    ti.task_instance_id,
    ti.task_id,
    ti.node_instance_id,
    ti.processor_id,
    ti.assigned_agent_id,
    ti.task_title,
    ti.task_description,
    ti.task_type,
    ti.status,
    ti.instructions,
    ti.input_data,
    ti.output_data,
    ti.workflow_context,
    ti.result_summary,
    ti.actual_duration,
    ti.priority,
    ti.start_at,
    ti.completed_at,
    ti.error_message,
    ti.created_at,
    ti.updated_at
FROM task_instance ti;