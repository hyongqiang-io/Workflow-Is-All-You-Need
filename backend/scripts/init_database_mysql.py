"""
MySQL数据库初始化脚本 - 与PostgreSQL版本完全兼容的表结构
MySQL Database Initialization Script - Fully Compatible Table Structure with PostgreSQL
"""

import asyncio
import aiomysql
import os
import sys
from pathlib import Path
from loguru import logger

# 添加父目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, parent_dir)

from backend.config.settings_mysql import get_settings


class MySQLDatabaseInitializer:
    """MySQL数据库初始化器 - 兼容PostgreSQL表结构"""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def create_database_if_not_exists(self):
        """如果数据库不存在则创建"""
        try:
            # 连接到MySQL服务器（不指定数据库）
            conn = await aiomysql.connect(
                host=self.settings.database.host,
                port=self.settings.database.port,
                user=self.settings.database.username,
                password=self.settings.database.password,
                charset=self.settings.database.charset
            )
            
            async with conn.cursor() as cursor:
                # 检查数据库是否存在
                await cursor.execute(
                    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s",
                    (self.settings.database.database,)
                )
                db_exists = await cursor.fetchone()
                
                if not db_exists:
                    # 创建数据库
                    await cursor.execute(
                        f"CREATE DATABASE `{self.settings.database.database}` "
                        f"CHARACTER SET {self.settings.database.charset} "
                        f"COLLATE {self.settings.database.charset}_unicode_ci"
                    )
                    await conn.commit()
                    logger.info(f"创建MySQL数据库: {self.settings.database.database}")
                else:
                    logger.info(f"MySQL数据库已存在: {self.settings.database.database}")
            
            conn.close()
        except Exception as e:
            logger.error(f"创建MySQL数据库失败: {e}")
            raise
    
    async def execute_sql_file(self, sql_content: str):
        """执行SQL文件内容"""
        try:
            conn = await aiomysql.connect(
                host=self.settings.database.host,
                port=self.settings.database.port,
                user=self.settings.database.username,
                password=self.settings.database.password,
                db=self.settings.database.database,
                charset=self.settings.database.charset
            )
            
            # 分割SQL语句
            statements = []
            current_statement = ""
            in_delimiter = False
            
            for line in sql_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('--'):
                    continue
                
                # 检测DELIMITER语句
                if line.upper().startswith('DELIMITER'):
                    delimiter_line = line.strip()
                    if '//' in delimiter_line:
                        in_delimiter = True
                    else:
                        in_delimiter = False
                    continue
                
                current_statement += line + '\n'
                
                # 检测语句结束
                if not in_delimiter and line.endswith(';'):
                    statements.append(current_statement.strip())
                    current_statement = ""
                elif in_delimiter and line.upper().endswith('END //'):
                    statements.append(current_statement.strip())
                    current_statement = ""
                    in_delimiter = False
            
            # 执行每个语句
            async with conn.cursor() as cursor:
                for i, statement in enumerate(statements):
                    if statement.strip():
                        try:
                            await cursor.execute(statement)
                            await conn.commit()
                            logger.info(f"执行MySQL语句 {i+1}/{len(statements)} 成功")
                        except Exception as e:
                            logger.error(f"执行MySQL语句 {i+1} 失败: {e}")
                            logger.error(f"失败的语句: {statement[:200]}...")
                            raise
            
            conn.close()
            logger.info("MySQL SQL文件执行完成")
        except Exception as e:
            logger.error(f"执行MySQL SQL文件失败: {e}")
            raise
    
    async def initialize_schema(self):
        """初始化MySQL数据库架构 - 保持与PostgreSQL相同的表结构"""
        try:
            sql_schema = """
-- MySQL版本的数据库架构 - 与PostgreSQL完全兼容

-- 表1：user（用户主表）
CREATE TABLE IF NOT EXISTS `user` (
    user_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    terminal_endpoint TEXT,
    profile JSON,
    description TEXT,
    role VARCHAR(50),
    status BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    INDEX idx_user_username (username),
    INDEX idx_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表2：agent（agent主表）
CREATE TABLE IF NOT EXISTS `agent` (
    agent_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    agent_name VARCHAR(255) NOT NULL,
    description TEXT,
    base_url VARCHAR(255),
    api_key VARCHAR(255),
    model_name VARCHAR(255),
    tool_config JSON,
    parameters JSON,
    is_autonomous BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    INDEX idx_agent_name (agent_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表3：workflow（工作流主表 - 版本控制）
CREATE TABLE IF NOT EXISTS `workflow` (
    workflow_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    workflow_base_id CHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    creator_id CHAR(36) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    parent_version_id CHAR(36),
    is_current_version BOOLEAN NOT NULL DEFAULT TRUE,
    change_description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_workflow_creator 
        FOREIGN KEY (creator_id) REFERENCES `user`(user_id),
    CONSTRAINT fk_workflow_parent_version 
        FOREIGN KEY (parent_version_id) REFERENCES `workflow`(workflow_id),
    
    INDEX idx_workflow_base_id (workflow_base_id),
    INDEX idx_workflow_current_version (workflow_base_id, is_current_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表4：node（节点表 - 版本控制）
CREATE TABLE IF NOT EXISTS `node` (
    node_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    node_base_id CHAR(36) NOT NULL,
    workflow_id CHAR(36) NOT NULL,
    workflow_base_id CHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    type ENUM('start', 'processor', 'end') NOT NULL,
    task_description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    parent_version_id CHAR(36),
    is_current_version BOOLEAN NOT NULL DEFAULT TRUE,
    position_x INTEGER,
    position_y INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_node_workflow 
        FOREIGN KEY (workflow_id) REFERENCES `workflow`(workflow_id),
    CONSTRAINT fk_node_parent_version 
        FOREIGN KEY (parent_version_id) REFERENCES `node`(node_id),
    
    INDEX idx_node_base_id (node_base_id),
    INDEX idx_node_workflow_base_id (workflow_base_id),
    INDEX idx_node_current_version (node_base_id, workflow_base_id, is_current_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表5：processor（处理器）
CREATE TABLE IF NOT EXISTS `processor` (
    processor_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36),
    agent_id CHAR(36),
    name VARCHAR(255) NOT NULL,
    type ENUM('human', 'agent', 'mix') NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_processor_user 
        FOREIGN KEY (user_id) REFERENCES `user`(user_id),
    CONSTRAINT fk_processor_agent 
        FOREIGN KEY (agent_id) REFERENCES `agent`(agent_id),
    CONSTRAINT chk_processor_reference CHECK (
        (type = 'human' AND user_id IS NOT NULL AND agent_id IS NULL) OR
        (type = 'agent' AND agent_id IS NOT NULL AND user_id IS NULL) OR
        (type = 'mix' AND user_id IS NOT NULL AND agent_id IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表6：workflow_user（工作流用户关联表）
CREATE TABLE IF NOT EXISTS `workflow_user` (
    workflow_base_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (workflow_base_id, user_id),
    CONSTRAINT fk_wu_user 
        FOREIGN KEY (user_id) REFERENCES `user`(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表7：node_processor（节点处理器关联表）
CREATE TABLE IF NOT EXISTS `node_processor` (
    node_id CHAR(36) NOT NULL,
    processor_id CHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (node_id, processor_id),
    CONSTRAINT fk_np_node 
        FOREIGN KEY (node_id) REFERENCES `node`(node_id),
    CONSTRAINT fk_np_processor 
        FOREIGN KEY (processor_id) REFERENCES `processor`(processor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表8：node_connection（节点连接表）
CREATE TABLE IF NOT EXISTS `node_connection` (
    from_node_id CHAR(36) NOT NULL,
    to_node_id CHAR(36) NOT NULL,
    workflow_id CHAR(36) NOT NULL,
    connection_type VARCHAR(50) DEFAULT 'normal',
    condition_config JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (from_node_id, to_node_id, workflow_id),
    CONSTRAINT fk_nc_from_node 
        FOREIGN KEY (from_node_id) REFERENCES `node`(node_id),
    CONSTRAINT fk_nc_to_node 
        FOREIGN KEY (to_node_id) REFERENCES `node`(node_id),
    CONSTRAINT fk_nc_workflow 
        FOREIGN KEY (workflow_id) REFERENCES `workflow`(workflow_id),
    CONSTRAINT chk_no_self_loop 
        CHECK (from_node_id != to_node_id),
    
    INDEX idx_node_connection_workflow (workflow_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表9：workflow_instance（工作流实例表）
CREATE TABLE IF NOT EXISTS `workflow_instance` (
    workflow_instance_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    workflow_id CHAR(36) NOT NULL,
    workflow_base_id CHAR(36) NOT NULL,
    executor_id CHAR(36) NOT NULL,
    workflow_instance_name VARCHAR(255),
    status ENUM('pending', 'running', 'paused', 'completed', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
    input_data JSON,
    context_data JSON,
    output_data JSON,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    error_message TEXT,
    current_node_id CHAR(36),
    retry_count INTEGER NOT NULL DEFAULT 0,
    execution_summary JSON,
    quality_metrics JSON,
    data_lineage JSON,
    output_summary JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_workflow_instance_workflow 
        FOREIGN KEY (workflow_id) REFERENCES `workflow`(workflow_id),
    CONSTRAINT fk_workflow_instance_executor 
        FOREIGN KEY (executor_id) REFERENCES `user`(user_id),
    CONSTRAINT fk_workflow_instance_current_node 
        FOREIGN KEY (current_node_id) REFERENCES `node`(node_id),
    
    INDEX idx_workflow_instance_workflow_id (workflow_id),
    INDEX idx_workflow_instance_workflow_base_id (workflow_base_id),
    INDEX idx_workflow_instance_status (status),
    INDEX idx_workflow_instance_executor (executor_id),
    INDEX idx_workflow_instance_current_node (current_node_id),
    INDEX idx_workflow_instance_created_status (created_at DESC, status),
    INDEX idx_workflow_instance_completed (completed_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表10：node_instance（节点实例表）
CREATE TABLE IF NOT EXISTS `node_instance` (
    node_instance_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    workflow_instance_id CHAR(36) NOT NULL,
    node_id CHAR(36) NOT NULL,
    node_base_id CHAR(36) NOT NULL,
    node_instance_name VARCHAR(255),
    task_description TEXT,
    status ENUM('pending', 'waiting', 'running', 'completed', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
    input_data JSON,
    output_data JSON,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_node_instance_workflow_instance 
        FOREIGN KEY (workflow_instance_id) REFERENCES `workflow_instance`(workflow_instance_id),
    CONSTRAINT fk_node_instance_node 
        FOREIGN KEY (node_id) REFERENCES `node`(node_id),
    
    INDEX idx_node_instance_workflow_instance (workflow_instance_id),
    INDEX idx_node_instance_node_id (node_id),
    INDEX idx_node_instance_node_base_id (node_base_id),
    INDEX idx_node_instance_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表11：task_instance（任务实例表）
CREATE TABLE IF NOT EXISTS `task_instance` (
    task_instance_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    node_instance_id CHAR(36) NOT NULL,
    workflow_instance_id CHAR(36) NOT NULL,
    processor_id CHAR(36) NOT NULL,
    task_type ENUM('human', 'agent', 'mixed') DEFAULT 'human',
    task_title VARCHAR(255) NOT NULL,
    task_description TEXT,
    instructions TEXT,
    status ENUM('pending', 'assigned', 'waiting', 'in_progress', 'completed', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 1,
    input_data TEXT,
    context_data TEXT,
    output_data TEXT,
    result_summary TEXT,
    assigned_user_id CHAR(36),
    assigned_agent_id CHAR(36),
    assigned_at TIMESTAMP NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    estimated_duration INTEGER,
    actual_duration INTEGER,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    CONSTRAINT fk_task_instance_node_instance 
        FOREIGN KEY (node_instance_id) REFERENCES `node_instance`(node_instance_id),
    CONSTRAINT fk_task_instance_workflow_instance 
        FOREIGN KEY (workflow_instance_id) REFERENCES `workflow_instance`(workflow_instance_id),
    CONSTRAINT fk_task_instance_processor 
        FOREIGN KEY (processor_id) REFERENCES `processor`(processor_id),
    CONSTRAINT fk_task_instance_assigned_user 
        FOREIGN KEY (assigned_user_id) REFERENCES `user`(user_id),
    CONSTRAINT fk_task_instance_assigned_agent 
        FOREIGN KEY (assigned_agent_id) REFERENCES `agent`(agent_id),
    CONSTRAINT chk_priority CHECK (priority >= 1 AND priority <= 5),
    
    INDEX idx_task_instance_node_instance (node_instance_id),
    INDEX idx_task_instance_workflow_instance (workflow_instance_id),
    INDEX idx_task_instance_processor (processor_id),
    INDEX idx_task_instance_status (status),
    INDEX idx_task_instance_task_type (task_type),
    INDEX idx_task_instance_priority (priority),
    INDEX idx_task_instance_assigned_user (assigned_user_id),
    INDEX idx_task_instance_assigned_agent (assigned_agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表12：workflow_execution（工作流执行状态跟踪表）
CREATE TABLE IF NOT EXISTS `workflow_execution` (
    execution_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    workflow_instance_id CHAR(36) NOT NULL,
    current_node_id CHAR(36),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    execution_context JSON,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_workflow_execution_workflow_instance 
        FOREIGN KEY (workflow_instance_id) REFERENCES `workflow_instance`(workflow_instance_id),
    CONSTRAINT fk_workflow_execution_current_node 
        FOREIGN KEY (current_node_id) REFERENCES `node`(node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表13：node_execution（节点执行状态跟踪表）
CREATE TABLE IF NOT EXISTS `node_execution` (
    node_execution_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    node_instance_id CHAR(36) NOT NULL,
    execution_order INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    execution_data JSON,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_node_execution_node_instance 
        FOREIGN KEY (node_instance_id) REFERENCES `node_instance`(node_instance_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表14：mcp_tool_registry（MCP工具注册表）
CREATE TABLE IF NOT EXISTS `mcp_tool_registry` (
    tool_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    server_name VARCHAR(255) NOT NULL,
    server_url TEXT NOT NULL,
    server_description TEXT,
    tool_name VARCHAR(255) NOT NULL,
    tool_description TEXT,
    tool_parameters JSON DEFAULT (JSON_OBJECT()),
    auth_config JSON,
    timeout_seconds INTEGER DEFAULT 30,
    is_server_active BOOLEAN DEFAULT TRUE,
    is_tool_active BOOLEAN DEFAULT TRUE,
    server_status VARCHAR(20) DEFAULT 'unknown',
    tool_usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0,
    bound_agents_count INTEGER DEFAULT 0,
    last_tool_call TIMESTAMP NULL,
    last_health_check TIMESTAMP NULL,
    last_tool_discovery TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    
    UNIQUE KEY unique_user_server_tool (user_id, server_name, tool_name),
    CONSTRAINT fk_mcp_tool_user 
        FOREIGN KEY (user_id) REFERENCES `user`(user_id),
    
    INDEX idx_mcp_tool_registry_user_id (user_id),
    INDEX idx_mcp_tool_registry_server_name (server_name),
    INDEX idx_mcp_tool_registry_active (is_server_active, is_tool_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 表15：agent_tool_bindings（Agent工具绑定表）
CREATE TABLE IF NOT EXISTS `agent_tool_bindings` (
    binding_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    agent_id CHAR(36) NOT NULL,
    tool_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    binding_config JSON DEFAULT (JSON_OBJECT()),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_agent_tool (agent_id, tool_id),
    CONSTRAINT fk_atb_agent 
        FOREIGN KEY (agent_id) REFERENCES `agent`(agent_id),
    CONSTRAINT fk_atb_tool 
        FOREIGN KEY (tool_id) REFERENCES `mcp_tool_registry`(tool_id) ON DELETE CASCADE,
    CONSTRAINT fk_atb_user 
        FOREIGN KEY (user_id) REFERENCES `user`(user_id),
    
    INDEX idx_agent_tool_bindings_agent_id (agent_id),
    INDEX idx_agent_tool_bindings_tool_id (tool_id),
    INDEX idx_agent_tool_bindings_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""
            
            await self.execute_sql_file(sql_schema)
            logger.info("MySQL数据库架构初始化完成")
        except Exception as e:
            logger.error(f"初始化MySQL数据库架构失败: {e}")
            raise
    
    async def create_functions(self):
        """创建MySQL数据库函数"""
        try:
            logger.info("🔧 创建存储函数...")
            
            # 由于MySQL存储函数语法复杂，我们分别创建
            conn = await aiomysql.connect(
                host=self.settings.database.host,
                port=self.settings.database.port,
                user=self.settings.database.username,
                password=self.settings.database.password,
                db=self.settings.database.database,
                charset=self.settings.database.charset
            )
            
            try:
                async with conn.cursor() as cursor:
                    # create_initial_workflow函数
                    await cursor.execute("DROP FUNCTION IF EXISTS create_initial_workflow")
                    
                    create_initial_workflow_sql = """
                    CREATE FUNCTION create_initial_workflow(
                        p_name VARCHAR(255),
                        p_description TEXT,
                        p_creator_id CHAR(36)
                    ) RETURNS CHAR(36)
                    READS SQL DATA
                    MODIFIES SQL DATA
                    DETERMINISTIC
                    BEGIN
                        DECLARE v_workflow_base_id CHAR(36);
                        DECLARE v_workflow_id CHAR(36);
                        
                        SET v_workflow_base_id = UUID();
                        SET v_workflow_id = UUID();
                        
                        INSERT INTO `workflow` (
                            workflow_id, workflow_base_id, name, description, creator_id, version, is_current_version
                        ) VALUES (
                            v_workflow_id, v_workflow_base_id, p_name, p_description, p_creator_id, 1, TRUE
                        );
                        
                        RETURN v_workflow_id;
                    END
                    """
                    
                    await cursor.execute(create_initial_workflow_sql)
                    await conn.commit()
                    logger.info("✅ create_initial_workflow函数创建成功")
                    
                    # create_node_version函数
                    await cursor.execute("DROP FUNCTION IF EXISTS create_node_version")
                    
                    create_node_version_sql = """
                    CREATE FUNCTION create_node_version(
                        p_node_base_id CHAR(36),
                        p_workflow_base_id CHAR(36),
                        p_new_name VARCHAR(255),
                        p_new_description TEXT,
                        p_new_position_x INTEGER,
                        p_new_position_y INTEGER
                    ) RETURNS CHAR(36)
                    READS SQL DATA
                    MODIFIES SQL DATA
                    DETERMINISTIC
                    BEGIN
                        DECLARE v_current_node_id CHAR(36);
                        DECLARE v_current_workflow_id CHAR(36);
                        DECLARE v_new_node_id CHAR(36);
                        DECLARE v_new_version INTEGER;
                        
                        -- 获取当前版本的节点和工作流
                        SELECT n.node_id, n.version, w.workflow_id 
                        INTO v_current_node_id, v_new_version, v_current_workflow_id
                        FROM `node` n
                        JOIN `workflow` w ON w.workflow_base_id = n.workflow_base_id
                        WHERE n.node_base_id = p_node_base_id 
                          AND n.workflow_base_id = p_workflow_base_id
                          AND n.is_current_version = TRUE
                          AND w.is_current_version = TRUE;
                        
                        IF v_current_node_id IS NULL THEN
                            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Node not found';
                        END IF;
                        
                        SET v_new_version = v_new_version + 1;
                        SET v_new_node_id = UUID();
                        
                        -- 创建新版本节点
                        INSERT INTO `node` (
                            node_id, node_base_id, workflow_id, workflow_base_id,
                            name, type, task_description, version, parent_version_id, is_current_version,
                            position_x, position_y
                        )
                        SELECT 
                            v_new_node_id, node_base_id, workflow_id, workflow_base_id,
                            COALESCE(p_new_name, name), type, COALESCE(p_new_description, task_description), 
                            v_new_version, v_current_node_id, TRUE,
                            COALESCE(p_new_position_x, position_x), COALESCE(p_new_position_y, position_y)
                        FROM `node` 
                        WHERE node_id = v_current_node_id;
                        
                        -- 将旧版本标记为非当前版本
                        UPDATE `node` 
                        SET is_current_version = FALSE 
                        WHERE node_base_id = p_node_base_id AND workflow_base_id = p_workflow_base_id;
                        
                        -- 将新版本标记为当前版本
                        UPDATE `node` 
                        SET is_current_version = TRUE 
                        WHERE node_id = v_new_node_id;
                        
                        RETURN v_new_node_id;
                    END
                    """
                    
                    await cursor.execute(create_node_version_sql)
                    await conn.commit()
                    logger.info("✅ create_node_version函数创建成功")
                    
                    # create_workflow_node函数
                    await cursor.execute("DROP FUNCTION IF EXISTS create_workflow_node")
                    
                    create_workflow_node_sql = """
                    CREATE FUNCTION create_workflow_node(
                        p_workflow_id CHAR(36),
                        p_workflow_base_id CHAR(36),
                        p_name VARCHAR(255),
                        p_type VARCHAR(20),
                        p_task_description TEXT,
                        p_position_x INT,
                        p_position_y INT
                    ) RETURNS CHAR(36)
                    READS SQL DATA
                    MODIFIES SQL DATA
                    DETERMINISTIC
                    BEGIN
                        DECLARE v_node_id CHAR(36);
                        DECLARE v_node_base_id CHAR(36);
                        
                        SET v_node_id = UUID();
                        SET v_node_base_id = UUID();
                        
                        INSERT INTO `node` (
                            node_id, node_base_id, workflow_id, workflow_base_id, 
                            name, type, task_description, version, is_current_version,
                            position_x, position_y
                        ) VALUES (
                            v_node_id, v_node_base_id, p_workflow_id, p_workflow_base_id,
                            p_name, p_type, p_task_description, 1, TRUE,
                            p_position_x, p_position_y
                        );
                        
                        RETURN v_node_id;
                    END
                    """
                    
                    await cursor.execute(create_workflow_node_sql)
                    await conn.commit()
                    logger.info("✅ create_workflow_node函数创建成功")
                    
            finally:
                conn.close()
            
            logger.info("MySQL数据库函数创建完成")
        except Exception as e:
            logger.error(f"创建MySQL数据库函数失败: {e}")
            raise
    
    async def create_views(self):
        """创建MySQL视图"""
        try:
            views_sql = """
