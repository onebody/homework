from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ..models import User
from ..database import get_db
from ..deps import get_current_user
from ..schemas import FaceEnrollOut, FaceStatusOut
from ..services import face_service
from ..utils.storage import public_url

router = APIRouter(prefix="/api/face", tags=["face"])


@router.post("/enroll", response_model=FaceEnrollOut)
async def enroll(
    photo: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """采集人脸底图（1:1 比对基准），要求检测到且仅检测到一张人脸。"""
    if user.role != "student":
        raise HTTPException(status_code=403, detail="仅学生可采集人脸底图")
    data = await photo.read()
    if not data:
        raise HTTPException(status_code=400, detail="未收到照片")
    return face_service.enroll(user, data, db)


@router.get("/status", response_model=FaceStatusOut)
def status(user: User = Depends(get_current_user)):
    """查询当前账号人脸底图采集状态。"""
    url = public_url(user.face_id_path) if user.face_id_path else None
    return FaceStatusOut(
        face_enrolled=user.face_enrolled,
        face_id_url=url,
        message="已采集人脸底图" if user.face_enrolled else "尚未采集人脸底图，建议先采集",
    )


@router.delete("/enroll", response_model=FaceStatusOut)
def unenroll(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """撤销人脸底图（仅解绑，不打卡历史记录，已采集的底图文件保留以供审计）。"""
    r = face_service.unenroll(user, db)
    return FaceStatusOut(face_enrolled=r["face_enrolled"], message=r["message"])
