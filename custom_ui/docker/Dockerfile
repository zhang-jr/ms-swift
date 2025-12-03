# MS-SWIFT Custom UI Dockerfile
# 基于官方 MS-SWIFT Docker 镜像

FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . /app

# 安装 MS-SWIFT (开发模式)
RUN pip install -e . --break-system-packages

# 安装后端依赖
WORKDIR /app/custom_ui/backend
RUN pip install -r requirements.txt --break-system-packages

# 安装 Node.js 18.x (用于前端构建)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# 构建前端
WORKDIR /app/custom_ui/frontend
COPY custom_ui/frontend/package*.json ./
RUN npm install
COPY custom_ui/frontend ./
RUN npm run build

# 复制启动脚本
WORKDIR /app
COPY custom_ui/docker/start.sh /start.sh
RUN chmod +x /start.sh

# 暴露端口
# 8000: FastAPI 后端
# 3000: 前端开发服务器 (可选)
EXPOSE 8000 3000

# 启动命令
CMD ["/start.sh"]
