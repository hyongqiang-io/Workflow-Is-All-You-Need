#!/bin/bash

# 工作流应用数据库备份脚本
# Workflow Application Database Backup Script

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# 配置变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
DATABASE_PATH="${DATABASE_PATH:-$PROJECT_ROOT/workflow.db}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
COMPRESS_BACKUPS="${COMPRESS_BACKUPS:-true}"

# 创建备份目录
create_backup_dir() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_info "创建备份目录: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi
}

# 检查数据库文件
check_database() {
    if [[ ! -f "$DATABASE_PATH" ]]; then
        log_error "数据库文件不存在: $DATABASE_PATH"
        exit 1
    fi
    
    # 检查数据库完整性
    if command -v sqlite3 &> /dev/null; then
        log_info "检查数据库完整性..."
        if ! sqlite3 "$DATABASE_PATH" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_error "数据库完整性检查失败"
            exit 1
        fi
        log_info "数据库完整性检查通过"
    fi
}

# 执行备份
perform_backup() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_filename="workflow_${timestamp}.db"
    local backup_path="$BACKUP_DIR/$backup_filename"
    
    log_info "开始备份数据库..."
    log_info "源文件: $DATABASE_PATH"
    log_info "备份文件: $backup_path"
    
    # 如果数据库正在使用，使用SQLite的备份命令
    if command -v sqlite3 &> /dev/null; then
        log_info "使用SQLite备份命令..."
        sqlite3 "$DATABASE_PATH" ".backup '$backup_path'"
    else
        log_info "使用文件复制..."
        cp "$DATABASE_PATH" "$backup_path"
    fi
    
    # 验证备份文件
    if [[ ! -f "$backup_path" ]]; then
        log_error "备份失败：备份文件不存在"
        exit 1
    fi
    
    # 检查备份文件大小
    local original_size=$(stat -f%z "$DATABASE_PATH" 2>/dev/null || stat -c%s "$DATABASE_PATH")
    local backup_size=$(stat -f%z "$backup_path" 2>/dev/null || stat -c%s "$backup_path")
    
    if [[ $backup_size -eq 0 ]]; then
        log_error "备份失败：备份文件为空"
        rm -f "$backup_path"
        exit 1
    fi
    
    log_info "备份完成"
    log_info "原文件大小: $(numfmt --to=iec $original_size)"
    log_info "备份文件大小: $(numfmt --to=iec $backup_size)"
    
    # 压缩备份文件
    if [[ "$COMPRESS_BACKUPS" == "true" ]]; then
        compress_backup "$backup_path"
    fi
    
    echo "$backup_path"
}

# 压缩备份文件
compress_backup() {
    local backup_path="$1"
    local compressed_path="${backup_path}.gz"
    
    log_info "压缩备份文件..."
    if gzip "$backup_path"; then
        log_info "压缩完成: $(basename "$compressed_path")"
        
        # 显示压缩比
        local original_size=$(stat -f%z "$compressed_path" 2>/dev/null || stat -c%s "$compressed_path")
        local decompressed_size=$(gzip -l "$compressed_path" | tail -1 | awk '{print $2}')
        local compression_ratio=$(echo "scale=1; ($decompressed_size - $original_size) * 100 / $decompressed_size" | bc 2>/dev/null || echo "N/A")
        
        if [[ "$compression_ratio" != "N/A" ]]; then
            log_info "压缩比: ${compression_ratio}%"
        fi
    else
        log_warn "压缩失败，保留原备份文件"
    fi
}

# 清理旧备份
cleanup_old_backups() {
    log_info "清理 $RETENTION_DAYS 天前的备份文件..."
    
    local deleted_count=0
    
    # 删除旧的备份文件
    if command -v find &> /dev/null; then
        # 使用find命令 (支持大多数系统)
        while IFS= read -r -d '' file; do
            log_info "删除旧备份: $(basename "$file")"
            rm -f "$file"
            ((deleted_count++))
        done < <(find "$BACKUP_DIR" -name "workflow_*.db*" -mtime +$RETENTION_DAYS -print0 2>/dev/null)
    else
        # 备用方法：使用ls和日期比较
        for file in "$BACKUP_DIR"/workflow_*.db*; do
            if [[ -f "$file" ]]; then
                local file_date=$(stat -f%m "$file" 2>/dev/null || stat -c%Y "$file")
                local cutoff_date=$(date -d "$RETENTION_DAYS days ago" +%s 2>/dev/null || date -j -v-${RETENTION_DAYS}d +%s)
                
                if [[ $file_date -lt $cutoff_date ]]; then
                    log_info "删除旧备份: $(basename "$file")"
                    rm -f "$file"
                    ((deleted_count++))
                fi
            fi
        done
    fi
    
    if [[ $deleted_count -gt 0 ]]; then
        log_info "已删除 $deleted_count 个旧备份文件"
    else
        log_info "没有需要删除的旧备份文件"
    fi
}

# 列出备份文件
list_backups() {
    log_info "备份文件列表:"
    
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_warn "备份目录不存在: $BACKUP_DIR"
        return
    fi
    
    local backup_count=0
    local total_size=0
    
    for file in "$BACKUP_DIR"/workflow_*.db*; do
        if [[ -f "$file" ]]; then
            local file_size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file")
            local file_date=$(date -r "$file" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -d "@$(stat -c%Y "$file")" '+%Y-%m-%d %H:%M:%S')
            
            printf "  %-30s %10s %s\n" "$(basename "$file")" "$(numfmt --to=iec $file_size)" "$file_date"
            
            ((backup_count++))
            ((total_size += file_size))
        fi
    done
    
    if [[ $backup_count -eq 0 ]]; then
        log_info "没有找到备份文件"
    else
        log_info "总计: $backup_count 个备份文件，占用空间: $(numfmt --to=iec $total_size)"
    fi
}

