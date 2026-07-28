"""钉钉机器人双向消息服务（Outgoing 回调）。

设计要点：
- 群里 @机器人 发送指令，钉钉 POST 到 /api/dingtalk/outgoing，
  接口直接在 HTTP 响应体返回消息，钉钉自动回贴到群内；
- 验签：优先「加签」模式（header 携带 timestamp + sign，
  sign = base64(HMAC-SHA256(timestamp + "\n" + token, key=token))），
  兼容 header 直接携带 token 明文比对的旧模式；未配置 Token 时接口拒绝服务；
- 支持指令：统计/今日、待审核、查询 <昵称>、通过/拒绝 <打卡ID>（需开启群内审核开关）；
- 群内审核直接复用 checkin_service.approve/reject，与后台审核完全同一逻辑。
"""
import base64
import hashlib
import hmac
import time
from datetime import date

from ..models import User, CheckIn

_TYPE_LABELS = {"normal": "正常打卡", "makeup": "补卡"}

HELP_TEXT = (
    "我能听懂这些指令：\n"
    "· 统计 —— 今日打卡概况\n"
    "· 待审核 —— 待审核打卡列表\n"
    "· 查询 <昵称> —— 查看学生打卡情况\n"
    "· 通过 <打卡ID> [备注] —— 审核通过\n"
    "· 拒绝 <打卡ID> [原因] —— 审核拒绝"
)


def verify_signature(cfg, timestamp: str | None, sign: str | None, token_header: str | None) -> str | None:
    """校验钉钉 Outgoing 请求签名，合法返回 None，非法返回错误说明。"""
    token = (cfg.outgoing_token or "").strip()
    if not token:
        return "未配置 Outgoing Token，双向消息未启用"
    if timestamp and sign:
        # 加签模式：时间戳有效期 1 小时
        try:
            ts_ms = int(timestamp)
        except ValueError:
            return "timestamp 非法"
        if abs(time.time() * 1000 - ts_ms) > 3600 * 1000:
            return "timestamp 已过期"
        raw = f"{timestamp}\n{token}".encode("utf-8")
        expected = base64.b64encode(
            hmac.new(token.encode("utf-8"), raw, hashlib.sha256).digest()
        ).decode("utf-8")
        if not hmac.compare_digest(expected, sign):
            return "签名校验失败"
        return None
    if token_header:
        # 旧模式：header 直接携带 token
        if not hmac.compare_digest(token, token_header):
            return "Token 校验失败"
        return None
    return "缺少验签信息（timestamp/sign 或 token）"


def handle_command(db, cfg, sender_nick: str, content: str) -> str:
    """解析并执行群指令，返回回复文本。"""
    text = (content or "").strip()
    if not text:
        return HELP_TEXT
    parts = text.split(None, 1)
    cmd, arg = parts[0], (parts[1].strip() if len(parts) > 1 else "")

    if cmd in ("统计", "今日", "今天"):
        return _cmd_stats(db)
    if cmd in ("待审核", "待审", "审核列表"):
        return _cmd_pending(db)
    if cmd == "查询":
        return _cmd_student(db, arg)
    if cmd in ("通过", "拒绝"):
        return _cmd_review(db, cfg, cmd, arg, sender_nick)
    return HELP_TEXT


def _cmd_stats(db) -> str:
    today = date.today()
    q = db.query(CheckIn).filter(CheckIn.check_date == today)
    total = q.count()
    users = {c.user_id for c in q.all()}
    pending = db.query(CheckIn).filter(CheckIn.review_status == "pending").count()
    geo_warn = db.query(CheckIn).filter(
        CheckIn.review_status == "pending", CheckIn.geo_flag.is_(True)
    ).count()
    students = db.query(User).filter(User.role == "student").count()
    lines = [
        f"【今日打卡统计】{today.strftime('%Y-%m-%d')}",
        f"打卡人数：{len(users)} / {students}",
        f"打卡记录：{total} 条",
        f"待审核：{pending} 条" + (f"（含位置异常 {geo_warn} 条 ⚠️）" if geo_warn else ""),
    ]
    return "\n".join(lines)


