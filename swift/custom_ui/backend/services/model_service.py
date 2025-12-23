"""
模型管理服务
提供本地模型和训练输出模型的查询功能
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

# 本地模型目录
MODELS_DIR = Path("/app/models")
OUTPUT_DIR = Path("/app/output")


class ModelService:
    """模型管理服务类"""

    def __init__(self):
        pass

    def _scan_local_models(self) -> List[Dict[str, Any]]:
        """
        扫描本地模型目录 (/app/models)

        Returns:
            list: 本地基础模型列表
        """
        models = []

        if not MODELS_DIR.exists():
            logger.warning(f"本地模型目录不存在: {MODELS_DIR}")
            return models

        try:
            # 扫描第一层目录（命名空间）
            for namespace_dir in MODELS_DIR.iterdir():
                if not namespace_dir.is_dir():
                    continue

                # 扫描第二层目录（模型名）
                for model_dir in namespace_dir.iterdir():
                    if not model_dir.is_dir():
                        continue

                    # 检查是否包含模型文件（config.json 或 .safetensors）
                    has_config = (model_dir / "config.json").exists()
                    has_model = any(model_dir.glob("*.safetensors")) or any(model_dir.glob("*.bin"))

                    if has_config or has_model:
                        model_id = f"{namespace_dir.name}/{model_dir.name}"
                        models.append({
                            "model_id": str(model_dir),  # 完整路径
                            "model_name": model_id,
                            "model_type": "base_model",
                            "size": self._get_dir_size(model_dir),
                            "description": f"本地模型: {model_id}",
                            "tags": ["local", "base_model"],
                            "source": "local"
                        })

            logger.info(f"扫描到 {len(models)} 个本地基础模型")

        except Exception as e:
            logger.error(f"扫描本地模型失败: {e}", exc_info=True)

        return models

    def _scan_trained_models(self) -> List[Dict[str, Any]]:
        """
        扫描训练输出目录 (/app/output)

        Returns:
            list: 训练输出的 adapter 模型列表
        """
        models = []

        if not OUTPUT_DIR.exists():
            logger.warning(f"训练输出目录不存在: {OUTPUT_DIR}")
            return models

        try:
            # 扫描 /app/output 下的所有训练任务目录
            for task_dir in OUTPUT_DIR.iterdir():
                if not task_dir.is_dir():
                    continue

                # 检查是否包含 adapter 模型文件
                has_adapter_config = (task_dir / "adapter_config.json").exists()
                has_adapter_model = (task_dir / "adapter_model.safetensors").exists() or (task_dir / "adapter_model.bin").exists()

                if has_adapter_config or has_adapter_model:
                    models.append({
                        "model_id": str(task_dir),  # 完整路径
                        "model_name": task_dir.name,
                        "model_type": "adapter",
                        "size": self._get_dir_size(task_dir),
                        "description": f"训练输出: {task_dir.name}",
                        "tags": ["trained", "adapter", "lora"],
                        "source": "output"
                    })

            logger.info(f"扫描到 {len(models)} 个训练输出模型")

        except Exception as e:
            logger.error(f"扫描训练输出模型失败: {e}", exc_info=True)

        return models

    def _get_dir_size(self, path: Path) -> str:
        """
        获取目录大小

        Args:
            path: 目录路径

        Returns:
            str: 格式化的大小字符串
        """
        try:
            total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())

            # 格式化大小
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if total_size < 1024.0:
                    return f"{total_size:.2f} {unit}"
                total_size /= 1024.0

            return f"{total_size:.2f} PB"
        except Exception:
            return "未知"

    def get_available_models(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取可用模型列表（本地模型 + 训练输出模型）

        Args:
            search: 搜索关键词

        Returns:
            list: 模型列表
        """
        # 合并本地模型和训练输出模型
        models = self._scan_local_models() + self._scan_trained_models()

        # 搜索过滤
        if search:
            search_lower = search.lower()
            models = [
                m for m in models
                if search_lower in m['model_name'].lower() or search_lower in m['model_id'].lower()
            ]

        logger.info(f"返回 {len(models)} 个可用模型")
        return models

    def get_available_datasets(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取可用数据集列表

        Args:
            search: 搜索关键词

        Returns:
            list: 数据集列表
        """
        # TODO: 从 ModelScope 或本地获取数据集列表
        """
        from swift.utils import get_dataset_list

        datasets = get_dataset_list()

        if search:
            datasets = [d for d in datasets if search.lower() in d['dataset_id'].lower()]

        return datasets
        """

        # 返回模拟数据
        return []

    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        获取模型详细信息

        Args:
            model_id: 模型 ID

        Returns:
            dict: 模型信息
        """
        # TODO: 从 ModelScope 获取模型信息
        """
        from modelscope.hub.api import HubApi

        api = HubApi()
        model_info = api.get_model(model_id)

        return model_info
        """

        return {}
