from datetime import date, datetime, timezone, timedelta
import time as _time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from ..models import User, CheckIn, StudentParent, Redemption, Prize, LotteryRecord, Notification, PushLog, PetAdoption, PetFeedLog, PetSpecies, PetFeedItem
from ..database import get_db
from ..schemas import ReviewRequest, PushConfigIn, PushConfigOut, PushLogOut, PushTestRequest, PushTemplatePreviewIn, SiteConfigIn, SiteConfigOut
from ..config import SUMMER_START, SUMMER_END, CHECKIN_POINTS, MAKEUP_POINTS, DEFAULT_PUSH_TEMPLATES
from ..deps import require_role
from ..utils.timeutil import now_local
from ..utils.storage import public_url
from ..utils.pagination import ADMIN_PAGE_SIZE, Page, paginate
from ..services import checkin_service
from ..services import webhook_push_service
from ..services.pet_service import compute_suitability

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
def users(
    page: int = 1,
    size: int = ADMIN_PAGE_SIZE,
    role: str | None = None,  # 可选筛选：student/parent/admin
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """用户列表（分页，可按角色筛选）。"""
    query = db.query(User)
    if role and role != "all":
        query = query.filter(User.role == role)
    items, meta = paginate(query.order_by(User.id), page, size)
    return {
        "items": [
            {
                "id": u.id, "username": u.username, "role": u.role, "nickname": u.nickname,
                "grade": u.grade, "phone": u.phone, "current_streak": u.current_streak,
                "longest_streak": u.longest_streak,             "effective_checkins": u.effective_checkins,
                "lottery_tickets": u.lottery_tickets, "points": u.points or 0,
                "bind_code": u.bind_code,
            }
            for u in items
        ],
        **meta,
    }


@router.get("/checkins")
def checkins(
    page: int = 1,
    size: int = ADMIN_PAGE_SIZE,
    status: str | None = None,  # 可选筛选：pending/approved/rejected
    geo: bool = False,  # 仅看位置异常
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """打卡记录列表（分页，包含用户昵称、审核状态；可按审核状态或位置异常筛选）"""
    query = db.query(CheckIn)
    if status and status != "all":
        query = query.filter(CheckIn.review_status == status)
    if geo:
        query = query.filter(CheckIn.geo_flag == True)
    items, meta = paginate(query.order_by(CheckIn.check_time.desc()), page, size)
    # 当页昵称一次性批量取，避免逐条查询
    nick_map = {}
    if items:
        uids = {c.user_id for c in items}
        nick_map = {u.id: u.nickname for u in db.query(User).filter(User.id.in_(uids)).all()}
    return {
        "items": [
            {
                "id": c.id,
                "user_id": c.user_id,
                "nickname": nick_map.get(c.user_id) or "-",
                "check_date": str(c.check_date),
                "check_time": c.check_time.strftime("%Y-%m-%d %H:%M"),
                "check_type": c.check_type,
                "geo_distance": c.geo_distance,
                "geo_flag": c.geo_flag,
                "scene_check": c.scene_check,
                "review_status": c.review_status,
                "review_note": c.review_note,
                "is_effective": c.is_effective,
                "photo": public_url(c.photo_path) if c.photo_path else "",
            }
            for c in items
        ],
        **meta,
    }


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
    page: int = 1,
    size: int = ADMIN_PAGE_SIZE,
    status: str | None = None,  # 可选筛选：pending/approved/rejected
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """兑换记录管理（分页，含学生昵称，按时间倒序，支持按状态筛选）。"""
    query = db.query(Redemption)
    if status and status != "all":
        query = query.filter(Redemption.status == status)
    items, meta = paginate(query.order_by(Redemption.redeemed_at.desc()), page, size)
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
    return {"items": out, **meta}


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
    # 打卡积分：None 表示恢复默认；有值则校验为 0–1000 的非负整数
    for field, label in ((req.checkin_points, "正常打卡积分"), (req.makeup_points, "补卡积分")):
        if field is not None and (field < 0 or field > 1000):
            raise HTTPException(status_code=400, detail=f"{label}需在 0–1000 之间（置空恢复默认）")
    cfg = get_or_create_site_config(db)
    cfg.student_title = title or None
    cfg.student_slogan = slogan or None
    cfg.checkin_points = req.checkin_points
    cfg.makeup_points = req.makeup_points
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
    wecom_aes_key = (req.wecom_bot_aes_key or "").strip()
    if wecom_aes_key and len(wecom_aes_key) != 43:
        raise HTTPException(status_code=400, detail="企微 EncodingAESKey 长度必须为 43 个字符")
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
    cfg.wecom_bot_token = (req.wecom_bot_token or "").strip() or None
    cfg.wecom_bot_aes_key = wecom_aes_key or None
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


@router.get("/push-logs", response_model=Page[PushLogOut])
def push_logs(
    page: int = 1,
    size: int = ADMIN_PAGE_SIZE,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """推送历史倒序列表（分页）。"""
    items, meta = paginate(db.query(PushLog).order_by(PushLog.id.desc()), page, size)
    return Page[PushLogOut](items=items, **meta)


# ========== 宠物管理 ==========

@router.get("/pets/overview")
def pets_overview(
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """宠物领养情况总览。"""
    total_students = db.query(User).filter_by(role="student").count()
    adopted_count = db.query(PetAdoption).filter_by(is_active=True).count()
    total_ever_adopted = db.query(PetAdoption).count()
    # 各阶段分布
    stage_dist = {}
    for stage in ["baby", "youth", "adult", "legend"]:
        stage_dist[stage] = db.query(PetAdoption).filter_by(is_active=True, current_stage=stage).count()
    return {
        "total_students": total_students,
        "adopted_count": adopted_count,
        "not_adopted_count": total_students - adopted_count,
        "total_ever_adopted": total_ever_adopted,
        "stage_distribution": stage_dist,
    }


@router.get("/pets/adoptions")
def pets_adoptions(
    page: int = 1,
    size: int = ADMIN_PAGE_SIZE,
    search: str = "",
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """宠物领养列表（可按用户名/昵称搜索）。"""
    q = db.query(PetAdoption).join(User, PetAdoption.user_id == User.id)
    if search:
        kw = f"%{search}%"
        q = q.filter((User.username.ilike(kw)) | (User.nickname.ilike(kw)) | (PetAdoption.nickname.ilike(kw)))
    q = q.order_by(PetAdoption.id.desc())
    items, meta = paginate(q, page, size)
    result = []
    for a in items:
        user = db.get(User, a.user_id)
        species = a.species
        result.append({
            "id": a.id,
            "user_id": a.user_id,
            "username": user.username if user else "",
            "nickname": user.nickname if user else "",
            "pet_nickname": a.nickname,
            "species_name": species.name if species else "",
            "emoji": getattr(species, f"emoji_{a.current_stage}", "🐾") if species else "🐾",
            "current_xp": a.current_xp,
            "current_stage": a.current_stage,
            "stage_label": {"baby": "幼年期", "youth": "少年期", "adult": "成年期", "legend": "传奇期"}.get(a.current_stage, a.current_stage),
            "adopted_at": a.adopted_at.isoformat() if a.adopted_at else None,
            "last_fed_at": a.last_fed_at.isoformat() if a.last_fed_at else None,
            "is_active": a.is_active,
            "abandoned_at": a.abandoned_at.isoformat() if a.abandoned_at else None,
        })
    return {"items": result, **meta}


@router.get("/pets/feed-logs")
def pets_feed_logs(
    page: int = 1,
    size: int = ADMIN_PAGE_SIZE,
    adoption_id: int = 0,
    user_id: int = 0,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """宠物成长流水（可按领养 ID 或用户 ID 筛选）。"""
    q = db.query(PetFeedLog)
    if adoption_id:
        q = q.filter_by(adoption_id=adoption_id)
    if user_id:
        q = q.filter_by(user_id=user_id)
    q = q.order_by(PetFeedLog.id.desc())
    items, meta = paginate(q, page, size)
    result = []
    for log in items:
        user = db.get(User, log.user_id)
        adoption = db.get(PetAdoption, log.adoption_id)
        result.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": user.username if user else "",
            "nickname": user.nickname if user else "",
            "pet_nickname": adoption.nickname if adoption else "",
            "feed_type": log.feed_type,
            "xp_gained": log.xp_gained,
            "total_xp_after": log.total_xp_after,
            "stage_before": log.stage_before,
            "stage_after": log.stage_after,
            "stage_changed": log.stage_before != log.stage_after if log.stage_before and log.stage_after else False,
            "trigger_checkin_id": log.trigger_checkin_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return {"items": result, **meta}


@router.put("/pets/{adoption_id}/adjust")
def pet_adjust(
    adoption_id: int,
    xp_delta: int = 0,
    set_stage: str = "",
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """管理员手动调整宠物数据（XP 增减 / 强制设定阶段）。"""
    from ..services.pet_service import calc_stage as _calc_stage
    adoption = db.get(PetAdoption, adoption_id)
    if not adoption:
        raise HTTPException(status_code=404, detail="宠物不存在")
    user = db.get(User, adoption.user_id)
    old_stage = adoption.current_stage

    if xp_delta != 0:
        adoption.current_xp = max(0, adoption.current_xp + xp_delta)
    if set_stage and set_stage in ("baby", "youth", "adult", "legend"):
        adoption.current_stage = set_stage
    elif xp_delta != 0:
        adoption.current_stage = _calc_stage(adoption.current_xp)

    # 同步 User 冗余字段
    if user and adoption.is_active:
        user.pet_xp = adoption.current_xp
        user.pet_level = adoption.current_stage

    # 写流水
    log = PetFeedLog(
        user_id=adoption.user_id,
        adoption_id=adoption.id,
        feed_type="admin_adjust",
        xp_gained=xp_delta,
        total_xp_after=adoption.current_xp,
        stage_before=old_stage,
        stage_after=adoption.current_stage,
    )
    db.add(log)
    db.commit()
    return {"message": "已调整", "current_xp": adoption.current_xp, "current_stage": adoption.current_stage}


@router.get("/pets/species")
def pets_species_list(
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """获取所有宠物种类配置。"""
    species = db.query(PetSpecies).order_by(PetSpecies.sort_order).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "emoji_baby": s.emoji_baby,
            "emoji_youth": s.emoji_youth,
            "emoji_adult": s.emoji_adult,
            "emoji_legend": s.emoji_legend,
            "status": s.status,
            "sort_order": s.sort_order,
        }
        for s in species
    ]


@router.post("/pets/species")
def pets_species_create(
    name: str = "",
    description: str = "",
    emoji_baby: str = "🐣",
    emoji_youth: str = "🐥",
    emoji_adult: str = "🐔",
    emoji_legend: str = "🦄",
    sort_order: int = 0,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """新增宠物种类。"""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="种类名称不能为空")
    species = PetSpecies(
        name=name.strip(),
        description=description,
        emoji_baby=emoji_baby,
        emoji_youth=emoji_youth,
        emoji_adult=emoji_adult,
        emoji_legend=emoji_legend,
        status="on",
        sort_order=sort_order,
    )
    db.add(species)
    db.commit()
    db.refresh(species)
    return {"message": "已创建", "id": species.id}


@router.put("/pets/species/{species_id}")
def pets_species_update(
    species_id: int,
    name: str = "",
    description: str = "",
    emoji_baby: str = "",
    emoji_youth: str = "",
    emoji_adult: str = "",
    emoji_legend: str = "",
    status: str = "",
    sort_order: int = -1,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """更新宠物种类配置。"""
    species = db.get(PetSpecies, species_id)
    if not species:
        raise HTTPException(status_code=404, detail="种类不存在")
    if name:
        species.name = name
    if description:
        species.description = description
    if emoji_baby:
        species.emoji_baby = emoji_baby
    if emoji_youth:
        species.emoji_youth = emoji_youth
    if emoji_adult:
        species.emoji_adult = emoji_adult
    if emoji_legend:
        species.emoji_legend = emoji_legend
    if status in ("on", "off"):
        species.status = status
    if sort_order >= 0:
        species.sort_order = sort_order
    db.commit()
    return {"message": "已更新"}


@router.delete("/pets/species/{species_id}")
def pets_species_delete(
    species_id: int,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """删除宠物种类（已有领养记录时禁止删除）。"""
    species = db.get(PetSpecies, species_id)
    if not species:
        raise HTTPException(status_code=404, detail="种类不存在")
    # 检查是否有领养记录
    adoption_count = db.query(PetAdoption).filter_by(species_id=species_id).count()
    if adoption_count > 0:
        raise HTTPException(status_code=400, detail=f"该种类已有 {adoption_count} 条领养记录，无法删除。可改为「不可领养」状态。")
    db.delete(species)
    db.commit()
    return {"message": "已删除"}


# ========== 宠物食物管理 ==========

@router.get("/pets/foods")
def pets_foods_list(
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """获取所有宠物食物列表。"""
    items = db.query(PetFeedItem).order_by(PetFeedItem.sort_order).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "emoji": f.emoji,
            "price": f.price,
            "xp_value": f.xp_value,
            "species_id": f.species_id,
            "species_name": f.species.name if f.species else None,
            "status": f.status,
            "sort_order": f.sort_order,
        }
        for f in items
    ]


@router.post("/pets/foods")
def pets_foods_create(
    name: str = "",
    description: str = "",
    emoji: str = "🍎",
    price: int = 5,
    xp_value: int = 5,
    species_id: int = 0,
    sort_order: int = 0,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """创建宠物食物。"""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="食物名称不能为空")
    if price < 1:
        raise HTTPException(status_code=400, detail="积分价格至少为 1")
    if xp_value < 1:
        raise HTTPException(status_code=400, detail="经验值至少为 1")
    food = PetFeedItem(
        name=name.strip(), description=description, emoji=emoji,
        price=price, xp_value=xp_value,
        species_id=species_id if species_id > 0 else None,
        sort_order=sort_order,
    )
    db.add(food)
    db.commit()
    return {"message": "已创建", "id": food.id}


@router.put("/pets/foods/{food_id}")
def pets_foods_update(
    food_id: int,
    name: str = "",
    description: str = "",
    emoji: str = "",
    price: int = -1,
    xp_value: int = -1,
    species_id: int = -1,
    status: str = "",
    sort_order: int = -1,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """更新宠物食物。"""
    food = db.get(PetFeedItem, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="食物不存在")
    if name and name.strip():
        food.name = name.strip()
    if description is not None:
        food.description = description
    if emoji and emoji.strip():
        food.emoji = emoji.strip()
    if price >= 0:
        food.price = price
    if xp_value >= 0:
        food.xp_value = xp_value
    if species_id >= 0:
        food.species_id = species_id if species_id > 0 else None
    if status and status in ("on", "off"):
        food.status = status
    if sort_order >= 0:
        food.sort_order = sort_order
    db.commit()
    return {"message": "已更新"}


@router.delete("/pets/foods/{food_id}")
def pets_foods_delete(
    food_id: int,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """删除宠物食物（已有喂养记录时禁止删除）。"""
    food = db.get(PetFeedItem, food_id)
    if not food:
        raise HTTPException(status_code=404, detail="食物不存在")
    feed_count = db.query(PetFeedLog).filter_by(feed_item_id=food_id).count()
    if feed_count > 0:
        raise HTTPException(status_code=400, detail=f"该食物已有 {feed_count} 条喂养记录，无法删除。可改为「下架」状态。")
    db.delete(food)
    db.commit()
    return {"message": "已删除"}


@router.get("/pets/feed-stats")
def pets_feed_stats(
    days: int = 7,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """喂养统计报表（按日/按食物类型）。"""
    cutoff = now_local() - timedelta(days=days)

    # 总览
    total_feeds = db.query(PetFeedLog).filter(
        PetFeedLog.created_at >= cutoff,
        PetFeedLog.feed_type == "item",
    ).count()
    total_xp = db.query(func.sum(PetFeedLog.xp_gained)).filter(
        PetFeedLog.created_at >= cutoff,
        PetFeedLog.feed_type == "item",
    ).scalar() or 0
    total_points = db.query(func.sum(PetFeedLog.points_cost)).filter(
        PetFeedLog.created_at >= cutoff,
        PetFeedLog.feed_type == "item",
    ).scalar() or 0

    # 按食物统计
    by_food = (
        db.query(
            PetFeedItem.name,
            PetFeedItem.emoji,
            func.count(PetFeedLog.id).label("count"),
            func.sum(PetFeedLog.xp_gained).label("total_xp"),
            func.sum(PetFeedLog.points_cost).label("total_cost"),
        )
        .join(PetFeedLog, PetFeedLog.feed_item_id == PetFeedItem.id)
        .filter(PetFeedLog.created_at >= cutoff, PetFeedLog.feed_type == "item")
        .group_by(PetFeedItem.id)
        .order_by(func.count(PetFeedLog.id).desc())
        .all()
    )

    return {
        "days": days,
        "total_feeds": total_feeds,
        "total_xp": total_xp,
        "total_points": total_points,
        "by_food": [
            {
                "name": r.name,
                "emoji": r.emoji,
                "count": r.count,
                "total_xp": r.total_xp or 0,
                "total_cost": r.total_cost or 0,
            }
            for r in by_food
        ],
    }


# ---------- 食物适配性管理 ----------

@router.get("/pets/suitability-matrix")
def suitability_matrix(
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """获取食物适配性矩阵（横轴=食物，纵轴=宠物种类）"""
    species_list = db.query(PetSpecies).filter_by(status="on").order_by(PetSpecies.sort_order).all()
    foods = db.query(PetFeedItem).filter_by(status="on").order_by(PetFeedItem.sort_order).all()

    matrix = []
    for sp in species_list:
        row = {
            "species_id": sp.id,
            "species_name": sp.name,
            "diet_type": sp.diet_type or "omnivore",
            "cells": [],
        }
        for food in foods:
            suit = compute_suitability(sp, food)
            row["cells"].append({
                "food_id": food.id,
                "level": suit["level"],
                "label": suit["label"],
                "emoji": suit["emoji"],
            })
        matrix.append(row)

    return {
        "species": [{"id": s.id, "name": s.name, "diet_type": s.diet_type or "omnivore"} for s in species_list],
        "foods": [{"id": f.id, "name": f.name, "emoji": f.emoji} for f in foods],
        "matrix": matrix,
    }


@router.put("/pets/foods/{food_id}/suitability")
def update_food_suitability(
    food_id: int,
    level: str,
    note: str = "",
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """更新食物的默认适配等级"""
    food = db.query(PetFeedItem).filter_by(id=food_id).first()
    if not food:
        raise HTTPException(404, "食物不存在")
    valid_levels = ("perfect", "suitable", "caution", "warning", "danger")
    if level not in valid_levels:
        raise HTTPException(400, f"适配等级无效，可选值：{', '.join(valid_levels)}")
    food.suitability_level = level
    food.suitability_note = note or None
    db.commit()
    return {"message": f"已更新 {food.name} 的适配等级为 {level}"}


# ---------- 生病/治愈记录查询 ----------

@router.get("/pets/sick-records")
def sick_records(
    days: int = 30,
    user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """查询最近 N 天的异常喂养事件（触发疾病的记录）"""
    cutoff = now_local() - timedelta(days=days)

    # 查询 suitability_result 为 warning/caution 的喂养记录
    logs = (
        db.query(PetFeedLog)
        .filter(
            PetFeedLog.created_at >= cutoff,
            PetFeedLog.feed_type == "item",
            PetFeedLog.suitability_result.in_(["warning", "caution"]),
        )
        .order_by(PetFeedLog.created_at.desc())
        .limit(100)
        .all()
    )

    return {
        "days": days,
        "total": len(logs),
        "records": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.adoption.user.username if log.adoption else "",
                "pet_name": log.adoption.nickname if log.adoption else "",
                "food_id": log.feed_item_id,
                "suitability": log.suitability_result,
                "xp_gained": log.xp_gained,
                "points_cost": log.points_cost,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
