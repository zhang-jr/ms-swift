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
        """
        发送消息到指定客户端
        如果发送失败（WebSocket 已关闭），自动清理连接
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(message)
            except Exception as e:
                # WebSocket 已关闭或出错，自动清理连接
                # 这是正常情况（用户切换页面等），不打印错误日志
                self.disconnect(client_id)

    async def broadcast(self, message: str):
        """
        广播消息到所有客户端
        自动清理失败的连接
        """
        disconnected_clients = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except Exception:
                # 记录需要清理的连接
                disconnected_clients.append(client_id)

        # 清理失败的连接
        for client_id in disconnected_clients:
            self.disconnect(client_id)

manager = ConnectionManager()

# WebSocket 端点 - 用于实时日志推送（纯推送模式）
@app.websocket("/ws/logs/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    print(f"[WebSocket] 接收连接请求: task_id={task_id}")
    await manager.connect(websocket, task_id)
    print(f"[WebSocket] 连接已建立: task_id={task_id}")

    try:
        # 纯推送模式：保持连接打开，直到客户端断开或发生错误
        # 不主动接收客户端消息，避免 receive_text() 阻塞导致的超时问题
        # 服务器端通过 manager.send_message() 推送日志
        while True:
            # 每 30 秒发送一次心跳，保持连接活跃
            import asyncio
            await asyncio.sleep(30)
            try:
                await websocket.send_text('{"type": "ping"}')
            except Exception as e:
                print(f"[WebSocket] 发送心跳失败: {e}")
                break

    except WebSocketDisconnect:
        print(f"[WebSocket] 客户端断开连接: task_id={task_id}")
    except Exception as e:
        print(f"[WebSocket] 异常断开: task_id={task_id}, error={e}")
    finally:
        # 确保清理连接
        manager.disconnect(task_id)

# API 信息端点（不占用根路径）
@app.get("/api")
async def api_info():
    return {
        "message": "MS-SWIFT Custom UI API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# 健康检查
@app.get("/api/health")
async def health():
    return {"status": "healthy"}

# 如果前端已构建，提供静态文件服务
frontend_build_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_build_path.exists():
    # 挂载静态资源目录
    app.mount("/assets", StaticFiles(directory=str(frontend_build_path / "assets")), name="assets")

    # Catch-all 路由：所有非 API 请求都返回前端 index.html（支持 SPA 路由）
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # API 请求已经被前面的路由处理，这里只处理前端路由
        if full_path.startswith("api/"):
            # 如果是未匹配的 API 路径，返回 404
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="API endpoint not found")

        # 检查是否是静态文件
        file_path = frontend_build_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)

        # 否则返回 index.html（SPA 客户端路由）
        return FileResponse(frontend_build_path / "index.html")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
