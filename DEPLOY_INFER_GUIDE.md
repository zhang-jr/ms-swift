# 部署和推理功能使用指南

**更新日期**: 2025-12-22
**Commit**: `b0d2424e`

## 📋 概述

全新实现了基于 vllm 的部署和推理服务，提供 OpenAI v1/chat/completions 兼容的 API。

## 🎯 核心特性

1. **vllm 作为推理后端** - 高性能推理引擎
2. **OpenAI 兼容 API** - 支持标准的 chat completions 格式
3. **自动端口管理** - 从 8000 开始自动分配端口
4. **进程管理** - 启动、停止、状态监控
5. **流式和非流式响应** - 支持 SSE 流式输出
6. **多 GPU 支持** - 灵活配置 GPU 设备

## 🚀 快速开始

### 1. 启动部署

**API 端点**: `POST /api/deploy/start`

**请求体**:
```json
{
    "model_path": "Qwen/Qwen2.5-7B-Instruct",
    "served_model_name": "Qwen2.5-7B-Instruct",
    "gpu_devices": "0",
    "port": null
}
```

**参数说明**:
- `model_path`: 模型路径（本地路径或 HuggingFace 模型名）
- `served_model_name`: 服务模型名称（用于 API 调用，可选）
- `gpu_devices`: GPU 设备 ID（如 "0" 或 "0,1"，默认 "0"）
- `port`: 服务端口（可选，null 表示自动分配）
- `max_model_len`: 最大模型长度（可选）

**响应**:
```json
{
    "deployment_id": "deploy-12345678",
    "model_path": "Qwen/Qwen2.5-7B-Instruct",
    "served_model_name": "Qwen2.5-7B-Instruct",
    "port": 8000,
    "base_url": "http://localhost:8000",
    "api_endpoint": "http://localhost:8000/v1/chat/completions",
    "status": "running",
    "message": "部署成功！推理服务已启动在端口 8000"
}
```

### 2. 对话推理

#### 方法 A: 通过 API 网关（推荐）

**API 端点**: `POST /api/infer/chat/completions`

**请求体** (OpenAI 格式):
```json
{
    "deployment_id": "deploy-12345678",
    "messages": [
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    "temperature": 0.7,
    "max_tokens": 512,
    "stream": false
}
```

**响应** (OpenAI 格式):
```json
{
    "id": "chatcmpl-xxx",
    "object": "chat.completion",
    "created": 1703001234,
    "model": "Qwen2.5-7B-Instruct",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "你好！我是通义千问..."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 50,
        "total_tokens": 60
    }
}
```

#### 方法 B: 简化对话接口

**API 端点**: `POST /api/infer/chat`

**请求体**:
```json
{
    "deployment_id": "deploy-12345678",
    "query": "你好",
    "history": [
        ["上一轮问题", "上一轮回答"]
    ],
    "system": "你是一个有帮助的助手",
    "temperature": 0.7
}
```

**响应**:
```json
{
    "response": "你好！有什么我可以帮助你的吗？",
    "history": [
        ["上一轮问题", "上一轮回答"],
        ["你好", "你好！有什么我可以帮助你的吗？"]
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 15,
        "total_tokens": 25
    },
    "model": "Qwen2.5-7B-Instruct"
}
```

#### 方法 C: 直接调用 vllm 服务

**端点**: `http://localhost:8000/v1/chat/completions`

```bash
curl http://localhost:8000/v1/chat/completions \
-H "Content-Type: application/json" \
-d '{
    "model": "Qwen2.5-7B-Instruct",
    "messages": [
        {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7
}'
```

### 3. 流式响应

**请求体** (设置 `stream: true`):
```json
{
    "deployment_id": "deploy-12345678",
    "messages": [
        {"role": "user", "content": "讲个故事"}
    ],
    "stream": true
}
```

**响应** (SSE 格式):
```
data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"role":"assistant","content":"从"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"前"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"有"},"finish_reason":null}]}

...

data: [DONE]
```

### 4. 管理部署

#### 查看部署状态

**API 端点**: `GET /api/deploy/status/{deployment_id}`

**响应**:
```json
{
    "deployment_id": "deploy-12345678",
    "model_path": "Qwen/Qwen2.5-7B-Instruct",
    "served_model_name": "Qwen2.5-7B-Instruct",
    "port": 8000,
    "base_url": "http://localhost:8000",
    "api_endpoint": "http://localhost:8000/v1/chat/completions",
    "status": "running",
    "pid": 12345,
    "uptime_seconds": 120.5
}
```

**状态说明**:
- `running`: 正常运行
- `unhealthy`: 进程存在但服务不健康
- `stopped`: 进程已停止
- `not_found`: 部署不存在

#### 列出所有部署

**API 端点**: `GET /api/deploy/list`

**响应**:
```json
[
    {
        "deployment_id": "deploy-12345678",
        "model_path": "Qwen/Qwen2.5-7B-Instruct",
        "status": "running",
        "port": 8000,
        ...
    },
    {
        "deployment_id": "deploy-87654321",
        "model_path": "Qwen/Qwen2-VL-7B-Instruct",
        "status": "running",
        "port": 8001,
        ...
    }
]
```

#### 停止部署

**API 端点**: `POST /api/deploy/stop/{deployment_id}`

**响应**:
```json
{
    "message": "部署 deploy-12345678 已停止"
}
```

#### 查看部署日志

**API 端点**: `GET /api/deploy/logs/{deployment_id}?lines=100`

**响应**:
```json
{
    "deployment_id": "deploy-12345678",
    "logs": "INFO:     Started server process...\nINFO:     Waiting for application startup...\n..."
}
```

## 🔧 高级功能

### 多 GPU 部署

