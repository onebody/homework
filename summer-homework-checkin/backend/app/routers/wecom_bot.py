"""企业微信智能机器人回调接口（双向消息）。

安全说明：本接口对企微服务器开放（无后台 JWT），依赖 Token 验签 + AESKey 解密防伪造；
未配置 Token/EncodingAESKey 时直接 403，不处理任何指令。

协议（官方文档 100719/101031）：
- GET  /callback：URL 有效性验证，验签后解密 echostr，1 秒内裸文本返回明文；
- POST /callback：接收 {"encrypt": "..."}，验签解密得消息明文 JSON，
  被动回复用户消息必须用 stream 类型（一次性 finish=true），回复体加密后返回。
"""
import json
import re
import time
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PushLog
from ..services.webhook_push_service import get_config
from ..services.dingtalk_bot_service import handle_command, HELP_TEXT
from ..utils import wecom_crypto

router = APIRouter(prefix="/api/wecom", tags=["wecom-bot"])

# msgid 排重：企微网络重试会重复回调同一消息，避免审核等指令重复执行
_SEEN_MSGIDS: OrderedDict[str, None] = OrderedDict()
_SEEN_LIMIT = 512

# 消息 content 开头的 @机器人名 前缀（如 "@打卡助手 统计"）
_AT_PREFIX = re.compile(r"^@\S+\s*")


def _get_bot_config(db: Session):
    """读取企微机器人配置，未配置时 403。"""
    cfg = get_config(db)
    token = (cfg.wecom_bot_token or "").strip()
    aes_key = (cfg.wecom_bot_aes_key or "").strip()
    if not token or not aes_key:
        raise HTTPException(status_code=403, detail="未配置企微机器人 Token/EncodingAESKey，双向消息未启用")
    return cfg, token, aes_key


def _seen_msgid(msgid: str) -> bool:
    """LRU 排重，重复返回 True。"""
    if not msgid:
        return False
    if msgid in _SEEN_MSGIDS:
        _SEEN_MSGIDS.move_to_end(msgid)
        return True
    _SEEN_MSGIDS[msgid] = None
    while len(_SEEN_MSGIDS) > _SEEN_LIMIT:
        _SEEN_MSGIDS.popitem(last=False)
    return False


@router.get("/callback")
def wecom_verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
    db: Session = Depends(get_db),
):
    """企微后台保存回调配置时的 URL 有效性验证。"""
    _, token, aes_key = _get_bot_config(db)
    if not wecom_crypto.verify_signature(token, timestamp, nonce, echostr, msg_signature):
        raise HTTPException(status_code=403, detail="签名校验失败")
    try:
        plain = wecom_crypto.decrypt(aes_key, echostr)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    # 必须裸文本返回明文（不能带引号/BOM/换行）
    return PlainTextResponse(plain)


@router.post("/callback")
async def wecom_callback(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    db: Session = Depends(get_db),
):
    """接收群/单聊消息，执行指令并加密被动回复（stream 一次性）。"""
    _cfg, token, aes_key = _get_bot_config(db)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="请求体不是合法 JSON")
    encrypt_b64 = body.get("encrypt") or ""
    if not wecom_crypto.verify_signature(token, timestamp, nonce, encrypt_b64, msg_signature):
        raise HTTPException(status_code=403, detail="签名校验失败")
    try:
        plain = wecom_crypto.decrypt(aes_key, encrypt_b64)
        msg = json.loads(plain)
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=403, detail="消息解密失败")

    msgid = str(msg.get("msgid") or "")
    if _seen_msgid(msgid):
        # 网络重试导致的重复回调，直接回空包（企微不再重试）
        return {}

    if msg.get("msgtype") == "text":
        content = _AT_PREFIX.sub("", ((msg.get("text") or {}).get("content") or "").strip())
    else:
        content = ""  # 非文本消息统一回帮助文案
    sender = ((msg.get("from") or {}).get("userid") or "群成员").strip()

    reply = handle_command(db, _cfg, sender, content) if content else HELP_TEXT

    # 指令留痕（不落 Token/密钥，仅记录指令摘要），与钉钉双向一致
    db.add(PushLog(channel="wechat", event_type="command",
                   title=f"{sender}：{content}"[:250], status="success"))
    db.commit()

    # 被动回复用户消息仅支持 stream 类型，一次性回复 finish=true
    reply_plain = json.dumps({
        "msgtype": "stream",
        "stream": {"id": msgid or nonce, "finish": True, "content": reply},
    }, ensure_ascii=False)
    reply_encrypt = wecom_crypto.encrypt(aes_key, reply_plain)
    reply_ts = str(int(time.time()))
    return {
        "encrypt": reply_encrypt,
        "msgsignature": wecom_crypto.compute_signature(token, reply_ts, nonce, reply_encrypt),
        "timestamp": int(reply_ts),
        "nonce": nonce,
    }
