"""
群组业务服务
Group Service
"""

import uuid
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger

from ..models.group import (
    GroupCreate, GroupUpdate, GroupResponse, GroupQuery,
    GroupList, GroupMember, ProcessorGroupInfo
)
from ..repositories.group.group_repository import GroupRepository
from ..repositories.processor.processor_repository import ProcessorRepository
from ..utils.exceptions import ValidationError, ConflictError, NotFoundError, AuthorizationError
from ..utils.helpers import now_utc


class GroupService:
    """群组业务服务类"""

    def __init__(self):
        self.group_repository = GroupRepository()
        self.processor_repository = ProcessorRepository()

    async def create_group(self, group_data: GroupCreate, creator_id: uuid.UUID) -> GroupResponse:
        """创建群组"""
        try:
            logger.info(f"开始创建群组 - 群组名称: {group_data.group_name}, 创建者ID: {creator_id}")
            logger.debug(f"群组数据: {group_data.dict()}")

            # 验证群组名称唯一性（可选，根据业务需求）
            # 这里暂时不限制重名

            # 创建群组
            logger.debug("调用群组仓储创建群组")
            created_group = await self.group_repository.create_group(group_data, creator_id)

            if not created_group:
                logger.error("群组仓储返回空结果")
                raise ValidationError("创建群组失败")

            logger.info(f"群组创建成功，群组ID: {created_group.get('group_id')}")
            logger.debug(f"创建的群组详情: {created_group}")

            response = self._format_group_response(created_group)
            logger.debug(f"格式化后的响应: {response}")

            return response

        except Exception as e:
            logger.error(f"创建群组失败，错误类型: {type(e).__name__}, 错误信息: {e}")
            logger.exception("完整的错误堆栈:")
            raise

    async def get_group_by_id(self, group_id: str, user_id: Optional[uuid.UUID] = None) -> Optional[GroupResponse]:
        """根据ID获取群组"""
        try:
            group_record = await self.group_repository.get_group_by_id(
                group_id, str(user_id) if user_id else None
            )

            if not group_record:
                return None

            return self._format_group_response(group_record)

        except Exception as e:
            logger.error(f"获取群组失败: {e}")
            return None

    async def search_groups(self, query_params: GroupQuery, user_id: Optional[uuid.UUID] = None) -> GroupList:
        """搜索群组"""
        try:
            groups, total = await self.group_repository.search_groups(
                query_params, str(user_id) if user_id else None
            )

            group_responses = [self._format_group_response(group) for group in groups]

            total_pages = (total + query_params.page_size - 1) // query_params.page_size

            return GroupList(
                groups=group_responses,
                total=total,
                page=query_params.page,
                page_size=query_params.page_size,
                total_pages=total_pages
            )

        except Exception as e:
            logger.error(f"搜索群组失败: {e}")
            return GroupList(
                groups=[],
                total=0,
                page=query_params.page,
                page_size=query_params.page_size,
                total_pages=0
            )

    async def update_group(self, group_id: str, group_data: GroupUpdate, user_id: uuid.UUID) -> GroupResponse:
        """更新群组"""
        try:
            # 验证权限 - 只有创建者可以修改群组
            if not await self.group_repository.is_group_creator(group_id, str(user_id)):
                raise AuthorizationError("无权限修改此群组")

            updated_group = await self.group_repository.update_group(group_id, group_data)
            if not updated_group:
                raise NotFoundError("群组不存在")

            return self._format_group_response(updated_group)

        except Exception as e:
            logger.error(f"更新群组失败: {e}")
            raise

    async def delete_group(self, group_id: str, user_id: uuid.UUID) -> bool:
        """删除群组"""
        try:
            # 验证权限 - 只有创建者可以删除群组
            if not await self.group_repository.is_group_creator(group_id, str(user_id)):
                raise AuthorizationError("无权限删除此群组")

            # 检查群组是否存在
            group = await self.group_repository.get_group_by_id(group_id)
            if not group:
                raise NotFoundError("群组不存在")

            return await self.group_repository.delete_group(group_id)

        except Exception as e:
            logger.error(f"删除群组失败: {e}")
            raise

    async def join_group(self, group_id: str, user_id: uuid.UUID) -> bool:
        """加入群组"""
        try:
            # 检查群组是否存在
            group = await self.group_repository.get_group_by_id(group_id)
            if not group:
                raise NotFoundError("群组不存在")

            # 检查群组是否公开
            if not group['is_public']:
                raise AuthorizationError("该群组不允许自由加入")

            # 检查是否已经是成员
            if await self.group_repository.is_user_member(group_id, str(user_id)):
                return True  # 已经是成员，返回成功

            return await self.group_repository.join_group(group_id, str(user_id))

        except Exception as e:
            logger.error(f"加入群组失败: {e}")
            raise

    async def leave_group(self, group_id: str, user_id: uuid.UUID) -> bool:
        """退出群组"""
        try:
            # 检查群组是否存在
            group = await self.group_repository.get_group_by_id(group_id)
            if not group:
                raise NotFoundError("群组不存在")

            # 创建者不能退出自己的群组
            if await self.group_repository.is_group_creator(group_id, str(user_id)):
                raise ValidationError("群组创建者不能退出群组")

            # 检查是否是成员
            if not await self.group_repository.is_user_member(group_id, str(user_id)):
                return True  # 不是成员，返回成功

            return await self.group_repository.leave_group(group_id, str(user_id))

        except Exception as e:
            logger.error(f"退出群组失败: {e}")
            raise

    async def get_group_members(self, group_id: str, page: int = 1, page_size: int = 50) -> Tuple[List[GroupMember], int]:
        """获取群组成员列表"""
        try:
            # 检查群组是否存在
            group = await self.group_repository.get_group_by_id(group_id)
            if not group:
                raise NotFoundError("群组不存在")

            members, total = await self.group_repository.get_group_members(group_id, page, page_size)

            member_responses = [
                GroupMember(
                    id=uuid.UUID(member['id']),
                    group_id=uuid.UUID(member['group_id']),
                    user_id=uuid.UUID(member['user_id']),
                    username=member['username'],
                    email=member['email'],
                    joined_at=member['joined_at'].isoformat() if member['joined_at'] else None,
                    status=member['status']
                )
                for member in members
            ]

            return member_responses, total

        except Exception as e:
            logger.error(f"获取群组成员失败: {e}")
            raise

    async def get_user_groups(self, user_id: uuid.UUID) -> List[GroupResponse]:
        """获取用户加入的群组列表"""
        try:
            query = GroupQuery(
                member_user_id=user_id,
                page=1,
                page_size=100  # 假设一个用户不会加入超过100个群组
            )

            result = await self.search_groups(query, user_id)
            return result.groups

        except Exception as e:
            logger.error(f"获取用户群组失败: {e}")
            return []

    async def get_group_processors(self, group_id: str, user_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        """获取群组内的processor列表"""
        try:
            # 检查群组是否存在
            group = await self.group_repository.get_group_by_id(group_id)
            if not group:
                raise NotFoundError("群组不存在")

            # 如果群组不公开，需要验证用户权限
            if not group['is_public'] and user_id:
                if not await self.group_repository.is_user_member(group_id, str(user_id)):
                    raise AuthorizationError("无权限查看此群组的processor")

            # 获取群组内的processor
            processors = await self.processor_repository.get_processors_by_group(group_id)
            return processors

        except Exception as e:
            logger.error(f"获取群组processor失败: {e}")
            raise

    def _format_group_response(self, group_record: Dict[str, Any]) -> GroupResponse:
        """格式化群组响应数据"""
        return GroupResponse(
            group_id=uuid.UUID(group_record['group_id']),
            group_name=group_record['group_name'],
            description=group_record.get('description'),
            avatar_url=group_record.get('avatar_url'),
            is_public=group_record['is_public'],
            creator_id=uuid.UUID(group_record['creator_id']),
            creator_name=group_record.get('creator_name'),
            member_count=group_record['member_count'],
            is_member=group_record.get('is_member', False),
            is_creator=group_record.get('is_creator', False),
            created_at=group_record['created_at'].isoformat() if group_record['created_at'] else None,
            updated_at=group_record['updated_at'].isoformat() if group_record['updated_at'] else None
        )