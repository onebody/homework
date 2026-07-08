from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database import get_db
from app.schemas import PrizeOut
from app import models

router = APIRouter(prefix="/api", tags=["prize"])


@router.get("/prizes", response_model=list[PrizeOut])
def list_prizes(user_id: int = Query(None), db: Session = Depends(get_db)):
    """奖品列表。传入 user_id 时，附带 can_redeem 标记（余额/库存/有效期综合判断）。"""
    prizes = db.query(models.Prize).all()
    acc_balance = None
    if user_id is not None:
        acc = db.query(models.PointAccount).filter(models.PointAccount.user_id == user_id).first()
        acc_balance = acc.balance if acc else 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC，与 SQLite 存储一致
    out = []
    for p in prizes:
        available = (
            p.stock > 0
            and (p.valid_from is None or now >= p.valid_from)
            and (p.valid_to is None or now <= p.valid_to)
        )
        can = available and (acc_balance is None or acc_balance >= p.cost_points)
        out.append(
            PrizeOut(
                id=p.id,
                name=p.name,
                description=p.description,
                cost_points=p.cost_points,
                stock=p.stock,
                valid_from=p.valid_from,
                valid_to=p.valid_to,
                can_redeem=can,
            )
        )
    return out
