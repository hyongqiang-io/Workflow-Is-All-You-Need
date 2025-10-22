"""
工作流框架主应用
Workflow Framework Main Application
"""

import os
from pathlib import Path

# 自动加载环境配置
def load_environment():
    """加载环境配置文件"""
    project_root = Path(__file__).parent.absolute()
    
    # 根据 ENVIRONMENT 环境变量决定加载哪个配置文件
    env_name = os.environ.get('ENVIRONMENT', 'development')
    
    # 尝试加载对应的环境配置文件
    env_files = [
        f".env.{env_name}",
        ".env.development",  # 备用开发配置
        ".env"  # 默认配置
    ]
    
    for env_file in env_files:
        env_path = project_root / env_file
        if env_path.exists():
            print(f"🔧 加载环境配置: {env_file}")
            
            # 手动解析 .env 文件并设置环境变量
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        # 只有当环境变量不存在时才设置
                        if key not in os.environ:
                            os.environ[key] = value
            
            return True
    
    print("⚠️  未找到环境配置文件，使用默认配置")
    return False

# 在导入其他模块之前先加载环境配置
load_environment()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
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
from backend.api.ai_workflow import router as ai_workflow_router
from backend.api.task_subdivision import router as task_subdivision_router
from backend.api.workflow_template_connection import router as workflow_template_connection_router
from backend.api.workflow_merge import router as workflow_merge_router
from backend.api.context_health import router as context_health_router
from backend.api.feishu import router as feishu_router
from backend.api.feishu_bot import router as feishu_bot_router
from backend.api.files import router as files_router
from backend.api.tab_completion import router as tab_completion_router
from backend.api.workflow_store import router as workflow_store_router
from backend.api.group import router as group_router
from backend.api.task_conversation import router as task_conversation_router
from backend.api.simulator_conversation import router as simulator_conversation_router
from backend.utils.database import initialize_database, close_database
from backend.utils.exceptions import BusinessException, ErrorResponse
from backend.services.execution_service import execution_engine
from backend.services.agent_task_service import agent_task_service
from backend.services.monitoring_service import monitoring_service
from backend.services.workflow_monitor_service import get_workflow_monitor

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


async def startup_context_health_check():
    """启动时的上下文健康检查和预热"""
    try:
        logger.info("🔍 执行启动时上下文健康检查...")
        
        from backend.services.workflow_execution_context import get_context_manager
        from backend.repositories.instance.workflow_instance_repository import WorkflowInstanceRepository
        
        context_manager = get_context_manager()
        workflow_repo = WorkflowInstanceRepository()
        
        # 获取正在运行和等待中的工作流实例
        running_workflows = await workflow_repo.get_instances_by_status(['running', 'pending'])
        
        if running_workflows:
            logger.info(f"🔄 发现 {len(running_workflows)} 个活动工作流，进行上下文预热...")
            
            recovered_count = 0
            failed_count = 0
            
            for workflow in running_workflows:
                workflow_instance_id = workflow['workflow_instance_id']
                workflow_name = workflow.get('workflow_instance_name', '未知')
                
                try:
                    # 检查上下文健康状态
                    health_status = await context_manager.check_context_health(workflow_instance_id)
                    
                    if not health_status['healthy']:
                        logger.info(f"🔧 恢复工作流上下文: {workflow_name} ({workflow_instance_id})")
                        # 触发自动恢复
                        context = await context_manager._restore_context_from_database(workflow_instance_id)
                        if context:
                            recovered_count += 1
                            logger.debug(f"✅ 工作流上下文恢复成功: {workflow_name}")
                        else:
                            failed_count += 1
                            logger.warning(f"❌ 工作流上下文恢复失败: {workflow_name}")
                    else:
                        logger.debug(f"✅ 工作流上下文健康: {workflow_name}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ 检查工作流上下文失败: {workflow_name} - {e}")
            
            logger.info(f"📊 上下文预热完成: 恢复 {recovered_count} 个，失败 {failed_count} 个")
        else:
            logger.info("📋 没有发现活动工作流，跳过上下文预热")
        
        # 输出上下文管理器配置
        logger.info("⚙️ 上下文管理器配置:")
        logger.info(f"   - 自动恢复: {'启用' if context_manager._auto_recovery_enabled else '禁用'}")
        logger.info(f"   - 持久化: {'启用' if context_manager._persistence_enabled else '禁用'}")
        logger.info(f"   - 当前上下文数: {len(context_manager.contexts)}")
        
    except Exception as e:
        logger.error(f"启动时上下文健康检查失败: {e}")
        # 不抛出异常，避免阻止应用启动


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic请求验证错误处理器"""
    logger.error(f"🚨 请求验证失败: {request.method} {request.url.path}")
    logger.error(f"🚨 验证错误详情: {exc.errors()}")
    
    # 获取原始请求体用于调试
    try:
        if hasattr(request, '_body'):
            body = request._body
        else:
            body = await request.body()
        logger.error(f"🚨 原始请求体: {body.decode('utf-8')}")
    except Exception as e:
        logger.error(f"🚨 无法读取请求体: {e}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "请求数据验证失败"
        }
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Pydantic数据验证错误处理器"""
    logger.error(f"🚨 数据验证失败: {request.method} {request.url.path}")
    logger.error(f"🚨 Pydantic错误详情: {exc.errors()}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "数据格式验证失败"
        }
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

        # 初始化任务对话数据库表
        try:
            from backend.database.init_task_conversation import init_task_conversation_tables
            await init_task_conversation_tables()
            logger.trace("任务对话数据库表初始化成功")
        except Exception as e:
            logger.warning(f"任务对话数据库表初始化失败: {e}")
        
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
        
        # 🔧 启动停滞工作流监控服务
        workflow_monitor = get_workflow_monitor()
        await workflow_monitor.start_monitoring()
        logger.trace("停滞工作流监控服务启动成功")
        
        # 🔧 启动上下文健康检查服务
        await startup_context_health_check()
        logger.trace("上下文健康检查完成")
        
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
        
        # 停止停滞工作流监控服务
        workflow_monitor = get_workflow_monitor()
        await workflow_monitor.stop_monitoring()
        logger.trace("停滞工作流监控服务已停止")
        
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
# AI工作流生成路由
logger.trace("注册AI工作流生成路由...")
app.include_router(ai_workflow_router)
logger.trace("AI工作流生成路由注册完成")
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

