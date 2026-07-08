from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import CheckInRequest, CheckInResult
from app import models
from app.services import points_service

router = APIRouter(prefix="/api", tags=["checkin"])


@router.post("/checkin", response_model=CheckInResult)
def checkin(req: CheckInRequest, db: Session = Depends(get_db)):
    if not db.query(models.User).filter(models.User.id == req.user_id).first():
        raise HTTPException(status_code=404, detail="用户不存在")
    return points_service.do_checkin(db, req.user_id)
