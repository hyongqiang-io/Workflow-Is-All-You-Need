-- 添加执行实例相关表结构

-- 工作流实例表
CREATE TABLE IF NOT EXISTS workflow_instance (
    workflow_instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    trigger_user_id UUID NOT NULL,
    workflow_instance_name VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    start_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_wi_workflow 
        FOREIGN KEY (workflow_id) REFERENCES "workflow"(workflow_id),
    CONSTRAINT fk_wi_trigger_user 
        FOREIGN KEY (trigger_user_id) REFERENCES "user"(user_id)
);

-- 节点实例表
CREATE TABLE IF NOT EXISTS node_instance (
    node_instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id UUID NOT NULL,
    node_id UUID NOT NULL,
    node_instance_name VARCHAR(255),
    task_description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    input_data JSONB,
    output_data JSONB,
    start_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_ni_workflow_instance 
        FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instance(workflow_instance_id),
    CONSTRAINT fk_ni_node 
        FOREIGN KEY (node_id) REFERENCES "node"(node_id)
);

-- 任务实例表
CREATE TABLE IF NOT EXISTS task_instance (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_instance_id UUID NOT NULL,
    processor_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    task_description TEXT,
    input_data JSONB,
    output_data JSONB,
    start_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_ti_node_instance 
        FOREIGN KEY (node_instance_id) REFERENCES node_instance(node_instance_id),
    CONSTRAINT fk_ti_processor 
        FOREIGN KEY (processor_id) REFERENCES processor(processor_id)
);

-- 为了兼容测试中的表名，创建视图
CREATE OR REPLACE VIEW workflow_execution AS
SELECT 
    workflow_instance_id as execution_id,
    workflow_id as workflow_base_id,
    (SELECT version FROM "workflow" w WHERE w.workflow_id = wi.workflow_id) as workflow_version,
    trigger_user_id as executor_user_id,
    status,
    start_at as start_time,
    completed_at as end_time,
    '{}' as input_data,  -- 简化的JSON
    created_at
FROM workflow_instance wi;

CREATE OR REPLACE VIEW node_execution AS
SELECT 
    node_instance_id as node_execution_id,
    wi.workflow_instance_id as execution_id,
    ni.node_id,
    (SELECT node_base_id FROM "node" n WHERE n.node_id = ni.node_id) as node_base_id,
    (SELECT processor_id FROM task_instance ti WHERE ti.node_instance_id = ni.node_instance_id LIMIT 1) as processor_id,
    ni.status,
    ni.start_at as start_time,
    ni.input_data,
    ni.output_data,
    ni.error_message,
    EXTRACT(EPOCH FROM (ni.completed_at - ni.start_at)) * 1000 as duration_ms,
    ni.created_at
FROM node_instance ni
JOIN workflow_instance wi ON ni.workflow_instance_id = wi.workflow_instance_id;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_workflow_instance_workflow_id ON workflow_instance(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_trigger_user ON workflow_instance(trigger_user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_status ON workflow_instance(status);
CREATE INDEX IF NOT EXISTS idx_node_instance_workflow_instance ON node_instance(workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_node_instance_node_id ON node_instance(node_id);
CREATE INDEX IF NOT EXISTS idx_node_instance_status ON node_instance(status);
CREATE INDEX IF NOT EXISTS idx_task_instance_node_instance ON task_instance(node_instance_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_processor ON task_instance(processor_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_status ON task_instance(status);