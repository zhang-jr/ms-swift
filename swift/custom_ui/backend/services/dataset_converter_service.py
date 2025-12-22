"""
数据集转换服务（重构版）
将标注数据转换为 HuggingFace Datasets 格式（Parquet）
基于标注平台的转换逻辑，适配训练平台的目录结构

核心原则:
1. overlays 只是可视化标注结果，训练数据使用 uploads 中的原始数据
2. 图片直接转 base64
3. PDF 从原始 PDF 提取页面图片（使用 PyMuPDF）
4. Video 暂时只保存路径（文件太大）
5. dataset_infos.json 保存在项目根目录（与 data 平行）
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
    """数据集转换器（重构版 - 使用 uploads 原始数据）"""

    def __init__(self, project_name: str):
        """
        初始化转换器

        Args:
            project_name: 标注项目文件夹名称（位于 /app/data 下）
        """
        # 安全验证：防止路径遍历攻击
        if ".." in project_name or "/" in project_name or "\\" in project_name:
            raise ValueError(f"非法的项目名称: {project_name}")

        self.project_name = project_name
        self.project_root = DATA_DIR / project_name
        self.instructions_dir = self.project_root / "instructions"  # 标注数据
        self.uploads_dir = self.project_root / "uploads"  # 原始媒体文件
        self.data_dir = self.project_root / "data"  # 输出目录

        # 验证目录
        self._validate_directories()

    def _validate_directories(self):
        """验证必需的目录是否存在"""
        if not self.project_root.exists():
            raise ValueError(f"项目根目录不存在: {self.project_root}")

        if not self.instructions_dir.exists():
            raise ValueError(f"instructions 目录不存在: {self.instructions_dir}")

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

    def process_image_instruction(self, inst_data: Dict) -> Optional[Dict]:
        """
        处理图像类型的instruction

        Args:
            inst_data: instruction 数据

        Returns:
            转换后的数据（使用 uploads 中的原始图片）
        """
        image_rel_path = inst_data["image"]

        # 从 uploads 获取原始图片
        upload_path = self.uploads_dir / image_rel_path

        if not upload_path.exists():
            logger.warning(f"原始图片不存在: {upload_path}")
            return None

        # 转换为 base64
        image_b64 = self.image_to_base64(upload_path)

        # 构建 messages（多模态格式）
        messages = [
            {"role": "user", "content": f"<image>{inst_data['instruction']}"},
            {"role": "assistant", "content": inst_data["raw_response"]},
        ]

        return {
            "messages": json.dumps(messages, ensure_ascii=False),  # 转为字符串
            "images": json.dumps([image_b64], ensure_ascii=False),  # 转为字符串
            "source_file": str(image_rel_path),
            "media_type": "image",
            "llm_provider": inst_data.get("llm_provider", ""),
            "model_name": inst_data.get("model_name", ""),
        }

    def process_pdf_instruction(self, inst_data: Dict) -> Optional[Dict]:
        """
        处理 PDF 类型的 instruction

        从原始 PDF 提取页面图片（使用 PyMuPDF）

        Args:
            inst_data: instruction 数据

        Returns:
            转换后的数据
        """
        pdf_rel_path = inst_data["pdf"]
        annotations = inst_data.get("annotations", [])

        # 获取所有被标注的页面
        annotated_pages = sorted(set(ann["page"] for ann in annotations if "page" in ann))

        if not annotated_pages:
            logger.warning(f"PDF {pdf_rel_path} 没有标注页面")
            return None

        # 从原始 PDF 提取页面图片
        pdf_path = self.uploads_dir / pdf_rel_path

        if not pdf_path.exists():
            logger.warning(f"原始 PDF 不存在: {pdf_path}")
            return None

        try:
            import pymupdf  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF 未安装，无法处理 PDF。请安装: pip install pymupdf")
            return None

        images_b64 = []

        try:
            doc = pymupdf.open(pdf_path)

            for page_num in annotated_pages:
                if page_num >= len(doc):
                    logger.warning(f"PDF {pdf_rel_path} 页面 {page_num} 不存在（总页数: {len(doc)}）")
                    continue

                # 提取页面为图片
                page = doc[page_num]
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))  # 2x 缩放
                img_bytes = pix.tobytes("png")

                # 转为 base64
                image_b64 = base64.b64encode(img_bytes).decode("utf-8")
                images_b64.append(image_b64)

            doc.close()

        except Exception as e:
            logger.error(f"从 PDF 提取页面失败 {pdf_path}: {e}")
            return None

        if not images_b64:
            logger.warning(f"PDF {pdf_rel_path} 没有可用的页面图片")
            return None

        # 构建 messages
        image_placeholders = "".join(["<image>"] * len(images_b64))
        messages = [
            {
                "role": "user",
                "content": f"{image_placeholders}{inst_data['instruction']}",
            },
            {"role": "assistant", "content": inst_data["raw_response"]},
        ]

        return {
            "messages": json.dumps(messages, ensure_ascii=False),
            "images": json.dumps(images_b64, ensure_ascii=False),
            "source_file": str(pdf_rel_path),
            "media_type": "pdf",
            "llm_provider": inst_data.get("llm_provider", ""),
            "model_name": inst_data.get("model_name", ""),
        }

    def process_video_instruction(self, inst_data: Dict) -> Optional[Dict]:
        """
        处理视频类型的 instruction

        视频文件太大，暂时只保存路径（或跳过）

        Args:
            inst_data: instruction 数据

        Returns:
            转换后的数据（或 None 跳过）
        """
        video_rel_path = inst_data["video"]
        annotations = inst_data.get("annotations", [])

        # 提取标注的帧
        annotated_frames = sorted(
            set(ann["frame"] for ann in annotations if "frame" in ann)
        )

        if not annotated_frames:
            logger.warning(f"视频 {video_rel_path} 没有标注帧，跳过")
            return None

        # 暂时跳过视频（文件太大）
        # TODO: 未来可以提取关键帧或保存路径
        logger.info(f"跳过视频 {video_rel_path}（暂不支持）")
        return None

    def convert_all(
        self,
        use_overlay: bool = False,  # 不再使用 overlay
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Dict]:
        """
        转换所有 instruction 文件

        扫描 instructions/ 下的所有 JSON 文件（递归）

        Args:
            use_overlay: 忽略（不再使用 overlay）
            progress_callback: 进度回调函数 (current, total, filename)

        Returns:
            转换后的数据列表
        """
        results = []
        instruction_files = list(self.instructions_dir.rglob("*.json"))
        total_files = len(instruction_files)

        logger.info(f"扫描 instructions/ 目录，找到 {total_files} 个 instruction 文件")

        # 统计各类型数据数量
        stats = {"image": 0, "pdf": 0, "video": 0, "skipped": 0}

        for idx, inst_file in enumerate(instruction_files, 1):
            try:
                with open(inst_file, "r", encoding="utf-8") as f:
                    inst_data = json.load(f)

                # 根据类型处理
                result = None
                if "image" in inst_data:
                    result = self.process_image_instruction(inst_data)
                    if result:
                        stats["image"] += 1
                elif "pdf" in inst_data:
                    result = self.process_pdf_instruction(inst_data)
                    if result:
                        stats["pdf"] += 1
                elif "video" in inst_data:
                    result = self.process_video_instruction(inst_data)
                    if result:
                        stats["video"] += 1
                else:
                    logger.warning(f"未知类型: {inst_file}")
                    stats["skipped"] += 1
                    continue

                if result:
                    results.append(result)
                    logger.debug(f"[{idx}/{total_files}] 处理成功: {inst_file.name}")
                else:
                    stats["skipped"] += 1

                # 调用进度回调
                if progress_callback:
                    progress_callback(idx, total_files, inst_file.name)

            except Exception as e:
                logger.error(f"处理失败 {inst_file}: {e}")
                stats["skipped"] += 1
                continue

        logger.info(f"转换完成: {len(results)}/{total_files} 个样本")
        logger.info(f"统计: 图片={stats['image']}, PDF={stats['pdf']}, 视频={stats['video']}, 跳过={stats['skipped']}")

        return results

    def save_to_parquet(
        self, results: List[Dict], output_path: str, compression: str = "snappy"
    ):
        """
        保存为单个 Parquet 文件

        注意: images 字段是字符串（JSON 格式），避免 Parquet 格式问题
        """
        df = pd.DataFrame(results)
        df.to_parquet(output_path, engine="pyarrow", compression=compression, index=False)
        logger.info(f"保存到: {output_path}")

    def save_to_parquet_sharded(
        self,
        results: List[Dict],
        output_dir: str,
        output_prefix: str = "train",
        max_shard_size_mb: int = 500,
    ) -> List[str]:
        """
        自动分片保存

        Args:
            results: 转换后的数据
            output_dir: 输出目录
            output_prefix: 文件前缀
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
            # images 字段（JSON 字符串）
            if "images" in sample:
                size += len(sample["images"])
            # messages 字段（JSON 字符串）
            if "messages" in sample:
                size += len(sample["messages"])
            # 其他字段
            for key in ["source_file", "media_type", "llm_provider", "model_name"]:
                if key in sample:
                    size += len(str(sample[key]))
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
            df.to_parquet(filepath, engine="pyarrow", compression="snappy", index=False)

            shard_size_mb = filepath.stat().st_size / (1024 * 1024)
            logger.info(
                f"✓ {filename} ({len(shard)} 样本, {shard_size_mb:.1f}MB)"
            )
            output_files.append(filename)

        return output_files

    def generate_dataset_infos(
        self,
        output_files: List[str],
        num_samples: int,
    ) -> Dict[str, Any]:
        """
        生成 dataset_infos.json 文件（保存在项目根目录，与 data 平行）

        Args:
            output_files: 生成的 Parquet 文件列表
            num_samples: 样本总数

        Returns:
            dataset_infos 字典
        """
        # 计算总大小
        total_bytes = 0
        for filename in output_files:
            filepath = self.data_dir / filename
            if filepath.exists():
                total_bytes += filepath.stat().st_size

        dataset_infos = {
            "default": {
                "description": f"Annotation dataset for vision tasks - {self.project_name}",
                "citation": "",
                "homepage": "",
                "license": "",
                "features": {
                    "messages": {"dtype": "string"},  # JSON 字符串
                    "images": {"dtype": "string"},  # JSON 字符串（base64 列表）
                    "source_file": {"dtype": "string"},
                    "media_type": {"dtype": "string"},
                    "llm_provider": {"dtype": "string"},
                    "model_name": {"dtype": "string"},
                },
                "splits": {
                    "train": {
                        "name": "train",
                        "num_bytes": total_bytes,
                        "num_examples": num_samples,
                        "dataset_name": self.project_name,
                    }
                },
                "download_size": total_bytes,
                "dataset_size": total_bytes,
            }
        }

        # 保存到项目根目录（与 data 平行）
        infos_path = self.project_root / "dataset_infos.json"
        with open(infos_path, "w", encoding="utf-8") as f:
            json.dump(dataset_infos, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ 生成 dataset_infos.json: {infos_path}")
        return dataset_infos

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
            media_type = result.get("media_type", "unknown")

            # 统计媒体类型
            if media_type in stats["media_types"]:
                stats["media_types"][media_type] += 1

            # 统计图片数量（解析 JSON 字符串）
            images_json = result.get("images", "[]")
            try:
                images_list = json.loads(images_json)
                stats["total_images"] += len(images_list)
            except:
                pass

            # 统计 LLM 提供商
            provider = result.get("llm_provider", "unknown")
            if provider:
                stats["providers"][provider] = stats["providers"].get(provider, 0) + 1

            # 统计模型
            model = result.get("model_name", "unknown")
            if model:
                stats["models"][model] = stats["models"].get(model, 0) + 1

        return stats


def validate_annotation_project(project_name: str) -> Dict[str, Any]:
    """
    验证标注项目结构

    项目结构要求:
    - instructions/ (必需) - 包含 instruction JSON 文件
    - uploads/ (必需) - 原始媒体文件

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

    instructions_dir = project_root / "instructions"
    uploads_dir = project_root / "uploads"

    missing_dirs = []
    if not instructions_dir.exists():
        missing_dirs.append("instructions")
    if not uploads_dir.exists():
        missing_dirs.append("uploads")

    if missing_dirs:
        return {
            "valid": False,
            "error": f"缺少必需的目录: {', '.join(missing_dirs)}",
        }

    # 统计 instruction 文件数量（递归扫描）
    instruction_files = list(instructions_dir.rglob("*.json"))

    # 统计各类型数量
    type_counts = {"image": 0, "pdf": 0, "video": 0, "unknown": 0}
    for inst_file in instruction_files:
        try:
            with open(inst_file, "r") as f:
                data = json.load(f)
                if "image" in data:
                    type_counts["image"] += 1
                elif "pdf" in data:
                    type_counts["pdf"] += 1
                elif "video" in data:
                    type_counts["video"] += 1
                else:
                    type_counts["unknown"] += 1
        except:
            pass

    return {
        "valid": True,
        "project_name": project_name,
        "instruction_count": len(instruction_files),
        "type_counts": type_counts,
        "structure": {
            "instructions": True,
            "uploads": True,
        },
    }
