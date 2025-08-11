"""
数据库初始化脚本
Database Initialization Script
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
from loguru import logger

# 添加父目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, parent_dir)

from backend.config import get_settings


class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def create_database_if_not_exists(self):
        """如果数据库不存在则创建"""
        try:
            # 连接到默认数据库（通常是postgres）
            conn = await asyncpg.connect(
                host=self.settings.database.host,
                port=self.settings.database.port,
                user=self.settings.database.username,
                password=self.settings.database.password,
                database='postgres'
            )
            
            # 检查目标数据库是否存在
            db_exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                self.settings.database.database
            )
            
            if not db_exists:
                # 创建数据库
                await conn.execute(f'CREATE DATABASE "{self.settings.database.database}"')
                logger.info(f"创建数据库: {self.settings.database.database}")
            else:
                logger.info(f"数据库已存在: {self.settings.database.database}")
            
            await conn.close()
        except Exception as e:
            logger.error(f"创建数据库失败: {e}")
            raise
    
    async def execute_sql_file(self, sql_content: str):
        """执行SQL文件内容"""
        try:
            conn = await asyncpg.connect(self.settings.database.database_url)
            
            # 分割SQL语句（简单处理，可能需要更复杂的解析）
            statements = []
            current_statement = ""
            in_function = False
            
            for line in sql_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('--'):
                    continue
                
                # 检测函数开始
                if 'CREATE OR REPLACE FUNCTION' in line.upper():
                    in_function = True
                
                current_statement += line + '\n'
                
                # 检测语句结束
                if line.endswith(';'):
                    if in_function:
                        # 检测函数结束
                        if line.endswith('$ LANGUAGE plpgsql;'):
                            in_function = False
                            statements.append(current_statement.strip())
                            current_statement = ""
                    else:
                        statements.append(current_statement.strip())
                        current_statement = ""
            
            # 执行每个语句
            for i, statement in enumerate(statements):
                if statement.strip():
                    try:
                        await conn.execute(statement)
                        logger.info(f"执行SQL语句 {i+1}/{len(statements)} 成功")
                    except Exception as e:
                        logger.error(f"执行SQL语句 {i+1} 失败: {e}")
                        logger.error(f"失败的语句: {statement[:200]}...")
                        raise
            
            await conn.close()
            logger.info("SQL文件执行完成")
        except Exception as e:
            logger.error(f"执行SQL文件失败: {e}")
            raise
    
    async def initialize_schema(self):
        """初始化数据库架构"""
        try:
            # 获取用户提供的SQL脚本内容
            sql_schema = """
