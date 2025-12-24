"""
模型管理 API 端点
提供模型和数据集列表查询
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import os
import json

router = APIRouter()

# 从环境变量获取目录路径
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/output"))
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))

# 响应模型
class ModelInfo(BaseModel):
    model_id: str
    model_name: str
    model_type: str
    size: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []

class DatasetInfo(BaseModel):
    dataset_id: str
    dataset_name: str
    description: Optional[str] = None
    num_samples: Optional[int] = None
    tags: List[str] = []

# 辅助函数：扫描模型目录
def scan_models() -> List[Dict[str, Any]]:
    """
    扫描 MODEL_DIR 目录，返回可用的模型列表

    目录结构示例：
    /app/models/
        ├── qwen-7b/          # 模型目录（包含 config.json, pytorch_model.bin 等）
        ├── chatglm3-6b/
        └── llama2-13b/

    Returns:
        List[Dict]: 模型信息列表
    """
    import logging
    logger = logging.getLogger(__name__)

    models = []

    logger.info(f"[scan_models] 扫描目录: {MODEL_DIR}")
    logger.info(f"[scan_models] 目录是否存在: {MODEL_DIR.exists()}")

    if not MODEL_DIR.exists():
        logger.warning(f"[scan_models] 目录不存在，创建目录: {MODEL_DIR}")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        return models

    # 递归扫描子目录（支持 ModelScope 目录结构：models/Author/ModelName）
    def scan_directory(directory: Path, depth: int = 0, max_depth: int = 3):
        """递归扫描目录寻找模型"""
        if depth > max_depth:
            return

        try:
            for item in directory.iterdir():
                if not item.is_dir():
                    continue

                # 检查是否是有效的模型目录（至少包含 config.json）
                config_file = item / "config.json"
                if config_file.exists():
                    # 找到有效模型
                    # 计算相对于 MODEL_DIR 的路径，用作 model_id（如 Qwen/Qwen2.5-0.6B-Instruct）
                    try:
                        relative_path = item.relative_to(MODEL_DIR)
                        model_id = str(relative_path).replace('\\', '/')  # 统一使用 / 分隔符
                        model_name = item.name
                        model_type = "unknown"
                        size = None

                        # 读取模型配置
                        try:
                            with open(config_file, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                                # 尝试从配置中提取模型类型
                                if "model_type" in config:
                                    model_type = config["model_type"]
                                elif "architectures" in config and config["architectures"]:
                                    model_type = config["architectures"][0]
                        except Exception as e:
                            logger.warning(f"[scan_models] 读取配置失败: {config_file}, 错误: {e}")

                        # 计算模型大小（目录大小）
                        try:
                            total_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                            size_gb = total_size / (1024 ** 3)
                            if size_gb >= 1:
                                size = f"{size_gb:.1f}GB"
                            else:
                                size = f"{total_size / (1024 ** 2):.0f}MB"
                        except Exception as e:
                            logger.warning(f"[scan_models] 计算大小失败: {item}, 错误: {e}")

                        logger.info(f"[scan_models] 找到有效模型: {model_id} (名称: {model_name})")

                        models.append({
                            "model_id": str(item),  # 使用绝对路径作为 ID
                            "model_name": model_name,
                            "model_type": model_type,
                            "size": size,
                            "description": f"本地模型: {model_id}",
                            "tags": ["local"],
                            "source": "local"
                        })
                    except Exception as e:
                        logger.error(f"[scan_models] 处理模型失败: {item}, 错误: {e}")
                else:
                    # 继续递归扫描子目录
                    scan_directory(item, depth + 1, max_depth)
        except PermissionError as e:
            logger.warning(f"[scan_models] 权限不足，跳过目录: {directory}, 错误: {e}")
        except Exception as e:
            logger.error(f"[scan_models] 扫描目录失败: {directory}, 错误: {e}")

    # 开始扫描
    scan_directory(MODEL_DIR)

    logger.info(f"[scan_models] 扫描完成，共找到 {len(models)} 个模型")
    return models


# 辅助函数：扫描训练输出模型目录
def scan_trained_models() -> List[Dict[str, Any]]:
    """
    扫描 OUTPUT_DIR 目录，返回训练输出的模型列表

    目录结构示例：
    /app/output/
        └── {task_id}/                    # 训练任务 ID
            └── {version}/                # 训练版本/时间戳
                ├── checkpoint-1/         # 检查点（包含 adapter）
                │   ├── adapter_config.json
                │   ├── adapter_model.safetensors
                │   └── ...
                ├── checkpoint-2/
                └── (可能有最终合并模型)

    Returns:
        List[Dict]: 训练输出的模型列表
    """
    import logging
    logger = logging.getLogger(__name__)

    models = []
    scanned_paths = set()  # 避免重复扫描

    logger.info(f"[scan_trained_models] 扫描目录: {OUTPUT_DIR}")
    logger.info(f"[scan_trained_models] 目录是否存在: {OUTPUT_DIR.exists()}")

    if not OUTPUT_DIR.exists():
        logger.warning(f"[scan_trained_models] 目录不存在: {OUTPUT_DIR}")
        return models

    try:
        # 递归查找所有包含 adapter_config.json 的目录（Adapter 模型）
        for adapter_config_file in OUTPUT_DIR.rglob("adapter_config.json"):
            model_dir = adapter_config_file.parent

            # 避免重复扫描
            if str(model_dir) in scanned_paths:
                continue
            scanned_paths.add(str(model_dir))

            # 检查是否包含 adapter 模型文件
            has_adapter_model = (model_dir / "adapter_model.safetensors").exists() or (model_dir / "adapter_model.bin").exists()

            if has_adapter_model:
                # 生成友好的显示名称（去掉 /app/output/ 前缀）
                relative_path = model_dir.relative_to(OUTPUT_DIR)
                display_name = str(relative_path).replace("\\", "/")

                # 计算模型大小
                try:
                    total_size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                    size_mb = total_size / (1024 ** 2)
                    if size_mb >= 1024:
                        size = f"{size_mb / 1024:.1f}GB"
                    else:
                        size = f"{size_mb:.0f}MB"
                except Exception as e:
                    logger.warning(f"[scan_trained_models] 计算大小失败: {model_dir}, 错误: {e}")
                    size = None

                logger.info(f"[scan_trained_models] 找到 Adapter 模型: {display_name}")

                models.append({
                    "model_id": str(model_dir),  # 绝对路径
                    "model_name": model_dir.name,  # checkpoint-1, checkpoint-2 等
                    "model_type": "adapter",
                    "size": size,
                    "description": f"训练输出 (Adapter): {display_name}",
                    "tags": ["trained", "adapter", "lora"],
                    "source": "output"
                })

        # 递归查找所有包含 config.json 的目录（完整模型）
        # 但排除已扫描的 adapter 目录
        for config_file in OUTPUT_DIR.rglob("config.json"):
            model_dir = config_file.parent

            # 避免重复扫描
            if str(model_dir) in scanned_paths:
                continue

            # 检查是否包含模型权重文件
            has_model_weights = any(model_dir.glob("*.safetensors")) or any(model_dir.glob("*.bin"))

            # 确保不是 adapter 目录（adapter 目录也有 config.json）
            is_adapter = (model_dir / "adapter_config.json").exists()

            if has_model_weights and not is_adapter:
                scanned_paths.add(str(model_dir))

                # 生成友好的显示名称
                relative_path = model_dir.relative_to(OUTPUT_DIR)
                display_name = str(relative_path).replace("\\", "/")

                # 计算模型大小
                try:
                    total_size = sum(f.stat().st_size for f in model_dir.rglob('*') if f.is_file())
                    size_gb = total_size / (1024 ** 3)
                    if size_gb >= 1:
                        size = f"{size_gb:.1f}GB"
                    else:
                        size = f"{total_size / (1024 ** 2):.0f}MB"
                except Exception as e:
                    logger.warning(f"[scan_trained_models] 计算大小失败: {model_dir}, 错误: {e}")
                    size = None

                logger.info(f"[scan_trained_models] 找到完整模型: {display_name}")

                models.append({
                    "model_id": str(model_dir),  # 绝对路径
                    "model_name": model_dir.name,
                    "model_type": "base_model",
                    "size": size,
                    "description": f"训练输出 (Merged): {display_name}",
                    "tags": ["trained", "merged", "full_model"],
                    "source": "output"
                })

        logger.info(f"[scan_trained_models] 扫描完成，共找到 {len(models)} 个训练输出模型")

    except Exception as e:
        logger.error(f"[scan_trained_models] 扫描失败: {e}", exc_info=True)

    return models


# 辅助函数：扫描数据集目录
def scan_datasets() -> List[Dict[str, Any]]:
    """
    扫描 DATA_DIR 目录，返回可用的数据集列表

    支持的文件格式：.jsonl, .json, .csv, .tsv, .txt

    Returns:
        List[Dict]: 数据集信息列表
    """
    import logging
    logger = logging.getLogger(__name__)

    datasets = []

    logger.info(f"[scan_datasets] 扫描目录: {DATA_DIR}")
    logger.info(f"[scan_datasets] 目录是否存在: {DATA_DIR.exists()}")

    if not DATA_DIR.exists():
        logger.warning(f"[scan_datasets] 目录不存在，创建目录: {DATA_DIR}")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return datasets

    # 支持的数据集文件格式（参考 HuggingFace/ModelScope 标准）
    supported_extensions = {
        # 文本数据格式
        '.jsonl', '.json', '.csv', '.tsv', '.txt',
        # Parquet/Arrow 格式（HuggingFace 默认格式）
        '.parquet', '.pq', '.arrow',
        # 图像格式（用于多模态数据集）
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
        # 音频格式（用于语音数据集）
        '.wav', '.mp3', '.flac', '.ogg',
        # 视频格式（用于视频数据集）
        '.mp4', '.avi', '.mov', '.mkv',
        # 其他常见格式
        '.pkl', '.pickle', '.npy', '.npz',  # Python 序列化/NumPy 格式
        '.h5', '.hdf5',  # HDF5 格式
    }

    # 递归扫描数据目录（支持多层目录结构，如多模态数据集）
    def scan_directory(directory: Path, depth: int = 0, max_depth: int = 5):
        """递归扫描目录寻找数据集文件"""
        if depth > max_depth:
            return

        try:
            for item in directory.iterdir():
                # 递归扫描子目录
                if item.is_dir():
                    scan_directory(item, depth + 1, max_depth)
                    continue

                # 检查文件格式
                if item.suffix.lower() not in supported_extensions:
                    continue

                logger.info(f"[scan_datasets] 找到数据集文件: {item}")

                # 计算相对路径（用作 dataset_id）
                try:
                    relative_path = item.relative_to(DATA_DIR)
                    dataset_id = str(relative_path).replace('\\', '/')
                    file_name = item.name
                    file_size = item.stat().st_size

                    # 尝试统计样本数量（仅对文本格式）
                    num_samples = None
                    if item.suffix.lower() in {'.jsonl', '.csv', '.txt', '.tsv'}:
                        try:
                            with open(item, 'r', encoding='utf-8') as f:
                                num_samples = sum(1 for _ in f)
                            # CSV 文件减去表头
                            if item.suffix.lower() == '.csv' and num_samples > 0:
                                num_samples -= 1
                        except Exception as e:
                            logger.debug(f"[scan_datasets] 统计行数失败: {item}, 错误: {e}")

                    # 格式化文件大小
                    if file_size >= 1024 ** 3:
                        size_str = f"{file_size / (1024 ** 3):.2f}GB"
                    elif file_size >= 1024 ** 2:
                        size_str = f"{file_size / (1024 ** 2):.2f}MB"
                    elif file_size >= 1024:
                        size_str = f"{file_size / 1024:.2f}KB"
                    else:
                        size_str = f"{file_size}B"

                    # 添加到数据集列表
                    datasets.append({
                        "dataset_id": dataset_id,  # 相对路径（如 folder/data.jsonl）
                        "dataset_name": file_name,  # 文件名
                        "description": f"文件大小: {size_str}, 路径: {dataset_id}",
                        "num_samples": num_samples,
                        "tags": [item.suffix.lower().replace('.', '')]
                    })
                except Exception as e:
                    logger.error(f"[scan_datasets] 处理文件失败: {item}, 错误: {e}")

        except PermissionError as e:
            logger.warning(f"[scan_datasets] 权限不足，跳过目录: {directory}, 错误: {e}")
        except Exception as e:
            logger.error(f"[scan_datasets] 扫描目录失败: {directory}, 错误: {e}")

    # 开始递归扫描
    scan_directory(DATA_DIR)

    logger.info(f"[scan_datasets] 扫描完成，共找到 {len(datasets)} 个数据集")
    return datasets

@router.get("/models", response_model=List[ModelInfo])
async def get_models(
    search: Optional[str] = None,
    model_type: Optional[str] = None,
    tag: Optional[str] = None
):
    """
    获取可用模型列表（从 /app/models 目录扫描）

    Args:
        search: 搜索关键词
        model_type: 模型类型过滤
        tag: 标签过滤

    Returns:
        List[ModelInfo]: 模型列表
    """
    # 从实际目录扫描模型
    models = scan_models()

    # 应用过滤
    if search:
        models = [m for m in models if search.lower() in m["model_name"].lower()
                  or search.lower() in m["model_id"].lower()]

    if model_type:
        models = [m for m in models if m["model_type"] == model_type]

    if tag:
        models = [m for m in models if tag in m["tags"]]

    return [ModelInfo(**m) for m in models]

@router.get("/trained-models", response_model=List[ModelInfo])
async def get_trained_models(
    search: Optional[str] = None,
    model_type: Optional[str] = None,
    tag: Optional[str] = None
):
    """
    获取训练输出模型列表（从 /app/output 目录扫描）

    Args:
        search: 搜索关键词
        model_type: 模型类型过滤（adapter, base_model）
        tag: 标签过滤

    Returns:
        List[ModelInfo]: 训练输出模型列表
    """
    # 从实际目录扫描训练输出模型
    models = scan_trained_models()

    # 应用过滤
    if search:
        models = [m for m in models if search.lower() in m["model_name"].lower()
                  or search.lower() in m["model_id"].lower()]

    if model_type:
        models = [m for m in models if m["model_type"] == model_type]

    if tag:
        models = [m for m in models if tag in m["tags"]]

    return [ModelInfo(**m) for m in models]

@router.get("/models/{model_id:path}")
async def get_model_detail(model_id: str):
    """
    获取模型详细信息

    Args:
        model_id: 模型 ID（可能包含路径）

    Returns:
        ModelInfo: 模型信息
    """
    models = scan_models()
    for model in models:
        if model["model_id"] == model_id or Path(model["model_id"]).name == model_id:
            return ModelInfo(**model)

    raise HTTPException(status_code=404, detail="模型不存在")

@router.get("/datasets", response_model=List[DatasetInfo])
async def get_datasets(
    search: Optional[str] = None,
    tag: Optional[str] = None
):
    """
    获取可用数据集列表（从 /app/data 目录扫描）

    Args:
        search: 搜索关键词
        tag: 标签过滤

    Returns:
        List[DatasetInfo]: 数据集列表
    """
    # 从实际目录扫描数据集
    datasets = scan_datasets()

    # 应用过滤
    if search:
        datasets = [d for d in datasets if search.lower() in d["dataset_name"].lower()
                    or search.lower() in d["dataset_id"].lower()]

    if tag:
        datasets = [d for d in datasets if tag in d["tags"]]

    return [DatasetInfo(**d) for d in datasets]

@router.get("/datasets/{dataset_id}")
async def get_dataset_detail(dataset_id: str):
    """
    获取数据集详细信息

    Args:
        dataset_id: 数据集 ID（文件名）

    Returns:
        DatasetInfo: 数据集信息
    """
    datasets = scan_datasets()
    for dataset in datasets:
        if dataset["dataset_id"] == dataset_id:
            return DatasetInfo(**dataset)

    raise HTTPException(status_code=404, detail="数据集不存在")

@router.get("/model-types")
async def get_model_types():
    """
    获取支持的模型类型列表

    Returns:
        dict: 模型类型列表
    """
    models = scan_models()
    model_types = list(set(m["model_type"] for m in models if m["model_type"] != "unknown"))

    return {"model_types": model_types}
