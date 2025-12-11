"""
训练 API 端点
提供模型训练相关的 API
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
from services.train_service import TrainService

router = APIRouter()

# 全局 TrainService 单例（共享 running_processes）
train_service = TrainService()

# 数据集配置模型
class DatasetConfig(BaseModel):
    """单个数据集的配置"""
    name: str  # 数据集名称或路径
    sample_count: Optional[int] = None  # 采样数量（可选，例如 500）

# 请求模型
class TrainRequest(BaseModel):
    model_id: str
    model_type: str = "qwen-7b-chat"
    # 数据集配置：支持多个数据集，每个可以设置采样数量
    # 示例: [{"name": "dataset1", "sample_count": 500}, {"name": "dataset2"}]
    datasets: List[DatasetConfig]
    train_type: str = "lora"

    # LoRA 参数
    lora_rank: int = 8
    lora_alpha: int = 32
    lora_dropout: float = 0.05

    # 训练参数
    num_train_epochs: int = 1
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 16
    learning_rate: float = 1e-4
    max_length: int = 2048

    # 其他参数
    output_dir: Optional[str] = None
    logging_steps: int = 10
    save_steps: int = 100

    # 高级参数
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01
    gradient_checkpointing: bool = True

class TrainResponse(BaseModel):
    task_id: str
    status: str
    message: str
    created_at: str

class TrainStatus(BaseModel):
    task_id: str
    status: str  # pending, running, completed, failed
    progress: float  # 0-100
    current_epoch: int
    total_epochs: int
    loss: Optional[float]
    loss_history: List[Dict[str, Any]] = []  # Loss 历史数据 [{"step": 1, "loss": 2.5, "epoch": 0.1}, ...]
    logs: List[str]
    created_at: str
    updated_at: str

# 模拟任务存储 (生产环境应使用数据库)
training_tasks: Dict[str, Dict[str, Any]] = {}

@router.post("/start", response_model=TrainResponse)
async def start_training(request: TrainRequest, background_tasks: BackgroundTasks):
    """
    启动训练任务

    Args:
        request: 训练请求参数
        background_tasks: FastAPI 后台任务

    Returns:
        TrainResponse: 包含任务 ID 和状态
    """
    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 设置输出目录
    if not request.output_dir:
        request.output_dir = f"./output/{task_id}"

    # 创建任务记录
    task = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "current_epoch": 0,
        "total_epochs": request.num_train_epochs,
        "loss": None,
        "loss_history": [],  # Loss 历史数据
        "logs": [],
        "request": request.model_dump(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    training_tasks[task_id] = task

    # 在后台启动训练（使用全局单例）
    background_tasks.add_task(train_service.run_training, task_id, request.model_dump())

    return TrainResponse(
        task_id=task_id,
        status="pending",
        message="训练任务已创建，正在启动...",
        created_at=task["created_at"]
    )

@router.get("/status/{task_id}", response_model=TrainStatus)
async def get_training_status(task_id: str):
    """
    获取训练任务状态

    Args:
        task_id: 任务 ID

    Returns:
        TrainStatus: 任务状态信息
    """
    if task_id not in training_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = training_tasks[task_id]
    return TrainStatus(**task)

@router.post("/stop/{task_id}")
async def stop_training(task_id: str):
    """
    停止训练任务（杀死训练进程并释放显存）

    Args:
        task_id: 任务 ID

    Returns:
        dict: 操作结果
    """
    if task_id not in training_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = training_tasks[task_id]
    if task["status"] not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail="任务无法停止")

    # 调用 TrainService 停止训练进程
    success = train_service.stop_training(task_id)

    if success:
        # 更新任务状态
        task["status"] = "stopped"
        task["updated_at"] = datetime.now().isoformat()

        # 发送停止日志到 WebSocket
        try:
            import asyncio
            from app import manager
            await manager.send_message(f"[训练已停止] 任务 {task_id} 已被用户手动停止", task_id)
        except Exception as e:
            print(f"Failed to send stop log: {e}")

        return {"message": "训练任务已停止", "task_id": task_id}
    else:
        raise HTTPException(status_code=500, detail="停止训练失败，进程可能已结束")

@router.get("/list")
async def list_training_tasks():
    """
    获取所有训练任务列表

    Returns:
        list: 任务列表
    """
    tasks = []
    for task_id, task in training_tasks.items():
        tasks.append({
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "created_at": task["created_at"]
        })

    return {"tasks": tasks}

@router.delete("/delete/{task_id}")
async def delete_training_task(task_id: str):
    """
    删除训练任务记录

    Args:
        task_id: 任务 ID

    Returns:
        dict: 操作结果
    """
    if task_id not in training_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = training_tasks[task_id]
    if task["status"] in ["pending", "running"]:
        raise HTTPException(status_code=400, detail="运行中的任务无法删除，请先停止")

    del training_tasks[task_id]

    return {"message": "任务已删除", "task_id": task_id}

@router.get("/logs/{task_id}")
async def get_training_logs(task_id: str):
    """
    获取训练任务的历史日志

    用于前端重新连接时加载历史日志，避免 WebSocket 断开导致日志丢失

    Args:
        task_id: 任务 ID

    Returns:
        dict: 包含日志数组的响应
    """
    if task_id not in training_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = training_tasks[task_id]
    logs = task.get('logs', [])

    return {
        "task_id": task_id,
        "logs": logs,
        "total_logs": len(logs)
    }

# 暴露任务存储给 WebSocket 和服务层
def get_task(task_id: str):
    return training_tasks.get(task_id)

def update_task(task_id: str, updates: dict):
    if task_id in training_tasks:
        training_tasks[task_id].update(updates)
        training_tasks[task_id]["updated_at"] = datetime.now().isoformat()
