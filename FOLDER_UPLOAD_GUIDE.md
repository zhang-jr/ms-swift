# 文件夹上传功能 - 保留目录结构

## 功能说明

**问题**: 之前的文件夹上传会展平所有文件，丢失原始的目录组织结构。

**解决方案**: 现在的实现会完整保留用户上传文件夹的目录层级关系。

## 工作原理

### 前端 (`frontend/src/api/data.ts`)

```typescript
// 使用 webkitRelativePath 获取文件的相对路径
const relativePath = (file as any).webkitRelativePath || file.name

// 通过 FormData 的第三个参数传递相对路径
formData.append('files', file, relativePath)
```

**示例**:
- 用户选择文件夹: `my_project/`
  ```
  my_project/
  ├── data/
  │   ├── train.csv
  │   └── test.csv
  └── config/
      └── settings.json
  ```
- `webkitRelativePath` 会是:
  - `"my_project/data/train.csv"`
  - `"my_project/data/test.csv"`
  - `"my_project/config/settings.json"`

### 后端 (`backend/api/data.py`)

```python
# 解析相对路径，去掉第一层目录（用户选择的根文件夹名）
path_parts = Path(relative_path).parts
if len(path_parts) > 1:
    target_relative_path = str(Path(*path_parts[1:]))

# 创建子目录
target_path = root_folder / target_relative_path
target_path.parent.mkdir(parents=True, exist_ok=True)

# 保存文件到正确位置
with open(target_path, "wb") as buffer:
    ...
```

**结果**: 上传后的文件夹结构（假设用户输入的文件夹名为 `project_001`）:
```
/app/data/project_001/
├── data/
│   ├── train.csv
│   └── test.csv
└── config/
    └── settings.json
```

## 测试步骤

### 1. 准备测试数据

创建一个带有子目录的测试文件夹:
```bash
test_upload/
├── instruction/
│   ├── task_001.json
│   └── task_002.json
├── uploads/
│   ├── image1.jpg
│   └── image2.png
└── overlays/
    └── overlay_001.png
```

### 2. 前端测试

1. 启动前端开发服务器:
   ```bash
   cd swift/custom_ui/frontend
   npm run dev
   ```

2. 打开浏览器访问数据管理页面

3. 点击"上传文件夹"按钮

4. 输入文件夹名称（如 `test_project`）

5. 点击"选择文件夹"，选择 `test_upload` 文件夹

6. 点击"上传"

### 3. 验证结果

**前端验证**:
- 在数据集列表中应该看到 `test_project` 文件夹
- 点击"预览"，应该看到 3 个子文件夹

**后端验证** (在 Docker 容器或服务器中):
```bash
# 检查目录结构
tree /app/data/test_project

# 预期输出:
# /app/data/test_project/
# ├── instruction/
# │   ├── task_001.json
# │   └── task_002.json
# ├── uploads/
# │   ├── image1.jpg
# │   └── image2.png
# └── overlays/
#     └── overlay_001.png
```

## 安全性考虑

### 路径遍历攻击防护

```python
# 安全性检查：防止路径遍历攻击
relative_path = relative_path.lstrip("./")
if ".." in relative_path or relative_path.startswith("/"):
    print(f"Skipping unsafe path: {relative_path}")
    continue
```

**阻止的恶意路径**:
- `../etc/passwd` ❌
- `/etc/passwd` ❌
- `../../sensitive_data` ❌

**允许的路径**:
- `data/train.csv` ✅
- `subfolder/config.json` ✅
- `images/cat.jpg` ✅

## 与数据转换功能的集成

上传带有完整目录结构的标注项目后，可以直接使用数据转换功能：

```
用户上传文件夹 (保留结构)
    ↓
annotation_project_001/
├── instruction/     *.json
├── uploads/         原始媒体
└── overlays/        标注图片
    ↓
点击"转换"按钮
    ↓
annotation_project_001_converted/
├── train-00000.parquet
├── train-00001.parquet
...
```

## 浏览器兼容性

- **Chrome/Edge**: 完全支持 `webkitRelativePath`
- **Firefox**: 完全支持
- **Safari**: 完全支持
- **IE**: ❌ 不支持文件夹上传

## 已知限制

1. **单个文件上传**: 只有通过文件夹选择器选择的文件才会包含 `webkitRelativePath`。单个文件上传不受影响。

2. **文件夹名称**: 用户输入的文件夹名称会替代原始文件夹的根目录名称。
   - 原始: `my_project/data/train.csv`
   - 上传为: `user_defined_name/data/train.csv`

3. **空文件夹**: 浏览器不会上传空文件夹（没有文件的目录）。

## 改进建议

- [ ] 添加上传进度条（显示当前上传文件和总进度）
- [ ] 支持断点续传（大文件夹上传）
- [ ] 自动使用原始文件夹名称（可选）
- [ ] 文件夹预览（上传前显示即将上传的文件列表）

## 相关文件

- **前端 API**: `swift/custom_ui/frontend/src/api/data.ts` (第 92-111 行)
- **后端 API**: `swift/custom_ui/backend/api/data.py` (第 226-336 行)
- **前端页面**: `swift/custom_ui/frontend/src/pages/DataManagementPage.tsx` (第 112-134 行)

## 提交记录

- 修复日期: 2025-12-22
- 相关 Issue: 保留用户项目组织方式的上传功能
