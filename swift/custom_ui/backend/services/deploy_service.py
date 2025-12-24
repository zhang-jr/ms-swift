"""
部署服务 - 使用 vllm 作为推理后端
通过 swift deploy 命令启动 OpenAI 兼容的推理服务器
"""
import subprocess
import asyncio
import time
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import requests
import signal

logger = logging.getLogger(__name__)

# 部署输出目录
DEPLOY_DIR = Path("/app/deployments")
DEPLOY_DIR.mkdir(parents=True, exist_ok=True)

# 模型目录
MODEL_DIR = Path("/app/models")


class DeployService:
    """部署服务类 - 管理 vllm 推理服务器"""

    def __init__(self):
        self.running_deployments: Dict[str, Dict[str, Any]] = {}
        self.base_port = 8000  # vllm 默认端口
        self.monitor_tasks: Dict[str, asyncio.Task] = {}  # 后台监控任务

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
            print(f"[DEBUG][resolve_model_path] 已经是绝对路径: {model_id}")
            return model_id

        # 检查本地模型目录
        local_model_path = MODEL_DIR / model_id
        print(f"[DEBUG][resolve_model_path] 检查本地路径: {local_model_path}")
        print(f"[DEBUG][resolve_model_path] 路径存在: {local_model_path.exists()}")

        if local_model_path.exists():
            config_exists = (local_model_path / "config.json").exists()
            print(f"[DEBUG][resolve_model_path] config.json 存在: {config_exists}")

            if config_exists:
                print(f"[DEBUG][resolve_model_path] ✓ 使用本地模型: {local_model_path}")
                return str(local_model_path)

        # 本地不存在，返回 model_id（ms-swift 会自动下载）
        print(f"[DEBUG][resolve_model_path] 本地模型不存在，将从 ModelScope 下载: {model_id}")
        return model_id

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
        gpu_devices: str = "0",
        max_model_len: Optional[int] = None,
        use_vllm: bool = True,
        gpu_memory_utilization: Optional[float] = 0.9,
        quantization_bit: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        启动部署服务 (使用 vllm 后端)

        Args:
            deployment_id: 部署 ID
            model_path: 模型路径（本地路径或 HuggingFace 模型名称）
            adapter_path: Adapter 路径（可选，如 LoRA adapter）
            served_model_name: 服务模型名称（用于 OpenAI API）
            host: 服务 Host（默认 0.0.0.0）
            port: 服务端口（默认自动分配）
            gpu_devices: GPU 设备 ID（如 "0" 或 "0,1"）
            max_model_len: 最大模型长度（可选）
            use_vllm: 是否使用 vLLM 后端（默认 True）
            gpu_memory_utilization: GPU 内存利用率（默认 0.9）
            quantization_bit: 量化位数（可选）
            **kwargs: 其他参数

        Returns:
            dict: 部署信息
        """
        # 参数验证
        print(f"[DEBUG] 开始部署验证 - deployment_id: {deployment_id}")
        print(f"[DEBUG] 参数检查 - model_path: {model_path}, adapter_path: {adapter_path}")
        print(f"[DEBUG] 参数检查 - use_vllm: {use_vllm}, port: {port}, max_model_len: {max_model_len}")

        if deployment_id in self.running_deployments:
            raise ValueError(f"部署 {deployment_id} 已存在")

        if not model_path or not model_path.strip():
            raise ValueError("model_path 不能为空")

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

        # 构建 swift deploy 命令（参考官方文档和源代码）
        # 参考：DeployArguments 类接受的参数
        # 官方示例：swift deploy --model MODEL --infer_backend vllm --max_new_tokens 2048 --served_model_name NAME
        cmd = [
            "swift", "deploy",
            "--model", resolved_model_path,  # 使用解析后的路径
            "--infer_backend", "vllm" if use_vllm else "pt",
            "--served_model_name", served_model_name,
        ]

        # 端口（swift deploy 会自动调用 find_free_port，所以只在指定时添加）
        if port is not None:
            cmd.extend(["--port", str(port)])

        # 添加 max_new_tokens（默认 2048，这是生成的最大 token 数）
        max_new_tokens = kwargs.get("max_new_tokens", 2048)
        cmd.extend(["--max_new_tokens", str(max_new_tokens)])

        # Adapter 路径（确保不是 None 或空字符串）
        if adapter_path and adapter_path.strip():
            cmd.extend(["--adapters", adapter_path])

        # vLLM 特定参数（谨慎添加，可能不被所有版本支持）
        # if gpu_memory_utilization is not None and use_vllm:
        #     cmd.extend(["--gpu_memory_utilization", str(gpu_memory_utilization)])

        # if quantization_bit:
        #     cmd.extend(["--quantization_bit", str(quantization_bit)])

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


# 全局实例
deploy_service = DeployService()
