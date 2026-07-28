from datetime import date, datetime, timezone, timedelta
import time as _time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from ..models import User, CheckIn, StudentParent, Redemption, Prize, LotteryRecord, Notification, PushLog
from ..database import get_db
from ..schemas import ReviewRequest, PushConfigIn, PushConfigOut, PushLogOut, PushTestRequest, PushTemplatePreviewIn, SiteConfigIn, SiteConfigOut
from ..config import SUMMER_START, SUMMER_END, CHECKIN_POINTS, MAKEUP_POINTS, DEFAULT_PUSH_TEMPLATES
from ..deps import require_role
from ..utils.timeutil import now_local
from ..services import checkin_service
from ..services import webhook_push_service

# 服务启动时间（用于计算运行时长）
_SERVER_START = _time.time()

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _core_stats(db: Session) -> dict:
    """stats 与 dashboard 共用的统计口径，保证两接口数据一致。

    - 打卡量类指标（有效打卡、位置异常）限定暑假统计窗口，与 summer_window 标注一致；
    - 待审核/待兑换等属于操作队列，全量统计（窗口外的待办同样需要处理）。
    """
    in_window = (CheckIn.check_date >= SUMMER_START, CheckIn.check_date <= SUMMER_END)
    return {
        "students": db.query(User).filter_by(role="student").count(),
        "parents": db.query(User).filter_by(role="parent").count(),
        "effective_checkins": db.query(CheckIn).filter(CheckIn.is_effective == True, *in_window).count(),
        "bindings": db.query(StudentParent).count(),
        "geo_risk_checkins": db.query(CheckIn).filter(CheckIn.geo_flag == True, *in_window).count(),
        "redeem_pending": db.query(Redemption).filter(Redemption.status == "pending").count(),
        "redeem_approved": db.query(Redemption).filter(Redemption.status == "fulfilled").count(),
        "redeem_rejected": db.query(Redemption).filter(Redemption.status == "rejected").count(),
        "summer_window": f"{SUMMER_START} ~ {SUMMER_END}",
    }


