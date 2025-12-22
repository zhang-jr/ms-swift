# 数据转换功能重构 - 适配 HuggingFace Datasets 标准

**更新日期**: 2025-12-22
**Commit**: `66b881f5`

## 📋 概述

重构了数据转换功能，使其完全符合 HuggingFace `datasets` 库的标准，支持 `load_dataset()` 直接加载，并优化了目录结构和用户体验。

## 🎯 核心改进

### 1️⃣ **输出到项目内 data/ 目录**

**旧版本**（创建独立文件夹）:
```
/app/data/
├── example_project/          ← 原始项目
└── example_project_converted/ ← 转换后的数据（独立文件夹）
    └── train-00000.parquet
```

**新版本**（项目内 data/ 目录）:
```
/app/data/
└── example_project/          ← 原始项目
    ├── instructions/         ← 标注数据
    ├── uploads/              ← 原始媒体
    ├── overlays/             ← 可视化标注
    └── data/                 ✅ 转换后输出（符合 datasets 标准）
        ├── train-00000-of-00002.parquet
        └── dataset_infos.json
```

**优势**:
- ✅ 符合 HuggingFace datasets 库的目录结构标准
- ✅ 转换后用户无需记住新的文件夹名称
- ✅ `load_dataset('/app/data/example_project')` 自动识别 data/ 目录
- ✅ 数据和项目保持在一起，便于管理

### 2️⃣ **自动生成 dataset_infos.json**

新增 `dataset_infos.json` 文件，加速 `datasets` 库加载：

```json
{
  "default": {
    "description": "Annotation dataset for vision tasks - example_project",
    "features": {
      "messages": {
        "feature": {
          "role": {"dtype": "string"},
          "content": {"dtype": "string"}
        }
      },
      "images": {
        "feature": {"dtype": "string"}
      },
      "metadata": {
        "source_file": {"dtype": "string"},
        "media_type": {"dtype": "string"},
        "llm_provider": {"dtype": "string"},
        "model_name": {"dtype": "string"}
      }
    },
    "splits": {
      "train": {
        "name": "train",
        "num_bytes": 12345678,
        "num_examples": 100,
        "dataset_name": "example_project"
      }
    },
    "download_size": 12345678,
    "dataset_size": 12345678
  }
}
```

**优势**:
- ✅ `datasets` 库无需扫描所有文件即可获取元数据
- ✅ 加速数据集加载
- ✅ 提供完整的特征定义

### 3️⃣ **支持新的目录结构 (instructions/)**

**旧版本**:
```
project/
├── instruction/    ← 单数，扁平结构
│   ├── task1.json
│   └── task2.json
└── uploads/
```

**新版本** (支持媒体类型分组):
```
project/
├── instructions/   ← 复数，支持子目录
│   ├── image/
│   │   └── test_data/
│   │       └── test_imgs/
│   │           ├── cover_0001_instruction.json
│   │           └── cover_0002_instruction.json
│   ├── pdf/
│   │   └── test_data/
│   │       └── test_pdf/
│   │           └── Paper_instruction.json
│   └── video/
│       └── test_data/
│           └── test_videos/
│               └── TestVideo1_instruction.json
└── uploads/
    └── test_data/
        ├── test_imgs/
        ├── test_pdf/
        └── test_videos/
```

**优势**:
- ✅ 按媒体类型分组（image/pdf/video）
- ✅ 保留原始的子目录结构
- ✅ 更清晰的数据组织
- ✅ 递归扫描所有 JSON 文件

### 4️⃣ **分片大小优化**

**旧配置**:
- 默认: 100MB
- 步进: 手动输入
- 最大: 500MB

**新配置**:
- 默认: 500MB ✅
- 步进: 100MB（+/- 按钮）✅
- 最大: 2000MB
- UI: InputNumber 组件（支持点击调整）

**原因**:
- HuggingFace Hub 推荐的 Parquet 分片大小为 500MB-1GB
- 方便用户快速调整（100MB 为单位）

### 5️⃣ **简化用户体验**

**旧版本**:
1. 用户需要输入"输出文件夹名称"
2. 转换后需要记住新的文件夹名称
3. 训练时选择 `example_project_converted`

