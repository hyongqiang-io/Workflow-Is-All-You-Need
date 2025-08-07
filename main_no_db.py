"""
工作流框架主应用 - 跳过数据库初始化
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import sys

from backend.api.auth import router as auth_router
from backend.api.user import router as user_router  
from backend.api.workflow import router as workflow_router
from backend.api.node import router as node_router
from backend.api.processor import router as processor_router
from backend.api.execution import router as execution_router
from backend.api.tools import router as tools_router
from backend.api.test import router as test_router
from backend.utils.exceptions import BusinessException, ErrorResponse

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# 创建FastAPI应用
app = FastAPI(
    title="工作流管理框架",
    description="人机协作工作流开发框架 (无数据库模式)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(BusinessException)
async def business_exception_handler(request, exc: BusinessException):
    """业务异常处理器"""
    logger.warning(f"业务异常: {exc.error_code} - {exc.message}")
    
    error_response = ErrorResponse(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """HTTP异常处理器"""
    logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    error_response = ErrorResponse(
        error_code="HTTP_ERROR",
        message=str(exc.detail) if exc.detail else "请求处理失败"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """通用异常处理器"""
    logger.error(f"未处理的异常: {type(exc).__name__}: {str(exc)}")
    
    error_response = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="服务器内部错误"
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )

# 简化的启动和关闭事件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        logger.info("正在启动工作流管理框架（无数据库模式）...")
        logger.warning("数据库功能已禁用 - 仅API接口可用")
        logger.info("工作流管理框架启动完成")
    except Exception as e:
        logger.error(f"应用启动失败: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("工作流管理框架已关闭")

# 注册路由
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(node_router, prefix="/api")
app.include_router(processor_router, prefix="/api")
app.include_router(execution_router)
app.include_router(tools_router, prefix="/api")
app.include_router(test_router, prefix="/api")

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用工作流管理框架",
        "version": "1.0.0",
        "mode": "no-database",
        "docs": "/docs",
        "api": "/api",
        "warning": "数据库功能已禁用"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "message": "服务运行正常",
        "mode": "no-database"
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("启动开发服务器（无数据库模式）...")
    uvicorn.run(
        "main_no_db:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )