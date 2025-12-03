#!/bin/bash
# MS-SWIFT Custom UI 启动脚本

set -e

echo "=========================================="
echo "   MS-SWIFT Custom UI Starting..."
echo "=========================================="

# 切换到后端目录
cd /app/swift/custom_ui/backend

# 启动 FastAPI 后端
echo "Starting FastAPI backend on port 8000..."
uvicorn app:app --host 0.0.0.0 --port 8000 --reload &

# 等待后端启动
sleep 5

echo "=========================================="
echo "   MS-SWIFT Custom UI Started!"
echo "=========================================="
echo ""
echo "Backend API:  http://localhost:8000"
echo "API Docs:     http://localhost:8000/docs"
echo "Frontend:     http://localhost:8000"
echo ""
echo "=========================================="

# 保持容器运行
wait
