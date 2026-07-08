from datetime import date, datetime, timedelta

from fastapi import HTTPException

from ..models import CheckIn, StudentParent, User
from ..config import MAX_MAKEUP_PER_MONTH, FACE_MODE_ON_ENROLLED, CHECKIN_POINTS, MAKEUP_POINTS
from ..utils.storage import save_upload
from .verification_service import verify_checkin
from .notify_service import notify, notify_parents_of_student


def _streaks(dates):
    """输入有效打卡日期列表，返回 (当前连续天数, 历史最长连续天数)。"""
    if not dates:
        return 0, 0
    s = sorted(set(dates))
    longest = cur_run = 1
    for i in range(1, len(s)):
        if (s[i] - s[i - 1]).days == 1:
            cur_run += 1
            longest = max(longest, cur_run)
        else:
            cur_run = 1
    today = date.today()
    last = s[-1]
    if last in (today, today - timedelta(days=1)):
        cs = 1
        for j in range(len(s) - 2, -1, -1):
            if (s[j + 1] - s[j]).days == 1:
                cs += 1
            else:
                break
        current = cs
    else:
        current = 0
    return current, longest


def recompute_and_grant(db, user):
    """重新计算连续天数与有效次数，并按 7 天里程碑发放抽奖资格。"""
    dates = [c.check_date for c in user.checkins if c.is_effective]
    current, longest = _streaks(dates)
    user.current_streak = current
    user.longest_streak = max(user.longest_streak, longest)
    user.effective_checkins = len(set(dates))

    new_milestone = current // 7
    if new_milestone > user.last_7_milestone:
        granted = new_milestone - user.last_7_milestone
        user.lottery_tickets += granted
        user.last_7_milestone = new_milestone
        notify(
            db, user.id, "student", "system",
            f"🎫 解锁 {granted} 次抽奖资格",
            f"你已连续有效打卡 {current} 天，获得 {granted} 次抽奖机会，快去抽奖吧！",
        )
    elif new_milestone < user.last_7_milestone:
        # 连续中断，放弃向下一里程碑的进度（已发放资格保留）
        user.last_7_milestone = new_milestone
    db.commit()
    return current, longest


def create_checkin(db, user, photo_bytes, lat, lng, check_type, reason, proof_bytes, makeup_for_date):
    """创建一条打卡记录，并执行全部业务规则。"""
    # 1) 照片合规校验
    ok, detail = _validate_photo_size(photo_bytes)
    if not ok:
        raise HTTPException(status_code=400, detail=detail)

    today = date.today()
    if check_type == "makeup":
        # 2) 补卡规则
        if not makeup_for_date:
            raise HTTPException(status_code=400, detail="补卡需指定补卡目标日期")
        try:
            target = datetime.strptime(makeup_for_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="补卡日期格式错误（应为 YYYY-MM-DD）")
        if target >= today:
            raise HTTPException(status_code=400, detail="补卡只能补过去的日期")
        if target < date(2026, 7, 1):
            raise HTTPException(status_code=400, detail="补卡日期不在暑假统计范围内")
        # 该目标日期已存在有效打卡则不可重复补
        dup = db.query(CheckIn).filter_by(user_id=user.id, check_date=target, is_effective=True).first()
        if dup:
            raise HTTPException(status_code=400, detail="该日期已有打卡记录，无需重复补卡")
        # 单自然月补卡上限
        month_start = target.replace(day=1)
        month_makeups = db.query(CheckIn).filter(
            CheckIn.user_id == user.id,
            CheckIn.check_type == "makeup",
            CheckIn.is_effective == True,
            CheckIn.check_date >= month_start,
        ).count()
        if month_makeups >= MAX_MAKEUP_PER_MONTH:
            raise HTTPException(
                status_code=400,
                detail=f"本月补卡次数已达上限（{MAX_MAKEUP_PER_MONTH} 次）",
            )
        if not proof_bytes:
            raise HTTPException(status_code=400, detail="补卡需上传补充作业完成凭证")
        check_date = target
    else:
        # 3) 正常打卡（允许多次，但需逐次审核）
        check_type = "normal"
        check_date = today

    # 4) 保存照片
    photo_path = save_upload(photo_bytes, user.id, "c")
    proof_path = save_upload(proof_bytes, user.id, "p") if proof_bytes else None

    # 5) 防代打卡校验
    ver = verify_checkin(user, photo_bytes, lat, lng)

    # 5.1) 人脸 1:1 比对策略（防代打卡拦截）
    face = (ver.get("face") or {})
    fstatus = face.get("status")
    if user.face_enrolled and fstatus in ("mismatch", "multiple_faces", "no_face"):
        raise HTTPException(status_code=400, detail=face.get("message") or "人脸校验未通过，疑似非本人打卡")
    if user.face_enrolled and fstatus == "model_unavailable" and FACE_MODE_ON_ENROLLED == "enforce":
        raise HTTPException(status_code=503, detail="人脸识别服务暂不可用，请稍后重试")

    ci = CheckIn(
        user_id=user.id,
        check_date=check_date,
        check_time=datetime.utcnow(),
        photo_path=photo_path,
        location_lat=lat,
        location_lng=lng,
        check_type=check_type,
        makeup_reason=reason,
        makeup_proof_path=proof_path,
        geo_distance=ver["geo_distance"],
        geo_flag=ver["geo_flag"],
        scene_check=ver["scene_check"],
        face_status=face.get("status"),
        face_score=face.get("score"),
        face_flag=face.get("status") in ("mismatch", "multiple_faces", "no_face"),
        review_status="pending",
        review_note=None,
        is_effective=False,
    )
    db.add(ci)
    db.commit()
    db.refresh(ci)

    # 6) 通知本人与家长：打卡已提交，等待审核
    label = "补卡" if check_type == "makeup" else "作业打卡"
    notify(
        db, user.id, "student", "checkin",
        f"📝 {label}已提交，等待管理员审核",
        f"你于 {ci.check_time.strftime('%Y-%m-%d %H:%M')} 提交了{label}，审核通过后将获得积分。",
        ci.id,
    )
    notify_parents_of_student(
        db, user, "checkin", f"孩子提交了{label}",
        f"孩子于 {ci.check_time.strftime('%Y-%m-%d %H:%M')} 提交了{label}，等待管理员审核。"
        + ("（温馨提示：打卡位置距常用位置较远，请关注）" if ver["geo_flag"] else ""),
        ci.id,
    )

    return ci, ver


