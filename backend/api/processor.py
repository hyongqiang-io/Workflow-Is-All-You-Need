"""
处理器管理API路由
Processor Management API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from loguru import logger

from ..models.base import BaseResponse
from ..models.processor import ProcessorType, ProcessorCreate, ProcessorUpdate
from ..models.agent import AgentUpdate, AgentCreate
from ..repositories.processor.processor_repository import ProcessorRepository
from ..repositories.user.user_repository import UserRepository
from ..repositories.agent.agent_repository import AgentRepository
from ..utils.middleware import get_current_active_user, CurrentUser, get_current_user_context
from ..services.cascade_deletion_service import cascade_deletion_service
from ..utils.exceptions import ValidationError, handle_validation_error

# 创建路由器
router = APIRouter(prefix="/processors", tags=["处理器管理"])

# 处理器仓库实例
processor_repository = ProcessorRepository()
user_repository = UserRepository()
agent_repository = AgentRepository()


@router.get("/test-no-auth")
async def test_route_no_auth():
    """测试路由 - 无需认证"""
    import datetime
    return {"message": "processor test route works", "timestamp": datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")}

@router.delete("/test-delete-simple/{processor_id}")
async def test_delete_simple(processor_id: str):
    """简单删除测试 - 无需认证"""
    import datetime
    logger.info(f"测试删除端点被调用: {processor_id}")
    return {
        "message": f"Delete test successful for processor: {processor_id}",
        "success": True,
        "method": "DELETE",
        "path": f"/processors/test-delete-simple/{processor_id}",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    }

@router.delete("/delete-test/{processor_id}")
async def test_delete_route(processor_id: str):
    """另一个删除测试路由 - 无需认证"""
    import datetime
    logger.info(f"另一个测试删除端点被调用: {processor_id}")
    return {
        "message": f"Alternative delete test for processor: {processor_id}",
        "success": True,
        "method": "DELETE",
        "path": f"/processors/delete-test/{processor_id}",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    }

@router.get("/test-with-auth")
async def test_route_with_auth(current_user: CurrentUser = Depends(get_current_user_context)):
    """测试路由 - 需要认证"""
    return {
        "message": "authenticated test route works", 
        "user_id": str(current_user.user_id),
        "username": current_user.username
    }

@router.post("/test-create", response_model=BaseResponse)
async def test_create_processor(
    processor_data: ProcessorCreate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """测试创建处理器 - 需要认证"""
    try:
        # 验证输入数据
        if processor_data.type == ProcessorType.HUMAN and not processor_data.user_id:
            raise ValidationError("human类型处理器必须指定user_id")
        elif processor_data.type == ProcessorType.AGENT and not processor_data.agent_id:
            raise ValidationError("agent类型处理器必须指定agent_id")
        elif processor_data.type == ProcessorType.SIMULATOR and not processor_data.agent_id:
            raise ValidationError("simulator类型处理器必须指定agent_id")
        elif processor_data.type == ProcessorType.MIX and (not processor_data.user_id or not processor_data.agent_id):
            raise ValidationError("mix类型处理器必须同时指定user_id和agent_id")
        
        # 创建处理器
        new_processor = await processor_repository.create_processor(processor_data, current_user.user_id)
        
        if not new_processor:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建处理器失败"
            )
        
        return BaseResponse(
            success=True,
            message="处理器创建成功（测试）",
            data={
                "processor": {
                    "processor_id": str(new_processor['processor_id']),
                    "name": new_processor['name'],
                    "type": new_processor['type'],
                    "version": new_processor['version'],
                    "created_at": new_processor['created_at'].isoformat() if new_processor['created_at'] else None,
                    "user_id": str(new_processor['user_id']) if new_processor['user_id'] else None,
                    "agent_id": str(new_processor['agent_id']) if new_processor['agent_id'] else None,
                }
            }
        )
        
    except ValidationError as e:
        logger.warning(f"处理器创建验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"创建处理器异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建处理器失败，请稍后再试"
        )

@router.post("/", response_model=BaseResponse)
async def create_processor(
    processor_data: ProcessorCreate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    创建新的处理器
    
    Args:
        processor_data: 处理器创建数据
        current_user: 当前用户
        
    Returns:
        创建的处理器信息
    """
    try:
        # 验证输入数据
        if processor_data.type == ProcessorType.HUMAN and not processor_data.user_id:
            raise ValidationError("human类型处理器必须指定user_id")
        elif processor_data.type == ProcessorType.AGENT and not processor_data.agent_id:
            raise ValidationError("agent类型处理器必须指定agent_id")
        elif processor_data.type == ProcessorType.SIMULATOR and not processor_data.agent_id:
            raise ValidationError("simulator类型处理器必须指定agent_id")
        elif processor_data.type == ProcessorType.MIX and (not processor_data.user_id or not processor_data.agent_id):
            raise ValidationError("mix类型处理器必须同时指定user_id和agent_id")
        
        # 创建处理器
        new_processor = await processor_repository.create_processor(processor_data, current_user.user_id)
        
        if not new_processor:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建处理器失败"
            )
        
        return BaseResponse(
            success=True,
            message="处理器创建成功",
            data={
                "processor": {
                    "processor_id": str(new_processor['processor_id']),
                    "name": new_processor['name'],
                    "type": new_processor['type'],
                    "version": new_processor['version'],
                    "created_at": new_processor['created_at'].isoformat() if new_processor['created_at'] else None,
                    "user_id": str(new_processor['user_id']) if new_processor['user_id'] else None,
                    "agent_id": str(new_processor['agent_id']) if new_processor['agent_id'] else None,
                },
                "created_by": str(current_user.user_id)
            }
        )
        
    except ValidationError as e:
        logger.warning(f"处理器创建验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"创建处理器异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建处理器失败，请稍后再试"
        )


