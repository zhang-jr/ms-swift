# 多 GPU 自动分配功能

## 功能概述

实现了**多 GPU 自动分配**功能，支持在多卡服务器上部署多个模型实例，每个 GPU 部署一个模型（不考虑 TP 多卡部署场景）。

## 实现时间
2025-12-24

## 核心功能

### 1. GPU 自动扫描
- 从 `CUDA_VISIBLE_DEVICES` 环境变量读取可用 GPU 列表
- 支持单卡（"0"）和多卡（"0,1,2,3"）配置
- 服务启动时自动检测并显示可用 GPU

### 2. GPU 自动分配
- **自动分配**: 部署时不指定 GPU，系统自动选择第一个空闲 GPU
- **手动指定**: 支持用户指定特定 GPU（如果该 GPU 可用）
- **占用检测**: 实时跟踪每个 GPU 的占用状态
- **错误提示**: 所有 GPU 被占用时返回友好错误信息

### 3. GPU 状态监控
- 实时显示每个 GPU 的使用状态（空闲/使用中）
- 显示每个 GPU 上运行的部署实例
- 每 10 秒自动刷新（与部署列表同步）

### 4. 端口自动分配
- 每个部署实例自动分配不同端口（从 8000 开始递增）
- 避免端口冲突

## 使用场景

### 场景 1: 单卡服务器
```bash
# Docker Compose 配置
CUDA_VISIBLE_DEVICES=0  # 单卡

# 部署流程
部署实例 A → GPU 0, 端口 8000
部署实例 B → 失败（GPU 0 已占用）
```

### 场景 2: 多卡服务器
```bash
# Docker Compose 配置
CUDA_VISIBLE_DEVICES=0,1,2,3  # 4 卡

# 部署流程
部署实例 A → GPU 0, 端口 8000（自动分配）
部署实例 B → GPU 1, 端口 8001（自动分配）
部署实例 C → GPU 2, 端口 8002（自动分配）
停止实例 A → GPU 0 空闲
部署实例 D → GPU 0, 端口 8003（复用空闲 GPU）
```

### 场景 3: 指定 GPU
```bash
# 部署请求
{
  "model_id_or_path": "Qwen2.5-7B-Instruct",
  "gpu_id": "2"  # 指定使用 GPU 2
}

# 系统检查
- GPU 2 在可用列表中？✓
- GPU 2 已被占用？✗
- 分配 GPU 2 → 成功
```

## 技术实现

### 后端实现

#### 1. GPU 扫描 (`deploy_service.py`)
```python
def _get_available_gpus(self) -> List[str]:
    """从 CUDA_VISIBLE_DEVICES 获取可用 GPU"""
    cuda_visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "0")
    gpu_ids = [gpu.strip() for gpu in cuda_visible_devices.split(",")]
    return gpu_ids
```

#### 2. GPU 分配逻辑
```python
def _allocate_gpu(self, preferred_gpu: Optional[str] = None) -> Optional[str]:
    """
    分配 GPU
    - preferred_gpu=None: 自动选择第一个空闲 GPU
    - preferred_gpu="0": 检查 GPU 0 是否可用
    """
    if preferred_gpu is not None:
        # 检查指定 GPU 是否可用
        if preferred_gpu not in self.available_gpus:
            return None
        if preferred_gpu in self._get_used_gpus():
            return None
        return preferred_gpu

    # 自动分配
    used_gpus = self._get_used_gpus()
    for gpu_id in self.available_gpus:
        if gpu_id not in used_gpus:
            return gpu_id

    return None  # 无可用 GPU
```

#### 3. GPU 状态跟踪
```python
def _get_used_gpus(self) -> set:
    """获取已被占用的 GPU"""
    used_gpus = set()
    for deployment in self.running_deployments.values():
        if deployment.get("status") in ["starting", "running"]:
            gpu_devices = deployment.get("gpu_devices", "")
            for gpu_id in gpu_devices.split(","):
                used_gpus.add(gpu_id.strip())
    return used_gpus
```

#### 4. GPU 状态 API
```python
@router.get("/gpu-status")
async def get_gpu_status():
    """
    返回格式:
    {
        "total_gpus": 4,
        "used_gpus": 2,
        "available_gpus": 2,
        "gpus": [
            {
                "gpu_id": "0",
                "status": "used",
                "deployments": [...]
            }
        ]
    }
    """
```

### 前端实现

#### 1. GPU 状态卡片
- 显示总 GPU 数、已用、空闲
- 每个 GPU 一个小卡片（空闲=绿边框，使用中=红边框）
- 显示每个 GPU 上运行的部署实例

#### 2. 部署列表添加 GPU 列
- 显示每个部署使用的 GPU ID
- 使用 Tag 组件高亮显示

#### 3. 自动刷新
- 每 10 秒刷新 GPU 状态
- 与部署列表同步刷新

## API 说明

### 1. 启动部署（GPU 自动分配）
```bash
POST /api/deploy/start
{
  "model_id_or_path": "Qwen2.5-7B-Instruct",
  "gpu_id": null  # null=自动分配，"0"=指定 GPU 0
}

# 响应
{
  "deployment_id": "deploy-abc123",
  "gpu_id": "0",  # 分配的 GPU
  "port": 8000,
  ...
}
```

### 2. 获取 GPU 状态
```bash
GET /api/deploy/gpu-status

# 响应
{
  "total_gpus": 4,
  "used_gpus": 2,
  "available_gpus": 2,
  "gpus": [
    {
      "gpu_id": "0",
      "status": "used",
      "deployments": [
        {
          "deployment_id": "deploy-abc123",
          "model": "Qwen2.5-7B-Instruct",
          "status": "running"
        }
      ]
    },
    {
      "gpu_id": "1",
      "status": "available",
      "deployments": []
    }
  ]
}
```

