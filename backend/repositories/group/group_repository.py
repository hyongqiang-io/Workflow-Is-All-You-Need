"""
群组仓储实现
Group Repository Implementation
"""

import uuid
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger

from ..base import BaseRepository
from ...models.group import GroupCreate, GroupUpdate, GroupQuery, GroupMember
from ...utils.database import get_db_manager
from ...utils.helpers import now_utc


class GroupRepository(BaseRepository):
    """群组仓储类"""

    def __init__(self):
        super().__init__("groups")
        self.member_table_name = "group_members"
        self.db = get_db_manager()

    async def create_group(self, group_data: GroupCreate, creator_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """创建群组"""
        try:
            group_id = str(uuid.uuid4())
            logger.info(f"准备创建群组，生成ID: {group_id}")
            logger.debug(f"群组数据: name={group_data.group_name}, public={group_data.is_public}")

            # 使用事务确保群组和成员都创建成功
            logger.debug("开始数据库事务")
            async with self.db.transaction() as conn:
                logger.debug("事务开始成功，准备插入群组记录")

                # 插入群组记录
                group_query = """
                INSERT INTO `groups`
                (group_id, group_name, description, creator_id, avatar_url, is_public, member_count, created_at, updated_at, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                group_params = (
                    group_id,
                    group_data.group_name,
                    group_data.description,
                    str(creator_id),
                    group_data.avatar_url,
                    group_data.is_public,
                    1,  # 创建者自动成为成员
                    now_utc(),
                    now_utc(),
                    False
                )

                logger.debug(f"执行群组插入SQL: {group_query}")
                logger.debug(f"群组插入参数: {group_params}")

                await conn.execute(group_query, group_params)
                logger.info("群组记录插入成功")

                # 自动添加创建者为群组成员
                member_id = str(uuid.uuid4())
                logger.debug(f"准备添加创建者为成员，成员ID: {member_id}")

                member_query = """
                INSERT INTO group_members
                (id, group_id, user_id, joined_at, status)
                VALUES (%s, %s, %s, %s, %s)
                """

                member_params = (
                    member_id,
                    group_id,
                    str(creator_id),
                    now_utc(),
                    'active'
                )

                logger.debug(f"执行成员插入SQL: {member_query}")
                logger.debug(f"成员插入参数: {member_params}")

                await conn.execute(member_query, member_params)
                logger.info("创建者成员关系插入成功")

            logger.info("事务提交成功，开始获取创建的群组信息")

            # 获取创建的群组信息
            result = await self.get_group_by_id(group_id)
            logger.debug(f"获取群组信息结果: {result}")

            return result

        except Exception as e:
            logger.error(f"创建群组失败，错误类型: {type(e).__name__}, 错误信息: {e}")
            logger.exception("群组创建完整错误堆栈:")
            return None

    async def get_group_by_id(self, group_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """根据ID获取群组"""
        try:
            # 基础群组信息查询
            query = """
            SELECT g.group_id, g.group_name, g.description, g.creator_id, g.avatar_url,
                   g.is_public, g.member_count, g.created_at, g.updated_at,
                   u.username as creator_name
            FROM `groups` g
            LEFT JOIN user u ON g.creator_id = u.user_id
            WHERE g.group_id = %s AND g.is_deleted = FALSE
            """

            result = await self.db.fetch_one(query, group_id)

            if not result:
                return None

            group_dict = dict(result)

            # 如果提供了用户ID，检查用户是否为群组成员和创建者
            if user_id:
                group_dict['is_member'] = await self.is_user_member(group_id, user_id)
                group_dict['is_creator'] = str(group_dict['creator_id']) == str(user_id)
                logger.debug(f"用户权限检查 - 群组: {group_id}, 用户: {user_id}")
                logger.debug(f"  创建者ID: {group_dict['creator_id']} (类型: {type(group_dict['creator_id'])})")
                logger.debug(f"  当前用户: {user_id} (类型: {type(user_id)})")
                logger.debug(f"  是否成员: {group_dict['is_member']}")
                logger.debug(f"  是否创建者: {group_dict['is_creator']}")
            else:
                group_dict['is_member'] = False
                group_dict['is_creator'] = False

            return group_dict

        except Exception as e:
            logger.error(f"获取群组失败: {e}")
            return None

    async def search_groups(self, query_params: GroupQuery, user_id: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """搜索群组"""
        try:
            # 构建查询条件
            where_conditions = ["g.is_deleted = FALSE"]
            query_values = []

            # 关键词搜索
            if query_params.keyword:
                where_conditions.append("(g.group_name LIKE %s OR g.description LIKE %s)")
                keyword_pattern = f"%{query_params.keyword}%"
                query_values.extend([keyword_pattern, keyword_pattern])

            # 公开性筛选
            if query_params.is_public is not None:
                where_conditions.append("g.is_public = %s")
                query_values.append(query_params.is_public)

            # 成员筛选
            if query_params.my_groups and user_id:
                where_conditions.append("EXISTS (SELECT 1 FROM group_members gm WHERE gm.group_id = g.group_id AND gm.user_id = %s AND gm.status = 'active')")
                query_values.append(user_id)

            # 根据成员用户ID筛选
            if query_params.member_user_id:
                where_conditions.append("EXISTS (SELECT 1 FROM group_members gm WHERE gm.group_id = g.group_id AND gm.user_id = %s AND gm.status = 'active')")
                query_values.append(str(query_params.member_user_id))

            where_clause = " AND ".join(where_conditions)

            # 获取总数
            count_query = f"""
            SELECT COUNT(*) as total
            FROM `groups` g
            WHERE {where_clause}
            """

            count_result = await self.db.fetch_one(count_query, *query_values)
            total = count_result['total'] if count_result else 0

            # 获取群组列表
            offset = (query_params.page - 1) * query_params.page_size
            list_query = f"""
            SELECT g.group_id, g.group_name, g.description, g.creator_id, g.avatar_url,
                   g.is_public, g.member_count, g.created_at, g.updated_at,
                   u.username as creator_name
            FROM `groups` g
            LEFT JOIN user u ON g.creator_id = u.user_id
            WHERE {where_clause}
            ORDER BY g.created_at DESC
            LIMIT %s OFFSET %s
            """

            query_values.extend([query_params.page_size, offset])
            groups = await self.db.fetch_all(list_query, *query_values)

            # 为每个群组添加用户相关信息
            result_groups = []
            for group in groups:
                group_dict = dict(group)
                if user_id:
                    group_dict['is_member'] = await self.is_user_member(group['group_id'], user_id)
                    group_dict['is_creator'] = str(group['creator_id']) == str(user_id)
                    logger.debug(f"搜索结果权限检查 - 群组: {group['group_id']}, 用户: {user_id}")
                    logger.debug(f"  创建者ID: {group['creator_id']} vs 用户ID: {user_id}")
                    logger.debug(f"  是否创建者: {group_dict['is_creator']}")
                else:
                    group_dict['is_member'] = False
                    group_dict['is_creator'] = False
                result_groups.append(group_dict)

            return result_groups, total

        except Exception as e:
            logger.error(f"搜索群组失败: {e}")
            return [], 0

    async def update_group(self, group_id: str, group_data: GroupUpdate) -> Optional[Dict[str, Any]]:
        """更新群组"""
        try:
            # 构建更新字段
            update_fields = []
            values = []

            if group_data.group_name is not None:
                update_fields.append("group_name = %s")
                values.append(group_data.group_name)

            if group_data.description is not None:
                update_fields.append("description = %s")
                values.append(group_data.description)

            if group_data.avatar_url is not None:
                update_fields.append("avatar_url = %s")
                values.append(group_data.avatar_url)

            if group_data.is_public is not None:
                update_fields.append("is_public = %s")
                values.append(group_data.is_public)

            if not update_fields:
                return await self.get_group_by_id(group_id)

            update_fields.append("updated_at = %s")
            values.append(now_utc())
            values.append(group_id)

            query = f"""
            UPDATE `groups`
            SET {', '.join(update_fields)}
            WHERE group_id = %s AND is_deleted = FALSE
            """

            await self.db.execute(query, *values)
            return await self.get_group_by_id(group_id)

        except Exception as e:
            logger.error(f"更新群组失败: {e}")
            return None

    async def delete_group(self, group_id: str) -> bool:
        """删除群组"""
        try:
            query = """
            UPDATE `groups`
            SET is_deleted = TRUE, updated_at = %s
            WHERE group_id = %s AND is_deleted = FALSE
            """

            result = await self.db.execute(query, now_utc(), group_id)
            return "UPDATE 1" in result

        except Exception as e:
            logger.error(f"删除群组失败: {e}")
            return False

    async def join_group(self, group_id: str, user_id: str) -> bool:
        """加入群组"""
        try:
            # 检查群组是否存在且公开
            group = await self.get_group_by_id(group_id)
            if not group:
                logger.warning(f"群组 {group_id} 不存在")
                return False

            if not group['is_public']:
                logger.warning(f"群组 {group_id} 不是公开群组")
                return False

            # 检查是否已经是成员
            if await self.is_user_member(group_id, user_id):
                logger.info(f"用户 {user_id} 已经是群组 {group_id} 的成员")
                return True

            # 添加成员
            member_id = str(uuid.uuid4())
            query = """
            INSERT INTO group_members
            (id, group_id, user_id, joined_at, status)
            VALUES (%s, %s, %s, %s, %s)
            """

            await self.db.execute(query, member_id, group_id, user_id, now_utc(), 'active')

            # 数据库触发器会自动更新成员数量
            logger.info(f"用户 {user_id} 成功加入群组 {group_id}")
            return True

        except Exception as e:
            logger.error(f"加入群组失败: {e}")
            return False

    async def leave_group(self, group_id: str, user_id: str) -> bool:
        """离开群组"""
        try:
            # 检查是否为创建者
            if await self.is_group_creator(group_id, user_id):
                logger.warning(f"创建者不能离开自己的群组 {group_id}")
                return False

            # 检查是否为成员
            if not await self.is_user_member(group_id, user_id):
                logger.info(f"用户 {user_id} 不是群组 {group_id} 的成员")
                return True

            # 删除成员关系
            query = """
            DELETE FROM group_members
            WHERE group_id = %s AND user_id = %s
            """

            result = await self.db.execute(query, group_id, user_id)

            # 数据库触发器会自动更新成员数量
            success = "UPDATE" in result or "DELETE" in result
            if success:
                logger.info(f"用户 {user_id} 成功离开群组 {group_id}")
            return success

        except Exception as e:
            logger.error(f"离开群组失败: {e}")
            return False

    async def get_group_members(self, group_id: str, page: int = 1, page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """获取群组成员列表"""
        try:
            # 获取总数
            count_query = """
            SELECT COUNT(*) as total
            FROM group_members gm
            WHERE gm.group_id = %s AND gm.status = 'active'
            """

            count_result = await self.db.fetch_one(count_query, group_id)
            total = count_result['total'] if count_result else 0

            # 获取成员列表
            offset = (page - 1) * page_size
            list_query = """
            SELECT gm.id, gm.group_id, gm.user_id, gm.joined_at, gm.status,
                   u.username, u.email
            FROM group_members gm
            LEFT JOIN user u ON gm.user_id = u.user_id
            WHERE gm.group_id = %s AND gm.status = 'active'
            ORDER BY gm.joined_at ASC
            LIMIT %s OFFSET %s
            """

            members = await self.db.fetch_all(list_query, group_id, page_size, offset)

            return [dict(member) for member in members], total

        except Exception as e:
            logger.error(f"获取群组成员失败: {e}")
            return [], 0

    async def is_user_member(self, group_id: str, user_id: str) -> bool:
        """检查用户是否为群组成员"""
        try:
            query = """
            SELECT COUNT(*) as count
            FROM group_members
            WHERE group_id = %s AND user_id = %s AND status = 'active'
            """

            result = await self.db.fetch_one(query, group_id, user_id)
            return result and result['count'] > 0

        except Exception as e:
            logger.error(f"检查成员身份失败: {e}")
            return False

    async def is_group_creator(self, group_id: str, user_id: str) -> bool:
        """检查用户是否为群组创建者"""
        try:
            query = """
            SELECT COUNT(*) as count
            FROM `groups`
            WHERE group_id = %s AND creator_id = %s AND is_deleted = FALSE
            """

            result = await self.db.fetch_one(query, group_id, user_id)
            return result and result['count'] > 0

        except Exception as e:
            logger.error(f"检查创建者身份失败: {e}")
            return False

    async def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户加入的所有群组"""
        try:
            query = """
            SELECT g.group_id, g.group_name, g.description, g.creator_id, g.avatar_url,
                   g.is_public, g.member_count, g.created_at, g.updated_at,
                   u.username as creator_name,
                   gm.joined_at,
                   (g.creator_id = %s) as is_creator
            FROM `groups` g
            INNER JOIN group_members gm ON g.group_id = gm.group_id
            LEFT JOIN user u ON g.creator_id = u.user_id
            WHERE gm.user_id = %s AND gm.status = 'active' AND g.is_deleted = FALSE
            ORDER BY gm.joined_at DESC
            """

            groups = await self.db.fetch_all(query, user_id, user_id)

            result = []
            for group in groups:
                group_dict = dict(group)
                group_dict['is_member'] = True  # 显然用户是成员
                result.append(group_dict)

            return result

        except Exception as e:
            logger.error(f"获取用户群组失败: {e}")
            return []