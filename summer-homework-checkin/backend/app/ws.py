"""WebSocket 实时通知通道（/api/ws/notifications）。

凭证经 ?token= 传递（浏览器 WS 握手无法设置请求头），复用 security.decode_token。
推送为 fire-and-forget：落库优先，推送失败静默，前端断线时降级 30s 轮询
/api/learning/notifications/unread 保证通知不丢。
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .security import decode_token

router = APIRouter(tags=["ws"])

# 心跳间隔（秒）：剔除死连接，防止代理空闲断链
HEARTBEAT_SECONDS = 30


class ConnectionManager:
    """user_id -> 活跃 WebSocket 集合；disconnect 一律在 finally 调用防泄漏。"""

    def __init__(self):
        self._conns: dict = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self._conns.setdefault(user_id, set()).add(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        conns = self._conns.get(user_id)
        if conns:
            conns.discard(ws)
            if not conns:
                self._conns.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict):
        dead = []
        for ws in list(self._conns.get(user_id, ())):
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    def count(self, user_id: int) -> int:
        return len(self._conns.get(user_id, ()))


manager = ConnectionManager()

# 主事件循环引用：notify_service 在同步上下文中通过
# run_coroutine_threadsafe 调度推送协程（跨线程安全）
_loop: asyncio.AbstractEventLoop = None


@router.on_event("startup")
async def _capture_loop():
    global _loop
    _loop = asyncio.get_running_loop()


def push_notification(user_id: int, payload: dict):
    """fire-and-forget 推送入口：任何异常静默降级（轮询兜底）。"""
    if _loop is None or _loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(manager.send_to_user(user_id, payload), _loop)
    except Exception:
        pass


@router.websocket("/api/ws/notifications")
async def ws_notifications(ws: WebSocket, token: str = ""):
    """?token= 鉴权；失败以 4401 关闭（需先 accept，否则自定义码被 HTTP 403 吞掉），前端据此降级轮询。"""
    user_id = None
    if token:
        payload = decode_token(token)
        if payload:
            user_id = payload.get("uid")
    if not user_id:
        await ws.accept()
        await ws.close(code=4401)
        return
    await manager.connect(user_id, ws)
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(user_id, ws)
