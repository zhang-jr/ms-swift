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

### 目标用户与使用场景

**目标用户**: 数据工程师（无需深度学习算法知识）

**核心使用场景**:
1. **数据管理（零配置）**
   - 通过浏览器上传训练数据（CSV, JSONL, JSON, TSV, TXT）
   - 数据自动保存到 Docker volume (`/app/data`)
   - 支持数据预览、下载、删除（最大 1GB）
   - 训练时只需传入文件名，系统自动从 `/app/data` 读取

2. **模型训练（可视化配置）**
   - 选择预训练模型（如 qwen-7b-chat）
   - 从已上传的数据集中选择
   - 可视化配置训练参数（LoRA rank, learning rate, epochs 等）
   - 实时查看训练进度和 loss 曲线
   - WebSocket 实时日志推送

3. **数据同步（自动化）**
   - 前端上传的数据通过 Docker volume 自动同步到容器
   - 训练输出自动保存到 `/app/output/{task_id}/`
   - 宿主机可通过配置的 `OUTPUT_DIR` 访问训练结果
   - 支持 NFS 共享存储，多机器共享模型

4. **部署灵活性**
   - 可复用相同镜像在多台机器或云端部署
   - GPU 数量、设备 ID、挂载目录均可通过 `.env` 配置
   - 支持单卡、多卡、指定卡、所有卡等灵活配置

**工作流程**:
```
数据工程师（浏览器）
    ↓ 上传数据（CSV/JSONL）
FastAPI 后端接收
    ↓ 保存到 /app/data
Docker Volume 自动同步
    ↓ 训练时读取
MS-SWIFT 训练进程
    ↓ 输出到 /app/output
Docker Volume 挂载
    ↓ 宿主机访问
训练结果 (OUTPUT_DIR)
```

**与原 Gradio UI 的区别**:
- Gradio UI: 需要手动配置数据集路径，适合开发者
- Custom UI: 浏览器上传数据，零配置，适合数据工程师

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
│   ├── ui/                  # 原 Gradio UI (参考后可删除)
│   │   ├── llm_train/
│   │   ├── llm_infer/
│   │   └── llm_deploy/
│   └── custom_ui/           # 【新增】自定义 UI 目录
│       ├── backend/             # API 后端
│       │   ├── app.py          # FastAPI 主应用 ✅
│       │   ├── api/            # API 路由
│       │   │   ├── data.py     # 数据管理 API ✅ NEW!
│       │   │   ├── train.py    # 训练 API ✅
│       │   │   ├── infer.py    # 推理 API ✅
│       │   │   ├── deploy.py   # 部署 API ✅
│       │   │   └── model.py    # 模型管理 API ✅
│       │   ├── services/       # 业务逻辑层
│       │   │   ├── train_service.py   ✅
│       │   │   ├── infer_service.py   ✅
│       │   │   ├── deploy_service.py  ✅
│       │   │   └── model_service.py   ✅
│       │   └── requirements.txt   # Python 依赖 ✅
│       ├── frontend/            # 前端代码 (React + TypeScript)
│       │   ├── src/
│       │   │   ├── components/  # 公共组件
│       │   │   │   └── Layout.tsx    ✅
│       │   │   ├── pages/       # 页面组件
│       │   │   │   ├── TrainPage.tsx    ✅
│       │   │   │   ├── InferPage.tsx    ✅
│       │   │   │   ├── DeployPage.tsx   ✅
│       │   │   │   └── DataManagementPage.tsx  🚧 待开发
│       │   │   ├── api/         # API 客户端
│       │   │   │   ├── client.ts   ✅
│       │   │   │   ├── data.ts     🚧 待实现
│       │   │   │   ├── train.ts    ✅
│       │   │   │   ├── infer.ts    ✅
│       │   │   │   ├── deploy.ts   ✅
│       │   │   │   └── model.ts    ✅
│       │   │   ├── types/       # TypeScript 类型
│       │   │   │   └── index.ts    ✅
│       │   │   ├── App.tsx         ✅
│       │   │   └── main.tsx        ✅
│       │   ├── package.json    ✅
│       │   └── vite.config.ts  ✅
│       ├── docker/              # Docker 配置
│       │   ├── Dockerfile           ✅
│       │   ├── docker-compose.yml   ✅
│       │   ├── .env.example         ✅ NEW!
│       │   └── start.sh             ✅
│       ├── README.md           ✅
│       ├── QUICKSTART.md       ✅
│       ├── USER_GUIDE.md       ✅ NEW!
│       └── PROJECT_SUMMARY.md  ✅
├── CLAUDE.md                # 本文档 (开发指南)
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

