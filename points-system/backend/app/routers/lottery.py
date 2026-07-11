from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import LotteryPrizeOut, LotteryDrawOut, DrawResult, DrawRequest, WheelSectorOut
from app import models
from app.services import lottery_service

router = APIRouter(prefix="/api", tags=["lottery"])


@router.get("/lottery/pool", response_model=list[LotteryPrizeOut])
def lottery_pool(db: Session = Depends(get_db)):
    """奖池配置（供前端展示中奖概率与库存）。"""
    rows = db.query(models.LotteryPrize).order_by(models.LotteryPrize.sort_order).all()
    return [
        LotteryPrizeOut(
            id=p.id, name=p.name, description=p.description,
            weight=p.weight, stock=p.stock, is_win=p.is_win,
        )
        for p in rows
    ]


@router.post("/lottery/draw", response_model=DrawResult)
def draw(req: DrawRequest, db: Session = Depends(get_db)):
    if not db.query(models.User).filter(models.User.id == req.user_id).first():
        raise HTTPException(status_code=404, detail="用户不存在")
    result = lottery_service.do_draw(db, req.user_id)
    d = result["draw"]
    # 将后端返回的扇区字典列表转换为 WheelSectorOut
    sectors_out = [
        WheelSectorOut(
            id=s["id"], name=s["name"],
            is_win=s["is_win"], weight=s["weight"],
        )
        for s in result["sectors"]
    ]
    return DrawResult(
        draw=LotteryDrawOut(
            id=d.id, user_id=d.user_id, prize_name=d.prize_name,
            is_win=d.is_win, created_at=d.created_at,
        ),
        lottery_tickets=result["lottery_tickets"],
        can_lottery=result["can_lottery"],
        sectors=sectors_out,
        winning_index=result["winning_index"],
    )


@router.get("/lottery/draws", response_model=list[LotteryDrawOut])
def list_draws(user_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(models.LotteryDraw)
        .filter(models.LotteryDraw.user_id == user_id)
        .order_by(models.LotteryDraw.created_at.desc())
        .all()
    )
    return [
        LotteryDrawOut(
            id=r.id, user_id=r.user_id, prize_name=r.prize_name,
            is_win=r.is_win, created_at=r.created_at,
        )
        for r in rows
    ]
