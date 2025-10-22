"""
模拟器执行相关数据模型
Simulator Execution Models
"""

import uuid
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from .base import BaseEntity, CreateRequest, UpdateRequest


class SimulatorExecutionType(str, Enum):
    """模拟器执行类型"""
    DIRECT_SUBMIT = "direct_submit"        # 弱模型直接提交
    CONVERSATION_RESULT = "conversation_result"  # 经过对话后提交


class SimulatorDecision(str, Enum):
    """模拟器决策类型"""
    DIRECT_SUBMIT = "direct_submit"           # 直接提交
    CONSULT_COMPLETE = "consult_complete"     # 咨询完成
    INTERRUPTED = "interrupted"               # 中途中断
    MAX_ROUNDS_REACHED = "max_rounds_reached" # 达到最大轮数
    WEAK_MODEL_TERMINATED = "weak_model_terminated"  # 弱模型自主终止


class ConversationRole(str, Enum):
    """对话角色"""
    USER = "user"                # 普通用户
    ASSISTANT = "assistant"      # AI助手
    WEAK_MODEL = "weak_model"    # 弱模型
    STRONG_MODEL = "strong_model" # 强模型


class SimulatorExecutionLogBase(BaseModel):
    """模拟器执行日志基础模型"""
    task_instance_id: uuid.UUID = Field(..., description="任务实例ID")
    session_id: uuid.UUID = Field(..., description="对话会话ID")
    execution_type: SimulatorExecutionType = Field(..., description="执行类型")
    weak_model: str = Field(..., description="弱模型名称")
    strong_model: str = Field(..., description="强模型名称")
    total_rounds: int = Field(default=0, description="总对话轮数")
    max_rounds: int = Field(default=20, description="最大对话轮数")
    final_decision: SimulatorDecision = Field(..., description="最终决策")
    result_data: Dict[str, Any] = Field(..., description="执行结果数据")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="结果置信度")
    decision_reasoning: Optional[str] = Field(None, description="决策推理过程")


class SimulatorExecutionLog(SimulatorExecutionLogBase, BaseEntity):
    """模拟器执行日志完整模型"""
    log_id: uuid.UUID = Field(..., description="日志ID")


class SimulatorExecutionLogCreate(SimulatorExecutionLogBase, CreateRequest):
    """模拟器执行日志创建模型"""
    pass


class SimulatorExecutionLogResponse(SimulatorExecutionLogBase):
    """模拟器执行日志响应模型"""
    log_id: uuid.UUID
    created_at: Optional[str] = None


class SimulatorTaskRequest(BaseModel):
    """模拟器任务请求"""
    task_instance_id: uuid.UUID = Field(..., description="任务实例ID")
    weak_model: Optional[str] = Field("Pro/Qwen/Qwen2.5-7B-Instruct", description="弱模型名称")
    max_rounds: int = Field(20, ge=1, le=50, description="最大对话轮数")
    auto_decision: bool = Field(True, description="是否自动决策")


class SimulatorTaskResponse(BaseModel):
    """模拟器任务响应"""
    success: bool = Field(..., description="是否成功")
    task_instance_id: uuid.UUID = Field(..., description="任务实例ID")
    execution_type: SimulatorExecutionType = Field(..., description="执行类型")
    result: Dict[str, Any] = Field(..., description="执行结果")
    conversation_summary: Optional[Dict[str, Any]] = Field(None, description="对话摘要")
    session_id: Optional[uuid.UUID] = Field(None, description="对话会话ID")


class ConversationMessageExtended(BaseModel):
    """扩展的对话消息模型"""
    message_id: Optional[uuid.UUID] = None
    session_id: uuid.UUID = Field(..., description="会话ID")
    role: ConversationRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    context_data: Optional[Dict[str, Any]] = Field(None, description="上下文数据")
    round_number: Optional[int] = Field(None, description="对话轮数")
    model_info: Optional[Dict[str, Any]] = Field(None, description="模型信息")
    created_at: Optional[str] = None


class SimulatorSessionStatus(str, Enum):
    """Simulator会话状态"""
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class SimulatorConversationSession(BaseModel):
    """Simulator对话会话"""
    session_id: str
    task_instance_id: str
    node_instance_id: str
    processor_id: str
    weak_model: str
    strong_model: str
    max_rounds: int = 20
    current_round: int = 0
    status: SimulatorSessionStatus = SimulatorSessionStatus.ACTIVE
    final_decision: Optional[SimulatorDecision] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class SimulatorConversationMessage(BaseModel):
    """Simulator对话消息"""
    message_id: str
    session_id: str
    round_number: int
    role: ConversationRole
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


# 请求/响应模型
class CreateSimulatorSessionRequest(BaseModel):
    """创建Simulator会话请求"""
    task_instance_id: str
    node_instance_id: str
    processor_id: str
    weak_model: str
    strong_model: str
    max_rounds: int = Field(default=20, ge=1, le=50)


class SendSimulatorMessageRequest(BaseModel):
    """发送Simulator消息请求"""
    session_id: str
    role: ConversationRole
    content: str
    metadata: Optional[Dict[str, Any]] = None


class SimulatorDecisionRequest(BaseModel):
    """Simulator决策请求"""
    session_id: str
    decision_type: SimulatorDecision
    result_data: Dict[str, Any]
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    decision_reasoning: Optional[str] = None


class SimulatorSessionResponse(BaseModel):
    """Simulator会话响应"""
    session: SimulatorConversationSession
    messages: List[SimulatorConversationMessage]
    can_continue: bool
    next_action: str  # "wait_weak_model", "wait_strong_model", "submit_decision"


class SimulatorExecutionResult(BaseModel):
    """Simulator执行结果"""
    success: bool = Field(..., description="是否成功")
    execution_type: SimulatorExecutionType = Field(..., description="执行类型")
    final_decision: SimulatorDecision = Field(..., description="最终决策")
    result_data: Dict[str, Any] = Field(..., description="结果数据")
    session_id: Optional[str] = Field(None, description="会话ID")
    total_rounds: int = Field(default=0, description="总对话轮数")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="置信度")
    decision_reasoning: Optional[str] = Field(None, description="决策推理")
    conversation_summary: Optional[str] = Field(None, description="对话摘要")