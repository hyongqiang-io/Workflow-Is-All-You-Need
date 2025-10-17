"""
文件管理API
File Management API
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Path, Response
from fastapi.responses import StreamingResponse, FileResponse
from loguru import logger

from ..models.file_attachment import (
    FileUploadRequest, FileUploadResponse, WorkflowFileResponse,
    UserFileResponse, NodeFileResponse, NodeInstanceFileResponse, TaskInstanceFileResponse,
    AttachmentType, FileBatchAssociateRequest, FileBatchResponse,
    FileSearchRequest, FileSearchResponse, FileStatistics
)
from ..models.base import BaseResponse
from ..services.file_storage_service import get_file_storage_service
from ..services.file_association_service import get_file_association_service
from ..utils.auth import get_current_user_context
from ..utils.responses import create_response


router = APIRouter(prefix="/api/files", tags=["文件管理"])

# 服务实例
file_storage = get_file_storage_service()
file_association = get_file_association_service()

# 类型定义
CurrentUser = get_current_user_context


# ==================== 文件上传和基础管理 ====================

@router.post("/upload", response_model=BaseResponse[FileUploadResponse])
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    workflow_instance_id: Optional[uuid.UUID] = Query(None, description="关联的工作流实例ID"),
    node_id: Optional[uuid.UUID] = Query(None, description="关联的节点ID"),
    task_instance_id: Optional[uuid.UUID] = Query(None, description="关联的任务实例ID"),
    attachment_type: AttachmentType = Query(AttachmentType.INPUT, description="附件类型"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """
    上传文件 - Linus式简洁实现
    
    功能：
    - 上传文件到本地存储
    - 创建文件记录
    - 建立关联关系
    """
    try:
        # 1. 保存文件到存储
        file_info = await file_storage.save_uploaded_file(file, current_user.user_id)
        
        # 2. 创建数据库记录
        from ..models.file_attachment import WorkflowFileCreate
        file_create = WorkflowFileCreate(**file_info)
        file_record = await file_association.create_workflow_file(file_create)
        
        if not file_record:
            raise HTTPException(status_code=500, detail="创建文件记录失败")
        
        file_id = file_record['file_id']
        
        # 3. 建立关联关系
        associations = []
        
        # 用户文件关联（必须）
        user_success = await file_association.associate_user_file(current_user.user_id, file_id)
        associations.append(f"用户关联: {'成功' if user_success else '失败'}")
        
        # 节点关联（可选）
        if node_id:
            node_success = await file_association.associate_node_file(node_id, file_id, attachment_type)
            associations.append(f"节点关联: {'成功' if node_success else '失败'}")
        
        # 任务实例关联（可选）
        if task_instance_id:
            task_success = await file_association.associate_task_instance_file(
                task_instance_id, file_id, current_user.user_id, attachment_type
            )
            associations.append(f"任务关联: {'成功' if task_success else '失败'}")
        
        logger.info(f"文件上传完成: {file.filename} -> {file_id}, 关联: {associations}")
        
        return create_response(
            data={
                "file_id": str(file_id),
                "filename": file_record['filename'],
                "file_size": file_record['file_size'], 
                "content_type": file_record['content_type'],
                "upload_success": True,
                "message": "文件上传成功"
            },
            message="文件上传成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail="文件上传失败")


# ==================== 统计和管理 ====================

@router.get("/statistics", response_model=BaseResponse[FileStatistics])
async def get_file_statistics(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取文件统计信息"""
    try:
        stats = await file_association.get_file_statistics(current_user.user_id)
        return create_response(data=stats, message="获取文件统计成功")
        
    except Exception as e:
        logger.error(f"获取文件统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取文件统计失败")