-- 表1：user（用户主表 - 不变）
CREATE TABLE IF NOT EXISTS "user" (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    terminal_endpoint TEXT,
    profile JSONB,
    description TEXT,
    role VARCHAR(50),
    status BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- 表2：agent（agent主表 - 不变）
CREATE TABLE IF NOT EXISTS agent (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name VARCHAR(255) NOT NULL,
    description TEXT,
    base_url VARCHAR(255),
    api_key VARCHAR(255),
    model_name VARCHAR(255),
    tool_config JSONB,
    parameters JSONB,
    is_autonomous BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- 表3：workflow（工作流主表 - 版本控制）
CREATE TABLE IF NOT EXISTS workflow (
    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_base_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    creator_id UUID NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    parent_version_id UUID,
    is_current_version BOOLEAN NOT NULL DEFAULT TRUE,
    change_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_workflow_creator 
        FOREIGN KEY (creator_id) REFERENCES "user"(user_id),
    CONSTRAINT fk_workflow_parent_version 
        FOREIGN KEY (parent_version_id) REFERENCES workflow(workflow_id)
);

-- 表4：node（节点表 - 版本控制）
CREATE TABLE IF NOT EXISTS node (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_base_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    workflow_base_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('start', 'processor', 'end')),
    task_description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    parent_version_id UUID,
    is_current_version BOOLEAN NOT NULL DEFAULT TRUE,
    position_x INTEGER,
    position_y INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_node_workflow 
        FOREIGN KEY (workflow_id) REFERENCES workflow(workflow_id),
    CONSTRAINT fk_node_parent_version 
        FOREIGN KEY (parent_version_id) REFERENCES node(node_id)
);

-- 表5：processor（处理器 - 不变，但增加版本追踪）
CREATE TABLE IF NOT EXISTS processor (
    processor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    agent_id UUID,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(10) NOT NULL CHECK (type IN ('human', 'agent', 'mix')),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_processor_user 
        FOREIGN KEY (user_id) REFERENCES "user"(user_id),
    CONSTRAINT fk_processor_agent 
        FOREIGN KEY (agent_id) REFERENCES agent(agent_id),
    CONSTRAINT chk_processor_reference CHECK (
        (type = 'human' AND user_id IS NOT NULL AND agent_id IS NULL) OR
        (type = 'agent' AND agent_id IS NOT NULL AND user_id IS NULL) OR
        (type = 'mix' AND user_id IS NOT NULL AND agent_id IS NOT NULL)
    )
);

-- 表6：workflow_user（工作流用户关联表 - 基于base_id）
CREATE TABLE IF NOT EXISTS workflow_user (
    workflow_base_id UUID NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (workflow_base_id, user_id),
    CONSTRAINT fk_wu_user 
        FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

-- 表7：node_processor（节点处理器关联表 - 版本化）
CREATE TABLE IF NOT EXISTS node_processor (
    node_id UUID NOT NULL,
    processor_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (node_id, processor_id),
    CONSTRAINT fk_np_node 
        FOREIGN KEY (node_id) REFERENCES node(node_id),
    CONSTRAINT fk_np_processor 
        FOREIGN KEY (processor_id) REFERENCES processor(processor_id)
);

-- 表8：node_connection（节点连接表 - 版本化）
CREATE TABLE IF NOT EXISTS node_connection (
    from_node_id UUID NOT NULL,
    to_node_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    connection_type VARCHAR(50) DEFAULT 'normal',
    condition_config JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (from_node_id, to_node_id, workflow_id),
    CONSTRAINT fk_nc_from_node 
        FOREIGN KEY (from_node_id) REFERENCES node(node_id),
    CONSTRAINT fk_nc_to_node 
        FOREIGN KEY (to_node_id) REFERENCES node(node_id),
    CONSTRAINT fk_nc_workflow 
        FOREIGN KEY (workflow_id) REFERENCES workflow(workflow_id),
    CONSTRAINT chk_no_self_loop 
        CHECK (from_node_id != to_node_id)
);

-- 表9：workflow_instance（工作流实例表）
CREATE TABLE IF NOT EXISTS workflow_instance (
    workflow_instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL,
    workflow_base_id UUID NOT NULL,
    executor_id UUID NOT NULL,
    trigger_user_id UUID NOT NULL,
    workflow_instance_name VARCHAR(255),
    instance_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    input_data JSONB,
    context_data JSONB,
    output_data JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    current_node_id UUID,
    retry_count INTEGER NOT NULL DEFAULT 0,
    -- 新增的结构化输出字段
    execution_summary JSONB,
    quality_metrics JSONB,
    data_lineage JSONB,
    output_summary JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_workflow_instance_workflow 
        FOREIGN KEY (workflow_id) REFERENCES workflow(workflow_id),
    CONSTRAINT fk_workflow_instance_executor 
        FOREIGN KEY (executor_id) REFERENCES "user"(user_id),
    CONSTRAINT fk_workflow_instance_trigger_user 
        FOREIGN KEY (trigger_user_id) REFERENCES "user"(user_id),
    CONSTRAINT fk_workflow_instance_current_node 
        FOREIGN KEY (current_node_id) REFERENCES node(node_id)
);

-- 表10：node_instance（节点实例表）
CREATE TABLE IF NOT EXISTS node_instance (
    node_instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id UUID NOT NULL,
    node_id UUID NOT NULL,
    node_base_id UUID NOT NULL,
    node_instance_name VARCHAR(255),
    task_description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'waiting', 'running', 'completed', 'failed', 'cancelled')),
    input_data JSONB,
    output_data JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_node_instance_workflow_instance 
        FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instance(workflow_instance_id),
    CONSTRAINT fk_node_instance_node 
        FOREIGN KEY (node_id) REFERENCES node(node_id)
);

