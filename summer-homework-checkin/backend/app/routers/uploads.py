import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..deps import get_current_user
from ..models import User, StudentParent
from ..utils.storage import validate_upload_path

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _owner_id(relative_path: str) -> str:
    """上传路径首段即文件归属的用户 ID（见 storage.save_upload 的命名规则）。"""
    return relative_path.replace(os.sep, "/").split("/", 1)[0]


def _can_read(owner: str, user: User, db: Session) -> bool:
    """归属校验：防止通过遍历他人 user_id 读取人脸/打卡照片。"""
    if user.role == "admin":
        return True
    if user.role == "student":
        return owner == str(user.id)
    if user.role == "parent":
        # 家长仅可读取其已绑定孩子的文件
        bound = {
            str(b.student_id)
            for b in db.query(StudentParent).filter_by(parent_id=user.id).all()
        }
        return owner in bound
    return False


@router.get("/{path:path}")
def get_upload(
    path: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """认证下载上传文件。替代原先公开挂载的 /uploads 静态目录。"""
    if not validate_upload_path(path):
        raise HTTPException(status_code=403, detail="非法的文件路径")

    if not _can_read(_owner_id(path), user, db):
        raise HTTPException(status_code=403, detail="无权访问该文件")

    full = os.path.join(UPLOAD_DIR, path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(full, headers={"Cache-Control": "private, max-age=300"})
