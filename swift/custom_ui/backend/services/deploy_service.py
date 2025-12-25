"""
部署服务 - 使用 vllm serve 直接启动推理后端
通过 vllm serve 命令启动 OpenAI 兼容的推理服务器
"""
import subprocess
import asyncio
import time
import json
import logging
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import requests
import signal

logger = logging.getLogger(__name__)

# 部署输出目录
DEPLOY_DIR = Path("/app/deployments")
DEPLOY_DIR.mkdir(parents=True, exist_ok=True)

# 模型目录
MODEL_DIR = Path("/app/models")
OUTPUT_DIR = Path("/app/output")  # 训练输出目录


class DeployService:
    """部署服务类 - 管理 vllm 推理服务器"""

    def __init__(self):
        self.running_deployments: Dict[str, Dict[str, Any]] = {}
        self.base_port = 8000  # vllm 默认端口
        self.monitor_tasks: Dict[str, asyncio.Task] = {}  # 后台监控任务
        self.available_gpus = self._get_available_gpus()  # 可用 GPU 列表
        print(f"[INFO][GPU] 检测到可用 GPU: {self.available_gpus}")

    def _get_available_gpus(self) -> List[str]:
        """
        获取可用 GPU 列表（从 CUDA_VISIBLE_DEVICES 读取）

        Returns:
            list: GPU ID 列表（如 ['0', '1', '2', '3']）
        """
        cuda_visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "0")
        print(f"[DEBUG][GPU] CUDA_VISIBLE_DEVICES: {cuda_visible_devices}")

        # 解析 CUDA_VISIBLE_DEVICES（支持 "0,1,2,3" 或 "0" 格式）
        if cuda_visible_devices:
            gpu_ids = [gpu.strip() for gpu in cuda_visible_devices.split(",")]
            return gpu_ids
        else:
            # 默认使用 GPU 0
            return ["0"]

    def _get_used_gpus(self) -> set:
        """
        获取已被占用的 GPU ID 集合

        Returns:
            set: 已占用的 GPU ID 集合（如 {'0', '1'}）
        """
        used_gpus = set()
        for deployment in self.running_deployments.values():
            # 只统计运行中或启动中的部署
            if deployment.get("status") in ["starting", "running"]:
                gpu_devices = deployment.get("gpu_devices", "")
                if gpu_devices:
                    # 支持单卡（"0"）和多卡（"0,1"）
                    for gpu_id in gpu_devices.split(","):
                        used_gpus.add(gpu_id.strip())
        return used_gpus

    def _allocate_gpu(self, preferred_gpu: Optional[str] = None) -> Optional[str]:
        """
        分配 GPU（自动选择空闲 GPU 或使用指定 GPU）

        Args:
            preferred_gpu: 优先使用的 GPU ID（可选）

        Returns:
            str: 分配的 GPU ID，如果无可用 GPU 则返回 None
        """
        # 如果指定了 GPU，检查是否可用
        if preferred_gpu is not None:
            if preferred_gpu not in self.available_gpus:
                print(f"[WARNING][GPU] 指定的 GPU {preferred_gpu} 不在可用列表中: {self.available_gpus}")
                return None

            used_gpus = self._get_used_gpus()
            if preferred_gpu in used_gpus:
                print(f"[WARNING][GPU] 指定的 GPU {preferred_gpu} 已被占用")
                return None

            print(f"[INFO][GPU] 使用指定 GPU: {preferred_gpu}")
            return preferred_gpu

        # 自动分配：选择第一个空闲 GPU
        used_gpus = self._get_used_gpus()
        for gpu_id in self.available_gpus:
            if gpu_id not in used_gpus:
                print(f"[INFO][GPU] 自动分配 GPU: {gpu_id}")
                return gpu_id

        # 无可用 GPU
        print(f"[WARNING][GPU] 所有 GPU 已被占用: {used_gpus}")
        return None

    def get_gpu_status(self) -> Dict[str, Any]:
        """
        获取 GPU 使用状态

        Returns:
            dict: GPU 状态信息
        """
        used_gpus = self._get_used_gpus()
        gpu_status = []

        for gpu_id in self.available_gpus:
            status = {
                "gpu_id": gpu_id,
                "status": "used" if gpu_id in used_gpus else "available",
                "deployments": []
            }

            # 查找使用该 GPU 的部署
            for deployment in self.running_deployments.values():
                if deployment.get("status") in ["starting", "running"]:
                    gpu_devices = deployment.get("gpu_devices", "")
                    if gpu_id in gpu_devices.split(","):
                        status["deployments"].append({
                            "deployment_id": deployment["deployment_id"],
                            "model": deployment["model_path"],
                            "status": deployment["status"]
                        })

            gpu_status.append(status)

        return {
            "total_gpus": len(self.available_gpus),
            "used_gpus": len(used_gpus),
            "available_gpus": len(self.available_gpus) - len(used_gpus),
            "gpus": gpu_status
        }

    def resolve_model_path(self, model_id: str) -> str:
        """
        验证模型路径

        前端传入的 model_id 已经是绝对路径（由 model_service 扫描返回）：
        - /app/models/Qwen/Qwen2.5-7B-Instruct（本地模型）
        - /app/output/xxx/v0-xxx/checkpoint-1（训练输出）

        Args:
            model_id: 模型绝对路径

        Returns:
            str: 验证后的模型路径

        Raises:
            ValueError: 路径不存在或格式错误
        """
        model_path = Path(model_id)

        # 验证：必须是绝对路径
        if not model_path.is_absolute():
            raise ValueError(
                f"模型路径必须是绝对路径，收到: {model_id}\n"
                f"请从模型列表中选择模型"
            )

        # 验证：路径必须存在
        if not model_path.exists():
            raise ValueError(f"模型路径不存在: {model_id}")

        # 验证：必须包含模型配置文件
        has_config = (model_path / "config.json").exists()
        has_adapter_config = (model_path / "adapter_config.json").exists()

        if not has_config and not has_adapter_config:
            raise ValueError(
                f"无效的模型目录（缺少 config.json 或 adapter_config.json）: {model_id}"
            )

        print(f"[DEBUG][resolve_model_path] ✓ 模型路径验证通过: {model_id}")
        return str(model_path)

    def _get_next_port(self) -> int:
        """获取下一个可用端口"""
        used_ports = {
            dep['port'] for dep in self.running_deployments.values()
        }
        port = self.base_port
        while port in used_ports:
            port += 1
        return port

    async def start_deployment(
        self,
        deployment_id: str,
        model_path: str,
        adapter_path: Optional[str] = None,
        served_model_name: Optional[str] = None,
        host: str = "0.0.0.0",
        port: Optional[int] = None,
        gpu_devices: Optional[str] = None,  # 改为可选，None 表示自动分配
        max_model_len: Optional[int] = None,
        gpu_memory_utilization: Optional[float] = 0.9,
        tensor_parallel_size: Optional[int] = None,
        quantization: Optional[str] = None,
        dtype: str = "auto",
        trust_remote_code: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        启动部署服务 (使用 vllm serve)

        Args:
            deployment_id: 部署 ID
            model_path: 模型路径（本地路径）
            adapter_path: Adapter 路径（可选，如 LoRA adapter）
            served_model_name: 服务模型名称（用于 OpenAI API，可多个）
            host: 服务 Host（默认 0.0.0.0）
            port: 服务端口（默认自动分配，默认 8000）
            gpu_devices: GPU 设备 ID（可选，None=自动分配，"0"=指定 GPU 0）
            max_model_len: 最大模型长度/上下文长度（可选）
            gpu_memory_utilization: GPU 内存利用率（默认 0.9）
            tensor_parallel_size: 张量并行大小（可选，多卡推理）
            quantization: 量化方法（如 awq, gptq, sqeeze_llm 等）
            dtype: 数据类型（auto, half, float16, bfloat16, float, float32）
            trust_remote_code: 是否信任远程代码（默认 False）
            **kwargs: 其他 vllm serve 参数

        Returns:
            dict: 部署信息
        """
        # 参数验证
        print(f"[DEBUG] 开始部署验证 - deployment_id: {deployment_id}")
        print(f"[DEBUG] 参数检查 - model_path: {model_path}, adapter_path: {adapter_path}")
        print(f"[DEBUG] 参数检查 - port: {port}, max_model_len: {max_model_len}")
        print(f"[DEBUG] 参数检查 - gpu_devices: {gpu_devices} (None=自动分配)")
        print(f"[DEBUG] 参数检查 - gpu_memory_utilization: {gpu_memory_utilization}")

        if deployment_id in self.running_deployments:
            raise ValueError(f"部署 {deployment_id} 已存在")

        if not model_path or not model_path.strip():
            raise ValueError("model_path 不能为空")

        # GPU 自动分配
        if gpu_devices is None:
            # 自动分配空闲 GPU
            allocated_gpu = self._allocate_gpu()
            if allocated_gpu is None:
                raise RuntimeError(
                    f"无可用 GPU，所有 GPU 已被占用。"
                    f"可用 GPU: {self.available_gpus}，"
                    f"已占用: {self._get_used_gpus()}"
                )
            gpu_devices = allocated_gpu
            print(f"[INFO][GPU] 自动分配 GPU: {gpu_devices}")
        else:
            # 用户指定 GPU，验证是否可用
            allocated_gpu = self._allocate_gpu(preferred_gpu=gpu_devices)
            if allocated_gpu is None:
                raise RuntimeError(
                    f"指定的 GPU {gpu_devices} 不可用。"
                    f"可用 GPU: {self.available_gpus}，"
                    f"已占用: {self._get_used_gpus()}"
                )
            print(f"[INFO][GPU] 使用指定 GPU: {gpu_devices}")

        # 解析模型路径（优先使用本地模型）
        print(f"[DEBUG] 开始解析模型路径: {model_path}")
        resolved_model_path = self.resolve_model_path(model_path)
        print(f"[DEBUG] ✓ 原始模型路径: {model_path}")
        print(f"[DEBUG] ✓ 解析后模型路径: {resolved_model_path}")

        # 分配端口
        if port is None:
            port = self._get_next_port()
            print(f"[DEBUG] 自动分配端口: {port}")
        else:
            print(f"[DEBUG] 使用指定端口: {port}")

        # 确定服务模型名称
        if served_model_name is None:
            served_model_name = Path(model_path).name
            print(f"[DEBUG] 自动生成 served_model_name: {served_model_name}")

        # 构建 vllm serve 命令
        # 参考：https://docs.vllm.ai/en/latest/configuration/serve_args.html
        # 格式：vllm serve <model_tag> [options]
        cmd = [
            "vllm", "serve",
            resolved_model_path,  # 位置参数：模型路径
        ]

        # 前端配置（Frontend）
        cmd.extend(["--host", host])
        cmd.extend(["--port", str(port)])

        # 服务模型名称（可以是多个，用空格分隔）
        if served_model_name:
            if isinstance(served_model_name, str):
                cmd.extend(["--served-model-name", served_model_name])
            elif isinstance(served_model_name, list):
                cmd.extend(["--served-model-name"] + served_model_name)

        # 模型配置（ModelConfig）
        if dtype:
            cmd.extend(["--dtype", dtype])

        if trust_remote_code:
            cmd.append("--trust-remote-code")

        if max_model_len is not None:
            cmd.extend(["--max-model-len", str(max_model_len)])

        if quantization:
            cmd.extend(["--quantization", quantization])

        # 缓存配置（CacheConfig）
        if gpu_memory_utilization is not None:
            cmd.extend(["--gpu-memory-utilization", str(gpu_memory_utilization)])

        # 并行配置（ParallelConfig）
        if tensor_parallel_size is not None:
            cmd.extend(["--tensor-parallel-size", str(tensor_parallel_size)])

        # LoRA 配置（如果有 adapter）
        if adapter_path and adapter_path.strip():
            cmd.append("--enable-lora")
            cmd.extend(["--lora-modules", f"{deployment_id}={adapter_path}"])

        # 其他可选参数（通过 kwargs 传入）
        # 支持的参数参考 vllm serve --help
        for key, value in kwargs.items():
            if value is not None and value != "":
                # 将下划线转换为连字符（vllm 使用连字符）
                param_name = key.replace("_", "-")
                if isinstance(value, bool):
                    if value:
                        cmd.append(f"--{param_name}")
                else:
                    cmd.extend([f"--{param_name}", str(value)])

        # 日志文件
        log_file = DEPLOY_DIR / f"{deployment_id}.log"

        print(f"[DEBUG] 启动部署: {deployment_id}")
        print(f"[DEBUG] 完整命令: {' '.join(cmd)}")
        print(f"[DEBUG] 端口: {port}")
        print(f"[DEBUG] GPU 设备: {gpu_devices}")
        print(f"[DEBUG] 日志文件: {log_file}")

        # 启动进程
        try:
            env = {
                **subprocess.os.environ,
                "CUDA_VISIBLE_DEVICES": gpu_devices,
            }

            print(f"[DEBUG] 环境变量 CUDA_VISIBLE_DEVICES: {gpu_devices}")

            with open(log_file, "w") as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    preexec_fn=subprocess.os.setsid if hasattr(subprocess.os, 'setsid') else None
                )

            print(f"[DEBUG] ✓ 进程已启动，PID: {process.pid}")

        except Exception as e:
            print(f"[ERROR] 启动进程失败: {e}")
            import traceback
            print(f"[ERROR] 详细堆栈:\n{traceback.format_exc()}")
            raise RuntimeError(f"无法启动部署进程: {str(e)}")

        # 立即保存部署信息（状态为 "starting"）
        deployment_info = {
            "deployment_id": deployment_id,
            "model_path": resolved_model_path,  # 保存解析后的路径
            "served_model_name": served_model_name,
            "port": port,
            "gpu_devices": gpu_devices,
            "process": process,
            "pid": process.pid,
            "log_file": str(log_file),
            "base_url": f"http://localhost:{port}",
            "api_endpoint": f"http://localhost:{port}/v1/chat/completions",
            "status": "starting",  # 初始状态为 starting
            "started_at": time.time(),
        }

        self.running_deployments[deployment_id] = deployment_info

        # 启动后台监控任务（包含启动检查和持续监控）
        monitor_task = asyncio.create_task(
            self._monitor_deployment_with_startup(deployment_id, port)
        )
        self.monitor_tasks[deployment_id] = monitor_task
        print(f"[DEBUG] ✓ 后台监控任务已启动: {deployment_id}")

        return {
            k: v for k, v in deployment_info.items()
            if k != "process"  # 不返回进程对象
        }

    async def _monitor_deployment_with_startup(self, deployment_id: str, port: int):
        """
        后台监控部署（包含启动检查）

        Args:
            deployment_id: 部署 ID
            port: 服务端口
        """
        print(f"[DEBUG][Monitor] 开始监控部署启动: {deployment_id}")

        if deployment_id not in self.running_deployments:
            print(f"[ERROR][Monitor] 部署 {deployment_id} 不存在")
            return

        deployment = self.running_deployments[deployment_id]
        process = deployment["process"]
        log_file = Path(deployment["log_file"])

        # 1. 等待服务启动（最多 5 分钟）
        max_startup_time = 300  # 5 分钟
        health_url = f"http://localhost:{port}/health"

        print(f"[DEBUG][Monitor] 等待服务启动: {health_url}")
        print(f"[DEBUG][Monitor] 最大等待时间: {max_startup_time} 秒")

        startup_success = False
        for i in range(max_startup_time):
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    print(f"[INFO][Monitor] ✓ 部署 {deployment_id} 启动成功（用时 {i+1} 秒）")
                    deployment["status"] = "running"
                    startup_success = True
                    break
            except requests.RequestException:
                pass

            # 每 10 秒打印一次进度
            if (i + 1) % 10 == 0:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"[ERROR][Monitor] 进程在启动时退出（退出码: {exit_code}）")
                    deployment["status"] = "failed"
                    deployment["exit_code"] = exit_code

                    # 读取日志
                    if log_file.exists():
                        with open(log_file, "r") as f:
                            logs = f.read()
                        print(f"[ERROR][Monitor] 最后 200 字符日志:\n{logs[-200:]}")

                    return
                else:
                    print(f"[DEBUG][Monitor] 等待中... {i+1}/{max_startup_time} 秒（进程运行中）")

            await asyncio.sleep(1)

        if not startup_success:
            print(f"[ERROR][Monitor] 部署启动超时（{max_startup_time} 秒）")
            deployment["status"] = "timeout"
            # 杀死进程
            try:
                process.kill()
                process.wait()
            except:
                pass
            return

        # 2. 持续监控服务状态（已启动成功）
        print(f"[DEBUG][Monitor] 开始持续监控: {deployment_id}")
        await self._monitor_deployment(deployment_id)

    async def _monitor_deployment(self, deployment_id: str):
        """
        后台监控部署状态（持续运行，直到部署停止或失败）

        Args:
            deployment_id: 部署 ID
        """
        print(f"[DEBUG][Monitor] 开始监控部署: {deployment_id}")

        while deployment_id in self.running_deployments:
            try:
                deployment = self.running_deployments[deployment_id]
                process = deployment["process"]

                # 1. 检查进程是否退出
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"[WARNING][Monitor] 部署 {deployment_id} 进程已退出（退出码: {exit_code}）")
                    deployment["status"] = "failed"
                    deployment["exit_code"] = exit_code
                    deployment["stopped_at"] = time.time()
                    break

                # 2. 检查服务健康状态
                try:
                    health_url = f"{deployment['base_url']}/health"
                    response = requests.get(health_url, timeout=2)

                    if response.status_code == 200:
                        # 服务健康
                        if deployment["status"] != "running":
                            print(f"[INFO][Monitor] 部署 {deployment_id} 恢复健康")
                            deployment["status"] = "running"
                    else:
                        # 服务不健康
                        print(f"[WARNING][Monitor] 部署 {deployment_id} 健康检查失败: {response.status_code}")
                        deployment["status"] = "unhealthy"
                except requests.RequestException as e:
                    # 健康检查失败（可能是服务正在重启或负载过高）
                    if deployment["status"] == "running":
                        print(f"[WARNING][Monitor] 部署 {deployment_id} 健康检查异常: {e}")
                        deployment["status"] = "unhealthy"

                # 每 10 秒检查一次
                await asyncio.sleep(10)

            except Exception as e:
                print(f"[ERROR][Monitor] 监控部署 {deployment_id} 出错: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(10)

        print(f"[DEBUG][Monitor] 停止监控部署: {deployment_id}")

    def stop_deployment(self, deployment_id: str):
        """
        停止部署服务

        Args:
            deployment_id: 部署 ID
        """
        if deployment_id not in self.running_deployments:
            raise ValueError(f"部署 {deployment_id} 不存在")

        deployment = self.running_deployments[deployment_id]
        process = deployment["process"]

        print(f"[DEBUG] 停止部署: {deployment_id} (PID: {process.pid})")

        # 1. 取消监控任务
        if deployment_id in self.monitor_tasks:
            monitor_task = self.monitor_tasks[deployment_id]
            if not monitor_task.done():
                monitor_task.cancel()
                print(f"[DEBUG] ✓ 已取消监控任务: {deployment_id}")
            del self.monitor_tasks[deployment_id]

        # 2. 优雅关闭进程
        try:
            # 发送 SIGTERM
            if hasattr(subprocess.os, 'killpg'):
                subprocess.os.killpg(subprocess.os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()

            # 等待进程结束（最多 10 秒）
            try:
                process.wait(timeout=10)
                print(f"[DEBUG] ✓ 部署 {deployment_id} 已停止")
            except subprocess.TimeoutExpired:
                print(f"[WARNING] 部署 {deployment_id} 未在 10 秒内停止，强制杀死")
                # 强制杀死
                if hasattr(subprocess.os, 'killpg'):
                    subprocess.os.killpg(subprocess.os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                process.wait()

        except Exception as e:
            print(f"[ERROR] 停止部署失败: {e}")
            # 强制杀死
            try:
                process.kill()
                process.wait()
            except:
                pass

        # 3. 更新部署状态
        deployment["status"] = "stopped"
        deployment["stopped_at"] = time.time()

        # 从运行列表中删除
        del self.running_deployments[deployment_id]

    def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        获取部署状态（由后台监控任务持续更新）

        Args:
            deployment_id: 部署 ID

        Returns:
            dict: 部署状态信息
        """
        if deployment_id not in self.running_deployments:
            return {
                "deployment_id": deployment_id,
                "status": "not_found",
            }

        deployment = self.running_deployments[deployment_id]

        # 状态由后台监控任务更新，直接返回当前状态
        status_info = {
            "deployment_id": deployment_id,
            "model_path": deployment["model_path"],
            "served_model_name": deployment["served_model_name"],
            "port": deployment["port"],
            "base_url": deployment["base_url"],
            "api_endpoint": deployment["api_endpoint"],
            "status": deployment.get("status", "unknown"),
            "pid": deployment["pid"],
            "gpu_id": deployment.get("gpu_devices", "N/A"),  # 前端显示用
            "uptime_seconds": time.time() - deployment["started_at"],
        }

        # 如果有退出码，添加到状态信息
        if "exit_code" in deployment:
            status_info["exit_code"] = deployment["exit_code"]

        # 如果已停止，添加停止时间
        if "stopped_at" in deployment:
            status_info["stopped_at"] = deployment["stopped_at"]

        return status_info

    def list_deployments(self) -> list:
        """
        列出所有部署

        Returns:
            list: 部署列表
        """
        deployments = []
        for deployment_id in list(self.running_deployments.keys()):
            try:
                status = self.get_deployment_status(deployment_id)
                deployments.append(status)
            except Exception as e:
                print(f"[ERROR] 获取部署状态失败: {deployment_id}, {e}")
                continue

        return deployments

    def get_deployment_logs(self, deployment_id: str, lines: int = 100) -> str:
        """
        获取部署日志

        Args:
            deployment_id: 部署 ID
            lines: 读取的行数

        Returns:
            str: 日志内容
        """
        if deployment_id not in self.running_deployments:
            raise ValueError(f"部署 {deployment_id} 不存在")

        log_file = Path(self.running_deployments[deployment_id]["log_file"])

        if not log_file.exists():
            return ""

        # 读取最后 N 行
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return "".join(all_lines[-lines:])

    def delete_deployment(self, deployment_id: str, remove_logs: bool = False):
        """
        删除部署（如果正在运行则先停止）

        Args:
            deployment_id: 部署 ID
            remove_logs: 是否删除日志文件（默认 False，保留日志）

        Raises:
            ValueError: 部署不存在
        """
        if deployment_id not in self.running_deployments:
            raise ValueError(f"部署 {deployment_id} 不存在")

        deployment = self.running_deployments[deployment_id]
        status = deployment.get("status", "unknown")

        print(f"[DEBUG] 删除部署: {deployment_id} (状态: {status})")

        # 1. 如果部署正在运行或启动中，先停止
        if status in ["starting", "running", "unhealthy"]:
            print(f"[DEBUG] 部署 {deployment_id} 正在运行，先停止...")
            try:
                self.stop_deployment(deployment_id)
                print(f"[DEBUG] ✓ 部署 {deployment_id} 已停止")
            except Exception as e:
                print(f"[WARNING] 停止部署失败，继续删除: {e}")
        else:
            # 2. 如果部署已失败或超时，只需取消监控任务
            if deployment_id in self.monitor_tasks:
                monitor_task = self.monitor_tasks[deployment_id]
                if not monitor_task.done():
                    monitor_task.cancel()
                    print(f"[DEBUG] ✓ 已取消监控任务: {deployment_id}")
                del self.monitor_tasks[deployment_id]

        # 3. 删除日志文件（可选）
        if remove_logs:
            log_file = Path(deployment.get("log_file", ""))
            if log_file.exists():
                try:
                    log_file.unlink()
                    print(f"[DEBUG] ✓ 已删除日志文件: {log_file}")
                except Exception as e:
                    print(f"[WARNING] 删除日志文件失败: {e}")

        # 4. 从运行列表中移除
        if deployment_id in self.running_deployments:
            del self.running_deployments[deployment_id]
            print(f"[DEBUG] ✓ 部署 {deployment_id} 已从列表中移除")


# 全局实例
deploy_service = DeployService()
