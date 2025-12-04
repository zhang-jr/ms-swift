# MS-SWIFT Custom UI Dockerfile
# 基于官方 MS-SWIFT Docker 镜像（已包含 MS-SWIFT 3.10.3）

FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3

# 设置工作目录
WORKDIR /app

# 安装 Node.js 18.x (用于前端构建，基础镜像未包含)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装后端额外依赖 (FastAPI、uvicorn 等 Web 框架，基础镜像未包含)
COPY swift/custom_ui/backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install -r /tmp/backend-requirements.txt --break-system-packages && \
    rm /tmp/backend-requirements.txt

# 构建前端
COPY swift/custom_ui/frontend/package*.json /tmp/frontend/
WORKDIR /tmp/frontend
RUN npm install

COPY swift/custom_ui/frontend /tmp/frontend
RUN npm run build && \
    mkdir -p /app/swift/custom_ui/frontend && \
    mv dist /app/swift/custom_ui/frontend/

# 复制后端代码
WORKDIR /app
COPY swift/custom_ui/backend /app/swift/custom_ui/backend

# 复制启动脚本
COPY swift/custom_ui/docker/start.sh /start.sh
RUN chmod +x /start.sh

# 暴露端口
# 8000: FastAPI 后端
EXPOSE 8000

# 启动命令
CMD ["/start.sh"]
