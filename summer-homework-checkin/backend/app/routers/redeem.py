from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from ..models import User, Prize, LotteryRecord
from ..database import get_db
from ..schemas import RedeemRequest, RedeemReplaceRequest, RedemptionOut, MallOut, LotteryRecordOut
from ..deps import get_current_user
from ..services import redeem_service

router = APIRouter(prefix="/api", tags=["redeem"])


class RedeemResult(BaseModel):
    """通用兑换结果：普通奖品返回完整兑换记录；抽奖机会仅返回余额和券数。"""
    redemption: Optional[RedemptionOut] = None
    balance: int
    lottery_tickets: int = 0
    is_lottery_ticket: bool = False
    message: str = ""


@router.get("/mall", response_model=MallOut)
def mall(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """积分商城聚合数据：余额、可兑换奖品、我的兑换、抽奖记录。"""
    prizes = redeem_service.list_prizes_for_mall(db)
    redemptions = redeem_service.list_redemptions(db, user)
    lottery_records = (
        db.query(LotteryRecord).filter_by(user_id=user.id)
        .order_by(LotteryRecord.drawn_at.desc()).all()
    )
    return MallOut(
        points=user.points or 0,
        lottery_tickets=user.lottery_tickets or 0,
        prizes=[{
            "id": p.id, "name": p.name, "description": p.description,
            "category": p.category, "cost_points": p.cost_points,
            "stock": p.stock, "image_url": p.image_url,
            "is_lottery_ticket": p.is_lottery_ticket,
            "ticket_qty": p.ticket_qty,
        } for p in prizes],
        redemptions=[RedemptionOut.model_validate(r) for r in redemptions],
        lottery_records=[LotteryRecordOut.model_validate(r) for r in lottery_records],
    )


@router.post("/redeem", response_model=RedeemResult)
def redeem(req: RedeemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in ("student", "parent"):
        raise HTTPException(status_code=403, detail="仅学生/家长可兑换")
    prize = db.query(Prize).filter(Prize.id == req.prize_id).first()
    is_lottery = prize.is_lottery_ticket if prize else False
    rec, bal = redeem_service.redeem(db, user, req.prize_id)
    if is_lottery:
        return RedeemResult(
            redemption=None,
            balance=bal,
            lottery_tickets=user.lottery_tickets or 0,
            is_lottery_ticket=True,
            message=f"成功兑换抽奖机会，当前抽奖券：{user.lottery_tickets or 0} 张",
        )
    return RedeemResult(
        redemption=RedemptionOut.model_validate(rec),
        balance=bal,
        lottery_tickets=user.lottery_tickets or 0,
        is_lottery_ticket=False,
        message=f"兑换成功：{prize.name if prize else '奖品'}",
    )


@router.post("/redeem/{rid}/replace", response_model=RedemptionOut)
def replace_redeem(
    rid: int, req: RedeemReplaceRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if user.role not in ("student", "parent"):
        raise HTTPException(status_code=403, detail="仅学生/家长可操作")
    rec, _ = redeem_service.replace_redemption(db, user, rid, req.new_prize_id)
    return RedemptionOut.model_validate(rec)
