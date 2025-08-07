#!/bin/bash

# 数据库备份脚本
# Database Backup Script

# 配置
BACKUP_DIR="/backup"
DB_CONTAINER="workflow_postgres"
DB_NAME="workflow_db"
DB_USER="postgres"
RETENTION_DAYS=30

# 创建备份目录
mkdir -p $BACKUP_DIR

# 生成时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/workflow_db_${TIMESTAMP}.sql"

echo "🗄️ 开始数据库备份..."
echo "时间: $(date)"
echo "备份文件: $BACKUP_FILE"

# 执行备份
docker exec $DB_CONTAINER pg_dump -U $DB_USER -h localhost $DB_NAME > $BACKUP_FILE

# 检查备份结果
if [ $? -eq 0 ]; then
    echo "✅ 数据库备份成功"
    
    # 压缩备份文件
    gzip $BACKUP_FILE
    echo "✅ 备份文件已压缩: ${BACKUP_FILE}.gz"
    
    # 显示备份文件大小
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}.gz" | cut -f1)
    echo "📁 备份文件大小: $BACKUP_SIZE"
    
else
    echo "❌ 数据库备份失败"
    exit 1
fi

# 清理旧备份
echo "🧹 清理超过 $RETENTION_DAYS 天的旧备份..."
find $BACKUP_DIR -name "workflow_db_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# 显示备份列表
echo "📋 当前备份文件列表:"
ls -lh $BACKUP_DIR/workflow_db_*.sql.gz | tail -10

echo "✅ 备份任务完成"