**新版本**:
1. 自动输出到 `{project_name}/data/` ✅
2. 转换完成后，直接使用项目名称 ✅
3. 训练时选择 `example_project`（系统自动读取 data/ 目录）

## 🛠️ 技术实现

### 后端 (`dataset_converter_service.py`)

**核心改动**:

1. **初始化改进**:
```python
def __init__(self, project_name: str):
    self.project_name = project_name
    self.project_root = DATA_DIR / project_name
    self.instructions_dir = self.project_root / "instructions"  # 改为复数
    self.data_dir = self.project_root / "data"  # 新增输出目录
```

2. **生成元数据**:
```python
def generate_dataset_infos(
    self,
    output_files: List[str],
    num_samples: int,
    data_dir: Path,
) -> Dict[str, Any]:
    """生成 dataset_infos.json（HuggingFace 标准）"""
    # 计算总大小
    total_bytes = sum(
        (data_dir / f).stat().st_size
        for f in output_files
        if (data_dir / f).exists()
    )

    # 生成元数据
    dataset_infos = {
        "default": {
            "description": f"Annotation dataset - {self.project_name}",
            "features": {...},
            "splits": {
                "train": {
                    "num_bytes": total_bytes,
                    "num_examples": num_samples,
                }
            },
            "download_size": total_bytes,
            "dataset_size": total_bytes,
        }
    }

    # 保存到 data/dataset_infos.json
    with open(data_dir / "dataset_infos.json", "w") as f:
        json.dump(dataset_infos, f, indent=2)
```

3. **验证逻辑更新**:
```python
def validate_annotation_project(project_name: str):
    instructions_dir = project_root / "instructions"  # 改为复数

    if not instructions_dir.exists():
        return {"valid": False, "error": "缺少必需的目录: instructions"}

    # 递归扫描所有 JSON 文件
    instruction_files = list(instructions_dir.rglob("*.json"))
```

### 后端 API (`api/data.py`)

**核心改动**:

```python
@router.post("/convert")
async def convert_annotation_dataset(request: ConvertRequest):
    # 输出到项目内的 data/ 目录
    output_dir = converter.data_dir

    # 清空已存在的 data/ 目录
    if output_dir.exists() and any(output_dir.iterdir()):
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存 Parquet 文件
    output_files = converter.save_to_parquet_sharded(
        results,
        output_dir=str(output_dir),
        output_prefix="train",
        max_shard_size_mb=request.shard_size_mb,
    )

    # 生成 dataset_infos.json（仅 Parquet 格式）
    converter.generate_dataset_infos(
        output_files=output_files,
        num_samples=len(results),
        data_dir=output_dir,
    )

    return ConvertResponse(
        status="success",
        output_folder=f"{request.project_name}/data",  # 返回相对路径
        output_files=output_files,
        summary=stats,
    )
```

### 前端 (`DataManagementPage.tsx`)

**核心改动**:

1. **默认配置修改**:
```typescript
const [convertConfig, setConvertConfig] = useState<ConvertRequest>({
  project_name: '',
  output_format: 'parquet',
  shard_size_mb: 500,  // 默认 500MB
  include_overlays: true,
  output_name: '',  // 不再需要用户输入
})
```

2. **UI 改进**:
```tsx
{/* 删除了"输出文件夹名称"输入框 */}
<div>
  <div>项目名称:</div>
  <Input value={convertConfig.project_name} disabled />
  <div style={{ fontSize: 12 }}>
    转换后的数据将保存到: {convertConfig.project_name}/data/
  </div>
</div>

{/* 分片大小使用 InputNumber */}
<InputNumber
  min={0}
  max={2000}
  step={100}  // 100MB 步进
  value={convertConfig.shard_size_mb}
  onChange={(value) => setConvertConfig({
    ...convertConfig,
    shard_size_mb: value || 500
  })}
  style={{ width: '100%' }}
/>
```

3. **使用指南更新**:
```tsx
<div>
  ✅ 转换完成！使用 datasets 库加载:
  1. 在训练页面选择数据集时，输入项目名称: "{convertConfig.project_name}"
  2. 系统会自动从 {convertResult.output_folder} 读取 Parquet 文件
  3. 支持 HuggingFace datasets.load_dataset() 直接加载
  4. 已生成 dataset_infos.json，确保快速加载
</div>
```

## 📊 使用示例

### Python 代码加载数据集

