# 配置模块
from . import settings  # 主配置（MySQL）
from . import feishu_config

# 启动时验证飞书配置
try:
    from .feishu_config import FeishuConfig
    FeishuConfig.validate_all()
except Exception as e:
    print(f"飞书配置验证失败: {e}")

# 数据库类型确认
print("✅ 当前使用数据库: MySQL (端口: 3306)")
print("✅ 数据库驱动: aiomysql")