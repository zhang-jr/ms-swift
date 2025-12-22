# 数据集转换功能说明

**更新日期**: 2025-12-22
**Commit**: `4225607b`

## 📋 概述

数据集转换功能将标注平台的原始标注数据转换为 HuggingFace Datasets 格式，用于模型训练。

## ⚠️ 重要修正（2025-12-22）

### 关键问题修复

**之前的实现存在的问题**:
1. ❌ **错误的数据源**: 从 `overlays/` 目录读取数据
2. ❌ **Parquet 格式错误**: 嵌套结构导致 "Repetition level histogram size mismatch"
3. ❌ **dataset_infos.json 位置错误**: 保存在 `data/` 目录内
4. ❌ **PDF 处理依赖**: 依赖 overlay 图片，而不是原始 PDF

**修复后的实现**:
1. ✅ **正确的数据源**: 从 `uploads/` 目录读取原始媒体文件
2. ✅ **Parquet 兼容**: messages 和 images 存储为 JSON 字符串
3. ✅ **标准位置**: dataset_infos.json 与 data/ 目录平行
4. ✅ **PDF 提取**: 使用 PyMuPDF 从原始 PDF 提取页面图片

## 🎯 核心原则

### 1. overlays 只是可视化，不是训练数据源

**overlays 文件夹的作用**:
- 标注工具生成的可视化结果（如带标注框的图片）
- 用于人工检查标注质量
- **不适合作为训练数据**（可能缺失、不完整）

**训练数据来源**:
- `uploads/` 目录包含用户上传的原始媒体文件
- 图片: 直接使用原始图片
- PDF: 从原始 PDF 提取页面
- 视频: 暂时跳过（文件过大）

### 2. 数据格式兼容 HuggingFace Datasets

**输出格式**:
```
project_name/
├── instructions/          # 标注数据（输入）
│   ├── image/
│   ├── pdf/
│   └── video/
├── uploads/              # 原始媒体文件（输入）
│   ├── images/
│   ├── pdfs/
│   └── videos/
├── data/                 # 转换后的数据集（输出）
│   ├── train-00000-of-00005.parquet
│   ├── train-00001-of-00005.parquet
│   └── ...
└── dataset_infos.json    # 数据集元信息（与 data/ 平行）
```

**Parquet Schema**:
```python
{
    "messages": "string",      # JSON 字符串，如 '[{"role":"user","content":"..."}]'
    "images": "string",        # JSON 字符串，如 '["base64_image_1", "base64_image_2"]'
    "source_file": "string",   # 原始文件路径
    "media_type": "string",    # image/pdf/video
    "llm_provider": "string",  # LLM 提供商
    "model_name": "string"     # 模型名称
}
```

## 🚀 使用方法

### 1. 准备标注项目

确保项目结构如下:
```
my_annotation_project/
├── instructions/          # 必需
│   ├── image/            # 可选（有图片标注时）
│   │   └── *.json
│   ├── pdf/              # 可选（有 PDF 标注时）
│   │   └── *.json
│   └── video/            # 可选（有视频标注时）
│       └── *.json
└── uploads/              # 必需
    ├── images/           # 对应图片标注
    ├── pdfs/             # 对应 PDF 标注
    └── videos/           # 对应视频标注
```

**注意**:
- `instructions/` 和 `uploads/` 是必需目录
- `overlays/` 目录可有可无（不再使用）
- 用户可以只标注部分类型（如只标注图片，不标注 PDF）

### 2. 上传到数据管理界面

1. 打开数据管理页面
2. 点击"上传文件夹"
3. 选择整个标注项目文件夹
4. 等待上传完成

### 3. 验证项目结构

上传后，系统会自动验证:
- ✅ 检查 `instructions/` 和 `uploads/` 目录是否存在
- ✅ 统计 instruction 文件数量
- ✅ 统计各类型数据（image/pdf/video）的数量