# 恢复备份
restore_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        log_error "请指定备份文件"
        echo "用法: $0 restore <backup_file>"
        echo "示例: $0 restore workflow_20240101_120000.db"
        list_backups
        exit 1
    fi
    
    # 检查备份文件路径
    if [[ ! -f "$backup_file" ]] && [[ -f "$BACKUP_DIR/$backup_file" ]]; then
        backup_file="$BACKUP_DIR/$backup_file"
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi
    
    # 检查是否为压缩文件
    if [[ "$backup_file" =~ \.gz$ ]]; then
        log_info "检测到压缩文件，正在解压..."
        local temp_file=$(mktemp)
        if gunzip -c "$backup_file" > "$temp_file"; then
            backup_file="$temp_file"
        else
            log_error "解压失败"
            rm -f "$temp_file"
            exit 1
        fi
    fi
    
    # 备份当前数据库
    if [[ -f "$DATABASE_PATH" ]]; then
        local current_backup="${DATABASE_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "备份当前数据库到: $current_backup"
        cp "$DATABASE_PATH" "$current_backup"
    fi
    
    # 恢复数据库
    log_info "恢复数据库从: $backup_file"
    log_info "目标位置: $DATABASE_PATH"
    
    cp "$backup_file" "$DATABASE_PATH"
    
    # 验证恢复的数据库
    if command -v sqlite3 &> /dev/null; then
        if sqlite3 "$DATABASE_PATH" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_info "数据库恢复成功并通过完整性检查"
        else
            log_error "恢复的数据库完整性检查失败"
            exit 1
        fi
    fi
    
    # 清理临时文件
    if [[ -f "$temp_file" ]]; then
        rm -f "$temp_file"
    fi
    
    log_info "数据库恢复完成"
}

# 验证备份
verify_backup() {
    local backup_file="$1"
    
    if [[ -z "$backup_file" ]]; then
        log_error "请指定备份文件"
        exit 1
    fi
    
    if [[ ! -f "$backup_file" ]] && [[ -f "$BACKUP_DIR/$backup_file" ]]; then
        backup_file="$BACKUP_DIR/$backup_file"
    fi
    
    if [[ ! -f "$backup_file" ]]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi
    
    log_info "验证备份文件: $backup_file"
    
    # 处理压缩文件
    local temp_file=""
    if [[ "$backup_file" =~ \.gz$ ]]; then
        log_info "解压缩验证..."
        temp_file=$(mktemp)
        if ! gunzip -c "$backup_file" > "$temp_file"; then
            log_error "解压失败"
            rm -f "$temp_file"
            exit 1
        fi
        backup_file="$temp_file"
    fi
    
    # 验证SQLite数据库
    if command -v sqlite3 &> /dev/null; then
        if sqlite3 "$backup_file" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_info "备份文件验证通过"
        else
            log_error "备份文件验证失败"
            [[ -n "$temp_file" ]] && rm -f "$temp_file"
            exit 1
        fi
        
        # 显示备份信息
        local table_count=$(sqlite3 "$backup_file" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
        log_info "数据表数量: $table_count"
        
        # 显示主要表的记录数
        local tables=("users" "workflows" "nodes" "tasks" "workflow_instances")
        for table in "${tables[@]}"; do
            local count=$(sqlite3 "$backup_file" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "N/A")
            if [[ "$count" != "N/A" ]]; then
                log_info "$table 表记录数: $count"
            fi
        done
    else
        log_warn "未安装sqlite3，跳过完整性检查"
    fi
    
    # 清理临时文件
    [[ -n "$temp_file" ]] && rm -f "$temp_file"
    
    log_info "备份验证完成"
}

# 显示使用帮助
show_help() {
    echo "工作流应用数据库备份管理脚本"
    echo
    echo "用法: $0 [命令] [选项]"
    echo
    echo "命令:"
    echo "  backup      执行数据库备份 (默认)"
    echo "  list        列出所有备份文件"
    echo "  restore     恢复指定的备份文件"
    echo "  verify      验证备份文件完整性"
    echo "  cleanup     清理过期的备份文件"
    echo "  help        显示此帮助信息"
    echo
    echo "示例:"
    echo "  $0                                    # 执行备份"
    echo "  $0 backup                             # 执行备份"
    echo "  $0 list                               # 列出备份"
    echo "  $0 restore workflow_20240101_120000.db  # 恢复备份"
    echo "  $0 verify workflow_20240101_120000.db   # 验证备份"
    echo "  $0 cleanup                            # 清理过期备份"
    echo
    echo "环境变量:"
    echo "  BACKUP_DIR          备份目录路径 (默认: $PROJECT_ROOT/backups)"
    echo "  DATABASE_PATH       数据库文件路径 (默认: $PROJECT_ROOT/workflow.db)"
    echo "  RETENTION_DAYS      备份保留天数 (默认: 7)"
    echo "  COMPRESS_BACKUPS    是否压缩备份 (默认: true)"
}

# 主函数
main() {
    local command=${1:-backup}
    
    case $command in
        backup)
            create_backup_dir
            check_database
            backup_file=$(perform_backup)
            cleanup_old_backups
            log_info "备份操作完成"
            ;;
        list)
            list_backups
            ;;
        restore)
            restore_backup "$2"
            ;;
        verify)
            verify_backup "$2"
            ;;
        cleanup)
            cleanup_old_backups
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi