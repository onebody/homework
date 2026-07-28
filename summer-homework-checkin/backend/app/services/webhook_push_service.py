"""Webhook 消息推送服务：打卡事件推送到钉钉 / 企业微信群机器人。

设计要点：
- push_checkin_event 为对外唯一入口，内部起 daemon 线程异步执行，
  任何异常只写 PushLog，绝不影响打卡主流程；
- 推送开关、事件类型过滤、限频均由数据库单行配置 PushConfig 控制；
- 日志（PushLog）不落 Webhook URL，避免敏感信息泄露。
"""
import json
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

from ..models import PushConfig, PushLog, CheckIn
from ..database import SessionLocal
from ..utils.timeutil import now_local

# 合法 Webhook 前缀（防 SSRF 兼防配错）
_URL_PREFIXES = {
    "dingtalk": "https://oapi.dingtalk.com/robot/send",
    "wechat": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send",
}

_EVENT_LABELS = {"submitted": "待审核", "approved": "已通过", "rejected": "已拒绝"}
_TYPE_LABELS = {"normal": "正常打卡", "makeup": "补卡"}


def get_config(db):
    """读取推送配置（单行表，不存在则懒创建默认行）。"""
    cfg = db.query(PushConfig).first()
    if not cfg:
        cfg = PushConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def validate_webhook_url(channel: str, url: str) -> str | None:
    """校验 Webhook URL 前缀，合法返回 None，非法返回错误说明。"""
    prefix = _URL_PREFIXES.get(channel)
    if not prefix:
        return f"未知渠道：{channel}"
    if not url.startswith(prefix):
        name = "钉钉" if channel == "dingtalk" else "企业微信"
        return f"{name} Webhook URL 必须以 {prefix} 开头"
    return None


def _send_webhook(url: str, text: str) -> str | None:
    """POST 文本消息到机器人 Webhook（钉钉/企微协议同形），成功返回 None，失败返回错误摘要。"""
    payload = json.dumps(
        {"msgtype": "text", "text": {"content": text}}, ensure_ascii=False
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        # 两家协议均以 errcode==0 表示成功
        if body.get("errcode", 0) != 0:
            return f"errcode={body.get('errcode')} {body.get('errmsg', '')}"[:500]
        return None
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {e.reason}"[:500]
    except Exception as e:
        return f"{type(e).__name__}: {e}"[:500]


def _log(db, channel: str, event_type: str, title: str, status: str, error: str = None):
    db.add(PushLog(channel=channel, event_type=event_type, title=(title or "")[:250],
                   status=status, error=error))
    db.commit()


def _rate_limited(db, cfg) -> bool:
    """近 60 秒成功推送条数达到上限则限频。"""
    if not cfg.rate_limit_per_min or cfg.rate_limit_per_min <= 0:
        return False
    since = now_local() - timedelta(seconds=60)
    n = db.query(PushLog).filter(
        PushLog.status == "success", PushLog.created_at >= since
    ).count()
    return n >= cfg.rate_limit_per_min


def _build_text(cfg, ci) -> tuple[str, str]:
    """组装推送文本，返回 (标题摘要, 完整文本)。"""
    nickname = ci.user.nickname if ci.user else f"用户{ci.user_id}"
    type_label = _TYPE_LABELS.get(ci.check_type, ci.check_type)
    status_label = _EVENT_LABELS.get(ci.review_status, ci.review_status)
    title = f"【暑假打卡】{nickname} {type_label} {status_label}"
    lines = [title, f"时间：{ci.check_time.strftime('%Y-%m-%d %H:%M')}"]
    if ci.geo_flag:
        lines.append("⚠️ 位置异常：距常用位置较远，请关注")
    if cfg.public_base_url and ci.photo_path:
        base = cfg.public_base_url.rstrip("/")
        lines.append(f"照片：{base}{ci.photo_url}")
    return title, "\n".join(lines)


def _channels(cfg):
    if cfg.dingtalk_url:
        yield "dingtalk", cfg.dingtalk_url
    if cfg.wechat_url:
        yield "wechat", cfg.wechat_url


def _do_push(checkin_id: int, event_type: str):
    """线程体：读配置→过滤→限频→逐渠道发送并记日志。全程不抛异常。"""
    db = SessionLocal()
    try:
        cfg = get_config(db)
        if not cfg.enabled:
            return
        if not getattr(cfg, f"push_on_{event_type}", False):
            return
        ci = db.get(CheckIn, checkin_id)
        if not ci:
            return
        title, text = _build_text(cfg, ci)
        for channel, url in _channels(cfg):
            if _rate_limited(db, cfg):
                _log(db, channel, event_type, title, "skipped",
                     f"触发限频（每分钟最多 {cfg.rate_limit_per_min} 条）")
                continue
            err = _send_webhook(url, text)
            _log(db, channel, event_type, title,
                 "failed" if err else "success", err)
    except Exception as e:
        # 兜底：推送模块自身异常也要留痕，且不影响主流程
        try:
            _log(db, "-", event_type, f"checkin#{checkin_id}", "failed",
                 f"推送模块异常 {type(e).__name__}: {e}"[:500])
        except Exception:
            pass
    finally:
        db.close()


def push_checkin_event(checkin_id: int, event_type: str):
    """对外唯一入口：后台线程异步推送打卡事件（submitted|approved|rejected）。"""
    threading.Thread(
        target=_do_push, args=(checkin_id, event_type), daemon=True
    ).start()


def send_test(db, channel: str) -> str | None:
    """同步发送一条测试消息，成功返回 None，失败返回错误说明（供后台测试按钮）。"""
    cfg = get_config(db)
    url = cfg.dingtalk_url if channel == "dingtalk" else cfg.wechat_url
    if not url:
        return "该渠道尚未配置 Webhook URL，请先保存配置"
    err = validate_webhook_url(channel, url)
    if err:
        return err
    now = now_local().strftime("%Y-%m-%d %H:%M:%S")
    err = _send_webhook(url, f"【暑假打卡】测试消息\n推送配置正常，发送时间：{now}")
    _log(db, channel, "test", "测试推送", "failed" if err else "success", err)
    return err
