#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor

def connect_to_database():
    """连接到PostgreSQL数据库"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='workflow_db',
            user='postgres',
            password='postgresql'
        )
        return conn
    except psycopg2.Error as e:
        print(f"数据库连接错误: {e}")
        return None

def execute_query(conn, query, description):
    """执行SQL查询并返回结果"""
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        
        print(f"\n{'='*60}")
        print(f"{description}")
        print(f"{'='*60}")
        
        if results:
            # 转换为DataFrame以便更好地显示
            df = pd.DataFrame([dict(record) for record in results])
            print(df.to_string(index=False))
            print(f"\n总记录数: {len(results)}")
        else:
            print("没有找到任何记录")
        
        return results
    
    except psycopg2.Error as e:
        print(f"查询执行错误: {e}")
        return None

def main():
    workflow_id = '64721581-26e2-464a-b5b9-f700da429908'
    
    # 连接数据库
    conn = connect_to_database()
    if not conn:
        return
    
    try:
        # 查询1: 检查工作流创建者信息
        query1 = """
        SELECT w.*, u.username as creator_name 
        FROM workflow w
        LEFT JOIN "user" u ON u.user_id = w.creator_id
        WHERE w.workflow_base_id = %s 
        AND w.is_current_version = TRUE;
        """
        
        print(f"查询工作流ID: {workflow_id}")
        results1 = execute_query(conn, cursor.mogrify(query1, (workflow_id,)).decode('utf-8'), 
                                "1. 工作流创建者信息")
        
        # 查询2: 检查所有活跃用户
        query2 = """
        SELECT user_id, username, email, is_deleted 
        FROM "user" 
        WHERE is_deleted = FALSE 
        ORDER BY created_at DESC;
        """
        
        results2 = execute_query(conn, query2, "2. 系统中所有活跃用户")
        
        # 查询3: 检查工作流连接记录
        query3 = """
        SELECT * FROM node_connection 
        WHERE workflow_base_id = %s;
        """
        
        results3 = execute_query(conn, cursor.mogrify(query3, (workflow_id,)).decode('utf-8'),
                                "3. 工作流连接记录")
        
        # 总结分析
        print(f"\n{'='*60}")
        print("分析总结")
        print(f"{'='*60}")
        
        if results1:
            workflow_info = results1[0]
            print(f"工作流基础ID: {workflow_info.get('workflow_base_id')}")
            print(f"工作流名称: {workflow_info.get('workflow_name', 'N/A')}")
            print(f"创建者ID: {workflow_info.get('creator_id')}")
            print(f"创建者用户名: {workflow_info.get('creator_name', '未找到用户名')}")
            print(f"是否为当前版本: {workflow_info.get('is_current_version')}")
            print(f"创建时间: {workflow_info.get('created_at')}")
        else:
            print("⚠️  未找到指定的工作流记录")
        
        if results2:
            print(f"\n系统中活跃用户总数: {len(results2)}")
            if results1 and results1[0].get('creator_id'):
                creator_id = results1[0]['creator_id']
                creator_exists = any(user['user_id'] == creator_id for user in results2)
                if creator_exists:
                    print(f"✅ 工作流创建者 ({creator_id}) 在活跃用户中")
                else:
                    print(f"❌ 工作流创建者 ({creator_id}) 不在活跃用户中")
        
        if results3:
            print(f"\n工作流连接记录数: {len(results3)}")
        else:
            print(f"\n⚠️  该工作流没有任何连接记录")
    
    except Exception as e:
        print(f"执行过程中发生错误: {e}")
    
    finally:
        conn.close()
        print(f"\n数据库连接已关闭")

if __name__ == "__main__":
    main()