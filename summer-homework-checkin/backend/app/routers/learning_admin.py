"""学习成长计划 - 管理端 API（prefix /api/admin/learning）。

学科/学期/班级/模板/指派/审核配置/提交审核队列。
独立成文件避免 routers/admin.py 继续膨胀。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_role
from ..models import (
    ClassGroup, LearningConfig, LearningPlan, LearningTask, ProgressRecord,
    Semester, Subject, TaskSubmission, User,
)
from ..schemas import (
    ClassGroupIn, ClassGroupOut, ClassMembersRequest, LearningConfigIn,
    PlanAssignRequest, SemesterIn, SemesterOut, SubjectIn, SubjectOut, TaskIn,
)
from ..services import learning_service as ls
from .learning import serialize_plan, serialize_submission, serialize_task

router = APIRouter(prefix="/api/admin/learning", tags=["learning-admin"])

_admin = require_role("admin")


# ---------- 全局配置 ----------

@router.get("/config")
def get_config(_user: User = Depends(_admin), db: Session = Depends(get_db)):
    cfg = ls.get_or_create_config(db)
    return {
        "mode": cfg.mode or "summer",
        "review_mode": cfg.review_mode or "admin",
        "current_semester_id": cfg.current_semester_id,
    }


@router.put("/config")
def update_config(req: LearningConfigIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    cfg = ls.get_or_create_config(db)
    if req.mode is not None:
        if req.mode not in ("summer", "semester", "holiday"):
            raise HTTPException(status_code=400, detail="mode 取值：summer|semester|holiday")
        cfg.mode = req.mode
    if req.review_mode is not None:
        if req.review_mode not in ("auto", "parent", "admin"):
            raise HTTPException(status_code=400, detail="review_mode 取值：auto|parent|admin")
        cfg.review_mode = req.review_mode
    if req.current_semester_id is not None:
        if req.current_semester_id > 0 and not db.get(Semester, req.current_semester_id):
            raise HTTPException(status_code=404, detail="学期不存在")
        cfg.current_semester_id = req.current_semester_id or None
    from ..utils.timeutil import now_local
    cfg.updated_at = now_local()
    db.commit()
    return {"ok": True, "mode": cfg.mode, "review_mode": cfg.review_mode,
            "current_semester_id": cfg.current_semester_id}


# ---------- 学科 CRUD ----------

@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(_user: User = Depends(_admin), db: Session = Depends(get_db)):
    rows = db.query(Subject).order_by(Subject.sort_order, Subject.id).all()
    return [SubjectOut.model_validate(s) for s in rows]


@router.post("/subjects", response_model=SubjectOut)
def create_subject(req: SubjectIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    if not (1 <= req.grade_min <= req.grade_max <= 6):
        raise HTTPException(status_code=400, detail="学段范围必须满足 1 ≤ grade_min ≤ grade_max ≤ 6")
    s = Subject(**req.model_dump(), is_preset=False)
    db.add(s)
    db.commit()
    db.refresh(s)
    return SubjectOut.model_validate(s)


@router.put("/subjects/{sid}", response_model=SubjectOut)
def update_subject(sid: int, req: SubjectIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    s = db.get(Subject, sid)
    if not s:
        raise HTTPException(status_code=404, detail="学科不存在")
    if not (1 <= req.grade_min <= req.grade_max <= 6):
        raise HTTPException(status_code=400, detail="学段范围必须满足 1 ≤ grade_min ≤ grade_max ≤ 6")
    for k, v in req.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return SubjectOut.model_validate(s)


@router.delete("/subjects/{sid}")
def delete_subject(sid: int, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    s = db.get(Subject, sid)
    if not s:
        raise HTTPException(status_code=404, detail="学科不存在")
    if db.query(LearningTask).filter_by(subject_id=sid).count() > 0:
        # 已被任务引用时不物理删除，仅下架
        s.status = "off"
        db.commit()
        return {"ok": True, "message": "学科已被任务引用，已改为下架"}
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------- 学期 CRUD ----------

@router.get("/semesters", response_model=list[SemesterOut])
def list_semesters(_user: User = Depends(_admin), db: Session = Depends(get_db)):
    rows = db.query(Semester).order_by(Semester.start_date.desc(), Semester.id.desc()).all()
    return [SemesterOut.model_validate(s) for s in rows]


@router.post("/semesters", response_model=SemesterOut)
def create_semester(req: SemesterIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    if req.end_date < req.start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    if req.type not in ("semester", "holiday", "summer"):
        raise HTTPException(status_code=400, detail="type 取值：semester|holiday|summer")
    s = Semester(**req.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return SemesterOut.model_validate(s)


@router.put("/semesters/{sid}", response_model=SemesterOut)
def update_semester(sid: int, req: SemesterIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    s = db.get(Semester, sid)
    if not s:
        raise HTTPException(status_code=404, detail="学期不存在")
    if req.end_date < req.start_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
    for k, v in req.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return SemesterOut.model_validate(s)


@router.delete("/semesters/{sid}")
def delete_semester(sid: int, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    s = db.get(Semester, sid)
    if not s:
        raise HTTPException(status_code=404, detail="学期不存在")
    if db.query(LearningPlan).filter_by(semester_id=sid).count() > 0:
        s.status = "archived"
        db.commit()
        return {"ok": True, "message": "学期已有计划引用，已改为归档"}
    cfg = ls.get_or_create_config(db)
    if cfg.current_semester_id == sid:
        cfg.current_semester_id = None
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---------- 班级与分班 ----------

@router.get("/classes", response_model=list[ClassGroupOut])
def list_classes(grade: int = None, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    q = db.query(ClassGroup)
    if grade:
        q = q.filter(ClassGroup.grade == grade)
    out = []
    for c in q.order_by(ClassGroup.grade, ClassGroup.id).all():
        item = ClassGroupOut.model_validate(c)
        item.member_count = db.query(User).filter_by(class_id=c.id, role="student").count()
        out.append(item)
    return out


@router.post("/classes", response_model=ClassGroupOut)
def create_class(req: ClassGroupIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    if not (1 <= req.grade <= 6):
        raise HTTPException(status_code=400, detail="年级取值 1-6")
    c = ClassGroup(name=req.name.strip(), grade=req.grade)
    db.add(c)
    db.commit()
    db.refresh(c)
    return ClassGroupOut.model_validate(c)


@router.put("/classes/{cid}", response_model=ClassGroupOut)
def update_class(cid: int, req: ClassGroupIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    c = db.get(ClassGroup, cid)
    if not c:
        raise HTTPException(status_code=404, detail="班级不存在")
    if not (1 <= req.grade <= 6):
        raise HTTPException(status_code=400, detail="年级取值 1-6")
    c.name = req.name.strip()
    c.grade = req.grade
    db.commit()
    db.refresh(c)
    return ClassGroupOut.model_validate(c)


@router.delete("/classes/{cid}")
def delete_class(cid: int, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    c = db.get(ClassGroup, cid)
    if not c:
        raise HTTPException(status_code=404, detail="班级不存在")
    for u in db.query(User).filter_by(class_id=cid).all():
        u.class_id = None  # 先解除学生归属，避免悬挂引用
    for t in db.query(LearningPlan).filter_by(class_id=cid, plan_type="template").all():
        t.class_id = None
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/classes/{cid}/members")
def assign_members(cid: int, req: ClassMembersRequest, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    """批量分班：把学生加入指定班级（同时冗余同步年级）。"""
    c = db.get(ClassGroup, cid)
    if not c:
        raise HTTPException(status_code=404, detail="班级不存在")
    count = 0
    for sid in req.student_ids:
        u = db.get(User, sid)
        if u and u.role == "student":
            u.class_id = c.id
            u.grade = c.grade
            count += 1
    db.commit()
    return {"ok": True, "assigned": count}


@router.get("/students")
def list_students(grade: int = None, class_id: int = None, q: str = None,
                  _user: User = Depends(_admin), db: Session = Depends(get_db)):
    """学生列表（供分班选择）。"""
    query = db.query(User).filter(User.role == "student")
    if grade:
        query = query.filter(User.grade == grade)
    if class_id:
        query = query.filter(User.class_id == class_id)
    if q:
        query = query.filter(User.nickname.contains(q))
    rows = query.order_by(User.grade, User.id).limit(200).all()
    clazz_map = {c.id: c.name for c in db.query(ClassGroup).all()}
    return {"items": [{
        "id": u.id, "username": u.username, "nickname": u.nickname,
        "grade": u.grade, "class_id": u.class_id,
        "class_name": clazz_map.get(u.class_id),
    } for u in rows]}


# ---------- 计划模板 CRUD ----------

@router.get("/templates")
def list_templates(semester_id: int = None, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    q = db.query(LearningPlan).filter(LearningPlan.plan_type == "template")
    if semester_id:
        q = q.filter(LearningPlan.semester_id == semester_id)
    plans = q.order_by(LearningPlan.id.desc()).all()
    return {"items": [serialize_plan(db, p) for p in plans]}


@router.post("/templates")
def create_template(payload: dict, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    period_type = payload.get("period_type") or "week"
    if period_type not in ("week", "month"):
        raise HTTPException(status_code=400, detail="period_type 取值：week|month")
    plan = LearningPlan(
        plan_type="template",
        name=name,
        description=payload.get("description"),
        semester_id=payload.get("semester_id"),
        grade=payload.get("grade"),
        class_id=payload.get("class_id"),
        period_type=period_type,
        status="draft",
        created_by=_user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return serialize_plan(db, plan)


@router.put("/templates/{tid}")
def update_template(tid: int, payload: dict, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    plan = db.get(LearningPlan, tid)
    if not plan or plan.plan_type != "template":
        raise HTTPException(status_code=404, detail="模板不存在")
    for field in ("name", "description", "semester_id", "grade", "class_id", "period_type", "status"):
        if field in payload:
            setattr(plan, field, payload[field])
    if plan.status not in ("draft", "published", "archived"):
        raise HTTPException(status_code=400, detail="status 取值：draft|published|archived")
    db.commit()
    return serialize_plan(db, plan)


@router.delete("/templates/{tid}")
def delete_template(tid: int, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    plan = db.get(LearningPlan, tid)
    if not plan or plan.plan_type != "template":
        raise HTTPException(status_code=404, detail="模板不存在")
    # 已实例化则仅归档，保留实例的历史回链
    instances = db.query(LearningPlan).filter_by(plan_type="instance", instantiated_from=tid).count()
    if instances > 0:
        plan.status = "archived"
        db.commit()
        return {"ok": True, "message": f"模板已有 {instances} 个学生实例，已改为归档"}
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.get("/templates/{tid}")
def template_detail(tid: int, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    plan = db.get(LearningPlan, tid)
    if not plan or plan.plan_type != "template":
        raise HTTPException(status_code=404, detail="模板不存在")
    tasks = (
        db.query(LearningTask).filter_by(plan_id=tid)
        .order_by(LearningTask.sort_order, LearningTask.id).all()
    )
    return {"plan": serialize_plan(db, plan),
            "tasks": [serialize_task(db, t) for t in tasks]}


@router.post("/templates/{tid}/tasks")
def add_template_task(tid: int, req: TaskIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    plan = db.get(LearningPlan, tid)
    if not plan or plan.plan_type != "template":
        raise HTTPException(status_code=404, detail="模板不存在")
    if not (req.title or "").strip():
        raise HTTPException(status_code=400, detail="任务标题不能为空")
    if req.subject_id and not db.get(Subject, req.subject_id):
        raise HTTPException(status_code=404, detail="学科不存在")
    task = LearningTask(
        plan_id=tid, title=req.title.strip(),
        subject_id=req.subject_id,
        completion_criteria=req.completion_criteria,
        est_minutes=req.est_minutes or 30,
        due_date=req.due_date,
        reward_points=req.reward_points or 0,
        reward_xp=req.reward_xp or 0,
        sort_order=req.sort_order or 0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return serialize_task(db, task)


@router.put("/tasks/{task_id}")
def update_task(task_id: int, req: TaskIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    task = db.get(LearningTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    data = req.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(task, k, v)
    db.commit()
    return serialize_task(db, task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    task = db.get(LearningTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    plan = db.get(LearningPlan, task.plan_id)
    if plan and plan.plan_type == "instance" and task.status == "done":
        raise HTTPException(status_code=400, detail="已完成的实例任务不可删除")
    db.query(ProgressRecord).filter_by(task_id=task_id).delete()
    db.query(TaskSubmission).filter_by(task_id=task_id).delete()
    db.delete(task)
    db.commit()
    return {"ok": True}


@router.post("/templates/{tid}/publish")
def publish_template(tid: int, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    plan = db.get(LearningPlan, tid)
    if not plan or plan.plan_type != "template":
        raise HTTPException(status_code=404, detail="模板不存在")
    if db.query(LearningTask).filter_by(plan_id=tid).count() == 0:
        raise HTTPException(status_code=400, detail="模板没有任务，不能发布")
    plan.status = "published"
    db.commit()
    return {"ok": True, "message": "模板已发布，学生端可见"}


@router.post("/templates/{tid}/assign")
def assign_template(tid: int, req: PlanAssignRequest, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    """批量实例化：按班级 > 年级 > 指定学生列表的优先级选择目标学生。
    跳过模板年级/班级不匹配的学生，幂等（已有实例不重复创建）。"""
    plan = db.get(LearningPlan, tid)
    if not plan or plan.plan_type != "template":
        raise HTTPException(status_code=404, detail="模板不存在")
    if plan.status != "published":
        raise HTTPException(status_code=400, detail="请先发布模板再指派")

    q = db.query(User).filter(User.role == "student")
    if req.class_id:
        q = q.filter(User.class_id == req.class_id)
    elif req.grade:
        q = q.filter(User.grade == req.grade)
    elif req.student_ids:
        q = q.filter(User.id.in_(req.student_ids))
    else:
        raise HTTPException(status_code=400, detail="需指定 class_id / grade / student_ids 之一")

    assigned, skipped = 0, 0
    for stu in q.all():
        try:
            ls.check_template_visible(db, plan, stu)
        except HTTPException:
            skipped += 1
            continue
        existing = db.query(LearningPlan).filter_by(
            plan_type="instance", student_id=stu.id, instantiated_from=plan.id,
        ).first()
        if existing:
            skipped += 1
            continue
        ls.instantiate_plan(db, plan, stu)
        assigned += 1
    return {"ok": True, "assigned": assigned, "skipped": skipped}


# ---------- 提交审核队列 ----------

@router.get("/submissions")
def list_submissions(status: str = "pending", page: int = 1, size: int = 20,
                     _user: User = Depends(_admin), db: Session = Depends(get_db)):
    from ..utils.pagination import ADMIN_PAGE_SIZE, Page, paginate
    q = db.query(TaskSubmission)
    if status != "all":
        q = q.filter(TaskSubmission.review_status == status)
    q = q.order_by(TaskSubmission.created_at.desc())
    items, meta = paginate(q, page, size, default_size=ADMIN_PAGE_SIZE)
    return Page[dict](items=[serialize_submission(db, s) for s in items], **meta)


@router.put("/submissions/{sid}/review")
def review_submission(sid: int, payload: dict, admin: User = Depends(_admin), db: Session = Depends(get_db)):
    from ..schemas import SubmissionReviewRequest
    req = SubmissionReviewRequest(**payload)
    sub = db.get(TaskSubmission, sid)
    if not sub:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    if req.approved:
        ls.approve_submission(db, sub, reviewer=admin, reviewer_role="admin", note=req.note)
    else:
        ls.reject_submission(db, sub, reviewer=admin, reviewer_role="admin", note=req.note)
    return serialize_submission(db, sub)
