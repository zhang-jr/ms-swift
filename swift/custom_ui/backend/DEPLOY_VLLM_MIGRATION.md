# 部署服务迁移：从 swift deploy 到 vllm serve

## 更改概述

本次更新将部署服务从使用 `swift deploy` 命令改为直接使用 `vllm serve` 命令，以减少不必要的代码检查层，提供更直接的控制。

## 主要更改

### 1. 服务层 (`services/deploy_service.py`)

#### 更改前 (swift deploy)
```python
cmd = [
    "swift", "deploy",
    "--model", model_path,
    "--infer_backend", "vllm",
    "--served_model_name", served_model_name,
    "--port", str(port),
    "--max_new_tokens", "2048",
]
```

#### 更改后 (vllm serve)
```python
cmd = [
    "vllm", "serve",
    model_path,  # 位置参数
    "--host", host,
    "--port", str(port),
    "--served-model-name", served_model_name,
    "--dtype", dtype,
    "--max-model-len", str(max_model_len),
    "--gpu-memory-utilization", str(gpu_memory_utilization),
    "--tensor-parallel-size", str(tensor_parallel_size),
    # ... 更多参数
]
```

### 2. 新增参数支持

#### 模型配置 (ModelConfig)
- `dtype`: 数据类型（auto, half, float16, bfloat16, float32）
- `max_model_len`: 最大上下文长度
- `quantization`: 量化方法（awq, gptq 等）
- `trust_remote_code`: 是否信任远程代码

#### 并行配置 (ParallelConfig)
- `tensor_parallel_size`: 张量并行大小（多卡推理）

#### LoRA 配置
- `--enable-lora`: 启用 LoRA 支持
- `--lora-modules`: LoRA 模块配置（格式：`name=path`）

#### 缓存配置 (CacheConfig)
- `gpu_memory_utilization`: GPU 内存利用率（保留）

### 3. API 层 (`api/deploy.py`)

#### 更新的 DeployRequest 模型
```python
class DeployRequest(BaseModel):
    # 基础参数
    model_id_or_path: str
    adapter_path: Optional[str] = None
    served_model_name: Optional[str] = None

    # 前端配置
    host: Optional[str] = "0.0.0.0"
    port: Optional[int] = None
    gpu_id: Optional[str] = None

    # 模型配置
    max_length: Optional[int] = None
    dtype: Optional[str] = "auto"
    trust_remote_code: Optional[bool] = False
    quantization: Optional[str] = None

    # 缓存配置
    gpu_memory_utilization: Optional[float] = 0.9

    # 并行配置
    tensor_parallel_size: Optional[int] = None
```

#### 移除的参数
- `use_vllm`: 已移除（始终使用 vllm）
- `quantization_bit`: 改为 `quantization`（字符串类型）
- `temperature`, `top_p`: 移除（应在推理时设置，而非部署时）
- `max_num_batched_tokens`: 移除（vllm 自动优化）

## 使用示例

### 示例 1 - 基础部署
```bash
POST /api/deploy/start
{
    "model_id_or_path": "/app/models/Qwen/Qwen2.5-7B-Instruct",
    "port": 8080
}
```

生成的命令：
```bash
CUDA_VISIBLE_DEVICES=0 vllm serve /app/models/Qwen/Qwen2.5-7B-Instruct \
    --host 0.0.0.0 \
    --port 8080 \
    --served-model-name Qwen2.5-7B-Instruct \
    --dtype auto \
    --gpu-memory-utilization 0.9
```

### 示例 2 - 带 LoRA Adapter
```bash
POST /api/deploy/start
{
    "model_id_or_path": "/app/models/Qwen/Qwen2.5-7B-Instruct",
    "adapter_path": "/app/output/train-12345678/v0-xxx/checkpoint-100",
    "port": 8081,
    "gpu_memory_utilization": 0.9
}
```

生成的命令：
```bash
CUDA_VISIBLE_DEVICES=0 vllm serve /app/models/Qwen/Qwen2.5-7B-Instruct \
    --host 0.0.0.0 \
    --port 8081 \
    --served-model-name Qwen2.5-7B-Instruct \
    --dtype auto \
    --gpu-memory-utilization 0.9 \
    --enable-lora \
    --lora-modules deploy-abc123=/app/output/train-12345678/v0-xxx/checkpoint-100
```

