"""
数据库辅助工具
Database Helper Utils
"""

import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


def generate_uuid() -> uuid.UUID:
    """生成UUID"""
    return uuid.uuid4()


def now_utc() -> datetime:
    """获取当前UTC时间"""
    return datetime.now(timezone.utc)


def safe_json_serializer(obj):
    """
    安全的JSON序列化器，处理特殊类型对象
    
    Args:
        obj: 要序列化的对象
        
    Returns:
        可序列化的值
        
    Raises:
        TypeError: 如果对象类型不受支持
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        # 处理自定义对象
        return obj.__dict__
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def safe_json_dumps(data: Any, **kwargs) -> str:
    """
    安全的JSON dumps，自动处理特殊类型对象
    
    Args:
        data: 要序列化的数据
        **kwargs: 传递给json.dumps的其他参数
        
    Returns:
        JSON字符串
    """
    # 设置默认参数
    default_kwargs = {
        'ensure_ascii': False,
        'indent': 2,
        'default': safe_json_serializer
    }
    default_kwargs.update(kwargs)
    
    return json.dumps(data, **default_kwargs)


def safe_json_loads(json_str: Optional[str], default: Any = None) -> Any:
    """
    安全的JSON loads，处理解析错误
    
    Args:
        json_str: 要解析的JSON字符串
        default: 解析失败时的默认值
        
    Returns:
        解析后的数据或默认值
    """
    if not json_str or not isinstance(json_str, str):
        return default
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        # 记录错误但不抛出异常
        import logging
        logging.warning(f"JSON解析失败: {e}, 原始数据: {json_str[:100]}...")
        return default


def dict_to_sql_update(data: Dict[str, Any], exclude: Optional[List[str]] = None) -> tuple:
    """
    将字典转换为SQL UPDATE语句的SET部分
    支持自动处理JSONB字段的序列化
    
    Args:
        data: 要更新的数据字典
        exclude: 要排除的字段列表
    
    Returns:
        (set_clause, values) 元组
    """
    if exclude is None:
        exclude = []
    
    filtered_data = {k: v for k, v in data.items() if k not in exclude and v is not None}
    
    if not filtered_data:
        return "", ()
    
    set_clauses = []
    values = []
    param_index = 1
    
    for key, value in filtered_data.items():
        set_clauses.append(f"{key} = ${param_index}")
        # 处理JSONB字段的序列化
        if isinstance(value, (dict, list)):
            values.append(safe_json_dumps(value))
        else:
            values.append(value)
        param_index += 1
    
    return ", ".join(set_clauses), tuple(values)


def dict_to_sql_insert(data: Dict[str, Any], exclude: Optional[List[str]] = None) -> tuple:
    """
    将字典转换为SQL INSERT语句的VALUES部分
    支持自动处理JSONB字段的序列化
    
    Args:
        data: 要插入的数据字典
        exclude: 要排除的字段列表
    
    Returns:
        (columns, placeholders, values) 元组
    """
    if exclude is None:
        exclude = []
    
    filtered_data = {k: v for k, v in data.items() if k not in exclude and v is not None}
    
    if not filtered_data:
        return "", "", ()
    
    columns = list(filtered_data.keys())
    placeholders = [f"${i+1}" for i in range(len(columns))]
    
    # 处理JSONB字段的序列化
    values = []
    for value in filtered_data.values():
        if isinstance(value, (dict, list)):
            # 对字典和列表进行JSON序列化
            values.append(safe_json_dumps(value))
        else:
            values.append(value)
    
    return ", ".join(columns), ", ".join(placeholders), tuple(values)


def build_where_clause(conditions: Dict[str, Any], start_param: int = 1) -> tuple:
    """
    构建WHERE子句
    
    Args:
        conditions: 查询条件字典
        start_param: 参数起始编号
    
    Returns:
        (where_clause, values, next_param_index) 元组
    """
    if not conditions:
        return "", (), start_param
    
    where_clauses = []
    values = []
    param_index = start_param
    
    for key, value in conditions.items():
        if value is not None:
            if isinstance(value, list):
                placeholders = [f"${param_index + i}" for i in range(len(value))]
                where_clauses.append(f"{key} = ANY(${param_index})")
                values.append(value)
                param_index += 1
            else:
                where_clauses.append(f"{key} = ${param_index}")
                values.append(value)
                param_index += 1
    
    where_clause = " AND ".join(where_clauses) if where_clauses else ""
    return where_clause, tuple(values), param_index


def paginate_query(base_query: str, page: int = 1, page_size: int = 20) -> str:
    """
    为查询添加分页
    
    Args:
        base_query: 基础查询语句
        page: 页码（从1开始）
        page_size: 每页大小
    
    Returns:
        带分页的查询语句
    """
    offset = (page - 1) * page_size
    return f"{base_query} LIMIT {page_size} OFFSET {offset}"


class QueryBuilder:
    """SQL查询构建器"""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.reset()
    
    def reset(self):
        """重置构建器"""
        self._select = "*"
        self._where_conditions = {}
        self._joins = []
        self._order_by = []
        self._group_by = []
        self._having = ""
        self._limit = None
        self._offset = None
        return self
    
    def select(self, columns: str):
        """设置SELECT字段"""
        self._select = columns
        return self
    
    def where(self, **conditions):
        """添加WHERE条件"""
        self._where_conditions.update(conditions)
        return self
    
    def join(self, join_clause: str):
        """添加JOIN"""
        self._joins.append(join_clause)
        return self
    
    def order_by(self, column: str, direction: str = "ASC"):
        """添加ORDER BY"""
        self._order_by.append(f"{column} {direction}")
        return self
    
    def group_by(self, column: str):
        """添加GROUP BY"""
        self._group_by.append(column)
        return self
    
    def limit(self, limit: int):
        """设置LIMIT"""
        self._limit = limit
        return self
    
    def offset(self, offset: int):
        """设置OFFSET"""
        self._offset = offset
        return self
    
    def build(self) -> tuple:
        """构建查询语句"""
        query_parts = [f"SELECT {self._select}", f"FROM {self.table_name}"]
        
        # 添加JOIN
        if self._joins:
            query_parts.extend(self._joins)
        
        # 添加WHERE
        where_clause, values, _ = build_where_clause(self._where_conditions)
        if where_clause:
            query_parts.append(f"WHERE {where_clause}")
        
        # 添加GROUP BY
        if self._group_by:
            query_parts.append(f"GROUP BY {', '.join(self._group_by)}")
        
        # 添加HAVING
        if self._having:
            query_parts.append(f"HAVING {self._having}")
        
        # 添加ORDER BY
        if self._order_by:
            query_parts.append(f"ORDER BY {', '.join(self._order_by)}")
        
        # 添加LIMIT和OFFSET
        if self._limit:
            query_parts.append(f"LIMIT {self._limit}")
        
        if self._offset:
            query_parts.append(f"OFFSET {self._offset}")
        
        return " ".join(query_parts), values