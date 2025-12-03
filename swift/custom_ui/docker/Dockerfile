# MS-SWIFT Custom Web UI - Docker Image
# 基于 ModelScope 官方镜像

FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3

LABEL maintainer="MS-SWIFT Contributors"
LABEL description="MS-SWIFT Custom Web UI with FastAPI backend and React frontend"

# 设置工作目录
WORKDIR /app

# 复制 ms-swift 源代码
COPY ../../.. /app/ms-swift

# 安装 ms-swift
WORKDIR /app/ms-swift
RUN pip install -e . --break-system-packages

# 复制 custom_ui 代码 (现在在 swift/custom_ui)
COPY .. /app/custom_ui

# 安装 API 后端依赖
WORKDIR /app/custom_ui/backend
RUN pip install -r requirements.txt --break-system-packages

# 安装 Node.js (用于前端构建)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm@latest

# 构建前端 (如果前端已开发)
# WORKDIR /app/custom_ui/frontend
# RUN npm install && npm run build

# 创建必要的目录
RUN mkdir -p /app/data /app/models /app/output /app/logs

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# 暴露端口
# 8000: API 后端
# 3000: 前端 (如果使用独立前端服务器)
EXPOSE 8000 3000

# 复制启动脚本
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

# 工作目录
WORKDIR /app/custom_ui/backend

# 启动命令
CMD ["/start.sh"]
