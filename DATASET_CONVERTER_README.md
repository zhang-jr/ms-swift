# 数据转换功能使用指南

## 概述

本功能实现了将标注平台的数据转换为 HuggingFace Datasets 格式（Parquet），方便数据工程师在训练平台中直接使用标注数据进行模型训练。

## 功能特性

- ✅ 支持图像、PDF、视频三种媒体类型
- ✅ 自动处理带标注框的 overlay 图片
- ✅ 支持 Parquet 和 JSONL 两种输出格式
- ✅ 自动分片保存（参考 FineVision 数据集）
- ✅ 提供完整的统计信息
- ✅ 前端可视化操作界面

## 使用流程

### 1. 准备标注数据

标注项目必须包含以下目录结构：

```
project_root/
├── instruction/         # 必需：包含 *.json 文件
├── uploads/            # 必需：原始媒体文件
└── overlays/           # 可选：带标注框的可视化图片
```

**通过 Docker volume 挂载标注数据**:

```bash
# 在 docker-compose.yml 中配置
services:
  ms-swift-custom-ui:
    volumes:
      - /path/to/annotation/projects:/app/data
```

或手动复制：

```bash
# 将标注项目复制到数据目录
cp -r /path/to/annotation/project /app/data/project_001
```

### 2. 在前端界面转换数据

1. 打开训练平台的**数据管理**页面
2. 找到标注项目文件夹（如 `project_001`）
3. 点击操作列的**"转换"**按钮（绿色图标）
4. 在弹出的模态框中配置转换参数：
   - **输出文件夹名称**: 默认为 `{project_name}_converted`
   - **输出格式**: Parquet（推荐）或 JSONL
   - **分片大小**: 100-200MB（推荐）
   - **使用 Overlay 图片**: 是（带标注框）或否（原始图片）
5. 点击**"开始转换"**
6. 等待转换完成，查看统计信息和生成的文件列表

### 3. 使用转换后的数据集

转换完成后，数据集会自动保存到 `/app/data/{output_name}/`。

在训练页面：
1. 选择数据集时，选择转换后的文件夹（如 `project_001_converted`）
2. 系统会自动读取该文件夹下的所有 Parquet 文件
3. 配置训练参数并开始训练

## API 使用

### 1. 验证标注项目结构

**端点**: `POST /api/data/validate-annotation-project`

**请求参数**:
```json
{
  "project_name": "project_001"
}
```

**响应示例**:
```json
{
  "valid": true,
  "project_name": "project_001",
  "instruction_count": 1000,
  "has_overlays": true,
  "structure": {
    "instruction": true,
    "uploads": true,
    "overlays": true
  }
}
```

### 2. 转换数据集

**端点**: `POST /api/data/convert`

**请求参数**:
```json
{
  "project_name": "project_001",
  "output_format": "parquet",
  "shard_size_mb": 100,
  "include_overlays": true,
  "output_name": "project_001_converted"
}
```

**响应示例**:
```json
{
  "status": "success",
  "output_folder": "project_001_converted",
  "output_files": [
    "train-00000-of-00005.parquet",
    "train-00001-of-00005.parquet",
    "train-00002-of-00005.parquet",
    "train-00003-of-00005.parquet",
    "train-00004-of-00005.parquet"
  ],
  "summary": {
    "total_samples": 1000,
    "media_types": {
      "image": 500,
      "pdf": 300,
      "video": 200
    },
    "total_images": 2500,
    "providers": {
      "qwen": 1000
    },
    "models": {
      "qwen-vl-plus": 1000
    }
  }
}
```

### 3. 获取支持的转换格式

**端点**: `GET /api/data/convert-formats`

**响应示例**:
```json
{
  "formats": [
    {
      "name": "parquet",
      "description": "Apache Parquet 格式，HuggingFace 推荐",
      "supports_sharding": true
    },
    {
      "name": "jsonl",
      "description": "JSON Lines 格式，用于调试",
      "supports_sharding": false
    }
  ],
  "media_types": [
    "image (jpg, png)",
    "pdf",
    "video (mp4)"
  ]
}
```

## 技术实现

### 后端服务

**文件**: `swift/custom_ui/backend/services/dataset_converter_service.py`

