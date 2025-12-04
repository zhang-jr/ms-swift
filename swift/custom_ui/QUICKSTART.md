# MS-SWIFT Custom UI 快速开始指南

本指南将帮助你快速部署和使用 MS-SWIFT Custom UI。

## 前置要求

### Docker 部署
- Docker >= 20.10
- Docker Compose >= 2.0
- NVIDIA GPU + CUDA 12.1+ (用于模型训练和推理)
- NVIDIA Container Toolkit

### 本地开发
- Python >= 3.8
- Node.js >= 18
- npm 或 yarn
- CUDA 环境 (可选,用于 GPU 加速)

## 方式一: Docker 部署 (推荐)

### 1. 安装 NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 2. 克隆项目

```bash
git clone https://github.com/zhang-jr/ms-swift.git
cd ms-swift
git checkout feature/custom-webui
```

### 3. 配置 GPU 和环境变量

```bash
cd swift/custom_ui/docker

# 复制环境变量配置模板
cp .env.example .env

# 编辑 .env 文件配置 GPU
nano .env  # 或使用其他编辑器
```

**常见 GPU 配置示例：**

```bash
# 单卡场景（默认）
GPU_COUNT=1
CUDA_VISIBLE_DEVICES=0

# 使用第2块GPU
GPU_COUNT=1
CUDA_VISIBLE_DEVICES=1

# 使用2块GPU
GPU_COUNT=2
CUDA_VISIBLE_DEVICES=0,1

# 使用所有GPU
GPU_COUNT=all
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7

# 使用指定的非连续GPU
GPU_COUNT=3
CUDA_VISIBLE_DEVICES=0,2,4
```

**其他可配置项：**
- `API_PORT`: API 访问端口（默认 8000）
- `DATA_DIR`: 数据目录路径（支持相对/绝对路径）
- `MODEL_DIR`: 模型目录路径（支持相对/绝对路径）
- `OUTPUT_DIR`: 输出目录路径（支持相对/绝对路径）

**目录配置示例：**

```bash
# 使用相对路径（默认，相对于 docker-compose.yml）
DATA_DIR=./data
MODEL_DIR=./models
OUTPUT_DIR=./output

# 使用绝对路径（生产环境推荐）
DATA_DIR=/mnt/data/ms-swift
MODEL_DIR=/mnt/ssd/models
OUTPUT_DIR=/mnt/ssd/output

# 挂载 NFS 共享存储
MODEL_DIR=/nfs/shared/models

# Windows Docker Desktop 路径
MODEL_DIR=/host_mnt/d/models
```

**路径规划建议：**
- `DATA_DIR`: 训练数据集，需要快速读取，建议使用 SSD
- `MODEL_DIR`: 预训练模型（体积大），可使用大容量 HDD
- `OUTPUT_DIR`: 训练输出（频繁写入），建议使用 SSD/NVMe

### 4. 构建和启动服务

```bash
# 构建镜像 (首次运行或代码更新后)
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f ms-swift-custom-ui
```

### 5. 访问服务

打开浏览器访问:
- 前端界面: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 6. 停止服务

```bash
docker-compose down

# 如需删除数据卷
docker-compose down -v
```

## 方式二: 本地开发部署

### 1. 安装 MS-SWIFT

```bash
git clone https://github.com/zhang-jr/ms-swift.git
cd ms-swift
git checkout feature/custom-webui

# 安装 MS-SWIFT
pip install -e .
```

### 2. 启动后端服务

```bash
cd swift/custom_ui/backend

# 安装后端依赖
pip install -r requirements.txt

# 启动 FastAPI 服务
python app.py
```

后端服务将在 http://localhost:8000 启动

### 3. 启动前端服务

新开一个终端:

```bash
cd swift/custom_ui/frontend

# 安装前端依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:3000 启动

### 4. 访问应用

打开浏览器访问 http://localhost:3000

## 使用示例

### 示例 1: 训练一个 LoRA 模型

1. 访问"模型训练"页面
2. 选择模型: `Qwen2.5 7B Instruct`
3. 选择数据集: `Alpaca 中文数据集`
4. 配置训练参数:
   - 训练轮数: 1
   - Batch Size: 1
   - 学习率: 0.0001
   - LoRA Rank: 8
5. 点击"开始训练"
6. 在右侧查看实时训练进度和日志

### 示例 2: 对话推理

1. 访问"模型推理"页面
2. 选择模型或输入模型路径
3. (可选) 输入 LoRA adapter 路径
4. 配置推理参数:
   - Temperature: 0.7
   - Top P: 0.9
5. 点击"加载模型"
6. 在对话框中输入消息并发送
7. 查看模型回复

### 示例 3: 部署 API 服务

1. 访问"模型部署"页面
2. 选择要部署的模型
3. 配置服务参数:
   - Host: 0.0.0.0
   - Port: 8080
4. 点击"启动部署"
5. 复制生成的 API 端点地址
6. 使用 OpenAI 客户端调用:

```python
import openai

client = openai.OpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8080/v1",
)

response = client.chat.completions.create(
    model="default",
    messages=[
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ]
)

print(response.choices[0].message.content)
```

## 配置说明

### 环境变量

可以通过环境变量配置服务:

```bash
# 后端 API 地址 (前端配置)
VITE_API_BASE_URL=http://localhost:8000/api

# CUDA 设备
CUDA_VISIBLE_DEVICES=0

# 模型缓存目录
MODELSCOPE_CACHE=/path/to/models
HF_HOME=/path/to/models
```

### Docker 卷挂载

默认挂载以下目录:

- `./data`: 数据集目录
- `./models`: 模型缓存目录
- `./output`: 训练输出目录

可以在 `docker-compose.yml` 中修改:

```yaml
volumes:
  - /your/custom/path:/app/data
  - /your/models/path:/app/models
  - /your/output/path:/app/output
```

## 故障排除

### 问题 1: Docker 构建失败

**可能原因**: 网络问题或依赖下载失败

**解决方案**:
```bash
# 使用国内镜像源
docker-compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题 2: GPU 不可用

**检查步骤**:
```bash
# 检查 GPU
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 检查容器内 GPU
docker-compose exec ms-swift-custom-ui nvidia-smi
```

### 问题 3: 端口冲突

**解决方案**:

修改 `docker-compose.yml` 中的端口映射:
```yaml
ports:
  - "8001:8000"  # 改用 8001 端口
```

### 问题 4: 前端无法连接后端

**检查步骤**:
1. 确认后端服务已启动: `curl http://localhost:8000/health`
2. 检查浏览器控制台的网络请求
3. 确认 CORS 配置正确

### 问题 5: WebSocket 连接失败

**可能原因**: 代理配置或防火墙

**解决方案**:
1. 检查 Vite 代理配置 (`vite.config.ts`)
2. 确认 WebSocket URL 正确
3. 检查防火墙设置

## 性能优化建议

### 1. 训练性能优化

- 使用梯度累积增加有效 batch size
- 启用梯度检查点节省显存
- 使用混合精度训练 (fp16/bf16)
- 调整 LoRA rank 和 alpha

### 2. 推理性能优化

- 使用 vLLM 进行推理加速
- 启用模型量化 (4-bit/8-bit)
- 调整 GPU 内存利用率
- 使用批处理推理

### 3. 部署性能优化

- 使用 vLLM 部署
- 启用连续批处理
- 配置合适的并发数
- 使用负载均衡

## 下一步

- 阅读 [README.md](./README.md) 了解更多功能
- 查看 [API 文档](http://localhost:8000/docs) 了解完整 API
- 参考 [MS-SWIFT 官方文档](https://swift.readthedocs.io/) 了解更多训练技巧
- 查看 [CALUDE.md](../CALUDE.md) 了解开发指南

## 获取帮助

如遇到问题,可以:
1. 查看日志: `docker-compose logs -f`
2. 提交 Issue: https://github.com/zhang-jr/ms-swift/issues
3. 参考官方文档: https://swift.readthedocs.io/

祝使用愉快!
