"""
数据集转换服务
将标注数据转换为 HuggingFace Datasets 格式（Parquet）
基于标注平台的转换逻辑，适配训练平台的目录结构
"""

import json
import base64
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import pandas as pd
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)

# 数据存储目录（Docker volume 挂载点）
DATA_DIR = Path("/app/data")


class DatasetConverter:
    """数据集转换器（适配训练平台）"""

    def __init__(self, project_name: str):
        """
        初始化转换器

        Args:
            project_name: 标注项目文件夹名称（位于 /app/data 下）
        """
        # 安全验证：防止路径遍历攻击
        if ".." in project_name or "/" in project_name or "\\" in project_name:
            raise ValueError(f"非法的项目名称: {project_name}")

        self.project_root = DATA_DIR / project_name
        self.instruction_dir = self.project_root / "instruction"
        self.overlays_dir = self.project_root / "overlays"
        self.uploads_dir = self.project_root / "uploads"

        # 验证目录
        self._validate_directories()

    def _validate_directories(self):
        """验证必需的目录是否存在"""
        if not self.project_root.exists():
            raise ValueError(f"项目根目录不存在: {self.project_root}")

        if not self.instruction_dir.exists():
            raise ValueError(f"instruction 目录不存在: {self.instruction_dir}")

        if not self.uploads_dir.exists():
            logger.warning(f"uploads 目录不存在: {self.uploads_dir}")

    def image_to_base64(self, image_path: Path) -> str:
        """将图像转换为base64编码"""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"图像编码失败 {image_path}: {e}")
            raise

    def process_image_instruction(
        self, inst_data: Dict, use_overlay: bool = True
    ) -> Dict:
        """
        处理图像类型的instruction

        Args:
            inst_data: instruction 数据
            use_overlay: 是否优先使用带标注框的 overlay 图片
        """
        image_rel_path = inst_data["image"]

        # 构建完整路径
        upload_path = self.uploads_dir / image_rel_path

        if not upload_path.exists():
            raise FileNotFoundError(f"原始图片不存在: {upload_path}")

        # 构建overlay路径
        overlay_path = self._get_overlay_path(image_rel_path, "image")

        # 选择使用原图还是overlay
        if use_overlay and overlay_path.exists():
            image_path = overlay_path
            logger.debug(f"使用 overlay 图片: {overlay_path}")
        else:
            image_path = upload_path
            logger.debug(f"使用原始图片: {upload_path}")

        # 转换为base64
        image_b64 = self.image_to_base64(image_path)

        # 构建messages
        messages = [
            {"role": "user", "content": f"<image>{inst_data['instruction']}"},
            {"role": "assistant", "content": inst_data["raw_response"]},
        ]

        return {
            "messages": messages,
            "images": [image_b64],
            "metadata": {
                "source_file": str(image_rel_path),
                "media_type": "image",
                "llm_provider": inst_data.get("llm_provider"),
                "model_name": inst_data.get("model_name"),
                "timestamp": inst_data.get("timestamp"),
            },
        }

    def process_pdf_instruction(
        self, inst_data: Dict, use_overlay: bool = True
    ) -> Dict:
        """
        处理PDF类型的instruction

        Args:
            inst_data: instruction 数据
            use_overlay: 是否优先使用带标注框的 overlay 图片
        """
        pdf_rel_path = inst_data["pdf"]
        annotations = inst_data.get("annotations", [])

        # 获取所有被标注的页面
        annotated_pages = sorted(set(ann["page"] for ann in annotations if "page" in ann))

        # 如果没有annotations，默认使用第0页
        if not annotated_pages:
            logger.warning(f"PDF {pdf_rel_path} 没有标注页面，使用第0页")
            annotated_pages = [0]

        # 收集所有页面的图像
        images_b64 = []
        for page in annotated_pages:
            overlay_path = self._get_pdf_overlay_path(pdf_rel_path, page)

            if use_overlay and overlay_path.exists():
                images_b64.append(self.image_to_base64(overlay_path))
                logger.debug(f"PDF 页面 {page}: 使用 overlay")
            else:
                # TODO: 如果没有overlay，需要从原始PDF提取页面
                logger.warning(f"PDF 页面 {page}: overlay 不存在 {overlay_path}")
                # 这里可以添加 PyMuPDF 来从原始PDF提取页面
                continue

        if not images_b64:
            raise ValueError(f"PDF {pdf_rel_path} 没有可用的图片")

        # 构建content中的<image>占位符
        image_placeholders = "".join(["<image>"] * len(images_b64))

        messages = [
            {
                "role": "user",
                "content": f"{image_placeholders}{inst_data['instruction']}",
            },
            {"role": "assistant", "content": inst_data["raw_response"]},
        ]

        return {
            "messages": messages,
            "images": images_b64,
            "metadata": {
                "source_file": str(pdf_rel_path),
                "media_type": "pdf",
                "pages": annotated_pages,
                "annotations": annotations,
                "llm_provider": inst_data.get("llm_provider"),
                "model_name": inst_data.get("model_name"),
                "timestamp": inst_data.get("timestamp"),
            },
        }

    def process_video_instruction(
        self, inst_data: Dict, use_overlay: bool = True
    ) -> Dict:
        """
        处理视频类型的instruction（转为关键帧）

        Args:
            inst_data: instruction 数据
            use_overlay: 是否优先使用带标注框的 overlay 图片
        """
        video_rel_path = inst_data["video"]
        annotations = inst_data.get("annotations", [])

        # 提取所有标注的帧
        annotated_frames = sorted(
            set(ann["frame"] for ann in annotations if "frame" in ann)
        )

        if not annotated_frames:
            logger.warning(f"视频 {video_rel_path} 没有标注帧")
            return None

        # 收集关键帧图像
        images_b64 = []
        for frame in annotated_frames:
            overlay_path = self._get_video_overlay_path(video_rel_path, frame)

            if use_overlay and overlay_path.exists():
                images_b64.append(self.image_to_base64(overlay_path))
                logger.debug(f"视频帧 {frame}: 使用 overlay")
            else:
                logger.warning(f"视频帧 {frame}: overlay 不存在 {overlay_path}")
                continue

        if not images_b64:
            logger.warning(f"视频 {video_rel_path} 没有可用的关键帧图片")
            return None

        # 提取timeline标注
        timeline_annotations = [
            ann for ann in annotations if ann.get("type") == "timeline"
        ]

        # 构建content
        image_placeholders = "".join(["<image>"] * len(images_b64))

        messages = [
            {
                "role": "user",
                "content": f"{image_placeholders}{inst_data['instruction']}",
            },
            {"role": "assistant", "content": inst_data["raw_response"]},
        ]

        return {
            "messages": messages,
            "images": images_b64,  # 关键帧作为图像序列
            "metadata": {
                "source_file": str(video_rel_path),
                "media_type": "video",
                "frames": annotated_frames,
                "timeline_annotations": timeline_annotations,
                "llm_provider": inst_data.get("llm_provider"),
                "model_name": inst_data.get("model_name"),
                "timestamp": inst_data.get("timestamp"),
            },
        }

    def _get_overlay_path(self, media_path: str, media_type: str) -> Path:
        """获取overlay文件路径"""
        # uploads/test_data/test_imgs/cover_0001.jpg
        # -> overlays/test_data/test_imgs/cover_0001_overlay.png
        parts = Path(media_path).parts
        filename = Path(media_path).stem

        # 重建路径（去掉第一级目录）
        rel_dir = Path(*parts[:-1]) if len(parts) > 1 else Path(".")
        overlay_path = self.overlays_dir / rel_dir / f"{filename}_overlay.png"
        return overlay_path

    def _get_pdf_overlay_path(self, pdf_path: str, page: int) -> Path:
        """获取PDF页面的overlay路径"""
        # uploads/test_data/test_pdf/PDU.pdf
        # -> overlays/test_data/test_pdf/PDU/page_0000_overlay.png
        parts = Path(pdf_path).parts
        pdf_name = Path(pdf_path).stem

        # 重建路径
        rel_dir = Path(*parts[:-1]) if len(parts) > 1 else Path(".")
        overlay_path = (
            self.overlays_dir / rel_dir / pdf_name / f"page_{page:04d}_overlay.png"
        )
        return overlay_path

    def _get_video_overlay_path(self, video_path: str, frame: int) -> Path:
        """获取视频帧的overlay路径"""
        # uploads/test_data/test_videos/TestVideo1.mp4
        # -> overlays/test_data/test_videos/TestVideo1/000027_overlay.png
        parts = Path(video_path).parts
        video_name = Path(video_path).stem

        # 重建路径
        rel_dir = Path(*parts[:-1]) if len(parts) > 1 else Path(".")
        overlay_path = (
            self.overlays_dir / rel_dir / video_name / f"{frame:06d}_overlay.png"
        )
        return overlay_path

    def convert_all(
        self,
        use_overlay: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Dict]:
        """
        转换所有instruction文件

        Args:
            use_overlay: 是否优先使用带标注框的图片
            progress_callback: 进度回调函数 (current, total, filename)

        Returns:
            转换后的数据列表
        """
        results = []
        instruction_files = list(self.instruction_dir.rglob("*.json"))
        total_files = len(instruction_files)

        logger.info(f"找到 {total_files} 个 instruction 文件")

        for idx, inst_file in enumerate(instruction_files, 1):
            try:
                with open(inst_file, "r", encoding="utf-8") as f:
                    inst_data = json.load(f)

                # 根据类型处理
                if "image" in inst_data:
                    result = self.process_image_instruction(inst_data, use_overlay)
                elif "pdf" in inst_data:
                    result = self.process_pdf_instruction(inst_data, use_overlay)
                elif "video" in inst_data:
                    result = self.process_video_instruction(inst_data, use_overlay)
                else:
                    logger.warning(f"未知类型: {inst_file}")
                    continue

                if result:
                    results.append(result)
                    logger.debug(f"[{idx}/{total_files}] 处理成功: {inst_file.name}")

                # 调用进度回调
                if progress_callback:
                    progress_callback(idx, total_files, inst_file.name)

            except Exception as e:
                logger.error(f"处理失败 {inst_file}: {e}")
                continue

        logger.info(f"转换完成: {len(results)}/{total_files} 个样本")
        return results

    def save_to_parquet(
        self, results: List[Dict], output_path: str, compression: str = "snappy"
    ):
        """保存为单个Parquet文件"""
        df = pd.DataFrame(results)
        df.to_parquet(output_path, engine="pyarrow", compression=compression)
        logger.info(f"保存到: {output_path}")

    def save_to_parquet_sharded(
        self,
        results: List[Dict],
        output_dir: str,
        output_prefix: str = "train",
        max_shard_size_mb: int = 100,
    ) -> List[str]:
        """
        自动分片保存，参考 FineVision 数据集

        Args:
            results: 转换后的数据
            output_dir: 输出目录
            output_prefix: 文件前缀（train/validation/test）
            max_shard_size_mb: 每个分片最大大小（MB）

        Returns:
            生成的文件名列表
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 预估每个样本的大小
        def estimate_size(sample: Dict) -> int:
            """估算样本大小（字节）"""
            size = 0
            # 图片base64大小
            if "images" in sample:
                for img in sample["images"]:
                    size += len(img)
            # 文本大小
            for msg in sample["messages"]:
                size += len(json.dumps(msg, ensure_ascii=False))
            # metadata大小
            size += len(json.dumps(sample.get("metadata", {}), ensure_ascii=False))
            return size

        # 分片
        shards = []
        current_shard = []
        current_size = 0
        max_size_bytes = max_shard_size_mb * 1024 * 1024

        for sample in results:
            sample_size = estimate_size(sample)

            # 检查是否需要创建新分片
            if current_size + sample_size > max_size_bytes and current_shard:
                shards.append(current_shard)
                current_shard = []
                current_size = 0

            current_shard.append(sample)
            current_size += sample_size

        # 添加最后一个分片
        if current_shard:
            shards.append(current_shard)

        total_shards = len(shards)
        logger.info(f"数据将分为 {total_shards} 个分片")

        output_files = []

        # 保存每个分片
        for idx, shard in enumerate(shards):
            filename = f"{output_prefix}-{idx:05d}-of-{total_shards:05d}.parquet"
            filepath = output_path / filename

            df = pd.DataFrame(shard)
            df.to_parquet(filepath, engine="pyarrow", compression="snappy")

            shard_size_mb = filepath.stat().st_size / (1024 * 1024)
            logger.info(
                f"✓ {filename} ({len(shard)} 样本, {shard_size_mb:.1f}MB)"
            )
            output_files.append(filename)

        return output_files

    def save_to_jsonl(self, results: List[Dict], output_path: str):
        """保存为JSONL格式（用于调试）"""
        with open(output_path, "w", encoding="utf-8") as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
        logger.info(f"保存到: {output_path}")

    def get_statistics(self, results: List[Dict]) -> Dict[str, Any]:
        """获取数据集统计信息"""
        stats = {
            "total_samples": len(results),
            "media_types": {"image": 0, "pdf": 0, "video": 0},
            "total_images": 0,
            "providers": {},
            "models": {},
        }

        for result in results:
            metadata = result.get("metadata", {})
            media_type = metadata.get("media_type", "unknown")

            # 统计媒体类型
            if media_type in stats["media_types"]:
                stats["media_types"][media_type] += 1

            # 统计图片数量
            stats["total_images"] += len(result.get("images", []))

            # 统计 LLM 提供商
            provider = metadata.get("llm_provider", "unknown")
            stats["providers"][provider] = stats["providers"].get(provider, 0) + 1

            # 统计模型
            model = metadata.get("model_name", "unknown")
            stats["models"][model] = stats["models"].get(model, 0) + 1

        return stats


def validate_annotation_project(project_name: str) -> Dict[str, Any]:
    """
    验证标注项目结构

    Args:
        project_name: 项目文件夹名称

    Returns:
        验证结果字典
    """
    # 安全验证
    if ".." in project_name or "/" in project_name or "\\" in project_name:
        return {
            "valid": False,
            "error": "非法的项目名称",
        }

    project_root = DATA_DIR / project_name

    if not project_root.exists():
        return {
            "valid": False,
            "error": f"项目不存在: {project_name}",
        }

    if not project_root.is_dir():
        return {
            "valid": False,
            "error": f"{project_name} 不是文件夹",
        }

    instruction_dir = project_root / "instruction"
    uploads_dir = project_root / "uploads"
    overlays_dir = project_root / "overlays"

    missing_dirs = []
    if not instruction_dir.exists():
        missing_dirs.append("instruction")
    if not uploads_dir.exists():
        missing_dirs.append("uploads")

    if missing_dirs:
        return {
            "valid": False,
            "error": f"缺少必需的目录: {', '.join(missing_dirs)}",
        }

    # 统计 instruction 文件数量
    instruction_files = list(instruction_dir.rglob("*.json"))
    has_overlays = overlays_dir.exists()

    return {
        "valid": True,
        "project_name": project_name,
        "instruction_count": len(instruction_files),
        "has_overlays": has_overlays,
        "structure": {
            "instruction": True,
            "uploads": True,
            "overlays": has_overlays,
        },
    }
