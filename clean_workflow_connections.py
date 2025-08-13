#!/usr/bin/env python3
"""
清理多余的连接，确保1->2->3的顺序
Clean up extra connections to ensure 1->2->3 sequence
"""

import asyncio
import sys
from pathlib import Path
from loguru import logger

# 添加父目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

async def clean_workflow_connections():
    """清理工作流的多余连接"""
    try:
        logger.info("🧹 清理工作流 '2' 的多余连接...")
        
        from backend.utils.database import initialize_database, db_manager
        
        await initialize_database()
        
        # 查询工作流 "2" 的信息
        workflow_info = await db_manager.fetch_one("""
            SELECT 
                workflow_id,
                workflow_base_id,
                name,
                creator_id
            FROM workflow 
            WHERE name = '2'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        if not workflow_info:
            print("❌ 没有找到工作流 '2'")
            return
        
        workflow_id = workflow_info['workflow_id']
        print(f"📋 清理工作流: {workflow_info['name']} ({workflow_info['workflow_base_id']})")
        
        # 查询当前所有连接
        current_connections = await db_manager.fetch_all("""
            SELECT 
                nc.from_node_id,
                nc.to_node_id,
                fn.name as from_name,
                tn.name as to_name,
                nc.connection_type
            FROM node_connection nc
            JOIN node fn ON nc.from_node_id = fn.node_id
            JOIN node tn ON nc.to_node_id = tn.node_id
            WHERE nc.workflow_id = %s
            ORDER BY fn.name, tn.name
        """, workflow_id)
        
        print(f"\n🔍 当前连接 ({len(current_connections)} 个):")
        for conn in current_connections:
            print(f"  - {conn['from_name']} -> {conn['to_name']} ({conn['connection_type']})")
        
        # 找到需要删除的1->3连接
        direct_connection = None
        for conn in current_connections:
            if conn['from_name'] == '1' and conn['to_name'] == '3':
                direct_connection = conn
                break
        
        if direct_connection:
            print(f"\n🗑️  删除多余的直连: 1 -> 3")
            
            # 删除1->3连接
            await db_manager.execute("""
                DELETE FROM node_connection 
                WHERE from_node_id = %s 
                AND to_node_id = %s 
                AND workflow_id = %s
            """, direct_connection['from_node_id'], direct_connection['to_node_id'], workflow_id)
            
            print("✅ 删除成功!")
        else:
            print("✅ 没有找到需要删除的1->3直连")
        
        # 验证清理后的连接
        final_connections = await db_manager.fetch_all("""
            SELECT 
                fn.name as from_name,
                tn.name as to_name,
                nc.connection_type
            FROM node_connection nc
            JOIN node fn ON nc.from_node_id = fn.node_id
            JOIN node tn ON nc.to_node_id = tn.node_id
            WHERE nc.workflow_id = %s
            ORDER BY fn.name, tn.name
        """, workflow_id)
        
        print(f"\n✅ 清理后的连接 ({len(final_connections)} 个):")
        for conn in final_connections:
            print(f"  - {conn['from_name']} -> {conn['to_name']} ({conn['connection_type']})")
        
        # 验证是否符合要求的1->2->3顺序
        has_1_to_2 = any(c['from_name'] == '1' and c['to_name'] == '2' for c in final_connections)
        has_2_to_3 = any(c['from_name'] == '2' and c['to_name'] == '3' for c in final_connections)
        has_1_to_3 = any(c['from_name'] == '1' and c['to_name'] == '3' for c in final_connections)
        
        print(f"\n📊 连接验证:")
        print(f"  1 -> 2: {'✅' if has_1_to_2 else '❌'}")
        print(f"  2 -> 3: {'✅' if has_2_to_3 else '❌'}")
        print(f"  1 -> 3 (不需要): {'❌ 仍存在' if has_1_to_3 else '✅ 已清理'}")
        
        if has_1_to_2 and has_2_to_3 and not has_1_to_3:
            print(f"\n🎉 完美! 工作流现在只有期望的顺序连接: 1 -> 2 -> 3")
        else:
            print(f"\n⚠️  连接结构还需要调整")
        
    except Exception as e:
        logger.error(f"清理失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("=" * 80)
    print("🧹 清理工作流的多余连接")
    print("=" * 80)
    
    await clean_workflow_connections()

if __name__ == "__main__":
    asyncio.run(main())