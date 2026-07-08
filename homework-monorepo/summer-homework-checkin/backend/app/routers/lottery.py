from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import User, Prize, LotteryRecord
from ..database import get_db
from ..schemas import LotteryResult, LotteryRecordOut
from ..deps import get_current_user
from ..services import lottery_service

router = APIRouter(prefix="/api/lottery", tags=["lottery"])


@router.get("/tickets")
def tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = (
        db.query(LotteryRecord).filter_by(user_id=user.id)
        .order_by(LotteryRecord.drawn_at.desc()).all()
    )
    return {
        "tickets": user.lottery_tickets,
        "records": [LotteryRecordOut.model_validate(r) for r in records],
    }


@router.post("/draw", response_model=LotteryResult)
def draw(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="仅学生可抽奖")
    return LotteryResult(**lottery_service.draw(db, user))
