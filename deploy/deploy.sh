#!/bin/bash
# 云服务器部署脚本

set -e

echo "=========================================="
echo "We-MP-RSS 云服务器部署"
echo "=========================================="

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 确定docker-compose命令
if docker compose version &> /dev/null; then
    DC="docker compose"
else
    DC="docker-compose"
fi

# 检查镜像是否存在
if ! docker images | grep -q "we-mp-rss"; then
    echo "⚠️  未找到 we-mp-rss 镜像"
    echo "请先执行: docker load -i we-mp-rss-latest.tar"
    exit 1
fi

# 检查.env文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在从 .env.example 创建..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请修改配置后重新运行此脚本"
    echo "编辑命令: nano .env"
    exit 0
fi

# 创建必要目录
mkdir -p mysql/data mysql/init data

echo ""
echo "启动服务..."
echo "=========================================="
$DC up -d

echo ""
echo "等待服务启动..."
sleep 10

echo ""
echo "服务状态："
echo "=========================================="
$DC ps

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo ""
echo "访问地址: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip'):${WEB_PORT:-8001}"
echo ""
echo "常用命令："
echo "  查看日志: $DC logs -f"
echo "  停止服务: $DC down"
echo "  重启服务: $DC restart"
echo "  查看状态: $DC ps"
echo "=========================================="
