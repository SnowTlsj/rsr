#!/bin/bash
# 快速部署脚本

echo "=========================================="
echo "肉苁蓉播种监测系统 - 快速部署"
echo "=========================================="
echo ""

# 步骤 1: 停止现有服务
echo "步骤 1/4: 停止现有服务..."
docker compose down
echo "✓ 服务已停止"
echo ""

# 步骤 2: 重新构建并启动
echo "步骤 2/4: 重新构建并启动服务..."
docker compose up -d --build
echo "✓ 服务已启动"
echo ""

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 步骤 3: 运行数据库迁移
echo "步骤 3/4: 运行数据库迁移..."
docker compose exec backend alembic upgrade head
if [ $? -eq 0 ]; then
    echo "✓ 数据库迁移成功"
else
    echo "✗ 数据库迁移失败，请检查日志"
    exit 1
fi
echo ""

# 步骤 4: 验证服务状态
echo "步骤 4/4: 验证服务状态..."
docker compose ps
echo ""

echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "访问地址："
echo "  前端: http://localhost:5174"
echo "  后端: http://localhost:8200"
echo ""
echo "测试命令："
echo "  pip install requests"
echo "  python test_ingest.py"
echo ""
echo "查看日志："
echo "  docker compose logs -f"
echo ""

