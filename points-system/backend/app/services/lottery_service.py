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


def _build_wheel_sectors(db: Session):
    """生成转盘扇区：随机 15 个真实奖品 + 随机 3~5 个"谢谢参与"，Fisher-Yates 洗牌。"""
    # 真实奖品（is_win=1，库存可用）
    real_prizes = [
        p for p in db.query(models.LotteryPrize)
        .filter(models.LotteryPrize.is_win == 1)
        .all()
        if p.stock is None or p.stock > 0
    ]
    # 随机选取最多 15 个
    random.shuffle(real_prizes)
    picked_real = real_prizes[:15]

    # 随机 3~5 个"谢谢参与"
    thanks_count = random.randint(3, 5)
    thanks_sectors = [
        {"id": None, "name": "谢谢参与", "is_win": False, "weight": 2, "stock": None}
        for _ in range(thanks_count)
    ]

    # 合并
    sectors = []
    for p in picked_real:
        sectors.append({
            "id": p.id,
            "name": p.name,
            "is_win": True,
            "weight": max(p.weight, 1),
            "stock": p.stock,
        })
    sectors.extend(thanks_sectors)

    # Fisher-Yates 洗牌
    for i in range(len(sectors) - 1, 0, -1):
        j = random.randint(0, i)
        sectors[i], sectors[j] = sectors[j], sectors[i]

    return sectors


def _pick_from_sectors(sectors):
    """从扇区列表中按权重随机选出一项，返回 (index, sector)。"""
    total_weight = sum(s["weight"] for s in sectors)
    r = random.uniform(0, total_weight)
    upto = 0
    for idx, s in enumerate(sectors):
        upto += s["weight"]
        if r <= upto:
            return idx, s
    return len(sectors) - 1, sectors[-1]


def do_draw(db: Session, user_id: int):
    """发起一次抽奖：消耗 1 张抽奖券，生成转盘扇区，执行加权随机抽奖。"""
    with _account_lock:
        acc = get_or_create_account(db, user_id)

        # 抽奖权限动态校验：抽奖券不足 1 张即视为未解锁，拦截抽奖
        if acc.lottery_tickets < config.TICKETS_PER_DRAW:
            raise HTTPException(
                status_code=409,
                detail=f"抽奖券不足，无法抽奖（需至少 {config.TICKETS_PER_DRAW} 张，当前 {acc.lottery_tickets} 张）",
            )

        # 同事务内：先扣券
        acc.lottery_tickets -= config.TICKETS_PER_DRAW

        # 生成转盘扇区（15 真实 + 3~5 谢谢参与）
        sectors = _build_wheel_sectors(db)

        # 从扇区中按权重随机选出结果
        winning_index, winner = _pick_from_sectors(sectors)

        # 如果是真实奖品，扣库存并落库
        prize = None
        is_win = winner["is_win"]
        if is_win and winner["id"] is not None:
            prize = db.query(models.LotteryPrize).filter(
                models.LotteryPrize.id == winner["id"]
            ).first()
            if prize and prize.stock is not None:
                prize.stock -= 1

        draw = models.LotteryDraw(
            user_id=user_id,
            prize_id=winner["id"],
            prize_name=winner["name"],
            is_win=1 if is_win else 0,
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
            note=f"抽奖消耗 {config.TICKETS_PER_DRAW} 张（{winner['name']}）",
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
            "can_lottery": acc.lottery_tickets >= config.TICKETS_PER_DRAW,
            "sectors": sectors,
            "winning_index": winning_index,
        }
