# MS-SWIFT Custom UI Dockerfile
# 基于官方 MS-SWIFT Docker 镜像

FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3

WORKDIR /app

# === 1. 修正 APT 镜像源配置（关键修复）===
# 原命令的正则表达式错误地匹配了 // 而非 ://，导致替换失败
# 合并 update 到同一层以优化缓存
RUN sed -i "s/archive.ubuntu.com/mirrors.aliyun.com/g; s/security.ubuntu.com/mirrors.aliyun.com/g" /etc/apt/sources.list && \
    apt-get update

# === 2. 配置 Pip 阿里云镜像 ===
# 使用 pip config 全局设置，后续无需重复指定 -i 参数
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

# === 3. 安装 Node.js 18.x 并验证 ===
# 只安装 nodejs（已包含 npm），避免单独安装 npm 导致冲突
# 添加版本验证，确保安装成功；清理 apt 缓存
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    node --version && \
    npm --version && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# === 4. 安装后端依赖 ===
# --break-system-packages 在 Docker 环境中可接受，但需备注
# 使用 --no-cache-dir 减少镜像层体积
COPY swift/custom_ui/backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/backend-requirements.txt && \
    rm /tmp/backend-requirements.txt

# === 5. 构建前端 ===
# 先单独复制 package 文件，利用 Docker 缓存
# 使用 npm ci 替代 npm install 确保依赖一致性
WORKDIR /tmp/frontend
COPY swift/custom_ui/frontend/package*.json ./

# 配置 npm 镜像并安装依赖（合并到单层）
RUN npm config set registry https://registry.npmmirror.com && \
    npm ci --only=production

# 复制前端源码并构建
COPY swift/custom_ui/frontend /tmp/frontend
RUN npm run build && \
    mkdir -p /app/swift/custom_ui/frontend && \
    mv dist /app/swift/custom_ui/frontend/

# === 6. 复制后端代码和启动脚本 ===
WORKDIR /app
COPY swift/custom_ui/backend /app/swift/custom_ui/backend
COPY swift/custom_ui/docker/start.sh /start.sh
RUN chmod +x /start.sh

# === 7. 暴露端口和启动 ===
EXPOSE 8000
CMD ["/bin/bash", "/start.sh"]