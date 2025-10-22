"""
时间戳处理工具函数
Timestamp Processing Utilities
"""

from datetime import datetime
from typing import Union, Optional
from loguru import logger


def safe_parse_timestamp(timestamp_value: Union[str, datetime, None]) -> Optional[datetime]:
    """
    安全地解析时间戳，支持多种输入类型

    Args:
        timestamp_value: 时间戳值，可能是字符串、datetime对象或None

    Returns:
        解析后的datetime对象，或None
    """
    if not timestamp_value:
        return None

    try:
        # 如果已经是datetime对象，直接返回
        if isinstance(timestamp_value, datetime):
            return timestamp_value

        # 如果是字符串，尝试解析
        if isinstance(timestamp_value, str):
            # 处理ISO格式的时间戳
            if 'Z' in timestamp_value:
                return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(timestamp_value)

        # 其他类型，尝试转换为字符串再解析
        timestamp_str = str(timestamp_value)
        if 'Z' in timestamp_str:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(timestamp_str)

    except Exception as e:
        logger.warning(f"⚠️ 无法解析时间戳 {timestamp_value} (类型: {type(timestamp_value)}): {e}")
        return None


def safe_format_timestamp(timestamp_value: Union[str, datetime, None]) -> Optional[str]:
    """
    安全地格式化时间戳为ISO字符串

    Args:
        timestamp_value: 时间戳值

    Returns:
        ISO格式的时间戳字符串，或None
    """
    parsed_time = safe_parse_timestamp(timestamp_value)
    if parsed_time:
        return parsed_time.isoformat()
    return None