"""多学段学习成长计划服务层。

职责：配置单行表、模板可见性隔离、模板实例化、任务状态计算、
进展记录、成果提交与审核联动（对齐 checkin_service.approve_checkin 范式）、
连续学习天数与成就勋章。

联动原则（与老模块解耦）：
- 不读写 checkins 表；积分直加 user.points；
- 宠物 XP 复用 pet_service.apply_xp_gain（不 commit，调用方控制事务）；
- 通知复用 notify_service.notify / notify_parents_of_student。
"""
import random
from datetime import date

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from ..models import (
    ClassGroup, LearningConfig, LearningPlan, LearningTask, PetAdoption,
    PetFeedLog, ProgressRecord, Semester, Subject, TaskSubmission, User, UserBadge,
)
from ..utils.storage import save_upload
from ..utils.timeutil import now_local
from .notify_service import notify, notify_parents_of_student
from .pet_service import apply_xp_gain, get_stage_emoji, get_stage_label, _notify_stage_up
from .checkin_service import _streaks


# ---------- 成就勋章定义 ----------
# key -> (名称, 说明, 判定函数(db, user) -> bool)。判定幂等，由授予记录去重。
BADGE_DEFS = {
    "plan_first": ("初露锋芒", "完成第一个学习任务"),
    "do_ten": ("勤学小蜜蜂", "累计完成 10 个学习任务"),
    "multi_subject": ("全能小达人", "完成的任务覆盖 3 个以上学科"),
    "streak7": ("坚持之星", "连续学习 7 天"),
    "full_plan": ("大满贯", "完成一个计划的全部任务"),
}


# ---------- 配置（单行表，同 site.get_or_create_site_config 范式） ----------

def get_or_create_config(db) -> LearningConfig:
    cfg = db.query(LearningConfig).first()
    if not cfg:
        cfg = LearningConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def resolve_review_mode(db) -> str:
    """解析生效的审核模式：auto|parent|admin（缺省回退 admin）。"""
    cfg = db.query(LearningConfig).first()
    if cfg and cfg.review_mode in ("auto", "parent", "admin"):
        return cfg.review_mode
    return "admin"


def current_semester(db) -> Semester | None:
    cfg = db.query(LearningConfig).first()
    if cfg and cfg.current_semester_id:
        return db.get(Semester, cfg.current_semester_id)
    return None


# ---------- 模板可见性（班级/年级隔离） ----------

def visible_templates(db, user: User) -> list[LearningPlan]:
    """学生对当前学生仅可见：已发布模板，且（模板未指定年级或年级匹配）
    且（模板未指定班级或班级匹配）。隔离在服务层查询条件实现。"""
    q = db.query(LearningPlan).filter(
        LearningPlan.plan_type == "template",
        LearningPlan.status == "published",
    )
    templates = []
    for t in q.all():
        if t.grade is not None and t.grade != user.grade:
            continue
        if t.class_id is not None and t.class_id != user.class_id:
            continue
        templates.append(t)
    return sorted(templates, key=lambda x: (x.semester_id or 0, x.id))


def check_template_visible(db, template: LearningPlan, user: User):
    """实例化前二次校验模板可见性（防越权构造 template_id）。"""
    if template.plan_type != "template" or template.status != "published":
        raise HTTPException(status_code=400, detail="该计划模板不可用")
    if template.grade is not None and template.grade != user.grade:
        raise HTTPException(status_code=403, detail="该计划不适用于你的年级")
    if template.class_id is not None and template.class_id != user.class_id:
        raise HTTPException(status_code=403, detail="该计划不适用于你的班级")


# ---------- 模板实例化 ----------

def instantiate_plan(db, template: LearningPlan, student: User) -> LearningPlan:
    """将模板复制为学生个人计划实例。幂等：同一模板已有实例则返回既有实例。"""
    check_template_visible(db, template, student)
    existing = db.query(LearningPlan).filter_by(
        plan_type="instance", student_id=student.id, instantiated_from=template.id,
    ).first()
    if existing:
        return existing

    semester_id = template.semester_id
    if semester_id is None:
        cfg = get_or_create_config(db)
        semester_id = cfg.current_semester_id  # 可空：允许无学期归属的实例

    inst = LearningPlan(
        plan_type="instance",
        name=template.name,
        description=template.description,
        semester_id=semester_id,
        grade=student.grade,
        class_id=student.class_id,
        period_type=template.period_type,
        student_id=student.id,
        instantiated_from=template.id,
        status="active",
        created_by=student.id,
    )
    db.add(inst)
    db.flush()  # 取得 inst.id 以便挂任务

    for t in template.tasks:
        db.add(LearningTask(
            plan_id=inst.id,
            template_task_id=t.id,
            subject_id=t.subject_id,
            title=t.title,
            completion_criteria=t.completion_criteria,
            est_minutes=t.est_minutes,
            due_date=t.due_date,
            reward_points=t.reward_points,
            reward_xp=t.reward_xp,
            sort_order=t.sort_order,
            status="todo",
        ))
    db.commit()
    db.refresh(inst)
    return inst


