# Copyright (c) Alibaba, Inc. and its affiliates.
"""
部署 API 端点
提供模型部署服务相关的 RESTful API
"""
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from services.deploy_service import DeployService

router = APIRouter()
deploy_service = DeployService()


# 请求/响应模型
class DeployRequest(BaseModel):
    """部署请求模型"""
    model: str = Field(..., description="模型 ID 或路径")
    model_type: Optional[str] = Field(None, description="模型类型")
    template: Optional[str] = Field(None, description="模板类型")
    port: int = Field(8000, description="服务端口")
    host: str = Field("0.0.0.0", description="服务地址")
    gpu_id: Optional[List[str]] = Field(["0"], description="GPU ID 列表")
    ckpt_dir: Optional[str] = Field(None, description="检查点目录 (LoRA)")
    max_model_len: Optional[int] = Field(None, description="最大模型长度")
    max_batch_size: Optional[int] = Field(None, description="最大批次大小")
    served_model_name: Optional[str] = Field(None, description="服务模型名称")
    more_params: Optional[Dict[str, Any]] = Field(None, description="其他参数")


class DeployResponse(BaseModel):
    """部署响应模型"""
    deployment_id: str = Field(..., description="部署 ID")
    status: str = Field(..., description="部署状态")
    message: str = Field(..., description="消息")
    port: int = Field(..., description="服务端口")
    endpoint: Optional[str] = Field(None, description="服务端点")


class DeploymentStatus(BaseModel):
    """部署状态模型"""
    deployment_id: str
    model: str
    status: str  # starting/running/stopped/failed
    port: int
    host: str
    endpoint: Optional[str] = None
    start_time: Optional[str] = None
    log_file: Optional[str] = None


# API 端点
@router.post("/start", response_model=DeployResponse, summary="启动部署服务")
async def start_deployment(
    request: DeployRequest,
    background_tasks: BackgroundTasks
):
    """
    启动模型部署服务

    - **model**: 模型 ID 或本地路径
    - **port**: 服务端口
    - **host**: 服务地址
    - 返回部署 ID 和端点信息
    """
    try:
        # 检查端口是否被占用
        if deploy_service.is_port_in_use(request.port):
            raise HTTPException(
                status_code=400,
                detail=f"端口 {request.port} 已被占用"
            )

        # 创建部署任务
        deployment_id = deploy_service.create_deployment(
            model=request.model,
            model_type=request.model_type,
            template=request.template,
            port=request.port,
            host=request.host,
            gpu_id=request.gpu_id,
            ckpt_dir=request.ckpt_dir,
            max_model_len=request.max_model_len,
            max_batch_size=request.max_batch_size,
            served_model_name=request.served_model_name,
            more_params=request.more_params
        )

        # 在后台启动部署
        background_tasks.add_task(deploy_service.run_deployment, deployment_id)

        # 构建端点 URL
        endpoint = f"http://{request.host}:{request.port}"

        return DeployResponse(
            deployment_id=deployment_id,
            status="starting",
            message="部署服务正在启动",
            port=request.port,
            endpoint=endpoint
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{deployment_id}", response_model=DeploymentStatus, summary="获取部署状态")
async def get_deployment_status(deployment_id: str):
    """
    获取部署服务状态

    - **deployment_id**: 部署 ID
    - 返回部署的当前状态
    """
    try:
        status = deploy_service.get_deployment_status(deployment_id)
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"部署 {deployment_id} 不存在"
            )
        return DeploymentStatus(**status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{deployment_id}", summary="停止部署服务")
async def stop_deployment(deployment_id: str):
    """
    停止部署服务

    - **deployment_id**: 部署 ID
    """
    try:
        success = deploy_service.stop_deployment(deployment_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"部署 {deployment_id} 不存在或无法停止"
            )

        return {
            "code": 0,
            "message": "部署服务已停止",
            "data": {"deployment_id": deployment_id}
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", summary="获取所有部署")
async def list_deployments():
    """
    获取所有部署服务列表
    """
    try:
        deployments = deploy_service.list_deployments()
        return {
            "code": 0,
            "message": "success",
            "data": {"deployments": deployments}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/{deployment_id}", summary="获取部署日志")
async def get_deployment_logs(
    deployment_id: str,
    lines: int = 50
):
    """
    获取部署服务日志

    - **deployment_id**: 部署 ID
    - **lines**: 读取的行数
    """
    try:
        logs = deploy_service.get_deployment_logs(deployment_id, lines)
        if logs is None:
            raise HTTPException(
                status_code=404,
                detail=f"部署 {deployment_id} 的日志不存在"
            )

        return {
            "code": 0,
            "message": "success",
            "data": {
                "deployment_id": deployment_id,
                "logs": logs
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/health/{deployment_id}", summary="健康检查")
async def check_deployment_health(deployment_id: str):
    """
    检查部署服务健康状态

    - **deployment_id**: 部署 ID
    """
    try:
        health = await deploy_service.check_health(deployment_id)
        return {
            "code": 0,
            "message": "success",
            "data": health
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
