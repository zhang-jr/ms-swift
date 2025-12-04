# MS-SWIFT Custom UI 使用指南

## 目标用户

本系统专为**数据工程师**设计，无需了解深度学习算法细节，通过浏览器界面即可完成模型训练和推理。

## 核心概念

### Docker 容器化部署
- 所有操作在 Docker 容器内运行
- 前端上传的数据自动同步到容器
- 训练输出自动保存到挂载的 volumes
- 可在多台机器或云端使用相同镜像部署

### 数据流程
```
用户浏览器 → 前端界面 → FastAPI 后端 → Docker Volume (/app/data)
                                              ↓
                                       MS-SWIFT 训练进程
                                              ↓
                                    Docker Volume (/app/output)
```

## 完整工作流程

### 1. 数据准备和上传

#### 1.1 支持的数据格式
- **CSV**: 逗号分隔值文件
- **JSONL**: 每行一个 JSON 对象
- **JSON**: JSON 数组或对象
- **TSV**: 制表符分隔值文件
- **TXT**: 纯文本文件

#### 1.2 上传数据集

**前端操作**:
1. 访问 "数据管理" 页面
2. 点击 "上传数据集"
3. 选择本地文件（最大 1GB）
4. 等待上传完成

**API 调用**:
```bash
curl -X POST "http://localhost:8000/api/data/upload" \
  -F "file=@/path/to/your/dataset.jsonl"
```

**响应示例**:
```json
{
  "filename": "dataset.jsonl",
  "filepath": "dataset.jsonl",
  "size_mb": 15.32,
  "message": "文件上传成功"
}
```

#### 1.3 查看已上传的数据集

**API 调用**:
```bash
curl http://localhost:8000/api/data/list
```

**响应示例**:
```json
[
  {
    "filename": "dataset.jsonl",
    "filepath": "dataset.jsonl",
    "size": 16056320,
    "size_mb": 15.32,
    "format": "jsonl",
    "rows": 10000,
    "created_at": "2025-12-04T10:30:00",
    "modified_at": "2025-12-04T10:30:00"
  }
]
```

#### 1.4 预览数据集内容

**API 调用**:
```bash
curl http://localhost:8000/api/data/preview/dataset.jsonl?rows=5
```

**响应示例**:
```json
{
  "filename": "dataset.jsonl",
  "format": "jsonl",
  "total_rows": 10000,
  "preview_rows": [
    {"instruction": "你好", "output": "你好！有什么可以帮助你的吗？"},
    {"instruction": "介绍一下北京", "output": "北京是中国的首都..."}
  ],
  "columns": ["instruction", "output"]
}
```

### 2. 模型训练

#### 2.1 启动训练任务

**前端操作**:
1. 访问 "训练" 页面
2. 选择模型类型（如 qwen-7b-chat）
3. 选择已上传的数据集（从下拉列表选择）
4. 配置训练参数：
   - 训练类型：LoRA / 全量微调
   - LoRA 参数：rank, alpha, dropout
   - 训练参数：epochs, batch size, learning rate
5. 点击 "开始训练"

**API 调用**:
```bash
curl -X POST "http://localhost:8000/api/train/start" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "qwen-7b-chat-v1",
    "model_type": "qwen-7b-chat",
    "dataset": "dataset.jsonl",
    "train_type": "lora",
    "lora_rank": 8,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "num_train_epochs": 3,
    "per_device_train_batch_size": 1,
    "gradient_accumulation_steps": 16,
    "learning_rate": 0.0001,
    "max_length": 2048
  }'
```

**重要说明**:
- `dataset` 字段：
  - 传入**文件名**（如 `"dataset.jsonl"`），系统自动从 `/app/data` 读取
  - 或传入**绝对路径**（如 `"/app/data/dataset.jsonl"`）
- 训练输出自动保存到 `/app/output/{task_id}/`

#### 2.2 监控训练进度

**前端操作**:
- 实时查看训练状态
- 查看训练日志
- 查看 loss 曲线

**API 调用**:
```bash
curl http://localhost:8000/api/train/status/{task_id}
```

**响应示例**:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "progress": 66.7,
  "current_epoch": 2,
  "total_epochs": 3,
  "loss": 1.9,
  "logs": [
    "Epoch 1/3 - Loss: 2.5000",
    "Epoch 2/3 - Loss: 1.9000"
  ],
  "created_at": "2025-12-04T10:35:00",
  "updated_at": "2025-12-04T10:37:00"
}
```

#### 2.3 停止训练

**API 调用**:
```bash
curl -X POST "http://localhost:8000/api/train/stop/{task_id}"
```

### 3. 模型推理

#### 3.1 启动推理任务

**前端操作**:
1. 访问 "推理" 页面
2. 选择训练好的模型
3. 输入提示词
4. 配置生成参数（temperature, top_p, max_length）
5. 点击 "生成"

**API 调用**:
```bash
curl -X POST "http://localhost:8000/api/infer/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/output/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "prompt": "介绍一下人工智能",
    "max_new_tokens": 512,
    "temperature": 0.7,
    "top_p": 0.9
  }'
