"""积分与兑换的核心业务逻辑。

设计要点：
1. 所有「读-改-写」操作都在同一个 SQLAlchemy Session 事务内完成，
   成功统一 commit，异常统一 rollback，保证余额与库存不会半更新。
2. 打卡防重复：业务层先查后写，并辅以 (user_id, check_date) 唯一约束兜底。
3. 兑换校验：先校验有效期/库存/余额，通过后才在同一事务内扣减库存与积分，
   并写一条支出流水，保证「库存-1」与「积分-N」要么同时成功、要么同时失败。
"""
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app import models, config


def get_or_create_account(db: Session, user_id: int) -> models.PointAccount:
    acc = db.query(models.PointAccount).filter_by(user_id=user_id).first()
    if acc is None:
        acc = models.PointAccount(user_id=user_id, balance=0, total_earned=0, total_spent=0)
        db.add(acc)
        db.flush()
    return acc


def compute_streak(db: Session, user_id: int, today: date) -> int:
    """计算截至 today 的连续打卡天数。"""
    last = (
        db.query(models.CheckIn)
        .filter(models.CheckIn.user_id == user_id, models.CheckIn.check_date < today)
        .order_by(models.CheckIn.check_date.desc())
        .first()
    )
    # 仅当昨天也打了卡，连续天数才 +1；中间断一天则重置为 1
    if last and (today - last.check_date).days == 1:
        return last.streak + 1
    return 1


def do_checkin(db: Session, user_id: int):
    today = date.today()

    # 防重复：先查
    existing = db.query(models.CheckIn).filter_by(user_id=user_id, check_date=today).first()
    if existing:
        raise HTTPException(status_code=409, detail="今日已打卡，请勿重复操作")

    streak = compute_streak(db, user_id, today)
    bonus = config.POINTS_STREAK_BONUS if streak % config.STREAK_BONUS_EVERY == 0 else 0
    total = config.POINTS_PER_CHECKIN + bonus

    acc = get_or_create_account(db, user_id)
    checkin = models.CheckIn(
        user_id=user_id,
        check_date=today,
        points_earned=total,
        streak=streak,
        bonus=bonus,
    )
    db.add(checkin)
    acc.balance += total
    acc.total_earned += total
    db.flush()  # 拿到 checkin.id，用于流水关联

    ledger = models.PointLedger(
        user_id=user_id,
        tx_type="earn",
        amount=total,
        balance_after=acc.balance,
        ref_type="checkin",
        ref_id=checkin.id,
        note=f"打卡得积分（连续{streak}天）" + (f" +连续奖励{bonus}" if bonus else ""),
    )
    db.add(ledger)

    try:
        db.commit()
    except IntegrityError:
        # 并发兜底：唯一约束拦截了重复打卡
        db.rollback()
        raise HTTPException(status_code=409, detail="今日已打卡，请勿重复操作")

    db.refresh(checkin)
    return {
        "checkin": checkin,
        "points_earned": total,
        "bonus": bonus,
        "streak": streak,
        "balance": acc.balance,
    }


def do_redeem(db: Session, user_id: int, prize_id: int):
    # 注意：SQLite 对行锁支持有限，这里依靠「单事务 + commit 原子性」保证一致；
    # 若改用 PostgreSQL，可在此处对 account / prize 加 with_for_update() 实现悲观锁。
    prize = db.query(models.Prize).filter(models.Prize.id == prize_id).first()
    if not prize:
        raise HTTPException(status_code=404, detail="奖品不存在")

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC，与 SQLite 存储一致
    if prize.valid_from and now < prize.valid_from:
        raise HTTPException(status_code=400, detail="奖品尚未开始兑换")
    if prize.valid_to and now > prize.valid_to:
        raise HTTPException(status_code=400, detail="奖品已过期")

    # 校验库存
    if prize.stock <= 0:
        raise HTTPException(status_code=409, detail="奖品库存不足")

    # 校验积分账户与余额
    acc = db.query(models.PointAccount).filter(models.PointAccount.user_id == user_id).first()
    if acc is None:
        raise HTTPException(status_code=400, detail="积分账户不存在")
    if acc.balance < prize.cost_points:
        raise HTTPException(status_code=400, detail="积分不足，无法兑换")

    # 同一事务内扣减：库存 -1，积分 -N
    acc.balance -= prize.cost_points
    acc.total_spent += prize.cost_points
    prize.stock -= 1

    redemption = models.Redemption(
        user_id=user_id,
        prize_id=prize_id,
        cost_points=prize.cost_points,
        status="issued",
    )
    db.add(redemption)
    db.flush()

    ledger = models.PointLedger(
        user_id=user_id,
        tx_type="spend",
        amount=prize.cost_points,
        balance_after=acc.balance,
        ref_type="redemption",
        ref_id=redemption.id,
        note=f"兑换「{prize.name}」",
    )
    db.add(ledger)

    db.commit()
    db.refresh(redemption)
    return {"redemption": redemption, "balance": acc.balance}
