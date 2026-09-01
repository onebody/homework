"""学习成长计划 - 学生端 API（prefix /api/learning）。

序列化辅助函数（serialize_task / serialize_plan / serialize_submission）
同时被 learning_admin.py 与 parent.py 复用。
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import (
    ClassGroup, LearningPlan, LearningTask, ProgressRecord, Semester,
    Subject, TaskSubmission, User, UserBadge,
)
from ..schemas import (
    InstantiateRequest, LearningSummaryOut, PlanOut, ProgressIn,
    SubjectOut, TaskOut,
)
from ..services import learning_service as ls

router = APIRouter(prefix="/api/learning", tags=["learning"])


# ---------- 序列化辅助（跨路由复用） ----------

def serialize_task(db: Session, task: LearningTask, user: User = None) -> dict:
    """任务输出：含学科信息、四态、当前用户进展与最近提交摘要。"""
    subj = db.get(Subject, task.subject_id) if task.subject_id else None
    out = TaskOut(
        id=task.id,
        plan_id=task.plan_id,
        subject_id=task.subject_id,
        subject_name=subj.name if subj else None,
        subject_emoji=subj.emoji if subj else None,
        title=task.title,
        completion_criteria=task.completion_criteria,
        est_minutes=task.est_minutes or 30,
        due_date=task.due_date,
        reward_points=task.reward_points or 0,
        reward_xp=task.reward_xp or 0,
        sort_order=task.sort_order or 0,
        status=task.status,
        computed_status=ls.computed_status(task),
        done_at=task.done_at,
    ).model_dump()

    if user is not None:
        prog = db.query(ProgressRecord).filter_by(
            task_id=task.id, user_id=user.id,
        ).order_by(ProgressRecord.created_at.desc()).first()
        if prog:
            out["progress_percent"] = prog.percent
        sub = db.query(TaskSubmission).filter_by(
            task_id=task.id, user_id=user.id,
        ).order_by(TaskSubmission.created_at.desc()).first()
        if sub:
            out["submission"] = {
                "id": sub.id,
                "review_status": sub.review_status,
                "review_note": sub.review_note,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
            }
    return out


def serialize_plan(db: Session, plan: LearningPlan, with_progress: bool = False) -> dict:
    semester = db.get(Semester, plan.semester_id) if plan.semester_id else None
    clazz = db.get(ClassGroup, plan.class_id) if plan.class_id else None
    out = PlanOut(
        id=plan.id,
        plan_type=plan.plan_type,
        name=plan.name,
        description=plan.description,
        semester_id=plan.semester_id,
        semester_name=semester.name if semester else None,
        grade=plan.grade,
        class_id=plan.class_id,
        class_name=clazz.name if clazz else None,
        period_type=plan.period_type or "week",
        status=plan.status,
        student_id=plan.student_id,
        instantiated_from=plan.instantiated_from,
        task_count=db.query(LearningTask).filter_by(plan_id=plan.id).count(),
    ).model_dump()
    if with_progress and plan.plan_type == "instance":
        out["progress"] = ls.plan_progress(db, plan)
    return out


def serialize_submission(db: Session, sub: TaskSubmission) -> dict:
    from ..schemas import SubmissionOut
    task = db.get(LearningTask, sub.task_id)
    owner = db.get(User, sub.user_id)
    return SubmissionOut(
        id=sub.id,
        task_id=sub.task_id,
        task_title=task.title if task else "",
        user_id=sub.user_id,
        user_nickname=owner.nickname if owner else "",
        content=sub.content,
        photo_url=sub.photo_url or "",
        review_status=sub.review_status,
        review_note=sub.review_note,
        reviewer_role=sub.reviewer_role,
        reviewed_at=sub.reviewed_at,
        created_at=sub.created_at,
    ).model_dump()


def build_summary(db: Session, user: User) -> LearningSummaryOut:
    """学生端首页学习卡片数据。"""
    cfg = ls.get_or_create_config(db)
    plans = db.query(LearningPlan).filter_by(
        plan_type="instance", student_id=user.id, status="active",
    ).all()
    total = done = pending = overdue = 0
    percent_sum = 0
    for p in plans:
        prog = ls.plan_progress(db, p)
        total += prog["total"]
        done += prog["done"]
        pending += prog["total"] - prog["done"] - prog["overdue"]
        overdue += prog["overdue"]
        percent_sum += prog["percent"]
    badge_count = db.query(UserBadge).filter_by(user_id=user.id).count()
    return LearningSummaryOut(
        mode=cfg.mode or "summer",
        study_streak=user.study_streak or 0,
        study_longest_streak=user.study_longest_streak or 0,
        active_plans=len(plans),
        percent=round(percent_sum / len(plans)) if plans else 0,
        done_tasks=done,
        total_tasks=total,
        pending_tasks=pending,
        overdue_tasks=overdue,
        badge_count=badge_count,
    )


# ---------- 配置与基础数据 ----------

@router.get("/config")
def get_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """当前模式/学期/审核模式/我的班级（前端模式切换依据）。"""
    cfg = ls.get_or_create_config(db)
    sem = db.get(Semester, cfg.current_semester_id) if cfg.current_semester_id else None
    clazz = db.get(ClassGroup, user.class_id) if user.class_id else None
    return {
        "mode": cfg.mode or "summer",
        "review_mode": cfg.review_mode or "admin",
        "current_semester_id": cfg.current_semester_id,
        "semester_name": sem.name if sem else None,
        "semester_range": f"{sem.start_date} ~ {sem.end_date}" if sem else None,
        "class_name": clazz.name if clazz else None,
    }


@router.get("/subjects", response_model=list[SubjectOut])
def subjects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按我的年级过滤的启用学科。"""
    grade = user.grade or 3
    rows = (
        db.query(Subject)
        .filter(Subject.status == "on", Subject.grade_min <= grade, Subject.grade_max >= grade)
        .order_by(Subject.sort_order, Subject.id)
        .all()
    )
    return [SubjectOut.model_validate(s) for s in rows]


