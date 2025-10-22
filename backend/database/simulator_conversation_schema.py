"""
Simulator对话数据库表结构
Simulator Conversation Database Schema
"""

CREATE_SIMULATOR_CONVERSATION_TABLES = """
-- Simulator对话会话表
CREATE TABLE IF NOT EXISTS `simulator_conversation_session` (
    session_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    task_instance_id CHAR(36) NOT NULL,
    node_instance_id CHAR(36) NOT NULL,
    processor_id CHAR(36) NOT NULL,
    weak_model VARCHAR(255) NOT NULL COMMENT 'Simulator模型名称',
    strong_model VARCHAR(255) NOT NULL COMMENT '强模型名称(来自processor绑定的agent)',
    max_rounds INT NOT NULL DEFAULT 20,
    current_round INT NOT NULL DEFAULT 0,
    status ENUM('active', 'completed', 'interrupted', 'failed') NOT NULL DEFAULT 'active',
    final_decision ENUM('direct_submit', 'consult_complete', 'max_rounds_reached', 'weak_model_terminated') NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,

    INDEX idx_session_task_instance (task_instance_id),
    INDEX idx_session_node_instance (node_instance_id),
    INDEX idx_session_processor (processor_id),
    INDEX idx_session_status (status),
    INDEX idx_session_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Simulator对话消息表
CREATE TABLE IF NOT EXISTS `simulator_conversation_message` (
    message_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    round_number INT NOT NULL,
    role ENUM('weak_model', 'strong_model', 'system') NOT NULL,
    content TEXT NOT NULL,
    metadata JSON NULL COMMENT '消息元数据：模型参数、耗时、决策原因等',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES simulator_conversation_session(session_id) ON DELETE CASCADE,
    INDEX idx_message_session (session_id),
    INDEX idx_message_round (session_id, round_number),
    INDEX idx_message_role (role),
    INDEX idx_message_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Simulator执行结果表
CREATE TABLE IF NOT EXISTS `simulator_execution_result` (
    result_id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    session_id CHAR(36) NOT NULL,
    task_instance_id CHAR(36) NOT NULL,
    execution_type ENUM('direct_submit', 'conversation_result') NOT NULL,
    result_data JSON NOT NULL COMMENT '执行结果数据',
    confidence_score DECIMAL(3,2) NULL COMMENT '结果置信度 0.00-1.00',
    total_rounds INT NOT NULL DEFAULT 0,
    decision_reasoning TEXT NULL COMMENT '决策推理过程',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES simulator_conversation_session(session_id) ON DELETE CASCADE,
    INDEX idx_result_session (session_id),
    INDEX idx_result_task_instance (task_instance_id),
    INDEX idx_result_type (execution_type),
    INDEX idx_result_confidence (confidence_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

# 创建表的辅助函数
async def create_simulator_conversation_tables(connection):
    """创建simulator对话相关的数据库表"""
    statements = [stmt.strip() for stmt in CREATE_SIMULATOR_CONVERSATION_TABLES.split(';') if stmt.strip()]

    for statement in statements:
        try:
            await connection.execute(statement)
            print(f"✅ 创建表成功: {statement[:50]}...")
        except Exception as e:
            print(f"❌ 创建表失败: {e}")
            raise