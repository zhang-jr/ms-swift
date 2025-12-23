"""
推理服务 - 支持本地模型加载和 OpenAI 兼容 API 调用
- 本地模型加载：直接加载模型到内存进行推理
- 远程推理：通过调用已部署的 vllm 服务进行推理
"""
import requests
import logging
from typing import Dict, Any, List, Optional, Iterator
import json
import asyncio
import uuid

logger = logging.getLogger(__name__)


class InferService:
    """推理服务类 - 支持本地模型加载和远程 API 调用"""

    def __init__(self):
        # 本地模型管理
        self._loaded_models: Dict[str, Dict[str, Any]] = {}  # model_instance_id -> model_info
        self._current_model_id: Optional[str] = None  # 当前激活的模型 ID

    def chat_completions(
        self,
        base_url: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        OpenAI 兼容的对话补全 API

        Args:
            base_url: 部署服务的基础 URL (如 http://localhost:8000)
            model: 模型名称（served_model_name）
            messages: 对话消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数 (0.0-2.0)
            max_tokens: 最大生成 token 数
            stream: 是否使用流式响应
            **kwargs: 其他 OpenAI API 参数

        Returns:
            dict: OpenAI 格式的响应
        """
        api_url = f"{base_url}/v1/chat/completions"

        # 构建请求体
        request_body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens is not None:
            request_body["max_tokens"] = max_tokens

        # 合并其他参数
        request_body.update(kwargs)

        logger.info(f"调用推理 API: {api_url}")
        logger.debug(f"请求体: {json.dumps(request_body, ensure_ascii=False)}")

        try:
            if stream:
                # 流式响应
                return self._stream_chat(api_url, request_body)
            else:
                # 非流式响应
                response = requests.post(
                    api_url,
                    json=request_body,
                    headers={"Content-Type": "application/json"},
                    timeout=120,  # 2 分钟超时
                )

                response.raise_for_status()
                result = response.json()

                logger.info(f"推理成功，使用 tokens: {result.get('usage', {})}")
                return result

        except requests.RequestException as e:
            logger.error(f"推理请求失败: {e}")
            raise RuntimeError(f"推理请求失败: {e}")

    def _stream_chat(
        self,
        api_url: str,
        request_body: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        """
        流式对话补全

        Args:
            api_url: API URL
            request_body: 请求体

        Yields:
            dict: 流式响应块
        """
        try:
            response = requests.post(
                api_url,
                json=request_body,
                headers={"Content-Type": "application/json"},
                stream=True,
                timeout=120,
            )

            response.raise_for_status()

            # 逐行读取 SSE 响应
            for line in response.iter_lines():
                if not line:
                    continue

                line = line.decode('utf-8')

                # SSE 格式: data: {...}
                if line.startswith('data: '):
                    data_str = line[6:]  # 去掉 "data: "

                    # 结束标记
                    if data_str.strip() == '[DONE]':
                        break

                    try:
                        chunk = json.loads(data_str)
                        yield chunk
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析流式响应失败: {e}, data: {data_str}")
                        continue

        except requests.RequestException as e:
            logger.error(f"流式推理请求失败: {e}")
            raise RuntimeError(f"流式推理请求失败: {e}")

    def simple_chat(
        self,
        base_url: str,
        model: str,
        query: str,
        history: Optional[List[List[str]]] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        简化的对话接口（兼容旧版本）

        Args:
            base_url: 部署服务的基础 URL
            model: 模型名称
            query: 用户查询
            history: 历史对话 [[user1, assistant1], [user2, assistant2], ...]
            system: 系统提示词
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            dict: 包含 response, history, usage 的字典
        """
        # 构建 messages
        messages = []

        # 添加系统提示
        if system:
            messages.append({"role": "system", "content": system})

        # 添加历史对话
        if history:
            for user_msg, assistant_msg in history:
                messages.append({"role": "user", "content": user_msg})
                messages.append({"role": "assistant", "content": assistant_msg})

        # 添加当前查询
        messages.append({"role": "user", "content": query})

        # 调用 chat_completions
        result = self.chat_completions(
            base_url=base_url,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        # 提取响应
        response_text = result['choices'][0]['message']['content']

        # 更新历史
        new_history = history.copy() if history else []
        new_history.append([query, response_text])

        return {
            "response": response_text,
            "history": new_history,
            "usage": result.get('usage', {}),
            "model": result.get('model', model),
        }

    def get_models(self, base_url: str) -> List[Dict[str, Any]]:
        """
        获取可用模型列表

        Args:
            base_url: 部署服务的基础 URL

        Returns:
            list: 模型列表
        """
        api_url = f"{base_url}/v1/models"

        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            result = response.json()

            return result.get('data', [])

        except requests.RequestException as e:
            logger.error(f"获取模型列表失败: {e}")
            return []

    # ============ 本地模型加载和推理 ============

    async def load_local_model(
        self,
        model_id_or_path: str,
        adapter_path: Optional[str] = None,
        model_type: Optional[str] = None,
        max_length: Optional[int] = None,
        temperature: Optional[float] = 0.7,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repetition_penalty: Optional[float] = None,
        quantization_bit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        加载本地模型到内存（模拟实现）

        注意：这是一个简化实现。真实场景需要使用 swift.llm 库加载模型。

        Args:
            model_id_or_path: 模型 ID 或路径
            adapter_path: Adapter 路径（可选）
            其他参数: 模型配置参数

        Returns:
            dict: 加载结果
        """
        model_instance_id = f"model-{uuid.uuid4().hex[:8]}"

        logger.info(f"加载模型: {model_id_or_path}, adapter: {adapter_path}")

        # 模拟模型加载延迟
        await asyncio.sleep(1)

        # 保存模型信息
        model_info = {
            "model_instance_id": model_instance_id,
            "model_id": model_id_or_path,
            "adapter_path": adapter_path,
            "model_type": model_type,
            "max_length": max_length or 2048,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
            "quantization_bit": quantization_bit,
            "loaded_at": None,  # 可以记录加载时间
        }

        self._loaded_models[model_instance_id] = model_info
        self._current_model_id = model_instance_id

        logger.info(f"模型加载成功: {model_instance_id}")

        return {
            "message": "模型加载成功",
            "model_instance_id": model_instance_id,
            "model_id": model_id_or_path,
        }

    def unload_local_model(self, model_instance_id: Optional[str] = None) -> Dict[str, Any]:
        """
        卸载已加载的模型

        Args:
            model_instance_id: 模型实例 ID（可选，不提供则卸载当前模型）

        Returns:
            dict: 卸载结果
        """
        # 如果不提供 ID，卸载当前模型
        if model_instance_id is None:
            model_instance_id = self._current_model_id

        if model_instance_id is None:
            raise ValueError("没有已加载的模型")

        if model_instance_id not in self._loaded_models:
            raise ValueError(f"模型 {model_instance_id} 不存在")

        # 移除模型
        model_info = self._loaded_models.pop(model_instance_id)

        # 如果卸载的是当前模型，清空当前模型 ID
        if self._current_model_id == model_instance_id:
            self._current_model_id = None

        logger.info(f"模型已卸载: {model_instance_id}")

        return {
            "message": "模型已卸载",
            "model_instance_id": model_instance_id,
        }

    def get_current_model(self) -> Optional[Dict[str, Any]]:
        """
        获取当前加载的模型信息

        Returns:
            dict: 当前模型信息，如果没有加载则返回 None
        """
        if self._current_model_id is None:
            return None

        return self._loaded_models.get(self._current_model_id)

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """
        获取所有已加载的模型列表

        Returns:
            list: 已加载模型列表
        """
        return list(self._loaded_models.values())

    async def chat_with_local_model(
        self,
        query: str,
        history: Optional[List[List[str]]] = None,
        system: Optional[str] = None,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        使用已加载的本地模型进行对话（模拟实现）

        注意：这是一个简化实现。真实场景需要调用 swift.llm 的推理接口。

        Args:
            query: 用户查询
            history: 历史对话
            system: 系统提示词
            max_new_tokens: 最大生成 token 数
            temperature: 温度参数
            top_p: Top-p 参数
            top_k: Top-k 参数

        Returns:
            dict: 对话响应
        """
        if self._current_model_id is None:
            raise ValueError("没有已加载的模型")

        current_model = self._loaded_models[self._current_model_id]

        logger.info(f"使用模型 {current_model['model_id']} 进行推理")

        # 模拟推理延迟
        await asyncio.sleep(0.5)

        # 模拟响应（真实场景需要调用模型）
        response_text = f"这是使用模型 {current_model['model_id']} 的模拟回复。您的问题是：{query}"

        # 更新历史
        new_history = history.copy() if history else []
        new_history.append([query, response_text])

        return {
            "response": response_text,
            "history": new_history,
            "usage": {
                "prompt_tokens": len(query) * 2,  # 模拟
                "completion_tokens": len(response_text) * 2,  # 模拟
                "total_tokens": (len(query) + len(response_text)) * 2,  # 模拟
            },
            "model": current_model["model_id"],
        }


# 全局实例
infer_service = InferService()
