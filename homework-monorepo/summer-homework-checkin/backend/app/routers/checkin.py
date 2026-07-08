from datetime import date

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from ..models import User
from ..database import get_db
from ..schemas import CheckInOut, StreakOut
from ..deps import get_current_user
from ..services import checkin_service
from ..utils.storage import save_upload, public_url
from ..utils.image import validate_photo

router = APIRouter(prefix="/api/checkin", tags=["checkin"])


@router.post("", response_model=CheckInOut)
async def do_checkin(
    photo: UploadFile = File(...),
    proof: UploadFile = File(None),
    location_lat: float = Form(None),
    location_lng: float = Form(None),
    check_type: str = Form("normal"),
    makeup_reason: str = Form(None),
    makeup_for_date: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="仅学生可打卡")
    photo_bytes = await photo.read()
    proof_bytes = await proof.read() if proof and proof.filename else b""
    ci, ver = checkin_service.create_checkin(
        db, user, photo_bytes, location_lat, location_lng,
        check_type, makeup_reason, proof_bytes, makeup_for_date,
    )
    return CheckInOut.model_validate(ci)


@router.post("/upload")
async def upload_photo(
    photo: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """通用图片上传（图片查看器「上传」功能使用）。返回可访问 URL。"""
    data = await photo.read()
    ok, detail = validate_photo(data)
    if not ok:
        raise HTTPException(status_code=400, detail=detail)
    path = save_upload(data, user.id, "up")
    return {"photo_path": path, "photo_url": public_url(path)}



@router.get("/today")
def today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status = checkin_service.get_today_status(db, user)
    return status


@router.get("/streak", response_model=StreakOut)
def streak(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    status = checkin_service.get_today_status(db, user)
    return StreakOut(
        current_streak=user.current_streak,
        longest_streak=user.longest_streak,
        effective_checkins=user.effective_checkins,
        lottery_tickets=user.lottery_tickets,
        today_checked=status["today_checked"],
        today_pending=status["today_pending"],
        can_makeup_this_month=status["can_makeup_this_month"],
    )


@router.get("/history", response_model=list[CheckInOut])
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = sorted(user.checkins, key=lambda c: c.check_time, reverse=True)
    return [CheckInOut.model_validate(c) for c in items]
