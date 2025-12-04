"""
MS-SWIFT Custom UI - FastAPI Backend
主应用入口
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os
from pathlib import Path

# 创建 FastAPI 应用
app = FastAPI(
    title="MS-SWIFT Custom UI API",
    description="自定义 Web UI for MS-SWIFT 模型训练和推理",
    version="1.0.0"
)

# CORS 配置 - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入路由
from api import train, infer, deploy, model, data

# 注册路由
app.include_router(data.router, prefix="/api/data", tags=["数据管理"])
app.include_router(train.router, prefix="/api/train", tags=["训练"])
app.include_router(infer.router, prefix="/api/infer", tags=["推理"])
app.include_router(deploy.router, prefix="/api/deploy", tags=["部署"])
app.include_router(model.router, prefix="/api/model", tags=["模型管理"])

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

manager = ConnectionManager()

# WebSocket 端点 - 用于实时日志推送
@app.websocket("/ws/logs/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await manager.connect(websocket, task_id)
    try:
        while True:
            # 保持连接，等待客户端消息
            data = await websocket.receive_text()
            # 这里可以处理客户端发来的消息
    except WebSocketDisconnect:
        manager.disconnect(task_id)

# 根路径
@app.get("/")
async def root():
    return {
        "message": "MS-SWIFT Custom UI API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# 健康检查
@app.get("/health")
async def health():
    return {"status": "healthy"}

# 如果前端已构建，提供静态文件服务
frontend_build_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_build_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_build_path / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = frontend_build_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_build_path / "index.html")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
