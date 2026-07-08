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
    return n


def notify_parents_of_student(db, student, ntype: str, title: str, content: str = "", related_id: int = None):
    binds = db.query(StudentParent).filter_by(student_id=student.id).all()
    for b in binds:
        notify(db, b.parent_id, "parent", ntype, title, content, related_id)
