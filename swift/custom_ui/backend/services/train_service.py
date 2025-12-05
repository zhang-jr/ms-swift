"""
训练服务
封装 ms-swift 训练功能
"""
import asyncio
import os
import subprocess
import signal
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import json
import re

# 数据目录和输出目录
DATA_DIR = Path("/app/data")
OUTPUT_DIR = Path("/app/output")

class TrainService:
    """训练服务类"""

    def __init__(self):
        self.running_processes: Dict[str, subprocess.Popen] = {}

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

    def build_train_command(self, task_id: str, config: Dict[str, Any]) -> list:
        """
        构建训练命令

        Args:
            task_id: 任务 ID
            config: 训练配置

        Returns:
            list: 训练命令参数列表
        """
        # 解析数据集路径
        dataset_path = self.resolve_dataset_path(config['dataset'])

        # 输出目录
        output_dir = OUTPUT_DIR / task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # 基础命令
        cmd = [
            "swift", "sft",
            "--model", config.get('model', 'Qwen/Qwen2.5-7B-Instruct'),
            "--dataset", dataset_path,
            "--output_dir", str(output_dir),
        ]

        # 训练类型（lora/full）
        train_type = config.get('train_type', 'lora')
        cmd.extend(["--train_type", train_type])

        # 数据类型
        torch_dtype = config.get('torch_dtype', 'bfloat16')
        cmd.extend(["--torch_dtype", torch_dtype])

        # 训练轮数
        num_train_epochs = config.get('num_train_epochs', 1)
        cmd.extend(["--num_train_epochs", str(num_train_epochs)])

        # batch size
        per_device_train_batch_size = config.get('per_device_train_batch_size', 1)
        cmd.extend(["--per_device_train_batch_size", str(per_device_train_batch_size)])

        per_device_eval_batch_size = config.get('per_device_eval_batch_size', 1)
        cmd.extend(["--per_device_eval_batch_size", str(per_device_eval_batch_size)])

        # 学习率
        learning_rate = config.get('learning_rate', 1e-4)
        cmd.extend(["--learning_rate", str(learning_rate)])

        # LoRA 参数（仅在 train_type=lora 时有效）
        if train_type == 'lora':
            lora_rank = config.get('lora_rank', 8)
            lora_alpha = config.get('lora_alpha', 32)
            cmd.extend([
                "--lora_rank", str(lora_rank),
                "--lora_alpha", str(lora_alpha),
                "--target_modules", "all-linear"
            ])

            lora_dropout = config.get('lora_dropout')
            if lora_dropout is not None:
                cmd.extend(["--lora_dropout", str(lora_dropout)])

        # 梯度累积
        gradient_accumulation_steps = config.get('gradient_accumulation_steps', 16)
        cmd.extend(["--gradient_accumulation_steps", str(gradient_accumulation_steps)])

        # 最大长度
        max_length = config.get('max_length', 2048)
        cmd.extend(["--max_length", str(max_length)])

        # 日志和保存频率
        logging_steps = config.get('logging_steps', 5)
        save_steps = config.get('save_steps', 50)
        eval_steps = config.get('eval_steps', 50)
        cmd.extend([
            "--logging_steps", str(logging_steps),
            "--save_steps", str(save_steps),
            "--eval_steps", str(eval_steps),
        ])

        # 保存限制
        save_total_limit = config.get('save_total_limit', 2)
        cmd.extend(["--save_total_limit", str(save_total_limit)])

        # warmup
        warmup_ratio = config.get('warmup_ratio', 0.05)
        cmd.extend(["--warmup_ratio", str(warmup_ratio)])

        # 权重衰减
        weight_decay = config.get('weight_decay', 0.01)
        cmd.extend(["--weight_decay", str(weight_decay)])

        # dataloader workers
        dataloader_num_workers = config.get('dataloader_num_workers', 4)
        cmd.extend(["--dataloader_num_workers", str(dataloader_num_workers)])

        # 系统提示词
        system = config.get('system', 'You are a helpful assistant.')
        if system:
            cmd.extend(["--system", system])

        # 模型作者和名称（用于自我认知）
        model_author = config.get('model_author')
        if model_author:
            cmd.extend(["--model_author", model_author])

        model_name = config.get('model_name')
        if model_name:
            cmd.extend(["--model_name", model_name])

        return cmd

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
            # 更新状态为运行中
            update_task(task_id, {
                "status": "running",
                "progress": 0
            })

            # 构建训练命令
            cmd = self.build_train_command(task_id, config)

            # 记录命令
            cmd_str = " ".join(cmd)
            await self._send_log_to_websocket(task_id, f"[开始训练] 命令: {cmd_str}\n")

            # 启动训练进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env={**os.environ, 'PYTHONUNBUFFERED': '1'}
            )

            # 保存进程引用
            self.running_processes[task_id] = process

            # 实时读取日志（异步方式）
            total_epochs = config.get('num_train_epochs', 1)

            # 使用异步方式读取进程输出
            loop = asyncio.get_event_loop()

            async def read_stream():
                """异步读取进程输出流"""
                while True:
                    # 在线程池中执行同步读取操作
                    line = await loop.run_in_executor(None, process.stdout.readline)

                    if not line:
                        break

                    line = line.strip()

                    # 发送日志到 WebSocket
                    await self._send_log_to_websocket(task_id, line)

                    # 解析日志提取进度信息
                    progress_info = self._parse_training_log(line, total_epochs)
                    if progress_info:
                        update_task(task_id, progress_info)

                    # 检查是否被停止
                    if task_id not in self.running_processes:
                        process.terminate()
                        break

            # 读取日志
            await read_stream()

            # 等待进程结束
            return_code = await loop.run_in_executor(None, process.wait)

            # 清理进程引用
            if task_id in self.running_processes:
                del self.running_processes[task_id]

            if return_code == 0:
                # 训练成功
                update_task(task_id, {
                    "status": "completed",
                    "progress": 100
                })
                await self._send_log_to_websocket(task_id, "\n[训练完成] 🎉")
            else:
                # 训练失败
                update_task(task_id, {
                    "status": "failed",
                    "error": f"训练进程退出码: {return_code}"
                })
                await self._send_log_to_websocket(task_id, f"\n[训练失败] 退出码: {return_code}")

        except FileNotFoundError as e:
            # 数据集不存在
            update_task(task_id, {
                "status": "failed",
                "error": str(e)
            })
            await self._send_log_to_websocket(task_id, f"[错误] {str(e)}")

        except Exception as e:
            # 其他错误
            update_task(task_id, {
                "status": "failed",
                "error": str(e)
            })
            await self._send_log_to_websocket(task_id, f"[训练失败] {str(e)}")

    def _parse_training_log(self, log_line: str, total_epochs: int) -> Optional[Dict[str, Any]]:
        """
        解析训练日志，提取进度信息

        Args:
            log_line: 日志行
            total_epochs: 总轮数

        Returns:
            dict: 进度信息（如果有）
        """
        try:
            # 尝试解析 trainer 输出的进度信息
            # 示例: {'loss': 2.5, 'learning_rate': 1e-4, 'epoch': 0.5}
            if '{' in log_line and '}' in log_line:
                # 提取 JSON 部分
                json_start = log_line.index('{')
                json_end = log_line.rindex('}') + 1
                json_str = log_line[json_start:json_end]

                # 解析 JSON（需要处理单引号）
                json_str = json_str.replace("'", '"')
                data = json.loads(json_str)

                result = {}

                # 提取 loss
                if 'loss' in data:
                    result['loss'] = float(data['loss'])

                # 提取 epoch 和计算进度
                if 'epoch' in data:
                    current_epoch = float(data['epoch'])
                    result['current_epoch'] = current_epoch
                    result['progress'] = (current_epoch / total_epochs) * 100

                # 提取学习率
                if 'learning_rate' in data:
                    result['learning_rate'] = float(data['learning_rate'])

                return result if result else None

        except (ValueError, KeyError, json.JSONDecodeError):
            pass

        return None

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

    def stop_training(self, task_id: str) -> bool:
        """
        停止训练任务

        Args:
            task_id: 任务 ID

        Returns:
            bool: 是否成功停止
        """
        if task_id in self.running_processes:
            process = self.running_processes[task_id]
            try:
                # 发送 SIGTERM 信号
                process.terminate()

                # 等待最多 10 秒
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # 强制杀死
                    process.kill()
                    process.wait()

                # 清理
                del self.running_processes[task_id]
                return True
            except Exception as e:
                print(f"Error stopping training {task_id}: {e}")
                return False

        return False

    def get_running_tasks(self) -> list:
        """
        获取所有正在运行的任务 ID

        Returns:
            list: 任务 ID 列表
        """
        return list(self.running_processes.keys())
