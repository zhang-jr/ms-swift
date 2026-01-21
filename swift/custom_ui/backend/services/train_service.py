"""
训练服务
封装 ms-swift 训练功能
"""
import asyncio
import os
import subprocess
import signal
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import json
import re

# 数据目录、模型目录和输出目录
DATA_DIR = Path("/app/data")
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))
OUTPUT_DIR = Path("/app/output")


def detect_gpus() -> Tuple[int, str]:
    """
    自动检测可用的 GPU 数量和设备 ID

    优先级:
    1. 环境变量 CUDA_VISIBLE_DEVICES（如果已设置）
    2. 自动检测所有可用 GPU

    Returns:
        Tuple[int, str]: (GPU 数量, CUDA_VISIBLE_DEVICES 字符串)
    """
    # 如果环境变量已设置，使用环境变量
    cuda_visible = os.environ.get('CUDA_VISIBLE_DEVICES')
    if cuda_visible is not None and cuda_visible.strip():
        gpu_ids = [x.strip() for x in cuda_visible.split(',') if x.strip()]
        return len(gpu_ids), cuda_visible

    # 尝试使用 torch 检测
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            if gpu_count > 0:
                gpu_ids = ','.join(str(i) for i in range(gpu_count))
                return gpu_count, gpu_ids
    except ImportError:
        pass

    # 尝试使用 nvidia-smi 检测
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            gpu_ids = [x.strip() for x in result.stdout.strip().split('\n') if x.strip()]
            if gpu_ids:
                return len(gpu_ids), ','.join(gpu_ids)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 默认单卡
    return 1, '0'


# 启动时检测 GPU 并缓存结果
_GPU_COUNT, _CUDA_VISIBLE_DEVICES = detect_gpus()
print(f"[train_service] 检测到 {_GPU_COUNT} 个 GPU, CUDA_VISIBLE_DEVICES={_CUDA_VISIBLE_DEVICES}")

