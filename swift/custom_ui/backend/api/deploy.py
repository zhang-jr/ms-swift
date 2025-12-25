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
    """部署请求（支持 vllm serve 参数）"""
    # 基础参数
    model_id_or_path: str  # 模型 ID 或路径
    adapter_path: Optional[str] = None  # Adapter 路径（可选，如 LoRA adapter）
    served_model_name: Optional[str] = None  # 服务模型名称（可选，默认从路径提取）

    # 前端配置
    host: Optional[str] = "0.0.0.0"  # 服务 Host
    port: Optional[int] = None  # 服务端口（None=自动分配，默认 8000）
    gpu_id: Optional[str] = None  # GPU ID（None=自动分配，"0"=指定单卡）

    # 模型配置
    max_length: Optional[int] = None  # 最大上下文长度（max_model_len）
    dtype: Optional[str] = "auto"  # 数据类型（auto, half, float16, bfloat16, float32）
    trust_remote_code: Optional[bool] = False  # 是否信任远程代码
    quantization: Optional[str] = None  # 量化方法（awq, gptq 等）

    # 缓存配置
    gpu_memory_utilization: Optional[float] = 0.9  # GPU 内存利用率

    # 并行配置
    tensor_parallel_size: Optional[int] = None  # 张量并行大小（多卡推理）


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
    启动模型部署服务（使用 vllm serve）

    示例 1 - 基础部署:
        POST /api/deploy/start
        {
            "model_id_or_path": "/app/models/Qwen/Qwen2.5-7B-Instruct",
            "port": 8080
        }

    示例 2 - 带 LoRA Adapter:
        POST /api/deploy/start
        {
            "model_id_or_path": "/app/models/Qwen/Qwen2.5-7B-Instruct",
            "adapter_path": "/app/output/train-12345678/v0-xxx/checkpoint-100",
            "port": 8081,
            "gpu_memory_utilization": 0.9
        }

    示例 3 - 多卡推理（张量并行）:
        POST /api/deploy/start
        {
            "model_id_or_path": "/app/models/Qwen/Qwen2.5-72B-Instruct",
            "tensor_parallel_size": 4,
            "gpu_memory_utilization": 0.95,
            "max_length": 32768
        }

    部署成功后，可通过 OpenAI 兼容 API 调用:
        curl http://localhost:8080/v1/chat/completions \\
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

    # 使用 print 替代 logger.info（logging 未配置，info 不会输出）
    print(f"[DEBUG] 收到部署请求: {deployment_id}")
    print(f"[DEBUG] 模型路径: {request.model_id_or_path}")
    print(f"[DEBUG] Adapter 路径: {request.adapter_path}")
    print(f"[DEBUG] 端口: {request.port}")
    print(f"[DEBUG] max_length: {request.max_length}")
    print(f"[DEBUG] 完整请求对象: {request}")

    # 参数转换：前端 -> 后端
    # served_model_name: 从请求获取，或从模型路径提取
    served_model_name = request.served_model_name or request.model_id_or_path.split('/')[-1]

    try:
        # 启动部署（使用 vllm serve）
        deployment_info = await deploy_service.start_deployment(
            deployment_id=deployment_id,
            model_path=request.model_id_or_path,
            adapter_path=request.adapter_path,
            served_model_name=served_model_name,
            host=request.host or "0.0.0.0",
            port=request.port,
            gpu_devices=request.gpu_id,  # None=自动分配，"0"=指定单卡
            max_model_len=request.max_length,
            gpu_memory_utilization=request.gpu_memory_utilization,
            tensor_parallel_size=request.tensor_parallel_size,
            quantization=request.quantization,
            dtype=request.dtype or "auto",
            trust_remote_code=request.trust_remote_code or False,
        )
        logger.info(f"部署成功: {deployment_id}")

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
        logger.error(f"部署参数错误 (ValueError): {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        logger.error(f"部署超时 (TimeoutError): {e}", exc_info=True)
        raise HTTPException(status_code=504, detail=str(e))
    except RuntimeError as e:
        logger.error(f"部署运行时错误 (RuntimeError): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"部署失败 (未知异常): {e}")
        logger.error(f"详细堆栈:\n{traceback.format_exc()}")
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


@router.delete("/delete/{deployment_id}")
async def delete_deployment(deployment_id: str, remove_logs: bool = False):
    """
    删除部署（如果正在运行则先停止）

    Args:
        deployment_id: 部署 ID
        remove_logs: 是否删除日志文件（默认 False，保留日志）

    Returns:
        dict: 操作结果
    """
    try:
        deploy_service.delete_deployment(deployment_id, remove_logs=remove_logs)
        return {
            "message": f"部署 {deployment_id} 已删除",
            "deployment_id": deployment_id
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"删除部署失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除部署失败: {str(e)}")


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


@router.get("/list")
async def list_deployments():
    """
    列出所有部署（返回格式适配前端）

    Returns:
        dict: {"deployments": [...]}
    """
    try:
        deployments = deploy_service.list_deployments()

        # 转换格式以匹配前端期望
        formatted_deployments = []
        for d in deployments:
            formatted_deployments.append({
                "deployment_id": d["deployment_id"],
                "model_id": d["model_path"],  # 保留旧字段（兼容性）
                "model_path": d["model_path"],  # 前端 tooltip 使用
                "endpoint": d["api_endpoint"],  # 前端期望 endpoint
                "status": d["status"],
                "created_at": d.get("started_at", 0) * 1000,  # 转换为毫秒时间戳
                "port": d["port"],
                "base_url": d["base_url"],
                "pid": d.get("pid"),
                "uptime_seconds": d.get("uptime_seconds"),
                "gpu_id": d.get("gpu_id", "N/A"),  # 修复：使用 gpu_id 而非 gpu_devices
                "served_model_name": d.get("served_model_name", ""),  # 添加模型名称
            })

        return {"deployments": formatted_deployments}

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


@router.get("/gpu-status")
async def get_gpu_status():
    """
    获取 GPU 使用状态

    示例:
        GET /api/deploy/gpu-status

    Returns:
        {
            "total_gpus": 4,
            "used_gpus": 2,
            "available_gpus": 2,
            "gpus": [
                {
                    "gpu_id": "0",
                    "status": "used",
                    "deployments": [
                        {
                            "deployment_id": "deploy-abc123",
                            "model": "Qwen2.5-7B-Instruct",
                            "status": "running"
                        }
                    ]
                },
                {
                    "gpu_id": "1",
                    "status": "available",
                    "deployments": []
                }
            ]
        }
    """
    try:
        gpu_status = deploy_service.get_gpu_status()
        return gpu_status

    except Exception as e:
        logger.error(f"获取 GPU 状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取 GPU 状态失败: {str(e)}")
