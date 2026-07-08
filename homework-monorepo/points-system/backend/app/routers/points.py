from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import AccountOut, LedgerOut
from app import models

router = APIRouter(prefix="/api", tags=["points"])


@router.get("/points", response_model=AccountOut)
def get_points(user_id: int, db: Session = Depends(get_db)):
    acc = db.query(models.PointAccount).filter(models.PointAccount.user_id == user_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="积分账户不存在")
    return acc


@router.get("/ledger", response_model=list[LedgerOut])
def get_ledger(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """查询积分流水（按时间倒序）。"""
    return (
        db.query(models.PointLedger)
        .filter(models.PointLedger.user_id == user_id)
        .order_by(models.PointLedger.created_at.desc())
        .limit(limit)
        .all()
    )
