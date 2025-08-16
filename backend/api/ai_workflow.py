"""
AI工作流生成API路由
AI Workflow Generation API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from loguru import logger

from ..services.ai_workflow_generator import AIWorkflowGeneratorService
from ..models.workflow_import_export import WorkflowExport
from ..models.user import UserResponse
from ..utils.auth import get_current_user
from ..utils.exceptions import ValidationError


router = APIRouter(prefix="/ai-workflows", tags=["AI工作流生成"])

# AI生成服务实例
ai_generator = AIWorkflowGeneratorService()


class AIWorkflowGenerateRequest(BaseModel):
    """AI工作流生成请求"""
    task_description: str = Field(..., description="任务描述", min_length=5, max_length=1000)
    workflow_name: Optional[str] = Field(None, description="可选的工作流名称")


class AIWorkflowGenerateResponse(BaseModel):
    """AI工作流生成响应"""
    success: bool = Field(True, description="是否成功")
    workflow_data: WorkflowExport = Field(..., description="生成的工作流数据")
    message: str = Field("AI工作流生成成功", description="响应消息")


@router.post("/generate", response_model=AIWorkflowGenerateResponse)
async def generate_workflow_from_description(
    request: AIWorkflowGenerateRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    根据任务描述生成AI工作流
    
    **功能说明：**
    - 用户输入任务描述
    - AI自动分析并生成完全个性化的工作流模板
    - 绝不使用固定模板，完全根据具体任务设计
    - 返回标准JSON格式，可直接导入
    
    **设计原则：**
    - 完全个性化：根据具体任务内容设计节点和流程
    - 避免通用词汇：不会出现"项目启动"等模板化名称
    - 支持并行分支：可以同时执行的任务会设计为并行
    - 严禁循环：确保是有向无环图（DAG）
    
    **示例描述：**
    - "分析期末学生成绩，找出学习薄弱环节"
    - "开发一个在线教育平台的用户管理模块"
    - "制作产品介绍视频并在社交媒体推广"
    """
    try:
        user_id = current_user.user_id
        
        logger.info(f"🤖 [AI-WORKFLOW-API] 收到AI工作流生成请求")
        logger.info(f"🤖 [AI-WORKFLOW-API] 用户ID: {user_id}")
        logger.info(f"🤖 [AI-WORKFLOW-API] 任务描述: '{request.task_description}'")
        logger.info(f"🤖 [AI-WORKFLOW-API] 任务描述长度: {len(request.task_description)}")
        logger.info(f"🤖 [AI-WORKFLOW-API] 工作流名称: '{request.workflow_name}'")
        
        # 验证请求数据
        if not request.task_description or len(request.task_description.strip()) < 5:
            logger.error(f"🤖 [AI-WORKFLOW-API] 任务描述太短: '{request.task_description}'")
            raise ValidationError("任务描述至少需要5个字符")
        
        if len(request.task_description) > 1000:
            logger.error(f"🤖 [AI-WORKFLOW-API] 任务描述太长: {len(request.task_description)}")
            raise ValidationError("任务描述不能超过1000个字符")
        
        logger.info(f"🤖 [AI-WORKFLOW-API] 请求数据验证通过，开始调用AI生成服务")
        
        # 调用AI生成服务
        workflow_data = await ai_generator.generate_workflow_from_description(
            task_description=request.task_description,
            user_id=user_id
        )
        
        logger.info(f"🤖 [AI-WORKFLOW-API] AI生成服务返回成功")
        logger.info(f"🤖 [AI-WORKFLOW-API] 生成的工作流名称: '{workflow_data.name}'")
        logger.info(f"🤖 [AI-WORKFLOW-API] 节点数量: {len(workflow_data.nodes)}")
        logger.info(f"🤖 [AI-WORKFLOW-API] 连接数量: {len(workflow_data.connections)}")
        
        # 如果用户指定了名称，使用用户指定的名称
        if request.workflow_name:
            original_name = workflow_data.name
            workflow_data.name = request.workflow_name
            logger.info(f"🤖 [AI-WORKFLOW-API] 使用用户指定名称: '{original_name}' → '{workflow_data.name}'")
        
        logger.info(f"🤖 [AI-WORKFLOW-API] AI工作流生成完成: {workflow_data.name}")
        
        response_message = f"🤖 AI成功生成个性化工作流：{len(workflow_data.nodes)}个节点，{len(workflow_data.connections)}个连接"
        logger.info(f"🤖 [AI-WORKFLOW-API] 响应消息: {response_message}")
        
        return AIWorkflowGenerateResponse(
            success=True,
            workflow_data=workflow_data,
            message=response_message
        )
        
    except ValidationError as e:
        logger.error(f"🤖 [AI-WORKFLOW-API] 数据验证失败: {str(e)}")
        logger.error(f"🤖 [AI-WORKFLOW-API] 请求数据: task_description='{request.task_description}', workflow_name='{request.workflow_name}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AI工作流生成失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"🤖 [AI-WORKFLOW-API] AI工作流生成服务异常: {type(e).__name__}: {str(e)}")
        logger.error(f"🤖 [AI-WORKFLOW-API] 异常发生时的请求数据: task_description='{request.task_description}', workflow_name='{request.workflow_name}'")
        import traceback
        logger.error(f"🤖 [AI-WORKFLOW-API] 异常堆栈: {traceback.format_exc()}")
        
        # 不再提供模板fallback，直接返回错误
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI工作流生成服务暂时不可用，请稍后再试。这是一个纯AI驱动的功能，需要网络连接到AI服务。错误详情: {str(e)}"
        )