#### 任务 2.1: 创建 FastAPI 应用 ✅
```python
# swift/custom_ui/backend/app.py
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
from api import data, train, infer, deploy, model
app.include_router(data.router, prefix="/api/data", tags=["数据管理"])
app.include_router(train.router, prefix="/api/train", tags=["训练"])
app.include_router(infer.router, prefix="/api/infer", tags=["推理"])
app.include_router(deploy.router, prefix="/api/deploy", tags=["部署"])
app.include_router(model.router, prefix="/api/model", tags=["模型管理"])
```

#### 任务 2.2: 数据管理 API 开发 ✅
- [x] `/api/data/upload` - 上传数据集（支持 CSV, JSONL, JSON, TSV, TXT, Parquet, Arrow）
- [x] `/api/data/list` - 获取数据集列表
- [x] `/api/data/preview/{filename}` - 预览数据集（前 N 行）
- [x] `/api/data/info/{filename}` - 获取数据集详细信息
- [x] `/api/data/download/{filename}` - 下载数据集
- [x] `/api/data/delete/{filename}` - 删除数据集
- [x] `/api/data/validate-annotation-project` - 验证标注项目结构 ✅ **[2025-12-15 新增]**
- [x] `/api/data/convert` - 转换标注数据为 HuggingFace Datasets 格式 ✅ **[2025-12-15 新增]**
- [x] `/api/data/convert-formats` - 获取支持的转换格式 ✅ **[2025-12-15 新增]**

**已实现功能**:
- 文件上传最大 1GB，自动保存到 `/app/data`
- 支持多种数据格式的预览（自动识别列名）
- 文件大小、行数统计
- 路径安全验证（防止路径遍历攻击）

**最新改进 (2025-12-11)**:
- ✅ **扩展文件类型支持** - 参考 HuggingFace/ModelScope 标准
  - 文本格式: `.jsonl`, `.json`, `.csv`, `.tsv`, `.txt`
  - Parquet/Arrow: `.parquet`, `.pq`, `.arrow` (HuggingFace 默认格式)
  - 图像格式: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`
  - 音频格式: `.wav`, `.mp3`, `.flac`, `.ogg`
  - 视频格式: `.mp4`, `.avi`, `.mov`, `.mkv`
  - 其他格式: `.pkl`, `.pickle`, `.npy`, `.npz`, `.h5`, `.hdf5`
- ✅ **Parquet/Arrow 预览** - 使用 pandas 和 pyarrow 读取并预览
- ✅ **递归目录扫描** - 支持多层目录结构（用于多模态数据集）
  - `scan_datasets()` 现在递归扫描最多 5 层子目录
  - 支持包含图片/音频的多模态数据集文件夹
  - 相对路径用作 dataset_id（如 `folder/subfolder/data.jsonl`）
- ✅ **Web 上传策略** - 只允许文本和结构化数据格式上传
  - 大文件（图片、音频、视频）建议通过 Docker volume 挂载
  - 保持预览能力与实际需求的平衡

**数据转换功能 (2025-12-15 新增)** ✅:
- ✅ **标注数据转换** - 将标注平台的数据转换为 HuggingFace Datasets 格式
  - 支持图像、PDF、视频三种媒体类型
  - 自动处理带标注框的 overlay 图片
  - 支持 Parquet 和 JSONL 两种输出格式
  - 自动分片保存（参考 FineVision 数据集）
  - 提供完整的统计信息（样本数、媒体类型、模型等）

- ✅ **项目结构验证** - 转换前自动验证标注项目
  - 检查必需目录（instruction, uploads, overlays）
  - 统计 instruction 文件数量
  - 检查是否包含 overlay 图片

- ✅ **转换服务** (`services/dataset_converter_service.py`)
  - `DatasetConverter` 类：核心转换逻辑
  - `validate_annotation_project()` 函数：项目验证
  - 路径安全验证（防止路径遍历攻击）
  - 支持自定义输出文件夹名称

- ✅ **前端转换界面** (`DataManagementPage.tsx`)
  - 数据集列表中的"转换"按钮（仅文件夹显示）
  - 转换配置模态框（输出格式、分片大小、overlay 选项）
  - 转换结果模态框（统计信息、生成文件列表）
  - 使用指南（如何在训练界面使用转换后的数据）

**转换工作流**:
```
标注项目文件夹（/app/data/project_001）
├── instruction/      *.json 文件
├── uploads/          原始媒体文件
└── overlays/         带标注框的图片
    ↓ 用户点击"转换"按钮
