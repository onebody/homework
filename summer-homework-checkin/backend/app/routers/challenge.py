"""闯关任务路由"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import User, ChallengeTask, ChallengeCheckIn, Notification
from ..deps import get_current_user
from ..services import challenge_service
from ..utils.storage import save_upload, public_url

router = APIRouter(prefix="/api/challenge", tags=["challenge"])


# ── 学生端 ──────────────────────────────────────────────────────────────────

@router.get("/tasks")
def list_tasks_for_student(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """学生端：获取闯关任务列表"""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="仅限学生访问")
    return challenge_service.list_tasks_for_student(db, current_user.id)


@router.get("/tasks/{task_id}")
def get_task_detail(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """学生端：获取任务详情"""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="仅限学生访问")

    task = db.query(ChallengeTask).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    status_info = challenge_service.get_student_task_status(db, task, current_user.id)
    unlocked = challenge_service.is_task_unlocked(task)
    latest = status_info["latest_checkin"]
    attachments = []
    if latest and latest.attachments:
        try:
            attachments = json.loads(latest.attachments)
        except Exception:
            pass

    return {
        "id": task.id,
        "name": task.name,
        "description": task.description,
        "sort_order": task.sort_order,
        "reward_points": task.reward_points,
        "status": "active" if unlocked else "locked",
        "unlock_at": task.unlock_at.isoformat() if task.unlock_at else None,
        "unlock_condition": task.unlock_condition,
        "user_status": status_info["status"],
        "latest_checkin": {
            "id": latest.id,
            "content": latest.content,
            "attachments": attachments,
            "review_status": latest.review_status,
            "review_note": latest.review_note,
            "created_at": latest.created_at.isoformat() if latest else None,
        } if latest else None,
    }


@router.post("/tasks/{task_id}/checkin")
def submit_checkin(
    task_id: int,
    content: Optional[str] = Form(None),
    attachments: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """学生端：提交任务打卡（Form 表单）"""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="仅限学生访问")

    # 解析附件
    attachment_str = None
    if attachments:
        try:
            # 验证是合法 JSON
            json.loads(attachments)
            attachment_str = attachments
        except Exception:
            attachment_str = json.dumps([attachments])

    data = {"content": content, "attachments": attachment_str}
    try:
        result = challenge_service.submit_checkin(db, current_user, task_id, data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/checkin-with-content")
def submit_checkin_with_content(
    task_id: int,
    content: Optional[str] = Form(None),
    attachments: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """学生端：提交任务打卡（支持文件附件）"""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="仅限学生访问")

    # 解析附件
    attachment_str = None
    if attachments:
        try:
            # 验证是合法 JSON
            json.loads(attachments)
            attachment_str = attachments
        except Exception:
            attachment_str = json.dumps([attachments])

    data = {"content": content, "attachments": attachment_str}
    try:
        result = challenge_service.submit_checkin(db, current_user, task_id, data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """上传打卡附件（图片/视频）"""
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    path = save_upload(contents, current_user.id, "challenge")
    url = public_url(path)
    return {"url": url, "path": path}


@router.get("/my-checkins")
def get_my_checkins(
    task_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """学生端：获取我的闯关打卡记录"""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="仅限学生访问")

    q = db.query(ChallengeCheckIn).filter(ChallengeCheckIn.user_id == current_user.id)
    if task_id:
        q = q.filter(ChallengeCheckIn.task_id == task_id)
    checkins = q.order_by(ChallengeCheckIn.created_at.desc()).all()

    result = []
    for c in checkins:
        task = db.query(ChallengeTask).get(c.task_id)
        attachments = []
        if c.attachments:
            try:
                attachments = json.loads(c.attachments)
            except Exception:
                pass
        result.append({
            "id": c.id,
            "task_id": c.task_id,
            "task_name": task.name if task else "",
            "content": c.content,
            "attachments": attachments,
            "review_status": c.review_status,
            "review_note": c.review_note,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


# ── 管理端 ──────────────────────────────────────────────────────────────────

@router.get("/admin/tasks")
def admin_list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：获取所有任务列表"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")

    tasks = db.query(ChallengeTask).order_by(ChallengeTask.sort_order).all()
    result = []
    for t in tasks:
        stats = challenge_service.get_task_stats(db, t)
        unlocked = challenge_service.is_task_unlocked(t)
        result.append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "sort_order": t.sort_order,
            "reward_points": t.reward_points,
            "status": t.status,
            "is_unlocked": unlocked,
            "unlock_at": t.unlock_at.isoformat() if t.unlock_at else None,
            "unlock_condition": t.unlock_condition,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "total_checkins": stats["total_checkins"],
            "pending_reviews": stats["pending_reviews"],
        })
    return result


@router.post("/admin/tasks")
def admin_create_task(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    sort_order: int = Form(0),
    reward_points: int = Form(10),
    status: str = Form("locked"),
    unlock_at: Optional[str] = Form(None),
    unlock_condition: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：创建任务"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")

    data = {
        "name": name,
        "description": description,
        "sort_order": sort_order,
        "reward_points": reward_points,
        "status": status,
        "unlock_at": unlock_at,
        "unlock_condition": unlock_condition,
    }
    task = challenge_service.create_task(db, data, current_user.id)
    return {"message": "任务创建成功", "task_id": task.id}


@router.put("/admin/tasks/{task_id}")
def admin_update_task(
    task_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    sort_order: Optional[int] = Form(None),
    reward_points: Optional[int] = Form(None),
    status: Optional[str] = Form(None),
    unlock_at: Optional[str] = Form(None),
    unlock_condition: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：更新任务"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")

    task = db.query(ChallengeTask).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if sort_order is not None:
        data["sort_order"] = sort_order
    if reward_points is not None:
        data["reward_points"] = reward_points
    if status is not None:
        data["status"] = status
    if unlock_at is not None:
        data["unlock_at"] = unlock_at
    if unlock_condition is not None:
        data["unlock_condition"] = unlock_condition

    challenge_service.update_task(db, task, data)
    return {"message": "任务更新成功"}


@router.delete("/admin/tasks/{task_id}")
def admin_delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：删除任务"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")

    task = db.query(ChallengeTask).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    challenge_service.delete_task(db, task)
    return {"message": "任务已删除"}


@router.post("/admin/tasks/{task_id}/unlock")
def admin_unlock_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：手动开放任务"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")

    task = db.query(ChallengeTask).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task.status = "active"
    db.commit()
    return {"message": "任务已开放"}


@router.get("/admin/checkins")
def admin_list_checkins(
    task_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：获取打卡记录列表"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")
    return challenge_service.list_all_checkins(db, task_id=task_id, status=status)


@router.get("/admin/checkins/pending-count")
def admin_pending_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：获取待审核数量"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")

    count = db.query(ChallengeCheckIn).filter(
        ChallengeCheckIn.review_status == "pending"
    ).count()
    return {"count": count}


@router.put("/admin/checkins/{checkin_id}/review")
def admin_review_checkin(
    checkin_id: int,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """管理端：审核打卡"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅限管理员访问")

    checkin = db.query(ChallengeCheckIn).get(checkin_id)
    if not checkin:
        raise HTTPException(status_code=404, detail="打卡记录不存在")

    action = data.get("status") or data.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="无效的审核操作，需为 approve 或 reject")
    note = data.get("note")
    challenge_service.review_checkin(db, checkin, action, note, current_user.id)
    return {"message": "审核完成"}
