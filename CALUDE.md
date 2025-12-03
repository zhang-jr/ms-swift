# MS-SWIFT 自定义 Web UI 开发指南

## 项目概述

**Fork 仓库**: https://github.com/zhang-jr/ms-swift  
**上游仓库**: https://github.com/modelscope/ms-swift  
**开发分支**: `feature/custom-webui`

### 项目目标

基于 ms-swift 原有功能,开发一个全新的前端界面,提供给普通用户进行模型训练、测试和推理的 Web 平台。

**核心需求**:
- 使用 ms-swift Docker 环境作为基础设施
- 替换现有的 Gradio UI (`swift/ui`) 为自定义前端界面
- 提供用户友好的训练、推理、测试操作界面
- 支持普通用户无需命令行即可完成全流程操作

## 技术栈

### 后端 (保留 ms-swift 核心)
- Python 3.8+
- ms-swift 框架 (训练/推理引擎)
- PyTorch >= 2.0
- 参考 Docker: `modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3`

### 前端 (新开发)
**选项 A - 现代 Web 框架**:
- React / Vue.js / Next.js
- TypeScript
- Tailwind CSS / Ant Design / Material-UI
- axios / fetch 用于 API 调用

**选项 B - Python Web 框架**:
- Streamlit (快速原型)
- FastAPI + 前端模板
- Flask + Bootstrap/Vue

### API 层
- FastAPI / Flask (替代 Gradio)
- RESTful API 设计
- WebSocket (用于实时训练日志)

## 项目结构
```
ms-swift/
├── swift/                    # 核心代码 (保持不变)
│   ├── llm/                 # LLM 相关
│   ├── trainers/            # 训练器
│   ├── tuners/              # 微调方法
│   └── ui/                  # 原 Gradio UI (参考后可删除)
│       ├── llm_train/
│       ├── llm_infer/
│       └── llm_deploy/
├── custom_ui/               # 【新增】自定义 UI 目录
│   ├── backend/             # API 后端
│   │   ├── app.py          # FastAPI/Flask 主应用
│   │   ├── api/            # API 路由
│   │   │   ├── train.py    # 训练 API
│   │   │   ├── infer.py    # 推理 API
│   │   │   └── deploy.py   # 部署 API
│   │   ├── services/       # 业务逻辑层
│   │   │   ├── train_service.py
│   │   │   ├── infer_service.py
│   │   │   └── model_service.py
│   │   └── utils/          # 工具函数
│   ├── frontend/            # 前端代码
│   │   ├── src/
│   │   │   ├── components/ # 组件
│   │   │   │   ├── TrainPanel/
│   │   │   │   ├── InferPanel/
│   │   │   │   └── ModelManager/
│   │   │   ├── pages/      # 页面
│   │   │   ├── api/        # API 调用
│   │   │   └── App.js      # 主应用
│   │   ├── public/
│   │   ├── package.json
│   │   └── vite.config.js / next.config.js
│   ├── docker/              # Docker 配置
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   └── README.md
├── examples/                # 保留原有示例
├── tests/                   # 测试
└── docs/                    # 文档
```

## 开发任务清单

### 阶段 1: 环境搭建与研究 

#### 任务 1.1: Fork 和环境配置
- [x] Fork ms-swift 到个人账户
- [x] 克隆仓库并创建开发分支
```bash
git clone https://github.com/zhang-jr/ms-swift.git
cd ms-swift
git remote add upstream https://github.com/modelscope/ms-swift.git
git checkout -b feature/custom-webui
```

#### 任务 1.2: Docker 环境搭建
- [x] 拉取 ms-swift Docker 镜像
```bash
docker pull modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3
```
- [ ] 测试原有 Gradio UI
```bash
swift web-ui
```
- [ ] 分析 `swift/ui` 目录结构和功能

#### 任务 1.3: 研究现有实现
- [ ] 分析 `swift/ui/llm_train/llm_train.py` - 训练界面实现
- [ ] 分析 `swift/ui/llm_infer/llm_infer.py` - 推理界面实现
- [ ] 分析 `swift/ui/llm_deploy/llm_deploy.py` - 部署界面实现
- [ ] 理解 Gradio 组件如何调用 ms-swift 核心功能
- [ ] 提取核心 API 调用逻辑

