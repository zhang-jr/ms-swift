"""
推理 API 端点 - OpenAI 兼容格式
通过已部署的 vllm 服务进行推理
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

# 导入服务
from services.deploy_service import deploy_service
from services.infer_service import infer_service


# 请求/响应模型
class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # user, assistant, system
    content: str


class ChatCompletionRequest(BaseModel):
    """对话补全请求（OpenAI 格式）"""
    deployment_id: str  # 部署 ID
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


class SimpleChatRequest(BaseModel):
    """简化的对话请求（兼容旧版本）"""
    deployment_id: str  # 部署 ID
    query: str
    history: Optional[List[List[str]]] = None  # [[user1, bot1], [user2, bot2], ...]
    system: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI 兼容的对话补全接口

    示例:
        POST /api/infer/chat/completions
        {
            "deployment_id": "deploy-12345678",
            "messages": [
                {"role": "user", "content": "你好"}
            ],
            "temperature": 0.7
        }

    Args:
        request: 对话补全请求

    Returns:
        dict: OpenAI 格式的响应
    """
    # 检查部署是否存在
    deployment = deploy_service.get_deployment_status(request.deployment_id)

    if deployment["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"部署 {request.deployment_id} 不存在")

    if deployment["status"] != "running":
        raise HTTPException(
            status_code=503,
            detail=f"部署 {request.deployment_id} 状态为 {deployment['status']}，无法提供服务"
        )

    # 转换消息格式
    messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

    # 构建请求参数
    kwargs = {}
    if request.top_p is not None:
        kwargs["top_p"] = request.top_p
    if request.frequency_penalty is not None:
        kwargs["frequency_penalty"] = request.frequency_penalty
    if request.presence_penalty is not None:
        kwargs["presence_penalty"] = request.presence_penalty

    try:
        if request.stream:
            # 流式响应
            return StreamingResponse(
                _stream_chat_generator(
                    deployment["base_url"],
                    deployment["served_model_name"],
                    messages,
                    request.temperature,
                    request.max_tokens,
                    **kwargs
                ),
                media_type="text/event-stream"
            )
        else:
            # 非流式响应
            result = infer_service.chat_completions(
                base_url=deployment["base_url"],
                model=deployment["served_model_name"],
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
                **kwargs
            )
            return result

    except RuntimeError as e:
        logger.error(f"推理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_chat_generator(
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_tokens: Optional[int],
    **kwargs
):
    """流式响应生成器"""
    try:
        for chunk in infer_service.chat_completions(
            base_url=base_url,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs
        ):
            # SSE 格式
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        # 结束标记
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"流式推理失败: {e}")
        error_data = {"error": str(e)}
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def simple_chat(request: SimpleChatRequest):
    """
    简化的对话接口（兼容旧版本）

    示例:
        POST /api/infer/chat
        {
            "deployment_id": "deploy-12345678",
            "query": "你好",
            "history": [["上一轮问题", "上一轮回答"]],
            "system": "你是一个有帮助的助手"
        }

    Args:
        request: 简化对话请求

    Returns:
        dict: 包含 response, history, usage 的字典
    """
    # 检查部署是否存在
    deployment = deploy_service.get_deployment_status(request.deployment_id)

    if deployment["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"部署 {request.deployment_id} 不存在")

    if deployment["status"] != "running":
        raise HTTPException(
            status_code=503,
            detail=f"部署 {request.deployment_id} 状态为 {deployment['status']}，无法提供服务"
        )

    try:
        result = infer_service.simple_chat(
            base_url=deployment["base_url"],
            model=deployment["served_model_name"],
            query=request.query,
            history=request.history,
            system=request.system,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return result

    except RuntimeError as e:
        logger.error(f"推理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{deployment_id}")
async def get_models(deployment_id: str):
    """
    获取部署的模型列表

    Args:
        deployment_id: 部署 ID

    Returns:
        dict: 模型列表
    """
    # 检查部署是否存在
    deployment = deploy_service.get_deployment_status(deployment_id)

    if deployment["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"部署 {deployment_id} 不存在")

    try:
        models = infer_service.get_models(deployment["base_url"])
        return {"models": models}

    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
