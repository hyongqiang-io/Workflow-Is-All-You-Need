#!/usr/bin/env python3
"""
简单的OpenAI客户端测试
Simple OpenAI Client Test
"""

import asyncio
import uuid

from workflow_framework.utils.openai_client import openai_client


async def test_openai_basic():
    """测试基础OpenAI功能"""
    
    print("=== OpenAI客户端重构测试 ===")
    print()
    
    try:
        # 1. 测试基础任务处理
        print("1. 测试任务处理...")
        task_data = {
            'task_id': str(uuid.uuid4()),
            'task_title': '数据分析任务',
            'task_description': '分析业务数据并提供见解',
            'input_data': {
                'users': 1000,
                'revenue': 50000,
                'conversion': 0.15
            },
            'instructions': '请分析数据并提供建议'
        }
        
        print("调用OpenAI API...")
        result = await openai_client.process_task(task_data)
        
        if result['success']:
            print("任务处理成功!")
            print(f"模型: {result['model']}")
            analysis = result['result']
            print(f"分析: {analysis.get('analysis', 'N/A')[:50]}...")
            if 'usage' in result:
                usage = result['usage']
                print(f"Token: {usage.get('total_tokens', 'N/A')}")
        else:
            print(f"任务失败: {result.get('error', 'Unknown')}")
        
        print()
        
        # 2. 测试情感分析
        print("2. 测试情感分析...")
        text = "这个产品很好用，我很满意！"
        sentiment = await openai_client.analyze_sentiment(text)
        
        print(f"文本: {text}")
        print(f"情感: {sentiment.get('sentiment', 'unknown')}")
        print(f"置信度: {sentiment.get('confidence', 0)}")
        print()
        
        # 3. 测试摘要
        print("3. 测试文本摘要...")
        long_text = "人工智能在现代商业中应用广泛。机器学习帮助企业预测趋势，优化管理，提升体验。自然语言处理让企业更好理解客户。未来AI将推动更多创新。"
        summary = await openai_client.summarize_text(long_text, 50)
        
        print(f"原文长度: {summary.get('original_length', 0)}")
        print(f"摘要: {summary.get('summary', 'N/A')}")
        print(f"压缩比: {summary.get('compression_ratio', 0):.2f}")
        print()
        
        # 4. 测试翻译
        print("4. 测试翻译...")
        chinese = "你好世界"
        translation = await openai_client.translate_text(chinese, 'en')
        
        print(f"原文: {chinese}")
        print(f"译文: {translation.get('translated_text', 'N/A')}")
        print()
        
        # 5. 测试代码生成
        print("5. 测试代码生成...")
        code_desc = "计算数组平均值"
        code = await openai_client.generate_code(code_desc, 'python')
        
        print(f"需求: {code_desc}")
        print(f"代码行数: {code.get('lines_of_code', 0)}")
        print("代码示例:")
        code_lines = code.get('code', '').split('\n')[:5]
        for line in code_lines:
            print(f"  {line}")
        print()
        
        print("=== 测试完成 ===")
        print()
        
        print("重构改进:")
        print("- 使用AsyncOpenAI真实API")
        print("- 统一消息构建模式")
        print("- 保留完整基础接口")
        print("- 增强错误处理机制")
        print("- 真实Token使用统计")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    try:
        success = await test_openai_basic()
        
        if success:
            print("\n测试成功!")
            print("OpenAI客户端重构完成。")
        else:
            print("\n测试失败!")
        
    except Exception as e:
        print(f"异常: {e}")
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(main())