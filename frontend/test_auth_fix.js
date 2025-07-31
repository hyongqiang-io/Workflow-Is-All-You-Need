/**
 * 测试认证修复的有效性
 * 在浏览器控制台中运行此脚本
 */

console.log('🧪 开始测试认证系统修复...');

// 测试用户状态一致性
async function testAuthFix() {
    console.log('='.repeat(50));
    
    // 1. 检查当前登录状态
    const token = localStorage.getItem('token');
    const userStr = localStorage.getItem('user');
    
    console.log('📱 当前状态检查:');
    console.log(`Token存在: ${!!token}`);
    console.log(`用户信息存在: ${!!userStr}`);
    
    if (token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            const now = Math.floor(Date.now() / 1000);
            const isExpired = payload.exp <= now;
            
            console.log(`Token用户ID: ${payload.sub}`);
            console.log(`Token用户名: ${payload.username}`);
            console.log(`Token是否过期: ${isExpired}`);
            
            if (userStr) {
                const user = JSON.parse(userStr);
                console.log(`本地用户ID: ${user.user_id}`);
                console.log(`本地用户名: ${user.username}`);
                console.log(`用户ID一致: ${payload.sub === user.user_id}`);
            }
        } catch (e) {
            console.error('❌ Token解析失败:', e);
        }
    }
    
    // 2. 测试API调用
    console.log('\n🌐 测试API调用:');
    try {
        const response = await fetch('http://localhost:8001/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ API调用成功');
            
            if (data.success && data.data?.user) {
                const apiUser = data.data.user;
                console.log(`API返回用户ID: ${apiUser.user_id}`);
                console.log(`API返回用户名: ${apiUser.username}`);
                
                // 比较一致性
                if (userStr) {
                    const localUser = JSON.parse(userStr);
                    const isConsistent = localUser.user_id === apiUser.user_id;
                    console.log(`本地与API一致: ${isConsistent}`);
                    
                    if (!isConsistent) {
                        console.warn('⚠️  发现不一致，这是问题的根源！');
                        console.log('建议执行: window.location.reload() 或重新登录');
                    }
                }
            }
        } else {
            console.error(`❌ API调用失败: ${response.status}`);
        }
    } catch (error) {
        console.error('❌ API调用异常:', error);
    }
    
    // 3. 测试Zustand store状态
    console.log('\n📦 测试Store状态:');
    try {
        // 假设store已经导入到全局
        if (window.useAuthStore) {
            const store = window.useAuthStore.getState();
            console.log(`Store用户存在: ${!!store.user}`);
            console.log(`Store认证状态: ${store.isAuthenticated}`);
            
            if (store.user) {
                console.log(`Store用户ID: ${store.user.user_id}`);
                console.log(`Store用户名: ${store.user.username}`);
            }
        } else {
            console.log('Store未在全局可用，跳过测试');
        }
    } catch (error) {
        console.error('❌ Store测试失败:', error);
    }
    
    console.log('\n✅ 认证系统测试完成');
    console.log('如果发现问题，请运行以下命令清理状态:');
    console.log('localStorage.clear(); window.location.reload();');
}

// 提供清理函数
function clearAuthState() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('auth-storage');
    console.log('🧹 认证状态已清理');
    console.log('请刷新页面并重新登录');
}

// 提供重新登录函数
function forceRelogin() {
    clearAuthState();
    window.location.href = '/login';
}

// 导出到全局
window.testAuthFix = testAuthFix;
window.clearAuthState = clearAuthState;
window.forceRelogin = forceRelogin;

console.log('🛠️  测试工具已加载，可用命令:');
console.log('  - testAuthFix()     // 运行完整测试');
console.log('  - clearAuthState()  // 清理认证状态');
console.log('  - forceRelogin()    // 强制重新登录');

// 自动运行测试
testAuthFix();