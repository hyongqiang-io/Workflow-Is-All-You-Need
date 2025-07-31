-- PostgreSQL数据库设置脚本
-- 在PostgreSQL中以超级用户身份运行此脚本

-- 创建用户
CREATE USER chenshuchen WITH PASSWORD 'your_password_here';

-- 创建数据库
CREATE DATABASE workflow_db OWNER chenshuchen;

-- 授予权限
GRANT ALL PRIVILEGES ON DATABASE workflow_db TO chenshuchen;

-- 连接到workflow_db数据库后运行
\c workflow_db

-- 授予schema权限
GRANT ALL ON SCHEMA public TO chenshuchen;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO chenshuchen;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO chenshuchen;

-- 设置默认权限
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chenshuchen;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chenshuchen;