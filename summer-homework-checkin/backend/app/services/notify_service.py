from ..models import Notification, StudentParent
from ..database import SessionLocal


def notify(db, user_id: int, role: str, ntype: str, title: str, content: str = "", related_id: int = None):
    n = Notification(
        user_id=user_id, recipient_role=role, type=ntype,
        title=title, content=content, related_id=related_id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    # WebSocket 实时推送（fire-and-forget）：落库优先，推送失败静默，
    # 前端断线时降级 30s 轮询 /api/learning/notifications/unread 保证不丢
    try:
        from .. import ws as ws_mod
        ws_mod.push_notification(user_id, {
            "type": "notification",
            "id": n.id,
            "ntype": ntype,
            "title": title,
            "content": content,
            "related_id": related_id,
        })
    except Exception:
        pass
    return n


def notify_parents_of_student(db, student, ntype: str, title: str, content: str = "", related_id: int = None):
    binds = db.query(StudentParent).filter_by(student_id=student.id).all()
    for b in binds:
        notify(db, b.parent_id, "parent", ntype, title, content, related_id)