class TrainService:
    """训练服务类"""

    def __init__(self):
        self.running_processes: Dict[str, subprocess.Popen] = {}

    def resolve_model_path(self, model_id: str) -> str:
        """
        解析模型路径

        如果模型在本地存在（/app/models/{model_id}），返回完整路径
        否则返回 model_id，让 ms-swift 从 ModelScope 下载

        Args:
            model_id: 模型ID（如 Qwen/Qwen2.5-0.6B-Instruct）

        Returns:
            str: 模型路径或ID
        """
        # 如果已经是绝对路径，直接返回
        if Path(model_id).is_absolute():
            return model_id

        # 检查本地模型目录
        local_model_path = MODEL_DIR / model_id
        if local_model_path.exists() and (local_model_path / "config.json").exists():
            print(f"[resolve_model_path] 使用本地模型: {local_model_path}")
            return str(local_model_path)

        # 本地不存在，返回 model_id（ms-swift 会自动下载）
        print(f"[resolve_model_path] 本地模型不存在，将从 ModelScope 下载: {model_id}")
        return model_id

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
        # 解析模型路径（优先使用本地模型）
        model_id = config.get('model_id', 'Qwen/Qwen2.5-7B-Instruct')
        model_path = self.resolve_model_path(model_id)

        # 解析数据集路径（支持多个数据集）
        datasets_config = config.get('datasets', [])
        if not datasets_config:
            raise ValueError("至少需要指定一个数据集")

        dataset_args = []
        for ds in datasets_config:
            # 解析数据集路径
            dataset_name = ds.get('name') if isinstance(ds, dict) else ds
            dataset_path = self.resolve_dataset_path(dataset_name)

            # 添加采样数量（如果指定）
            sample_count = ds.get('sample_count') if isinstance(ds, dict) else None
            if sample_count and sample_count > 0:
                dataset_args.append(f"{dataset_path}#{sample_count}")
            else:
                dataset_args.append(dataset_path)

        # 输出目录
        output_dir = OUTPUT_DIR / task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # 基础命令
        cmd = [
            "swift", "sft",
            "--model", model_path,
            "--output_dir", str(output_dir),
        ]

        # 添加多个数据集参数
        cmd.append("--dataset")
        cmd.extend(dataset_args)

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

        # ========== 性能优化参数 ==========

        # Attention 实现方式（默认使用 flash_attn 提升性能）
        # 可选: 'sdpa', 'eager', 'flash_attn', 'flash_attention_2', 'flash_attention_3'
        attn_impl = config.get('attn_impl', 'flash_attn')
        cmd.extend(["--attn_impl", attn_impl])

        # DeepSpeed 配置（默认使用 zero3 支持大模型训练）
        # 可选: 'zero0', 'zero1', 'zero2', 'zero3', 'zero2_offload', 'zero3_offload'
        # 也可以传入自定义 deepspeed 配置文件路径
        deepspeed = config.get('deepspeed', 'zero3')
        cmd.extend(["--deepspeed", deepspeed])

        # Gradient Checkpointing（默认已开启，可以显著降低显存）
        gradient_checkpointing = config.get('gradient_checkpointing')
        if gradient_checkpointing is not None:
            cmd.extend(["--gradient_checkpointing", str(gradient_checkpointing).lower()])

        # Padding Free（降低显存占用，需配合 flash_attn 使用）
        padding_free = config.get('padding_free')
        if padding_free:
            cmd.extend(["--padding_free", "true"])

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

            # 构建训练环境变量（自动检测 GPU 并设置分布式训练）
            train_env = {
                **os.environ,
                'PYTHONUNBUFFERED': '1',
                'CUDA_VISIBLE_DEVICES': _CUDA_VISIBLE_DEVICES,
                'NPROC_PER_NODE': str(_GPU_COUNT),
            }

            # 记录命令和环境
            cmd_str = " ".join(cmd)
            await self._send_log_to_websocket(
                task_id,
                f"[开始训练] GPU: {_GPU_COUNT} 个 (CUDA_VISIBLE_DEVICES={_CUDA_VISIBLE_DEVICES})\n"
                f"[开始训练] 命令: {cmd_str}\n"
            )

            # 启动训练进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=train_env
            )

            # 保存进程引用
            self.running_processes[task_id] = process

            # 实时读取日志（异步方式）
            total_epochs = config.get('num_train_epochs', 1)

            # 使用异步方式读取进程输出
            loop = asyncio.get_event_loop()

            # 步数计数器（用于 loss 历史记录）
            step_counter = 0

            async def read_stream():
                """异步读取进程输出流"""
                nonlocal step_counter

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
                        # 如果有 loss 数据，添加到 loss_history
                        if 'loss' in progress_info:
                            step_counter += 1
                            task = get_task(task_id)
                            if task:
                                if 'loss_history' not in task:
                                    task['loss_history'] = []

                                # 添加 loss 历史记录
                                loss_record = {
                                    'step': step_counter,
                                    'loss': progress_info['loss'],
                                    'epoch': progress_info.get('current_epoch', 0),
                                }
                                task['loss_history'].append(loss_record)

                                # 限制历史记录数量（最多保留 1000 个点）
                                if len(task['loss_history']) > 1000:
                                    task['loss_history'] = task['loss_history'][-1000:]

                        # 更新任务状态
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

            # 检查任务当前状态（可能已被手动停止）
            task = get_task(task_id)
            if task and task.get('status') == 'stopped':
                # 任务已被手动停止，不要覆盖状态
                await self._send_log_to_websocket(task_id, "\n[训练已停止] 进程已终止")
                return

            if return_code == 0:
                # 训练成功
                update_task(task_id, {
                    "status": "completed",
                    "progress": 100
                })
                await self._send_log_to_websocket(task_id, "\n[训练完成] 🎉")
            else:
                # 训练失败或被信号终止
                # 检查是否是被信号终止（SIGTERM=-15, SIGKILL=-9）
                if return_code in [-15, -9, 143]:  # 143 = 128 + 15 (Docker 中的 SIGTERM)
                    # 可能是被停止，但状态未及时更新，设置为 stopped
                    update_task(task_id, {"status": "stopped"})
                    await self._send_log_to_websocket(task_id, "\n[训练已停止] 进程被终止信号中断")
                else:
                    # 其他退出码视为失败
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
        result = {}

        # 1. 优先解析 tqdm 进度条（格式：Train: 91% █████████▏  1600/1700）
        # 这样可以让进度条与日志中显示的百分比一致
        tqdm_pattern = r'Train:\s*(\d+)%.*?(\d+)/(\d+)'
        tqdm_match = re.search(tqdm_pattern, log_line)
        if tqdm_match:
            step_percent = int(tqdm_match.group(1))
            current_step = int(tqdm_match.group(2))
            total_steps = int(tqdm_match.group(3))

            # 使用 tqdm 显示的百分比作为主进度
            result['progress'] = float(step_percent)
            result['current_step'] = current_step
            result['total_steps'] = total_steps

        # 2. 解析 trainer 输出的 JSON 信息（loss, epoch, learning_rate）
        try:
            if '{' in log_line and '}' in log_line:
                # 提取 JSON 部分
                json_start = log_line.index('{')
                json_end = log_line.rindex('}') + 1
                json_str = log_line[json_start:json_end]

                # 解析 JSON（需要处理单引号）
                json_str = json_str.replace("'", '"')
                data = json.loads(json_str)

                # 提取 loss
                if 'loss' in data:
                    result['loss'] = float(data['loss'])

                # 提取 epoch（用于显示当前轮次，但不用于计算主进度）
                if 'epoch' in data:
                    current_epoch = float(data['epoch'])
                    result['current_epoch'] = current_epoch

                    # 只有在没有 tqdm 进度时，才使用 epoch 计算进度
                    if 'progress' not in result:
                        result['progress'] = (current_epoch / total_epochs) * 100

                # 提取学习率
                if 'learning_rate' in data:
                    result['learning_rate'] = float(data['learning_rate'])

        except (ValueError, KeyError, json.JSONDecodeError):
            pass

        return result if result else None

    async def _send_log_to_websocket(self, task_id: str, message: str):
        """
        发送日志：保存到任务存储 + 推送到 WebSocket

        Args:
            task_id: 任务 ID
            message: 日志消息
        """
        from api.train import get_task, update_task

        # 1. 保存日志到任务存储（持久化）
        task = get_task(task_id)
        if task:
            if 'logs' not in task:
                task['logs'] = []
            task['logs'].append(message)
            # 限制日志数量，避免内存溢出（最多保留最近 10000 条）
            if len(task['logs']) > 10000:
                task['logs'] = task['logs'][-10000:]

        # 2. 通过 WebSocket 实时推送（如果有连接）
        try:
            from app import manager
            await manager.send_message(message, task_id)
        except Exception:
            # WebSocket 推送失败不影响日志保存
            # ConnectionManager 已经自动处理连接清理，无需打印错误
            pass

    def stop_training(self, task_id: str) -> bool:
        """
        停止训练任务（杀死进程树，释放 GPU 显存）

        Args:
            task_id: 任务 ID

        Returns:
            bool: 是否成功停止
        """
        if task_id in self.running_processes:
            process = self.running_processes[task_id]
            try:
                print(f"[stop_training] 正在停止任务 {task_id}, PID={process.pid}")

                # 杀死进程树（包括所有子进程）
                # 这对于 swift sft 很重要，因为它可能启动多个子进程
                import psutil
                try:
                    parent = psutil.Process(process.pid)
                    children = parent.children(recursive=True)

                    # 先发送 SIGTERM 给所有进程（优雅退出）
                    print(f"[stop_training] 发现 {len(children)} 个子进程")
                    for child in children:
                        try:
                            print(f"[stop_training] 终止子进程 PID={child.pid}")
                            child.terminate()
                        except psutil.NoSuchProcess:
                            pass

                    parent.terminate()

                    # 等待最多 10 秒
                    gone, alive = psutil.wait_procs(children + [parent], timeout=10)

                    # 强制杀死仍然存活的进程
                    for p in alive:
                        try:
                            print(f"[stop_training] 强制杀死进程 PID={p.pid}")
                            p.kill()
                        except psutil.NoSuchProcess:
                            pass

                    print(f"[stop_training] 成功停止任务 {task_id}")

                except psutil.NoSuchProcess:
                    print(f"[stop_training] 进程 {process.pid} 已不存在")
                except Exception as e:
                    print(f"[stop_training] psutil 方法失败，使用 fallback: {e}")
                    # Fallback: 使用原来的方法
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

                # 清理进程引用
                del self.running_processes[task_id]
                return True

            except Exception as e:
                print(f"[stop_training] 停止训练失败 {task_id}: {e}")
                return False

        print(f"[stop_training] 任务 {task_id} 不在运行进程列表中")
        return False

    def get_running_tasks(self) -> list:
        """
        获取所有正在运行的任务 ID

        Returns:
            list: 任务 ID 列表
        """
        return list(self.running_processes.keys())