### 4. 执行转换

1. 在数据集列表中找到上传的项目文件夹
2. 点击"转换"按钮
3. 配置转换参数:
   - **输出格式**: Parquet（推荐）或 JSONL
   - **分片大小**: 默认 500MB（可调整为 100/200/.../2000MB）
   - **使用 overlays**: 忽略（不再使用）
4. 点击"开始转换"

### 5. 转换结果

转换成功后，会在项目目录下生成:
```
my_annotation_project/
├── data/                           # 新生成
│   ├── train-00000-of-00005.parquet
│   ├── train-00001-of-00005.parquet
│   └── ...
└── dataset_infos.json              # 新生成（与 data/ 平行）
```

**统计信息**:
```json
{
  "total_samples": 1000,
  "media_types": {
    "image": 800,
    "pdf": 200,
    "video": 0
  },
  "total_images": 1200,
  "providers": {
    "openai": 500,
    "claude": 500
  },
  "models": {
    "gpt-4": 500,
    "claude-3": 500
  }
}
```

### 6. 在训练中使用

**方法 A: 使用转换后的数据集**

在训练界面选择数据集时:
1. 数据集名称: `my_annotation_project/data`
2. 系统会自动加载所有 Parquet 分片
3. 自动读取 `dataset_infos.json` 加速加载

**方法 B: 使用 HuggingFace datasets 库**

```python
from datasets import load_dataset

# 加载数据集（从项目根目录）
dataset = load_dataset(
    "parquet",
    data_dir="/app/data/my_annotation_project/data"
)

# 访问样本
sample = dataset['train'][0]

# 解析 JSON 字符串
import json
messages = json.loads(sample['messages'])
images = json.loads(sample['images'])

print(f"Messages: {messages}")
print(f"Images count: {len(images)}")
```

## 📊 支持的媒体类型

### 图片（Image）

**支持格式**: JPG, PNG, GIF, BMP, WebP

**处理流程**:
1. 从 `uploads/{image_path}` 读取原始图片
2. 转换为 base64 编码
3. 构建多模态 messages:
   ```json
   [
     {"role": "user", "content": "<image>请描述这张图片"},
     {"role": "assistant", "content": "这是一张..."}
   ]
   ```
4. 存储为 JSON 字符串

### PDF

**处理流程**:
1. 从 `uploads/{pdf_path}` 读取原始 PDF
2. 使用 PyMuPDF 提取标注的页面
3. 每页转换为 PNG 图片（2x 缩放）
4. 转换为 base64 编码
5. 构建多模态 messages（多图片）:
   ```json
   [
     {"role": "user", "content": "<image><image>请总结这些页面"},
     {"role": "assistant", "content": "这些页面..."}
   ]
   ```

**依赖**: PyMuPDF (已包含在 requirements.txt)

### 视频（Video）

**当前状态**: 暂时跳过（文件过大）

**未来计划**:
- 提取关键帧
- 保存视频路径
- 使用视频采样策略

## 🔧 配置选项

### 分片大小 (Shard Size)

**默认**: 500MB
**可选**: 100MB, 200MB, ..., 2000MB（步进 100MB）

**建议**:
- 小数据集（<1000 样本）: 100-200MB
- 中等数据集（1000-10000 样本）: 500MB
- 大数据集（>10000 样本）: 1000-2000MB

**影响**:
- 分片过小: 文件数量过多，加载慢
- 分片过大: 单文件过大，内存占用高

### 输出格式

**Parquet（推荐）**:
- ✅ 列式存储，加载快
- ✅ 压缩率高
- ✅ HuggingFace datasets 默认格式
- ✅ 支持增量加载

**JSONL**:
- ✅ 文本格式，易读
- ❌ 文件体积大
- ❌ 加载慢

## 🐛 常见问题

### Q1: 转换失败，提示"原始图片不存在"

**原因**: `uploads/` 目录中缺少对应的媒体文件

