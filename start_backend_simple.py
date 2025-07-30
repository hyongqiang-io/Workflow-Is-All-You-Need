#!/usr/bin/env python3
"""
简化的后端启动脚本
Simple Backend Startup Script
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目路径到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量
os.environ['PYTHONPATH'] = str(project_root)

def main():
    """启动应用"""
    try:
        print("启动工作流管理框架...")
        print(f"项目根目录: {project_root}")
        
        # 导入主应用
        from main import app
        import uvicorn
        
        print("模块导入成功")
        print("启动HTTP服务器...")
        print("访问地址: http://localhost:8001")
        print("API文档: http://localhost:8001/docs")
        print("自动重载: 已禁用")
        print("-" * 50)
        
        # 启动服务器
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8001,
            reload=False,  # 禁用自动重载以防止服务自动关闭
            log_level="info",
            access_log=True
        )
        
    except ImportError as e:
        print(f"模块导入失败: {e}")
        print("请检查依赖是否已安装: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()