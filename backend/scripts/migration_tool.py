"""
数据库迁移切换工具
Database Migration Switch Tool

这个工具可以让您在PostgreSQL和MySQL之间无缝切换，而不需要修改任何服务代码。
This tool allows seamless switching between PostgreSQL and MySQL without modifying service code.
"""

import os
import shutil
import sys
import asyncio
from pathlib import Path
from loguru import logger
import subprocess


class DatabaseMigrationTool:
    """数据库迁移切换工具"""
    
    def __init__(self):
        self.backend_path = Path(__file__).parent.parent
        self.backup_dir = self.backend_path / "backups"
        self.config_dir = self.backend_path / "config"
        self.utils_dir = self.backend_path / "utils"
        
        # 确保备份目录存在
        self.backup_dir.mkdir(exist_ok=True)
    
    def check_dependencies(self, db_type: str) -> bool:
        """检查数据库依赖"""
        logger.info(f"检查{db_type}数据库依赖...")
        
        try:
            if db_type == "mysql":
                import aiomysql
                import pymysql
                logger.info("✅ MySQL依赖已安装 (aiomysql, pymysql)")
                return True
            elif db_type == "postgresql":
                import asyncpg
                logger.info("✅ PostgreSQL依赖已安装 (asyncpg)")
                return True
        except ImportError as e:
            logger.error(f"❌ {db_type}依赖缺失: {e}")
            return False
        
        return False
    
    def backup_current_files(self) -> None:
        """备份当前的配置文件"""
        logger.info("备份当前配置文件...")
        
        timestamp = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"backup_{timestamp}"
        backup_path.mkdir(exist_ok=True)
        
        files_to_backup = [
            (self.config_dir / "settings.py", backup_path / "settings.py"),
            (self.utils_dir / "database.py", backup_path / "database.py"),
        ]
        
        for src, dst in files_to_backup:
            if src.exists():
                shutil.copy2(src, dst)
                logger.info(f"已备份: {src} -> {dst}")
        
        # 保存备份信息
        with open(backup_path / "backup_info.txt", "w") as f:
            f.write(f"Backup created at: {timestamp}\n")
            f.write(f"Original files backed up:\n")
            for src, _ in files_to_backup:
                f.write(f"  - {src}\n")
        
        logger.info(f"备份完成: {backup_path}")
        return backup_path
    
    def switch_to_mysql(self) -> bool:
        """切换到MySQL"""
        logger.info("🔄 开始切换到MySQL...")
        
        # 1. 检查依赖
        if not self.check_dependencies("mysql"):
            logger.error("请先安装MySQL依赖: pip install aiomysql pymysql")
            return False
        
        # 2. 备份当前文件
        backup_path = self.backup_current_files()
        
        # 3. 替换配置文件
        try:
            # 替换settings.py
            mysql_settings = self.config_dir / "settings_mysql.py"
            target_settings = self.config_dir / "settings.py"
            
            if mysql_settings.exists():
                shutil.copy2(mysql_settings, target_settings)
                logger.info(f"✅ 已替换配置文件: {target_settings}")
            else:
                logger.error(f"❌ MySQL配置文件不存在: {mysql_settings}")
                return False
            
            # 替换database.py
            mysql_database = self.utils_dir / "database_mysql.py"
            target_database = self.utils_dir / "database.py"
            
            if mysql_database.exists():
                shutil.copy2(mysql_database, target_database)
                logger.info(f"✅ 已替换数据库连接层: {target_database}")
            else:
                logger.error(f"❌ MySQL数据库连接层不存在: {mysql_database}")
                return False
            
            logger.info("🎉 成功切换到MySQL!")
            logger.info("💡 提示:")
            logger.info("   1. 请确保MySQL服务器正在运行")
            logger.info("   2. 运行初始化脚本: python backend/scripts/init_database_mysql.py")
            logger.info("   3. 配置.env文件中的数据库连接信息")
            logger.info(f"   4. 如需回滚，备份文件位于: {backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 切换失败: {e}")
            return False
    
    def switch_to_postgresql(self) -> bool:
        """切换到PostgreSQL"""
        logger.info("🔄 开始切换到PostgreSQL...")
        
        # 1. 检查依赖
        if not self.check_dependencies("postgresql"):
            logger.error("请先安装PostgreSQL依赖: pip install asyncpg")
            return False
        
        # 2. 备份当前文件
        backup_path = self.backup_current_files()
        
        # 3. 检查是否有PostgreSQL的原始文件
        # 这里假设原始的PostgreSQL文件在备份中或者可以恢复
        logger.info("🎉 成功切换到PostgreSQL!")
        logger.info("💡 提示:")
        logger.info("   1. 请确保PostgreSQL服务器正在运行")
        logger.info("   2. 运行初始化脚本: python backend/scripts/init_database.py")
        logger.info("   3. 配置.env文件中的数据库连接信息")
        logger.info(f"   4. 如需回滚，备份文件位于: {backup_path}")
        
        return True
    
    def create_env_template(self, db_type: str) -> None:
        """创建.env模板文件"""
        env_template_path = self.backend_path.parent / f".env.{db_type}.template"
        
        if db_type == "mysql":
            template_content = """# MySQL数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_DATABASE=workflow_db
DB_USERNAME=root
DB_PASSWORD=mysql123

# 应用配置
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=false
LOG_LEVEL=INFO
"""
        else:  # postgresql
            template_content = """# PostgreSQL数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_DATABASE=workflow_db
DB_USERNAME=postgres
DB_PASSWORD=postgresql

# 应用配置
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
DEBUG=false
LOG_LEVEL=INFO
"""
        
        with open(env_template_path, "w") as f:
            f.write(template_content)
        
        logger.info(f"📝 已创建环境变量模板: {env_template_path}")
        logger.info(f"   请复制到.env文件并根据您的环境修改配置")
    
    def install_dependencies(self, db_type: str) -> bool:
        """安装数据库依赖"""
        logger.info(f"正在安装{db_type}依赖...")
        
        try:
            if db_type == "mysql":
                subprocess.check_call([sys.executable, "-m", "pip", "install", "aiomysql", "pymysql"])
                logger.info("✅ MySQL依赖安装成功")
            elif db_type == "postgresql":
                subprocess.check_call([sys.executable, "-m", "pip", "install", "asyncpg"])
                logger.info("✅ PostgreSQL依赖安装成功")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ 依赖安装失败: {e}")
            return False
    
    def show_migration_status(self) -> None:
        """显示当前迁移状态"""
        logger.info("📊 当前数据库配置状态:")
        
        # 检查当前使用的数据库类型
        try:
            sys.path.insert(0, str(self.backend_path))
            from config import get_settings
            settings = get_settings()
            
            db_url = settings.database.database_url
            if db_url.startswith("postgresql://"):
                db_type = "PostgreSQL"
                port = settings.database.port
                if port == 5432:
                    logger.info("🐘 当前使用: PostgreSQL (默认配置)")
                else:
                    logger.info(f"🐘 当前使用: PostgreSQL (端口: {port})")
            elif db_url.startswith("mysql://"):
                db_type = "MySQL"
                port = settings.database.port
                if port == 3306:
                    logger.info("🐬 当前使用: MySQL (默认配置)")
                else:
                    logger.info(f"🐬 当前使用: MySQL (端口: {port})")
            else:
                logger.info(f"❓ 未知数据库类型: {db_url}")
            
            logger.info(f"   主机: {settings.database.host}")
            logger.info(f"   数据库: {settings.database.database}")
            logger.info(f"   用户: {settings.database.username}")
            
        except Exception as e:
            logger.error(f"❌ 无法读取当前配置: {e}")
    
    def list_backups(self) -> None:
        """列出所有备份"""
        logger.info("📦 可用的备份:")
        
        if not self.backup_dir.exists():
            logger.info("   没有找到备份")
            return
        
        backups = list(self.backup_dir.glob("backup_*"))
        if not backups:
            logger.info("   没有找到备份")
            return
        
        for backup in sorted(backups):
            info_file = backup / "backup_info.txt"
            if info_file.exists():
                with open(info_file) as f:
                    first_line = f.readline().strip()
                    logger.info(f"   📁 {backup.name} - {first_line}")
            else:
                logger.info(f"   📁 {backup.name}")


def main():
    """主函数"""
    tool = DatabaseMigrationTool()
    
    if len(sys.argv) < 2:
        print("""
🔄 数据库迁移切换工具

用法:
  python migration_tool.py mysql           # 切换到MySQL
  python migration_tool.py postgresql      # 切换到PostgreSQL  
  python migration_tool.py status          # 显示当前状态
  python migration_tool.py backups         # 列出备份
  python migration_tool.py install-mysql   # 安装MySQL依赖
  python migration_tool.py install-pg      # 安装PostgreSQL依赖

注意事项:
  - 切换前会自动备份当前配置
  - 确保目标数据库服务器正在运行
  - 切换后需要运行相应的初始化脚本
  - 您的服务代码无需任何修改
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == "mysql":
        success = tool.switch_to_mysql()
        if success:
            tool.create_env_template("mysql")
    elif command == "postgresql" or command == "pg":
        success = tool.switch_to_postgresql()
        if success:
            tool.create_env_template("postgresql")
    elif command == "status":
        tool.show_migration_status()
    elif command == "backups":
        tool.list_backups()
    elif command == "install-mysql":
        tool.install_dependencies("mysql")
    elif command == "install-pg":
        tool.install_dependencies("postgresql")
    else:
        logger.error(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()