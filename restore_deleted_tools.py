#!/usr/bin/env python3
"""
恢复被软删除的MCP工具
"""

import sys
import asyncio
from pathlib import Path

# 添加backend路径
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

async def restore_deleted_tools():
    print("🔧 恢复被软删除的MCP工具...")
    
    try:
        from backend.utils.database import db_manager, initialize_database
        
        # 初始化数据库
        await initialize_database()
        
        print("✅ 数据库连接成功")
        
        # 查找被软删除的工具
        deleted_tools = await db_manager.fetch_all("""
            SELECT tool_id, tool_name, server_name, user_id
            FROM mcp_tool_registry 
            WHERE is_deleted = 1 AND server_name = 'weather'
            ORDER BY tool_name
        """)
        
        if not deleted_tools:
            print("❌ 没有找到被删除的weather工具")
            return
        
        print(f"📋 找到 {len(deleted_tools)} 个被删除的工具:")
        for tool in deleted_tools:
            print(f"   - {tool['tool_name']} @ {tool['server_name']} (ID: {tool['tool_id']})")
        
        # 恢复工具
        print(f"\n🔄 开始恢复工具...")
        restored_count = 0
        
        for tool in deleted_tools:
            try:
                result = await db_manager.execute("""
                    UPDATE mcp_tool_registry 
                    SET is_deleted = 0, updated_at = NOW()
                    WHERE tool_id = %s
                """, tool['tool_id'])
                
                if result == "UPDATE 1":
                    print(f"   ✅ 恢复成功: {tool['tool_name']}")
                    restored_count += 1
                else:
                    print(f"   ❌ 恢复失败: {tool['tool_name']} (无更新)")
                    
            except Exception as e:
                print(f"   ❌ 恢复失败: {tool['tool_name']} - {e}")
        
        print(f"\n🎯 恢复完成: {restored_count}/{len(deleted_tools)} 个工具")
        
        # 验证恢复结果
        print(f"\n📋 验证恢复结果:")
        active_tools = await db_manager.fetch_all("""
            SELECT tool_name, server_name, is_tool_active, is_server_active, server_status
            FROM mcp_tool_registry 
            WHERE is_deleted = 0 AND server_name = 'weather'
            ORDER BY tool_name
        """)
        
        if active_tools:
            print(f"   现在有 {len(active_tools)} 个活跃的weather工具:")
            for tool in active_tools:
                tool_status = "✅ 激活" if tool['is_tool_active'] else "❌ 禁用"
                server_status = "✅ 激活" if tool['is_server_active'] else "❌ 禁用"
                print(f"   - {tool['tool_name']}: 工具{tool_status} | 服务器{server_status} ({tool['server_status']})")
        else:
            print("   ❌ 恢复后仍然没有活跃的weather工具")
        
        print(f"\n💡 提示: 现在UI应该能显示这些工具了")
        
    except Exception as e:
        print(f"\n❌ 恢复失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(restore_deleted_tools())