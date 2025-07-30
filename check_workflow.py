#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import psycopg2
import sys
from psycopg2.extras import DictCursor

def connect_database():
    """连接PostgreSQL数据库"""
    try:
        connection = psycopg2.connect(
            host="localhost",
            port=5432,
            database="workflow_db",
            user="postgres",
            password="postgresql"
        )
        print("数据库连接成功!")
        return connection
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def execute_query(connection, query, description):
    """执行SQL查询并返回结果"""
    try:
        cursor = connection.cursor(cursor_factory=DictCursor)
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"\n{'='*60}")
        print(f"{description}")
        print(f"{'='*60}")
        
        if results:
            # 打印列名
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                print(f"列名: {' | '.join(columns)}")
                print("-" * 60)
                
                # 打印数据
                for row in results:
                    row_data = []
                    for col in columns:
                        value = row[col]
                        if value is None:
                            value = "NULL"
                        row_data.append(str(value))
                    print(" | ".join(row_data))
            print(f"\n总计: {len(results)} 条记录")
        else:
            print("未找到数据")
            
        cursor.close()
        return results
        
    except Exception as e:
        print(f"查询执行失败: {e}")
        return None

def main():
    # 连接数据库
    conn = connect_database()
    if not conn:
        sys.exit(1)
    
    try:
        # 查询1: 检查工作流创建者
        workflow_query = """
        SELECT w.workflow_base_id, w.name, w.creator_id, u.username as creator_name 
        FROM workflow w
        LEFT JOIN "user" u ON u.user_id = w.creator_id
        WHERE w.workflow_base_id = '64721581-26e2-464a-b5b9-f700da429908' 
        AND w.is_current_version = TRUE;
        """
        
        workflow_results = execute_query(
            conn, 
            workflow_query, 
            "查询工作流 '64721581-26e2-464a-b5b9-f700da429908' 的创建者"
        )
        
        # 查询2: 检查所有用户
        users_query = """
        SELECT user_id, username, email, is_deleted 
        FROM "user" 
        ORDER BY created_at DESC;
        """
        
        users_results = execute_query(
            conn, 
            users_query, 
            "检查系统中的所有用户"
        )
        
        # 查询3: 先检查node_connection表结构
        table_check_query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'node_connection' 
        ORDER BY ordinal_position;
        """
        
        execute_query(
            conn, 
            table_check_query, 
            "检查node_connection表结构"
        )
        
        # 查询4: 检查节点连接 - 先尝试不同的列名
        connections_query = """
        SELECT * FROM node_connection 
        WHERE workflow_id = '64721581-26e2-464a-b5b9-f700da429908' 
        LIMIT 10;
        """
        
        connections_results = execute_query(
            conn, 
            connections_query, 
            "检查工作流的节点连接"
        )
        
        # 分析结果
        print(f"\n{'='*60}")
        print("分析结果")
        print(f"{'='*60}")
        
        if workflow_results:
            workflow = workflow_results[0]
            creator_id = workflow['creator_id']
            creator_name = workflow['creator_name']
            
            print(f"工作流名称: {workflow['name']}")
            print(f"创建者ID: {creator_id}")
            print(f"创建者用户名: {creator_name}")
            
            if creator_name is None:
                print("WARNING: 工作流的创建者在用户表中不存在!")
                if users_results:
                    print("但是系统中存在其他用户:")
                    for user in users_results[:5]:  # 只显示前5个用户
                        status = "已删除" if user['is_deleted'] else "正常"
                        print(f"  - {user['username']} (ID: {user['user_id']}, 状态: {status})")
            else:
                print("SUCCESS: 工作流创建者存在且有效")
        else:
            print("WARNING: 未找到指定的工作流")
            
        if connections_results:
            print(f"SUCCESS: 找到 {len(connections_results)} 个节点连接")
        else:
            print("WARNING: 该工作流没有节点连接或表结构不匹配")
            
    finally:
        conn.close()
        print("\n数据库连接已关闭")

if __name__ == "__main__":
    main()