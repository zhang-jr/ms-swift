# MS-SWIFT Custom UI - Frontend

基于 React + Vite + Ant Design 的前端界面。

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:3000

## 构建

```bash
# 生产构建
npm run build

# 预览构建结果
npm run preview
```

## 技术栈

- React 18
- Vite 5
- Ant Design 5
- React Router 6
- Axios

## 目录结构

```
src/
├── api/              # API 客户端
│   ├── client.js    # axios 实例
│   ├── train.js     # 训练 API
│   └── infer.js     # 推理 API
├── pages/           # 页面组件
│   ├── TrainPage.jsx
│   ├── InferPage.jsx
│   ├── DeployPage.jsx
│   └── ModelsPage.jsx
├── components/      # 通用组件
├── App.jsx          # 主应用
└── main.jsx         # 入口文件
```

## 待开发功能

- [ ] WebSocket 实时日志
- [ ] 训练进度可视化
- [ ] 模型管理界面
- [ ] 部署管理界面
- [ ] 多模态输入支持
- [ ] 用户认证
- [ ] 主题切换
