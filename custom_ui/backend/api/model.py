"""
模型管理 API 端点
提供模型和数据集列表查询
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter()

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

# 模拟数据 - 实际应从 ModelScope 获取
MOCK_MODELS = [
    {
        "model_id": "qwen/Qwen2.5-7B-Instruct",
        "model_name": "Qwen2.5 7B Instruct",
        "model_type": "qwen2_5-7b-instruct",
        "size": "7B",
        "description": "Qwen2.5 7B 指令微调模型",
        "tags": ["chat", "instruction"]
    },
    {
        "model_id": "qwen/Qwen2.5-14B-Instruct",
        "model_name": "Qwen2.5 14B Instruct",
        "model_type": "qwen2_5-14b-instruct",
        "size": "14B",
        "description": "Qwen2.5 14B 指令微调模型",
        "tags": ["chat", "instruction"]
    },
    {
        "model_id": "ZhipuAI/chatglm3-6b",
        "model_name": "ChatGLM3 6B",
        "model_type": "chatglm3-6b",
        "size": "6B",
        "description": "ChatGLM3 对话模型",
        "tags": ["chat", "chinese"]
    },
    {
        "model_id": "internlm/internlm2-chat-7b",
        "model_name": "InternLM2 Chat 7B",
        "model_type": "internlm2-chat-7b",
        "size": "7B",
        "description": "书生·浦语 2.0 对话模型",
        "tags": ["chat", "chinese"]
    },
]

MOCK_DATASETS = [
    {
        "dataset_id": "alpaca-zh",
        "dataset_name": "Alpaca 中文数据集",
        "description": "中文指令微调数据集",
        "num_samples": 50000,
        "tags": ["instruction", "chinese"]
    },
    {
        "dataset_id": "belle-500k",
        "dataset_name": "BELLE 500K",
        "description": "BELLE 中文指令数据集",
        "num_samples": 500000,
        "tags": ["instruction", "chinese"]
    },
    {
        "dataset_id": "alpaca-en",
        "dataset_name": "Alpaca English",
        "description": "英文指令微调数据集",
        "num_samples": 52000,
        "tags": ["instruction", "english"]
    },
    {
        "dataset_id": "advertise-gen",
        "dataset_name": "广告生成数据集",
        "description": "中文广告文案生成数据集",
        "num_samples": 10000,
        "tags": ["generation", "chinese"]
    },
]

@router.get("/models", response_model=List[ModelInfo])
async def get_models(
    search: Optional[str] = None,
    model_type: Optional[str] = None,
    tag: Optional[str] = None
):
    """
    获取可用模型列表

    Args:
        search: 搜索关键词
        model_type: 模型类型过滤
        tag: 标签过滤

    Returns:
        List[ModelInfo]: 模型列表
    """
    # TODO: 从 ModelScope 实际获取模型列表
    # from swift.utils import get_model_list
    # models = get_model_list()

    models = MOCK_MODELS.copy()

    # 应用过滤
    if search:
        models = [m for m in models if search.lower() in m["model_name"].lower()
                  or search.lower() in m["model_id"].lower()]

    if model_type:
        models = [m for m in models if m["model_type"] == model_type]

    if tag:
        models = [m for m in models if tag in m["tags"]]

    return [ModelInfo(**m) for m in models]

@router.get("/models/{model_id}")
async def get_model_detail(model_id: str):
    """
    获取模型详细信息

    Args:
        model_id: 模型 ID

    Returns:
        ModelInfo: 模型信息
    """
    # 在路径中的斜杠会被编码，这里处理一下
    for model in MOCK_MODELS:
        if model["model_id"] == model_id or model["model_id"].replace("/", "_") == model_id:
            return ModelInfo(**model)

    raise HTTPException(status_code=404, detail="模型不存在")

@router.get("/datasets", response_model=List[DatasetInfo])
async def get_datasets(
    search: Optional[str] = None,
    tag: Optional[str] = None
):
    """
    获取可用数据集列表

    Args:
        search: 搜索关键词
        tag: 标签过滤

    Returns:
        List[DatasetInfo]: 数据集列表
    """
    # TODO: 从 ModelScope 实际获取数据集列表
    # from swift.utils import get_dataset_list
    # datasets = get_dataset_list()

    datasets = MOCK_DATASETS.copy()

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
        dataset_id: 数据集 ID

    Returns:
        DatasetInfo: 数据集信息
    """
    for dataset in MOCK_DATASETS:
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
    # TODO: 从 swift 获取实际支持的模型类型
    model_types = list(set(m["model_type"] for m in MOCK_MODELS))

    return {"model_types": model_types}
