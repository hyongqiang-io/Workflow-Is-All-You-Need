/**
 * 用户会话诊断工具
 * User Session Diagnostic Tool
 * 
 * 在浏览器控制台中运行此脚本来诊断用户身份问题
 */

class UserSessionDiagnostic {
    /**
     * 运行完整的用户会话诊断
     */
    static runFullDiagnosis() {
        console.log('🔍 开始用户会话诊断...');
        console.log('=' .repeat(50));
        
        this.checkLocalStorage();
        this.checkTokenValidity();
        this.checkUserInfo();
        this.checkApiConnection();
        this.provideSuggestions();
    }
    
    /**
     * 检查本地存储
     */
    static checkLocalStorage() {
        console.log('📱 检查本地存储...');
        
        const token = localStorage.getItem('token');
        const user = localStorage.getItem('user');
        const otherKeys = Object.keys(localStorage).filter(key => 
            key.includes('auth') || key.includes('user') || key.includes('token')
        );
        
        console.log(`Token存在: ${!!token}`);
        console.log(`用户信息存在: ${!!user}`);
        console.log(`其他认证相关键: ${otherKeys.join(', ') || '无'}`);
        
        if (otherKeys.length > 2) {
            console.warn('⚠️  发现多个认证相关键，可能存在冲突');
        }
    }
    
    /**
     * 检查Token有效性
     */
    static checkTokenValidity() {
        console.log('\\n🔐 检查Token有效性...');
        
        const token = localStorage.getItem('token');
        if (!token) {
            console.error('❌ Token不存在');
            return;
        }
        
        try {
            const parts = token.split('.');
            if (parts.length !== 3) {
                console.error('❌ Token格式无效');
                return;
            }
            
            const payload = JSON.parse(atob(parts[1]));
            const now = Math.floor(Date.now() / 1000);
            
            console.log(`Token用户ID: ${payload.sub}`);
            console.log(`Token用户名: ${payload.username}`);
            console.log(`Token签发时间: ${new Date(payload.iat * 1000).toLocaleString()}`);
            console.log(`Token过期时间: ${new Date(payload.exp * 1000).toLocaleString()}`);
            console.log(`当前时间: ${new Date().toLocaleString()}`);
            
            const timeToExpiry = payload.exp - now;
            if (timeToExpiry <= 0) {
                console.error('❌ Token已过期');
            } else if (timeToExpiry < 300) { // 5分钟
                console.warn(`⚠️  Token即将过期 (${Math.floor(timeToExpiry / 60)}分钟后)`);
            } else {
                console.log(`✅ Token有效 (${Math.floor(timeToExpiry / 3600)}小时后过期)`);
            }
            
        } catch (error) {
            console.error('❌ Token解析失败:', error.message);
        }
    }
    
    /**
     * 检查用户信息
     */
    static checkUserInfo() {
        console.log('\\n👤 检查用户信息...');
        
        const userStr = localStorage.getItem('user');
        if (!userStr) {
            console.error('❌ 用户信息不存在');
            return;
        }
        
        try {
            const user = JSON.parse(userStr);
            console.log('存储的用户信息:');
            console.log(`  用户ID: ${user.user_id || user.id || '未知'}`);
            console.log(`  用户名: ${user.username || '未知'}`);
            console.log(`  邮箱: ${user.email || '未知'}`);
            console.log(`  角色: ${user.role || '未设置'}`);
            
            // 检查用户名是否为测试用户
            if (user.username && user.username.startsWith('test_user_')) {
                console.warn('⚠️  当前登录的是测试用户，可能导致权限问题');
            }
            
        } catch (error) {
            console.error('❌ 用户信息解析失败:', error.message);
        }
    }
    
