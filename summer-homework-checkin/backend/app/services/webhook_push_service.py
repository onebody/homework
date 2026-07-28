"""Webhook 消息推送服务：打卡事件推送到钉钉 / 企业微信群机器人。

设计要点：
- push_checkin_event 为对外唯一入口，内部起 daemon 线程异步执行，
  任何异常只写 PushLog，绝不影响打卡主流程；
- 推送开关、事件类型过滤、限频均由数据库单行配置 PushConfig 控制；
- 日志（PushLog）不落 Webhook URL，避免敏感信息泄露。
"""
import json
import re
import threading
import urllib.request
import urllib.error
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

from ..models import PushConfig, PushLog, CheckIn, ChallengeCheckIn
from ..database import SessionLocal
from ..config import DEFAULT_PUSH_TEMPLATES
from ..utils.timeutil import now_local

# 合法 Webhook 前缀（防 SSRF 兼防配错）
_URL_PREFIXES = {
    "dingtalk": "https://oapi.dingtalk.com/robot/send",
    "wechat": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send",
}

_EVENT_LABELS = {"pending": "待审核", "submitted": "待审核", "approved": "已通过", "rejected": "已拒绝"}
_TYPE_LABELS = {"normal": "正常打卡", "makeup": "补卡"}

# 内置默认模板（预填到配置供后台编辑；标题/正文被清空时推送仍回退到这里）
_DEFAULT_TEMPLATES = DEFAULT_PUSH_TEMPLATES

# 各类模板支持的占位符（供后台帮助文案/预览校验参考）
_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


def _render(tpl: str, vars: dict) -> str:
    """安全渲染模板：已知占位符替换，未知占位符原样保留；
    替换后为空的行自动清理（如无照片时的 {photo_line} 行）。"""
    def sub(m):
        key = m.group(1)
        return str(vars[key]) if key in vars else m.group(0)
    text = _PLACEHOLDER_RE.sub(sub, tpl or "")
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln.strip())


def _finalize(cfg, title: str, body: str) -> tuple[str, str]:
    """拼接 标题+正文+签名，返回 (日志摘要标题, 完整推送文本)。"""
    parts = [title]
    if body:
        parts.append(body)
    sig = (getattr(cfg, "tpl_signature", None) or "").strip()
    if sig:
        parts.append(sig)
    return title, "\n".join(parts)


def get_config(db):
    """读取推送配置（单行表，不存在则懒创建默认行）。

    旧库升级场景：模板字段为 NULL（从未保存过）时补种默认值，
    保证后台界面总能看到可编辑的预填内容。
    """
    cfg = db.query(PushConfig).first()
    if not cfg:
        cfg = PushConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    elif cfg.tpl_daily_title is None and cfg.tpl_daily_body is None \
            and cfg.tpl_challenge_title is None and cfg.tpl_challenge_body is None \
            and cfg.tpl_signature is None:
        cfg.tpl_daily_title = _DEFAULT_TEMPLATES["daily_title"]
        cfg.tpl_daily_body = _DEFAULT_TEMPLATES["daily_body"]
        cfg.tpl_challenge_title = _DEFAULT_TEMPLATES["challenge_title"]
        cfg.tpl_challenge_body = _DEFAULT_TEMPLATES["challenge_body"]
        cfg.tpl_signature = _DEFAULT_TEMPLATES["signature"]
        db.commit()
        db.refresh(cfg)
    return cfg


