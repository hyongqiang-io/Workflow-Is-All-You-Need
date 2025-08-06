const express = require('express');
const app = express();
const port = 3005;

app.use(express.json());

// CORS支持
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key');
  next();
});

// 健康检查
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// 工具列表
app.get('/mcp/tools', (req, res) => {
  res.json({
    tools: [
      {
        name: 'get_time',
        description: '获取当前时间',
        parameters: {
          type: 'object',
          properties: {
            timezone: {
              type: 'string',
              description: '时区',
              default: 'UTC'
            }
          }
        }
      },
      {
        name: 'calculate',
        description: '执行数学计算',
        parameters: {
          type: 'object',
          properties: {
            expression: {
              type: 'string',
              description: '数学表达式，如 "2+3*4"'
            }
          },
          required: ['expression']
        }
      },
      {
        name: 'random_number',
        description: '生成随机数',
        parameters: {
          type: 'object',
          properties: {
            min: { type: 'number', default: 0 },
            max: { type: 'number', default: 100 }
          }
        }
      }
    ]
  });
});

// 工具调用
app.post('/mcp/tools/call', (req, res) => {
  const { name, arguments: args } = req.body;
  
  try {
    let result;
    
    switch (name) {
      case 'get_time':
        const timezone = args?.timezone || 'UTC';
        result = `当前时间 (${timezone}): ${new Date().toLocaleString()}`;
        break;
        
      case 'calculate':
        const expression = args?.expression;
        if (!expression) {
          throw new Error('缺少表达式参数');
        }
        // 简单的数学计算（生产环境需要更安全的实现）
        const calcResult = eval(expression);
        result = `${expression} = ${calcResult}`;
        break;
        
      case 'random_number':
        const min = args?.min || 0;
        const max = args?.max || 100;
        const randomNum = Math.floor(Math.random() * (max - min + 1)) + min;
        result = `随机数 (${min}-${max}): ${randomNum}`;
        break;
        
      default:
        throw new Error(`未知工具: ${name}`);
    }
    
    res.json({
      success: true,
      result: result,
      timestamp: new Date().toISOString()
    });
    
  } catch (error) {
    res.status(400).json({
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });
  }
});

// MCP协议支持
app.post('/mcp', (req, res) => {
  const { method, params, id } = req.body;
  
  switch (method) {
    case 'tools/list':
      res.json({
        result: {
          tools: [
            {
              name: 'get_time',
              description: '获取当前时间',
              parameters: {
                type: 'object',
                properties: {
                  timezone: { type: 'string', default: 'UTC' }
                }
              }
            }
          ]
        },
        id
      });
      break;
      
    case 'tools/call':
      // 处理工具调用
      const toolName = params?.name;
      const toolArgs = params?.arguments || {};
      
      if (toolName === 'get_time') {
        res.json({
          result: {
            content: [{
              type: 'text',
              text: `当前时间: ${new Date().toLocaleString()}`
            }]
          },
          id
        });
      } else {
        res.json({
          error: { code: -32602, message: `未知工具: ${toolName}` },
          id
        });
      }
      break;
      
    default:
      res.json({
        error: { code: -32601, message: `未知方法: ${method}` },
        id
      });
  }
});

app.listen(port, () => {
  console.log(`🚀 Node.js MCP测试服务器运行在 http://localhost:${port}`);
  console.log(`📋 可用工具: get_time, calculate, random_number`);
  console.log(`🔧 工具列表: GET http://localhost:${port}/mcp/tools`);
  console.log(`⚡ 工具调用: POST http://localhost:${port}/mcp/tools/call`);
});

module.exports = app;