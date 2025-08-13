"""
工作流管理API路由
Workflow Management API Routes
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, UploadFile, File
from fastapi.responses import JSONResponse
from loguru import logger
import json

from ..models.base import BaseResponse
from ..models.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from ..models.workflow_import_export import WorkflowImport, ImportPreview, ImportResult
from ..services.workflow_service import WorkflowService
from ..services.workflow_import_export_service import WorkflowImportExportService
from ..services.cascade_deletion_service import cascade_deletion_service
from ..utils.middleware import get_current_active_user, CurrentUser, get_current_user_context
from ..utils.exceptions import (
    ValidationError, ConflictError, handle_validation_error, handle_conflict_error
)

# 创建路由器
router = APIRouter(prefix="/workflows", tags=["工作流管理"])

# 工作流服务实例
workflow_service = WorkflowService()

# 导入导出服务实例
import_export_service = WorkflowImportExportService()


@router.post("", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: dict = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    创建新工作流
    
    Args:
        workflow_data: 工作流创建数据
        current_user: 当前用户
        
    Returns:
        创建的工作流信息
    """
    try:
        if not workflow_data:
            raise ValidationError("请提供工作流数据")
        
        # 设置创建者ID
        workflow_data["creator_id"] = current_user.user_id
        
        # 创建WorkflowCreate对象
        workflow_create = WorkflowCreate(**workflow_data)
        
        # 创建工作流
        workflow_response = await workflow_service.create_workflow(workflow_create)
        
        logger.info(f"用户 {current_user.username} 创建了工作流: {workflow_data.get('name', '')}")
        
        return BaseResponse(
            success=True,
            message="工作流创建成功",
            data={
                "workflow": workflow_response.model_dump(),
                "message": "工作流已创建，可以开始添加节点"
            }
        )
        
    except ValidationError as e:
        logger.warning(f"工作流创建输入验证失败: {e}")
        raise handle_validation_error(e)
    except ConflictError as e:
        logger.warning(f"工作流创建冲突: {e}")
        raise handle_conflict_error(e)
    except Exception as e:
        logger.error(f"创建工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建工作流失败，请稍后再试"
        )


