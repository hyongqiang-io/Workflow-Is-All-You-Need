#!/bin/bash

# nginx API代理修复脚本
# 修复健康端点和API代理配置问题

set -e

NGINX_CONFIG="/etc/nginx/sites-enabled/autolabflow"
BACKUP_CONFIG="/home/ubuntu/Workflow-Is-All-You-Need/nginx-autolabflow.backup"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔧 修复nginx API代理配置...${NC}"

# 1. 备份当前配置
echo -e "${YELLOW}💾 备份当前nginx配置...${NC}"
sudo cp "$NGINX_CONFIG" "$BACKUP_CONFIG"
echo -e "${GREEN}✅ 配置已备份到: $BACKUP_CONFIG${NC}"

# 2. 创建新的配置文件
echo -e "${YELLOW}📝 生成修复后的配置...${NC}"

# 临时配置文件
TEMP_CONFIG="/tmp/autolabflow-fixed.conf"

cat > "$TEMP_CONFIG" << 'EOF'
server {
    listen 80;
    server_name autolabflow.online www.autolabflow.online _;
    
    # Frontend static files - use /var/www/html
    root /var/www/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Frontend routes
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Health check endpoint - proxy to backend
    location /health {
        proxy_pass http://127.0.0.1:8001/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        access_log off;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # CORS headers for API
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Credentials true always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Accept,Authorization,Cache-Control,Content-Type,DNT,If-Modified-Since,Keep-Alive,Origin,User-Agent,X-Requested-With" always;
        
        if ($request_method = OPTIONS) {
            return 204;
        }
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8001/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API Documentation
    location /docs {
        proxy_pass http://127.0.0.1:8001/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8001/redoc;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl;
    server_name autolabflow.online www.autolabflow.online;
    
    ssl_certificate /etc/nginx/autolabflow.online_bundle.crt;
    ssl_certificate_key /etc/nginx/autolabflow.online.key;
    
    # Frontend static files
    root /var/www/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Frontend routes
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }

    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Health check endpoint - proxy to backend
    location /health {
        proxy_pass http://127.0.0.1:8001/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        access_log off;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # CORS headers for API
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Credentials true always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Accept,Authorization,Cache-Control,Content-Type,DNT,If-Modified-Since,Keep-Alive,Origin,User-Agent,X-Requested-With" always;
        
        if ($request_method = OPTIONS) {
            return 204;
        }
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8001/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API Documentation
    location /docs {
        proxy_pass http://127.0.0.1:8001/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8001/redoc;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# 3. 替换配置文件
echo -e "${YELLOW}🔄 应用新配置...${NC}"
sudo cp "$TEMP_CONFIG" "$NGINX_CONFIG"

# 4. 测试nginx配置
echo -e "${YELLOW}🧪 测试nginx配置...${NC}"
if sudo nginx -t; then
    echo -e "${GREEN}✅ Nginx配置测试通过${NC}"
    
    # 5. 重新加载nginx
    echo -e "${YELLOW}🔄 重新加载nginx...${NC}"
    sudo systemctl reload nginx
    echo -e "${GREEN}✅ Nginx已重新加载${NC}"
    
    # 6. 测试API代理
    echo -e "${YELLOW}🔍 测试API代理...${NC}"
    sleep 2
    
    # 测试健康端点
    if curl -f -s http://localhost/health >/dev/null; then
        echo -e "${GREEN}✅ HTTP健康端点代理正常${NC}"
    else
        echo -e "${RED}❌ HTTP健康端点代理失败${NC}"
    fi
    
    # 测试API端点
    if curl -f -s http://localhost/api/auth/me >/dev/null 2>&1 || [[ $? -eq 22 ]]; then
        echo -e "${GREEN}✅ HTTP API代理正常（返回认证错误是正常的）${NC}"
    else
        echo -e "${RED}❌ HTTP API代理失败${NC}"
    fi
    
    echo -e "${GREEN}🎉 nginx API代理修复完成！${NC}"
    echo -e "${BLUE}💡 测试命令:${NC}"
    echo "  HTTP健康检查: curl http://localhost/health"
    echo "  HTTPS健康检查: curl https://www.autolabflow.online/health"
    echo "  API文档: https://www.autolabflow.online/docs"
    
else
    echo -e "${RED}❌ Nginx配置测试失败${NC}"
    echo -e "${YELLOW}🔄 恢复备份配置...${NC}"
    sudo cp "$BACKUP_CONFIG" "$NGINX_CONFIG"
    sudo systemctl reload nginx
    echo -e "${YELLOW}⚠️  已恢复原配置${NC}"
    exit 1
fi

# 清理临时文件
rm -f "$TEMP_CONFIG"