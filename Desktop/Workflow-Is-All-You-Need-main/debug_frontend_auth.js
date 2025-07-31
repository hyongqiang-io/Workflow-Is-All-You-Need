// 前端调试脚本 - 在浏览器控制台运行
console.log("=== 前端认证调试 ===");

// 检查当前认证状态
const checkAuthState = () => {
  console.log("1. 检查localStorage:");
  console.log("  token:", localStorage.getItem('token'));
  console.log("  auth-storage:", localStorage.getItem('auth-storage'));
  
  console.log("\n2. 检查Zustand状态:");
  const authStorage = localStorage.getItem('auth-storage');
  if (authStorage) {
    try {
      const parsed = JSON.parse(authStorage);
      console.log("  解析的存储状态:", parsed);
    } catch (e) {
      console.log("  存储解析失败:", e);
    }
  }
};

// 测试API连接
const testAPIConnection = async () => {
  console.log("\n3. 测试API连接:");
  
  try {
    const response = await fetch('http://localhost:8000/health');
    console.log("  后端健康检查:", response.status, await response.text());
  } catch (e) {
    console.log("  ❌ 后端连接失败:", e.message);
    return false;
  }
  
  return true;
};

// 测试注册API
const testRegister = async () => {
  console.log("\n4. 测试注册API:");
  
  const testData = {
    username: "debuguser" + Date.now(),
    email: "debuguser" + Date.now() + "@example.com",
    password: "password123"
  };
  
  try {
    const response = await fetch('http://localhost:8000/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(testData)
    });
    
    console.log("  注册状态码:", response.status);
    const data = await response.text();
    console.log("  注册响应:", data);
    
    if (response.status === 201) {
      console.log("  ✅ 注册API正常");
      return testData;
    } else {
      console.log("  ❌ 注册API异常");
      return null;
    }
  } catch (e) {
    console.log("  ❌ 注册请求失败:", e.message);
    return null;
  }
};

// 测试登录API
const testLogin = async (userData) => {
  if (!userData) return;
  
  console.log("\n5. 测试登录API:");
  
  const loginData = {
    username_or_email: userData.username,
    password: userData.password
  };
  
  try {
    const response = await fetch('http://localhost:8000/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(loginData)
    });
    
    console.log("  登录状态码:", response.status);
    const data = await response.text();
    console.log("  登录响应:", data);
    
    if (response.status === 200) {
      console.log("  ✅ 登录API正常");
      try {
        const parsed = JSON.parse(data);
        console.log("  登录数据结构:", parsed);
      } catch (e) {
        console.log("  响应解析失败:", e);
      }
    } else {
      console.log("  ❌ 登录API异常");
    }
  } catch (e) {
    console.log("  ❌ 登录请求失败:", e.message);
  }
};

// 执行完整诊断
const runDiagnosis = async () => {
  console.log("开始前端认证诊断...\n");
  
  checkAuthState();
  
  const apiOk = await testAPIConnection();
  if (!apiOk) {
    console.log("\n❌ 请先启动后端服务器:");
    console.log("   D:\\anaconda3\\envs\\fornew\\python.exe main.py");
    return;
  }
  
  const userData = await testRegister();
  await testLogin(userData);
  
  console.log("\n=== 诊断完成 ===");
  console.log("如果API正常但前端不能跳转，请检查:");
  console.log("1. 浏览器开发者工具的Network标签");
  console.log("2. 控制台的错误信息");
  console.log("3. React组件的状态更新");
};

// 在浏览器控制台运行
runDiagnosis();