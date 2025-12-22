"""
部署 API 端点 - vllm 推理服务器
提供 OpenAI 兼容的推理服务部署和管理
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# 导入部署服务
from services.deploy_service import deploy_service


# 请求/响应模型
class DeployRequest(BaseModel):
    """部署请求"""
    model_path: str  # 模型路径（本地或 HuggingFace 模型名）
    served_model_name: Optional[str] = None  # 服务模型名称（用于 API 调用）
    port: Optional[int] = None  # 服务端口（None 表示自动分配）
    gpu_devices: str = "0"  # GPU 设备 ID（如 "0" 或 "0,1"）
    max_model_len: Optional[int] = None  # 最大模型长度


class DeployResponse(BaseModel):
    """部署响应"""
    deployment_id: str
    model_path: str
    served_model_name: str
    port: int
    base_url: str
    api_endpoint: str
    status: str
    message: str


class DeploymentStatus(BaseModel):
    """部署状态"""
    deployment_id: str
    model_path: str
    served_model_name: str
    port: int
    base_url: str
    api_endpoint: str
    status: str  # running, unhealthy, stopped, not_found
    pid: Optional[int] = None
    uptime_seconds: Optional[float] = None


@router.post("/start", response_model=DeployResponse)
async def start_deployment(request: DeployRequest, background_tasks: BackgroundTasks):
    """
    启动模型部署服务（使用 vllm 后端）

    示例:
        POST /api/deploy/start
        {
            "model_path": "Qwen/Qwen2.5-7B-Instruct",
            "served_model_name": "Qwen2.5-7B-Instruct",
            "gpu_devices": "0"
        }

    部署成功后，可通过以下方式调用:
        curl http://localhost:8000/v1/chat/completions \\
        -H "Content-Type: application/json" \\
        -d '{
            "model": "Qwen2.5-7B-Instruct",
            "messages": [{"role": "user", "content": "你好"}]
        }'

    Args:
        request: 部署请求参数

    Returns:
        DeployResponse: 部署信息
    """
    import uuid

    # 生成部署 ID
    deployment_id = f"deploy-{uuid.uuid4().hex[:8]}"

    logger.info(f"收到部署请求: {deployment_id}, 模型: {request.model_path}")

    try:
        # 启动部署（异步，等待服务启动）
        deployment_info = await deploy_service.start_deployment(
            deployment_id=deployment_id,
            model_path=request.model_path,
            served_model_name=request.served_model_name,
            port=request.port,
            gpu_devices=request.gpu_devices,
            max_model_len=request.max_model_len,
        )

        return DeployResponse(
            deployment_id=deployment_info["deployment_id"],
            model_path=deployment_info["model_path"],
            served_model_name=deployment_info["served_model_name"],
            port=deployment_info["port"],
            base_url=deployment_info["base_url"],
            api_endpoint=deployment_info["api_endpoint"],
            status=deployment_info["status"],
            message=f"部署成功！推理服务已启动在端口 {deployment_info['port']}"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"部署失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"部署失败: {str(e)}")


@router.post("/stop/{deployment_id}")
async def stop_deployment(deployment_id: str):
    """
    停止部署服务

    Args:
        deployment_id: 部署 ID

    Returns:
        dict: 操作结果
    """
    try:
        deploy_service.stop_deployment(deployment_id)
        return {"message": f"部署 {deployment_id} 已停止"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"停止部署失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"停止部署失败: {str(e)}")


@router.get("/status/{deployment_id}", response_model=DeploymentStatus)
async def get_deployment_status(deployment_id: str):
    """
    获取部署状态

    Args:
        deployment_id: 部署 ID

    Returns:
        DeploymentStatus: 部署状态
    """
    try:
        status = deploy_service.get_deployment_status(deployment_id)

        if status["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"部署 {deployment_id} 不存在")

        return DeploymentStatus(**status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取部署状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取部署状态失败: {str(e)}")


@router.get("/list", response_model=List[DeploymentStatus])
async def list_deployments():
    """
    列出所有部署

    Returns:
        list: 部署列表
    """
    try:
        deployments = deploy_service.list_deployments()
        return [DeploymentStatus(**d) for d in deployments]

    except Exception as e:
        logger.error(f"列出部署失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"列出部署失败: {str(e)}")


@router.get("/logs/{deployment_id}")
async def get_deployment_logs(deployment_id: str, lines: int = 100):
    """
    获取部署日志

    Args:
        deployment_id: 部署 ID
        lines: 读取的行数

    Returns:
        dict: 日志内容
    """
    try:
        logs = deploy_service.get_deployment_logs(deployment_id, lines)
        return {"deployment_id": deployment_id, "logs": logs}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取部署日志失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取部署日志失败: {str(e)}")
