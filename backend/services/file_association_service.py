"""
文件关联管理服务
File Association Management Service
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from ..repositories.base import BaseRepository
from ..utils.database import get_db_manager
from ..models.file_attachment import (
    WorkflowFile, WorkflowFileCreate, WorkflowFileResponse,
    UserFile, UserFileCreate, UserFileResponse,
    NodeFile, NodeFileCreate, NodeFileResponse,
    NodeInstanceFile, NodeInstanceFileCreate, NodeInstanceFileResponse,
    TaskInstanceFile, TaskInstanceFileCreate, TaskInstanceFileResponse,
    AttachmentType, AccessType, FileBatchResponse
)
from ..utils.helpers import now_utc


class FileAssociationService:
    """文件关联管理服务 - Linus式统一设计"""
    
    def __init__(self):
        self.db = get_db_manager()
    
    def _process_datetime_fields(self, records: List[Any]) -> List[Dict[str, Any]]:
        """处理数据库记录中的datetime字段 - Linus式统一处理"""
        processed_records = []
        for record in records:
            record_dict = dict(record)
            # 转换datetime字段为字符串
            for key, value in record_dict.items():
                if isinstance(value, datetime):
                    record_dict[key] = value.isoformat() if value else None
            processed_records.append(record_dict)
        return processed_records
    
    # ==================== 工作流文件核心管理 ====================
    
    async def create_workflow_file(self, file_data: WorkflowFileCreate) -> Optional[Dict[str, Any]]:
        """创建工作流文件记录"""
        try:
            # 生成UUID作为file_id
            file_id = str(uuid.uuid4())
            
            # MySQL兼容的INSERT语句
            insert_query = """
                INSERT INTO workflow_file (
                    file_id, filename, original_filename, file_path, file_size, 
                    content_type, file_hash, uploaded_by, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
            """
            
            # 执行插入
            await self.db.execute(insert_query, 
                file_id,
                file_data.filename,
                file_data.original_filename,
                file_data.file_path,
                file_data.file_size,
                file_data.content_type,
                file_data.file_hash,
                file_data.uploaded_by
            )
            
            # 查询刚插入的记录
            select_query = """
                SELECT file_id, filename, original_filename, file_path, file_size,
                       content_type, file_hash, uploaded_by, created_at, updated_at
                FROM workflow_file 
                WHERE file_id = $1
            """
            
            result = await self.db.fetch_one(select_query, file_id)
            
            if result:
                logger.info(f"创建工作流文件记录成功: {file_data.filename}")
                return dict(result)
            return None
            
        except Exception as e:
            logger.error(f"创建工作流文件记录失败: {e}")
            return None
    
    async def get_workflow_file_by_id(self, file_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取工作流文件"""
        try:
            query = """
                SELECT wf.*, u.username as uploaded_by_name
                FROM workflow_file wf
                LEFT JOIN user u ON wf.uploaded_by = u.user_id
                WHERE wf.file_id = $1 AND wf.is_deleted = FALSE
            """
            
            result = await self.db.fetch_one(query, file_id)
            if result:
                # 处理单个记录的datetime字段
                processed_result = self._process_datetime_fields([result])
                return processed_result[0] if processed_result else None
            return None
            
        except Exception as e:
            logger.error(f"获取工作流文件失败: {e}")
            return None
    
    async def get_workflow_file_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """根据哈希获取文件 - 用于去重"""
        try:
            query = """
                SELECT * FROM workflow_file 
                WHERE file_hash = $1 AND is_deleted = FALSE
                LIMIT 1
            """
            
            result = await self.db.fetch_one(query, file_hash)
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"根据哈希获取文件失败: {e}")
            return None
    
    async def delete_workflow_file(self, file_id: uuid.UUID, hard_delete: bool = False) -> bool:
        """删除工作流文件"""
        try:
            if hard_delete:
                # 硬删除 - 完全从数据库移除
                query = "DELETE FROM workflow_file WHERE file_id = $1"
            else:
                # 软删除 - 标记为已删除
                query = """
                    UPDATE workflow_file 
                    SET is_deleted = TRUE, updated_at = NOW()
                    WHERE file_id = $1
                """
            
            result = await self.db.execute(query, file_id)
            logger.info(f"删除工作流文件成功: {file_id} ({'硬删除' if hard_delete else '软删除'})")
            return True
            
        except Exception as e:
            logger.error(f"删除工作流文件失败: {e}")
            return False
    
    # ==================== 用户文件关联管理 ====================
    
    async def associate_user_file(self, user_id: uuid.UUID, file_id: uuid.UUID, 
                                 access_type: AccessType = AccessType.OWNER) -> bool:
        """关联用户和文件"""
        try:
            # 生成UUID作为user_file_id - Linus式修复: 数据结构要求啥就给啥
            user_file_id = str(uuid.uuid4())
            
            # MySQL兼容的UPSERT语法
            query = """
                INSERT INTO user_file (user_file_id, user_id, file_id, access_type)
                VALUES ($1, $2, $3, $4)
                ON DUPLICATE KEY UPDATE
                access_type = VALUES(access_type)
            """
            
            await self.db.execute(query, user_file_id, user_id, file_id, access_type.value)
            logger.info(f"用户文件关联成功: user={user_id}, file={file_id}")
            return True
            
        except Exception as e:
            logger.error(f"用户文件关联失败: {e}")
            return False
    
    async def get_user_files(self, user_id: uuid.UUID, page: int = 1, 
                           page_size: int = 20, keyword: Optional[str] = None,
                           content_type: Optional[str] = None, sort_by: str = "created_at",
                           sort_order: str = "desc") -> Dict[str, Any]:
        """获取用户的所有文件"""
        try:
            offset = (page - 1) * page_size
            
            # 构建WHERE条件
            where_conditions = ["uf.user_id = $1", "wf.is_deleted = FALSE"]
            params = [user_id]
            param_counter = 1
            
            # Linus式调试: 记录查询参数
            logger.info(f"get_user_files 查询参数: user_id={user_id}, page={page}, page_size={page_size}")
            
            # 关键词搜索
            if keyword:
                param_counter += 1
                where_conditions.append(f"(wf.filename LIKE ${param_counter} OR wf.original_filename LIKE ${param_counter})")
                params.append(f"%{keyword}%")
            
            # 内容类型过滤
            if content_type:
                param_counter += 1
                where_conditions.append(f"wf.content_type LIKE ${param_counter}")
                params.append(f"{content_type}%")
            
            # 构建ORDER BY
            valid_sort_fields = ["created_at", "filename", "file_size", "content_type"]
            sort_field = sort_by if sort_by in valid_sort_fields else "created_at"
            sort_direction = "DESC" if sort_order.upper() == "DESC" else "ASC"
            
            # 获取文件列表
            query = f"""
                SELECT uf.*, wf.*, u.username as uploaded_by_name
                FROM user_file uf
                JOIN workflow_file wf ON uf.file_id = wf.file_id
                LEFT JOIN user u ON wf.uploaded_by = u.user_id
                WHERE {" AND ".join(where_conditions)}
                ORDER BY wf.{sort_field} {sort_direction}
                LIMIT ${param_counter + 1} OFFSET ${param_counter + 2}
            """
            
            params.extend([page_size, offset])
            
            # Linus式调试: 记录完整查询
            logger.info(f"执行查询: {query}")
            logger.info(f"查询参数: {params}")
            
            files = await self.db.fetch_all(query, *params)
            
            # Linus式调试: 记录查询结果
            logger.info(f"查询到 {len(files)} 个文件")
            if files:
                for i, file in enumerate(files):
                    logger.info(f"文件 {i+1}: {dict(file)}")
            
            # 获取总数
            count_query = f"""
                SELECT COUNT(*) as total
                FROM user_file uf
                JOIN workflow_file wf ON uf.file_id = wf.file_id
                WHERE {" AND ".join(where_conditions)}
            """
            
            count_params = params[:-2]  # 移除LIMIT和OFFSET参数
            count_result = await self.db.fetch_one(count_query, *count_params)
            total = int(count_result['total']) if count_result else 0
            
            logger.info(f"文件总数: {total}")
            
            # 处理datetime序列化 - Linus式修复: 使用统一处理函数
            processed_files = self._process_datetime_fields(files)
            
            result = {
                'files': processed_files,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            }
            
            logger.info(f"返回结果: files={len(result['files'])}, total={result['total']}")
            return result
            
        except Exception as e:
            logger.error(f"获取用户文件失败: {e}")
            return {'files': [], 'total': 0, 'page': page, 'page_size': page_size, 'total_pages': 0}
    
    # ==================== 节点文件关联管理 ====================
    
    async def associate_node_file(self, node_id: uuid.UUID, file_id: uuid.UUID,
                                 attachment_type: AttachmentType = AttachmentType.INPUT) -> bool:
        """关联节点和文件"""
        try:
            # 生成UUID作为node_file_id - Linus式修复: 数据结构要求啥就给啥
            node_file_id = str(uuid.uuid4())
            
            # MySQL兼容的UPSERT语法
            query = """
                INSERT INTO node_file (node_file_id, node_id, file_id, attachment_type)
                VALUES ($1, $2, $3, $4)
                ON DUPLICATE KEY UPDATE
                attachment_type = VALUES(attachment_type)
            """
            
            await self.db.execute(query, node_file_id, node_id, file_id, attachment_type.value)
            logger.info(f"节点文件关联成功: node={node_id}, file={file_id}")
            return True
            
        except Exception as e:
            logger.error(f"节点文件关联失败: {e}")
            return False
    
    async def get_node_files(self, node_id: uuid.UUID) -> List[Dict[str, Any]]:
        """获取节点的所有文件"""
        try:
            query = """
                SELECT nf.*, wf.*, u.username as uploaded_by_name
                FROM node_file nf
                JOIN workflow_file wf ON nf.file_id = wf.file_id
                LEFT JOIN user u ON wf.uploaded_by = u.user_id
                WHERE nf.node_id = $1 AND wf.is_deleted = FALSE
                ORDER BY nf.created_at DESC
            """
            
            files = await self.db.fetch_all(query, node_id)
            return self._process_datetime_fields(files)
            
        except Exception as e:
            logger.error(f"获取节点文件失败: {e}")
            return []
    
    async def remove_node_file_association(self, node_id: uuid.UUID, file_id: uuid.UUID) -> bool:
        """移除节点文件关联"""
        try:
            query = "DELETE FROM node_file WHERE node_id = $1 AND file_id = $2"
            await self.db.execute(query, node_id, file_id)
            logger.info(f"移除节点文件关联成功: node={node_id}, file={file_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除节点文件关联失败: {e}")
            return False

    async def inherit_node_files_to_instance(self, node_id: uuid.UUID, node_instance_id: uuid.UUID) -> bool:
        """
        将节点设计时的附件继承到节点实例
        Critical: 在 node_instance 创建时必须调用此方法
        """
        try:
            # 🔧 Linus式修复: 通过node_id找到node_base_id，然后继承附件
            inherit_query = """
                INSERT INTO node_instance_file (node_instance_file_id, node_instance_id, file_id, attachment_type)
                SELECT UUID(), %s, nf.file_id, nf.attachment_type
                FROM node_file nf
                JOIN node n ON nf.node_id = n.node_base_id
                WHERE n.node_id = %s
            """
            
            result = await self.db.execute(inherit_query, node_instance_id, node_id)
            
            # 验证继承结果
            count_query = """
                SELECT COUNT(*) as inherited_count
                FROM node_instance_file nif
                WHERE nif.node_instance_id = %s
            """
            count_result = await self.db.fetch_one(count_query, node_instance_id)
            inherited_count = count_result['inherited_count'] if count_result else 0
            
            logger.info(f"✅ [附件继承] 节点 {node_id} -> 实例 {node_instance_id}: 继承了 {inherited_count} 个附件")
            return True
            
        except Exception as e:
            logger.error(f"❌ [附件继承] 节点附件继承失败: {e}")
            return False
    
    # ==================== 节点实例文件关联管理 ====================
    
    async def associate_node_instance_file(self, node_instance_id: uuid.UUID, file_id: uuid.UUID,
                                         attachment_type: AttachmentType = AttachmentType.INPUT) -> bool:
        """关联节点实例和文件"""
        try:
            # MySQL兼容语法 - 使用IGNORE忽略重复插入
            query = """
                INSERT IGNORE INTO node_instance_file (node_instance_id, file_id, attachment_type)
                VALUES ($1, $2, $3)
            """
            
            await self.db.execute(query, node_instance_id, file_id, attachment_type.value)
            logger.info(f"节点实例文件关联成功: node_instance={node_instance_id}, file={file_id}")
            return True
            
        except Exception as e:
            logger.error(f"节点实例文件关联失败: {e}")
            return False
    
    async def get_node_instance_files(self, node_instance_id: uuid.UUID, 
                                    attachment_type: Optional[AttachmentType] = None) -> List[Dict[str, Any]]:
        """获取节点实例的文件"""
        try:
            base_query = """
                SELECT nif.*, wf.*, u.username as uploaded_by_name
                FROM node_instance_file nif
                JOIN workflow_file wf ON nif.file_id = wf.file_id
                LEFT JOIN user u ON wf.uploaded_by = u.user_id
                WHERE nif.node_instance_id = $1 AND wf.is_deleted = FALSE
            """
            
            if attachment_type:
                query = base_query + " AND nif.attachment_type = $2 ORDER BY nif.created_at DESC"
                files = await self.db.fetch_all(query, node_instance_id, attachment_type.value)
            else:
                query = base_query + " ORDER BY nif.created_at DESC"
                files = await self.db.fetch_all(query, node_instance_id)
                
            return self._process_datetime_fields(files)
            
        except Exception as e:
            logger.error(f"获取节点实例文件失败: {e}")
            return []
    
    # ==================== 任务实例文件关联管理 ====================
    
    async def associate_task_instance_file(self, task_instance_id: uuid.UUID, file_id: uuid.UUID,
                                         uploaded_by: uuid.UUID, 
                                         attachment_type: AttachmentType = AttachmentType.INPUT) -> bool:
        """关联任务实例和文件"""
        try:
            # 🔧 Linus式修复: 正确处理主键ID和MySQL语法
            task_instance_file_id = str(uuid.uuid4())
            
            # MySQL兼容语法 - 修复参数占位符
            query = """
                INSERT IGNORE INTO task_instance_file (task_instance_file_id, task_instance_id, file_id, uploaded_by, attachment_type)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            await self.db.execute(query, task_instance_file_id, task_instance_id, file_id, uploaded_by, attachment_type.value)
            logger.info(f"任务实例文件关联成功: task_instance={task_instance_id}, file={file_id}")
            return True
            
        except Exception as e:
            logger.error(f"任务实例文件关联失败: {e}")
            return False
    
    async def get_task_instance_files(self, task_instance_id: uuid.UUID,
                                    attachment_type: Optional[AttachmentType] = None) -> List[Dict[str, Any]]:
        """获取任务实例的文件"""
        try:
            base_query = """
                SELECT tif.*, wf.*, u1.username as uploaded_by_name, u2.username as file_uploader_name
                FROM task_instance_file tif
                JOIN workflow_file wf ON tif.file_id = wf.file_id
                LEFT JOIN user u1 ON tif.uploaded_by = u1.user_id
                LEFT JOIN user u2 ON wf.uploaded_by = u2.user_id
                WHERE tif.task_instance_id = $1 AND wf.is_deleted = FALSE
            """
            
            if attachment_type:
                query = base_query + " AND tif.attachment_type = $2 ORDER BY tif.created_at DESC"
                files = await self.db.fetch_all(query, task_instance_id, attachment_type.value)
            else:
                query = base_query + " ORDER BY tif.created_at DESC"
                files = await self.db.fetch_all(query, task_instance_id)
                
            return self._process_datetime_fields(files)
            
        except Exception as e:
            logger.error(f"获取任务实例文件失败: {e}")
            return []
    
    # ==================== 批量操作 ====================
    
    async def batch_associate_files(self, entity_type: str, entity_id: uuid.UUID, 
                                  file_ids: List[uuid.UUID], attachment_type: AttachmentType,
                                  uploaded_by: Optional[uuid.UUID] = None) -> FileBatchResponse:
        """批量关联文件到实体"""
        success_files = []
        failed_files = []
        
        for file_id in file_ids:
            try:
                success = False
                
                if entity_type == "node":
                    success = await self.associate_node_file(entity_id, file_id, attachment_type)
                elif entity_type == "node_instance":
                    success = await self.associate_node_instance_file(entity_id, file_id, attachment_type)
                elif entity_type == "task_instance" and uploaded_by:
                    success = await self.associate_task_instance_file(entity_id, file_id, uploaded_by, attachment_type)
                elif entity_type == "user" and uploaded_by:
                    success = await self.associate_user_file(uploaded_by, file_id, AccessType.OWNER)
                
                if success:
                    success_files.append(file_id)
                else:
                    failed_files.append({"file_id": file_id, "reason": "关联操作失败"})
                    
            except Exception as e:
                failed_files.append({"file_id": file_id, "reason": str(e)})
        
        return FileBatchResponse(
            success_count=len(success_files),
            failed_count=len(failed_files),
            success_files=[str(file_id) for file_id in success_files],  # Linus式修复: 转换UUID为字符串
            failed_files=failed_files
        )
    
    # ==================== 权限验证 ====================
    
    async def check_file_permission(self, file_id: uuid.UUID, user_id: uuid.UUID, 
                                  action: str = "read") -> bool:
        """检查用户对文件的权限"""
        try:
            # Linus式调试: 记录权限检查参数
            logger.info(f"检查文件权限: file_id={file_id}, user_id={user_id}, action={action}")
            
            # 检查用户是否是文件的上传者或有访问权限
            # Linus式修复: 使用不同的参数占位符避免重复
            query = """
                SELECT 1 FROM workflow_file wf
                LEFT JOIN user_file uf ON wf.file_id = uf.file_id AND uf.user_id = $2
                WHERE wf.file_id = $1 AND wf.is_deleted = FALSE
                AND (wf.uploaded_by = $3 OR uf.user_id IS NOT NULL)
            """
            
            logger.info(f"执行权限查询: {query}")
            logger.info(f"查询参数: [{file_id}, {user_id}, {user_id}]")
            
            result = await self.db.fetch_one(query, file_id, user_id, user_id)
            has_permission = result is not None
            
            logger.info(f"权限检查结果: {has_permission}")
            return has_permission
            
        except Exception as e:
            logger.error(f"检查文件权限失败: {e}")
            return False
    
    # ==================== 统计和清理 ====================
    
    async def get_file_statistics(self, user_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """获取文件统计信息"""
        try:
            base_condition = "WHERE wf.is_deleted = FALSE"
            params = []
            
            if user_id:
                base_condition += " AND wf.uploaded_by = $1"
                params.append(user_id)
            
            # 总文件数和大小
            stats_query = f"""
                SELECT 
                    COUNT(*) as total_files,
                    COALESCE(SUM(wf.file_size), 0) as total_size,
                    ROUND(COALESCE(SUM(wf.file_size), 0) / 1024.0 / 1024.0, 2) as total_size_mb
                FROM workflow_file wf
                {base_condition}
            """
            
            stats = await self.db.fetch_one(stats_query, *params)
            
            # 文件类型统计
            type_query = f"""
                SELECT content_type, COUNT(*) as count
                FROM workflow_file wf
                {base_condition}
                GROUP BY content_type
                ORDER BY count DESC
                LIMIT 10
            """
            
            types = await self.db.fetch_all(type_query, *params)
            
            return {
                'total_files': int(stats['total_files']) if stats and stats['total_files'] else 0,
                'total_size': int(stats['total_size']) if stats and stats['total_size'] else 0,
                'total_size_mb': float(stats['total_size_mb']) if stats and stats['total_size_mb'] else 0.0,
                'file_type_stats': {t['content_type']: int(t['count']) for t in types}
            }
            
        except Exception as e:
            logger.error(f"获取文件统计失败: {e}")
            return {'total_files': 0, 'total_size': 0, 'total_size_mb': 0.0, 'file_type_stats': {}}


# 全局文件关联服务实例
_file_association_service: Optional[FileAssociationService] = None

def get_file_association_service() -> FileAssociationService:
    """获取文件关联服务实例"""
    global _file_association_service
    if _file_association_service is None:
        _file_association_service = FileAssociationService()
    return _file_association_service