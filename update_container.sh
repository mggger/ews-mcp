#!/bin/bash

# 自动化更新 EWS MCP Server 容器脚本
# 功能：清理旧镜像和容器，构建新镜像，启动新容器

set -e  # 遇到错误立即退出

echo "=========================================="
echo "开始更新 EWS MCP Server"
echo "=========================================="

# 1. 检查并删除旧容器
echo ""
echo "步骤 1: 检查容器 ews-mcp-server..."
if docker ps -a --format '{{.Names}}' | grep -q "^ews-mcp-server$"; then
    echo "发现容器 ews-mcp-server，正在停止并删除..."
    docker stop ews-mcp-server 2>/dev/null || true
    docker rm ews-mcp-server
    echo "✓ 容器已删除"
else
    echo "✓ 容器不存在，跳过删除"
fi

# 2. 检查并删除旧镜像
echo ""
echo "步骤 2: 检查镜像 ews-mcp-server..."
if docker images --format '{{.Repository}}' | grep -q "^ews-mcp-server$"; then
    echo "发现镜像 ews-mcp-server，正在删除..."
    docker rmi ews-mcp-server:latest
    echo "✓ 镜像已删除"
else
    echo "✓ 镜像不存在，跳过删除"
fi

# 3. 构建新镜像
echo ""
echo "步骤 3: 构建新镜像..."
docker build . -t ews-mcp-server:latest
echo "✓ 镜像构建完成"

# 4. 启动新容器
echo ""
echo "步骤 4: 启动新容器..."
docker run -d \
    --name ews-mcp-server \
    -p 8765:8765 \
    --env-file .env \
    -v $(pwd)/logs:/app/logs \
    ews-mcp-server:latest
echo "✓ 容器已启动"

# 5. 验证容器状态
echo ""
echo "步骤 5: 验证容器状态..."
sleep 2
if docker ps --format '{{.Names}}' | grep -q "^ews-mcp-server$"; then
    echo "✓ 容器运行正常"
    echo ""
    echo "=========================================="
    echo "更新完成！"
    echo "=========================================="
    echo ""
    echo "容器信息："
    docker ps --filter "name=ews-mcp-server" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "查看日志: docker logs -f ews-mcp-server"
else
    echo "✗ 容器启动失败"
    echo "请检查日志: docker logs ews-mcp-server"
    exit 1
fi
