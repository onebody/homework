"""积分兑换抽奖券与抽奖的核心业务逻辑。

设计要点（与 points_service 保持一致）：
1. 所有「读-改-写」操作在同一个 SQLAlchemy Session 事务内完成，
   成功统一 commit，异常统一 rollback，杜绝「积分扣了券没到」「券发了抽奖却没解锁」等半更新。
2. 兑换抽奖券：先校验积分余额 ≥ 本次所需积分（含最低门槛），通过后在同事务内
   扣减积分、增加抽奖券，并各写一条流水（积分支出 + 抽奖券发放）。
3. 抽奖：先校验抽奖券 ≥ 1（券不足即视为未解锁），通过后在同事务内扣减 1 张抽奖券、
   按权重随机选奖、写抽奖券消耗流水与抽奖记录。券减到 0 时抽奖权限自动失效（派生自余额）。
4. 抽奖权限「解锁/锁定」不单独存状态位，而是直接由 account.lottery_tickets ≥ 1 派生，
   从根上避免状态与余额不一致。
"""
import random
import threading
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app import models, config
from app.services.points_service import get_or_create_account

# 单进程内部并发控制：uvicorn 线程池内多个请求会并发读写同一账户，
# 用进程内锁把「读-改-写」整体串行化，杜绝 SQLite 下「丢失更新」
# （两个请求读到同一余额、各自扣减、后者覆盖前者）。
# 注：多进程/多实例部署请改用数据库的悲观锁（PostgreSQL 的 with_for_update()）。
_account_lock = threading.Lock()


def do_convert(db: Session, user_id: int, qty: int):
    """积分兑换抽奖券：qty 张，消耗 qty * POINTS_PER_TICKET 积分。"""
    if qty is None or qty < 1:
        raise HTTPException(status_code=400, detail="兑换数量必须 ≥ 1")

    with _account_lock:
        cost = qty * config.POINTS_PER_TICKET

        acc = get_or_create_account(db, user_id)

        # 最低门槛 + 余额校验：连 1 张都换不起，直接拦截并给出清晰提示
        if acc.balance < config.POINTS_PER_TICKET:
            raise HTTPException(
                status_code=400,
                detail=f"积分不足，无法兑换抽奖券（至少需 {config.POINTS_PER_TICKET} 分，当前 {acc.balance} 分）",
            )
        if acc.balance < cost:
            raise HTTPException(
                status_code=400,
                detail=f"积分不足，本次兑换 {qty} 张需 {cost} 分，当前仅 {acc.balance} 分",
            )

        # 同一事务内：扣积分 + 加抽奖券
        acc.balance -= cost
        acc.total_spent += cost
        acc.lottery_tickets += qty

        conversion = models.Conversion(
            user_id=user_id,
            qty=qty,
            cost_points=cost,
            status="issued",
        )
        db.add(conversion)
        db.flush()

        # 积分支出流水
        db.add(models.PointLedger(
            user_id=user_id,
            tx_type="spend",
            amount=cost,
            balance_after=acc.balance,
            ref_type="convert",
            ref_id=conversion.id,
            note=f"兑换 {qty} 张抽奖券",
        ))
        # 抽奖券发放流水
        db.add(models.LotteryTicketLedger(
            user_id=user_id,
            tx_type="issue",
            amount=qty,
            balance_after=acc.lottery_tickets,
            ref_type="convert",
            ref_id=conversion.id,
            note=f"积分兑换获得 {qty} 张抽奖券（-{cost} 分）",
        ))

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="兑换处理冲突，请重试")

        db.refresh(conversion)
        return {
            "conversion": conversion,
            "balance": acc.balance,
            "lottery_tickets": acc.lottery_tickets,
        }


def _pick_lottery_prize(db: Session):
    """按 weight 加权随机选出当前可发放的奖池条目（库存为 None 或 >0 视为可发放）。"""
    prizes = db.query(models.LotteryPrize).order_by(models.LotteryPrize.sort_order).all()
    available = [p for p in prizes if p.stock is None or p.stock > 0]
    if not available:
        return None
    total_weight = sum(p.weight for p in available)
    r = random.uniform(0, total_weight)
    upto = 0
    for p in available:
        upto += p.weight
        if r <= upto:
            return p
    return available[-1]


def do_draw(db: Session, user_id: int):
    """发起一次抽奖：消耗 1 张抽奖券并执行加权随机抽奖。"""
    with _account_lock:
        acc = get_or_create_account(db, user_id)

        # 抽奖权限动态校验：抽奖券不足 1 张即视为未解锁，拦截抽奖
        if acc.lottery_tickets < config.TICKETS_PER_DRAW:
            raise HTTPException(
                status_code=409,
                detail=f"抽奖券不足，无法抽奖（需至少 {config.TICKETS_PER_DRAW} 张，当前 {acc.lottery_tickets} 张）",
            )

        # 同事务内：先扣券，再抽奖，保证「扣券」与「抽奖结果落库」原子
        acc.lottery_tickets -= config.TICKETS_PER_DRAW

        prize = _pick_lottery_prize(db)
        if prize is None:
            # 理论上不会发生（奖池含不限量「谢谢参与」），兜底保护
            raise HTTPException(status_code=500, detail="奖池暂无可发放奖品")

        # 有限库存奖品扣库存
        if prize.stock is not None:
            prize.stock -= 1

        draw = models.LotteryDraw(
            user_id=user_id,
            prize_id=prize.id,
            prize_name=prize.name,
            is_win=prize.is_win,
        )
        db.add(draw)
        db.flush()

        # 抽奖券消耗流水
        db.add(models.LotteryTicketLedger(
            user_id=user_id,
            tx_type="consume",
            amount=config.TICKETS_PER_DRAW,
            balance_after=acc.lottery_tickets,
            ref_type="draw",
            ref_id=draw.id,
            note=f"抽奖消耗 {config.TICKETS_PER_DRAW} 张（{prize.name}）",
        ))

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="抽奖处理冲突，请重试")

        db.refresh(draw)
        return {
            "draw": draw,
            "lottery_tickets": acc.lottery_tickets,
            # 抽奖权限由余额派生：扣到 0 即自动锁定
            "can_lottery": acc.lottery_tickets >= config.TICKETS_PER_DRAW,
        }
