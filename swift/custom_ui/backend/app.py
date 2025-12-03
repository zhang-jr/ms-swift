# Copyright (c) Alibaba, Inc. and its affiliates.
"""
MS-SWIFT Custom Web UI - FastAPI Backend
主应用入口,提供 RESTful API 替代 Gradio UI
"""
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 导入 API 路由
from api import train, infer, deploy


# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时执行
    print("🚀 MS-SWIFT Custom Web UI Backend Starting...")
    yield
    # 关闭时执行
    print("👋 MS-SWIFT Custom Web UI Backend Shutting down...")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="MS-SWIFT Custom UI API",
    description="自定义 Web UI 后端 API,用于 MS-SWIFT 模型训练、推理和部署",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置 - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 统一的响应格式
class Response:
    """统一的 API 响应格式"""

    @staticmethod
    def success(data=None, message="success"):
        """成功响应"""
        return JSONResponse(
            status_code=200,
            content={
                "code": 0,
                "message": message,
                "data": data or {}
            }
        )

    @staticmethod
    def error(message="error", code=1, status_code=400):
        """错误响应"""
        return JSONResponse(
            status_code=status_code,
            content={
                "code": code,
                "message": message,
                "data": {}
            }
        )


# 注册路由
app.include_router(train.router, prefix="/api/train", tags=["训练 Training"])
app.include_router(infer.router, prefix="/api/infer", tags=["推理 Inference"])
app.include_router(deploy.router, prefix="/api/deploy", tags=["部署 Deployment"])


# 健康检查端点
@app.get("/", summary="根路径")
async def root():
    """根路径,返回 API 信息"""
    return {
        "name": "MS-SWIFT Custom UI API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", summary="健康检查")
async def health_check():
    """健康检查端点"""
    return Response.success(
        data={"status": "healthy"},
        message="Service is running"
    )


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理器"""
    print(f"❌ Global exception: {exc}")
    return Response.error(
        message=str(exc),
        code=500,
        status_code=500
    )


if __name__ == "__main__":
    import uvicorn

    # 从环境变量获取配置
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    print(f"🌐 Starting server at http://{host}:{port}")
    print(f"📚 API docs at http://{host}:{port}/docs")

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True,  # 开发模式,生产环境应设为 False
        log_level="info"
    )
