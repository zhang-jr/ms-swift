# MS-SWIFT Custom Web UI 快速启动指南

本文档提供快速启动 MS-SWIFT Custom Web UI 的完整步骤。

## 方式一: 本地开发模式

### 1. 环境准备

确保已安装:
- Python 3.8+
- Node.js 18+
- CUDA 11.8+ (如果使用 GPU)

### 2. 安装 MS-SWIFT

```bash
# 克隆仓库
git clone https://github.com/zhang-jr/ms-swift.git
cd ms-swift

# 安装 MS-SWIFT
pip install -e .
```

### 3. 启动后端服务

```bash
# 进入后端目录
cd swift/custom_ui/backend

# 安装依赖
pip install -r requirements.txt

# 启动 FastAPI 服务
python app.py
```

后端服务将在 `http://localhost:8000` 启动。

查看 API 文档: http://localhost:8000/docs

### 4. 启动前端界面

打开新终端:

```bash
# 进入前端目录
cd swift/custom_ui/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端界面将在 `http://localhost:3000` 启动。

## 方式二: Docker 部署

### 1. 构建镜像

```bash
cd ms-swift/swift/custom_ui/docker

# 构建 Docker 镜像
docker-compose build
```

### 2. 启动服务

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

服务访问:
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 前端 (如果已构建): http://localhost:3000

### 3. 停止服务

```bash
docker-compose down
```

## 使用示例

### 训练模型

#### 方法 1: 使用 Web 界面

1. 打开浏览器访问 http://localhost:3000
2. 进入"模型训练"页面
3. 选择模型和数据集
4. 配置训练参数
5. 点击"开始训练"

#### 方法 2: 使用 API

```python
import requests

url = "http://localhost:8000/api/train/start"
data = {
    "model": "qwen/Qwen2.5-0.5B-Instruct",
    "dataset": ["alpaca-zh"],
    "train_type": "lora",
    "num_train_epochs": 1,
    "batch_size": 1,
    "learning_rate": 1e-4,
    "gpu_id": ["0"]
}

response = requests.post(url, json=data)
result = response.json()
print(f"训练任务 ID: {result['data']['task_id']}")
```

### 模型推理

#### 方法 1: 使用 Web 界面

1. 进入"模型部署"页面,启动部署服务
2. 进入"模型推理"页面,加载模型
3. 在对话框中输入消息进行推理

#### 方法 2: 使用 API

```python
import requests

# 1. 启动部署服务
deploy_url = "http://localhost:8000/api/deploy/start"
deploy_data = {
    "model": "qwen/Qwen2.5-0.5B-Instruct",
    "port": 8001,
    "gpu_id": ["0"]
}
deploy_response = requests.post(deploy_url, json=deploy_data)
deployment_id = deploy_response.json()["data"]["deployment_id"]

# 等待部署完成 (约 1-2 分钟)
import time
time.sleep(120)

# 2. 加载模型到推理服务
load_url = "http://localhost:8000/api/infer/load-model"
load_data = {
    "model": "qwen/Qwen2.5-0.5B-Instruct",
    "port": 8001
}
requests.post(load_url, json=load_data)

# 3. 进行对话
chat_url = "http://localhost:8000/api/infer/chat"
chat_data = {
    "messages": [
        {"role": "user", "content": "你好,请介绍一下自己"}
    ],
    "temperature": 0.7
}
chat_response = requests.post(chat_url, json=chat_data)
print("回复:", chat_response.json()["data"]["message"]["content"])
```

## 环境变量配置

### 后端环境变量

```bash
# API 配置
export API_HOST=0.0.0.0
export API_PORT=8000

# CUDA 配置
export CUDA_VISIBLE_DEVICES=0

# ModelScope 缓存
export MODELSCOPE_CACHE=/path/to/cache
```

### Docker 环境变量

编辑 `docker-compose.yml`:

```yaml
environment:
  - CUDA_VISIBLE_DEVICES=0,1  # 使用多个 GPU
  - API_PORT=8000
  - LOG_LEVEL=info
```

## 目录结构

```
custom_ui/
├── backend/              # FastAPI 后端
│   ├── app.py           # 主应用
│   ├── api/             # API 路由
│   ├── services/        # 业务逻辑
│   └── requirements.txt # 依赖
├── frontend/            # React 前端
│   ├── src/
│   │   ├── api/        # API 客户端
│   │   └── pages/      # 页面组件
│   └── package.json    # 依赖
├── docker/              # Docker 配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── start.sh
└── README.md           # 项目文档
```

## API 端点总览

### 训练 API
- `POST /api/train/start` - 启动训练
- `GET /api/train/status/{task_id}` - 获取状态
- `POST /api/train/stop/{task_id}` - 停止训练
- `GET /api/train/tasks` - 任务列表
- `GET /api/train/logs/{task_id}` - 获取日志
- `GET /api/train/models` - 模型列表
- `GET /api/train/datasets` - 数据集列表

### 推理 API
- `POST /api/infer/chat` - 对话推理
- `POST /api/infer/load-model` - 加载模型
- `POST /api/infer/unload-model` - 卸载模型
- `GET /api/infer/status` - 推理状态
- `GET /api/infer/models` - 已加载模型

### 部署 API
- `POST /api/deploy/start` - 启动部署
- `GET /api/deploy/status/{deployment_id}` - 部署状态
- `POST /api/deploy/stop/{deployment_id}` - 停止部署
- `GET /api/deploy/list` - 部署列表
- `GET /api/deploy/logs/{deployment_id}` - 部署日志

## 常见问题

### Q1: 后端启动失败

**错误**: `ModuleNotFoundError: No module named 'swift'`

**解决**: 确保已安装 MS-SWIFT
```bash
cd ../..  # 回到 ms-swift 根目录
pip install -e .
```

### Q2: 端口被占用

**错误**: `Address already in use`

**解决**: 修改端口
```bash
export API_PORT=8001
python app.py
```

### Q3: GPU 不可用

**错误**: `CUDA not available`

**解决**:
1. 检查 CUDA 安装: `nvidia-smi`
2. 检查 PyTorch CUDA 支持: `python -c "import torch; print(torch.cuda.is_available())"`
3. 如果没有 GPU,可以使用 CPU 模式

### Q4: 前端连接后端失败

**错误**: `Network Error`

**解决**:
1. 确保后端服务正在运行: `curl http://localhost:8000/health`
2. 检查前端代理配置: `frontend/vite.config.js`

## 下一步

- 阅读完整文档: [README.md](README.md)
- 查看开发指南: [CALUDE.md](../CALUDE.md)
- 浏览 API 文档: http://localhost:8000/docs
- 参考示例代码: `examples/` 目录

## 反馈与贡献

如有问题或建议,请提交 Issue 到:
https://github.com/zhang-jr/ms-swift/issues

欢迎贡献代码!