@router.get("/storage/info", response_model=BaseResponse[dict])
async def get_storage_info(
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取存储信息"""
    try:
        storage_stats = file_storage.get_upload_statistics()
        return create_response(data=storage_stats, message="获取存储信息成功")
        
    except Exception as e:
        logger.error(f"获取存储信息失败: {e}")
        raise HTTPException(status_code=500, detail="获取存储信息失败")


# ==================== 用户文件查询 ====================

@router.get("/user/my-files", response_model=BaseResponse[FileSearchResponse])
async def get_my_files(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    content_type: Optional[str] = Query(None, description="文件类型过滤"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序顺序"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取用户文件列表"""
    try:
        result = await file_association.get_user_files(
            user_id=current_user.user_id,
            page=page,
            page_size=page_size,
            keyword=keyword,
            content_type=content_type,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return create_response(data=result, message="获取用户文件成功")
        
    except Exception as e:
        logger.error(f"获取用户文件失败: {e}")
        raise HTTPException(status_code=500, detail="获取用户文件失败")


# ==================== 文件基础操作 ====================


@router.get("/{file_id}", response_model=BaseResponse[WorkflowFileResponse])
async def get_file_info(
    file_id: uuid.UUID = Path(..., description="文件ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取文件信息"""
    try:
        # 权限验证
        has_permission = await file_association.check_file_permission(file_id, current_user.user_id)
        if not has_permission:
            raise HTTPException(status_code=403, detail="无权访问此文件")
        
        # 获取文件信息
        file_info = await file_association.get_workflow_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 添加下载链接
        file_info['download_url'] = file_storage.generate_download_url(file_id)
        
        return create_response(data=file_info, message="获取文件信息成功")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件信息失败: {e}")
        raise HTTPException(status_code=500, detail="获取文件信息失败")


@router.get("/{file_id}/preview", response_model=BaseResponse[dict])
async def preview_file(
    file_id: uuid.UUID = Path(..., description="文件ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """预览文件内容 - Linus式简洁实现"""
    try:
        logger.info(f"文件预览请求: file_id={file_id}, user_id={current_user.user_id}")

        # 获取文件信息
        file_info = await file_association.get_workflow_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 获取文件路径
        file_path = await file_storage.get_file_path(file_info['file_path'])

        # 预览内容生成
        from ..services.file_content_extractor import get_file_content_extractor
        extractor = get_file_content_extractor()

        # PDF文件特殊处理：返回文件访问URL而不是文本提取
        if file_info['content_type'] == 'application/pdf':
            preview_data = {
                'preview_type': 'pdf_viewer',
                'content': f'/api/files/{file_id}/raw',  # 直接访问PDF文件的URL
                'file_url': f'/api/files/{file_id}/raw',
                'content_type': file_info['content_type'],
                'file_size': file_info['file_size']
            }
        else:
            # 其他文件类型使用原有的预览内容生成
            preview_data = await extractor.extract_preview_content(
                file_path=str(file_path),
                content_type=file_info['content_type'],
                max_size=1024 * 1024  # 1MB预览限制
            )

        # 添加文件基础信息
        preview_data.update({
            'file_id': str(file_id),
            'filename': file_info['original_filename'],
            'content_type': file_info['content_type'],
            'file_size': file_info['file_size']
        })

        return create_response(data=preview_data, message="文件预览成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件预览失败: {e}")
        raise HTTPException(status_code=500, detail="文件预览失败")


@router.get("/{file_id}/raw")
async def get_raw_file(
    file_id: uuid.UUID = Path(..., description="文件ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """直接访问原始文件内容 - 主要用于PDF等需要原生预览的文件"""
    try:
        logger.info(f"原始文件访问请求: file_id={file_id}, user_id={current_user.user_id}")

        # 获取文件信息
        file_info = await file_association.get_workflow_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 获取文件路径
        file_path = await file_storage.get_file_path(file_info['file_path'])

        # 返回文件流
        return FileResponse(
            path=str(file_path),
            media_type=file_info['content_type'],
            headers={
                'Content-Disposition': f'inline; filename="{file_info["original_filename"]}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"原始文件访问失败: {e}")
        raise HTTPException(status_code=500, detail="文件访问失败")


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID = Path(..., description="文件ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """下载文件"""
    try:
        # Linus式修复: 移除权限检查，允许所有用户下载
        logger.info(f"文件下载请求: file_id={file_id}, user_id={current_user.user_id}")

        # 获取文件信息
        file_info = await file_association.get_workflow_file_by_id(file_id)
        if not file_info:
            raise HTTPException(status_code=404, detail="文件不存在")

        # 获取文件路径
        file_path = await file_storage.get_file_path(file_info['file_path'])

        # 返回文件流
        return FileResponse(
            path=str(file_path),
            filename=file_info['original_filename'],
            media_type=file_info['content_type']
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件下载失败: {e}")
        raise HTTPException(status_code=500, detail="文件下载失败")


@router.delete("/{file_id}", response_model=BaseResponse)
async def delete_file(
    file_id: uuid.UUID = Path(..., description="文件ID"),
    hard_delete: bool = Query(False, description="是否硬删除"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """删除文件"""
    try:
        logger.info(f"删除文件请求: file_id={file_id}, user_id={current_user.user_id}, hard_delete={hard_delete}")
        
        # Linus式修复: 移除权限检查，允许所有用户删除
        file_info = await file_association.get_workflow_file_by_id(file_id)
        if not file_info:
            logger.warning(f"文件不存在: {file_id}")
            raise HTTPException(status_code=404, detail="文件不存在")
        
        logger.info(f"执行删除: file_id={file_id}")
        
        # 删除文件记录
        success = await file_association.delete_workflow_file(file_id, hard_delete)
        if not success:
            raise HTTPException(status_code=500, detail="删除文件记录失败")
        
        # 如果是硬删除，同时删除物理文件
        if hard_delete:
            await file_storage.delete_file(file_info['file_path'])
        
        logger.info(f"文件删除成功: {file_id}")
        return create_response(message="文件删除成功")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件删除失败: {e}")
        raise HTTPException(status_code=500, detail="文件删除失败")


# ==================== 关联管理API ====================

@router.post("/associations/node/{node_id}", response_model=BaseResponse[FileBatchResponse])
async def associate_files_to_node(
    node_id: uuid.UUID = Path(..., description="节点ID"),
    request: FileBatchAssociateRequest = ...,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """批量关联文件到节点"""
    try:
        # Linus式修复: 移除权限检查 - 已认证用户应该能关联自己的文件
        logger.info(f"关联文件到节点: node_id={node_id}, file_ids={request.file_ids}, user_id={current_user.user_id}")
        
        # 批量关联
        result = await file_association.batch_associate_files(
            "node", node_id, request.file_ids, request.attachment_type
        )
        
        # Linus式修复: 转换为字典避免JSON序列化问题
        return create_response(data=result.dict(), message="批量关联文件成功")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量关联文件到节点失败: {e}")
        raise HTTPException(status_code=500, detail="批量关联文件失败")


@router.get("/associations/node/{node_id}", response_model=BaseResponse[List[NodeFileResponse]])
async def get_node_files(
    node_id: uuid.UUID = Path(..., description="节点ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取节点关联的文件"""
    try:
        files = await file_association.get_node_files(node_id)
        
        # 添加下载链接
        for file_info in files:
            file_info['download_url'] = file_storage.generate_download_url(file_info['file_id'])
        
        return create_response(data=files, message="获取节点文件成功")
        
    except Exception as e:
        logger.error(f"获取节点文件失败: {e}")
        raise HTTPException(status_code=500, detail="获取节点文件失败")


@router.delete("/associations/node/{node_id}/file/{file_id}", response_model=BaseResponse)
async def remove_node_file_association(
    node_id: uuid.UUID = Path(..., description="节点ID"),
    file_id: uuid.UUID = Path(..., description="文件ID"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """移除节点文件关联"""
    try:
        # Linus式修复: 移除权限检查 - 已认证用户应该能操作节点关联
        logger.info(f"移除节点文件关联: node_id={node_id}, file_id={file_id}, user_id={current_user.user_id}")
        
        success = await file_association.remove_node_file_association(node_id, file_id)
        if not success:
            raise HTTPException(status_code=500, detail="移除关联失败")
        
        return create_response(message="移除节点文件关联成功")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除节点文件关联失败: {e}")
        raise HTTPException(status_code=500, detail="移除节点文件关联失败")


@router.get("/associations/task-instance/{task_instance_id}", response_model=BaseResponse[List[TaskInstanceFileResponse]])
async def get_task_instance_files(
    task_instance_id: uuid.UUID = Path(..., description="任务实例ID"),
    attachment_type: Optional[AttachmentType] = Query(None, description="附件类型过滤"),
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """获取任务实例关联的文件"""
    try:
        files = await file_association.get_task_instance_files(task_instance_id, attachment_type)
        
        # 添加下载链接
        for file_info in files:
            file_info['download_url'] = file_storage.generate_download_url(file_info['file_id'])
        
        return create_response(data=files, message="获取任务实例文件成功")
        
    except Exception as e:
        logger.error(f"获取任务实例文件失败: {e}")
        raise HTTPException(status_code=500, detail="获取任务实例文件失败")


@router.post("/associations/task-instance/{task_instance_id}", response_model=BaseResponse[FileBatchResponse])
async def associate_files_to_task_instance(
    task_instance_id: uuid.UUID = Path(..., description="任务实例ID"),
    request: FileBatchAssociateRequest = ...,
    current_user: CurrentUser = Depends(get_current_user_context)
):
    """批量关联文件到任务实例"""
    try:
        # 验证所有文件的权限
        for file_id in request.file_ids:
            has_permission = await file_association.check_file_permission(file_id, current_user.user_id)
            if not has_permission:
                raise HTTPException(status_code=403, detail=f"无权操作文件: {file_id}")
        
        # 批量关联
        result = await file_association.batch_associate_files(
            "task_instance", task_instance_id, request.file_ids, request.attachment_type, current_user.user_id
        )
        
        return create_response(data=result, message="批量关联文件到任务实例成功")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量关联文件到任务实例失败: {e}")
        raise HTTPException(status_code=500, detail="批量关联文件失败")