    /**
     * 检查API连接
     */
    static async checkApiConnection() {
        console.log('\\n🌐 检查API连接...');
        
        try {
            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('✅ API连接正常');
                
                if (data.success && data.data && data.data.user) {
                    const apiUser = data.data.user;
                    console.log('API返回的用户信息:');
                    console.log(`  用户ID: ${apiUser.user_id}`);
                    console.log(`  用户名: ${apiUser.username}`);
                    console.log(`  邮箱: ${apiUser.email}`);
                    
                    // 比较本地存储和API返回的用户信息
                    const localUser = JSON.parse(localStorage.getItem('user') || '{}');
                    if (localUser.user_id !== apiUser.user_id) {
                        console.error('❌ 本地用户信息与API不匹配！');
                        console.log('这是导致权限问题的主要原因。');
                    } else {
                        console.log('✅ 本地用户信息与API匹配');
                    }
                } else {
                    console.warn('⚠️  API响应格式异常');
                }
            } else {
                console.error(`❌ API请求失败: ${response.status} ${response.statusText}`);
                
                if (response.status === 401) {
                    console.log('原因: Token无效或已过期');
                } else if (response.status === 403) {
                    console.log('原因: 权限不足');
                } else if (response.status >= 500) {
                    console.log('原因: 服务器错误');
                }
            }
        } catch (error) {
            console.error('❌ API连接失败:', error.message);
            console.log('可能的原因: 网络问题或后端服务未启动');
        }
    }
    
    /**
     * 提供修复建议
     */
    static provideSuggestions() {
        console.log('\\n💡 修复建议:');
        console.log('-'.repeat(50));
        
        const token = localStorage.getItem('token');
        const user = localStorage.getItem('user');
        
        if (!token || !user) {
            console.log('1. 重新登录以获取有效的Token和用户信息');
            console.log('   执行: window.location.href = "/login"');
        } else {
            try {
                const payload = JSON.parse(atob(token.split('.')[1]));
                const now = Math.floor(Date.now() / 1000);
                
                if (payload.exp <= now) {
                    console.log('1. Token已过期，需要重新登录');
                    console.log('   执行: this.clearAuthAndRedirect()');
                } else {
                    console.log('1. Token有效，检查用户权限设置');
                }
            } catch (e) {
                console.log('1. Token格式错误，清除并重新登录');
                console.log('   执行: this.clearAuthAndRedirect()');
            }
        }
        
        console.log('2. 清除所有认证数据：this.clearAllAuth()');
        console.log('3. 检查是否有多个标签页登录不同用户');
        console.log('4. 如果问题持续，联系管理员检查后端用户状态');
    }
    
    /**
     * 清除所有认证数据
     */
    static clearAllAuth() {
        const authKeys = Object.keys(localStorage).filter(key =>
            key.includes('auth') || key.includes('user') || key.includes('token')
        );
        
        authKeys.forEach(key => {
            localStorage.removeItem(key);
            console.log(`🗑️  已清除: ${key}`);
        });
        
        console.log('✅ 所有认证数据已清除');
        return authKeys.length;
    }
    
    /**
     * 清除认证并跳转登录
     */
    static clearAuthAndRedirect() {
        this.clearAllAuth();
        console.log('🔄 正在跳转到登录页...');
        setTimeout(() => {
            window.location.href = '/login';
        }, 1000);
    }
    
    /**
     * 生成诊断报告
     */
    static generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            localStorage: {
                token: !!localStorage.getItem('token'),
                user: !!localStorage.getItem('user'),
                allKeys: Object.keys(localStorage)
            },
            tokenInfo: null,
            userInfo: null
        };
        
        // 解析Token
        const token = localStorage.getItem('token');
        if (token) {
            try {
                const payload = JSON.parse(atob(token.split('.')[1]));
                report.tokenInfo = {
                    userId: payload.sub,
                    username: payload.username,
                    exp: payload.exp,
                    isExpired: Math.floor(Date.now() / 1000) > payload.exp
                };
            } catch (e) {
                report.tokenInfo = { error: e.message };
            }
        }
        
        // 解析用户信息
        const userStr = localStorage.getItem('user');
        if (userStr) {
            try {
                report.userInfo = JSON.parse(userStr);
            } catch (e) {
                report.userInfo = { error: e.message };
            }
        }
        
        console.log('📋 诊断报告:', report);
        return report;
    }
}

// 自动运行诊断（如果在控制台中直接运行此脚本）
if (typeof window !== 'undefined') {
    console.log('🔧 用户会话诊断工具已加载');
    console.log('运行 UserSessionDiagnostic.runFullDiagnosis() 开始诊断');
    console.log('或者运行以下快捷命令:');
    console.log('  - UserSessionDiagnostic.clearAllAuth() // 清除所有认证数据');
    console.log('  - UserSessionDiagnostic.clearAuthAndRedirect() // 清除并跳转登录');
    console.log('  - UserSessionDiagnostic.generateReport() // 生成诊断报告');
    
    // 设置全局快捷方式
    window.diagUser = UserSessionDiagnostic;
}

export default UserSessionDiagnostic;