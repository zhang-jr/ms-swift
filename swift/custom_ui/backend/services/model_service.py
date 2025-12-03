# Copyright (c) Alibaba, Inc. and its affiliates.
"""
模型服务层
处理模型管理相关的业务逻辑
"""
import os
from typing import List, Dict, Optional

from swift.llm import MODEL_MAPPING, get_model_info_table
from swift.utils import get_logger

logger = get_logger()


class ModelService:
    """模型服务类"""

    def __init__(self):
        pass

    def list_available_models(self) -> List[Dict[str, str]]:
        """
        获取可用模型列表

        Returns:
            models: 模型列表,包含模型 ID 和信息
        """
        try:
            models = []
            for model_id, model_meta in MODEL_MAPPING.items():
                models.append({
                    "model_id": model_id,
                    "model_type": getattr(model_meta, "model_type", "unknown"),
                    "template": getattr(model_meta, "template", "unknown"),
                    "size": getattr(model_meta, "size", "unknown"),
                    "requires": getattr(model_meta, "requires", [])
                })

            return sorted(models, key=lambda x: x["model_id"])

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """
        获取单个模型信息

        Args:
            model_id: 模型 ID

        Returns:
            model_info: 模型信息
        """
        try:
            if model_id not in MODEL_MAPPING:
                return None

            model_meta = MODEL_MAPPING[model_id]
            return {
                "model_id": model_id,
                "model_type": getattr(model_meta, "model_type", "unknown"),
                "template": getattr(model_meta, "template", "unknown"),
                "size": getattr(model_meta, "size", "unknown"),
                "requires": getattr(model_meta, "requires", []),
                "tags": getattr(model_meta, "tags", [])
            }

        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return None

    def search_models(self, query: str) -> List[Dict]:
        """
        搜索模型

        Args:
            query: 搜索关键词

        Returns:
            models: 匹配的模型列表
        """
        all_models = self.list_available_models()
        query_lower = query.lower()

        return [
            model for model in all_models
            if query_lower in model["model_id"].lower() or
            query_lower in model["model_type"].lower()
        ]

    def list_local_models(self, base_dir: str = "./models") -> List[Dict]:
        """
        获取本地已下载的模型列表

        Args:
            base_dir: 模型存储目录

        Returns:
            local_models: 本地模型列表
        """
        if not os.path.exists(base_dir):
            return []

        local_models = []
        try:
            for item in os.listdir(base_dir):
                model_path = os.path.join(base_dir, item)
                if os.path.isdir(model_path):
                    # 检查是否是有效的模型目录
                    has_config = os.path.exists(os.path.join(model_path, "config.json"))
                    has_model_file = any(
                        os.path.exists(os.path.join(model_path, f))
                        for f in ["pytorch_model.bin", "model.safetensors"]
                    )

                    if has_config or has_model_file:
                        local_models.append({
                            "name": item,
                            "path": model_path,
                            "has_config": has_config,
                            "has_model_file": has_model_file
                        })

            return sorted(local_models, key=lambda x: x["name"])

        except Exception as e:
            logger.error(f"Failed to list local models: {e}")
            return []

    def get_model_size(self, model_path: str) -> Optional[int]:
        """
        获取模型大小(字节)

        Args:
            model_path: 模型路径

        Returns:
            size: 模型大小
        """
        if not os.path.exists(model_path):
            return None

        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(model_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
            return total_size

        except Exception as e:
            logger.error(f"Failed to get model size: {e}")
            return None