-- MySQL版本的数据库视图

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
FROM `workflow` w
JOIN `user` u ON u.user_id = w.creator_id
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
FROM `node` n
JOIN `workflow` w ON w.workflow_id = n.workflow_id
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
FROM `workflow` w
JOIN `user` u ON u.user_id = w.creator_id
LEFT JOIN `node` n ON n.workflow_id = w.workflow_id
WHERE w.is_deleted = FALSE
GROUP BY w.workflow_id, w.workflow_base_id, w.name, w.version, 
         w.change_description, w.created_at, u.username, w.is_current_version
ORDER BY w.workflow_base_id, w.version DESC;

-- MCP工具视图
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
FROM `mcp_tool_registry` 
WHERE is_deleted = FALSE
ORDER BY server_name, tool_name;

-- 工作流实例详情视图
CREATE OR REPLACE VIEW workflow_instance_detail_view AS
SELECT 
    wi.workflow_instance_id,
    wi.workflow_id,
    wi.workflow_base_id,
    wi.executor_id,
    wi.workflow_instance_name,
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
    COUNT(ni.node_instance_id) as total_nodes,
    SUM(CASE WHEN ni.status = 'completed' THEN 1 ELSE 0 END) as completed_nodes,
    SUM(CASE WHEN ni.status = 'failed' THEN 1 ELSE 0 END) as failed_nodes,
    SUM(CASE WHEN ni.status = 'running' THEN 1 ELSE 0 END) as running_nodes