### 示例 3 - 多卡推理（张量并行）
```bash
POST /api/deploy/start
{
    "model_id_or_path": "/app/models/Qwen/Qwen2.5-72B-Instruct",
    "tensor_parallel_size": 4,
    "gpu_memory_utilization": 0.95,
    "max_length": 32768
}
```

生成的命令：
```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve /app/models/Qwen/Qwen2.5-72B-Instruct \
    --host 0.0.0.0 \
    --port 8000 \
    --served-model-name Qwen2.5-72B-Instruct \
    --dtype auto \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.95 \
    --tensor-parallel-size 4
```

## 参数映射对照表

| 原参数 (swift deploy) | 新参数 (vllm serve) | 说明 |
|---------------------|-------------------|------|
| `--model` | 位置参数 | 模型路径作为第一个位置参数 |
| `--infer_backend vllm` | （移除） | 始终使用 vllm |
| `--served_model_name` | `--served-model-name` | 下划线改为连字符 |
| `--port` | `--port` | 保持不变 |
| `--max_new_tokens` | （移除） | 在推理请求时设置 |
| `--adapters` | `--lora-modules` | 需要 `--enable-lora` |
| （无） | `--dtype` | 新增：数据类型 |
| （无） | `--max-model-len` | 新增：最大上下文长度 |
| （无） | `--tensor-parallel-size` | 新增：多卡并行 |
| （无） | `--quantization` | 新增：量化方法 |
| （无） | `--trust-remote-code` | 新增：信任远程代码 |

## 兼容性说明

### 前端兼容性
- 前端无需修改（API 接口保持兼容）
- `use_vllm` 参数将被忽略（始终使用 vllm）
- `quantization_bit` 参数已弃用，请使用 `quantization`

### 运行时要求
- 需要安装 `vllm` 包（已包含在基础镜像中）
- vllm 版本：0.11.0+（基础镜像已满足）

## 优势

1. **减少中间层**：直接调用 vllm serve，避免 swift deploy 的额外检查
2. **更多控制**：支持完整的 vllm serve 参数
3. **更好的性能**：减少不必要的代码转换
4. **更灵活的配置**：支持多卡推理、量化等高级特性

## 潜在问题与解决方案

### 问题 1：LoRA 名称冲突
- **问题**：多个部署使用相同的 LoRA adapter 时，名称可能冲突
- **解决方案**：使用 `deployment_id` 作为 LoRA 名称

### 问题 2：多卡推理时的 GPU 分配
- **问题**：`tensor_parallel_size` 需要多张 GPU
- **解决方案**：自动验证可用 GPU 数量，不足时拒绝部署

### 问题 3：健康检查端点
- **问题**：vllm serve 的健康检查端点可能不同
- **解决方案**：使用标准的 `/health` 端点（vllm 默认支持）

## 测试建议

### 单元测试
```python
def test_deploy_command_generation():
    service = DeployService()
    # 测试基础部署
    # 测试 LoRA 部署
    # 测试多卡部署
```

### 集成测试
```bash
# 1. 启动部署
curl -X POST http://localhost:8000/api/deploy/start \
  -H "Content-Type: application/json" \
  -d '{"model_id_or_path": "/app/models/Qwen/Qwen2.5-7B-Instruct"}'

# 2. 等待启动完成
curl http://localhost:8000/api/deploy/status/{deployment_id}

# 3. 测试推理
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2.5-7B-Instruct",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 4. 停止部署
curl -X POST http://localhost:8000/api/deploy/stop/{deployment_id}
```

## 下一步工作

1. [ ] 更新前端界面以支持新参数（如 `tensor_parallel_size`、`dtype`）
2. [ ] 添加参数验证（如检查 GPU 数量是否满足 `tensor_parallel_size`）
3. [ ] 添加更详细的日志输出
4. [ ] 编写集成测试
5. [ ] 更新用户文档

## 参考文档

- [vLLM Serve Arguments](https://docs.vllm.ai/en/latest/configuration/serve_args.html)
- [vLLM OpenAI Compatible Server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
- [vLLM Multi-GPU Inference](https://docs.vllm.ai/en/latest/serving/distributed_serving.html)