def _cmd_pending(db) -> str:
    rows = (
        db.query(CheckIn)
        .filter(CheckIn.review_status == "pending")
        .order_by(CheckIn.id.asc())
        .limit(10)
        .all()
    )
    if not rows:
        return "当前没有待审核的打卡记录 🎉"
    lines = [f"【待审核打卡】共 {len(rows)} 条（最多显示 10 条）"]
    for c in rows:
        nick = c.user.nickname if c.user else f"用户{c.user_id}"
        flag = " ⚠️位置异常" if c.geo_flag else ""
        lines.append(
            f"#{c.id} {nick} {_TYPE_LABELS.get(c.check_type, c.check_type)} "
            f"{c.check_time.strftime('%m-%d %H:%M')}{flag}"
        )
    lines.append("回复「通过 <ID>」或「拒绝 <ID> 原因」可直接审核")
    return "\n".join(lines)


def _cmd_student(db, arg: str) -> str:
    if not arg:
        return "用法：查询 <学生昵称>"
    matches = (
        db.query(User)
        .filter(User.role == "student", User.nickname.contains(arg))
        .limit(5)
        .all()
    )
    if not matches:
        return f"未找到昵称包含「{arg}」的学生"
    if len(matches) > 1:
        names = "、".join(u.nickname for u in matches)
        return f"找到多名学生：{names}\n请用完整昵称再查一次"
    u = matches[0]
    last = (
        db.query(CheckIn)
        .filter(CheckIn.user_id == u.id)
        .order_by(CheckIn.id.desc())
        .first()
    )
    lines = [
        f"【{u.nickname}】打卡情况",
        f"连续打卡：{u.current_streak or 0} 天（最长 {u.longest_streak or 0} 天）",
        f"累计有效：{u.effective_checkins or 0} 次",
        f"积分余额：{u.points or 0} 分",
    ]
    if last:
        status = {"pending": "待审核", "approved": "已通过", "rejected": "已拒绝"}.get(
            last.review_status, last.review_status
        )
        lines.append(
            f"最近打卡：{last.check_time.strftime('%Y-%m-%d %H:%M')} "
            f"{_TYPE_LABELS.get(last.check_type, last.check_type)}（{status}）"
        )
    else:
        lines.append("最近打卡：暂无记录")
    return "\n".join(lines)


def _cmd_review(db, cfg, action: str, arg: str, sender_nick: str) -> str:
    if not cfg.allow_bot_review:
        return "群内审核未开启，请在后台「推送配置」中打开「允许群内审核」开关"
    parts = arg.split(None, 1)
    if not parts or not parts[0].lstrip("#").isdigit():
        return f"用法：{action} <打卡ID> [{'备注' if action == '通过' else '原因'}]"
    ci_id = int(parts[0].lstrip("#"))
    note = parts[1].strip() if len(parts) > 1 else None
    ci = db.get(CheckIn, ci_id)
    if not ci:
        return f"未找到打卡记录 #{ci_id}"
    nick = ci.user.nickname if ci.user else f"用户{ci.user_id}"

    from fastapi import HTTPException
    from . import checkin_service

    note_full = f"{note}（群内审核 by {sender_nick}）" if note else f"群内审核 by {sender_nick}"
    try:
        if action == "通过":
            checkin_service.approve_checkin(db, ci, note_full)
            return f"✅ 已通过 #{ci_id}（{nick}），积分已发放"
        checkin_service.reject_checkin(db, ci, note_full)
        return f"❌ 已拒绝 #{ci_id}（{nick}）" + (f"，原因:{note}" if note else "")
    except HTTPException as e:
        return f"操作失败：{e.detail}"
