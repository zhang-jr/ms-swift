# 标注数据集结构要求

## 📋 必需的目录结构

要使用**数据转换功能**，你的标注项目文件夹必须包含以下目录结构：

```
your_project/                     ← 项目根目录（例如 "example"）
├── instruction/                  ✅ 必需！存放标注的 instruction JSON 文件
│   ├── task_001.json
│   ├── task_002.json
│   └── ...
├── uploads/                      ✅ 必需！存放原始媒体文件
│   ├── image1.jpg
│   ├── document.pdf
│   ├── video.mp4
│   └── ...
└── overlays/                     ⚠️ 可选（带标注框的可视化图片）
    ├── image1_overlay.png
    ├── document/
    │   └── page_0000_overlay.png
    └── video/
        └── 000027_overlay.png
```

## ❌ 常见错误

### 错误 1: 缺少 `instruction` 目录
```
example/                          ❌ 错误！
├── data.json
└── images/
    └── img1.jpg
```

**错误提示**: "项目验证失败: 缺少必要的目录: instruction"

**解决方法**: 创建 `instruction` 目录并将 JSON 文件放入其中
```bash
mkdir -p example/instruction
mv example/data.json example/instruction/
```

### 错误 2: 缺少 `uploads` 目录
```
example/                          ❌ 错误！
├── instruction/
│   └── task.json
└── image.jpg                     ← 文件在根目录
```

**错误提示**: "项目验证失败: 缺少必要的目录: uploads"

**解决方法**: 创建 `uploads` 目录并将媒体文件放入其中
```bash
mkdir -p example/uploads
mv example/image.jpg example/uploads/
```

## ✅ 正确示例

### 示例 1: 图像标注项目
```
image_annotation_project/
├── instruction/
│   ├── img001.json              # {"image": "cat.jpg", "instruction": "描述这张图片", ...}
│   ├── img002.json
│   └── img003.json
├── uploads/
│   ├── cat.jpg
│   ├── dog.jpg
│   └── bird.jpg
└── overlays/                    # 可选
    ├── cat_overlay.png
    ├── dog_overlay.png
    └── bird_overlay.png
```

### 示例 2: PDF 标注项目
```
pdf_annotation_project/
├── instruction/
│   ├── doc1_page0.json          # {"pdf": "report.pdf", "annotations": [...], ...}
│   └── doc1_page1.json
├── uploads/
│   └── report.pdf
└── overlays/
    └── report/                  # PDF 的 overlay 按文档名分组
        ├── page_0000_overlay.png
        └── page_0001_overlay.png
```

### 示例 3: 视频标注项目
```
video_annotation_project/
├── instruction/
│   └── video1.json              # {"video": "demo.mp4", "annotations": [...], ...}
├── uploads/
│   └── demo.mp4
└── overlays/
    └── demo/                    # 视频的 overlay 按视频名分组
        ├── 000027_overlay.png   # 第 27 帧
        ├── 000055_overlay.png
        └── 000103_overlay.png
```

## 📝 Instruction JSON 格式

### 图像类型
```json
{
  "image": "cat.jpg",                      // 相对于 uploads/ 的路径
  "instruction": "描述这张图片中的内容",
  "raw_response": "图片中有一只橘色的猫...",
  "llm_provider": "openai",                // 可选
  "model_name": "gpt-4-vision",           // 可选
  "timestamp": "2025-01-01T12:00:00Z"     // 可选
}
```

### PDF 类型
```json
{
  "pdf": "report.pdf",
  "instruction": "总结这份报告的关键内容",
  "raw_response": "这份报告主要包含...",
  "annotations": [
    {"page": 0, "type": "text", "content": "..."},
    {"page": 1, "type": "table", "content": "..."}
  ],
  "llm_provider": "anthropic",
  "model_name": "claude-3-opus"
}
```

### 视频类型
```json
{
  "video": "demo.mp4",
  "instruction": "描述视频中发生的事件",
  "raw_response": "视频展示了...",
  "annotations": [
    {"frame": 27, "type": "object", "label": "car"},
    {"frame": 55, "type": "object", "label": "person"},
    {"frame": 103, "type": "timeline", "start": 0, "end": 5, "event": "开场"}
  ],
  "llm_provider": "google",
  "model_name": "gemini-pro-vision"
}
```

## 🔧 验证你的项目

### 方法 1: 使用前端界面
1. 上传你的项目文件夹到数据管理页面
2. 在数据集列表中找到你的项目
3. 点击"转换"按钮
4. 系统会自动验证目录结构

### 方法 2: 手动检查
在 Docker 容器中运行：
```bash
# 进入容器
docker exec -it ms-swift-ui bash

# 检查项目结构
tree /app/data/your_project

# 或使用 ls
ls -la /app/data/your_project/
ls -la /app/data/your_project/instruction/
ls -la /app/data/your_project/uploads/
```

## 📊 转换后的数据格式

转换成功后会生成 HuggingFace Datasets 格式：

```
your_project_converted/
├── train-00000-of-00003.parquet
├── train-00001-of-00003.parquet
└── train-00002-of-00003.parquet
```

每个 Parquet 文件包含：
- `messages`: 对话格式 (role, content)
- `images`: Base64 编码的图片列表
- `metadata`: 源文件信息、媒体类型、模型信息等

## 🚀 使用转换后的数据训练

在训练页面：
1. 选择数据集：`your_project_converted`
2. 选择模型：例如 `Qwen/Qwen2-VL-7B-Instruct`
3. 配置训练参数
4. 开始训练

系统会自动读取该文件夹下的所有 Parquet 文件。

## ❓ 常见问题

### Q: 我的文件夹结构正确，但仍然提示缺少目录？
A: 可能是以下原因：
1. 文件夹名称拼写错误（区分大小写）
2. Docker volume 挂载路径不正确
3. 权限问题（文件夹不可读）

解决方法：
```bash
# 检查实际路径
docker exec ms-swift-ui ls -la /app/data/

# 检查权限
docker exec ms-swift-ui ls -ld /app/data/your_project/
docker exec ms-swift-ui ls -ld /app/data/your_project/instruction/
```

### Q: 我可以没有 overlays 目录吗？
A: 可以！`overlays` 目录是可选的。如果没有 overlay 图片，转换时会使用原始媒体文件。

### Q: instruction 文件可以放在子目录中吗？
A: 可以！系统会递归扫描 `instruction/` 下的所有 `*.json` 文件：
```
instruction/
├── batch1/
│   ├── task1.json
│   └── task2.json
└── batch2/
    └── task3.json
```

### Q: uploads 文件可以组织成子目录吗？
A: 可以！只要 instruction JSON 中的路径相对于 `uploads/` 正确即可：
```json
{
  "image": "animals/cats/persian_cat.jpg",  // 相对于 uploads/
  ...
}
```

## 📚 参考资料

- **项目文档**: `CLAUDE.md` - 完整的开发指南
- **上传指南**: `FOLDER_UPLOAD_GUIDE.md` - 文件夹上传功能说明
- **快速开始**: `QUICKSTART.md` - 快速启动指南
- **项目总结**: `PROJECT_SUMMARY.md` - 项目概览

## 🆘 获取帮助

如果遇到问题：
1. 检查 Docker 容器日志：`docker logs ms-swift-ui`
2. 验证文件权限：`docker exec ms-swift-ui ls -la /app/data/`
3. 查看后端日志：容器内的 stdout 输出
