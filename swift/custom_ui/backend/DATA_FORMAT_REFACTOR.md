# 数据格式重构说明

## 重构概述

将数据格式从复杂的 `messages` 格式改为 **MS-SWIFT 原生支持的 query-response 格式**，同时修正媒体数据为标准的 **Data URL 格式**。

## 改动原因

### 问题 1: messages 字段复杂嵌套

**之前的实现**（存在问题）：
```python
# Parquet 存储格式
{
  "messages": "[{\"role\": \"user\", \"content\": \"...\"}, ...]",  # JSON 字符串
  "images": ["base64_string"],  # 纯 base64
  "videos": ["/path/to/video.mp4"]
}
```

**问题**：
- `messages` 需要序列化为 JSON 字符串
- MS-SWIFT 代码可能没有 `json.loads()` 解析逻辑
- 增加了训练时的复杂度

### 问题 2: 媒体数据格式不标准

**之前的实现**：
```python
"images": ["iVBORw0KGgoAAAANSUhEUgAA..."]  # 纯 base64 字符串
```

**MS-SWIFT 官方要求**：
```python
"images": ["data:image/jpg;base64,iVBORw0KGgoAAAANSUhEUgAA..."]  # Data URL 格式
"videos": ["data:video/mp4;base64,{base64}"]  # 或路径
```

## 解决方案

### 1. 采用 query-response 格式

**MS-SWIFT 官方格式**：
```python
{
  "system": "<system>",
  "query": "<query>",
  "response": "<response>",
  "history": [["<query1>", "<response1>"]]
}
```

**我们的实现**（完全兼容）：
```python
{
  "query": "<image>图片中有什么异常",  # instruction → query
  "response": "检测到以下异常...",     # raw_response → response
  "system": "",                      # 系统提示（可选）
  "history": [],                     # 历史对话（单轮 QA 为空）
  "images": ["data:image/jpeg;base64,{base64}"],
  "videos": ["/path/to/video.mp4"],
  "source_file": "example.jpg",
  "media_type": "image",
  "llm_provider": "openai",
  "model_name": "gpt-4"
}
```

**优势**：
- ✅ 所有字段都是简单类型（字符串或列表）
- ✅ 无需 JSON 序列化/反序列化
- ✅ MS-SWIFT 原生支持，无需额外处理
- ✅ 适合单轮 QA 场景

### 2. 使用 Data URL 格式

**图片**：
```python
# 之前（错误）
"images": ["iVBORw0KGgoAAAANSUhEUgAA..."]

# 现在（正确）
"images": ["data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAA..."]
```

**视频**：
```python
# 路径（推荐，视频太大）
"videos": ["/app/data/project_001/uploads/video.mp4"]

# 或 Data URL（可选）
"videos": ["data:video/mp4;base64,{base64}"]
```

**PDF（提取为图片）**：
```python
"images": [
  "data:image/png;base64,{page1_base64}",
  "data:image/png;base64,{page2_base64}",
  ...
]
```

## 修改内容

### 修改的文件

1. **`dataset_converter_service.py`** - 核心转换服务
   - `image_to_data_url()` - 新增：将图片转为 Data URL
   - `process_image_instruction()` - 改为 query-response 格式
   - `process_pdf_instruction()` - 改为 query-response 格式 + Data URL
   - `process_video_instruction()` - 改为 query-response 格式
   - `save_to_parquet()` - 更新 Features 定义
   - `save_to_parquet_sharded()` - 更新 Features 定义
   - `generate_dataset_infos()` - 更新元数据描述

2. **`test_parquet_format.py`** - 测试脚本
   - 验证 query-response 格式
   - 验证 Data URL 格式
   - 显示训练使用示例

3. **`DATA_FORMAT_REFACTOR.md`** - 本文档

### 代码对比

#### 之前的实现

```python
# process_image_instruction()
def process_image_instruction(self, inst_data: Dict) -> Optional[Dict]:
    image_b64 = self.image_to_base64(upload_path)

    messages = [
        {"role": "user", "content": f"<image>{inst_data['instruction']}"},
        {"role": "assistant", "content": inst_data["raw_response"]},
    ]

    return {
        "messages": messages,  # 需要序列化
        "images": [image_b64],  # 纯 base64
        "videos": [],
        ...
    }

# save_to_parquet()
def save_to_parquet(self, results, output_path):
    # 序列化 messages
    serialized_results = []
    for sample in results:
        sample_copy = sample.copy()
        sample_copy["messages"] = json.dumps(sample["messages"])
        serialized_results.append(sample_copy)

    features = Features({
        "messages": Value("string"),  # JSON 字符串
        ...
    })
    dataset = Dataset.from_list(serialized_results, features=features)
```

#### 现在的实现

```python
# image_to_data_url()（新增）
def image_to_data_url(self, image_path: Path) -> str:
    ext = image_path.suffix.lower().lstrip('.')
    if ext == 'jpg':
        ext = 'jpeg'

    with open(image_path, "rb") as f:
        base64_data = base64.b64encode(f.read()).decode("utf-8")

    return f"data:image/{ext};base64,{base64_data}"

# process_image_instruction()
def process_image_instruction(self, inst_data: Dict) -> Optional[Dict]:
    image_data_url = self.image_to_data_url(upload_path)

    return {
        "query": f"<image>{inst_data['instruction']}",  # 简单字符串
        "response": inst_data["raw_response"],          # 简单字符串
        "system": "",
        "history": [],
        "images": [image_data_url],  # Data URL 格式
        "videos": [],
        ...
    }

# save_to_parquet()
def save_to_parquet(self, results, output_path):
    # 无需序列化，直接保存
    features = Features({
        "query": Value("string"),
        "response": Value("string"),
        "system": Value("string"),
        "history": Sequence(Sequence(Value("string"))),
        "images": Sequence(Value("string")),  # Data URL 列表
        "videos": Sequence(Value("string")),
        ...
    })
    dataset = Dataset.from_list(results, features=features)
```

