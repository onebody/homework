from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import RedeemRequest, RedeemResult, RedemptionOut
from app import models
from app.services import points_service

router = APIRouter(prefix="/api", tags=["redeem"])


@router.post("/redeem", response_model=RedeemResult)
def redeem(req: RedeemRequest, db: Session = Depends(get_db)):
    if not db.query(models.User).filter(models.User.id == req.user_id).first():
        raise HTTPException(status_code=404, detail="用户不存在")
    result = points_service.do_redeem(db, req.user_id, req.prize_id)
    r = result["redemption"]
    return RedeemResult(
        redemption=RedemptionOut(
            id=r.id,
            user_id=r.user_id,
            prize_id=r.prize_id,
            prize_name=r.prize.name,
            cost_points=r.cost_points,
            status=r.status,
            created_at=r.created_at,
        ),
        balance=result["balance"],
    )


@router.get("/redemptions", response_model=list[RedemptionOut])
def list_redemptions(user_id: int, db: Session = Depends(get_db)):
    """查询某用户的兑换记录。"""
    rows = (
        db.query(models.Redemption)
        .filter(models.Redemption.user_id == user_id)
        .order_by(models.Redemption.created_at.desc())
        .all()
    )
    return [
        RedemptionOut(
            id=r.id,
            user_id=r.user_id,
            prize_id=r.prize_id,
            prize_name=r.prize.name,
            cost_points=r.cost_points,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rows
    ]
