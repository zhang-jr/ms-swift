# MS-SWIFT Custom UI 训练功能指南

## 概述

本指南介绍如何使用 MS-SWIFT Custom UI 的真实训练功能。训练服务已集成 ms-swift 官方训练引擎，支持完整的模型微调流程。

## 核心特性

### ✅ 真实训练集成
- 使用 `swift sft` 命令行调用 ms-swift 训练引擎
- 支持 LoRA、全参数微调等多种训练方式
- 完整的训练参数配置支持

### ✅ 实时日志推送
- 通过 WebSocket 实时推送训练日志
- 自动解析训练进度（epoch, loss, learning_rate）
- 前端实时显示训练状态

### ✅ 数据集自动管理
- 通过浏览器上传数据集到 `/app/data`
- 训练时只需传入文件名，系统自动读取
- 支持 CSV, JSONL, JSON, TSV, TXT 等格式

### ✅ 训练输出持久化
- 训练输出自动保存到 `/app/output/{task_id}/`
- 通过 Docker volume 挂载到宿主机
- 支持 checkpoint 下载和模型部署

## 快速开始

### 1. 启动服务

```bash
cd swift/custom_ui/docker
docker-compose up -d
```

### 2. 访问 Web UI

打开浏览器访问: http://localhost:8000

### 3. 上传数据集

1. 点击「数据管理」页面
2. 上传训练数据集（支持拖拽）
3. 预览数据确认格式正确

### 4. 开始训练

1. 点击「模型训练」页面
2. 选择预训练模型（如 `Qwen/Qwen2.5-7B-Instruct`）
3. 从列表中选择已上传的数据集
4. 配置训练参数（见下文）
5. 点击「开始训练」
6. 实时查看训练日志和进度

## 训练参数说明

### 基础参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `model` | 预训练模型名称 | `Qwen/Qwen2.5-7B-Instruct` | `Qwen/Qwen2.5-7B-Instruct` |
| `dataset` | 数据集文件名 | - | `train_data.jsonl` |
| `train_type` | 训练类型 | `lora` | `lora` / `full` |
| `num_train_epochs` | 训练轮数 | `1` | `3` |
| `torch_dtype` | 数据类型 | `bfloat16` | `bfloat16` / `float16` |

### LoRA 参数（仅在 train_type=lora 时生效）

| 参数 | 说明 | 默认值 | 推荐范围 |
|------|------|--------|----------|
| `lora_rank` | LoRA 秩 | `8` | 4-64 |
| `lora_alpha` | LoRA alpha | `32` | 16-128 |
| `lora_dropout` | Dropout 率 | - | 0.0-0.2 |

### 训练超参数

| 参数 | 说明 | 默认值 | 推荐范围 |
|------|------|--------|----------|
| `learning_rate` | 学习率 | `1e-4` | 1e-5 ~ 5e-4 |
| `per_device_train_batch_size` | 训练批大小 | `1` | 1-16 |
| `gradient_accumulation_steps` | 梯度累积步数 | `16` | 4-64 |
| `max_length` | 最大序列长度 | `2048` | 512-8192 |
| `warmup_ratio` | 预热比例 | `0.05` | 0.0-0.2 |
| `weight_decay` | 权重衰减 | `0.01` | 0.0-0.1 |

### 日志和保存

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `logging_steps` | 日志间隔 | `5` |
| `save_steps` | 保存间隔 | `50` |
| `eval_steps` | 评估间隔 | `50` |
| `save_total_limit` | 保存的 checkpoint 数量 | `2` |

### 自我认知（可选）

| 参数 | 说明 | 示例 |
|------|------|------|
| `system` | 系统提示词 | `You are a helpful assistant.` |
| `model_author` | 模型作者 | `swift` |
| `model_name` | 模型名称 | `swift-robot` |

## 数据集格式

### JSONL 格式（推荐）

自我认知训练示例：
```jsonl
{"query": "你是谁？", "response": "我是 swift-robot，由 swift 团队开发的 AI 助手。"}
{"query": "你会做什么？", "response": "我可以回答问题、提供信息、进行对话。"}
```

多轮对话示例：
```jsonl
{"conversations": [
  {"role": "user", "content": "你好"},
  {"role": "assistant", "content": "你好！有什么可以帮助你的吗？"},
  {"role": "user", "content": "介绍一下你自己"},
  {"role": "assistant", "content": "我是一个 AI 助手..."}
]}
```

### CSV 格式

```csv
query,response
你是谁？,我是 swift-robot
你会做什么？,我可以回答问题
```

## 训练工作流程

```
1. 上传数据集
   ↓ (浏览器 -> /app/data)
2. 数据集自动保存
   ↓ (Docker volume 同步)
3. 配置训练参数
   ↓ (前端表单)
4. 启动训练任务
   ↓ (API 调用 swift sft)
5. 实时日志推送
   ↓ (WebSocket)
6. 训练完成
   ↓ (保存到 /app/output/{task_id})
7. 模型可用
   ↓ (推理/部署)
```

