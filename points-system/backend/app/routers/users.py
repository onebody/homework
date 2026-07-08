from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, datetime, timezone
from app.database import get_db
from app.schemas import UserCreate, UserOut, PrizeOut
from app import models, config

router = APIRouter(prefix="/api", tags=["users"])


@router.post("/register", response_model=UserOut)
def register(req: UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == req.username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = models.User(username=req.username, display_name=req.display_name or req.username)
    db.add(user)
    db.flush()
    # 注册即开通积分账户
    db.add(models.PointAccount(user_id=user.id, balance=0, total_earned=0, total_spent=0))
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.id).all()


@router.get("/dashboard")
def dashboard(user_id: int, db: Session = Depends(get_db)):
    """一次性返回前端看板所需的全部数据。"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    acc = db.query(models.PointAccount).filter(models.PointAccount.user_id == user_id).first()
    balance = acc.balance if acc else 0
    total_earned = acc.total_earned if acc else 0
    total_spent = acc.total_spent if acc else 0
    lottery_tickets = acc.lottery_tickets if acc else 0

    today = date.today()
    today_ci = (
        db.query(models.CheckIn)
        .filter(models.CheckIn.user_id == user_id, models.CheckIn.check_date == today)
        .first()
    )
    last = (
        db.query(models.CheckIn)
        .filter(models.CheckIn.user_id == user_id)
        .order_by(models.CheckIn.check_date.desc())
        .first()
    )
    # 连续天数：若最近一次是今天或昨天，则沿用其 streak；否则为 0
    streak = last.streak if (last and (today - last.check_date).days <= 1) else 0

    ledger = (
        db.query(models.PointLedger)
        .filter(models.PointLedger.user_id == user_id)
        .order_by(models.PointLedger.created_at.desc())
        .limit(20)
        .all()
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC，与 SQLite 存储一致
    prizes = []
    for p in db.query(models.Prize).all():
        available = (
            p.stock > 0
            and (p.valid_from is None or now >= p.valid_from)
            and (p.valid_to is None or now <= p.valid_to)
        )
        prizes.append(
            PrizeOut(
                id=p.id,
                name=p.name,
                description=p.description,
                cost_points=p.cost_points,
                stock=p.stock,
                valid_from=p.valid_from,
                valid_to=p.valid_to,
                can_redeem=available and balance >= p.cost_points,
            )
        )

    redemptions = (
        db.query(models.Redemption)
        .filter(models.Redemption.user_id == user_id)
        .order_by(models.Redemption.created_at.desc())
        .all()
    )
    redemptions_out = [
        {
            "id": r.id,
            "prize_name": r.prize.name,
            "cost_points": r.cost_points,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in redemptions
    ]

    # 抽奖券流水 & 兑换抽奖券记录 & 抽奖记录
    ticket_ledger = (
        db.query(models.LotteryTicketLedger)
        .filter(models.LotteryTicketLedger.user_id == user_id)
        .order_by(models.LotteryTicketLedger.created_at.desc())
        .limit(20)
        .all()
    )
    conversions = (
        db.query(models.Conversion)
        .filter(models.Conversion.user_id == user_id)
        .order_by(models.Conversion.created_at.desc())
        .all()
    )
    lottery_draws = (
        db.query(models.LotteryDraw)
        .filter(models.LotteryDraw.user_id == user_id)
        .order_by(models.LotteryDraw.created_at.desc())
        .all()
    )

    # 抽奖奖池（供前端转盘初始化）
    lottery_pool = [
        {
            "id": lp.id,
            "name": lp.name,
            "description": lp.description,
            "is_win": bool(lp.is_win),
            "weight": lp.weight,
            "stock": lp.stock,
        }
        for lp in db.query(models.LotteryPrize).order_by(models.LotteryPrize.sort_order).all()
    ]

    return {
        "user": {"id": user.id, "username": user.username, "display_name": user.display_name},
        "balance": balance,
        "total_earned": total_earned,
        "total_spent": total_spent,
        "lottery_tickets": lottery_tickets,
        "can_lottery": lottery_tickets >= config.TICKETS_PER_DRAW,
        "points_per_ticket": config.POINTS_PER_TICKET,
        "today_checked_in": today_ci is not None,
        "current_streak": streak,
        "prizes": prizes,
        "lottery_pool": lottery_pool,  # 转盘初始化用
        "redemptions": redemptions_out,
        "conversions": [
            {
                "id": c.id,
                "qty": c.qty,
                "cost_points": c.cost_points,
                "created_at": c.created_at,
            }
            for c in conversions
        ],
        "ticket_ledger": [
            {
                "id": t.id,
                "tx_type": t.tx_type,
                "amount": t.amount,
                "balance_after": t.balance_after,
                "note": t.note,
                "created_at": t.created_at,
            }
            for t in ticket_ledger
        ],
        "lottery_draws": [
            {
                "id": d.id,
                "prize_name": d.prize_name,
                "is_win": d.is_win,
                "created_at": d.created_at,
            }
            for d in lottery_draws
        ],
        "ledger": [
            {
                "id": l.id,
                "tx_type": l.tx_type,
                "amount": l.amount,
                "balance_after": l.balance_after,
                "note": l.note,
                "created_at": l.created_at,
            }
            for l in ledger
        ],
    }