# ---------- 任务状态 ----------

def computed_status(task: LearningTask, today: date = None) -> str:
    """四态：todo|doing|done|overdue。逾期 = 已过截止日且未完成（查询时计算，绝不写库）。"""
    if task.status == "done":
        return "done"
    today = today or date.today()
    if task.due_date and task.due_date < today:
        return "overdue"
    return task.status  # todo|doing


def plan_progress(db, plan: LearningPlan) -> dict:
    """计划进度汇总：完成数/总数/百分比（供环形进度条渲染）。"""
    today = date.today()
    tasks = db.query(LearningTask).filter_by(plan_id=plan.id).all()
    total = len(tasks)
    done = sum(1 for t in tasks if computed_status(t, today) == "done")
    overdue = sum(1 for t in tasks if computed_status(t, today) == "overdue")
    doing = sum(1 for t in tasks if computed_status(t, today) == "doing")
    percent = round(done * 100 / total) if total else 0
    return {"done": done, "total": total, "percent": percent,
            "doing": doing, "overdue": overdue}


def resolve_student_task(db, user: User, task_id: int) -> LearningTask:
    """取任务并校验归属：必须属于当前学生自己的计划实例。"""
    task = db.get(LearningTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    plan = db.get(LearningPlan, task.plan_id)
    if not plan or plan.plan_type != "instance" or plan.student_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该任务")
    return task


# ---------- 进展与提交 ----------

def add_progress(db, user: User, task: LearningTask, note, minutes_spent, percent) -> ProgressRecord:
    if task.status == "done":
        raise HTTPException(status_code=400, detail="任务已完成，无需再记录进展")
    percent = max(0, min(100, int(percent or 0)))
    rec = ProgressRecord(
        task_id=task.id, user_id=user.id,
        note=(note or "").strip() or None,
        minutes_spent=max(0, int(minutes_spent or 0)),
        percent=percent,
    )
    db.add(rec)
    # todo -> doing 自动流转（doing 保持）
    if task.status == "todo":
        task.status = "doing"
    db.commit()
    db.refresh(rec)
    return rec


def submit_task(db, user: User, task: LearningTask, content, photo_bytes) -> TaskSubmission:
    """提交任务成果进入审核流。依 review_mode 决定自动通过或等待人工审核。"""
    if task.status == "done":
        raise HTTPException(status_code=400, detail="任务已完成，无需重复提交")
    dup = db.query(TaskSubmission).filter(
        TaskSubmission.task_id == task.id,
        TaskSubmission.user_id == user.id,
        TaskSubmission.review_status.in_(["pending", "approved"]),
    ).first()
    if dup:
        raise HTTPException(
            status_code=400,
            detail="已审核通过" if dup.review_status == "approved" else "已提交，等待审核中",
        )
    if not (content or "").strip() and not photo_bytes:
        raise HTTPException(status_code=400, detail="请填写完成说明或上传成果照片")

    photo_path = save_upload(photo_bytes, user.id, "t") if photo_bytes else None
    sub = TaskSubmission(
        task_id=task.id, user_id=user.id,
        content=(content or "").strip() or None,
        photo_path=photo_path,
        review_status="pending",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    review_mode = resolve_review_mode(db)
    if review_mode == "auto":
        # 自动通过：直接走批准联动（不重复发通知，approve 内部会通知）
        return approve_submission(db, sub, reviewer=None, reviewer_role="auto")

    notify(
        db, user.id, "student", "learning",
        "📝 学习任务已提交，等待审核",
        f"任务「{task.title}」已提交，审核通过后将获得 {task.reward_points} 积分与宠物经验。",
        sub.id,
    )
    notify_parents_of_student(
        db, user, "learning", f"孩子提交了学习任务「{task.title}」",
        f"孩子提交了学习任务「{task.title}」的成果，等待审核。",
        sub.id,
    )
    return sub


# ---------- 审核联动（对齐 checkin_service.approve_checkin 范式） ----------

def approve_submission(db, sub: TaskSubmission, reviewer: User | None, reviewer_role: str, note: str = None) -> TaskSubmission:
    """审核通过：发积分 → 重算连续学习天数 → 随机活跃宠物加 XP → 通知 → 勋章。"""
    if sub.review_status == "approved":
        raise HTTPException(status_code=400, detail="该提交已审核通过")
    task = db.get(LearningTask, sub.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="关联任务不存在")
    # 幂等守卫：同一任务已有 approved 提交则拒绝（服务层兜底，
    # 与部分唯一索引双保险，保证串行/并发下奖励只发一次）
    approved_exists = db.query(TaskSubmission).filter(
        TaskSubmission.task_id == sub.task_id,
        TaskSubmission.review_status == "approved",
    ).first()
    if approved_exists:
        raise HTTPException(status_code=400, detail="该任务已有审核通过的提交，本次审核无效")

    # 1) 标记通过（部分唯一索引兑底：同一任务并发多条 approved 时，
    # 第二个提交会在 commit 时触发 IntegrityError，回滚并拒绝，确保发奖只发生一次）
    sub.review_status = "approved"
    sub.review_note = note
    sub.reviewed_by = reviewer.id if reviewer else None
    sub.reviewer_role = reviewer_role
    sub.reviewed_at = now_local()
    sub.is_effective = True
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该任务已有审核通过的提交，本次审核无效")

    # 2) 任务置为完成（奖励发放幂等的状态锚点）
    task.status = "done"
    task.done_at = now_local()
    db.commit()

    # 3) 发积分
    user = db.get(User, sub.user_id)
    gained = task.reward_points or 0
    user.points = (user.points or 0) + gained
    db.commit()
    db.refresh(user)

    # 4) 重算连续学习天数
    recompute_study_streak(db, user)
    db.refresh(user)

    # 5) 宠物成长：多宠物场景随机选取一只活跃宠物（同 approve_checkin 策略）
    pet_result = None
    xp = task.reward_xp or 0
    if xp > 0:
        active_pets = db.query(PetAdoption).filter_by(user_id=user.id, is_active=True).all()
        target_pet = random.choice(active_pets) if active_pets else None
        if target_pet:
            old_stage = target_pet.current_stage
            pet_result = apply_xp_gain(db, target_pet, user, xp)
            db.add(PetFeedLog(
                user_id=user.id,
                adoption_id=target_pet.id,
                feed_type="task",
                xp_gained=xp,
                total_xp_after=target_pet.current_xp,
                stage_before=old_stage,
                stage_after=pet_result["new_stage"],
                trigger_task_submission_id=sub.id,
            ))
            if pet_result["stage_changed"]:
                _notify_stage_up(db, user, target_pet, old_stage, pet_result["new_stage"])
    db.commit()
    db.refresh(user)

    # 6) 勋章判定（幂等）
    new_badges = check_and_award_badges(db, user)

    # 6.5) 成长农场：任务审核通过 → 转化成长能量（未开通农场静默跳过，开通时回填）
    from . import farm_service
    farm_gain = farm_service.on_task_approved(db, user.id, sub.id, task.title)

    # 7) 通知学生与家长
    msg = f"任务「{task.title}」审核通过，+{gained} 积分，当前积分 {user.points}。"
    if farm_gain:
        msg += f" 成长能量 +{farm_gain}⚡"
    if pet_result:
        pet_msg = f"宠物成长 +{pet_result['xp_gained']} XP"
        if pet_result["stage_changed"]:
            pet_msg += f"，升级到 {get_stage_emoji(pet_result['new_stage'])}{get_stage_label(pet_result['new_stage'])}"
        msg += f" {pet_msg}"
    if new_badges:
        msg += " 解锁勋章：" + "、".join(b.badge_name for b in new_badges) + "！"
    notify(
        db, user.id, "student", "learning",
        f"✅ 学习任务审核通过，+{gained} 积分",
        msg,
        sub.id,
    )
    notify_parents_of_student(
        db, user, "learning", f"孩子的任务「{task.title}」已通过审核",
        f"任务「{task.title}」审核通过，孩子获得 {gained} 积分。",
        sub.id,
    )
    return sub


def reject_submission(db, sub: TaskSubmission, reviewer: User | None, reviewer_role: str, note: str = None) -> TaskSubmission:
    if sub.review_status == "rejected":
        raise HTTPException(status_code=400, detail="该提交已被拒绝")
    sub.review_status = "rejected"
    sub.review_note = note
    sub.reviewed_by = reviewer.id if reviewer else None
    sub.reviewer_role = reviewer_role
    sub.reviewed_at = now_local()
    sub.is_effective = False
    db.commit()

    task = db.get(LearningTask, sub.task_id)
    title = task.title if task else "学习任务"
    notify(
        db, sub.user_id, "student", "learning",
        "❌ 学习任务审核未通过",
        f"任务「{title}」的提交未通过审核。" + (f"原因：{note}" if note else ""),
        sub.id,
    )
    return sub


# ---------- 连续学习天数 ----------

def recompute_study_streak(db, user: User) -> tuple[int, int]:
    """基于已批准提交的审核日期重算连续学习天数（复用打卡 _streaks 算法）。"""
    subs = db.query(TaskSubmission).filter(
        TaskSubmission.user_id == user.id,
        TaskSubmission.review_status == "approved",
        TaskSubmission.reviewed_at.isnot(None),
    ).all()
    dates = [s.reviewed_at.date() for s in subs]
    current, longest = _streaks(dates)
    user.study_streak = current
    user.study_longest_streak = max(user.study_longest_streak or 0, longest)
    db.commit()
    return current, longest


# ---------- 成就勋章 ----------

def _check_plan_first(db, user) -> bool:
    return db.query(TaskSubmission).filter_by(
        user_id=user.id, review_status="approved").count() >= 1


def _check_do_ten(db, user) -> bool:
    return db.query(TaskSubmission).filter_by(
        user_id=user.id, review_status="approved").count() >= 10


def _check_multi_subject(db, user) -> bool:
    rows = (
        db.query(LearningTask.subject_id)
        .join(TaskSubmission, TaskSubmission.task_id == LearningTask.id)
        .filter(TaskSubmission.user_id == user.id, TaskSubmission.review_status == "approved")
        .filter(LearningTask.subject_id.isnot(None))
        .distinct().count()
    )
    return rows >= 3


def _check_streak7(db, user) -> bool:
    return (user.study_streak or 0) >= 7 or (user.study_longest_streak or 0) >= 7


def _check_full_plan(db, user) -> bool:
    plans = db.query(LearningPlan).filter_by(plan_type="instance", student_id=user.id).all()
    for p in plans:
        prog = plan_progress(db, p)
        if prog["total"] > 0 and prog["done"] == prog["total"]:
            return True
    return False


_BADGE_CHECKS = {
    "plan_first": _check_plan_first,
    "do_ten": _check_do_ten,
    "multi_subject": _check_multi_subject,
    "streak7": _check_streak7,
    "full_plan": _check_full_plan,
}


def check_and_award_badges(db, user: User) -> list[UserBadge]:
    """判定并授予满足条件的勋章（同用户同 badge_key 幂等）。返回本次新授予列表。"""
    owned = {b.badge_key for b in db.query(UserBadge).filter_by(user_id=user.id).all()}
    awarded = []
    for key, (name, _desc) in BADGE_DEFS.items():
        if key in owned:
            continue
        try:
            ok = _BADGE_CHECKS[key](db, user)
        except Exception:
            ok = False
        if ok:
            b = UserBadge(user_id=user.id, badge_key=key, badge_name=name)
            db.add(b)
            awarded.append(b)
    if awarded:
        db.commit()
        for b in awarded:
            notify(
                db, user.id, "student", "system",
                f"🏅 获得新勋章：{b.badge_name}",
                f"恭喜！你解锁了成就勋章「{b.badge_name}」，去勋章墙看看吧！",
            )
    return awarded


def badge_wall(db, user: User) -> list[dict]:
    """勋章墙：全量定义 + 是否已得。"""
    owned = {b.badge_key: b for b in db.query(UserBadge).filter_by(user_id=user.id).all()}
    out = []
    for key, (name, desc) in BADGE_DEFS.items():
        got = owned.get(key)
        out.append({
            "key": key, "name": name, "description": desc,
            "earned": bool(got),
            "earned_at": got.earned_at if got else None,
        })
    return out