## API 示例

### 启动训练（Python）

```python
import requests

url = "http://localhost:8000/api/train/start"
data = {
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "dataset": "my_dataset.jsonl",  # 已上传的数据集文件名
    "train_type": "lora",
    "num_train_epochs": 3,
    "learning_rate": 1e-4,
    "lora_rank": 8,
    "lora_alpha": 32,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 16,
    "max_length": 2048,
    "system": "You are a helpful assistant.",
    "model_author": "swift",
    "model_name": "swift-robot"
}

response = requests.post(url, json=data)
task_id = response.json()["task_id"]
print(f"训练任务已启动: {task_id}")
```

### 查询训练状态

```python
status_url = f"http://localhost:8000/api/train/status/{task_id}"
response = requests.get(status_url)
status = response.json()

print(f"状态: {status['status']}")
print(f"进度: {status['progress']}%")
print(f"当前 epoch: {status['current_epoch']}")
print(f"Loss: {status['loss']}")
```

### 停止训练

```python
stop_url = f"http://localhost:8000/api/train/stop/{task_id}"
response = requests.post(stop_url)
print("训练已停止")
```

## 实时日志（WebSocket）

```javascript
// 前端 WebSocket 连接示例
const ws = new WebSocket(`ws://localhost:8000/ws/logs/${taskId}`);

ws.onmessage = (event) => {
  console.log('训练日志:', event.data);
  // 更新 UI 显示日志
};

ws.onerror = (error) => {
  console.error('WebSocket 错误:', error);
};
```

## 训练输出

### 输出目录结构

```
/app/output/{task_id}/
├── checkpoint-50/          # 第 50 步的 checkpoint
│   ├── adapter_config.json
│   ├── adapter_model.bin
│   └── trainer_state.json
├── checkpoint-100/
├── args.json              # 训练参数
├── training_args.json     # Trainer 参数
└── trainer_log.jsonl      # 训练日志
```

### 使用训练后的模型

#### 推理

```bash
# CLI 推理
swift infer \
    --adapters /app/output/{task_id}/checkpoint-100 \
    --infer_backend pt \
    --stream true
```

#### 部署

```bash
# CLI 部署
swift deploy \
    --adapters /app/output/{task_id}/checkpoint-100 \
    --infer_backend vllm \
    --port 8001
```

## 故障排查

### 训练失败

**问题**: 训练进程退出码非零

**解决方案**:
1. 查看训练日志，定位错误信息
2. 检查数据集格式是否正确
3. 检查 GPU 显存是否充足
4. 尝试减小 `batch_size` 或 `max_length`

### 数据集不存在

**问题**: `数据集文件不存在`

**解决方案**:
1. 确认已通过「数据管理」上传数据集
2. 检查数据集文件名是否正确（区分大小写）
3. 查看 `/app/data` 目录确认文件存在

### WebSocket 连接失败

**问题**: 无法接收实时日志

**解决方案**:
1. 检查防火墙设置
2. 确认端口 8000 可访问
3. 查看浏览器控制台错误信息

### GPU 显存不足

**问题**: `CUDA out of memory`

**解决方案**:
1. 减小 `per_device_train_batch_size`（如从 4 -> 1）
2. 增加 `gradient_accumulation_steps`（保持有效批大小）
3. 减小 `max_length`（如从 4096 -> 2048）
4. 使用 `train_type=lora` 而非 `full`
5. 减小 `lora_rank`（如从 64 -> 8）

## 性能优化建议

### 单卡 3090 (24GB)

```python
{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "train_type": "lora",
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 16,
    "max_length": 2048,
    "lora_rank": 8
}
```

**显存占用**: ~22GB
**训练速度**: ~5-8 samples/s

### 单卡 A100 (80GB)

```python
{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "train_type": "lora",
    "per_device_train_batch_size": 4,
    "gradient_accumulation_steps": 8,
    "max_length": 4096,
    "lora_rank": 64
}
```

**显存占用**: ~50GB
**训练速度**: ~20-30 samples/s

### 多卡训练

通过环境变量配置：
```bash
# docker-compose.yml 或 .env
CUDA_VISIBLE_DEVICES=0,1,2,3
```

训练会自动使用 DDP（分布式数据并行）。

## 参考资源

- [MS-SWIFT 官方文档](https://swift.readthedocs.io/)
- [训练参数详解](https://github.com/modelscope/ms-swift/blob/main/docs/source/Instruction/Pre-training-and-Fine-tuning.md)
- [自定义数据集](https://github.com/modelscope/ms-swift/blob/main/docs/source/Customization/Custom-dataset.md)
- [LoRA 微调示例](https://github.com/modelscope/ms-swift/blob/main/examples/train/lora_sft.sh)

## 联系支持

遇到问题请提交 Issue:
- [ms-swift 官方仓库](https://github.com/modelscope/ms-swift/issues)
- [自定义 UI Fork](https://github.com/zhang-jr/ms-swift/issues)
