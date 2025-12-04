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

    # 遍历一级子目录
    all_dirs = list(MODEL_DIR.iterdir())
    logger.info(f"[scan_models] 目录中的所有项: {[d.name for d in all_dirs]}")

    for model_path in all_dirs:
        if not model_path.is_dir():
            continue

        # 检查是否是有效的模型目录（至少包含 config.json）
        config_file = model_path / "config.json"
        if not config_file.exists():
            continue

        # 读取模型配置
        model_name = model_path.name
        model_type = "unknown"
        size = None

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 尝试从配置中提取模型类型
                if "model_type" in config:
                    model_type = config["model_type"]
                elif "architectures" in config and config["architectures"]:
                    model_type = config["architectures"][0]
        except Exception:
            pass

        # 计算模型大小（目录大小）
        try:
            total_size = sum(f.stat().st_size for f in model_path.rglob('*') if f.is_file())
            size_gb = total_size / (1024 ** 3)
            if size_gb >= 1:
                size = f"{size_gb:.1f}GB"
            else:
                size = f"{total_size / (1024 ** 2):.0f}MB"
        except Exception:
            pass

        logger.info(f"[scan_models] 找到有效模型: {model_name}")

        models.append({
            "model_id": str(model_path),
            "model_name": model_name,
            "model_type": model_type,
            "size": size,
            "description": f"本地模型: {model_name}",
            "tags": ["local"]
        })

    logger.info(f"[scan_models] 扫描完成，共找到 {len(models)} 个模型")
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

    # 支持的数据集文件格式
    supported_extensions = {'.jsonl', '.json', '.csv', '.tsv', '.txt'}

    # 遍历数据目录中的文件
    all_files = list(DATA_DIR.iterdir())
    logger.info(f"[scan_datasets] 目录中的所有项: {[f.name for f in all_files]}")

    for file_path in all_files:
        if not file_path.is_file():
            logger.debug(f"[scan_datasets] 跳过非文件: {file_path.name}")
            continue

        if file_path.suffix.lower() not in supported_extensions:
            logger.debug(f"[scan_datasets] 跳过不支持的格式: {file_path.name} (后缀: {file_path.suffix})")
            continue

        logger.info(f"[scan_datasets] 找到数据集文件: {file_path.name}")

        # 获取文件信息
        file_name = file_path.name
        file_size = file_path.stat().st_size

        # 尝试统计样本数量（仅对 JSONL 和 CSV 文件）
        num_samples = None
        if file_path.suffix.lower() in {'.jsonl', '.csv'}:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    num_samples = sum(1 for _ in f)
                # CSV 文件减去表头
                if file_path.suffix.lower() == '.csv' and num_samples > 0:
                    num_samples -= 1
            except Exception:
                pass

        # 格式化文件大小
        if file_size >= 1024 ** 3:
            size_str = f"{file_size / (1024 ** 3):.2f}GB"
        elif file_size >= 1024 ** 2:
            size_str = f"{file_size / (1024 ** 2):.2f}MB"
        elif file_size >= 1024:
            size_str = f"{file_size / 1024:.2f}KB"
        else:
            size_str = f"{file_size}B"

        datasets.append({
            "dataset_id": file_name,
            "dataset_name": file_name,
            "description": f"文件大小: {size_str}",
            "num_samples": num_samples,
            "tags": [file_path.suffix.lower().replace('.', '')]
        })

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
