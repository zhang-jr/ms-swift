"""
推理 API 端点 - 支持本地模型加载和 OpenAI 兼容推理
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
class LoadModelRequest(BaseModel):
    """加载模型请求"""
    model_id_or_path: str
    adapter_path: Optional[str] = None
    model_type: Optional[str] = None
    max_length: Optional[int] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repetition_penalty: Optional[float] = None
    quantization_bit: Optional[int] = None


class ChatRequest(BaseModel):
    """对话请求（直接模型推理）"""
    query: str
    history: Optional[List[List[str]]] = None
    system: Optional[str] = None
    max_new_tokens: Optional[int] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = None
    top_k: Optional[int] = None


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
    """简化的对话请求（基于部署）"""
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


# ============ 本地模型加载和推理端点 ============

@router.post("/load-model")
async def load_model(request: LoadModelRequest):
    """
    加载本地模型到内存（用于直接推理）

    示例:
        POST /api/infer/load-model
        {
            "model_id_or_path": "Qwen/Qwen2.5-7B-Instruct",
            "adapter_path": "/app/output/train-12345678",
            "temperature": 0.7
        }

    Args:
        request: 模型加载请求

    Returns:
        dict: 加载结果
    """
    try:
        result = await infer_service.load_local_model(
            model_id_or_path=request.model_id_or_path,
            adapter_path=request.adapter_path,
            model_type=request.model_type,
            max_length=request.max_length,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repetition_penalty=request.repetition_penalty,
            quantization_bit=request.quantization_bit,
        )
        return result

    except Exception as e:
        logger.error(f"加载模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"加载模型失败: {str(e)}")


@router.post("/unload-model")
async def unload_model(model_instance_id: Optional[str] = None):
    """
    卸载已加载的模型

    Args:
        model_instance_id: 模型实例 ID（可选，不提供则卸载当前模型）

    Returns:
        dict: 卸载结果
    """
    try:
        result = infer_service.unload_local_model(model_instance_id)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"卸载模型失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"卸载模型失败: {str(e)}")


@router.get("/current-model")
async def get_current_model():
    """
    获取当前加载的模型信息

    Returns:
        dict: 当前模型信息，如果没有加载则返回 null
    """
    try:
        current_model = infer_service.get_current_model()
        return {"current_model": current_model}

    except Exception as e:
        logger.error(f"获取当前模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/loaded-models")
async def get_loaded_models():
    """
    获取所有已加载的模型列表

    Returns:
        dict: 已加载模型列表
    """
    try:
        models = infer_service.get_loaded_models()
        return {"models": models}

    except Exception as e:
        logger.error(f"获取已加载模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    使用已加载的本地模型进行对话

    示例:
        POST /api/infer/chat
        {
            "query": "你好",
            "history": [["上一轮问题", "上一轮回答"]],
            "system": "你是一个有帮助的助手",
            "temperature": 0.7
        }

    Args:
        request: 对话请求

    Returns:
        dict: 对话响应
    """
    try:
        # 检查是否有加载的模型
        current_model = infer_service.get_current_model()
        if not current_model:
            raise HTTPException(
                status_code=400,
                detail="没有已加载的模型，请先使用 /load-model 加载模型"
            )

        result = await infer_service.chat_with_local_model(
            query=request.query,
            history=request.history,
            system=request.system,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")