核心类：
- `DatasetConverter`: 数据集转换器
  - `convert_all()`: 转换所有 instruction 文件
  - `process_image_instruction()`: 处理图像类型
  - `process_pdf_instruction()`: 处理 PDF 类型
  - `process_video_instruction()`: 处理视频类型
  - `save_to_parquet_sharded()`: 分片保存为 Parquet
  - `get_statistics()`: 获取统计信息

核心函数：
- `validate_annotation_project()`: 验证项目结构

### API 端点

**文件**: `swift/custom_ui/backend/api/data.py`

- `POST /api/data/validate-annotation-project`: 验证标注项目
- `POST /api/data/convert`: 转换数据集
- `GET /api/data/convert-formats`: 获取支持的格式

### 前端界面

**文件**: `swift/custom_ui/frontend/src/pages/DataManagementPage.tsx`

组件功能：
- 数据集列表中的"转换"按钮（仅文件夹）
- 转换配置模态框
- 转换结果模态框

**文件**: `swift/custom_ui/frontend/src/api/data.ts`

API 客户端方法：
- `validateAnnotationProject()`: 验证项目
- `convertAnnotationDataset()`: 转换数据集
- `getConvertFormats()`: 获取格式

## 依赖

转换功能需要以下额外依赖（已添加到 `backend/requirements.txt`）:

```
pillow>=11.0.0  # 图像处理
pymupdf>=1.25.2  # PDF 处理（可选）
opencv-python>=4.10.0  # 视频处理（可选）
```

## 常见问题

### Q: 支持哪些媒体格式？

A: 支持图像（jpg/png）、PDF、视频（mp4）。

### Q: 什么是 overlay 图片？

A: Overlay 图片是标注平台生成的带有可视化标注框的图片，用于训练时提供更明确的视觉提示。

### Q: 为什么推荐使用 Parquet 格式？

A: Parquet 是 HuggingFace Datasets 的默认格式，支持高效的列式存储和压缩，加载速度快，适合大规模数据集。

### Q: 转换后的数据集可以直接用于训练吗？

A: 可以。转换后的数据集已经符合 HuggingFace Datasets 格式，可以直接在训练界面中选择使用。

### Q: 如何处理大型数据集？

A: 使用分片功能（shard_size_mb）将大型数据集分割成多个小文件，推荐每片 100-200MB。

### Q: 转换失败怎么办？

A:
1. 检查项目结构是否完整（instruction, uploads 目录必须存在）
2. 检查 instruction 文件格式是否正确
3. 查看后端日志了解具体错误信息
4. 确保有足够的磁盘空间

## 安全性

- ✅ 路径安全验证：防止路径遍历攻击
- ✅ 文件大小限制：避免系统资源耗尽
- ✅ 输出文件夹冲突检测：防止覆盖现有数据
- ✅ 权限控制：所有操作仅限于 `/app/data` 目录

## 性能优化建议

### 1. 分片策略

| 数据集大小 | 推荐分片大小 | 说明 |
|-----------|-------------|------|
| < 1GB     | 50-100MB    | 小数据集，加快加载速度 |
| 1-10GB    | 100-200MB   | 中等数据集，平衡性能 |
| > 10GB    | 200-500MB   | 大数据集，减少文件数 |

### 2. 内存优化

对于大型数据集：
- 增加系统内存
- 使用更小的分片大小
- 分批处理数据

### 3. 磁盘优化

- 使用 SSD 存储转换后的数据集
- 定期清理不需要的转换结果
- 使用 NFS 共享存储实现多机器共享

## 与标注平台集成

标注平台完成标注后，通过以下方式将数据同步到训练平台：

**方式 1: Docker Volume 挂载**（推荐）
```yaml
volumes:
  - /shared/annotation/projects:/app/data
```

**方式 2: 手动复制**
```bash
rsync -av /path/to/annotation/project/ /path/to/training/data/project_001/
```

**方式 3: NFS 共享**
```bash
mount -t nfs server:/annotation/projects /app/data
```

## 更新日志

### v1.0.0 (2025-12-15)

- ✅ 初始版本
- ✅ 支持图像、PDF、视频转换
- ✅ 提供前端可视化操作界面
- ✅ 支持 Parquet 和 JSONL 格式
- ✅ 自动分片功能
- ✅ 项目结构验证

## 支持

遇到问题？

1. 查看日志: `docker logs ms-swift-ui`
2. 查看 API 文档: http://localhost:8000/docs
3. 查看开发指南: [CLAUDE.md](./CLAUDE.md)
4. 提交 Issue 或联系开发团队