FROM `workflow_instance` wi
JOIN `workflow` w ON w.workflow_id = wi.workflow_id
JOIN `user` u ON u.user_id = wi.executor_id
LEFT JOIN `node_instance` ni ON ni.workflow_instance_id = wi.workflow_instance_id AND ni.is_deleted = FALSE
WHERE wi.is_deleted = FALSE
GROUP BY wi.workflow_instance_id, wi.workflow_id, wi.workflow_base_id, wi.executor_id,
         wi.workflow_instance_name, wi.status, wi.input_data, 
         wi.context_data, wi.output_data, wi.started_at, wi.completed_at, 
         wi.error_message, wi.current_node_id, wi.retry_count, wi.execution_summary,
         wi.quality_metrics, wi.data_lineage, wi.output_summary, wi.created_at, wi.updated_at,
         w.name, w.description, u.username;

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
FROM `task_instance` ti
JOIN `node_instance` ni ON ni.node_instance_id = ti.node_instance_id
JOIN `node` n ON n.node_id = ni.node_id
JOIN `processor` p ON p.processor_id = ti.processor_id
JOIN `workflow_instance` wi ON wi.workflow_instance_id = ti.workflow_instance_id
JOIN `workflow` w ON w.workflow_id = wi.workflow_id
LEFT JOIN `user` au ON au.user_id = ti.assigned_user_id
LEFT JOIN `agent` aa ON aa.agent_id = ti.assigned_agent_id
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
    SUM(CASE WHEN ti.status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
    SUM(CASE WHEN ti.status = 'failed' THEN 1 ELSE 0 END) as failed_tasks,
    SUM(CASE WHEN ti.status = 'in_progress' THEN 1 ELSE 0 END) as running_tasks
FROM `node_instance` ni
JOIN `node` n ON n.node_id = ni.node_id
JOIN `workflow_instance` wi ON wi.workflow_instance_id = ni.workflow_instance_id
JOIN `workflow` w ON w.workflow_id = wi.workflow_id
LEFT JOIN `task_instance` ti ON ti.node_instance_id = ni.node_instance_id AND ti.is_deleted = FALSE
WHERE ni.is_deleted = FALSE AND wi.is_deleted = FALSE
GROUP BY ni.node_instance_id, ni.workflow_instance_id, ni.node_id, ni.node_base_id,
         ni.node_instance_name, ni.task_description, ni.status, ni.input_data, ni.output_data,
         ni.started_at, ni.completed_at, ni.error_message, ni.retry_count,
         ni.created_at, ni.updated_at, n.name, n.type, n.task_description,
         n.position_x, n.position_y, wi.workflow_instance_name, w.name;
"""
            
            await self.execute_sql_file(views_sql)
            logger.info("MySQL数据库视图创建完成")
        except Exception as e:
            logger.error(f"创建MySQL数据库视图失败: {e}")
            raise
    
    async def create_sample_data(self):
        """创建示例数据"""
        try:
            sample_data_sql = """
-- 插入示例用户
INSERT IGNORE INTO `user` (user_id, username, password_hash, email, role, description) VALUES
(UUID(), 'admin', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'admin@example.com', 'admin', 'System Administrator'),
(UUID(), 'user1', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'user1@example.com', 'user', 'Regular User 1'),
(UUID(), 'user2', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'user2@example.com', 'user', 'Regular User 2');

-- 插入示例Agent
INSERT IGNORE INTO `agent` (agent_id, agent_name, description, model_name, is_autonomous) VALUES
(UUID(), 'GPT-4', 'OpenAI GPT-4 Agent', 'gpt-4', false),
(UUID(), 'Claude', 'Anthropic Claude Agent', 'claude-3', false),
(UUID(), 'AutoAgent', 'Autonomous AI Agent', 'auto-model', true);
"""
            
            await self.execute_sql_file(sample_data_sql)
            logger.info("MySQL示例数据创建完成")
        except Exception as e:
            logger.error(f"创建MySQL示例数据失败: {e}")
            raise
    
    async def initialize_all(self, include_sample_data: bool = False):
        """完整初始化MySQL数据库"""
        try:
            logger.info("开始初始化MySQL数据库...")
            
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
            
            logger.info("MySQL数据库初始化完成！")
        except Exception as e:
            logger.error(f"MySQL数据库初始化失败: {e}")
            raise


async def main():
    """主函数"""
    import sys
    
    include_sample_data = '--with-sample-data' in sys.argv
    
    initializer = MySQLDatabaseInitializer()
    await initializer.initialize_all(include_sample_data)


if __name__ == "__main__":
    asyncio.run(main())