```python
from datasets import load_dataset

# 方法 1: 直接加载项目（推荐）
dataset = load_dataset('/app/data/example_project')
# 自动识别 example_project/data/ 目录

# 方法 2: 指定 data/ 目录
dataset = load_dataset('/app/data/example_project/data')

# 查看数据集信息
print(dataset)
# DatasetDict({
#     train: Dataset({
#         features: ['messages', 'images', 'metadata'],
#         num_rows: 100
#     })
# })

# 访问数据
for sample in dataset['train']:
    messages = sample['messages']
    images = sample['images']
    metadata = sample['metadata']
```

### 训练界面使用

1. 在数据管理页面点击"转换"按钮
2. 配置转换参数（默认 500MB 分片）
3. 转换完成后，在训练页面：
   - 数据集名称: `example_project`（系统自动读取 data/ 目录）
   - 或者: `example_project/data`

## 🔄 迁移指南

### 从旧版本迁移

**场景 1: 已有旧版本转换的数据**

如果你之前使用旧版本转换生成了 `example_project_converted/` 文件夹：

```bash
# 进入容器
docker exec -it ms-swift-ui bash

# 移动数据到项目内的 data/ 目录
mkdir -p /app/data/example_project/data
mv /app/data/example_project_converted/*.parquet /app/data/example_project/data/

# 删除旧文件夹
rm -rf /app/data/example_project_converted
```

**场景 2: 旧的目录结构 (instruction/)**

如果你的项目使用旧的 `instruction/` 目录：

```bash
# 重命名为 instructions/
mv /app/data/example_project/instruction /app/data/example_project/instructions

# 重新转换
# 在前端点击"转换"按钮即可
```

## ⚠️ 注意事项

### 1. 数据会被覆盖

转换时会**清空并重建** `data/` 目录。如果你手动修改过 data/ 目录中的文件，转换前请备份！

### 2. 目录结构要求

新版本要求项目结构为：
```
project/
├── instructions/   ✅ 必需（复数）
├── uploads/       ✅ 必需
└── overlays/      ⚠️  可选
```

旧版本的 `instruction/`（单数）不再支持，需要重命名为 `instructions/`。

### 3. 分片大小建议

- **小数据集** (< 500MB): 设置为 0（不分片）
- **中等数据集** (500MB - 5GB): 使用默认 500MB
- **大数据集** (> 5GB): 使用 1000MB 或更大

### 4. dataset_infos.json 仅在 Parquet 格式生成

如果选择 JSONL 格式输出，不会生成 `dataset_infos.json`。建议使用 Parquet 格式以获得最佳性能。

## 📚 相关文档

- **DATASET_README.md** - 数据集结构详细说明
- **FOLDER_UPLOAD_GUIDE.md** - 文件夹上传功能说明
- **CLAUDE.md** - 完整开发指南
- **PROJECT_SUMMARY.md** - 项目概览

## 🐛 常见问题

### Q: 转换后在训练页面找不到数据集？

**A**: 确保在训练页面选择数据集时，输入**项目名称**（例如 `example_project`），而不是 `example_project/data`。系统会自动识别 data/ 目录。

### Q: 提示"缺少必需的目录: instructions"？

**A**: 你的项目使用的是旧版本的 `instruction/` 目录（单数）。请重命名为 `instructions/`（复数）：
```bash
mv /app/data/your_project/instruction /app/data/your_project/instructions
```

### Q: 如何验证 dataset_infos.json 是否正确？

**A**: 检查文件内容：
```bash
cat /app/data/example_project/data/dataset_infos.json
```

应该包含 `features`、`splits`、`num_examples` 等字段。

### Q: 转换失败，显示权限错误？

**A**: 检查目录权限：
```bash
docker exec ms-swift-ui ls -la /app/data/example_project/
docker exec ms-swift-ui chmod -R 755 /app/data/example_project/
```

## 🎉 总结

这次重构使数据转换功能：
- ✅ 完全符合 HuggingFace datasets 标准
- ✅ 支持 `load_dataset()` 直接加载
- ✅ 简化了用户操作流程
- ✅ 提升了数据集加载速度
- ✅ 改善了数据组织结构

现在用户可以无缝地在标注、转换、训练之间切换，无需关心底层的文件路径和格式转换细节！