@router.get("/available-test", response_model=BaseResponse)
async def get_available_processors_test(
    processor_type: Optional[str] = None
):
    """获取可用的处理器列表（测试版本，无需认证）"""
    try:
        available_processors = []
        
        # 获取用户处理器（如果类型为空或为HUMAN/MIX）
        if not processor_type or processor_type in ["human", "mix"]:
            users = await user_repository.get_all_active_users()
            for user in users:
                available_processors.append({
                    "id": str(user['user_id']),
                    "name": f"用户: {user['username']}",
                    "type": "human",
                    "entity_type": "user",
                    "entity_id": str(user['user_id']),
                    "description": f"用户 {user['username']} ({user['email']})",
                    "role": user.get('role', 'user'),
                    "status": user.get('status', True)
                })
        
        # 获取Agent处理器（如果类型为空或为AGENT/MIX）
        if not processor_type or processor_type in ["agent", "mix"]:
            agents = await agent_repository.get_all_active_agents()
            for agent in agents:
                available_processors.append({
                    "id": str(agent['agent_id']),
                    "name": f"{agent['agent_name']}",
                    "type": "agent",
                    "entity_type": "agent",
                    "entity_id": str(agent['agent_id']),
                    "description": agent.get('description', ''),
                    "capabilities": agent.get('tags', []),  # 修复：使用tags字段而不是capabilities
                    "tags": agent.get('tags', []),  # 同时保留tags字段以备将来使用
                    "status": agent.get('status', True)
                })
        
        return BaseResponse(
            success=True,
            message="获取可用处理器列表成功（测试）",
            data={
                "processors": available_processors,
                "count": len(available_processors),
                "filter": processor_type if processor_type else "all"
            }
        )
        
    except Exception as e:
        logger.error(f"获取可用处理器列表异常: {e}")
        # 打印详细的异常信息用于调试
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取可用处理器列表失败: {str(e)}"
        )

