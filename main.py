"""
工作流框架主应用
Workflow Framework Main Application
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import sys
import time

from backend.api.auth import router as auth_router
from backend.api.user import router as user_router
from backend.api.workflow import router as workflow_router
from backend.api.node import router as node_router
from backend.api.processor import router as processor_router
from backend.api.execution import router as execution_router
from backend.api.tools import router as tools_router
from backend.api.test import router as test_router
from backend.api.workflow_output import router as workflow_output_router
from backend.api.mcp import router as mcp_router
from backend.api.mcp_user_tools import router as mcp_user_tools_router
from backend.api.agent_tools import router as agent_tools_router
from backend.utils.database import initialize_database, close_database
from backend.utils.exceptions import BusinessException, ErrorResponse
from backend.services.execution_service import execution_engine
from backend.services.agent_task_service import agent_task_service
from backend.services.monitoring_service import monitoring_service

# 配置日志 - 修复Windows GBK编码问题
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    enqueue=True  # 避免多线程日志冲突
)

# 创建FastAPI应用
app = FastAPI(
    title="工作流管理框架",
    description="人机协作工作流开发框架",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求"""
    start_time = time.time()
    
    # 记录请求信息
    logger.trace(f"HTTP请求进入: {request.method} {request.url}")
    logger.trace(f"请求路径: {request.url.path}")
    logger.trace(f"请求头: {dict(request.headers)}")
    
    # 特别关注删除请求
    if request.method == "DELETE" and "processors" in str(request.url.path):
        logger.trace(f"收到删除处理器请求: {request.url.path}")
        logger.trace(f"完整URL: {request.url}")
    
    response = await call_next(request)
    
    # 记录响应信息
    process_time = time.time() - start_time
    logger.trace(f"HTTP响应: {response.status_code} (耗时: {process_time:.3f}s)")
    
    # 如果是404，记录更多信息
    if response.status_code == 404:
        logger.error(f"404错误: {request.method} {request.url.path}")
    
    return response

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制为具体域名
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
    
    # 如果detail是字典（来自BusinessException），直接返回
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # 否则包装为标准错误响应
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


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        logger.trace("正在启动工作流管理框架...")
        
        # 初始化数据库连接
        await initialize_database()
        logger.trace("数据库连接初始化成功")
        
        # 启动执行引擎
        await execution_engine.start_engine()
        logger.trace("工作流执行引擎启动成功")
        
        # 启动Agent任务服务
        await agent_task_service.start_service()
        logger.trace("Agent任务处理服务启动成功")
        
        # 启动MCP工具服务
        from backend.services.mcp_tool_service import mcp_tool_service
        await mcp_tool_service.initialize()
        logger.trace("MCP工具管理服务启动成功")
        
        # 启动数据库驱动的MCP服务（替代原有服务）
        from backend.services.database_mcp_service import database_mcp_service
        await database_mcp_service.initialize()
        logger.trace("数据库驱动的MCP服务启动成功")
        
        # 启动监控服务
        await monitoring_service.start_monitoring()
        logger.trace("监控服务启动成功")
        
        logger.trace("工作流管理框架启动完成")
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    try:
        logger.trace("正在关闭工作流管理框架...")
        
        # 停止监控服务
        await monitoring_service.stop_monitoring()
        logger.trace("监控服务已停止")
        
        # 停止数据库驱动的MCP服务
        from backend.services.database_mcp_service import database_mcp_service
        await database_mcp_service.shutdown()
        logger.trace("数据库驱动的MCP服务已停止")
        
        # 停止MCP工具服务
        from backend.services.mcp_tool_service import mcp_tool_service
        await mcp_tool_service.shutdown()
        logger.trace("MCP工具管理服务已停止")
        
        # 停止Agent任务服务
        await agent_task_service.stop_service()
        logger.trace("Agent任务处理服务已停止")
        
        # 停止执行引擎
        await execution_engine.stop_engine()
        logger.trace("工作流执行引擎已停止")
        
        # 关闭数据库连接
        await close_database()
        logger.trace("数据库连接已关闭")
        
        logger.trace("工作流管理框架已关闭")
        
    except Exception as e:
        logger.error(f"应用关闭异常: {e}")


# 注册路由  
logger.trace("开始注册路由...")
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(node_router, prefix="/api")
logger.trace("注册processor路由...")
app.include_router(processor_router, prefix="/api")
logger.trace("processor路由注册完成")
app.include_router(execution_router)
app.include_router(tools_router, prefix="/api")
app.include_router(test_router, prefix="/api")
app.include_router(workflow_output_router)
logger.trace("注册MCP路由...")
app.include_router(mcp_router, prefix="/api")
logger.trace("MCP路由注册完成")

# 注册新的MCP工具管理路由
logger.trace("注册MCP用户工具管理路由...")
app.include_router(mcp_user_tools_router, prefix="/api/mcp", tags=["MCP用户工具"])
logger.trace("MCP用户工具管理路由注册完成")

# 注册Agent工具绑定路由
logger.trace("注册Agent工具绑定路由...")
app.include_router(agent_tools_router, prefix="/api", tags=["Agent工具绑定"])
logger.trace("Agent工具绑定路由注册完成")
logger.trace("所有路由注册完成")

# 打印所有已注册的路由用于调试
logger.trace("已注册的路由列表:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        logger.trace(f"{list(route.methods)} {route.path}")
    elif hasattr(route, 'path_regex'):
        logger.trace(f"路由: {route.path_regex.pattern}")


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用工作流管理框架",
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "message": "服务运行正常"
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.trace("启动服务器...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,  # 恢复为8001端口
        reload=False,  # 禁用自动重载以防止服务自动关闭
        log_level="info"
    )