### 阶段 2: API 后端开发 

#### 任务 2.1: 创建 FastAPI 应用
```python
# custom_ui/backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MS-SWIFT Custom UI API")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
from api import train, infer, deploy
app.include_router(train.router, prefix="/api/train", tags=["训练"])
app.include_router(infer.router, prefix="/api/infer", tags=["推理"])
app.include_router(deploy.router, prefix="/api/deploy", tags=["部署"])
```

#### 任务 2.2: 训练 API 开发
- [ ] `/api/train/start` - 启动训练
- [ ] `/api/train/stop` - 停止训练
- [ ] `/api/train/status` - 获取训练状态
- [ ] `/api/train/logs` - 实时日志 (WebSocket)
- [ ] `/api/models` - 模型列表
- [ ] `/api/datasets` - 数据集列表

**参考实现**:
```python
# custom_ui/backend/api/train.py
from fastapi import APIRouter, BackgroundTasks
from services.train_service import TrainService

router = APIRouter()
train_service = TrainService()

@router.post("/start")
async def start_training(
    model_id: str,
    dataset: str,
    train_type: str = "lora",
    background_tasks: BackgroundTasks
):
    """启动训练任务"""
    task_id = train_service.create_task(
        model_id=model_id,
        dataset=dataset,
        train_type=train_type
    )
    background_tasks.add_task(train_service.run_training, task_id)
    return {"task_id": task_id, "status": "started"}
```

#### 任务 2.3: 推理 API 开发
- [ ] `/api/infer/chat` - 对话推理
- [ ] `/api/infer/load-model` - 加载模型
- [ ] `/api/infer/unload-model` - 卸载模型

#### 任务 2.4: 部署 API 开发
- [ ] `/api/deploy/start` - 启动部署服务
- [ ] `/api/deploy/stop` - 停止部署服务
- [ ] `/api/deploy/status` - 部署状态

### 阶段 3: 前端开发

#### 任务 3.1: 项目初始化
```bash
cd custom_ui
npx create-next-app frontend
# 或
npm create vite@latest frontend -- --template react-ts
```

#### 任务 3.2: 主要页面组件

**训练面板** (`TrainPanel.tsx`):
- 模型选择器
- 数据集选择器
- 训练参数配置 (LoRA rank, learning rate, epochs 等)
- 训练进度显示
- 实时日志查看

**推理面板** (`InferPanel.tsx`):

- 模型加载器
- 对话界面
- 参数调整 (temperature, max_tokens 等)
- 历史记录

**模型管理** (`ModelManager.tsx`):

- 已训练模型列表
- 模型信息展示
- 下载/删除操作
- 推送到 ModelScope Hub

#### 任务 3.3: API 集成
```typescript
// frontend/src/api/train.ts
export const trainAPI = {
  startTraining: async (params: TrainParams) => {
    const response = await fetch('/api/train/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    return response.json();
  },
  
  getStatus: async (taskId: string) => {
    const response = await fetch(`/api/train/status/${taskId}`);
    return response.json();
  }
};
```

### 阶段 4: Docker 集成 

#### 任务 4.1: Dockerfile 编写
```dockerfile
# custom_ui/docker/Dockerfile
FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3

# 安装 ms-swift
WORKDIR /app
COPY . /app
RUN pip install -e . --break-system-packages

# 安装 API 后端依赖
WORKDIR /app/custom_ui/backend
RUN pip install fastapi uvicorn websockets --break-system-packages

# 安装 Node.js (用于前端)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
RUN apt-get install -y nodejs

# 构建前端
WORKDIR /app/custom_ui/frontend
COPY custom_ui/frontend/package*.json ./
RUN npm install
COPY custom_ui/frontend ./
RUN npm run build

# 启动脚本
WORKDIR /app
COPY custom_ui/docker/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000 3000
CMD ["/start.sh"]
```

