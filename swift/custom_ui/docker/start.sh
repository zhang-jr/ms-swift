#!/bin/bash
# MS-SWIFT Custom Web UI - Startup Script

set -e

echo "========================================="
echo "MS-SWIFT Custom Web UI - Starting..."
echo "========================================="

# 检查 GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Information:"
    nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv,noheader
    echo ""
else
    echo "Warning: nvidia-smi not found. Running in CPU mode."
    echo ""
fi

# 检查 CUDA
if python -c "import torch; print('CUDA available:', torch.cuda.is_available())"; then
    python -c "import torch; print('CUDA version:', torch.version.cuda if torch.cuda.is_available() else 'N/A')"
    python -c "import torch; print('GPU count:', torch.cuda.device_count() if torch.cuda.is_available() else 0)"
    echo ""
fi

# 打印环境信息
echo "Python version:"
python --version
echo ""

echo "MS-SWIFT version:"
python -c "import swift; print(swift.__version__)" || echo "MS-SWIFT not found"
echo ""

# 创建必要的目录
mkdir -p /app/data /app/models /app/output /app/logs

# 切换到 backend 目录
cd /app/custom_ui/backend

echo "========================================="
echo "Starting FastAPI backend..."
echo "========================================="
echo "API Host: ${API_HOST:-0.0.0.0}"
echo "API Port: ${API_PORT:-8000}"
echo "API Docs: http://${API_HOST:-0.0.0.0}:${API_PORT:-8000}/docs"
echo "========================================="

# 启动 FastAPI 应用
# 使用 uvicorn 运行,支持热重载
exec uvicorn app:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --log-level "${LOG_LEVEL:-info}" \
    --no-access-log