## 数据格式示例

### 单张图片

```json
{
  "query": "<image>图片中有什么异常",
  "response": "检测到以下异常：文本模糊、颜色失真",
  "system": "",
  "history": [],
  "images": ["data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA..."],
  "videos": [],
  "source_file": "document_001.jpg",
  "media_type": "image",
  "llm_provider": "openai",
  "model_name": "gpt-4-vision"
}
```

### 多张图片（PDF）

```json
{
  "query": "<image><image><image>文档中哪些页面有问题",
  "response": "第2页存在文本模糊，第3页存在颜色异常",
  "system": "",
  "history": [],
  "images": [
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",  # 第1页
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",  # 第2页
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."   # 第3页
  ],
  "videos": [],
  "source_file": "report.pdf",
  "media_type": "pdf",
  "llm_provider": "openai",
  "model_name": "gpt-4-vision"
}
```

### 视频

```json
{
  "query": "<video>视频中哪些帧有问题",
  "response": "第5秒处检测到异常：画面抖动",
  "system": "",
  "history": [],
  "images": [],
  "videos": ["/app/data/project_001/uploads/surveillance_001.mp4"],
  "source_file": "surveillance_001.mp4",
  "media_type": "video",
  "llm_provider": "anthropic",
  "model_name": "claude-3-opus"
}
```

## 训练使用方法

### 直接使用（无需任何预处理）

```python
from datasets import load_dataset

# 加载数据集
dataset = load_dataset(
    "parquet",
    data_files="/app/data/project_001_converted/*.parquet",
    split="train"
)

# 查看数据（已经是 MS-SWIFT 标准格式）
print(dataset[0])
# {
#     "query": "<image>图片中有什么异常",
#     "response": "检测到以下异常...",
#     "system": "",
#     "history": [],
#     "images": ["data:image/jpeg;base64,..."],
#     "videos": []
# }

# 直接用于训练
# swift sft \
#     --dataset /app/data/project_001_converted/ \
#     --model Qwen/Qwen2.5-7B-Instruct \
#     --train_type lora
```

## 测试方法

使用更新后的测试脚本：

```bash
python swift/custom_ui/backend/test_parquet_format.py \
  /app/data/project_001_converted/train-00000-of-00001.parquet
```

**测试内容**：
- ✅ 验证 query/response/system/history 字段
- ✅ 验证 Data URL 格式（data:image/{ext};base64,{base64}）
- ✅ 验证 history 嵌套列表格式
- ✅ 显示训练使用示例
- ✅ 显示不同类型数据格式

## 对比总结

| 方面 | 之前的实现 | 现在的实现 |
|------|-----------|-----------|
| **数据格式** | messages（复杂嵌套） | query-response（简单） |
| **序列化** | 需要 json.dumps() | 无需序列化 |
| **反序列化** | 需要 json.loads() | 无需反序列化 |
| **图片格式** | 纯 base64 字符串 | Data URL 格式 |
| **MS-SWIFT 兼容** | ⚠️ 可能不兼容 | ✅ 原生支持 |
| **训练使用** | ❌ 需要预处理 | ✅ 直接使用 |
| **代码复杂度** | 高（序列化/反序列化） | 低（直接读写） |
| **维护性** | 差（自定义格式） | 好（官方格式） |

## 核心改进

1. **✅ 简化数据格式** - 从复杂的 messages 改为简单的 query-response
2. **✅ 标准化媒体格式** - 使用 Data URL 格式（官方要求）
3. **✅ 消除序列化开销** - 无需 JSON 序列化/反序列化
4. **✅ 原生兼容 MS-SWIFT** - 直接使用官方支持的格式
5. **✅ 降低维护成本** - 遵循官方标准，减少自定义逻辑

## 向后兼容性

⚠️ **不兼容旧格式** - 之前生成的 Parquet 文件需要重新转换

**迁移方法**：
1. 删除旧的 Parquet 文件
2. 使用新代码重新运行转换
3. 验证新数据格式正确

## 参考资料

- **MS-SWIFT 官方文档**: https://swift.readthedocs.io/
- **MS-SWIFT 数据格式**: `{"system": "<system>", "query": "<query>", "response": "<response>", "history": [["<q1>", "<r1>"]]}`
- **Data URL 标准**: `data:[<mediatype>][;base64],<data>`
- **HuggingFace Datasets**: https://huggingface.co/docs/datasets/

## 总结

这次重构将数据格式从自定义的 messages 格式改为 MS-SWIFT 原生支持的 query-response 格式，并修正媒体数据为标准的 Data URL 格式。主要优势：

- **简单高效** - 无需序列化/反序列化
- **原生兼容** - MS-SWIFT 直接支持
- **标准化** - 遵循官方格式
- **易维护** - 减少自定义逻辑

现在数据可以**直接用于 MS-SWIFT 训练，无需任何预处理**！