# 注册AI工作流生成路由
logger.trace("注册AI工作流生成路由...")
app.include_router(ai_workflow_router, prefix="/api", tags=["AI工作流生成"])
logger.trace("AI工作流生成路由注册完成")

# 注册任务细分路由
logger.trace("注册任务细分路由...")
app.include_router(task_subdivision_router, prefix="/api", tags=["任务细分"])
logger.trace("任务细分路由注册完成")

# 注册工作流模板连接路由
logger.trace("注册工作流模板连接路由...")
app.include_router(workflow_template_connection_router, tags=["工作流模板连接"])
logger.trace("工作流模板连接路由注册完成")

# 注册工作流合并路由
logger.trace("注册工作流合并路由...")
app.include_router(workflow_merge_router, prefix="/api", tags=["工作流合并"])
logger.trace("工作流合并路由注册完成")

# 注册上下文健康监控路由
logger.trace("注册上下文健康监控路由...")
app.include_router(context_health_router, tags=["上下文健康监控"])
logger.trace("上下文健康监控路由注册完成")

# 注册飞书OAuth路由
logger.trace("注册飞书OAuth路由...")
app.include_router(feishu_router, prefix="/api", tags=["飞书OAuth"])
app.include_router(feishu_bot_router, prefix="/api", tags=["飞书机器人"])
logger.trace("飞书OAuth路由注册完成")

# 注册文件管理路由
logger.trace("注册文件管理路由...")
app.include_router(files_router, tags=["文件管理"])
app.include_router(tab_completion_router, tags=["Tab补全"])
app.include_router(workflow_store_router, prefix="/api", tags=["工作流商店"])
app.include_router(group_router, prefix="/api", tags=["群组管理"])
app.include_router(task_conversation_router, tags=["任务对话"])
app.include_router(simulator_conversation_router, tags=["Simulator对话"])
logger.trace("文件管理路由注册完成")

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
    import os
    
    # 统一使用8000端口
    environment = os.environ.get('ENVIRONMENT', 'production')
    port = int(os.environ.get('PORT', 8000))  # 统一使用8000端口
    
    logger.trace(f"启动服务器... (环境: {environment}, 端口: {port})")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
