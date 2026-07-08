"""闯关任务打卡业务逻辑。"""
from datetime import datetime, date, timezone
from sqlalchemy.orm import Session

from ..models import ChallengeTask, ChallengeCheckIn, User, Notification


def _make_aware(dt: datetime) -> datetime:
    """确保 datetime 带时区信息（统一为 UTC）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_task_unlocked(task: ChallengeTask, now: datetime = None) -> bool:
    """判断任务是否已开放。"""
    if now is None:
        now = datetime.now(timezone.utc)
    # 管理员手动开放
    if task.status == "active":
        return True
    # 定时自动开放
    if task.status == "scheduled" and task.unlock_at:
        unlock_at = _make_aware(task.unlock_at)
        if now >= unlock_at:
            return True
    return False


def get_student_task_status(db: Session, task: ChallengeTask, user_id: int) -> dict:
    """获取学生对某任务的状态。"""
    now = datetime.now(timezone.utc)
    unlocked = is_task_unlocked(task, now)

    latest = db.query(ChallengeCheckIn).filter(
        ChallengeCheckIn.user_id == user_id,
        ChallengeCheckIn.task_id == task.id
    ).order_by(ChallengeCheckIn.created_at.desc()).first()

    if not unlocked:
        user_status = "locked"
    elif latest is None:
        user_status = "pending"
    elif latest.review_status == "approved":
        user_status = "completed"
    elif latest.review_status == "pending":
        user_status = "reviewing"
    elif latest.review_status == "rejected":
        user_status = "rejected"
    else:
        user_status = "pending"

    return {
        "status": user_status,
        "latest_checkin": latest,
    }


def create_task(db: Session, data: dict, admin_id: int) -> ChallengeTask:
    """管理员创建闯关任务。"""
    unlock_at = None
    if data.get("unlock_at"):
        unlock_at = datetime.fromisoformat(data["unlock_at"])
        if unlock_at.tzinfo is None:
            unlock_at = unlock_at.replace(tzinfo=timezone.utc)
        if data.get("status") == "locked":
            data["status"] = "scheduled"

    task = ChallengeTask(
        name=data["name"],
        description=data.get("description"),
        sort_order=data.get("sort_order", 0),
        reward_points=data.get("reward_points", 10),
        status=data.get("status", "locked"),
        unlock_at=unlock_at,
        unlock_condition=data.get("unlock_condition"),
        created_by=admin_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task: ChallengeTask, data: dict) -> ChallengeTask:
    """管理员更新任务。"""
    for k, v in data.items():
        if v is not None and hasattr(task, k):
            if k == "unlock_at" and v:
                dt = datetime.fromisoformat(v)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                task.unlock_at = dt
            elif k == "unlock_at" and not v:
                task.unlock_at = None
            elif k != "unlock_at":
                setattr(task, k, v)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: ChallengeTask):
    """管理员删除任务（同时删除关联打卡记录）。"""
    db.query(ChallengeCheckIn).filter(ChallengeCheckIn.task_id == task.id).delete()
    db.delete(task)
    db.commit()


def list_tasks_for_student(db: Session, user_id: int) -> list:
    """获取学生端任务列表（按排序顺序）。"""
    tasks = db.query(ChallengeTask).order_by(ChallengeTask.sort_order).all()
    result = []
    now = datetime.now(timezone.utc)
    for task in tasks:
        status_info = get_student_task_status(db, task, user_id)
        unlocked = is_task_unlocked(task, now)
        latest = status_info["latest_checkin"]
        attachments = []
        if latest and latest.attachments:
            try:
                import json
                attachments = json.loads(latest.attachments)
            except Exception:
                pass
        result.append({
            "id": task.id,
            "name": task.name,
            "description": task.description,
            "sort_order": task.sort_order,
            "reward_points": task.reward_points,
            "status": "active" if unlocked else "locked",
            "unlock_at": task.unlock_at,
            "user_status": status_info["status"],
            "latest_checkin": {
                "id": latest.id,
                "content": latest.content,
                "attachments": attachments,
                "review_status": latest.review_status,
                "review_note": latest.review_note,
                "created_at": latest.created_at.isoformat() if latest else None,
            } if latest else None,
        })
    return result


def submit_checkin(db: Session, user: User, task_id: int, data: dict) -> dict:
    """学生提交闯关任务打卡。"""
    task = db.query(ChallengeTask).get(task_id)
    if not task:
        raise ValueError("任务不存在")
    if not is_task_unlocked(task):
        raise ValueError("任务尚未开放")

    status_info = get_student_task_status(db, task, user.id)
    if status_info["status"] == "completed":
        raise ValueError("该任务已完成，无需重复打卡")
    if status_info["status"] == "reviewing":
        raise ValueError("已有待审核的打卡记录")

    record = ChallengeCheckIn(
        user_id=user.id,
        task_id=task_id,
        content=data.get("content"),
        attachments=data.get("attachments"),
        review_status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 通知管理员
    _notify_admins(db, user.nickname, task.name)
    return {"id": record.id, "message": "打卡已提交，等待审核"}


def _notify_admins(db: Session, student_name: str, task_name: str):
    """通知管理员有新闯关打卡待审核。"""
    from ..models import User as U
    admins = db.query(U).filter(U.role == "admin").all()
    for admin in admins:
        n = Notification(
            user_id=admin.id,
            recipient_role="admin",
            type="checkin",
            title="闯关任务打卡待审核",
            content=f"学生 {student_name} 提交了「{task_name}」闯关打卡",
        )
        db.add(n)
    db.commit()


def review_checkin(db: Session, checkin: ChallengeCheckIn, action: str, note: str, admin_id: int):
    """管理员审核闯关打卡。"""
    task = db.query(ChallengeTask).get(checkin.task_id)
    if action == "approve":
        checkin.review_status = "approved"
        checkin.reviewed_by = admin_id
        checkin.reviewed_at = datetime.now(timezone.utc)
        if note:
            checkin.review_note = note
        # 发放积分
        user = db.query(User).get(checkin.user_id)
        if user and task:
            user.points = (user.points or 0) + task.reward_points
        # 通知学生
        n = Notification(
            user_id=checkin.user_id,
            recipient_role="student",
            type="checkin",
            title="闯关任务审核通过",
            content=f"「{task.name}」审核通过，获得 {task.reward_points} 积分！",
            related_id=checkin.id,
        )
        db.add(n)
    elif action == "reject":
        checkin.review_status = "rejected"
        checkin.reviewed_by = admin_id
        checkin.reviewed_at = datetime.now(timezone.utc)
        checkin.review_note = note or "审核未通过"
        n = Notification(
            user_id=checkin.user_id,
            recipient_role="student",
            type="checkin",
            title="闯关任务审核未通过",
            content=f"「{task.name}」审核未通过：{checkin.review_note}，请重新提交",
            related_id=checkin.id,
        )
        db.add(n)
    else:
        raise ValueError("无效的审核操作")
    db.commit()


def list_all_checkins(db: Session, task_id: int = None, status: str = None) -> list:
    """管理端：列出所有闯关打卡记录。"""
    q = db.query(ChallengeCheckIn)
    if task_id:
        q = q.filter(ChallengeCheckIn.task_id == task_id)
    if status:
        q = q.filter(ChallengeCheckIn.review_status == status)
    records = q.order_by(ChallengeCheckIn.created_at.desc()).all()
    result = []
    for r in records:
        user = db.query(User).get(r.user_id)
        task = db.query(ChallengeTask).get(r.task_id)
        attachments = []
        if r.attachments:
            try:
                import json
                attachments = json.loads(r.attachments)
            except Exception:
                pass
        result.append({
            "id": r.id,
            "user_id": r.user_id,
            "user_nickname": user.nickname if user else "",
            "task_id": r.task_id,
            "task_name": task.name if task else "",
            "content": r.content,
            "attachments": attachments,
            "review_status": r.review_status,
            "review_note": r.review_note,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return result


def get_task_stats(db: Session, task: ChallengeTask) -> dict:
    """获取任务的统计信息。"""
    total = db.query(ChallengeCheckIn).filter(ChallengeCheckIn.task_id == task.id).count()
    pending = db.query(ChallengeCheckIn).filter(
        ChallengeCheckIn.task_id == task.id,
        ChallengeCheckIn.review_status == "pending"
    ).count()
    return {"total_checkins": total, "pending_reviews": pending}
