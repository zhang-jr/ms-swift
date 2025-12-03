# Copyright (c) Alibaba, Inc. and its affiliates.
"""
训练服务层
处理模型训练相关的业务逻辑
"""
import os
import sys
import json
import uuid
import time
import asyncio
from copy import deepcopy
from datetime import datetime
from subprocess import Popen, PIPE, STDOUT
from typing import Dict, List, Optional, Any
from pathlib import Path

from swift.llm import RLHFArguments, DATASET_MAPPING
from swift.utils import get_logger

logger = get_logger()


class TrainService:
    """训练服务类"""

    def __init__(self):
        # 存储所有训练任务
        self.tasks: Dict[str, Dict] = {}
        # 存储进程对象
        self.processes: Dict[str, Popen] = {}

    def create_task(
        self,
        model: str,
        model_type: Optional[str] = None,
        template: Optional[str] = None,
        dataset: Optional[List[str]] = None,
        custom_train_dataset_path: Optional[str] = None,
        train_stage: str = "sft",
        train_type: str = "lora",
        num_train_epochs: int = 1,
        batch_size: int = 1,
        learning_rate: float = 1e-4,
        max_length: int = 2048,
        gradient_accumulation_steps: int = 16,
        gpu_id: Optional[List[str]] = None,
        seed: int = 42,
        output_dir: Optional[str] = None,
        logging_steps: int = 5,
        save_steps: Optional[int] = None,
        more_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建训练任务

        Args:
            model: 模型 ID 或路径
            其他参数同 TrainRequest

        Returns:
            task_id: 任务 ID
        """
        # 生成任务 ID
        task_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_name = f"train_{task_id}_{timestamp}"

        # 设置输出目录
        if output_dir is None:
            output_dir = f"output/{task_name}"
        os.makedirs(output_dir, exist_ok=True)

        # 设置日志目录
        logging_dir = os.path.join(output_dir, "runs")
        os.makedirs(logging_dir, exist_ok=True)

        # 日志文件
        log_file = os.path.join(logging_dir, "run.log")

        # 构建参数
        kwargs = {
            "model": model,
            "train_type": train_type,
            "num_train_epochs": num_train_epochs,
            "per_device_train_batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": max_length,
            "gradient_accumulation_steps": gradient_accumulation_steps,
            "seed": seed,
            "output_dir": output_dir,
            "logging_dir": logging_dir,
            "logging_steps": logging_steps,
        }

        # 可选参数
        if model_type:
            kwargs["model_type"] = model_type
        if template:
            kwargs["template"] = template
        if dataset:
            kwargs["dataset"] = dataset
        if custom_train_dataset_path:
            kwargs["custom_train_dataset_path"] = custom_train_dataset_path
        if save_steps:
            kwargs["save_steps"] = save_steps
        if more_params:
            kwargs.update(more_params)

        # GPU 配置
        gpu_str = ",".join(gpu_id) if gpu_id else "0"

        # 保存任务信息
        self.tasks[task_id] = {
            "task_id": task_id,
            "task_name": task_name,
            "status": "pending",
            "train_stage": train_stage,
            "kwargs": kwargs,
            "gpu_id": gpu_str,
            "output_dir": output_dir,
            "logging_dir": logging_dir,
            "log_file": log_file,
            "start_time": None,
            "end_time": None,
            "progress": 0.0,
            "message": "任务已创建"
        }

        logger.info(f"Created training task: {task_id}")
        return task_id

    def run_training(self, task_id: str):
        """
        运行训练任务(在后台进程中)

        Args:
            task_id: 任务 ID
        """
        if task_id not in self.tasks:
            logger.error(f"Task {task_id} not found")
            return

        task = self.tasks[task_id]
        task["status"] = "running"
        task["start_time"] = datetime.now().isoformat()
        task["message"] = "训练进行中"

        try:
            # 构建命令
            command = self._build_command(task)
            logger.info(f"Running command: {' '.join(command)}")

            # 设置环境变量
            env = deepcopy(os.environ)
            if "cpu" not in task["gpu_id"]:
                env["CUDA_VISIBLE_DEVICES"] = task["gpu_id"]

            # 启动进程
            process = Popen(
                command,
                env=env,
                stdout=open(task["log_file"], "w"),
                stderr=STDOUT,
                cwd=os.getcwd()
            )

            self.processes[task_id] = process
            logger.info(f"Training process started: PID {process.pid}")

            # 等待进程结束
            return_code = process.wait()

            # 更新任务状态
            if return_code == 0:
                task["status"] = "completed"
                task["message"] = "训练完成"
                task["progress"] = 100.0
            else:
                task["status"] = "failed"
                task["message"] = f"训练失败,退出码: {return_code}"

        except Exception as e:
            logger.error(f"Training task {task_id} failed: {e}")
            task["status"] = "failed"
            task["message"] = str(e)

        finally:
            task["end_time"] = datetime.now().isoformat()
            if task_id in self.processes:
                del self.processes[task_id]

    def _build_command(self, task: Dict) -> List[str]:
        """
        构建训练命令

        Args:
            task: 任务信息

        Returns:
            command: 命令列表
        """
        command = ["swift", task["train_stage"]]
        kwargs = task["kwargs"]

        # 添加参数
        for key, value in kwargs.items():
            if value is None:
                continue
            if isinstance(value, bool):
                if value:
                    command.extend([f"--{key}", "true"])
            elif isinstance(value, list):
                command.extend([f"--{key}"] + [str(v) for v in value])
            else:
                command.extend([f"--{key}", str(value)])

        # 添加固定参数
        command.extend([
            "--add_version", "False",
            "--ignore_args_error", "True"
        ])

        return command

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态

        Args:
            task_id: 任务 ID

        Returns:
            status: 任务状态信息
        """
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        return {
            "task_id": task_id,
            "status": task["status"],
            "progress": task.get("progress", 0.0),
            "message": task.get("message", ""),
            "start_time": task.get("start_time"),
            "end_time": task.get("end_time"),
            "output_dir": task.get("output_dir"),
            "logging_dir": task.get("logging_dir")
        }

    def get_task_info(self, task_id: str) -> Optional[Dict]:
        """获取任务完整信息"""
        return self.tasks.get(task_id)

    def stop_task(self, task_id: str) -> bool:
        """
        停止训练任务

        Args:
            task_id: 任务 ID

        Returns:
            success: 是否成功停止
        """
        if task_id not in self.tasks:
            return False

        if task_id in self.processes:
            process = self.processes[task_id]
            process.terminate()
            time.sleep(1)
            if process.poll() is None:
                process.kill()

            self.tasks[task_id]["status"] = "stopped"
            self.tasks[task_id]["message"] = "任务已停止"
            self.tasks[task_id]["end_time"] = datetime.now().isoformat()
            del self.processes[task_id]
            logger.info(f"Task {task_id} stopped")
            return True

        return False

    def list_tasks(self) -> List[Dict]:
        """
        获取所有任务列表

        Returns:
            tasks: 任务列表
        """
        return [
            {
                "task_id": task_id,
                "task_name": task["task_name"],
                "status": task["status"],
                "start_time": task.get("start_time"),
                "output_dir": task["output_dir"]
            }
            for task_id, task in self.tasks.items()
        ]

    def get_task_logs(
        self,
        task_id: str,
        lines: int = 50,
        offset: int = 0
    ) -> Optional[str]:
        """
        获取任务日志

        Args:
            task_id: 任务 ID
            lines: 读取行数
            offset: 偏移量

        Returns:
            logs: 日志内容
        """
        if task_id not in self.tasks:
            return None

        log_file = self.tasks[task_id]["log_file"]
        if not os.path.exists(log_file):
            return ""

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                start = max(0, len(all_lines) - lines - offset)
                end = len(all_lines) - offset
                return "".join(all_lines[start:end])
        except Exception as e:
            logger.error(f"Failed to read log file: {e}")
            return None

    async def stream_task_logs(self, task_id: str):
        """
        流式读取任务日志(用于 WebSocket)

        Args:
            task_id: 任务 ID

        Yields:
            log_line: 日志行
        """
        if task_id not in self.tasks:
            return

        log_file = self.tasks[task_id]["log_file"]

        # 等待日志文件创建
        for _ in range(30):
            if os.path.exists(log_file):
                break
            await asyncio.sleep(0.5)

        if not os.path.exists(log_file):
            yield "日志文件未创建"
            return

        # 实时读取日志
        with open(log_file, "r", encoding="utf-8") as f:
            # 先读取已有内容
            for line in f:
                yield line.rstrip("\n")

            # 持续读取新内容
            while task_id in self.processes:
                line = f.readline()
                if line:
                    yield line.rstrip("\n")
                else:
                    await asyncio.sleep(0.5)

    def list_available_datasets(self) -> List[str]:
        """
        获取可用数据集列表

        Returns:
            datasets: 数据集列表
        """
        try:
            # 从 swift 获取数据集列表
            datasets = list(DATASET_MAPPING.keys())
            return sorted(datasets)
        except Exception as e:
            logger.error(f"Failed to list datasets: {e}")
            return []