后端转换服务
    ↓ 处理所有 instruction 文件
    ↓ 转换为 HuggingFace Datasets 格式
转换后的数据集（/app/data/project_001_converted）
├── train-00000-of-00005.parquet
├── train-00001-of-00005.parquet
...
    ↓ 用户在训练界面选择
MS-SWIFT 训练
```

#### 任务 2.3: 训练 API 开发 ✅ **[已完成 - 真实训练集成]**
- [x] `/api/train/start` - 启动训练
- [x] `/api/train/stop` - 停止训练
- [x] `/api/train/status/{task_id}` - 获取训练状态
- [x] `/api/train/list` - 获取所有训练任务
- [x] `/api/train/delete/{task_id}` - 删除训练任务
- [x] `/ws/logs/{task_id}` - 实时日志 (WebSocket)

**已实现功能** (使用真实 ms-swift 训练引擎):
- ✅ 通过 `swift sft` 命令行调用真实训练
- ✅ 自动解析数据集路径（支持文件名或绝对路径）
- ✅ 训练时传入文件名，系统自动从 `/app/data` 读取
- ✅ 训练输出自动保存到 `/app/output/{task_id}/`
- ✅ 实时捕获训练日志并通过 WebSocket 推送
- ✅ 自动解析训练进度（epoch, loss, learning_rate）
- ✅ 支持停止训练（SIGTERM -> SIGKILL）
- ✅ 支持完整的训练参数配置（LoRA rank, learning_rate, epochs 等）

**真实训练实现** (`services/train_service.py`):
```python
# 核心实现：使用 subprocess 调用 swift sft 命令
def build_train_command(self, task_id: str, config: Dict[str, Any]) -> list:
    dataset_path = self.resolve_dataset_path(config['dataset'])
    output_dir = OUTPUT_DIR / task_id

    cmd = [
        "swift", "sft",
        "--model", config.get('model', 'Qwen/Qwen2.5-7B-Instruct'),
        "--dataset", dataset_path,
        "--output_dir", str(output_dir),
        "--train_type", config.get('train_type', 'lora'),
        "--num_train_epochs", str(config.get('num_train_epochs', 1)),
        "--learning_rate", str(config.get('learning_rate', 1e-4)),
        # ... 更多参数
    ]
    return cmd

async def run_training(self, task_id: str, config: Dict[str, Any]):
    # 启动训练进程
    process = subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True)

    # 异步读取日志并推送到 WebSocket
    async def read_stream():
        while True:
            line = await loop.run_in_executor(None, process.stdout.readline)
            if not line: break

            # 推送日志
            await self._send_log_to_websocket(task_id, line.strip())

            # 解析进度（epoch, loss, learning_rate）
            progress_info = self._parse_training_log(line, total_epochs)
            if progress_info:
                update_task(task_id, progress_info)

    await read_stream()
    return_code = await loop.run_in_executor(None, process.wait)
```

#### 任务 2.4: 推理 API 开发 ✅
- [x] `/api/infer/chat` - 对话推理
- [x] `/api/infer/load-model` - 加载模型
- [x] `/api/infer/unload-model` - 卸载模型
- [x] `/api/infer/models` - 已加载模型列表

#### 任务 2.5: 部署 API 开发 ✅
- [x] `/api/deploy/start` - 启动部署服务
- [x] `/api/deploy/stop` - 停止部署服务
- [x] `/api/deploy/status/{deployment_id}` - 部署状态
- [x] `/api/deploy/list` - 部署列表

#### 任务 2.6: 模型管理 API 开发 ✅
- [x] `/api/model/models` - 获取模型列表
- [x] `/api/model/datasets` - 获取数据集列表
- [x] `/api/model/model-types` - 获取模型类型

### 阶段 3: 前端开发

#### 任务 3.1: 项目初始化 ✅
```bash
cd swift/custom_ui
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install antd react-router-dom axios
```

#### 任务 3.2: 主要页面组件 ✅

**数据管理页面** (`DataManagementPage.tsx`) - 🚧 待开发:
- [ ] 文件上传组件（拖拽上传）
- [ ] 数据集列表（表格显示）
- [ ] 数据预览弹窗（表格形式）
- [ ] 下载/删除操作

**训练面板** (`TrainPage.tsx`) - ✅ 已完成:
- [x] 模型选择器
- [x] 数据集选择器（支持从已上传列表选择）
- [x] 训练参数配置 (LoRA rank, learning rate, epochs 等)
- [x] 训练进度显示
- [x] 实时日志查看（WebSocket）

**推理面板** (`InferPage.tsx`) - ✅ 已完成:
- [x] 模型加载器
- [x] 对话界面
- [x] 参数调整 (temperature, max_tokens 等)
- [x] 历史消息显示

**部署面板** (`DeployPage.tsx`) - ✅ 已完成:
- [x] 部署配置表单
- [x] 部署列表管理
- [x] 端点地址显示
- [x] 使用示例代码

#### 任务 3.3: API 集成 ✅
```typescript
// swift/custom_ui/frontend/src/api/data.ts
export const dataAPI = {
  uploadDataset: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch('/api/data/upload', {
      method: 'POST',
      body: formData
    });
    return response.json();
  },

  listDatasets: async () => {
    const response = await fetch('/api/data/list');
    return response.json();
  },

  previewDataset: async (filename: string, rows: number = 10) => {
    const response = await fetch(`/api/data/preview/${filename}?rows=${rows}`);
    return response.json();
  }
};

