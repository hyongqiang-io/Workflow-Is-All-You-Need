#!/usr/bin/env python3
"""
展示真实AI生成的详细工作流
Display detailed AI-generated workflow
"""

import asyncio
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.services.ai_workflow_generator import AIWorkflowGeneratorService

async def test_detailed_ai_generation():
    """测试详细的AI生成"""
    print("=== 测试真实AI生成的详细工作流 ===")
    
    service = AIWorkflowGeneratorService()
    
    # 测试不同类型的任务
    test_cases = [
        "数据分析一下期末学生的成绩",
        "开发一个在线教育平台",
        "制作公司年度总结报告",
        "组织团队建设活动"
    ]
    
    for i, task_description in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"测试用例 {i}: {task_description}")
        print('='*60)
        
        try:
            user_id = uuid.uuid4()
            workflow_export = await service.generate_workflow_from_description(
                task_description=task_description,
                user_id=user_id
            )
            
            print(f"✅ 生成成功!")
            print(f"工作流名称: {workflow_export.name}")
            print(f"工作流描述: {workflow_export.description}")
            print(f"节点总数: {len(workflow_export.nodes)}")
            print(f"连接总数: {len(workflow_export.connections)}")
            
            # 显示所有节点的详细信息
            print(f"\n📋 节点详情:")
            for j, node in enumerate(workflow_export.nodes, 1):
                print(f"{j}. 【{node.type.upper()}】{node.name}")
                print(f"   位置: ({node.position_x}, {node.position_y})")
                print(f"   描述: {node.task_description}")
                print()
            
            # 显示连接关系
            print(f"🔗 连接关系:")
            for j, conn in enumerate(workflow_export.connections, 1):
                print(f"{j}. {conn.from_node_name} → {conn.to_node_name}")
                print(f"   类型: {conn.connection_type}")
                if conn.connection_path:
                    start_pos = conn.connection_path[0]
                    end_pos = conn.connection_path[-1]
                    print(f"   路径: ({start_pos['x']},{start_pos['y']}) → ({end_pos['x']},{end_pos['y']})")
                print()
            
            # 检查生成方式
            metadata = workflow_export.metadata
            if metadata:
                generated_by = metadata.get('generated_by', 'Unknown')
                print(f"🤖 生成方式: {generated_by}")
                if generated_by == 'AI':
                    print("✅ 使用了真实的DeepSeek AI生成")
                elif generated_by == 'AI_Mock':
                    print("⚠️ 使用了Mock生成（网络问题）")
                
        except Exception as e:
            print(f"❌ 生成失败: {e}")
            
        print("\n" + "="*60)
        
        # 等待一下避免API频率限制
        if i < len(test_cases):
            print("等待3秒避免API限制...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(test_detailed_ai_generation())