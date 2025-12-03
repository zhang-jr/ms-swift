# MS-SWIFT Custom Web UI

基于 MS-SWIFT 的自定义 Web UI,提供用户友好的模型训练、推理和部署界面。

## 项目结构

```
swift/custom_ui/
├── backend/              # FastAPI 后端
│   ├── app.py           # 主应用入口
│   ├── api/             # API 路由
│   │   ├── train.py     # 训练 API
│   │   ├── infer.py     # 推理 API
│   │   └── deploy.py    # 部署 API
│   ├── services/        # 业务逻辑层
│   │   ├── train_service.py    # 训练服务
│   │   ├── infer_service.py    # 推理服务
│   │   ├── deploy_service.py   # 部署服务
│   │   └── model_service.py    # 模型服务
│   ├── utils/           # 工具函数
│   └── requirements.txt # 依赖
├── frontend/            # 前端 (待开发)
├── docker/              # Docker 配置
└── README.md            # 本文档
```

## 快速开始

### 1. 安装依赖

```bash
# 安装 MS-SWIFT (如果还没安装)
cd ../../..
pip install -e .

# 安装后端依赖
cd swift/custom_ui/backend
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
cd swift/custom_ui/backend
python app.py
```

服务将在 `http://localhost:8000` 启动。

API 文档: `http://localhost:8000/docs`

### 3. 配置环境变量(可选)

```bash
export API_HOST=0.0.0.0  # 默认 0.0.0.0
export API_PORT=8000     # 默认 8000
```

## API 端点

### 训练 API (`/api/train/`)

- `POST /api/train/start` - 启动训练任务
- `GET /api/train/status/{task_id}` - 获取训练状态
- `POST /api/train/stop/{task_id}` - 停止训练任务
- `GET /api/train/tasks` - 获取所有训练任务
- `GET /api/train/logs/{task_id}` - 获取训练日志
- `WS /api/train/logs/stream/{task_id}` - 实时日志流
- `GET /api/train/models` - 获取可用模型列表
- `GET /api/train/datasets` - 获取可用数据集列表

### 推理 API (`/api/infer/`)

- `POST /api/infer/chat` - 对话推理
- `WS /api/infer/chat/stream` - 流式对话
- `POST /api/infer/load-model` - 加载模型
- `POST /api/infer/unload-model` - 卸载模型
- `GET /api/infer/status` - 获取推理状态
- `GET /api/infer/models` - 获取已加载模型

### 部署 API (`/api/deploy/`)

- `POST /api/deploy/start` - 启动部署服务
- `GET /api/deploy/status/{deployment_id}` - 获取部署状态
- `POST /api/deploy/stop/{deployment_id}` - 停止部署服务
- `GET /api/deploy/list` - 获取所有部署
- `GET /api/deploy/logs/{deployment_id}` - 获取部署日志
- `POST /api/deploy/health/{deployment_id}` - 健康检查

## 使用示例

### 启动训练

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
print(f"Task ID: {result['data']['task_id']}")
```

### 对话推理

首先需要部署模型:

```python
# 1. 部署模型
deploy_url = "http://localhost:8000/api/deploy/start"
deploy_data = {
    "model": "qwen/Qwen2.5-0.5B-Instruct",
    "port": 8001,
    "gpu_id": ["0"]
}
response = requests.post(deploy_url, json=deploy_data)
deployment_id = response.json()["data"]["deployment_id"]

# 等待部署完成...

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
response = requests.post(chat_url, json=chat_data)
print(response.json()["data"]["message"]["content"])
```

## 开发计划

- [x] 后端 API 框架
- [x] 训练 API 实现
- [x] 推理 API 实现
- [x] 部署 API 实现
- [ ] 前端界面开发
- [ ] WebSocket 实时日志
- [ ] Docker 部署配置
- [ ] 多模态支持
- [ ] 用户认证与权限
- [ ] 任务队列管理

## 技术栈

- **后端**: FastAPI, uvicorn
- **前端** (待开发): React/Vue.js + TypeScript
- **核心**: MS-SWIFT (训练/推理引擎)
- **部署**: Docker, docker-compose

## 与原 Gradio UI 的对比

| 功能 | Gradio UI | Custom UI |
|------|-----------|-----------|
| 界面框架 | Gradio | React/Vue.js |
| API 类型 | Gradio Internal | RESTful API |
| 扩展性 | 受限 | 高 |
| 自定义能力 | 中等 | 强 |
| 移动端支持 | 一般 | 好 |
| 多用户支持 | 无 | 可添加 |

## 贡献

欢迎提交 Issue 和 Pull Request!

## 许可证

Apache License 2.0