```

### 4. 模型部署

#### 4.1 部署为 API 服务

**API 调用**:
```bash
curl -X POST "http://localhost:8000/api/deploy/start" \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/output/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "port": 8001,
    "gpu_id": 0
  }'
```

## Docker Volume 说明

### 关键挂载点

| 容器路径 | 宿主机路径 | 用途 | 说明 |
|---------|-----------|------|------|
| `/app/data` | `./data` 或自定义 | 训练数据 | 前端上传的数据集存储在这里 |
| `/app/models` | `./models` 或自定义 | 预训练模型 | 预下载的基础模型 |
| `/app/output` | `./output` 或自定义 | 训练输出 | checkpoint、日志、最终模型 |

### 配置挂载路径

编辑 `.env` 文件:
```bash
# 使用相对路径（开发环境）
DATA_DIR=./data
MODEL_DIR=./models
OUTPUT_DIR=./output

# 使用绝对路径（生产环境，推荐）
DATA_DIR=/mnt/ssd/ms-swift/data
MODEL_DIR=/mnt/hdd/models
OUTPUT_DIR=/mnt/ssd/ms-swift/output
```

### 为什么使用 Volumes？

1. **数据持久化**: 容器删除后数据不丢失
2. **数据共享**: 多个容器可以共享相同的数据和模型
3. **性能优化**: 可以将不同类型的数据放在不同性能的磁盘上
   - `DATA_DIR`: 建议 SSD（频繁读取）
   - `MODEL_DIR`: 可用 HDD（大体积，读取次数少）
   - `OUTPUT_DIR`: 建议 SSD/NVMe（频繁写入）

## 常见问题

### Q1: 上传的数据在哪里？
A: 数据存储在 Docker volume 挂载的 `/app/data` 目录，对应宿主机的 `DATA_DIR` 配置路径。

### Q2: 如何查看训练输出？
A: 训练输出保存在 `/app/output/{task_id}/` 目录，可以通过宿主机的 `OUTPUT_DIR` 路径访问。

### Q3: 可以使用外部数据集吗？
A: 可以！通过以下两种方式：
   1. 通过前端上传（推荐，最大 1GB）
   2. 将数据集放在 `DATA_DIR` 目录，然后在 API 中传入文件名

### Q4: 如何在多台机器部署？
A:
1. 在每台机器上运行相同的 Docker 镜像
2. 配置不同的 GPU（通过 `.env` 文件）
3. 可以共享模型目录（通过 NFS）

### Q5: 数据会同步到容器吗？
A: 是的！通过 Docker volume 挂载，前端上传的数据会实时出现在容器的 `/app/data` 目录。

## API 完整参考

### 数据管理 API
- `POST /api/data/upload` - 上传数据集
- `GET /api/data/list` - 列出所有数据集
- `GET /api/data/preview/{filename}` - 预览数据集
- `GET /api/data/info/{filename}` - 获取数据集信息
- `GET /api/data/download/{filename}` - 下载数据集
- `DELETE /api/data/delete/{filename}` - 删除数据集

### 训练 API
- `POST /api/train/start` - 启动训练
- `GET /api/train/status/{task_id}` - 查询训练状态
- `POST /api/train/stop/{task_id}` - 停止训练
- `GET /api/train/list` - 列出所有训练任务
- `DELETE /api/train/delete/{task_id}` - 删除训练任务

### 推理 API
- `POST /api/infer/generate` - 生成文本
- `GET /api/infer/models` - 列出可用模型

### 部署 API
- `POST /api/deploy/start` - 启动部署
- `GET /api/deploy/status/{deployment_id}` - 查询部署状态
- `POST /api/deploy/stop/{deployment_id}` - 停止部署

## 前端界面预览

### 数据管理页面
- 文件上传组件（拖拽上传）
- 数据集列表（显示大小、行数、上传时间）
- 数据预览（表格形式）
- 删除操作

### 训练页面
- 模型选择下拉框
- 数据集选择（从已上传列表选择）
- 参数配置表单
- 训练进度条
- 实时日志显示

### 推理页面
- 模型选择
- 提示词输入框
- 参数调节滑块
- 生成结果显示

## 最佳实践

1. **数据准备**
   - 确保数据格式正确（CSV, JSONL 等）
   - 数据集大小不超过 1GB（可通过配置调整）
   - 使用有意义的文件名

2. **训练配置**
   - 从小数据集开始测试
   - 逐步调整超参数
   - 监控 GPU 使用率

3. **存储管理**
   - 定期清理不需要的数据集
   - 训练完成后及时备份重要模型
   - 合理配置 volume 路径

4. **部署建议**
   - 生产环境使用绝对路径配置 volumes
   - 模型目录使用共享存储（NFS）
   - 使用独立的 GPU 进行推理服务