@router.get("", response_model=BaseResponse)
async def get_user_workflows(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取当前用户的工作流列表
    
    Args:
        current_user: 当前用户
        
    Returns:
        用户的工作流列表
    """
    try:
        workflows = await workflow_service.get_user_workflows(current_user.user_id)
        
        return BaseResponse(
            success=True,
            message="获取工作流列表成功",
            data={
                "workflows": [workflow.model_dump() for workflow in workflows],
                "count": len(workflows)
            }
        )
        
    except Exception as e:
        logger.error(f"获取用户工作流列表异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取工作流列表失败"
        )


# =============================================================================
# 工作流导入导出API（必须在 /{workflow_base_id} 路由之前）
# =============================================================================

@router.get("/{workflow_base_id}/export", response_model=BaseResponse)
async def export_workflow(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    导出工作流为JSON格式（去除processor分配信息）
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        工作流JSON数据
    """
    try:
        logger.info(f"用户 {current_user.username} 开始导出工作流: {workflow_base_id}")
        
        # 导出工作流
        export_data = await import_export_service.export_workflow(workflow_base_id, current_user.user_id)
        
        # 生成文件名
        filename = import_export_service.generate_workflow_filename(export_data.name)
        
        logger.info(f"工作流导出成功: {export_data.name}")
        
        return BaseResponse(
            success=True,
            message="工作流导出成功",
            data={
                "export_data": export_data.model_dump(),
                "filename": filename,
                "export_info": {
                    "workflow_name": export_data.name,
                    "nodes_count": len(export_data.nodes),
                    "connections_count": len(export_data.connections),
                    "export_timestamp": export_data.export_timestamp
                }
            }
        )
        
    except ValidationError as e:
        logger.warning(f"导出工作流验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"导出工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导出工作流失败，请稍后再试"
        )


@router.get("/{workflow_base_id}", response_model=BaseResponse)
async def get_workflow(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流详细信息
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        工作流详细信息
    """
    try:
        workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        # 检查访问权限（暂时只允许创建者访问）
        if workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流"
            )
        
        return BaseResponse(
            success=True,
            message="获取工作流信息成功",
            data={"workflow": workflow.model_dump()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流详细信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取工作流信息失败"
        )


@router.put("/{workflow_base_id}", response_model=BaseResponse)
async def update_workflow(
    workflow_base_id: uuid.UUID,
    workflow_data: WorkflowUpdate,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    更新工作流信息
    
    Args:
        workflow_base_id: 工作流基础ID
        workflow_data: 更新数据
        current_user: 当前用户
        
    Returns:
        更新后的工作流信息
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权修改此工作流"
            )
        
        # 更新工作流
        updated_workflow = await workflow_service.update_workflow(
            workflow_base_id, workflow_data, current_user.user_id
        )
        
        logger.info(f"用户 {current_user.username} 更新了工作流: {workflow_base_id}")
        
        return BaseResponse(
            success=True,
            message="工作流更新成功",
            data={"workflow": updated_workflow.model_dump()}
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.warning(f"工作流更新输入验证失败: {e}")
        raise handle_validation_error(e)
    except ConflictError as e:
        logger.warning(f"工作流更新冲突: {e}")
        raise handle_conflict_error(e)
    except Exception as e:
        logger.error(f"更新工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新工作流失败，请稍后再试"
        )


@router.delete("/{workflow_base_id}", response_model=BaseResponse)
async def delete_workflow(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    删除工作流
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        删除结果
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此工作流"
            )
        
        # 删除工作流
        success = await workflow_service.delete_workflow(workflow_base_id, current_user.user_id)
        
        if success:
            logger.info(f"用户 {current_user.username} 删除了工作流: {workflow_base_id}")
            return BaseResponse(
                success=True,
                message="工作流删除成功",
                data={"message": "工作流及其所有相关数据已删除"}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除工作流失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除工作流失败，请稍后再试"
        )


@router.delete("/{workflow_base_id}/cascade", response_model=BaseResponse)
async def delete_workflow_cascade(
    workflow_base_id: uuid.UUID,
    soft_delete: bool = Query(True, description="是否软删除"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    级联删除工作流及其所有相关数据
    
    Args:
        workflow_base_id: 工作流基础ID
        soft_delete: 是否软删除（默认True）
        current_user: 当前用户
        
    Returns:
        级联删除结果统计
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权删除此工作流"
            )
        
        # 执行级联删除
        deletion_result = await cascade_deletion_service.delete_workflow_base_cascade(
            workflow_base_id, soft_delete
        )
        
        if deletion_result['deleted_workflow_base']:
            logger.info(f"用户 {current_user.username} 级联删除了工作流: {workflow_base_id}")
            return BaseResponse(
                success=True,
                message="工作流级联删除成功",
                data={
                    "message": "工作流及其所有相关数据已删除",
                    "deletion_stats": deletion_result
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="级联删除工作流失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"级联删除工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="级联删除工作流失败，请稍后再试"
        )


@router.get("/{workflow_base_id}/deletion-preview", response_model=BaseResponse)
async def get_workflow_deletion_preview(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    预览工作流删除将影响的数据量
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        删除预览数据
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权查看此工作流"
            )
        
        # 获取删除预览
        preview = await cascade_deletion_service.get_deletion_preview(workflow_base_id)
        
        return BaseResponse(
            success=True,
            message="删除预览获取成功",
            data=preview
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取删除预览异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取删除预览失败，请稍后再试"
        )


@router.get("/{workflow_base_id}/versions", response_model=BaseResponse)
async def get_workflow_versions(
    workflow_base_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流版本历史
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        版本历史列表
    """
    try:
        # 检查工作流是否存在和权限
        existing_workflow = await workflow_service.get_workflow_by_base_id(workflow_base_id)
        if not existing_workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        
        if existing_workflow.creator_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流"
            )
        
        # 获取版本历史
        versions = await workflow_service.get_workflow_versions(workflow_base_id)
        
        return BaseResponse(
            success=True,
            message="获取版本历史成功",
            data={
                "versions": versions,
                "count": len(versions)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作流版本历史异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取版本历史失败"
        )


@router.get("/search/", response_model=BaseResponse)
async def search_workflows(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(50, ge=1, le=100, description="结果数量限制"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    搜索工作流
    
    Args:
        keyword: 搜索关键词
        limit: 结果数量限制
        current_user: 当前用户
        
    Returns:
        搜索结果
    """
    try:
        workflows = await workflow_service.search_workflows(keyword, limit)
        
        return BaseResponse(
            success=True,
            message="搜索完成",
            data={
                "workflows": [workflow.model_dump() for workflow in workflows],
                "count": len(workflows),
                "keyword": keyword
            }
        )
        
    except Exception as e:
        logger.error(f"搜索工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索失败，请稍后再试"
        )


@router.get("/stats/summary", response_model=BaseResponse)
async def get_workflow_stats(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流统计信息
    
    Args:
        current_user: 当前用户
        
    Returns:
        统计信息
    """
    try:
        stats = await workflow_service.get_workflow_stats()
        
        return BaseResponse(
            success=True,
            message="获取统计信息成功",
            data={"stats": stats}
        )
        
    except Exception as e:
        logger.error(f"获取工作流统计信息异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计信息失败"
        )


# 工作流节点相关端点
@router.get("/{workflow_base_id}/nodes", response_model=BaseResponse)
async def get_workflow_nodes(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    获取工作流的所有节点
    
    Args:
        workflow_base_id: 工作流基础ID
        current_user: 当前用户
        
    Returns:
        节点列表
    """
    try:
        from ..services.node_service import NodeService
        node_service = NodeService()
        nodes = await node_service.get_workflow_nodes(workflow_base_id, current_user.user_id)
        
        return BaseResponse(
            success=True,
            message="获取节点列表成功",
            data={
                "nodes": [node.model_dump() for node in nodes],
                "count": len(nodes),
                "workflow_id": str(workflow_base_id)
            }
        )
        
    except Exception as e:
        logger.error(f"获取工作流节点列表异常: {e}")
        if "无权访问" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此工作流的节点"
            )
        elif "不存在" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="工作流不存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="获取节点列表失败"
            )


@router.post("/{workflow_base_id}/nodes", response_model=BaseResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_node(
    workflow_base_id: uuid.UUID = Path(..., description="工作流基础ID"),
    node_data: dict = None,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    为工作流创建新节点
    
    Args:
        workflow_base_id: 工作流基础ID
        node_data: 节点创建数据
        current_user: 当前用户
        
    Returns:
        创建的节点信息
    """
    try:
        from ..services.node_service import NodeService
        from ..models.node import NodeCreate
        
        if not node_data:
            raise ValidationError("请提供节点数据")
        
        # 设置工作流ID
        node_data["workflow_base_id"] = workflow_base_id
        node_data["creator_id"] = current_user.user_id
        
        # 创建NodeCreate对象
        node_create = NodeCreate(**node_data)
        
        node_service = NodeService()
        node_response = await node_service.create_node(node_create, current_user.user_id)
        
        logger.info(f"用户 {current_user.username} 为工作流 {workflow_base_id} 创建了节点: {node_data.get('name', '')}")
        
        return BaseResponse(
            success=True,
            message="节点创建成功",
            data={
                "node": node_response.model_dump(),
                "message": "节点已创建，可以继续添加处理器和连接"
            }
        )
        
    except ValidationError as e:
        logger.warning(f"节点创建输入验证失败: {e}")
        raise handle_validation_error(e)
    except Exception as e:
        logger.error(f"创建节点异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建节点失败，请稍后再试"
        )


@router.post("/import/preview", response_model=BaseResponse)
async def preview_workflow_import(
    import_data: WorkflowImport,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    预览工作流导入数据
    
    Args:
        import_data: 导入数据
        current_user: 当前用户
        
    Returns:
        导入预览信息
    """
    try:
        logger.info(f"用户 {current_user.username} 预览导入工作流: {import_data.name}")
        
        # 预览导入
        preview_data = await import_export_service.preview_import(import_data, current_user.user_id)
        
        return BaseResponse(
            success=True,
            message="预览成功",
            data={
                "preview": preview_data.model_dump(),
                "can_import": preview_data.validation_result["valid"] and len(preview_data.conflicts) == 0,
                "requires_confirmation": len(preview_data.conflicts) > 0
            }
        )
        
    except Exception as e:
        logger.error(f"预览导入异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="预览失败，请稍后再试"
        )


@router.post("/import", response_model=BaseResponse)
async def import_workflow(
    import_data: WorkflowImport,
    overwrite: bool = Query(False, description="是否覆盖同名工作流"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    导入工作流
    
    Args:
        import_data: 导入数据
        overwrite: 是否覆盖同名工作流
        current_user: 当前用户
        
    Returns:
        导入结果
    """
    try:
        logger.info(f"用户 {current_user.username} 开始导入工作流: {import_data.name}")
        
        # 导入工作流
        import_result = await import_export_service.import_workflow(
            import_data, current_user.user_id, overwrite
        )
        
        if import_result.success:
            logger.info(f"工作流导入成功: {import_data.name}")
            return BaseResponse(
                success=True,
                message=import_result.message,
                data={
                    "import_result": import_result.model_dump(),
                    "workflow_id": import_result.workflow_id
                }
            )
        else:
            logger.warning(f"工作流导入失败: {import_result.message}")
            return BaseResponse(
                success=False,
                message=import_result.message,
                data={
                    "import_result": import_result.model_dump()
                }
            )
        
    except Exception as e:
        logger.error(f"导入工作流异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导入工作流失败，请稍后再试"
        )


@router.post("/import/upload", response_model=BaseResponse)
async def upload_workflow_file(
    file: UploadFile = File(..., description="工作流JSON文件"),
    overwrite: bool = Query(False, description="是否覆盖同名工作流"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    通过文件上传导入工作流
    
    Args:
        file: JSON文件
        overwrite: 是否覆盖同名工作流
        current_user: 当前用户
        
    Returns:
        导入结果
    """
    try:
        # 验证文件类型
        if not file.filename.endswith('.json'):
            raise ValidationError("只支持JSON文件格式")
        
        # 读取文件内容
        content = await file.read()
        
        try:
            json_data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise ValidationError(f"JSON文件格式错误: {e}")
        except UnicodeDecodeError as e:
            raise ValidationError(f"文件编码错误: {e}")
        
        # 解析导入数据
        try:
            import_data = WorkflowImport(**json_data)
        except Exception as e:
            raise ValidationError(f"工作流数据格式错误: {e}")
        
        logger.info(f"用户 {current_user.username} 通过文件上传导入工作流: {import_data.name}")
        
        # 导入工作流
        import_result = await import_export_service.import_workflow(
            import_data, current_user.user_id, overwrite
        )
        
        if import_result.success:
            logger.info(f"文件上传导入成功: {import_data.name}")
            return BaseResponse(
                success=True,
                message=f"文件 '{file.filename}' 导入成功",
                data={
                    "import_result": import_result.model_dump(),
                    "workflow_id": import_result.workflow_id,
                    "filename": file.filename
                }
            )
        else:
            logger.warning(f"文件上传导入失败: {import_result.message}")
            return BaseResponse(
                success=False,
                message=import_result.message,
                data={
                    "import_result": import_result.model_dump(),
                    "filename": file.filename
                }
            )
        
    except ValidationError as e:
        logger.warning(f"文件上传导入验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"文件上传导入异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件导入失败，请稍后再试"
        )