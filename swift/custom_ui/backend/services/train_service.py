"""
训练服务
封装 ms-swift 训练功能
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# 数据目录
DATA_DIR = Path("/app/data")

class TrainService:
    """训练服务类"""

    def __init__(self):
        self.running_tasks: Dict[str, Any] = {}

    def resolve_dataset_path(self, dataset: str) -> str:
        """
        解析数据集路径
        如果是文件名，自动从 /app/data 目录查找
        如果是绝对路径，直接使用

        Args:
            dataset: 数据集文件名或路径

        Returns:
            str: 完整的数据集路径

        Raises:
            FileNotFoundError: 数据集文件不存在
        """
        dataset_path = Path(dataset)

        # 如果是绝对路径，直接使用
        if dataset_path.is_absolute():
            if not dataset_path.exists():
                raise FileNotFoundError(f"数据集不存在: {dataset}")
            return str(dataset_path)

        # 如果是相对路径或文件名，在 DATA_DIR 中查找
        full_path = DATA_DIR / dataset
        if not full_path.exists():
            raise FileNotFoundError(
                f"数据集文件不存在: {dataset}。"
                f"请先通过 /api/data/upload 上传数据集，或使用绝对路径。"
            )

        return str(full_path)

    async def run_training(self, task_id: str, config: Dict[str, Any]):
        """
        执行训练任务

        Args:
            task_id: 任务 ID
            config: 训练配置
        """
        # 导入训练任务管理
        from api.train import get_task, update_task

        try:
            # 解析数据集路径
            dataset_path = self.resolve_dataset_path(config['dataset'])
            config['dataset'] = dataset_path

            # 更新状态为运行中
            update_task(task_id, {
                "status": "running",
                "progress": 0
            })

            # TODO: 实际调用 ms-swift 训练
            # 这里需要集成 swift.llm.sft_main 或使用命令行调用
            """
            from swift.llm import sft_main, TrainArguments
            from swift.utils import get_logger

            logger = get_logger()

            # 构建训练参数
            train_args = TrainArguments(
                model_type=config['model_type'],
                dataset=[config['dataset']],
                train_dataset_sample=-1,
                num_train_epochs=config['num_train_epochs'],
                per_device_train_batch_size=config['per_device_train_batch_size'],
                gradient_accumulation_steps=config['gradient_accumulation_steps'],
                learning_rate=config['learning_rate'],
                max_length=config['max_length'],
                lora_rank=config['lora_rank'],
                lora_alpha=config['lora_alpha'],
                lora_dropout=config['lora_dropout'],
                output_dir=config['output_dir'],
                logging_steps=config['logging_steps'],
                save_steps=config['save_steps'],
                warmup_ratio=config['warmup_ratio'],
                weight_decay=config['weight_decay'],
                gradient_checkpointing=config['gradient_checkpointing'],
            )

            # 启动训练
            result = sft_main(train_args)
            """

            # 模拟训练过程
            total_epochs = config.get('num_train_epochs', 1)
            for epoch in range(total_epochs):
                # 模拟 epoch 训练
                await asyncio.sleep(2)  # 模拟训练时间

                progress = (epoch + 1) / total_epochs * 100
                loss = 2.5 - (epoch * 0.3)  # 模拟 loss 下降

                # 更新任务进度
                task = get_task(task_id)
                if task:
                    logs = task.get("logs", [])
                    logs.append(f"Epoch {epoch + 1}/{total_epochs} - Loss: {loss:.4f}")

                    update_task(task_id, {
                        "current_epoch": epoch + 1,
                        "progress": progress,
                        "loss": loss,
                        "logs": logs
                    })

                    # 通过 WebSocket 推送日志
                    await self._send_log_to_websocket(
                        task_id,
                        f"Epoch {epoch + 1}/{total_epochs} - Loss: {loss:.4f}"
                    )

            # 训练完成
            update_task(task_id, {
                "status": "completed",
                "progress": 100
            })

            await self._send_log_to_websocket(task_id, "训练完成!")

        except Exception as e:
            # 训练失败
            update_task(task_id, {
                "status": "failed",
                "error": str(e)
            })

            await self._send_log_to_websocket(task_id, f"训练失败: {str(e)}")

    async def _send_log_to_websocket(self, task_id: str, message: str):
        """
        通过 WebSocket 发送日志

        Args:
            task_id: 任务 ID
            message: 日志消息
        """
        try:
            from app import manager
            await manager.send_message(message, task_id)
        except Exception as e:
            print(f"Failed to send log via WebSocket: {e}")

    def stop_training(self, task_id: str):
        """
        停止训练任务

        Args:
            task_id: 任务 ID
        """
        # TODO: 实现训练任务停止逻辑
        if task_id in self.running_tasks:
            # 发送停止信号
            self.running_tasks[task_id]["should_stop"] = True
