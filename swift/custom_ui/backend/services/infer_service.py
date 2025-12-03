# Copyright (c) Alibaba, Inc. and its affiliates.
"""
推理服务层
处理模型推理和对话相关的业务逻辑
"""
import os
import socket
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from swift.llm import InferClient, InferRequest, RequestConfig
from swift.utils import get_logger

logger = get_logger()


class InferService:
    """推理服务类"""

    def __init__(self):
        # 当前加载的模型信息
        self.current_model: Optional[Dict] = None
        # InferClient 实例
        self.client: Optional[InferClient] = None
        # 部署服务信息 (与 DeployService 共享)
        self.deployment_info: Optional[Dict] = None

    def is_model_loaded(self) -> bool:
        """检查是否有模型已加载"""
        return self.current_model is not None and self.client is not None

    def is_port_in_use(self, port: int, host: str = "127.0.0.1") -> bool:
        """
        检查端口是否被占用

        Args:
            port: 端口号
            host: 主机地址

        Returns:
            in_use: 是否被占用
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return False
            except OSError:
                return True

    async def load_model(
        self,
        model: str,
        model_type: Optional[str] = None,
        template: Optional[str] = None,
        port: int = 8000,
        gpu_id: Optional[List[str]] = None,
        ckpt_dir: Optional[str] = None,
        more_params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        加载模型(通过启动部署服务)

        注意: 实际的模型部署由 DeployService 处理
        这里只是创建 InferClient 连接到已部署的服务

        Args:
            model: 模型 ID 或路径
            port: 服务端口
            其他参数同 LoadModelRequest

        Returns:
            success: 是否成功
        """
        try:
            # 检查端口上是否有服务
            # 实际应该先通过 DeployService 启动服务
            # 这里假设服务已经由外部启动

            # 等待服务启动
            max_retries = 30
            for i in range(max_retries):
                if self.is_port_in_use(port):
                    break
                await asyncio.sleep(1)
            else:
                logger.error(f"Service on port {port} not available")
                return False

            # 创建 InferClient
            self.client = InferClient(port=port)

            # 保存模型信息
            self.current_model = {
                "model": model,
                "model_type": model_type,
                "template": template,
                "port": port,
                "ckpt_dir": ckpt_dir,
                "load_time": datetime.now().isoformat()
            }

            logger.info(f"Model loaded: {model} on port {port}")
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def unload_model(self) -> bool:
        """
        卸载模型

        Returns:
            success: 是否成功
        """
        if not self.is_model_loaded():
            return False

        self.current_model = None
        self.client = None
        logger.info("Model unloaded")
        return True

    async def chat(
        self,
        messages: List[Dict],
        model: str = "default",
        system: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        max_tokens: int = 2048,
        repetition_penalty: float = 1.0,
        stream: bool = False
    ) -> Dict:
        """
        对话推理

        Args:
            messages: 消息历史
            model: 模型名称或 LoRA 模块
            其他参数同 ChatRequest

        Returns:
            response: 推理响应
        """
        if not self.is_model_loaded():
            raise RuntimeError("No model loaded")

        try:
            # 添加 system 消息
            if system and (not messages or messages[0].get("role") != "system"):
                messages = [{"role": "system", "content": system}] + messages

            # 创建推理请求
            infer_request = InferRequest(messages=messages)

            # 创建请求配置
            request_config = RequestConfig(
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_tokens=max_tokens,
                repetition_penalty=repetition_penalty,
                stream=stream
            )

            # 模型参数
            model_kwargs = {}
            if model != "default":
                model_kwargs["model"] = model

            # 调用推理
            result = self.client.infer(
                infer_requests=[infer_request],
                request_config=request_config,
                **model_kwargs
            )

            # 非流式返回
            if not stream:
                response = result[0]
                return {
                    "message": {
                        "role": "assistant",
                        "content": response.choices[0].message.content
                    },
                    "finish_reason": response.choices[0].finish_reason,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            else:
                # 流式返回 generator
                return result[0]

        except Exception as e:
            logger.error(f"Chat inference failed: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[Dict],
        model: str = "default",
        system: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        max_tokens: int = 2048,
        repetition_penalty: float = 1.0
    ):
        """
        流式对话推理

        Args:
            messages: 消息历史
            其他参数同 chat()

        Yields:
            chunk: 流式响应块
        """
        if not self.is_model_loaded():
            raise RuntimeError("No model loaded")

        try:
            # 添加 system 消息
            if system and (not messages or messages[0].get("role") != "system"):
                messages = [{"role": "system", "content": system}] + messages

            # 创建推理请求
            infer_request = InferRequest(messages=messages)

            # 创建请求配置
            request_config = RequestConfig(
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_tokens=max_tokens,
                repetition_penalty=repetition_penalty,
                stream=True
            )

            # 模型参数
            model_kwargs = {}
            if model != "default":
                model_kwargs["model"] = model

            # 调用推理
            stream_generator = self.client.infer(
                infer_requests=[infer_request],
                request_config=request_config,
                **model_kwargs
            )[0]

            # 流式返回
            for chunk in stream_generator:
                if chunk is None:
                    continue
                yield {
                    "content": chunk.choices[0].delta.content,
                    "finish_reason": chunk.choices[0].finish_reason
                }

        except Exception as e:
            logger.error(f"Stream chat failed: {e}")
            raise

    def get_status(self) -> Dict:
        """
        获取推理服务状态

        Returns:
            status: 状态信息
        """
        if not self.is_model_loaded():
            return {
                "status": "idle",
                "model": None,
                "message": "No model loaded"
            }

        return {
            "status": "ready",
            "model": self.current_model.get("model"),
            "port": self.current_model.get("port"),
            "load_time": self.current_model.get("load_time"),
            "message": "Model is ready for inference"
        }

    def list_loaded_models(self) -> List[Dict]:
        """
        获取已加载的模型列表

        Returns:
            models: 模型列表
        """
        if not self.is_model_loaded():
            return []

        return [self.current_model]
