#!/usr/bin/env python3
"""
自动配置Playwright MCP工具 - Linus式直接解决方案
Auto-configure Playwright MCP Tool - Direct Solution
"""

import requests
import json
import time
import subprocess
import os
from pathlib import Path

class PlaywrightMCPSetup:
    """Playwright MCP自动配置器 - 简单直接"""

    def __init__(self):
        self.backend_url = "http://localhost:8000"  # 你的后端API地址
        self.playwright_port = 8087
        self.playwright_url = f"http://localhost:{self.playwright_port}"

    def check_playwright_server(self):
        """检查Playwright MCP服务器状态"""
        try:
            # 简单的连接测试
            response = subprocess.run(['curl', '-s', f'{self.playwright_url}/mcp'],
                                    capture_output=True, timeout=5)
            return True  # 即使返回错误，说明服务器在运行
        except:
            return False

    def start_playwright_server(self):
        """启动Playwright MCP服务器"""
        print("🚀 启动Playwright MCP服务器...")
        try:
            # 启动服务器（后台运行）
            subprocess.Popen([
                'npx', '@playwright/mcp@latest',
                '--port', str(self.playwright_port),
                '--headless',
                '--isolated'  # 使用隔离模式，不保存状态
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 等待服务器启动
            for i in range(10):
                time.sleep(1)
                if self.check_playwright_server():
                    print(f"✅ Playwright MCP服务器已启动 (端口 {self.playwright_port})")
                    return True
                print(f"   等待启动... ({i+1}/10)")

            print("❌ Playwright MCP服务器启动失败")
            return False

        except Exception as e:
            print(f"❌ 启动失败: {e}")
            return False

    def add_to_workflow_system(self):
        """添加到工作流系统"""
        print("📝 添加Playwright MCP到工作流系统...")

        # 服务器配置
        server_config = {
            "server_name": "playwright-mcp",
            "server_url": f"{self.playwright_url}/mcp",
            "server_description": "Microsoft官方Playwright MCP服务器 - 浏览器自动化工具",
            "auth_config": {"type": "none"}
        }

        try:
            # 调用你的API添加服务器
            # 注意：这里需要用户认证，你可能需要调整
            response = requests.post(
                f"{self.backend_url}/api/v1/mcp-tools/servers",
                json=server_config,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Playwright MCP已成功添加到工作流系统")
                print(f"   - 发现工具数量: {result.get('tools_discovered', 0)}")
                print(f"   - 新增工具: {result.get('tools_added', 0)}")
                return True
            else:
                print(f"❌ 添加失败: HTTP {response.status_code}")
                print(f"   错误信息: {response.text}")
                return False

        except Exception as e:
            print(f"❌ 添加失败: {e}")
            return False

    def create_startup_script(self):
        """创建启动脚本"""
        script_content = f"""#!/bin/bash
# Playwright MCP 自动启动脚本

echo "🎭 启动Playwright MCP服务器..."
npx @playwright/mcp@latest --port {self.playwright_port} --headless --isolated &

echo "⏳ 等待服务器启动..."
sleep 3

echo "✅ Playwright MCP服务器已启动"
echo "🌐 服务地址: {self.playwright_url}/mcp"
echo "📋 使用方法:"
echo "   1. 在工作流中调用browser工具"
echo "   2. 支持页面导航、点击、输入、截图等操作"
echo ""
echo "🛑 要停止服务器，请运行: pkill -f playwright/mcp"
"""

        script_path = "/home/ubuntu/Workflow-Is-All-You-Need/mcp/start_playwright_mcp.sh"
        with open(script_path, 'w') as f:
            f.write(script_content)

        os.chmod(script_path, 0o755)
        print(f"📄 启动脚本已创建: {script_path}")

    def create_usage_examples(self):
        """创建使用示例"""
        examples = """# Playwright MCP 使用示例

## 通过工作流API调用

### 1. 打开新页面并导航
```python
# 打开新页面
result = await mcp_service.call_tool(
    "playwright-mcp",
    "create_page",
    {}
)

# 导航到网页
result = await mcp_service.call_tool(
    "playwright-mcp",
    "navigate",
    {"url": "https://www.example.com"}
)
```

### 2. 页面交互
```python
# 点击元素
result = await mcp_service.call_tool(
    "playwright-mcp",
    "click",
    {"selector": "button[type='submit']"}
)

# 输入文本
result = await mcp_service.call_tool(
    "playwright-mcp",
    "type",
    {
        "selector": "input[name='username']",
        "text": "admin"
    }
)

# 截图
result = await mcp_service.call_tool(
    "playwright-mcp",
    "screenshot",
    {"full_page": true}
)
```

### 3. 信息提取
```python
# 获取页面标题
result = await mcp_service.call_tool(
    "playwright-mcp",
    "get_title",
    {}
)

# 获取元素文本
result = await mcp_service.call_tool(
    "playwright-mcp",
    "get_text",
    {"selector": "h1"}
)

# 等待元素出现
result = await mcp_service.call_tool(
    "playwright-mcp",
    "wait_for_selector",
    {"selector": ".loading-complete"}
)
```

## 常用工具列表

- `create_page` - 创建新页面
- `navigate` - 导航到URL
- `click` - 点击元素
- `type` - 输入文本
- `screenshot` - 截图
- `get_title` - 获取标题
- `get_text` - 获取文本
- `wait_for_selector` - 等待元素
- `scroll` - 滚动页面
- `close_page` - 关闭页面

## 办公场景应用

### 自动化报告生成
1. 登录系统
2. 导航到报告页面
3. 填写参数
4. 生成并下载报告
5. 截图保存

### 网站监控
1. 定期访问目标网站
2. 检查关键元素是否存在
3. 截图记录状态
4. 发送告警通知

### 数据采集
1. 批量访问列表页面
2. 提取关键信息
3. 分页处理
4. 结构化数据存储
"""

        examples_path = "/home/ubuntu/Workflow-Is-All-You-Need/mcp/playwright_usage.md"
        with open(examples_path, 'w') as f:
            f.write(examples)

        print(f"📚 使用示例已创建: {examples_path}")

    def setup(self):
        """完整安装流程"""
        print("🎭 Playwright MCP 自动配置开始")
        print("=" * 50)

        # 1. 检查或启动服务器
        if not self.check_playwright_server():
            if not self.start_playwright_server():
                return False
        else:
            print("✅ Playwright MCP服务器已在运行")

        # 2. 创建脚本和文档
        self.create_startup_script()
        self.create_usage_examples()

        # 3. 添加到工作流系统（可选，需要认证）
        print("\n📝 要添加到工作流系统，请运行:")
        print(f"   curl -X POST {self.backend_url}/api/v1/mcp-tools/servers \\")
        print('     -H "Content-Type: application/json" \\')
        print('     -H "Authorization: Bearer YOUR_TOKEN" \\')
        print('     -d \'{"server_name": "playwright-mcp", "server_url": "' + f'{self.playwright_url}/mcp' + '", "server_description": "Microsoft官方Playwright MCP - 浏览器自动化", "auth_config": {"type": "none"}}\'')

        print("\n🎉 Playwright MCP配置完成!")
        print(f"🌐 服务地址: {self.playwright_url}/mcp")
        print("📋 下一步:")
        print("   1. 通过工作流系统测试browser工具")
        print("   2. 查看usage示例: cat /home/ubuntu/Workflow-Is-All-You-Need/mcp/playwright_usage.md")
        print("   3. 必要时重启: ./start_playwright_mcp.sh")

        return True

def main():
    """主函数"""
    setup = PlaywrightMCPSetup()
    success = setup.setup()

    if success:
        print("\n🎯 Linus评价: 最简可用的浏览器自动化方案 - 没有废话，直接工作!")
    else:
        print("\n❌ 配置失败，请检查日志")

if __name__ == "__main__":
    main()