// swift/custom_ui/frontend/src/api/train.ts
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

### 阶段 4: Docker 集成 ✅

#### 任务 4.1: Dockerfile 编写 ✅
```dockerfile
# swift/custom_ui/docker/Dockerfile
FROM modelscope-registry.cn-hangzhou.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-cuda12.8.1-py311-torch2.8.0-vllm0.11.0-modelscope1.31.0-swift3.10.3

# 基础镜像已包含 MS-SWIFT 3.10.3，无需重复安装

# 安装 Node.js 18.x (用于前端构建)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装后端额外依赖 (FastAPI、uvicorn 等)
COPY swift/custom_ui/backend/requirements.txt /tmp/backend-requirements.txt
RUN pip install -r /tmp/backend-requirements.txt --break-system-packages && \
    rm /tmp/backend-requirements.txt

# 构建前端
COPY swift/custom_ui/frontend/package*.json /tmp/frontend/
WORKDIR /tmp/frontend
RUN npm install

COPY swift/custom_ui/frontend /tmp/frontend
RUN npm run build && \
    mkdir -p /app/swift/custom_ui/frontend && \
    mv dist /app/swift/custom_ui/frontend/

# 复制后端代码
WORKDIR /app
COPY swift/custom_ui/backend /app/swift/custom_ui/backend

# 复制启动脚本
COPY swift/custom_ui/docker/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000
CMD ["/start.sh"]
```

**优化点**:
- 移除了多余的 MS-SWIFT 安装（基础镜像已包含）
- 只安装基础镜像未包含的依赖（Node.js、FastAPI 等）
- 优化构建缓存策略
- 添加 apt-get clean 减小镜像体积

#### 任务 4.2: Docker Compose ✅
```yaml
# swift/custom_ui/docker/docker-compose.yml
version: '3.8'

services:
  ms-swift-custom-ui:
    build:
      context: ../../..
      dockerfile: swift/custom_ui/docker/Dockerfile
    container_name: ms-swift-ui
    ports:
      - "${API_PORT:-8000}:8000"   # API 和前端访问端口
    volumes:
      # 数据目录（用户上传的数据集）
      - ${DATA_DIR:-./data}:/app/data
      # 模型目录（预训练模型）
      - ${MODEL_DIR:-./models}:/app/models
      # 输出目录（训练输出）
      - ${OUTPUT_DIR:-./output}:/app/output
    environment:
      # CUDA 设备配置
      - CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
      - PYTHONUNBUFFERED=1
      - MODELSCOPE_CACHE=/app/models
      - HF_HOME=/app/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: ${GPU_COUNT:-1}  # 支持环境变量配置
              capabilities: [gpu]
    restart: unless-stopped
    stdin_open: true
    tty: true
```

**灵活配置** - 通过 `.env` 文件:
```bash
# GPU 配置
GPU_COUNT=2
CUDA_VISIBLE_DEVICES=0,1

# 端口配置
API_PORT=8000

# 目录配置（支持绝对路径）
DATA_DIR=/mnt/ssd/ms-swift/data
MODEL_DIR=/mnt/hdd/models
OUTPUT_DIR=/mnt/ssd/ms-swift/output
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