@router.get("/available", response_model=BaseResponse)
async def get_available_processors(
    processor_type: Optional[ProcessorType] = Query(None, description="处理器类型筛选"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取可用的处理器列表（从用户和Agent表获取）
    
    Args:
        processor_type: 处理器类型筛选
        current_user: 当前用户
        
    Returns:
        可用处理器列表
    """
    try:
        available_processors = []
        
        # 获取用户处理器（如果类型为空或为HUMAN/MIX）
        if not processor_type or processor_type in [ProcessorType.HUMAN, ProcessorType.MIX]:
            users = await user_repository.get_all_active_users()
            for user in users:
                available_processors.append({
                    "id": str(user['user_id']),
                    "name": f"用户: {user['username']}",
                    "type": "human",
                    "entity_type": "user",
                    "entity_id": str(user['user_id']),
                    "description": f"用户 {user['username']} ({user['email']})",
                    "role": user.get('role', 'user'),
                    "status": user.get('status', True)
                })
        
        # 获取Agent处理器（如果类型为空或为AGENT/MIX）
        if not processor_type or processor_type in ["agent", "mix"]:
            agents = await agent_repository.get_all_active_agents()
            for agent in agents:
                available_processors.append({
                    "id": str(agent['agent_id']),
                    "name": f"{agent['agent_name']}",
                    "type": "agent",
                    "entity_type": "agent",
                    "entity_id": str(agent['agent_id']),
                    "description": agent.get('description', ''),
                    "capabilities": agent.get('tags', []),  # 修复：使用tags字段而不是capabilities
                    "tags": agent.get('tags', []),  # 同时保留tags字段以备将来使用
                    "status": agent.get('status', True)
                })
        
        return BaseResponse(
            success=True,
            message="获取可用处理器列表成功",
            data={
                "processors": available_processors,
                "count": len(available_processors),
                "filter": processor_type.value if processor_type else "all"
            }
        )
        
    except Exception as e:
        logger.error(f"获取可用处理器列表异常: {e}")
        # 打印详细的异常信息用于调试
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取可用处理器列表失败: {str(e)}"
        )


@router.get("/grouped", response_model=BaseResponse)
async def get_processors_grouped(
    current_user: Optional[CurrentUser] = Depends(get_current_user_context)
):
    """
    获取按群组分类的处理器列表

    Args:
        current_user: 当前用户（可选）

    Returns:
        按群组分类的处理器列表
    """
    try:
        user_id = str(current_user.user_id) if current_user else None
        grouped_processors = await processor_repository.get_processors_grouped(user_id)

        return BaseResponse(
            success=True,
            data=grouped_processors,
            message="获取分组处理器列表成功"
        )

    except Exception as e:
        logger.error(f"获取分组处理器列表失败: {e}")
        return BaseResponse(
            success=False,
            message="获取分组处理器列表失败",
            data={"公共Processor": []}
        )


@router.get("/registered", response_model=BaseResponse)
async def get_registered_processors(
    processor_type: Optional[ProcessorType] = Query(None, description="处理器类型筛选"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取已注册的处理器列表（仅显示公开的或用户所在群组的处理器）

    Args:
        processor_type: 处理器类型筛选
        current_user: 当前用户

    Returns:
        已注册处理器列表
    """
    try:
        user_id = current_user.user_id

        if processor_type:
            processors = await processor_repository.get_accessible_processors_by_type(processor_type, user_id)
        else:
            # 获取所有类型的用户可访问处理器
            all_processors = []
            for ptype in ProcessorType:
                processors_of_type = await processor_repository.get_accessible_processors_by_type(ptype, user_id)
                all_processors.extend(processors_of_type)
            processors = all_processors

        # 格式化响应数据
        formatted_processors = []
        for processor in processors:
            formatted_processor = {
                "processor_id": str(processor['processor_id']),
                "name": processor['name'],
                "type": processor['type'],
                "version": processor['version'],
                "created_at": processor['created_at'].isoformat() if processor['created_at'] else None,
                "user_id": str(processor['user_id']) if processor['user_id'] else None,
                "agent_id": str(processor['agent_id']) if processor['agent_id'] else None,
                "username": processor.get('username'),
                "user_email": processor.get('user_email'),
                "agent_name": processor.get('agent_name'),
                "agent_description": processor.get('agent_description'),
                "creator_name": processor.get('creator_name'),
                "group_id": str(processor['group_id']) if processor['group_id'] else None,
                "group_name": processor.get('group_name'),
                "group_is_public": processor.get('group_is_public')
            }
            formatted_processors.append(formatted_processor)

        return BaseResponse(
            success=True,
            message="获取已注册处理器列表成功",
            data={
                "processors": formatted_processors,
                "count": len(formatted_processors),
                "filter": processor_type.value if processor_type else "all"
            }
        )
        
    except Exception as e:
        logger.error(f"获取已注册处理器列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取已注册处理器列表失败"
        )


@router.get("/{processor_id}", response_model=BaseResponse)
async def get_processor_details(
    processor_id: uuid.UUID = Path(..., description="处理器ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取处理器详细信息
    
    Args:
        processor_id: 处理器ID
        current_user: 当前用户
        
    Returns:
        处理器详细信息
    """
    try:
        processor = await processor_repository.get_processor_with_details(processor_id)
        
        if not processor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="处理器不存在"
            )
        
        # 格式化响应数据
        formatted_processor = {
            "processor_id": str(processor['processor_id']),
            "name": processor['name'],
            "type": processor['type'],
            "version": processor['version'],
            "created_at": processor['created_at'].isoformat() if processor['created_at'] else None,
            "user_id": str(processor['user_id']) if processor['user_id'] else None,
            "agent_id": str(processor['agent_id']) if processor['agent_id'] else None,
            "username": processor.get('username'),
            "user_email": processor.get('user_email'),
            "agent_name": processor.get('agent_name'),
            "agent_description": processor.get('agent_description')
        }
        
        return BaseResponse(
            success=True,
            message="获取处理器详情成功",
            data={"processor": formatted_processor}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取处理器详情异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取处理器详情失败"
        )


@router.get("/user/{user_id}", response_model=BaseResponse)
async def get_user_processors(
    user_id: uuid.UUID = Path(..., description="用户ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取用户的处理器列表
    
    Args:
        user_id: 用户ID
        current_user: 当前用户
        
    Returns:
        用户处理器列表
    """
    try:
        processors = await processor_repository.get_processors_by_user(user_id)
        
        # 格式化响应数据
        formatted_processors = []
        for processor in processors:
            formatted_processor = {
                "processor_id": str(processor['processor_id']),
                "name": processor['name'],
                "type": processor['type'],
                "version": processor['version'],
                "created_at": processor['created_at'].isoformat() if processor['created_at'] else None,
                "user_id": str(processor['user_id']) if processor['user_id'] else None,
                "agent_id": str(processor['agent_id']) if processor['agent_id'] else None,
                "username": processor.get('username'),
                "user_email": processor.get('user_email'),
                "agent_name": processor.get('agent_name'),
                "agent_description": processor.get('agent_description')
            }
            formatted_processors.append(formatted_processor)
        
        return BaseResponse(
            success=True,
            message="获取用户处理器列表成功",
            data={
                "processors": formatted_processors,
                "count": len(formatted_processors),
                "user_id": str(user_id)
            }
        )
        
    except Exception as e:
        logger.error(f"获取用户处理器列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户处理器列表失败"
        )


@router.get("/search/", response_model=BaseResponse)
async def search_processors(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(50, ge=1, le=100, description="结果数量限制"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    搜索处理器
    
    Args:
        keyword: 搜索关键词
        limit: 结果数量限制
        current_user: 当前用户
        
    Returns:
        搜索结果
    """
    try:
        processors = await processor_repository.search_processors(keyword, limit)
        
        # 格式化响应数据
        formatted_processors = []
        for processor in processors:
            formatted_processor = {
                "processor_id": str(processor['processor_id']),
                "name": processor['name'],
                "type": processor['type'],
                "version": processor['version'],
                "created_at": processor['created_at'].isoformat() if processor['created_at'] else None,
                "user_id": str(processor['user_id']) if processor['user_id'] else None,
                "agent_id": str(processor['agent_id']) if processor['agent_id'] else None,
                "username": processor.get('username'),
                "user_email": processor.get('user_email'),
                "agent_name": processor.get('agent_name'),
                "agent_description": processor.get('agent_description')
            }
            formatted_processors.append(formatted_processor)
        
        return BaseResponse(
            success=True,
            message="搜索完成",
            data={
                "processors": formatted_processors,
                "count": len(formatted_processors),
                "keyword": keyword
            }
        )
        
    except Exception as e:
        logger.error(f"搜索处理器异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索失败，请稍后再试"
        )


@router.delete("/delete/{processor_id}", response_model=BaseResponse)
async def delete_processor(
    processor_id: uuid.UUID = Path(..., description="处理器ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除处理器
    
    Args:
        processor_id: 处理器ID
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        logger.info(f"DELETE请求进入 - processor_id={processor_id}, user_id={current_user.user_id}")
        logger.info(f"处理器ID类型: {type(processor_id)}, 值: {processor_id}")
        
        # 首先检查处理器是否存在
        logger.info(f"开始查询处理器详情...")
        processor = await processor_repository.get_processor_with_details(processor_id)
        logger.info(f"查询结果: {processor}")
        
        if not processor:
            logger.warning(f"处理器不存在: {processor_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="处理器不存在"
            )
        
        logger.info(f"找到处理器: {processor.get('name', '')}")
        
        # 检查删除权限：只有创建者可以删除processor（历史数据允许删除）
        processor_created_by = processor.get('created_by')
        
        # 如果有创建者信息，检查是否为创建者
        if processor_created_by is not None and str(processor_created_by) != str(current_user.user_id):
            logger.warning(f"权限不足: 用户 {current_user.user_id} 尝试删除非自己创建的处理器 {processor_id}")
            logger.warning(f"处理器创建者: {processor_created_by}, 当前用户: {current_user.user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足：只有处理器的创建者可以删除该处理器"
            )
        
        # 历史数据处理器（created_by为空）允许任何用户删除
        if processor_created_by is None:
            logger.info(f"允许删除历史数据处理器: {processor_id} (无创建者信息)")
        
        # 1. 先清空所有工作流节点中对该处理器的引用
        logger.info(f"步骤1: 清空工作流节点中的处理器引用")
        clear_result = await cascade_deletion_service.clear_processor_references(processor_id)
        logger.info(f"清空结果: 影响了 {clear_result['cleared_records']} 个关联记录，{len(clear_result['affected_workflows'])} 个工作流")
        
        # 检查处理器是否正在被使用（可以添加额外的检查逻辑）
        # 例如检查是否有正在进行的任务使用此处理器
        
        # 执行软删除
        logger.info(f"开始执行软删除...")
        success = await processor_repository.delete_processor(processor_id, soft_delete=True)
        logger.info(f"删除操作结果: {success}")
        
        if not success:
            logger.error(f"删除处理器操作失败: {processor_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除处理器失败"
            )
        
        logger.info(f"处理器删除成功: {processor_id}")
        
        return BaseResponse(
            success=True,
            message="处理器删除成功",
            data={
                "processor_id": str(processor_id),
                "processor_name": processor.get('name', ''),
                "deleted_by": str(current_user.user_id),
                "cascade_clear_result": {
                    "cleared_records": clear_result['cleared_records'],
                    "affected_workflows": clear_result['affected_workflows']
                }
            }
        )
        
    except HTTPException as he:
        logger.error(f"HTTP异常: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"删除处理器异常: {e}")
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除处理器失败，请稍后再试"
        )


@router.put("/{processor_id}", response_model=BaseResponse)
async def update_processor(
    processor_id: uuid.UUID = Path(..., description="处理器ID"),
    processor_data: ProcessorUpdate = ...,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    更新处理器
    
    Args:
        processor_id: 处理器ID
        processor_data: 处理器更新数据
        current_user: 当前用户
        
    Returns:
        更新结果
    """
    try:
        logger.info(f"Processor更新请求: processor_id={processor_id}, user_id={current_user.user_id}")
        
        # 首先检查处理器是否存在
        processor = await processor_repository.get_processor_with_details(processor_id)
        if not processor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="处理器不存在"
            )
        
        # 检查权限：只有创建者可以编辑
        processor_created_by = processor.get('created_by')
        if processor_created_by is not None and str(processor_created_by) != str(current_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足：只有处理器的创建者可以编辑该处理器"
            )
        
        # 历史数据（created_by为空）允许任何用户编辑
        if processor_created_by is None:
            logger.info(f"允许编辑历史数据处理器: {processor_id} (无创建者信息)")
        
        # 更新处理器
        updated_processor = await processor_repository.update_processor(processor_id, processor_data)
        
        if not updated_processor:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新处理器失败"
            )
        
        # 获取更新后的详细信息
        updated_details = await processor_repository.get_processor_with_details(processor_id)
        
        return BaseResponse(
            success=True,
            message="处理器更新成功",
            data={
                "processor": {
                    "processor_id": str(updated_details['processor_id']),
                    "name": updated_details['name'],
                    "type": updated_details['type'],
                    "version": updated_details['version'],
                    "created_at": updated_details['created_at'].isoformat() if updated_details['created_at'] else None,
                    "user_id": str(updated_details['user_id']) if updated_details['user_id'] else None,
                    "agent_id": str(updated_details['agent_id']) if updated_details['agent_id'] else None,
                    "username": updated_details.get('username'),
                    "user_email": updated_details.get('user_email'),
                    "agent_name": updated_details.get('agent_name'),
                    "agent_description": updated_details.get('agent_description'),
                    "creator_name": updated_details.get('creator_name')
                },
                "updated_by": str(current_user.user_id)
            }
        )
        
    except ValidationError as e:
        logger.warning(f"处理器更新验证失败: {e}")
        raise handle_validation_error(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新处理器异常: {e}")
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新处理器失败，请稍后再试"
        )


@router.put("/agents/{agent_id}", response_model=BaseResponse)
async def update_agent(
    agent_id: uuid.UUID = Path(..., description="Agent ID"),
    agent_update: AgentUpdate = ...,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    更新Agent信息
    
    Args:
        agent_id: Agent ID
        agent_update: Agent更新数据
        current_user: 当前用户
        
    Returns:
        更新结果
    """
    try:
        logger.info(f"Agent更新请求: agent_id={agent_id}, user_id={current_user.user_id}")
        logger.info(f"Agent更新数据: {agent_update.model_dump(exclude_unset=True)}")
        
        # 更新Agent信息
        updated_agent = await agent_repository.update_agent(agent_id, agent_update)
        
        if not updated_agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent不存在"
            )
        
        return BaseResponse(
            success=True,
            message="Agent更新成功",
            data={
                "agent": updated_agent,
                "updated_by": str(current_user.user_id)
            }
        )
        
    except ValidationError as e:
        logger.warning(f"Agent更新验证失败: {e}")
        raise handle_validation_error(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent更新异常: {e}")
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent更新失败，请稍后再试"
        )


@router.delete("/agents/{agent_id}", response_model=BaseResponse)
async def delete_agent(
    agent_id: uuid.UUID = Path(..., description="Agent ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除Agent
    
    Args:
        agent_id: Agent ID
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        logger.info(f"DELETE Agent请求进入 - agent_id={agent_id}, user_id={current_user.user_id}")
        logger.info(f"Agent ID类型: {type(agent_id)}, 值: {agent_id}")
        
        # 首先检查Agent是否存在
        logger.info(f"开始查询Agent详情...")
        agent = await agent_repository.get_agent_by_id(agent_id)
        logger.info(f"查询结果: {agent}")
        
        if not agent:
            logger.warning(f"Agent不存在: {agent_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent不存在"
            )
        
        logger.info(f"找到Agent: {agent.get('agent_name', '')}")
        
        # 检查Agent是否正在被使用（可以添加额外的检查逻辑）
        # 例如检查是否有正在进行的任务使用此Agent
        
        # 执行软删除
        logger.info(f"开始执行Agent软删除...")
        success = await agent_repository.delete_agent(agent_id, soft_delete=True)
        logger.info(f"Agent删除操作结果: {success}")
        
        if not success:
            logger.error(f"删除Agent操作失败: {agent_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除Agent失败"
            )
        
        logger.info(f"Agent删除成功: {agent_id}")
        
        return BaseResponse(
            success=True,
            message="Agent删除成功",
            data={
                "agent_id": str(agent_id),
                "agent_name": agent.get('agent_name', ''),
                "deleted_by": str(current_user.user_id)
            }
        )
        
    except HTTPException as he:
        logger.error(f"HTTP异常: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"删除Agent异常: {e}")
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除Agent失败，请稍后再试"
        )


@router.post("/agents", response_model=BaseResponse)
async def create_agent(
    agent_data: AgentCreate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    创建新的Agent
    
    Args:
        agent_data: Agent创建数据
        current_user: 当前用户
        
    Returns:
        创建的Agent信息
    """
    try:
        logger.info(f"POST Agent创建请求进入 - user_id={current_user.user_id}")
        logger.info(f"Agent创建数据: {agent_data}")
        
        # 创建Agent
        new_agent = await agent_repository.create_agent(agent_data)
        
        if not new_agent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建Agent失败"
            )
        
        logger.info(f"Agent创建成功: {new_agent.get('agent_id')}")
        
        return BaseResponse(
            success=True,
            message="Agent创建成功",
            data={
                "agent": {
                    "agent_id": str(new_agent['agent_id']),
                    "agent_name": new_agent['agent_name'],
                    "description": new_agent['description'],
                    "base_url": new_agent['base_url'],
                    "api_key": new_agent['api_key'],
                    "model_name": new_agent['model_name'],
                    "tool_config": new_agent['tool_config'],
                    "parameters": new_agent['parameters'],
                    "is_autonomous": new_agent['is_autonomous'],
                    "tags": new_agent.get('tags', []),
                    "created_at": new_agent['created_at'].isoformat() if new_agent['created_at'] else None,
                },
                "created_by": str(current_user.user_id)
            }
        )
        
    except ValueError as ve:
        logger.warning(f"Agent创建验证失败: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建Agent异常: {e}")
        import traceback
        logger.error(f"异常详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建Agent失败，请稍后再试"
        )