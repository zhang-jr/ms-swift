# MS-SWIFT Custom Web UI

基于 MS-SWIFT 的自定义 Web UI，提供用户友好的模型训练、推理和部署界面。

## 特性

- **模型训练**: 可视化配置训练参数，实时查看训练进度和日志
- **模型推理**: 加载模型进行对话式推理，支持自定义参数
- **模型部署**: 一键部署模型为 API 服务，支持 OpenAI 兼容接口
- **实时日志**: 通过 WebSocket 实时推送训练日志
- **现代化界面**: 基于 React + Ant Design 的响应式界面
- **Docker 部署**: 完整的 Docker 容器化支持

## 技术栈

### 后端
- **FastAPI**: 高性能异步 Web 框架
- **WebSocket**: 实时日志推送
- **MS-SWIFT**: 模型训练和推理引擎

### 前端
- **React 18**: 现代化前端框架
- **TypeScript**: 类型安全
- **Ant Design 5**: 企业级 UI 组件库
- **Vite**: 极速开发服务器和构建工具

## 快速开始

详细的快速开始指南请参考 [QUICKSTART.md](./QUICKSTART.md)

### Docker 部署 (推荐)

```bash
# 构建镜像
cd custom_ui/docker
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

访问 http://localhost:8000

### 本地开发

#### 后端开发

```bash
cd custom_ui/backend

# 安装依赖
pip install -r requirements.txt

# 启动后端
python app.py
```

后端 API: http://localhost:8000
API 文档: http://localhost:8000/docs

#### 前端开发

```bash
cd custom_ui/frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端界面: http://localhost:3000

## 项目结构

```
custom_ui/
├── backend/                # FastAPI 后端
│   ├── api/               # API 路由
│   │   ├── train.py       # 训练 API
│   │   ├── infer.py       # 推理 API
│   │   ├── deploy.py      # 部署 API
│   │   └── model.py       # 模型管理 API
│   ├── services/          # 业务逻辑层
│   │   ├── train_service.py
│   │   ├── infer_service.py
│   │   └── deploy_service.py
│   ├── app.py            # FastAPI 主应用
│   └── requirements.txt   # Python 依赖
├── frontend/              # React 前端
│   ├── src/
│   │   ├── api/          # API 客户端
│   │   ├── components/   # React 组件
│   │   ├── pages/        # 页面组件
│   │   ├── types/        # TypeScript 类型
│   │   └── App.tsx       # 主应用
│   ├── package.json
│   └── vite.config.ts
├── docker/                # Docker 配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── start.sh
├── README.md
└── QUICKSTART.md
```

## API 文档

启动后端服务后，访问以下地址查看完整的 API 文档:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 主要 API 端点

#### 训练相关
- `POST /api/train/start` - 启动训练任务
- `GET /api/train/status/{task_id}` - 获取训练状态
- `POST /api/train/stop/{task_id}` - 停止训练
- `WS /ws/logs/{task_id}` - 实时训练日志 (WebSocket)

#### 推理相关
- `POST /api/infer/load-model` - 加载模型
- `POST /api/infer/chat` - 对话推理
- `POST /api/infer/unload-model` - 卸载模型

#### 部署相关
- `POST /api/deploy/start` - 启动部署服务
- `GET /api/deploy/status/{deployment_id}` - 获取部署状态
- `POST /api/deploy/stop/{deployment_id}` - 停止部署

#### 模型管理
- `GET /api/model/models` - 获取模型列表
- `GET /api/model/datasets` - 获取数据集列表

## 功能说明

### 1. 模型训练

在训练页面可以:
- 选择预训练模型和数据集
- 配置 LoRA 参数 (rank, alpha, dropout)
- 设置训练超参数 (学习率, batch size, epochs 等)
- 实时查看训练进度和 loss
- 通过 WebSocket 查看实时训练日志

### 2. 模型推理

在推理页面可以:
- 加载模型 (支持基础模型和 LoRA adapter)
- 配置推理参数 (temperature, top_p, top_k)
- 进行对话式推理
- 查看 token 使用统计

### 3. 模型部署

在部署页面可以:
- 将模型部署为 API 服务
- 配置服务端口和推理参数
- 支持 vLLM 加速
- 生成 OpenAI 兼容的 API 端点

## 开发指南

### 添加新的 API 端点

1. 在 `backend/api/` 目录下创建或修改路由文件
2. 在 `backend/services/` 目录下实现业务逻辑
3. 在 `backend/app.py` 中注册路由

### 添加新的前端页面

1. 在 `frontend/src/pages/` 目录下创建页面组件
2. 在 `frontend/src/api/` 目录下添加 API 客户端
3. 在 `frontend/src/types/` 目录下定义 TypeScript 类型
4. 在 `frontend/src/App.tsx` 中添加路由

## 常见问题

### Q: 如何连接到真实的 MS-SWIFT 引擎?

A: 当前实现使用模拟数据进行演示。要连接真实的 MS-SWIFT 引擎，需要在 `backend/services/` 中的服务类里取消注释 TODO 部分的代码，导入并调用 `swift.llm` 模块的相关函数。

### Q: WebSocket 连接失败?

A: 确保:
1. 后端服务正常运行
2. WebSocket URL 配置正确 (开发环境会自动代理)
3. 防火墙允许 WebSocket 连接

### Q: 前端构建失败?

A: 确保:
1. Node.js 版本 >= 18
2. 运行 `npm install` 安装所有依赖
3. 检查是否有 TypeScript 类型错误

## 许可证

本项目基于 MS-SWIFT，遵循相同的开源许可证。

## 参考资源

- [MS-SWIFT 官方文档](https://swift.readthedocs.io/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [React 文档](https://react.dev/)
- [Ant Design 文档](https://ant.design/)

## 贡献

欢迎提交 Issue 和 Pull Request!
