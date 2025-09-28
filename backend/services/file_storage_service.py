"""
文件存储服务
File Storage Service
"""

import os
import uuid
import hashlib
import aiofiles
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException
from loguru import logger

from ..config.settings import get_settings
from ..utils.helpers import now_utc


class FileStorageService:
    """文件存储服务 - Linus式简洁设计"""
    
    def __init__(self):
        self.settings = get_settings()
        self.upload_root = Path(self.settings.upload_root_dir if hasattr(self.settings, 'upload_root_dir') else "./uploads")
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.allowed_content_types = {
            # 文档类型
            "application/pdf",
            "application/msword", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            # 文本类型
            "text/plain",
            "text/csv",
            "text/html",
            "text/markdown",
            "application/json",
            "application/xml",
            # 图片类型
            "image/jpeg",
            "image/png", 
            "image/gif",
            "image/webp",
            "image/svg+xml",
            # 压缩文件
            "application/zip",
            "application/x-rar-compressed",
            "application/x-7z-compressed",
            # 其他
            "application/octet-stream"
        }
    
    def _ensure_upload_directory(self) -> Path:
        """确保上传目录存在"""
        now = datetime.now()
        date_path = self.upload_root / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
        date_path.mkdir(parents=True, exist_ok=True)
        return date_path
    
    def _validate_file(self, file: UploadFile) -> None:
        """验证文件 - Linus原则：简单直接的验证"""
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        
        if file.size and file.size > self.max_file_size:
            raise HTTPException(
                status_code=413, 
                detail=f"文件大小超过限制 ({self.max_file_size / 1024 / 1024:.1f}MB)"
            )
        
        # 基于文件名推断MIME类型
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0]
        if not content_type:
            content_type = "application/octet-stream"
            
        if content_type not in self.allowed_content_types:
            raise HTTPException(
                status_code=415,
                detail=f"不支持的文件类型: {content_type}"
            )
    
    def _generate_unique_filename(self, original_filename: str) -> str:
        """生成唯一文件名 - 避免冲突"""
        file_ext = Path(original_filename).suffix
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{file_ext}"
    
    async def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件SHA256哈希 - 用于去重"""
        hash_sha256 = hashlib.sha256()
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    async def save_uploaded_file(self, file: UploadFile, uploaded_by: uuid.UUID) -> Dict[str, Any]:
        """
        保存上传的文件 - 核心方法
        
        Returns:
            包含文件信息的字典
        """
        try:
            # 验证文件
            self._validate_file(file)
            
            # 准备存储路径
            upload_dir = self._ensure_upload_directory()
            unique_filename = self._generate_unique_filename(file.filename)
            file_path = upload_dir / unique_filename
            
            # 获取文件内容类型
            content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
            
            # 保存文件
            file_size = 0
            async with aiofiles.open(file_path, 'wb') as dest_file:
                while chunk := await file.read(8192):
                    await dest_file.write(chunk)
                    file_size += len(chunk)
            
            # 计算文件哈希
            file_hash = await self._calculate_file_hash(file_path)
            
            # 返回文件信息
            file_info = {
                'filename': unique_filename,
                'original_filename': file.filename,
                'file_path': str(file_path),
                'file_size': file_size,
                'content_type': content_type,
                'file_hash': file_hash,
                'uploaded_by': uploaded_by
            }
            
            logger.info(f"文件上传成功: {file.filename} -> {unique_filename} ({file_size} bytes)")
            return file_info
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"文件上传失败: {e}")
            # 清理可能已创建的文件
            if 'file_path' in locals() and file_path.exists():
                try:
                    file_path.unlink()
                except:
                    pass
            raise HTTPException(status_code=500, detail="文件上传失败")
    
    async def get_file_path(self, file_path_str: str) -> Path:
        """获取文件路径对象"""
        file_path = Path(file_path_str)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        return file_path
    
    async def delete_file(self, file_path_str: str) -> bool:
        """删除文件"""
        try:
            file_path = Path(file_path_str)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"文件删除成功: {file_path}")
                return True
            else:
                logger.warning(f"尝试删除不存在的文件: {file_path}")
                return False
        except Exception as e:
            logger.error(f"文件删除失败: {file_path_str}, 错误: {e}")
            return False
    
    def get_file_info(self, file_path_str: str) -> Optional[Dict[str, Any]]:
        """获取文件基础信息"""
        try:
            file_path = Path(file_path_str)
            if not file_path.exists():
                return None
                
            stat = file_path.stat()
            return {
                'file_size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'content_type': mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
            }
        except Exception as e:
            logger.error(f"获取文件信息失败: {file_path_str}, 错误: {e}")
            return None
    
    async def check_file_exists_by_hash(self, file_hash: str) -> Optional[str]:
        """通过哈希值检查文件是否已存在 - 去重功能"""
        # 这里应该查询数据库中是否已有相同哈希的文件
        # 当前简化实现，返回None表示未找到重复文件
        return None
    
    def generate_download_url(self, file_id: uuid.UUID) -> str:
        """生成文件下载URL"""
        return f"/api/files/{file_id}/download"
    
    def get_upload_statistics(self) -> Dict[str, Any]:
        """获取上传统计信息"""
        try:
            total_files = 0
            total_size = 0
            
            # 遍历上传目录计算统计信息
            if self.upload_root.exists():
                for file_path in self.upload_root.rglob("*"):
                    if file_path.is_file():
                        total_files += 1
                        total_size += file_path.stat().st_size
            
            return {
                'total_files': total_files,
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'upload_root': str(self.upload_root)
            }
        except Exception as e:
            logger.error(f"获取上传统计失败: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'total_size_mb': 0.0,
                'upload_root': str(self.upload_root)
            }
    
    async def cleanup_orphaned_files(self, existing_file_paths: List[str]) -> Dict[str, int]:
        """清理孤儿文件 - 数据库中不存在记录的文件"""
        try:
            existing_paths_set = set(existing_file_paths)
            deleted_count = 0
            scanned_count = 0
            
            if self.upload_root.exists():
                for file_path in self.upload_root.rglob("*"):
                    if file_path.is_file():
                        scanned_count += 1
                        if str(file_path) not in existing_paths_set:
                            try:
                                file_path.unlink()
                                deleted_count += 1
                                logger.info(f"清理孤儿文件: {file_path}")
                            except Exception as e:
                                logger.error(f"清理孤儿文件失败: {file_path}, 错误: {e}")
            
            return {
                'scanned_count': scanned_count,
                'deleted_count': deleted_count
            }
        except Exception as e:
            logger.error(f"清理孤儿文件操作失败: {e}")
            return {'scanned_count': 0, 'deleted_count': 0}


# 全局文件存储服务实例 - Linus原则：简单直接
_file_storage_service: Optional[FileStorageService] = None

def get_file_storage_service() -> FileStorageService:
    """获取文件存储服务实例"""
    global _file_storage_service
    if _file_storage_service is None:
        _file_storage_service = FileStorageService()
    return _file_storage_service