-- 表11：task_instance（任务实例表）
CREATE TABLE IF NOT EXISTS task_instance (
    task_instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_instance_id UUID NOT NULL,
    workflow_instance_id UUID NOT NULL,
    processor_id UUID NOT NULL,
    task_type VARCHAR(20) DEFAULT 'human' CHECK (task_type IN ('human', 'agent', 'mixed')),
    task_title VARCHAR(255) NOT NULL,
    task_description TEXT DEFAULT '',
    instructions TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'assigned', 'waiting', 'in_progress', 'completed', 'failed', 'cancelled')),
    priority INTEGER DEFAULT 1 CHECK (priority >= 1 AND priority <= 5),
    input_data TEXT,
    context_data TEXT,
    output_data TEXT,
    result_summary TEXT,
    assigned_user_id UUID,
    assigned_agent_id UUID,
    assigned_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_duration INTEGER,
    actual_duration INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_task_instance_node_instance 
        FOREIGN KEY (node_instance_id) REFERENCES node_instance(node_instance_id),
    CONSTRAINT fk_task_instance_workflow_instance 
        FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instance(workflow_instance_id),
    CONSTRAINT fk_task_instance_processor 
        FOREIGN KEY (processor_id) REFERENCES processor(processor_id),
    CONSTRAINT fk_task_instance_assigned_user 
        FOREIGN KEY (assigned_user_id) REFERENCES "user"(user_id),
    CONSTRAINT fk_task_instance_assigned_agent 
        FOREIGN KEY (assigned_agent_id) REFERENCES agent(agent_id)
);

-- 表12：workflow_execution（工作流执行状态跟踪表）
CREATE TABLE IF NOT EXISTS workflow_execution (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id UUID NOT NULL,
    current_node_id UUID,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    execution_context JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_workflow_execution_workflow_instance 
        FOREIGN KEY (workflow_instance_id) REFERENCES workflow_instance(workflow_instance_id),
    CONSTRAINT fk_workflow_execution_current_node 
        FOREIGN KEY (current_node_id) REFERENCES node(node_id)
);