@router.get("/templates")
def templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """可见计划模板（班级/年级隔离后）。"""
    cfg = ls.get_or_create_config(db)
    items = [serialize_plan(db, t) for t in ls.visible_templates(db, user)]
    return {
        "mode": cfg.mode or "summer",
        "items": items,
        # 已实例化的模板 ID 集合，前端据此显示「已加入」
        "instantiated": [
            p.instantiated_from for p in db.query(LearningPlan).filter_by(
                plan_type="instance", student_id=user.id,
            ).all() if p.instantiated_from
        ],
    }


@router.post("/plans/instantiate")
def instantiate(req: InstantiateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    template = db.get(LearningPlan, req.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="计划模板不存在")
    inst = ls.instantiate_plan(db, template, user)
    return {"ok": True, "plan_id": inst.id, "message": "计划已激活"}


# ---------- 我的计划与任务 ----------

@router.get("/plans")
def my_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plans = db.query(LearningPlan).filter_by(
        plan_type="instance", student_id=user.id,
    ).order_by(LearningPlan.id.desc()).all()
    return {"items": [serialize_plan(db, p, with_progress=True) for p in plans]}


def _resolve_my_plan(db: Session, user: User, plan_id: int) -> LearningPlan:
    plan = db.get(LearningPlan, plan_id)
    if not plan or plan.plan_type != "instance" or plan.student_id != user.id:
        raise HTTPException(status_code=404, detail="计划不存在")  # 404 防探测
    return plan


@router.get("/plans/{plan_id}")
def plan_detail(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _resolve_my_plan(db, user, plan_id)
    tasks = (
        db.query(LearningTask).filter_by(plan_id=plan.id)
        .order_by(LearningTask.sort_order, LearningTask.id).all()
    )
    return {
        "plan": serialize_plan(db, plan, with_progress=True),
        "tasks": [serialize_task(db, t, user) for t in tasks],
    }


@router.get("/summary", response_model=LearningSummaryOut)
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_summary(db, user)


@router.get("/badges")
def badges(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": ls.badge_wall(db, user)}


@router.post("/tasks/{task_id}/progress")
def add_progress(task_id: int, req: ProgressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = ls.resolve_student_task(db, user, task_id)
    rec = ls.add_progress(db, user, task, req.note, req.minutes_spent, req.percent)
    return {
        "ok": True,
        "record_id": rec.id,
        "task_status": task.status,
        "computed_status": ls.computed_status(task),
    }


@router.post("/tasks/{task_id}/submit")
async def submit_task(
    task_id: int,
    content: str = Form(None),
    photo: UploadFile = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交任务成果（文字 + 可选照片）。review_mode=auto 时提交即自动通过。"""
    task = ls.resolve_student_task(db, user, task_id)
    photo_bytes = await photo.read() if photo and photo.filename else None
    sub = ls.submit_task(db, user, task, content, photo_bytes)
    return {
        "ok": True,
        "submission_id": sub.id,
        "review_status": sub.review_status,
        "message": "已自动通过审核" if sub.review_status == "approved" else "已提交，等待审核",
    }


# ---------- 学生端通知（WebSocket 断线降级轮询用） ----------

@router.get("/notifications/unread")
def unread_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import Notification
    role = "parent" if user.role == "parent" else "student"
    count = db.query(Notification).filter_by(
        user_id=user.id, recipient_role=role, read=False,
    ).count()
    items = (
        db.query(Notification)
        .filter_by(user_id=user.id, recipient_role=role)
        .order_by(Notification.created_at.desc()).limit(10).all()
    )
    from ..schemas import NotificationOut
    return {
        "unread": count,
        "items": [NotificationOut.model_validate(n) for n in items],
    }


@router.patch("/notifications/{nid}/read")
def read_notification(nid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import Notification
    n = db.get(Notification, nid)
    if n and n.user_id == user.id:
        n.read = True
        db.commit()
    return {"ok": True}