def approve_checkin(db, ci, note=None):
    """管理员审核通过一条打卡记录：标记有效，发放积分，重算连续天数。"""
    if ci.review_status == "approved":
        raise HTTPException(status_code=400, detail="该记录已审核通过")
    gained = CHECKIN_POINTS if ci.check_type == "normal" else MAKEUP_POINTS
    ci.review_status = "approved"
    ci.review_note = note
    ci.is_effective = True
    db.commit()

    user = db.get(User, ci.user_id)
    user.points = (user.points or 0) + gained
    db.commit()

    # 重算连续天数与抽奖资格
    db.refresh(user)
    recompute_and_grant(db, user)
    db.refresh(user)

    notify(
        db, user.id, "student", "checkin",
        f"✅ 打卡审核通过，+{gained} 积分",
        f"你于 {ci.check_time.strftime('%Y-%m-%d %H:%M')} 的打卡已审核通过，当前积分 {user.points}。",
        ci.id,
    )
    return ci


def reject_checkin(db, ci, note=None):
    """管理员拒绝一条打卡记录。"""
    if ci.review_status == "rejected":
        raise HTTPException(status_code=400, detail="该记录已被拒绝")
    ci.review_status = "rejected"
    ci.review_note = note
    ci.is_effective = False
    db.commit()

    notify(
        db, ci.user_id, "student", "checkin",
        "❌ 打卡审核未通过",
        f"你于 {ci.check_time.strftime('%Y-%m-%d %H:%M')} 的打卡未通过审核。" + (f"原因：{note}" if note else ""),
        ci.id,
    )
    return ci


def _validate_photo_size(data):
    from ..config import MIN_PHOTO_BYTES, PHOTO_MAX_BYTES
    from ..utils.image import inspect_image
    if not (MIN_PHOTO_BYTES <= len(data) <= PHOTO_MAX_BYTES):
        return False, "照片体积不符合要求（需大于 5KB 且小于 10MB）"
    ok, w, h, fmt = inspect_image(data)
    if not ok:
        return False, "文件不是有效的 JPEG/PNG 图像"
    if w < 200 or h < 200:
        return False, f"照片尺寸过小（{w}x{h}），请上传清晰现场照片"
    return True, f"{fmt} {w}x{h}"


def get_today_status(db, user):
    today = date.today()
    # 查所有今天的打卡记录（包括待审核的）
    all_today = db.query(CheckIn).filter(
        CheckIn.user_id == user.id,
        CheckIn.check_date == today,
        CheckIn.check_type == "normal",
    ).all()
    # 已审核通过的
    approved = [c for c in all_today if c.review_status == "approved"]
    # 待审核的
    pending = [c for c in all_today if c.review_status == "pending"]
    
    # 本月已用补卡（仅计已审核通过的）
    month_start = today.replace(day=1)
    used = db.query(CheckIn).filter(
        CheckIn.user_id == user.id,
        CheckIn.check_type == "makeup",
        CheckIn.is_effective == True,
        CheckIn.check_date >= month_start,
    ).count()
    return {
        "today_checked": len(approved) > 0,
        "today_pending": len(pending) > 0,
        "today_count": len(all_today),
        "approved_count": len(approved),
        "pending_count": len(pending),
        "can_makeup_this_month": max(0, MAX_MAKEUP_PER_MONTH - used),
    }