def validate_webhook_url(channel: str, url: str) -> str | None:
    """严格校验 Webhook URL（scheme/host/path 分段比对），合法返回 None，非法返回错误说明。"""
    prefix = _URL_PREFIXES.get(channel)
    if not prefix:
        return f"未知渠道：{channel}"
    name = "钉钉" if channel == "dingtalk" else "企业微信"
    try:
        parsed = urlparse(url)
        expected = urlparse(prefix)
    except ValueError:
        return f"{name} Webhook URL 非法"
    # 逐段比对，避免 startswith 在解析歧义 URL 上被绕过（如 userinfo/端口把戏）
    if parsed.scheme != "https" or parsed.netloc != expected.netloc \
            or parsed.path != expected.path:
        return f"{name} Webhook URL 必须以 {prefix} 开头"
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """禁止重定向：防止白名单域名经开放重定向跳到内网地址（SSRF）。"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _send_webhook(url: str, text: str) -> str | None:
    """POST 文本消息到机器人 Webhook（钉钉/企微协议同形），成功返回 None，失败返回错误摘要。"""
    payload = json.dumps(
        {"msgtype": "text", "text": {"content": text}}, ensure_ascii=False
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with _opener.open(req, timeout=10) as resp:
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


def _daily_vars(cfg, ci) -> dict:
    """日常打卡可用占位符。"""
    photo = ""
    if cfg.public_base_url and ci.photo_path:
        photo = f"{cfg.public_base_url.rstrip('/')}{ci.photo_url}"
    return {
        "nickname": ci.user.nickname if ci.user else f"用户{ci.user_id}",
        "type": _TYPE_LABELS.get(ci.check_type, ci.check_type),
        "status": _EVENT_LABELS.get(ci.review_status, ci.review_status),
        "time": ci.check_time.strftime("%Y-%m-%d %H:%M"),
        "photo": photo,
        "photo_line": f"照片：{photo}" if photo else "",
        "geo_warn": "⚠️ 位置异常：距常用位置较远，请关注" if ci.geo_flag else "",
    }


def _challenge_vars(cfg, ci) -> dict:
    """闯关打卡可用占位符。"""
    points = ci.task.reward_points if ci.task else ""
    reason = ci.review_note or ""
    approved = ci.review_status == "approved"
    rejected = ci.review_status == "rejected"
    return {
        "nickname": ci.user.nickname if ci.user else f"用户{ci.user_id}",
        "task": ci.task.name if ci.task else f"任务{ci.task_id}",
        "status": _EVENT_LABELS.get(ci.review_status, ci.review_status),
        "time": ci.created_at.strftime("%Y-%m-%d %H:%M"),
        "points": points if approved else "",
        "points_line": f"奖励积分：{points}" if approved and points != "" else "",
        "reason": reason if rejected else "",
        "reason_line": f"原因：{reason}" if rejected and reason else "",
    }


def _build_text(cfg, ci) -> tuple[str, str]:
    """组装日常打卡推送文本（后台可自定义模板），返回 (标题摘要, 完整文本)。"""
    vars = _daily_vars(cfg, ci)
    title = _render(getattr(cfg, "tpl_daily_title", None) or _DEFAULT_TEMPLATES["daily_title"], vars)
    body = _render(getattr(cfg, "tpl_daily_body", None) or _DEFAULT_TEMPLATES["daily_body"], vars)
    return _finalize(cfg, title, body)


def _build_challenge_text(cfg, ci) -> tuple[str, str]:
    """组装闯关打卡推送文本（后台可自定义模板），返回 (标题摘要, 完整文本)。"""
    vars = _challenge_vars(cfg, ci)
    title = _render(getattr(cfg, "tpl_challenge_title", None) or _DEFAULT_TEMPLATES["challenge_title"], vars)
    body = _render(getattr(cfg, "tpl_challenge_body", None) or _DEFAULT_TEMPLATES["challenge_body"], vars)
    return _finalize(cfg, title, body)


# 预览用样例数据（不读真实用户数据，避免预览泄露隐私）
_SAMPLE_VARS = {
    "daily": {
        "nickname": "小航", "type": "正常打卡", "status": "待审核",
        "time": "2026-08-01 09:30",
        "photo": "https://example.com/uploads/2/c_demo.jpg",
        "photo_line": "照片：https://example.com/uploads/2/c_demo.jpg",
        "geo_warn": "⚠️ 位置异常：距常用位置较远，请关注",
    },
    "challenge": {
        "nickname": "小航", "task": "背诵古诗10首", "status": "已通过",
        "time": "2026-08-01 09:30",
        "points": 50, "points_line": "奖励积分：50",
        "reason": "照片不清晰", "reason_line": "原因：照片不清晰",
    },
}


def render_preview(kind: str, title_tpl: str, body_tpl: str, signature: str) -> str:
    """用样例数据渲染模板预览（供后台编辑时查看效果，不落库不外发）。"""
    vars = _SAMPLE_VARS.get(kind) or _SAMPLE_VARS["daily"]
    title = _render(title_tpl or _DEFAULT_TEMPLATES[f"{kind}_title"], vars)
    body = _render(body_tpl or _DEFAULT_TEMPLATES[f"{kind}_body"], vars)
    parts = [title]
    if body:
        parts.append(body)
    if (signature or "").strip():
        parts.append(signature.strip())
    return "\n".join(parts)


def validate_template_title(title_tpl: str) -> str | None:
    """检查自定义标题模板是否含钉钉机器人关键词，缺失时返回提示文案（软警告，不阻止保存）。

    系统严格按模板发送、不自动补全；若钉钉机器人设置了关键词过滤，
    不含关键词的消息会被钉钉拒收，故仅提醒管理员自行确认。
    """
    if title_tpl and "暑假打卡" not in title_tpl:
        return "标题模板不含关键词「暑假打卡」：若钉钉机器人设置了该关键词过滤，消息可能发送失败，请确认机器人安全设置"
    return None


def _channels(cfg):
    if cfg.dingtalk_url:
        yield "dingtalk", cfg.dingtalk_url
    if cfg.wechat_url:
        yield "wechat", cfg.wechat_url


def _do_push(checkin_id: int, event_type: str, kind: str = "daily"):
    """线程体：读配置→过滤→限频→逐渠道发送并记日志。全程不抛异常。

    kind=daily 为日常打卡；kind=challenge 为闯关打卡（受 push_on_challenge 独立开关控制，
    事件类型过滤沿用 push_on_submitted/approved/rejected，日志事件加 ch_ 前缀）。
    """
    is_challenge = kind == "challenge"
    log_event = f"ch_{event_type}" if is_challenge else event_type
    db = SessionLocal()
    try:
        cfg = get_config(db)
        if not cfg.enabled:
            return
        if is_challenge and not getattr(cfg, "push_on_challenge", False):
            return
        if not getattr(cfg, f"push_on_{event_type}", False):
            return
        ci = db.get(ChallengeCheckIn if is_challenge else CheckIn, checkin_id)
        if not ci:
            return
        title, text = (_build_challenge_text if is_challenge else _build_text)(cfg, ci)
        for channel, url in _channels(cfg):
            if _rate_limited(db, cfg):
                _log(db, channel, log_event, title, "skipped",
                     f"触发限频（每分钟最多 {cfg.rate_limit_per_min} 条）")
                continue
            # 严格按模板渲染结果发送，不做任何自动补全或前后缀修改
            err = _send_webhook(url, text)
            _log(db, channel, log_event, title,
                 "failed" if err else "success", err)
    except Exception as e:
        # 兜底：推送模块自身异常也要留痕，且不影响主流程
        try:
            _log(db, "-", log_event, f"{kind}-checkin#{checkin_id}", "failed",
                 f"推送模块异常 {type(e).__name__}: {e}"[:500])
        except Exception:
            pass
    finally:
        db.close()


def push_checkin_event(checkin_id: int, event_type: str):
    """对外入口：后台线程异步推送日常打卡事件（submitted|approved|rejected）。"""
    threading.Thread(
        target=_do_push, args=(checkin_id, event_type), daemon=True
    ).start()


def push_challenge_event(checkin_id: int, event_type: str):
    """对外入口：后台线程异步推送闯关打卡事件（submitted|approved|rejected）。"""
    threading.Thread(
        target=_do_push, args=(checkin_id, event_type, "challenge"), daemon=True
    ).start()


def send_test(db, channel: str) -> str | None:
    """同步发送一条测试消息，成功返回 None，失败返回错误说明（供后台测试按钮）。

    用当前已保存的日常打卡模板渲染样例数据，严格按模板发送（不加任何
    额外前后缀），测试收到的即真实推送效果。
    """
    cfg = get_config(db)
    url = cfg.dingtalk_url if channel == "dingtalk" else cfg.wechat_url
    if not url:
        return "该渠道尚未配置 Webhook URL，请先保存配置"
    err = validate_webhook_url(channel, url)
    if err:
        return err
    text = render_preview(
        "daily",
        (cfg.tpl_daily_title or "").strip(),
        (cfg.tpl_daily_body or "").strip(),
        (cfg.tpl_signature or "").strip(),
    )
    err = _send_webhook(url, text)
    _log(db, channel, "test", "测试推送（当前模板渲染）", "failed" if err else "success", err)
    return err
