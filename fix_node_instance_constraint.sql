-- Fix node_instance status constraint to include 'waiting' status
-- 修复 node_instance 状态约束，增加 'waiting' 状态

-- Drop the existing constraint
ALTER TABLE node_instance DROP CONSTRAINT IF EXISTS node_instance_status_check;

-- Add the new constraint that includes 'waiting'
ALTER TABLE node_instance 
ADD CONSTRAINT node_instance_status_check 
CHECK (status IN ('pending', 'waiting', 'running', 'completed', 'failed', 'cancelled'));

-- Also update task_instance constraint if it exists
ALTER TABLE task_instance DROP CONSTRAINT IF EXISTS task_instance_status_check;

ALTER TABLE task_instance 
ADD CONSTRAINT task_instance_status_check 
CHECK (status IN ('pending', 'assigned', 'waiting', 'in_progress', 'running', 'completed', 'failed', 'cancelled'));

-- Update workflow_instance constraint if needed
ALTER TABLE workflow_instance DROP CONSTRAINT IF EXISTS workflow_instance_status_check;

ALTER TABLE workflow_instance 
ADD CONSTRAINT workflow_instance_status_check 
CHECK (status IN ('pending', 'waiting', 'running', 'paused', 'completed', 'failed', 'cancelled'));