#### 任务 4.2: Docker Compose
```yaml
# custom_ui/docker/docker-compose.yml
version: '3.8'

services:
  ms-swift-ui:
    build:
      context: ../..
      dockerfile: custom_ui/docker/Dockerfile
    ports:
      - "8000:8000"  # API
      - "3000:3000"  # Frontend
    volumes:
      - ./data:/app/data
      - ./models:/app/models
      - ./output:/app/output
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

### 阶段 5: 测试与优化

- [ ] 端到端测试训练流程
- [ ] 端到端测试推理流程
- [ ] 性能优化
- [ ] UI/UX 改进
- [ ] 文档编写

## 核心功能映射

### 从 Gradio 到自定义 UI

| 原 Gradio 功能                      | 对应自定义实现                                             |
| ----------------------------------- | ---------------------------------------------------------- |
| `swift/ui/llm_train/llm_train.py`   | `custom_ui/backend/api/train.py` + `frontend/TrainPanel`   |
| `swift/ui/llm_infer/llm_infer.py`   | `custom_ui/backend/api/infer.py` + `frontend/InferPanel`   |
| `swift/ui/llm_deploy/llm_deploy.py` | `custom_ui/backend/api/deploy.py` + `frontend/DeployPanel` |

### 调用 ms-swift 核心功能

保持使用 ms-swift 的核心 API:
```python
from swift.llm import sft_main, infer_main, deploy_main
from swift.utils import get_logger

# 在 service 层调用
class TrainService:
    def run_training(self, task_id: str):
        args = self.get_training_args(task_id)
        result = sft_main(args)
        return result
```

## Git 工作流

### 日常开发
```bash
# 1. 同步上游
git fetch upstream
git merge upstream/main

# 2. 开发功能
git add custom_ui/
git commit -m "feat: 添加训练 API 端点"

# 3. 推送到 fork
git push origin feature/custom-webui
```

### 提交 PR 到上游(可选)
如果你想将自定义 UI 贡献回上游项目:
1. 确保代码质量和文档完整
2. 在 GitHub 上从 `feature/custom-webui` 向上游 `main` 提交 PR
3. 说明新 UI 的优势和使用场景

## 开发规范

### Python 代码
- 遵循 PEP 8
- 使用 type hints
- 添加 docstring

### TypeScript/JavaScript
- 使用 ESLint + Prettier
- 遵循 Airbnb Style Guide
- 组件使用 TypeScript

### API 设计
- RESTful 风格
- 统一返回格式:
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

## 测试方法

### 后端测试
```bash
cd custom_ui/backend
pytest tests/
```

### 前端测试
```bash
cd custom_ui/frontend
npm run test
```

### 集成测试
```bash
docker-compose -f custom_ui/docker/docker-compose.yml up
# 访问 http://localhost:3000 测试完整流程
```

## Claude Code 使用场景

### 适合让 Claude Code 帮助的任务:

1. **API 端点开发**
   - "帮我实现训练 API 的 `/api/train/start` 端点,参考 swift/ui/llm_train 的实现"

2. **前端组件开发**
   - "创建一个 React 训练面板组件,需要包含模型选择、数据集选择和参数配置"

3. **代码审查**
   - "审查这个 API 路由代码,确保错误处理完善"

4. **Docker 配置**
   - "帮我优化 Dockerfile,确保前后端都能正确启动"

5. **调试问题**
   - "训练任务启动失败,日志显示 XXX 错误,如何修复?"

6. **文档编写**
   - "为这个 API 端点生成 OpenAPI 文档"

## 重要提醒

1. **不要修改** `swift/` 核心目录,保持与上游兼容
2. **所有新代码** 放在 `custom_ui/` 目录下
3. **定期同步** 上游更新,避免分支过于落后
4. **充分测试** 后再提交代码
5. **文档同步** 更新,方便其他开发者理解

## 参考资源

- ms-swift 官方文档: https://swift.readthedocs.io/
- FastAPI 文档: https://fastapi.tiangolo.com/
- React 文档: https://react.dev/
- ModelScope Hub: https://modelscope.cn/

## 常见问题

### Q: 如何调试 ms-swift 核心功能?
A: 在 `custom_ui/backend/services/` 中添加日志,使用 `get_logger()` 输出详细信息

### Q: 前端如何实时显示训练日志?
A: 使用 WebSocket 连接,后端通过 WebSocket 推送训练日志到前端

### Q: 如何处理长时间训练任务?
A: 使用 BackgroundTasks 或 Celery 将训练任务放入后台队列

---

**下一步行动**: 
1. 完成环境搭建
2. 研究 `swift/ui` 实现
3. 开始 API 后端开发