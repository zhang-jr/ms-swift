# Copyright (c) Alibaba, Inc. and its affiliates.
"""
部署服务层
处理模型部署相关的业务逻辑
"""
import os
import sys
import uuid
import socket
import asyncio
import httpx
from copy import deepcopy
from datetime import datetime
from subprocess import Popen, STDOUT
from typing import Dict, List, Optional, Any

from swift.utils import get_logger

logger = get_logger()


class DeployService:
    """部署服务类"""

    def __init__(self):
        # 存储所有部署
        self.deployments: Dict[str, Dict] = {}
        # 存储进程对象
        self.processes: Dict[str, Popen] = {}

    def is_port_in_use(self, port: int, host: str = "0.0.0.0") -> bool:
        """
        检查端口是否被占用

        Args:
            port: 端口号
            host: 主机地址

        Returns:
            in_use: 是否被占用
        """
        # 检查是否已经被当前服务占用
        for deployment in self.deployments.values():
            if deployment["port"] == port and deployment["status"] in ("starting", "running"):
                return True

        # 检查系统端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    def create_deployment(
        self,
        model: str,
        model_type: Optional[str] = None,
        template: Optional[str] = None,
        port: int = 8000,
        host: str = "0.0.0.0",
        gpu_id: Optional[List[str]] = None,
        ckpt_dir: Optional[str] = None,
        max_model_len: Optional[int] = None,
        max_batch_size: Optional[int] = None,
        served_model_name: Optional[str] = None,
        more_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建部署任务

        Args:
            model: 模型 ID 或路径
            其他参数同 DeployRequest

        Returns:
            deployment_id: 部署 ID
        """
        # 生成部署 ID
        deployment_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 输出目录
        output_dir = f"output/deploy_{deployment_id}_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)

        # 日志文件
        log_file = os.path.join(output_dir, "deploy.log")

        # 构建参数
        kwargs = {
            "model": model,
            "port": port,
            "host": host,
        }

        # 可选参数
        if model_type:
            kwargs["model_type"] = model_type
        if template:
            kwargs["template"] = template
        if ckpt_dir:
            kwargs["ckpt_dir"] = ckpt_dir
        if max_model_len:
            kwargs["max_model_len"] = max_model_len
        if max_batch_size:
            kwargs["max_batch_size"] = max_batch_size
        if served_model_name:
            kwargs["served_model_name"] = served_model_name
        if more_params:
            kwargs.update(more_params)

        # GPU 配置
        gpu_str = ",".join(gpu_id) if gpu_id else "0"

        # 保存部署信息
        self.deployments[deployment_id] = {
            "deployment_id": deployment_id,
            "model": model,
            "status": "pending",
            "kwargs": kwargs,
            "gpu_id": gpu_str,
            "port": port,
            "host": host,
            "log_file": log_file,
            "start_time": None,
            "endpoint": None
        }

        logger.info(f"Created deployment: {deployment_id}")
        return deployment_id

    def run_deployment(self, deployment_id: str):
        """
        运行部署服务(在后台进程中)

        Args:
            deployment_id: 部署 ID
        """
        if deployment_id not in self.deployments:
            logger.error(f"Deployment {deployment_id} not found")
            return

        deployment = self.deployments[deployment_id]
        deployment["status"] = "starting"
        deployment["start_time"] = datetime.now().isoformat()

        try:
            # 构建命令
            command = self._build_command(deployment)
            logger.info(f"Running deployment command: {' '.join(command)}")

            # 设置环境变量
            env = deepcopy(os.environ)
            if "cpu" not in deployment["gpu_id"]:
                env["CUDA_VISIBLE_DEVICES"] = deployment["gpu_id"]

            # 启动进程
            process = Popen(
                command,
                env=env,
                stdout=open(deployment["log_file"], "w"),
                stderr=STDOUT,
                cwd=os.getcwd()
            )

            self.processes[deployment_id] = process
            logger.info(f"Deployment process started: PID {process.pid}")

            # 更新状态为 running
            deployment["status"] = "running"
            deployment["endpoint"] = f"http://{deployment['host']}:{deployment['port']}"

            # 注意: 不要等待进程结束,让它在后台运行
            # process.wait() 会阻塞

        except Exception as e:
            logger.error(f"Deployment {deployment_id} failed: {e}")
            deployment["status"] = "failed"
            deployment["message"] = str(e)

    def _build_command(self, deployment: Dict) -> List[str]:
        """
        构建部署命令

        Args:
            deployment: 部署信息

        Returns:
            command: 命令列表
        """
        command = ["swift", "deploy"]
        kwargs = deployment["kwargs"]

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
            "--log_file", deployment["log_file"],
            "--ignore_args_error", "true"
        ])

        return command

    def get_deployment_status(self, deployment_id: str) -> Optional[Dict]:
        """
        获取部署状态

        Args:
            deployment_id: 部署 ID

        Returns:
            status: 部署状态信息
        """
        if deployment_id not in self.deployments:
            return None

        deployment = self.deployments[deployment_id]

        # 检查进程是否还在运行
        if deployment_id in self.processes:
            process = self.processes[deployment_id]
            if process.poll() is not None:
                # 进程已结束
                deployment["status"] = "stopped"
                del self.processes[deployment_id]

        return {
            "deployment_id": deployment_id,
            "model": deployment["model"],
            "status": deployment["status"],
            "port": deployment["port"],
            "host": deployment["host"],
            "endpoint": deployment.get("endpoint"),
            "start_time": deployment.get("start_time"),
            "log_file": deployment["log_file"]
        }

    def stop_deployment(self, deployment_id: str) -> bool:
        """
        停止部署服务

        Args:
            deployment_id: 部署 ID

        Returns:
            success: 是否成功停止
        """
        if deployment_id not in self.deployments:
            return False

        if deployment_id in self.processes:
            process = self.processes[deployment_id]
            process.terminate()
            import time
            time.sleep(1)
            if process.poll() is None:
                process.kill()

            self.deployments[deployment_id]["status"] = "stopped"
            del self.processes[deployment_id]
            logger.info(f"Deployment {deployment_id} stopped")
            return True

        return False

    def list_deployments(self) -> List[Dict]:
        """
        获取所有部署列表

        Returns:
            deployments: 部署列表
        """
        return [
            {
                "deployment_id": deployment_id,
                "model": deployment["model"],
                "status": deployment["status"],
                "port": deployment["port"],
                "endpoint": deployment.get("endpoint")
            }
            for deployment_id, deployment in self.deployments.items()
        ]

    def get_deployment_logs(
        self,
        deployment_id: str,
        lines: int = 50
    ) -> Optional[str]:
        """
        获取部署日志

        Args:
            deployment_id: 部署 ID
            lines: 读取行数

        Returns:
            logs: 日志内容
        """
        if deployment_id not in self.deployments:
            return None

        log_file = self.deployments[deployment_id]["log_file"]
        if not os.path.exists(log_file):
            return ""

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            logger.error(f"Failed to read log file: {e}")
            return None

    async def check_health(self, deployment_id: str) -> Dict:
        """
        检查部署服务健康状态

        Args:
            deployment_id: 部署 ID

        Returns:
            health: 健康状态信息
        """
        if deployment_id not in self.deployments:
            return {"status": "unknown", "message": "Deployment not found"}

        deployment = self.deployments[deployment_id]

        if deployment["status"] != "running":
            return {"status": "down", "message": f"Status: {deployment['status']}"}

        # 尝试访问健康检查端点
        try:
            endpoint = deployment.get("endpoint")
            if not endpoint:
                return {"status": "unknown", "message": "No endpoint"}

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{endpoint}/health", timeout=5.0)
                if response.status_code == 200:
                    return {"status": "healthy", "message": "Service is running"}
                else:
                    return {"status": "unhealthy", "message": f"Status code: {response.status_code}"}

        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}
