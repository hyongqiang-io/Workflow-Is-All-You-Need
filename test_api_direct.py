#!/usr/bin/env python3
"""
直接测试API调用
Direct API Testing
"""

import requests
import json
from loguru import logger

def test_api_direct():
    """直接测试API调用"""
    
    # 测试获取工作流节点
    workflow_id = "64721581-26e2-464a-b5b9-f700da429908"
    api_url = f"http://localhost:8001/api/nodes/workflow/{workflow_id}"
    
    logger.info(f"🌐 测试节点API: {api_url}")
    
    try:
        response = requests.get(api_url, timeout=10)
        logger.info(f"📨 API响应状态: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            logger.info(f"✅ API调用成功")
            
            # 检查节点数据中是否包含processor_id
            if response_data.get('success') and response_data.get('data') and response_data['data'].get('nodes'):
                nodes = response_data['data']['nodes']
                logger.info(f"📋 找到 {len(nodes)} 个节点:")
                
                for node in nodes:
                    processor_info = ""
                    if 'processor_id' in node and node['processor_id']:
                        processor_info = f"✅ processor_id: {node['processor_id']}"
                    else:
                        processor_info = "❌ 无processor_id"
                    
                    logger.info(f"   - {node.get('name', '未命名')} ({node.get('type', '未知类型')}) - {processor_info}")
                    
                    # 显示完整的节点数据
                    logger.info(f"   完整数据: {json.dumps(node, indent=4)}")
            else:
                logger.warning("⚠️  API响应格式异常")
                logger.info(f"完整响应: {json.dumps(response_data, indent=2)}")
        else:
            logger.error(f"❌ API调用失败: {response.status_code}")
            logger.error(f"响应内容: {response.text}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 网络请求失败: {e}")
    
    # 测试连接API
    logger.info(f"\n🌐 测试连接API")
    connections_url = f"http://localhost:8001/api/nodes/connections/workflow/{workflow_id}"
    
    try:
        response = requests.get(connections_url, timeout=10)
        logger.info(f"📨 连接API响应状态: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            logger.info(f"✅ 连接API调用成功: {json.dumps(response_data, indent=2)}")
        else:
            logger.error(f"❌ 连接API调用失败: {response.status_code}")
            logger.error(f"响应内容: {response.text}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 连接API网络请求失败: {e}")

if __name__ == "__main__":
    test_api_direct()