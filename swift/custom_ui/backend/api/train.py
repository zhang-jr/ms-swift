# Copyright (c) Alibaba, Inc. and its affiliates.
"""
训练 API 端点
提供模型训练相关的 RESTful API
"""
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from services.train_service import TrainService
from services.model_service import ModelService

router = APIRouter()
train_service = TrainService()
model_service = ModelService()


# 请求/响应模型
class TrainRequest(BaseModel):
    """训练请求模型"""
    model: str = Field(..., description="模型 ID 或路径")
    model_type: Optional[str] = Field(None, description="模型类型")
    template: Optional[str] = Field(None, description="模板类型")
    dataset: Optional[List[str]] = Field(None, description="数据集列表")
    custom_train_dataset_path: Optional[str] = Field(None, description="自定义数据集路径")
    train_stage: str = Field("sft", description="训练阶段: pt/sft")
    train_type: str = Field("lora", description="训练类型: full/lora/qlora等")

    # 训练超参数
    num_train_epochs: Optional[int] = Field(1, description="训练轮数")
    batch_size: Optional[int] = Field(1, description="批次大小")
    learning_rate: Optional[float] = Field(1e-4, description="学习率")
    max_length: Optional[int] = Field(2048, description="最大序列长度")
    gradient_accumulation_steps: Optional[int] = Field(16, description="梯度累积步数")

    # 运行配置
    gpu_id: Optional[List[str]] = Field(["0"], description="GPU ID 列表")
    seed: Optional[int] = Field(42, description="随机种子")
    output_dir: Optional[str] = Field(None, description="输出目录")
    logging_steps: Optional[int] = Field(5, description="日志记录步数")
    save_steps: Optional[int] = Field(None, description="保存检查点步数")

    # 其他参数
    more_params: Optional[Dict[str, Any]] = Field(None, description="其他高级参数")


class TrainResponse(BaseModel):
    """训练响应模型"""
    task_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="消息")
    output_dir: Optional[str] = Field(None, description="输出目录")
    logging_dir: Optional[str] = Field(None, description="日志目录")


class TaskStatus(BaseModel):
    """任务状态模型"""
    task_id: str
    status: str  # pending/running/completed/failed
    progress: Optional[float] = None
    message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    output_dir: Optional[str] = None
    logging_dir: Optional[str] = None


# API 端点
@router.post("/start", response_model=TrainResponse, summary="启动训练")
async def start_training(
    request: TrainRequest,
    background_tasks: BackgroundTasks
):
    """
    启动模型训练任务

    - **model**: 模型 ID 或本地路径
    - **dataset**: 数据集列表
    - **train_type**: 训练类型 (full/lora/qlora等)
    - 返回任务 ID 和状态
    """
    try:
        # 验证数据集
        if not request.dataset and not request.custom_train_dataset_path:
            raise HTTPException(
                status_code=400,
                detail="请提供 dataset 或 custom_train_dataset_path"
            )

        # 创建训练任务
        task_id = train_service.create_task(
            model=request.model,
            model_type=request.model_type,
            template=request.template,
            dataset=request.dataset,
            custom_train_dataset_path=request.custom_train_dataset_path,
            train_stage=request.train_stage,
            train_type=request.train_type,
            num_train_epochs=request.num_train_epochs,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate,
            max_length=request.max_length,
            gradient_accumulation_steps=request.gradient_accumulation_steps,
            gpu_id=request.gpu_id,
            seed=request.seed,
            output_dir=request.output_dir,
            logging_steps=request.logging_steps,
            save_steps=request.save_steps,
            more_params=request.more_params
        )

        # 在后台启动训练
        background_tasks.add_task(train_service.run_training, task_id)

        # 获取任务信息
        task_info = train_service.get_task_info(task_id)

        return TrainResponse(
            task_id=task_id,
            status="started",
            message="训练任务已启动",
            output_dir=task_info.get("output_dir"),
            logging_dir=task_info.get("logging_dir")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=TaskStatus, summary="获取训练状态")
async def get_training_status(task_id: str):
    """
    获取训练任务状态

    - **task_id**: 任务 ID
    - 返回任务的当前状态和进度
    """
    try:
        status = train_service.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
        return TaskStatus(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{task_id}", summary="停止训练")
async def stop_training(task_id: str):
    """
    停止训练任务

    - **task_id**: 任务 ID
    """
    try:
        success = train_service.stop_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或无法停止")
        return {
            "code": 0,
            "message": "训练任务已停止",
            "data": {"task_id": task_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks", summary="获取所有训练任务")
async def list_training_tasks():
    """
    获取所有训练任务列表
    """
    try:
        tasks = train_service.list_tasks()
        return {
            "code": 0,
            "message": "success",
            "data": {"tasks": tasks}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{task_id}", summary="获取训练日志")
async def get_training_logs(
    task_id: str,
    lines: int = 50,
    offset: int = 0
):
    """
    获取训练日志

    - **task_id**: 任务 ID
    - **lines**: 读取的行数
    - **offset**: 偏移量
    """
    try:
        logs = train_service.get_task_logs(task_id, lines, offset)
        if logs is None:
            raise HTTPException(status_code=404, detail=f"任务 {task_id} 的日志不存在")
        return {
            "code": 0,
            "message": "success",
            "data": {
                "task_id": task_id,
                "logs": logs
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/logs/stream/{task_id}")
async def stream_training_logs(websocket: WebSocket, task_id: str):
    """
    WebSocket 实时流式传输训练日志

    - **task_id**: 任务 ID
    """
    await websocket.accept()

    try:
        async for log_line in train_service.stream_task_logs(task_id):
            await websocket.send_json({
                "type": "log",
                "data": log_line
            })
    except WebSocketDisconnect:
        print(f"Client disconnected from task {task_id} log stream")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        await websocket.close()


@router.get("/models", summary="获取可用模型列表")
async def list_models():
    """
    获取可用的模型列表
    """
    try:
        models = model_service.list_available_models()
        return {
            "code": 0,
            "message": "success",
            "data": {"models": models}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets", summary="获取可用数据集列表")
async def list_datasets():
    """
    获取可用的数据集列表
    """
    try:
        datasets = train_service.list_available_datasets()
        return {
            "code": 0,
            "message": "success",
            "data": {"datasets": datasets}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
