from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import ConvertRequest, ConvertResult, ConversionOut, LotteryTicketLedgerOut
from app import models
from app.services import lottery_service

router = APIRouter(prefix="/api", tags=["convert"])


@router.post("/convert", response_model=ConvertResult)
def convert(req: ConvertRequest, db: Session = Depends(get_db)):
    if not db.query(models.User).filter(models.User.id == req.user_id).first():
        raise HTTPException(status_code=404, detail="用户不存在")
    result = lottery_service.do_convert(db, req.user_id, req.qty)
    c = result["conversion"]
    return ConvertResult(
        conversion=ConversionOut(
            id=c.id,
            user_id=c.user_id,
            qty=c.qty,
            cost_points=c.cost_points,
            status=c.status,
            created_at=c.created_at,
        ),
        balance=result["balance"],
        lottery_tickets=result["lottery_tickets"],
    )


@router.get("/conversions", response_model=list[ConversionOut])
def list_conversions(user_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Conversion)
        .filter(models.Conversion.user_id == user_id)
        .order_by(models.Conversion.created_at.desc())
        .all()
    )
    return [
        ConversionOut(
            id=r.id, user_id=r.user_id, qty=r.qty,
            cost_points=r.cost_points, status=r.status, created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/ticket-ledger", response_model=list[LotteryTicketLedgerOut])
def ticket_ledger(user_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(models.LotteryTicketLedger)
        .filter(models.LotteryTicketLedger.user_id == user_id)
        .order_by(models.LotteryTicketLedger.created_at.desc())
        .all()
    )
    return [
        LotteryTicketLedgerOut(
            id=r.id, user_id=r.user_id, tx_type=r.tx_type, amount=r.amount,
            balance_after=r.balance_after, ref_type=r.ref_type, ref_id=r.ref_id,
            note=r.note, created_at=r.created_at,
        )
        for r in rows
    ]
