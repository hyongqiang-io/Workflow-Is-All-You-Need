#!/usr/bin/env python3
"""
简化的后端启动脚本
"""

import uvicorn
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("启动后端服务...")
    print("服务地址: http://localhost:8080")
    print("API文档: http://localhost:8080/docs")
    print("按 Ctrl+C 停止服务")
    
    try:
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8080,
            reload=False,  # 禁用自动重载以防止服务自动关闭
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        print("请检查:")
        print("1. 是否安装了所有依赖: pip install -r requirements.txt")
        print("2. 数据库是否运行")
        print("3. 环境变量是否正确配置") 