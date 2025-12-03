# Copyright (c) Alibaba, Inc. and its affiliates.
"""
推理 API 端点
提供模型推理和对话相关的 RESTful API
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from services.infer_service import InferService

router = APIRouter()
infer_service = InferService()


# 请求/响应模型
class ChatMessage(BaseModel):
    """聊天消息模型"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """对话请求模型"""
    model: Optional[str] = Field("default", description="模型名称或 LoRA 模块名")
    messages: List[ChatMessage] = Field(..., description="消息历史")
    system: Optional[str] = Field(None, description="系统提示词")
    temperature: Optional[float] = Field(0.7, description="温度参数")
    top_p: Optional[float] = Field(0.9, description="Top-p 采样")
    top_k: Optional[int] = Field(50, description="Top-k 采样")
    max_tokens: Optional[int] = Field(2048, description="最大生成 token 数")
    repetition_penalty: Optional[float] = Field(1.0, description="重复惩罚")
    stream: Optional[bool] = Field(False, description="是否流式输出")


class ChatResponse(BaseModel):
    """对话响应模型"""
    message: ChatMessage
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


class LoadModelRequest(BaseModel):
    """加载模型请求"""
    model: str = Field(..., description="模型 ID 或路径")
    model_type: Optional[str] = Field(None, description="模型类型")
    template: Optional[str] = Field(None, description="模板类型")
    port: Optional[int] = Field(8000, description="服务端口")
    gpu_id: Optional[List[str]] = Field(["0"], description="GPU ID 列表")
    ckpt_dir: Optional[str] = Field(None, description="检查点目录")
    more_params: Optional[Dict[str, Any]] = Field(None, description="其他参数")


# API 端点
@router.post("/chat", summary="对话推理")
async def chat(request: ChatRequest):
    """
    与模型进行对话

    - **messages**: 消息历史
    - **model**: 使用的模型或 LoRA 模块
    - **temperature**: 温度参数,控制输出随机性
    - 返回模型的回复
    """
    try:
        # 检查是否有模型已加载
        if not infer_service.is_model_loaded():
            raise HTTPException(
                status_code=400,
                detail="请先加载模型"
            )

        # 调用推理服务
        response = await infer_service.chat(
            messages=[msg.dict() for msg in request.messages],
            model=request.model,
            system=request.system,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_tokens=request.max_tokens,
            repetition_penalty=request.repetition_penalty,
            stream=request.stream
        )

        return {
            "code": 0,
            "message": "success",
            "data": response
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket):
    """
    WebSocket 流式对话

    客户端发送 ChatRequest JSON
    服务端流式返回生成的内容
    """
    await websocket.accept()

    try:
        # 接收请求
        request_data = await websocket.receive_json()
        request = ChatRequest(**request_data)

        # 检查模型是否加载
        if not infer_service.is_model_loaded():
            await websocket.send_json({
                "type": "error",
                "message": "请先加载模型"
            })
            await websocket.close()
            return

        # 流式生成
        async for chunk in infer_service.chat_stream(
            messages=[msg.dict() for msg in request.messages],
            model=request.model,
            system=request.system,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            max_tokens=request.max_tokens,
            repetition_penalty=request.repetition_penalty
        ):
            await websocket.send_json({
                "type": "chunk",
                "data": chunk
            })

        # 发送完成信号
        await websocket.send_json({
            "type": "done"
        })

    except WebSocketDisconnect:
        print("Client disconnected from chat stream")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        await websocket.close()


@router.post("/load-model", summary="加载模型")
async def load_model(request: LoadModelRequest):
    """
    加载模型到内存

    - **model**: 模型 ID 或本地路径
    - **port**: 服务端口
    - **gpu_id**: 使用的 GPU
    """
    try:
        # 检查端口是否被占用
        if infer_service.is_port_in_use(request.port):
            raise HTTPException(
                status_code=400,
                detail=f"端口 {request.port} 已被占用"
            )

        # 加载模型
        success = await infer_service.load_model(
            model=request.model,
            model_type=request.model_type,
            template=request.template,
            port=request.port,
            gpu_id=request.gpu_id,
            ckpt_dir=request.ckpt_dir,
            more_params=request.more_params
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="模型加载失败"
            )

        return {
            "code": 0,
            "message": "模型加载成功",
            "data": {
                "model": request.model,
                "port": request.port,
                "status": "loaded"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unload-model", summary="卸载模型")
async def unload_model():
    """
    卸载当前加载的模型,释放资源
    """
    try:
        success = infer_service.unload_model()
        if not success:
            raise HTTPException(
                status_code=400,
                detail="没有已加载的模型"
            )

        return {
            "code": 0,
            "message": "模型已卸载",
            "data": {"status": "unloaded"}
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", summary="获取推理状态")
async def get_inference_status():
    """
    获取当前推理服务状态
    """
    try:
        status = infer_service.get_status()
        return {
            "code": 0,
            "message": "success",
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models", summary="获取已加载的模型")
async def list_loaded_models():
    """
    获取当前已加载的模型列表
    """
    try:
        models = infer_service.list_loaded_models()
        return {
            "code": 0,
            "message": "success",
            "data": {"models": models}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
