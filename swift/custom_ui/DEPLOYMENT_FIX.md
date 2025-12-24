# 部署功能修复说明

## 修复时间
2025-12-24

## 问题分析

### 原始问题
1. **参数错误** - `max_model_len` 被错误地传递给 `max_new_tokens`
2. **状态管理缺陷** - 启动时同步等待，进程异常退出时没有保存部署信息
3. **缺少持续监控** - 启动成功后不再监控服务状态
4. **前后端字段不匹配** - 前端期望的字段名与后端返回不一致

### 根本原因
部署服务是**持续运行的服务器进程**（类似 nginx、uvicorn），而不是一次性任务。原实现：
- ❌ 同步等待启动（阻塞 API 调用）
- ❌ 启动失败时抛出异常（部署信息未保存）
- ❌ 启动成功后无监控（进程异常退出不可见）

## 修复内容

### 1. 参数修复 ✅
**文件**: `swift/custom_ui/backend/services/deploy_service.py:156-158`

```python
# 修复前（错误）
if max_model_len is not None and max_model_len > 0:
    cmd.extend(["--max_new_tokens", str(max_model_len)])

# 修复后（正确）
max_new_tokens = kwargs.get("max_new_tokens", 2048)
cmd.extend(["--max_new_tokens", str(max_new_tokens)])
```

**说明**:
- `max_model_len` 是模型上下文长度（如 8192）
- `max_new_tokens` 是生成的最大 token 数（如 2048）
- 两者不应混淆

### 2. 异步启动 + 后台监控 ✅
**文件**: `swift/custom_ui/backend/services/deploy_service.py`

#### 2.1 立即保存部署信息
```python
# 进程启动后立即保存（状态 "starting"）
deployment_info = {
    "deployment_id": deployment_id,
    "status": "starting",  # 初始状态
    # ... 其他字段
}
self.running_deployments[deployment_id] = deployment_info
```

#### 2.2 后台监控任务
```python
# 启动后台监控（包含启动检查 + 持续监控）
monitor_task = asyncio.create_task(
    self._monitor_deployment_with_startup(deployment_id, port)
)
self.monitor_tasks[deployment_id] = monitor_task
```

#### 2.3 监控逻辑
1. **启动检查**（最多 5 分钟）
   - 每秒检查健康端点 `/health`
   - 检查进程是否退出
   - 启动成功 → 状态更新为 `running`
   - 进程退出 → 状态更新为 `failed`
   - 超时 → 状态更新为 `timeout`

2. **持续监控**（每 10 秒）
   - 检查进程是否退出
   - 检查健康端点是否正常
   - 自动更新部署状态

### 3. 状态定义 ✅

| 状态 | 说明 | 前端颜色 |
|------|------|----------|
| `starting` | 正在启动（模型加载、CUDA 图捕获） | 蓝色动画 |
| `running` | 运行中（健康检查通过） | 绿色 |
| `unhealthy` | 不健康（进程运行但健康检查失败） | 橙色 |
| `failed` | 失败（进程异常退出） | 红色 |
| `timeout` | 启动超时（5 分钟内未成功） | 红色 |
| `stopped` | 已停止（手动停止） | 灰色 |

### 4. API 字段适配 ✅
**文件**: `swift/custom_ui/backend/api/deploy.py:198-228`

```python
# 转换格式以匹配前端期望
formatted_deployments.append({
    "deployment_id": d["deployment_id"],
    "model_id": d["model_path"],      # 前端期望 model_id
    "endpoint": d["api_endpoint"],    # 前端期望 endpoint
    "status": d["status"],
    "created_at": d.get("started_at", 0) * 1000,  # 毫秒时间戳
    # ...
})
```

### 5. 前端自动刷新 ✅
**文件**: `swift/custom_ui/frontend/src/pages/DeployPage.tsx:45-50`

```typescript
// 每 10 秒自动刷新部署列表（监控状态变化）
const interval = setInterval(() => {
  loadDeployments()
}, 10000)
```

## 部署工作流

### 正常流程
```
用户点击"启动部署"
    ↓
后端启动进程（PID: 804）
    ↓
立即返回（状态: starting）
    ↓ 后台监控任务启动
等待服务启动（最多 5 分钟）
├─ 模型加载（约 1.6 秒）
├─ torch.compile（约 49.5 秒）
├─ KV cache 初始化（约 57 秒）
└─ CUDA 图捕获（约 6 秒）
    ↓
健康检查成功 (/health → 200)
    ↓
状态更新: starting → running
    ↓ 持续监控（每 10 秒）
前端自动刷新显示"运行中"
```

### 异常流程
```
用户点击"启动部署"
    ↓
后端启动进程（PID: 804）
    ↓
立即返回（状态: starting）
    ↓ 后台监控任务启动
等待服务启动...
    ↓
进程异常退出（退出码: 1）
    ↓
状态更新: starting → failed
    ↓
前端自动刷新显示"失败"
    ↓
用户查看日志（/api/deploy/logs/{id}）
```

## 测试建议

### 1. 正常启动测试
```bash
# Docker Compose 启动
cd swift/custom_ui/docker
docker-compose up

# 前端访问
http://localhost:8000

# 启动部署（前端 UI）
模型: Qwen3-VL-4B-Instruct
端口: 12321

# 观察状态变化
starting (0-30s) → running (30s+)
```

### 2. 异常测试
```bash
# 测试进程退出（手动杀死）
docker exec ms-swift-ui kill -9 <PID>

# 观察状态变化
running → failed

# 测试启动超时（使用不存在的模型）
模型: invalid-model-name

# 观察状态变化
starting (0-300s) → timeout (300s+)
```

### 3. 健康检查测试
```bash
# 手动检查健康端点
curl http://localhost:12321/health

# 预期响应
HTTP/1.1 200 OK
```

## 相关文件

### 后端
- `swift/custom_ui/backend/services/deploy_service.py` - 部署服务核心逻辑
- `swift/custom_ui/backend/api/deploy.py` - 部署 API 端点

### 前端
- `swift/custom_ui/frontend/src/pages/DeployPage.tsx` - 部署页面
- `swift/custom_ui/frontend/src/api/deploy.ts` - 部署 API 客户端

## 注意事项

1. **vLLM 启动时间**
   - 小模型（< 7B）: 约 1-2 分钟
   - 大模型（> 7B）: 约 3-5 分钟
   - 包含 torch.compile、CUDA 图捕获等耗时操作

2. **健康检查超时**
   - 当前设置为 5 分钟（300 秒）
   - 如需调整: 修改 `deploy_service.py:255`

3. **监控频率**
   - 后端监控: 每 10 秒
   - 前端刷新: 每 10 秒
   - 可根据需求调整

4. **日志查看**
   - API: `GET /api/deploy/logs/{deployment_id}`
   - 文件: `/app/deployments/{deployment_id}.log`

## 已知限制

1. **重启恢复** - Docker 容器重启后，部署信息丢失（存储在内存）
   - 未来改进: 持久化到 SQLite/文件
2. **多实例** - 当前不支持同一模型的多个部署实例
   - 未来改进: 支持多实例负载均衡
3. **GPU 分配** - 当前默认使用 GPU 0
   - 未来改进: 支持指定 GPU 设备

## 总结

本次修复解决了部署功能的核心问题，使其：
- ✅ 正确处理长时间启动（异步 + 后台监控）
- ✅ 持续监控服务状态（自动更新）
- ✅ 前端实时显示（自动刷新）
- ✅ 异常情况可追溯（日志 + 状态）

部署服务现在是一个**真正的持续运行服务**，而不是一次性任务。
