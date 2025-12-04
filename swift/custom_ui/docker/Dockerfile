# MS-SWIFT Custom UI Dockerfile
# 基于官方 MS-SWIFT Docker 镜像（已包含 MS-SWIFT 3.10.3）

FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3

# 设置工作目录
WORKDIR /app

# 配置阿里云镜像源（提升下载速度）
RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
    sed -i 's@//.*security.ubuntu.com@//mirrors.aliyun.com@g' /etc/apt/sources.list && \
    apt-get update

# 配置 pip 阿里云镜像（提升 Python 包下载速度）
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

# 安装 Node.js 18.x (用于前端构建，基础镜像未包含)
# 注意：只安装 nodejs，npm 已包含在内，不要单独安装 npm 包（会导致版本冲突）
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 验证 Node.js 和 npm 版本，并配置 npm 镜像
RUN node --version && \
    npm --version && \
    npm config set registry https://registry.npmmirror.com

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