@router.get("/stats")
def stats(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return _core_stats(db)


@router.get("/dashboard")
def dashboard(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """富统计仪表盘：多维度统计 + 图表数据 + 系统状态。"""
    # 统一使用北京时间取「今天」，不依赖容器时区设置
    today = now_local().date()
    month_start = today.replace(day=1)

    # ---- 基础统计 ----
    total_students = db.query(User).filter_by(role="student").count()
    total_parents = db.query(User).filter_by(role="parent").count()
    total_users = total_students + total_parents

    # 本月活跃用户（本月有打卡记录的去重用户数）
    monthly_active = db.query(distinct(CheckIn.user_id)).filter(
        CheckIn.check_date >= month_start
    ).count()

    # 今日新增打卡
    today_checkins = db.query(CheckIn).filter(CheckIn.check_date == today).count()

    # 本月累计积分发放（有效打卡 * 对应积分）
    month_normal = db.query(CheckIn).filter(
        CheckIn.check_date >= month_start,
        CheckIn.is_effective == True,
        CheckIn.check_type == "normal"
    ).count()
    month_makeup = db.query(CheckIn).filter(
        CheckIn.check_date >= month_start,
        CheckIn.is_effective == True,
        CheckIn.check_type == "makeup"
    ).count()
    monthly_points_issued = month_normal * CHECKIN_POINTS + month_makeup * MAKEUP_POINTS

    # 待审核打卡 / 待处理兑换
    pending_checkins = db.query(CheckIn).filter(CheckIn.review_status == "pending").count()
    pending_redemptions = db.query(Redemption).filter(Redemption.status == "pending").count()

    # 最高连续打卡天数（取学生历史最长记录，断签不会导致数字回落）
    max_streak_month = db.query(func.max(User.longest_streak)).filter(
        User.role == "student"
    ).scalar() or 0

    # 本月平均每日打卡次数
    days_elapsed = (today - month_start).days + 1
    month_total_checkins = db.query(CheckIn).filter(
        CheckIn.check_date >= month_start
    ).count()
    avg_daily_checkins = round(month_total_checkins / days_elapsed, 1) if days_elapsed > 0 else 0

    # ---- 图表数据：近 30 天打卡趋势 ----
    trend = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        count = db.query(CheckIn).filter(CheckIn.check_date == d).count()
        trend.append({"date": str(d), "count": count})

    # ---- 图表数据：用户类型分布 ----
    user_distribution = {
        "student": total_students,
        "parent": total_parents,
        "admin": db.query(User).filter_by(role="admin").count(),
    }

    # ---- 图表数据：奖品兑换类别分布 ----
    prize_category_rows = db.query(
        Prize.category, func.count(Redemption.id)
    ).join(Redemption, Redemption.prize_id == Prize.id).group_by(Prize.category).all()
    prize_distribution = {cat: cnt for cat, cnt in prize_category_rows}

    # ---- 系统状态 ----
    uptime_seconds = int(_time.time() - _SERVER_START)
    # 最新通知
    latest_notifications = db.query(Notification).order_by(
        Notification.created_at.desc()
    ).limit(5).all()
    notifications = [
        {"id": n.id, "title": n.title, "created_at": n.created_at.strftime("%m-%d %H:%M") if n.created_at else ""}
        for n in latest_notifications
    ]

    return {
        # 基础统计
        "total_users": total_users,
        "total_students": total_students,
        "total_parents": total_parents,
        "monthly_active": monthly_active,
        "today_checkins": today_checkins,
        "monthly_points_issued": monthly_points_issued,
        "pending_checkins": pending_checkins,
        "pending_redemptions": pending_redemptions,
        "max_streak_month": max_streak_month,
        "avg_daily_checkins": avg_daily_checkins,
        # 原有字段兼容（与 /stats 共用 _core_stats 口径，保证两接口一致）
        **_core_stats(db),
        # 图表
        "trend_30d": trend,
        "user_distribution": user_distribution,
        "prize_distribution": prize_distribution,
        # 系统状态
        "system": {
            "uptime_seconds": uptime_seconds,
            "db_status": "connected",
            "notifications": notifications,
        },
    }


@router.get("/users")
def users(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    items = db.query(User).order_by(User.id).all()
    return [
        {
            "id": u.id, "username": u.username, "role": u.role, "nickname": u.nickname,
            "grade": u.grade, "phone": u.phone, "current_streak": u.current_streak,
            "longest_streak": u.longest_streak,             "effective_checkins": u.effective_checkins,
            "lottery_tickets": u.lottery_tickets, "points": u.points or 0,
            "bind_code": u.bind_code,
        }
        for u in items
    ]


@router.get("/checkins")
def checkins(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """获取打卡记录列表（包含用户昵称、审核状态）"""
    items = db.query(CheckIn).order_by(CheckIn.check_time.desc()).limit(500).all()
    return [
        {
            "id": c.id, 
            "user_id": c.user_id,
            "nickname": db.query(User).filter(User.id == c.user_id).first().nickname if db.query(User).filter(User.id == c.user_id).first() else "-",
            "check_date": str(c.check_date),
            "check_time": c.check_time.strftime("%Y-%m-%d %H:%M"), 
            "check_type": c.check_type,
            "geo_distance": c.geo_distance, 
            "geo_flag": c.geo_flag,
            "scene_check": c.scene_check, 
            "review_status": c.review_status,
            "review_note": c.review_note,
            "is_effective": c.is_effective,
            "photo": f"/uploads/{c.photo_path}" if c.photo_path else "",
        }
        for c in items
    ]


@router.get("/checkins/pending-count")
def pending_count(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """获取待审核打卡记录数量"""
    count = db.query(CheckIn).filter(CheckIn.review_status == "pending").count()
    return {"count": count}


@router.put("/checkins/{checkin_id}/review")
def review_checkin(
    checkin_id: int,
    req: ReviewRequest,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """审核打卡记录：批准或拒绝，批准后自动发放积分并重算连续天数。"""
    ci = db.query(CheckIn).filter(CheckIn.id == checkin_id).first()
    if not ci:
        raise HTTPException(status_code=404, detail="打卡记录不存在")
    if ci.review_status != "pending":
        raise HTTPException(status_code=400, detail="该记录已审核")
    if req.status == "approved":
        checkin_service.approve_checkin(db, ci, note=req.note)
    elif req.status == "rejected":
        checkin_service.reject_checkin(db, ci, note=req.note)
    else:
        raise HTTPException(status_code=400, detail="status 必须是 approved 或 rejected")
    return {"message": "审核完成", "review_status": ci.review_status}


@router.get("/redemptions")
def redemptions(
    status: str | None = None,  # 可选筛选：pending/approved/rejected
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """兑换记录管理（含学生昵称，按时间倒序，支持按状态筛选）。"""
    query = db.query(Redemption)
    if status:
        query = query.filter(Redemption.status == status)
    items = query.order_by(Redemption.redeemed_at.desc()).limit(500).all()
    out = []
    for r in items:
        u = db.get(User, r.user_id)
        out.append({
            "id": r.id, "user_id": r.user_id, "nickname": u.nickname if u else "-",
            "username": u.username if u else "-",
            "prize_name": r.prize_name, "cost_points": r.cost_points,
            "redeemed_at": r.redeemed_at.strftime("%Y-%m-%d %H:%M"),
            "status": r.status, "replaced_by": r.replaced_by,
            "note": r.note,
            "review_note": r.review_note,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.strftime("%Y-%m-%d %H:%M") if r.reviewed_at else None,
        })
    return out


@router.get("/redemptions/{redemption_id}")
def redemption_detail(
    redemption_id: int,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """兑换记录详情。"""
    r = db.get(Redemption, redemption_id)
    if not r:
        raise HTTPException(status_code=404, detail="兑换记录不存在")
    u = db.get(User, r.user_id)
    prize = db.get(Prize, r.prize_id)
    return {
        "id": r.id,
        "user_id": r.user_id,
        "nickname": u.nickname if u else "-",
        "username": u.username if u else "-",
        "prize_id": r.prize_id,
        "prize_name": r.prize_name,
        "prize_description": prize.description if prize else None,
        "cost_points": r.cost_points,
        "redeemed_at": r.redeemed_at.strftime("%Y-%m-%d %H:%M"),
        "status": r.status,
        "replaced_by": r.replaced_by,
        "note": r.note,
        "review_note": r.review_note,
        "reviewed_by": r.reviewed_by,
        "reviewed_at": r.reviewed_at.strftime("%Y-%m-%d %H:%M") if r.reviewed_at else None,
    }


@router.put("/redemptions/{redemption_id}/review")
def review_redemption(
    redemption_id: int,
    req: ReviewRequest,
    admin_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """审核兑换记录：兑现或拒绝。
    
    - approved: 标记为已兑现（fulfilled）
    - rejected: 标记为已拒绝（rejected），退还积分
    """
    r = db.get(Redemption, redemption_id)
    if not r:
        raise HTTPException(status_code=404, detail="兑换记录不存在")
    if r.status != "pending":
        raise HTTPException(status_code=400, detail="该记录已处理，不可重复操作")
    
    user = db.get(User, r.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    now = now_local()
    
    if req.status == "approved":
        r.status = "fulfilled"
        r.review_note = req.note or ""
        r.reviewed_by = admin_user.id
        r.reviewed_at = now
        message = "已兑现"
    elif req.status == "rejected":
        r.status = "rejected"
        r.review_note = req.note or ""
        r.reviewed_by = admin_user.id
        r.reviewed_at = now
        # 退还积分
        user.points = (user.points or 0) + r.cost_points
        message = "已拒绝，积分已退还"
    else:
        raise HTTPException(status_code=400, detail="status 必须是 approved 或 rejected")
    
    db.commit()
    
    return {
        "message": message,
        "status": r.status,
        "reviewed_at": now.strftime("%Y-%m-%d %H:%M"),
        "reviewed_by": admin_user.nickname,
    }


@router.get("/site-config", response_model=SiteConfigOut)
def get_site_config(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """获取站点配置（仅管理员可见）。"""
    from .site import get_or_create_site_config
    return get_or_create_site_config(db)


@router.put("/site-config", response_model=SiteConfigOut)
def save_site_config(req: SiteConfigIn, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """保存站点配置：标题限 64 字、标语限 128 字，置空则恢复默认值。"""
    from .site import get_or_create_site_config
    title = (req.student_title or "").strip()
    if len(title) > 64:
        raise HTTPException(status_code=400, detail="标题最长 64 个字符")
    slogan = (req.student_slogan or "").strip()
    if len(slogan) > 128:
        raise HTTPException(status_code=400, detail="欢迎标语最长 128 个字符")
    cfg = get_or_create_site_config(db)
    cfg.student_title = title or None
    cfg.student_slogan = slogan or None
    cfg.updated_at = now_local()
    db.commit()
    db.refresh(cfg)
    return cfg


@router.get("/push-config", response_model=PushConfigOut)
def get_push_config(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """获取推送配置（仅管理员可见）。"""
    return webhook_push_service.get_config(db)


@router.put("/push-config", response_model=PushConfigOut)
def save_push_config(req: PushConfigIn, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """保存推送配置，非空 Webhook URL 需通过前缀校验。

    标题模板不含钉钉关键词时不拒绝保存（发送侧会自动补前缀），
    仅通过响应的 warning 字段软提醒管理员。
    """
    for channel, url in (("dingtalk", req.dingtalk_url), ("wechat", req.wechat_url)):
        if url:
            err = webhook_push_service.validate_webhook_url(channel, url.strip())
            if err:
                raise HTTPException(status_code=400, detail=err)
    warnings = []
    for label, tpl in (("日常打卡", req.tpl_daily_title), ("闯关打卡", req.tpl_challenge_title)):
        err = webhook_push_service.validate_template_title((tpl or "").strip())
        if err:
            warnings.append(f"{label}{err}")
    cfg = webhook_push_service.get_config(db)
    cfg.enabled = req.enabled
    cfg.dingtalk_url = (req.dingtalk_url or "").strip() or None
    cfg.wechat_url = (req.wechat_url or "").strip() or None
    cfg.push_on_submitted = req.push_on_submitted
    cfg.push_on_approved = req.push_on_approved
    cfg.push_on_rejected = req.push_on_rejected
    cfg.push_on_challenge = req.push_on_challenge
    cfg.rate_limit_per_min = max(0, req.rate_limit_per_min)
    cfg.public_base_url = (req.public_base_url or "").strip() or None
    cfg.outgoing_token = (req.outgoing_token or "").strip() or None
    cfg.allow_bot_review = req.allow_bot_review
    # 标题/正文清空时回填内置默认模板（界面始终有可编辑的起点）；签名清空存空串表示不追加
    _tpl_defaults = DEFAULT_PUSH_TEMPLATES
    cfg.tpl_daily_title = (req.tpl_daily_title or "").strip() or _tpl_defaults["daily_title"]
    cfg.tpl_daily_body = (req.tpl_daily_body or "").strip() or _tpl_defaults["daily_body"]
    cfg.tpl_challenge_title = (req.tpl_challenge_title or "").strip() or _tpl_defaults["challenge_title"]
    cfg.tpl_challenge_body = (req.tpl_challenge_body or "").strip() or _tpl_defaults["challenge_body"]
    cfg.tpl_signature = (req.tpl_signature or "").strip()
    cfg.updated_at = now_local()
    db.commit()
    db.refresh(cfg)
    out = PushConfigOut.model_validate(cfg)
    out.warning = "；".join(warnings) or None
    return out


@router.post("/push-config/test")
def test_push(req: PushTestRequest, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """向指定渠道发送一条测试消息，验证 Webhook URL 可用性。"""
    if req.channel not in ("dingtalk", "wechat"):
        raise HTTPException(status_code=400, detail="channel 必须是 dingtalk 或 wechat")
    err = webhook_push_service.send_test(db, req.channel)
    return {"ok": err is None, "error": err}


@router.post("/push-config/preview")
def preview_push_template(req: PushTemplatePreviewIn, _: User = Depends(require_role("admin"))):
    """用样例数据预览推送模板渲染效果（不保存、不外发）。"""
    if req.kind not in ("daily", "challenge"):
        raise HTTPException(status_code=400, detail="kind 必须是 daily 或 challenge")
    err = webhook_push_service.validate_template_title((req.title_tpl or "").strip())
    text = webhook_push_service.render_preview(
        req.kind, (req.title_tpl or "").strip(), (req.body_tpl or "").strip(), req.signature or "")
    return {"text": text, "warning": err}


@router.get("/push-logs", response_model=list[PushLogOut])
def push_logs(limit: int = 50, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """推送历史倒序列表。"""
    limit = min(max(1, limit), 200)
    return db.query(PushLog).order_by(PushLog.id.desc()).limit(limit).all()
