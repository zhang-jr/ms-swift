"""
推理服务 - OpenAI 兼容的 API 调用
通过调用已部署的 vllm 服务进行推理
"""
import requests
import logging
from typing import Dict, Any, List, Optional, Iterator
import json

logger = logging.getLogger(__name__)


class InferService:
    """推理服务类 - 调用 vllm 部署的 OpenAI 兼容 API"""

    def __init__(self):
        # 推理服务不再需要加载模型（由 deploy_service 管理）
        pass

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


# 全局实例
infer_service = InferService()