### 3. 部署列表（包含 GPU 信息）
```bash
GET /api/deploy/list

# 响应
{
  "deployments": [
    {
      "deployment_id": "deploy-abc123",
      "model_id": "Qwen2.5-7B-Instruct",
      "gpu_id": "0",  # 新增字段
      "port": 8000,
      "status": "running",
      ...
    }
  ]
}
```

## Docker 配置

### 单卡配置
```yaml
# docker-compose.yml
environment:
  - CUDA_VISIBLE_DEVICES=0

deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### 多卡配置
```yaml
# docker-compose.yml
environment:
  - CUDA_VISIBLE_DEVICES=0,1,2,3

deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 4  # 或 all
          capabilities: [gpu]
```

### 环境变量配置
```bash
# .env 文件
CUDA_VISIBLE_DEVICES=0,1,2,3
GPU_COUNT=4
```

## 测试场景

### 测试 1: 自动分配（多卡）
```bash
# 前置条件: CUDA_VISIBLE_DEVICES=0,1,2,3

# 操作
1. 部署模型 A（不指定 GPU）
2. 部署模型 B（不指定 GPU）
3. 部署模型 C（不指定 GPU）

# 预期结果
- 模型 A → GPU 0
- 模型 B → GPU 1
- 模型 C → GPU 2
- GPU 状态: GPU 0,1,2 使用中，GPU 3 空闲
```

### 测试 2: 指定 GPU
```bash
# 操作
部署模型 D，指定 GPU=2

# 预期结果（GPU 2 已被占用）
- 错误: "指定的 GPU 2 不可用"

# 操作
部署模型 D，指定 GPU=3

# 预期结果（GPU 3 空闲）
- 成功，模型 D → GPU 3
```

### 测试 3: GPU 释放与复用
```bash
# 操作
1. 停止模型 A（释放 GPU 0）
2. 部署模型 E（不指定 GPU）

# 预期结果
- GPU 0 状态: 使用中 → 空闲 → 使用中
- 模型 E → GPU 0（复用）
```

### 测试 4: 所有 GPU 占用
```bash
# 前置条件: 4 个模型占用了 GPU 0,1,2,3

# 操作
部署模型 F（不指定 GPU）

# 预期结果
- 错误: "无可用 GPU，所有 GPU 已被占用"
- GPU 状态显示: 4/4 使用中
```

## 前端界面

### GPU 状态卡片
```
┌─ GPU 状态 (2/4 使用中) ────────────────── [刷新] ─┐
│                                                    │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐         │
│  │GPU 0 │  │GPU 1 │  │GPU 2 │  │GPU 3 │         │
│  │使用中│  │使用中│  │空闲  │  │空闲  │         │
│  ├──────┤  ├──────┤  └──────┘  └──────┘         │
│  │abc123│  │def456│                              │
│  │Qwen  │  │Llama │                              │
│  └──────┘  └──────┘                              │
└────────────────────────────────────────────────────┘
```

### 部署列表（添加 GPU 列）
```
┌─ 部署列表 ────────────────────────────────────────┐
│ ID      │ 模型    │ GPU │ 端口 │ 状态   │ 操作    │
├─────────┼─────────┼─────┼──────┼────────┼─────────┤
│ abc123  │ Qwen2.5 │ 0   │ 8000 │ 运行中 │ [停止]  │
│ def456  │ Llama3  │ 1   │ 8001 │ 运行中 │ [停止]  │
│ ghi789  │ GLM-4   │ 2   │ 8002 │ 启动中 │         │
└─────────┴─────────┴─────┴──────┴────────┴─────────┘
```

## 已知限制

1. **不支持 TP 多卡部署**
   - 当前假设每个模型只需一个 GPU
   - 未来可扩展支持多卡 TP（如 `gpu_devices="0,1"`）

2. **容器重启后状态丢失**
   - GPU 占用信息存储在内存
   - 容器重启后需要重新扫描

3. **无 GPU 负载均衡**
   - 按顺序分配 GPU（0 → 1 → 2 → 3）
   - 未考虑 GPU 显存、算力等因素

## 未来改进

1. **智能 GPU 选择**
   - 考虑 GPU 显存使用率
   - 考虑 GPU 算力负载
   - 优先选择负载最低的 GPU

2. **TP 多卡支持**
   - 支持 `gpu_devices="0,1"` 形式
   - 分配多个 GPU 给单个部署

3. **GPU 亲和性**
   - 相同模型优先部署在相同 GPU（利用 KV cache）

4. **持久化状态**
   - 将 GPU 占用信息保存到 SQLite
   - 容器重启后恢复状态

## 相关文件

### 后端
- `swift/custom_ui/backend/services/deploy_service.py` - GPU 分配逻辑
- `swift/custom_ui/backend/api/deploy.py` - GPU 状态 API

### 前端
- `swift/custom_ui/frontend/src/pages/DeployPage.tsx` - GPU 状态显示
- `swift/custom_ui/frontend/src/api/deploy.ts` - GPU API 客户端

## 总结

本次实现的多 GPU 自动分配功能：
- ✅ 自动扫描可用 GPU（CUDA_VISIBLE_DEVICES）
- ✅ 自动分配空闲 GPU
- ✅ 支持手动指定 GPU
- ✅ 实时 GPU 状态监控
- ✅ 前端可视化显示
- ✅ 端口自动分配
- ✅ 错误友好提示

适用于多卡服务器场景，显著提升 GPU 利用率和部署效率！
