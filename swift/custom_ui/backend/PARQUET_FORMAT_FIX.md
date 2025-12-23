# Parquet 格式修复说明

## 问题描述

在使用 HuggingFace Datasets 保存多模态训练数据到 Parquet 格式时，遇到了 **列式存储导致数据结构变形** 的问题。

### 原始问题

**期望的数据格式**（MS-SWIFT 训练需要的 chat template 格式）：
```json
{
  "messages": [
    {"role": "user", "content": "浙江的省会在哪？"},
    {"role": "assistant", "content": "浙江的省会在杭州。"}
  ]
}
```

**实际保存后读取的格式**（Parquet 列式存储）：
```python
{
  "messages": {
    "role": ["user", "assistant"],
    "content": ["浙江的省会在哪？", "浙江的省会在杭州。"]
  }
}
```

### 根本原因

Parquet 是 **列式存储格式**，当保存嵌套的列表结构（list of dict）时，会自动转换为列式表示：

```python
# 原始数据（行式）
[
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]

# Parquet 列式存储后
{
  "role": ["user", "assistant"],
  "content": ["...", "..."]
}
```

这种转换破坏了 MS-SWIFT 训练所需的 chat template 格式。

## 解决方案

将 `messages` 字段 **序列化为 JSON 字符串** 后再保存到 Parquet，这样可以：

1. ✅ 保持原始的嵌套列表结构
2. ✅ 利用 Parquet 的高效压缩和查询性能
3. ✅ 训练时只需一行代码反序列化即可使用

### 修改内容

**修改文件**: `dataset_converter_service.py`

**核心改动**:
```python
# 修改前（错误）
features = Features({
    "messages": Sequence({
        "role": Value("string"),
        "content": Value("string")
    }),
    ...
})
dataset = Dataset.from_list(results, features=features)

# 修改后（正确）
# 1. 序列化 messages 为 JSON 字符串
serialized_results = []
for sample in results:
    sample_copy = sample.copy()
    sample_copy["messages"] = json.dumps(sample["messages"], ensure_ascii=False)
    serialized_results.append(sample_copy)

# 2. Features 定义 messages 为字符串
features = Features({
    "messages": Value("string"),  # JSON 字符串
    ...
})
dataset = Dataset.from_list(serialized_results, features=features)
```

## 数据格式说明

### Parquet 文件中的存储格式

```json
{
  "messages": "[{\"role\": \"user\", \"content\": \"浙江的省会在哪？\"}, {\"role\": \"assistant\", \"content\": \"浙江的省会在杭州。\"}]",
  "images": ["base64_encoded_image_1", "base64_encoded_image_2"],
  "videos": ["/path/to/video1.mp4"],
  "source_file": "example.jpg",
  "media_type": "image",
  "llm_provider": "openai",
  "model_name": "gpt-4"
}
```

**关键点**:
- `messages`: **JSON 字符串**（不是列表）
- `images`: 列表（base64 字符串）
- `videos`: 列表（文件路径）

### 训练时的使用方法

MS-SWIFT 训练时需要反序列化 `messages` 字段：

```python
from datasets import load_dataset
import json

# 1. 加载 Parquet 数据集
dataset = load_dataset(
    "parquet",
    data_files="/app/data/project_001_converted/*.parquet",
    split="train"
)

# 2. 数据预处理：反序列化 messages
def preprocess(sample):
    """将 messages 从 JSON 字符串转换为 list of dict"""
    sample['messages'] = json.loads(sample['messages'])
    return sample

dataset = dataset.map(preprocess)

# 3. 现在数据格式正确，可以用于训练
print(dataset[0]['messages'])
# 输出: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
```

## 测试方法

使用提供的测试脚本验证数据格式：

```bash
python swift/custom_ui/backend/test_parquet_format.py \
  /app/data/project_001_converted/train-00000-of-00001.parquet
```

**测试脚本功能**:
- ✅ 验证 `messages` 字段是否为字符串类型
- ✅ 反序列化后验证是否为标准的 chat template 格式
- ✅ 显示训练时如何使用数据

## 影响范围

### 修改的函数

1. `DatasetConverter.save_to_parquet()` - 单文件保存
2. `DatasetConverter.save_to_parquet_sharded()` - 分片保存
3. `DatasetConverter.generate_dataset_infos()` - 元数据生成

### 向后兼容性

- ⚠️ **不兼容旧格式** - 之前生成的 Parquet 文件需要重新转换
- ✅ **JSONL 格式不受影响** - `save_to_jsonl()` 无需修改

## 其他多模态格式示例

### 图像数据
```json
{
  "messages": "[{\"role\": \"user\", \"content\": \"<image>两张图片有什么区别\"}, {\"role\": \"assistant\", \"content\": \"前一张是小猫，后一张是小狗\"}]",
  "images": ["base64_image_1", "base64_image_2"],
  "videos": []
}
```

### 音频数据
```json
{
  "messages": "[{\"role\": \"user\", \"content\": \"<audio>语音说了什么\"}, {\"role\": \"assistant\", \"content\": \"今天天气真好呀\"}]",
  "images": [],
  "videos": [],
  "audios": ["/xxx/x.mp3"]
}
```

### 视频数据
```json
{
  "messages": "[{\"role\": \"user\", \"content\": \"<video>视频中是什么\"}, {\"role\": \"assistant\", \"content\": \"一只小狗在草地上奔跑\"}]",
  "images": [],
  "videos": ["/xxx/x.mp4"]
}
```

### 混合多模态数据
```json
{
  "messages": "[{\"role\": \"system\", \"content\": \"你是个有用无害的助手\"}, {\"role\": \"user\", \"content\": \"<image>图片中是什么，<video>视频中是什么\"}, {\"role\": \"assistant\", \"content\": \"图片中是一个大象，视频中是一只小狗在草地上奔跑\"}]",
  "images": ["base64_image"],
  "videos": ["/xxx/x.mp4"]
}
```

## 常见问题

### Q1: 为什么不直接使用 JSONL 格式？

**A**: Parquet 格式有以下优势：
- 更高的压缩率（节省存储空间）
- 支持列式查询（可以只读取需要的列）
- 更快的加载速度（对于大数据集）
- HuggingFace 生态的标准格式

### Q2: 序列化 messages 会影响性能吗？

**A**: 影响很小：
- 序列化开销：在数据转换阶段一次性完成
- 反序列化开销：在训练时使用 `dataset.map()` 批量处理
- JSON 解析速度很快（Python 内置优化）

### Q3: 如何验证数据格式是否正确？

**A**: 使用提供的测试脚本：
```bash
python test_parquet_format.py <parquet_file>
```

## 总结

| 方面 | 修改前 | 修改后 |
|------|--------|--------|
| **messages 类型** | Sequence of dict | JSON 字符串 |
| **Parquet 存储** | 列式（结构变形） | 字符串（保持原样） |
| **训练使用** | ❌ 格式错误 | ✅ 需要反序列化 |
| **兼容性** | - | ⚠️ 需要重新转换旧数据 |

**核心改进**:
- ✅ 解决了 Parquet 列式存储破坏 chat template 格式的问题
- ✅ 保持了 Parquet 的高效性能
- ✅ 训练时只需一行代码反序列化即可使用
- ✅ 支持所有多模态数据格式（图像、音频、视频、混合）
