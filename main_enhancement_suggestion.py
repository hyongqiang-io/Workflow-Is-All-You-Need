"""
main函数数据库初始化增强建议
Enhanced database initialization for main function
"""

# 在startup_event函数中添加以下代码段，在initialize_database()之后：

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        logger.trace("正在启动工作流管理框架...")
        
        # 初始化数据库连接
        await initialize_database()
        logger.trace("数据库连接初始化成功")
        
        # 可选：验证数据库表结构完整性
        try:
            from backend.utils.database import db_manager
            
            # 简单验证关键表是否存在
            tables_to_check = ['user', 'workflow', 'node', 'processor', 'workflow_instance', 'node_instance', 'task_instance']
            for table_name in tables_to_check:
                count = await db_manager.fetch_val(f"SELECT COUNT(*) FROM `{table_name}` LIMIT 1")
                logger.trace(f"✅ 表 {table_name} 验证通过")
            
            logger.trace("数据库表结构验证完成")
            
        except Exception as e:
            logger.warning(f"数据库表结构验证失败: {e}")
            # 不抛出异常，允许应用继续启动
        
        # 其余启动逻辑...
        await execution_engine.start_engine()
        # ... 其他代码保持不变
        
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
        raise