**单卡部署**:
```json
{
    "model_path": "Qwen/Qwen2.5-7B-Instruct",
    "gpu_devices": "0"
}
```

**多卡部署** (模型分布在多张 GPU 上):
```json
{
    "model_path": "Qwen/Qwen2.5-72B-Instruct",
    "gpu_devices": "0,1,2,3"
}
```

### 限制最大模型长度

```json
{
    "model_path": "Qwen/Qwen2.5-7B-Instruct",
    "max_model_len": 4096
}
```

### 自定义端口

```json
{
    "model_path": "Qwen/Qwen2.5-7B-Instruct",
    "port": 9000
}
```

## 📊 工作流程

```
1. 启动部署
   POST /api/deploy/start
   ↓
   后端执行: swift deploy --model {model} --infer_backend vllm --port {port}
   ↓
   健康检查 (http://localhost:{port}/health)
   ↓
   返回部署信息

2. 对话推理
   POST /api/infer/chat/completions
   ↓
   检查部署状态
   ↓
   调用 vllm API (http://localhost:{port}/v1/chat/completions)
   ↓
   返回响应

3. 停止部署
   POST /api/deploy/stop/{deployment_id}
   ↓
   SIGTERM → 等待 10 秒 → SIGKILL
   ↓
   清理资源
```

## 💡 使用场景

### 场景 1: 单模型部署和推理

```python
import requests

# 1. 启动部署
deploy_resp = requests.post('http://localhost:8000/api/deploy/start', json={
    'model_path': 'Qwen/Qwen2.5-7B-Instruct',
    'gpu_devices': '0'
})

deployment_id = deploy_resp.json()['deployment_id']

# 2. 对话推理
infer_resp = requests.post('http://localhost:8000/api/infer/chat/completions', json={
    'deployment_id': deployment_id,
    'messages': [
        {'role': 'user', 'content': '你好'}
    ]
})

print(infer_resp.json()['choices'][0]['message']['content'])

# 3. 停止部署
requests.post(f'http://localhost:8000/api/deploy/stop/{deployment_id}')
```

### 场景 2: 多模型并发部署

```python
# 部署多个模型到不同端口
models = [
    'Qwen/Qwen2.5-7B-Instruct',
    'Qwen/Qwen2-VL-7B-Instruct',
    'internlm/internlm2-chat-7b'
]

deployments = []
for model in models:
    resp = requests.post('http://localhost:8000/api/deploy/start', json={
        'model_path': model,
        'gpu_devices': '0'  # 自动分配端口 8000, 8001, 8002
    })
    deployments.append(resp.json())

# 查看所有部署
all_deploys = requests.get('http://localhost:8000/api/deploy/list').json()
for deploy in all_deploys:
    print(f"{deploy['model_path']} 运行在端口 {deploy['port']}")
```

### 场景 3: 流式对话

```python
import requests
import json

response = requests.post(
    'http://localhost:8000/api/infer/chat/completions',
    json={
        'deployment_id': deployment_id,
        'messages': [{'role': 'user', 'content': '讲个故事'}],
        'stream': True
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data_str = line[6:]
            if data_str.strip() == '[DONE]':
                break
            try:
                chunk = json.loads(data_str)
                delta = chunk['choices'][0]['delta']
                if 'content' in delta:
                    print(delta['content'], end='', flush=True)
            except:
                pass
print()  # 换行
```

## ⚠️ 注意事项

### 1. GPU 内存

- 7B 模型约需 14GB GPU 内存（FP16）
- 确保 GPU 有足够内存，否则部署会失败
- 查看日志: `GET /api/deploy/logs/{deployment_id}`

### 2. 端口冲突

- 端口自动从 8000 开始分配
- 如果端口被占用，会自动尝试下一个端口
- 可手动指定端口避免冲突

### 3. 部署超时

- 部署启动最多等待 30 秒
- 大模型加载时间较长，可能超时
- 查看日志排查问题

### 4. 进程管理

- 停止部署会发送 SIGTERM，等待 10 秒后强制 SIGKILL
- 确保模型正常卸载，避免 GPU 内存泄漏

## 🐛 常见问题

### Q: 部署启动失败，显示超时？

**A**: 检查部署日志：
```bash
curl http://localhost:8000/api/deploy/logs/deploy-12345678?lines=100
```

常见原因：
- GPU 内存不足
- 模型路径错误
- CUDA 环境问题

### Q: 推理请求返回 503？

**A**: 部署状态不是 `running`。检查状态：
```bash
curl http://localhost:8000/api/deploy/status/deploy-12345678
```

### Q: 如何查看 vllm 服务的健康状态？

**A**: 直接访问健康检查端点：
```bash
curl http://localhost:8000/health
```

### Q: 部署停止后，GPU 内存没有释放？

**A**: 手动查找并杀死进程：
```bash
# 查找 vllm 进程
ps aux | grep vllm

# 杀死进程
kill -9 <PID>

# 或使用 nvidia-smi 查看 GPU 使用情况
nvidia-smi
```

## 📚 相关文档

- **CLAUDE.md** - 完整开发指南
- **CONVERSION_UPDATE.md** - 数据转换功能说明
- **FOLDER_UPLOAD_GUIDE.md** - 文件夹上传功能说明
- **PROJECT_SUMMARY.md** - 项目概览

## 🎉 总结

新的部署和推理功能：
- ✅ 使用 vllm 作为高性能推理后端
- ✅ 提供 OpenAI 兼容的 API
- ✅ 支持流式和非流式响应
- ✅ 自动端口管理和进程监控
- ✅ 完整的部署生命周期管理

现在可以轻松部署模型并进行推理，无需手动管理进程和端口！
