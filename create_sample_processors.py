#!/usr/bin/env python3
"""
创建示例处理器数据
"""

import asyncio
import sys
from pathlib import Path

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from workflow_framework.utils.database import db_manager

async def create_sample_processors():
    """创建示例处理器数据"""
    try:
        # 清空现有处理器数据
        await db_manager.execute("DELETE FROM processor")
        print("已清空现有处理器数据")
        
        # 插入示例处理器
        processors = [
            {
                'name': 'GPT-4处理器',
                'type': 'agent',
                'agent_id': None,
                'user_id': None
            },
            {
                'name': 'Claude处理器', 
                'type': 'agent',
                'agent_id': None,
                'user_id': None
            },
            {
                'name': '人工审核处理器',
                'type': 'human',
                'agent_id': None,
                'user_id': None
            },
            {
                'name': '数据清洗处理器',
                'type': 'agent',
                'agent_id': None,
                'user_id': None
            },
            {
                'name': '文档生成处理器',
                'type': 'agent', 
                'agent_id': None,
                'user_id': None
            }
        ]
        
        for processor in processors:
            await db_manager.execute("""
                INSERT INTO processor (name, type, user_id, agent_id)
                VALUES ($1, $2, $3, $4)
            """, processor['name'], processor['type'], processor['user_id'], processor['agent_id'])
        
        print(f"成功创建 {len(processors)} 个示例处理器")
        
        # 验证创建结果
        result = await db_manager.fetch_all("SELECT * FROM processor")
        print("创建的处理器:")
        for proc in result:
            print(f"  - {proc['name']} ({proc['type']})")
            
    except Exception as e:
        print(f"创建处理器失败: {e}")

if __name__ == "__main__":
    asyncio.run(create_sample_processors())