**解决方案**:
1. 检查 `uploads/` 目录结构
2. 确保 instruction 文件中的路径与 uploads/ 中的文件路径一致
3. 示例:
   ```json
   // instruction 文件
   {"image": "images/photo1.jpg", ...}

   // 对应文件应该存在于
   uploads/images/photo1.jpg
   ```

### Q2: PDF 转换失败，提示"PyMuPDF 未安装"

**原因**: 缺少 PyMuPDF 库

**解决方案**:
```bash
pip install pymupdf>=1.25.2
```

### Q3: load_dataset() 加载失败，提示格式错误

**原因**: Parquet 文件格式不兼容（旧版本转换的数据）

**解决方案**:
1. 删除旧的 `data/` 目录
2. 重新执行转换
3. 使用最新版本（Commit: 4225607b 之后）

### Q4: 训练时 messages 是字符串而不是列表

**说明**: 这是正确的行为！

**原因**: 为了兼容 Parquet 格式，messages 和 images 存储为 JSON 字符串

**使用方法**:
```python
import json

# 加载样本
sample = dataset['train'][0]

# 解析 JSON 字符串
messages = json.loads(sample['messages'])
images = json.loads(sample['images'])

# 现在 messages 是列表了
for msg in messages:
    print(msg['role'], msg['content'])
```

### Q5: 只标注了图片，PDF 怎么办？

**说明**: 支持部分标注！

**行为**:
- 如果 `instructions/pdf/` 为空，转换时会跳过 PDF
- 只会转换有标注的类型（image/pdf/video）
- 不影响转换结果

## 📚 技术细节

### Parquet Schema 设计

**为什么 messages 和 images 是字符串？**

Parquet 不支持嵌套的复杂结构（如 `List[Dict]`），会导致错误:
```
OSError: Repetition level histogram size mismatch
```

**解决方案**:
存储为 JSON 字符串，使用时再解析:
```python
# 存储时
data = {
    "messages": json.dumps([{"role": "user", "content": "..."}], ensure_ascii=False),
    "images": json.dumps(["base64_1", "base64_2"], ensure_ascii=False)
}

# 加载时
messages = json.loads(data['messages'])
images = json.loads(data['images'])
```

### dataset_infos.json 位置

**为什么在项目根目录？**

HuggingFace datasets 库的标准结构:
```
dataset_name/
├── data/                # 数据文件
│   ├── train-00000.parquet
│   └── ...
└── dataset_infos.json   # 元信息（与 data/ 平行）
```

如果放在 `data/` 内部，`load_dataset()` 无法正确识别。

### PDF 页面提取

**为什么使用 PyMuPDF？**

- ✅ 高性能（C++ 底层）
- ✅ 支持高分辨率渲染（2x 缩放）
- ✅ 跨平台兼容
- ✅ 输出高质量 PNG

**示例代码**:
```python
import pymupdf

doc = pymupdf.open("document.pdf")
page = doc[0]  # 第一页
pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))  # 2x 缩放
img_bytes = pix.tobytes("png")
doc.close()
```

## 🎉 总结

**修复后的转换功能**:
- ✅ 使用正确的数据源（uploads/ 而非 overlays/）
- ✅ 兼容 HuggingFace datasets 库（Parquet 格式）
- ✅ 符合标准目录结构（dataset_infos.json 位置）
- ✅ 支持 PDF 页面提取（PyMuPDF）
- ✅ 支持部分标注场景
- ✅ 提供详细的统计信息

现在可以放心使用数据转换功能，生成的数据集可直接用于模型训练！

---

**相关文档**:
- `CLAUDE.md` - 完整开发指南
- `DEPLOY_INFER_GUIDE.md` - 部署和推理功能说明
- `FOLDER_UPLOAD_GUIDE.md` - 文件夹上传功能说明
- `PROJECT_SUMMARY.md` - 项目概览