-- 表13：node_execution（节点执行状态跟踪表）
CREATE TABLE IF NOT EXISTS node_execution (
    node_execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_instance_id UUID NOT NULL,
    execution_order INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    execution_data JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT fk_node_execution_node_instance 
        FOREIGN KEY (node_instance_id) REFERENCES node_instance(node_instance_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_workflow_base_id ON workflow(workflow_base_id);
CREATE INDEX IF NOT EXISTS idx_workflow_current_version ON workflow(workflow_base_id, is_current_version) WHERE is_current_version = TRUE;
CREATE INDEX IF NOT EXISTS idx_node_base_id ON node(node_base_id);
CREATE INDEX IF NOT EXISTS idx_node_workflow_base_id ON node(workflow_base_id);
CREATE INDEX IF NOT EXISTS idx_node_current_version ON node(node_base_id, workflow_base_id, is_current_version) WHERE is_current_version = TRUE;
CREATE INDEX IF NOT EXISTS idx_node_connection_workflow ON node_connection(workflow_id);
CREATE INDEX IF NOT EXISTS idx_user_username ON "user"(username);
CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);
CREATE INDEX IF NOT EXISTS idx_agent_name ON agent(agent_name);

-- 实例表索引
CREATE INDEX IF NOT EXISTS idx_workflow_instance_workflow_id ON workflow_instance(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_workflow_base_id ON workflow_instance(workflow_base_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_status ON workflow_instance(status);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_executor ON workflow_instance(executor_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_trigger_user ON workflow_instance(trigger_user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_current_node ON workflow_instance(current_node_id);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_created_status ON workflow_instance(created_at DESC, status);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_completed ON workflow_instance(completed_at DESC) WHERE completed_at IS NOT NULL;

-- 新增输出数据字段索引
CREATE INDEX IF NOT EXISTS idx_workflow_instance_execution_summary ON workflow_instance USING GIN (execution_summary);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_quality_metrics ON workflow_instance USING GIN (quality_metrics);
CREATE INDEX IF NOT EXISTS idx_workflow_instance_data_lineage ON workflow_instance USING GIN (data_lineage);

CREATE INDEX IF NOT EXISTS idx_node_instance_workflow_instance ON node_instance(workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_node_instance_node_id ON node_instance(node_id);
CREATE INDEX IF NOT EXISTS idx_node_instance_node_base_id ON node_instance(node_base_id);
CREATE INDEX IF NOT EXISTS idx_node_instance_status ON node_instance(status);

CREATE INDEX IF NOT EXISTS idx_task_instance_node_instance ON task_instance(node_instance_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_workflow_instance ON task_instance(workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_processor ON task_instance(processor_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_status ON task_instance(status);
CREATE INDEX IF NOT EXISTS idx_task_instance_task_type ON task_instance(task_type);
CREATE INDEX IF NOT EXISTS idx_task_instance_priority ON task_instance(priority);
CREATE INDEX IF NOT EXISTS idx_task_instance_assigned_user ON task_instance(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_task_instance_assigned_agent ON task_instance(assigned_agent_id);

-- 表14：mcp_tool_registry（MCP工具注册表）
CREATE TABLE IF NOT EXISTS mcp_tool_registry (
    tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    server_name VARCHAR(255) NOT NULL,
    server_url TEXT NOT NULL,
    server_description TEXT,
    tool_name VARCHAR(255) NOT NULL,
    tool_description TEXT,
    tool_parameters JSONB DEFAULT '{}',
    auth_config JSONB,
    timeout_seconds INTEGER DEFAULT 30,
    is_server_active BOOLEAN DEFAULT TRUE,
    is_tool_active BOOLEAN DEFAULT TRUE,
    server_status VARCHAR(20) DEFAULT 'unknown',
    tool_usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0,
    bound_agents_count INTEGER DEFAULT 0,
    last_tool_call TIMESTAMP WITH TIME ZONE,
    last_health_check TIMESTAMP WITH TIME ZONE,
    last_tool_discovery TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    UNIQUE(user_id, server_name, tool_name),
    CONSTRAINT fk_mcp_tool_user 
        FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

-- 表15：agent_tool_bindings（Agent工具绑定表）
CREATE TABLE IF NOT EXISTS agent_tool_bindings (
    binding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL,
    tool_id UUID NOT NULL,
    user_id UUID NOT NULL,
    binding_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    UNIQUE(agent_id, tool_id),
    CONSTRAINT fk_atb_agent 
        FOREIGN KEY (agent_id) REFERENCES agent(agent_id),
    CONSTRAINT fk_atb_tool 
        FOREIGN KEY (tool_id) REFERENCES mcp_tool_registry(tool_id) ON DELETE CASCADE,
    CONSTRAINT fk_atb_user 
        FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

-- MCP表索引
CREATE INDEX IF NOT EXISTS idx_mcp_tool_registry_user_id ON mcp_tool_registry(user_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_registry_server_name ON mcp_tool_registry(server_name);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_registry_active ON mcp_tool_registry(is_server_active, is_tool_active);
CREATE INDEX IF NOT EXISTS idx_agent_tool_bindings_agent_id ON agent_tool_bindings(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_tool_bindings_tool_id ON agent_tool_bindings(tool_id);
CREATE INDEX IF NOT EXISTS idx_agent_tool_bindings_user_id ON agent_tool_bindings(user_id);

-- 创建user_mcp_tools_view视图
CREATE OR REPLACE VIEW user_mcp_tools_view AS
SELECT 
    tool_id,
    user_id,
    server_name,
    server_url,
    server_description,
    tool_name,
    tool_description,
    tool_parameters,
    auth_config,
    timeout_seconds,
    is_server_active,
    is_tool_active,
    server_status,
    tool_usage_count,
    success_rate,
    bound_agents_count,
    last_tool_call,
    last_health_check,
    created_at,
    updated_at
FROM mcp_tool_registry 
WHERE is_deleted = FALSE
ORDER BY server_name, tool_name;
"""
            
            await self.execute_sql_file(sql_schema)
            logger.info("数据库架构初始化完成")
        except Exception as e:
            logger.error(f"初始化数据库架构失败: {e}")
            raise
    
    async def create_functions(self):
        """创建数据库函数"""
        try:
            functions_sql = """
-- 版本管理函数：创建工作流新版本
CREATE OR REPLACE FUNCTION create_workflow_version(
    p_workflow_base_id UUID,
    p_editor_user_id UUID,
    p_change_description TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_current_workflow_id UUID;
    v_new_workflow_id UUID;
    v_new_version INTEGER;
    v_node_record RECORD;
    v_old_new_node_map JSONB := '{}';
    v_connection_record RECORD;
BEGIN
    -- 获取当前版本的工作流
    SELECT workflow_id, version INTO v_current_workflow_id, v_new_version
    FROM workflow 
    WHERE workflow_base_id = p_workflow_base_id AND is_current_version = TRUE;
    
    IF v_current_workflow_id IS NULL THEN
        RAISE EXCEPTION 'Workflow base_id % not found or no current version', p_workflow_base_id;
    END IF;
    
    v_new_version := v_new_version + 1;
    
    -- 开始事务
    BEGIN
        -- 1. 将当前版本标记为非当前版本
        UPDATE workflow 
        SET is_current_version = FALSE 
        WHERE workflow_base_id = p_workflow_base_id AND is_current_version = TRUE;
        
        -- 2. 创建新的工作流版本
        INSERT INTO workflow (
            workflow_base_id, name, description, creator_id, version, 
            parent_version_id, is_current_version, change_description
        )
        SELECT 
            workflow_base_id, name, description, creator_id, v_new_version,
            v_current_workflow_id, TRUE, p_change_description
        FROM workflow 
        WHERE workflow_id = v_current_workflow_id
        RETURNING workflow_id INTO v_new_workflow_id;
        
        -- 3. 将当前版本的所有节点标记为非当前版本
        UPDATE node 
        SET is_current_version = FALSE 
        WHERE workflow_base_id = p_workflow_base_id AND is_current_version = TRUE;
        
        -- 4. 复制所有节点到新版本
        FOR v_node_record IN 
            SELECT * FROM node 
            WHERE workflow_id = v_current_workflow_id
        LOOP
            DECLARE
                v_new_node_id UUID;
            BEGIN
                INSERT INTO node (
                    node_base_id, workflow_id, workflow_base_id, name, type,
                    task_description, version, parent_version_id, is_current_version,
                    position_x, position_y
                )
                VALUES (
                    v_node_record.node_base_id, v_new_workflow_id, p_workflow_base_id,
                    v_node_record.name, v_node_record.type, v_node_record.task_description,
                    v_new_version, v_node_record.node_id, TRUE,
                    v_node_record.position_x, v_node_record.position_y
                )
                RETURNING node_id INTO v_new_node_id;
                
                -- 记录旧节点ID到新节点ID的映射
                v_old_new_node_map := jsonb_set(
                    v_old_new_node_map, 
                    ARRAY[v_node_record.node_id::text], 
                    to_jsonb(v_new_node_id::text)
                );
                
                -- 复制节点处理器关联
                INSERT INTO node_processor (node_id, processor_id)
                SELECT v_new_node_id, processor_id
                FROM node_processor 
                WHERE node_id = v_node_record.node_id;
            END;
        END LOOP;
        
        -- 5. 复制节点连接关系
        FOR v_connection_record IN 
            SELECT * FROM node_connection 
            WHERE workflow_id = v_current_workflow_id
        LOOP
            INSERT INTO node_connection (
                from_node_id, to_node_id, workflow_id, 
                connection_type, condition_config
            )
            VALUES (
                (v_old_new_node_map->>v_connection_record.from_node_id::text)::UUID,
                (v_old_new_node_map->>v_connection_record.to_node_id::text)::UUID,
                v_new_workflow_id,
                v_connection_record.connection_type,
                v_connection_record.condition_config
            );
        END LOOP;
        
        RETURN v_new_workflow_id;
        
    EXCEPTION
        WHEN OTHERS THEN
            RAISE;
    END;
END;
$$ LANGUAGE plpgsql;

-- 版本管理函数：创建节点新版本
CREATE OR REPLACE FUNCTION create_node_version(
    p_node_base_id UUID,
    p_workflow_base_id UUID,
    p_new_name VARCHAR(255) DEFAULT NULL,
    p_new_description TEXT DEFAULT NULL,
    p_new_position_x INTEGER DEFAULT NULL,
    p_new_position_y INTEGER DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_current_node_id UUID;
    v_current_workflow_id UUID;
    v_new_node_id UUID;
    v_new_version INTEGER;
BEGIN
    -- 获取当前版本的节点和工作流
    SELECT n.node_id, n.version, w.workflow_id 
    INTO v_current_node_id, v_new_version, v_current_workflow_id
    FROM node n
    JOIN workflow w ON w.workflow_base_id = n.workflow_base_id
    WHERE n.node_base_id = p_node_base_id 
      AND n.workflow_base_id = p_workflow_base_id
      AND n.is_current_version = TRUE
      AND w.is_current_version = TRUE;
    
    IF v_current_node_id IS NULL THEN
        RAISE EXCEPTION 'Node base_id % not found in workflow base_id %', p_node_base_id, p_workflow_base_id;
    END IF;
    
    v_new_version := v_new_version + 1;
    
    -- 首先创建新的工作流版本（如果需要的话）
    v_current_workflow_id := create_workflow_version(p_workflow_base_id, NULL, 'Node update');
    
    -- 获取新工作流版本中对应的节点ID
    SELECT node_id INTO v_new_node_id
    FROM node 
    WHERE node_base_id = p_node_base_id 
      AND workflow_id = v_current_workflow_id
      AND is_current_version = TRUE;
    
    -- 更新节点信息
    UPDATE node SET
        name = COALESCE(p_new_name, name),
        task_description = COALESCE(p_new_description, task_description),
        position_x = COALESCE(p_new_position_x, position_x),
        position_y = COALESCE(p_new_position_y, position_y),
        version = v_new_version
    WHERE node_id = v_new_node_id;
    
    RETURN v_new_node_id;
END;
$$ LANGUAGE plpgsql;

-- 初始化函数：创建第一个工作流
CREATE OR REPLACE FUNCTION create_initial_workflow(
    p_name VARCHAR(255),
    p_description TEXT,
    p_creator_id UUID
) RETURNS UUID AS $$
DECLARE
    v_workflow_base_id UUID;
    v_workflow_id UUID;
BEGIN
    v_workflow_base_id := gen_random_uuid();
    
    INSERT INTO workflow (
        workflow_base_id, name, description, creator_id, version, is_current_version
    ) VALUES (
        v_workflow_base_id, p_name, p_description, p_creator_id, 1, TRUE
    ) RETURNING workflow_id INTO v_workflow_id;
    
    RETURN v_workflow_id;
END;
$$ LANGUAGE plpgsql;
"""
            
            await self.execute_sql_file(functions_sql)
            logger.info("数据库函数创建完成")
        except Exception as e:
            logger.error(f"创建数据库函数失败: {e}")
            raise
    
    async def create_views(self):
        """创建视图"""
        try:
            views_sql = """
-- 便捷视图：获取当前版本的工作流和节点
CREATE OR REPLACE VIEW current_workflow_view AS
SELECT 
    w.workflow_id,
    w.workflow_base_id,
    w.name,
    w.description,
    w.creator_id,
    w.version,
    w.created_at,
    u.username as creator_name
FROM workflow w
JOIN "user" u ON u.user_id = w.creator_id
WHERE w.is_current_version = TRUE AND w.is_deleted = FALSE;

CREATE OR REPLACE VIEW current_node_view AS
SELECT 
    n.node_id,
    n.node_base_id,
    n.workflow_id,
    n.workflow_base_id,
    n.name,
    n.type,
    n.task_description,
    n.version,
    n.position_x,
    n.position_y,
    w.name as workflow_name
FROM node n
JOIN workflow w ON w.workflow_id = n.workflow_id
WHERE n.is_current_version = TRUE AND n.is_deleted = FALSE
  AND w.is_current_version = TRUE AND w.is_deleted = FALSE;

-- 版本历史视图
CREATE OR REPLACE VIEW workflow_version_history AS
SELECT 
    w.workflow_id,
    w.workflow_base_id,
    w.name,
    w.version,
    w.change_description,
    w.created_at,
    u.username as creator_name,
    w.is_current_version,
    COUNT(n.node_id) as node_count
FROM workflow w
JOIN "user" u ON u.user_id = w.creator_id
LEFT JOIN node n ON n.workflow_id = w.workflow_id
WHERE w.is_deleted = FALSE
GROUP BY w.workflow_id, w.workflow_base_id, w.name, w.version, 
         w.change_description, w.created_at, u.username, w.is_current_version
ORDER BY w.workflow_base_id, w.version DESC;

-- 工作流实例详情视图
CREATE OR REPLACE VIEW workflow_instance_detail_view AS
SELECT 
    wi.workflow_instance_id,
    wi.workflow_id,
    wi.workflow_base_id,
    wi.executor_id,
    wi.trigger_user_id,
    wi.workflow_instance_name,
    wi.instance_name,
    wi.status,
    wi.input_data,
    wi.context_data,
    wi.output_data,
    wi.started_at,
    wi.completed_at,
    wi.error_message,
    wi.current_node_id,
    wi.retry_count,
    wi.execution_summary,
    wi.quality_metrics,
    wi.data_lineage,
    wi.output_summary,
    wi.created_at,
    wi.updated_at,
    w.name as workflow_name,
    w.description as workflow_description,
    u.username as executor_name,
    tu.username as trigger_user_name,
    COUNT(ni.node_instance_id) as total_nodes,
    COUNT(CASE WHEN ni.status = 'completed' THEN 1 END) as completed_nodes,
    COUNT(CASE WHEN ni.status = 'failed' THEN 1 END) as failed_nodes,
    COUNT(CASE WHEN ni.status = 'running' THEN 1 END) as running_nodes
FROM workflow_instance wi
JOIN workflow w ON w.workflow_id = wi.workflow_id
JOIN "user" u ON u.user_id = wi.executor_id
LEFT JOIN "user" tu ON tu.user_id = wi.trigger_user_id
LEFT JOIN node_instance ni ON ni.workflow_instance_id = wi.workflow_instance_id AND ni.is_deleted = FALSE
WHERE wi.is_deleted = FALSE
GROUP BY wi.workflow_instance_id, wi.workflow_id, wi.workflow_base_id, wi.executor_id, wi.trigger_user_id,
         wi.workflow_instance_name, wi.instance_name, wi.status, wi.input_data, 
         wi.context_data, wi.output_data, wi.started_at, wi.completed_at, 
         wi.error_message, wi.current_node_id, wi.retry_count, wi.execution_summary,
         wi.quality_metrics, wi.data_lineage, wi.output_summary, wi.created_at, wi.updated_at,
         w.name, w.description, u.username, tu.username;

-- 任务实例详情视图
CREATE OR REPLACE VIEW task_instance_detail_view AS
SELECT 
    ti.task_instance_id,
    ti.node_instance_id,
    ti.workflow_instance_id,
    ti.processor_id,
    ti.task_type,
    ti.task_title,
    ti.task_description,
    ti.instructions,
    ti.status,
    ti.priority,
    ti.input_data,
    ti.context_data,
    ti.output_data,
    ti.result_summary,
    ti.assigned_user_id,
    ti.assigned_agent_id,
    ti.assigned_at,
    ti.started_at,
    ti.completed_at,
    ti.estimated_duration,
    ti.actual_duration,
    ti.error_message,
    ti.created_at,
    ti.updated_at,
    ni.node_instance_name,
    n.name as node_name,
    n.type as node_type,
    p.name as processor_name,
    p.type as processor_type,
    au.username as assigned_user_name,
    aa.agent_name as assigned_agent_name,
    wi.workflow_instance_name,
    w.name as workflow_name
FROM task_instance ti
JOIN node_instance ni ON ni.node_instance_id = ti.node_instance_id
JOIN node n ON n.node_id = ni.node_id
JOIN processor p ON p.processor_id = ti.processor_id
JOIN workflow_instance wi ON wi.workflow_instance_id = ti.workflow_instance_id
JOIN workflow w ON w.workflow_id = wi.workflow_id
LEFT JOIN "user" au ON au.user_id = ti.assigned_user_id
LEFT JOIN agent aa ON aa.agent_id = ti.assigned_agent_id
WHERE ti.is_deleted = FALSE AND ni.is_deleted = FALSE AND wi.is_deleted = FALSE;

-- 节点实例详情视图
CREATE OR REPLACE VIEW node_instance_detail_view AS
SELECT 
    ni.node_instance_id,
    ni.workflow_instance_id,
    ni.node_id,
    ni.node_base_id,
    ni.node_instance_name,
    ni.task_description as node_instance_task_description,
    ni.status,
    ni.input_data,
    ni.output_data,
    ni.started_at,
    ni.completed_at,
    ni.error_message,
    ni.retry_count,
    ni.created_at,
    ni.updated_at,
    n.name as node_name,
    n.type as node_type,
    n.task_description as node_task_description,
    n.position_x,
    n.position_y,
    wi.workflow_instance_name,
    w.name as workflow_name,
    COUNT(ti.task_instance_id) as total_tasks,
    COUNT(CASE WHEN ti.status = 'completed' THEN 1 END) as completed_tasks,
    COUNT(CASE WHEN ti.status = 'failed' THEN 1 END) as failed_tasks,
    COUNT(CASE WHEN ti.status = 'in_progress' THEN 1 END) as running_tasks
FROM node_instance ni
JOIN node n ON n.node_id = ni.node_id
JOIN workflow_instance wi ON wi.workflow_instance_id = ni.workflow_instance_id
JOIN workflow w ON w.workflow_id = wi.workflow_id
LEFT JOIN task_instance ti ON ti.node_instance_id = ni.node_instance_id AND ti.is_deleted = FALSE
WHERE ni.is_deleted = FALSE AND wi.is_deleted = FALSE
GROUP BY ni.node_instance_id, ni.workflow_instance_id, ni.node_id, ni.node_base_id,
         ni.node_instance_name, ni.task_description, ni.status, ni.input_data, ni.output_data,
         ni.started_at, ni.completed_at, ni.error_message, ni.retry_count,
         ni.created_at, ni.updated_at, n.name, n.type, n.task_description,
         n.position_x, n.position_y, wi.workflow_instance_name, w.name;
"""
            
            await self.execute_sql_file(views_sql)
            logger.info("数据库视图创建完成")
        except Exception as e:
            logger.error(f"创建数据库视图失败: {e}")
            raise
    
    async def create_sample_data(self):
        """创建示例数据"""
        try:
            sample_data_sql = """
-- 插入示例用户
INSERT INTO "user" (username, password_hash, email, role, description) VALUES
('admin', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'admin@example.com', 'admin', 'System Administrator'),
('user1', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'user1@example.com', 'user', 'Regular User 1'),
('user2', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'user2@example.com', 'user', 'Regular User 2')
ON CONFLICT DO NOTHING;

-- 插入示例Agent
INSERT INTO agent (agent_name, description, model_name, is_autonomous) VALUES
('GPT-4', 'OpenAI GPT-4 Agent', 'gpt-4', false),
('Claude', 'Anthropic Claude Agent', 'claude-3', false),
('AutoAgent', 'Autonomous AI Agent', 'auto-model', true)
ON CONFLICT DO NOTHING;
"""
            
            await self.execute_sql_file(sample_data_sql)
            logger.info("示例数据创建完成")
        except Exception as e:
            logger.error(f"创建示例数据失败: {e}")
            raise
    
    async def initialize_all(self, include_sample_data: bool = False):
        """完整初始化数据库"""
        try:
            logger.info("开始初始化数据库...")
            
            # 1. 创建数据库
            await self.create_database_if_not_exists()
            
            # 2. 初始化架构
            await self.initialize_schema()
            
            # 3. 创建函数
            await self.create_functions()
            
            # 4. 创建视图
            await self.create_views()
            
            # 5. 创建示例数据（可选）
            if include_sample_data:
                await self.create_sample_data()
            
            logger.info("数据库初始化完成！")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise


async def main():
    """主函数"""
    import sys
    
    include_sample_data = '--with-sample-data' in sys.argv
    
    initializer = DatabaseInitializer()
    await initializer.initialize_all(include_sample_data)


if __name__ == "__main__":
    asyncio.run(main())