"""钉钉机器人 Outgoing 回调路由（双向消息入口）。

安全说明：本接口对钉钉服务器开放（无后台 JWT），依赖 Outgoing Token 验签防伪造；
未配置 Token 时直接 403，不处理任何指令。
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PushLog
from ..services.webhook_push_service import get_config
from ..services.dingtalk_bot_service import verify_signature, handle_command

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dingtalk", tags=["dingtalk-bot"])


@router.post("/outgoing")
async def dingtalk_outgoing(request: Request, db: Session = Depends(get_db)):
    cfg = get_config(db)
    
    # 调试日志：记录钉钉发送的所有请求头（用于排查签名验证失败）
    logger.info(f"[钉钉回调] 收到请求，来源IP: {request.client.host if request.client else 'unknown'}")
    logger.debug(f"[钉钉回调] 请求头: timestamp={request.headers.get('timestamp')}, "
                 f"sign={request.headers.get('sign')}, token={request.headers.get('token')}")
    
    err = verify_signature(
        cfg,
        request.headers.get("timestamp"),
        request.headers.get("sign"),
        request.headers.get("token"),
    )
    if err:
        logger.warning(f"[钉钉回调] 签名验证失败: {err}")
        logger.warning(f"[钉钉回调] 实际收到的 headers: "
                      f"timestamp={request.headers.get('timestamp')}, "
                      f"sign={request.headers.get('sign')}, "
                      f"token={request.headers.get('token')}")
        raise HTTPException(status_code=403, detail=err)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体不是合法 JSON")

    content = ((body.get("text") or {}).get("content") or "").strip()
    sender = (body.get("senderNick") or "群成员").strip()

    reply = handle_command(db, cfg, sender, content)

    # 指令留痕（不落 URL/Token，仅记录指令摘要）
    db.add(PushLog(channel="dingtalk", event_type="command",
                   title=f"{sender}：{content}"[:250], status="success"))
    db.commit()

    # 响应体即回复消息，钉钉自动回贴到群内
    return {"msgtype": "text", "text": {"content": reply}}
