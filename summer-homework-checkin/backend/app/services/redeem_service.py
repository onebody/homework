from fastapi import HTTPException

from ..models import Prize, Redemption
from .notify_service import notify


def list_prizes_for_mall(db):
    """积分商城可兑换奖品列表（仅上架且积分>0）。"""
    items = db.query(Prize).filter(
        Prize.status == "on", Prize.cost_points > 0
    ).order_by(Prize.cost_points.asc()).all()
    return [p for p in items]


def list_redemptions(db, user):
    return (
        db.query(Redemption).filter_by(user_id=user.id)
        .order_by(Redemption.redeemed_at.desc()).all()
    )


def redeem(db, user, prize_id):
    """用积分兑换指定奖品：扣积分、减库存、写兑换记录。
    
    区分两类奖品：
    1. 抽奖机会奖品（is_lottery_ticket=True）：自动成功，直接给券，不创建兑换记录
    2. 实物奖品（is_lottery_ticket=False）：创建"待发放"状态的兑换记录，需管理员手动核实兑现
    """
    prize = db.get(Prize, prize_id)
    if not prize:
        raise HTTPException(status_code=404, detail="奖品不存在")
    if prize.status != "on":
        raise HTTPException(status_code=400, detail="该奖品已下架")
    if prize.cost_points <= 0:
        raise HTTPException(status_code=400, detail="该奖品不支持积分兑换")
    if not prize.is_lottery_ticket and prize.stock == 0:
        raise HTTPException(status_code=400, detail="该奖品已兑完")
    if (user.points or 0) < prize.cost_points:
        raise HTTPException(
            status_code=400,
            detail=f"积分不足，还需 {prize.cost_points - user.points} 分",
        )

    # 扣积分
    user.points -= prize.cost_points

    # 抽奖机会奖品：自动成功，直接增加抽奖券数量，创建 fulfilled 状态的兑换记录
    if prize.is_lottery_ticket:
        ticket_qty = prize.ticket_qty or 1
        user.lottery_tickets = (user.lottery_tickets or 0) + ticket_qty

        rec = Redemption(
            user_id=user.id,
            prize_id=prize.id,
            prize_name=prize.name,
            cost_points=prize.cost_points,
            status="fulfilled",  # 虚拟奖品，系统自动兑现，无需管理员核实
            note="系统自动兑现（抽奖券已发放）",
        )
        db.add(rec)
        db.commit()
        db.refresh(user)
        db.refresh(rec)

        notify(
            db, user.id, "student", "redeem",
            f"🎰 已兑换「{prize.name}」",
            f"消耗 {prize.cost_points} 积分，获得 {ticket_qty} 张抽奖券，当前剩余 {user.points} 分，抽奖券 {user.lottery_tickets} 张。",
            rec.id,
        )
        return rec, user.points

    # 实物奖品：减库存 + 创建"待发放"状态的兑换记录（需管理员手动核实）
    if prize.stock and prize.stock > 0:
        prize.stock -= 1

    rec = Redemption(
        user_id=user.id,
        prize_id=prize.id,
        prize_name=prize.name,
        cost_points=prize.cost_points,
        status="pending",  # 待发放状态，等待管理员核实
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    notify(
        db, user.id, "student", "redeem",
        f"🎁 已兑换「{prize.name}」",
        f"消耗 {prize.cost_points} 积分，当前剩余 {user.points} 分。兑换已提交，等待管理员核实发放。",
        rec.id,
    )
    return rec, user.points


def replace_redemption(db, user, redemption_id, new_prize_id):
    """将已有兑换替换为另一个奖品（直接选择替换）。

    规则：
    - 原兑换记为 replaced，并指向新记录；
    - 退还原消耗积分，再按新奖品分值结算（多退少补）；
    - 新奖品库存 -1，原奖品库存 +1（回滚）。
    """
    old = db.get(Redemption, redemption_id)
    if not old or old.user_id != user.id:
        raise HTTPException(status_code=404, detail="兑换记录不存在")
    if old.status == "replaced":
        raise HTTPException(status_code=400, detail="该兑换已被替换")
    if old.status == "cancelled":
        raise HTTPException(status_code=400, detail="该兑换已取消")

    new_prize = db.get(Prize, new_prize_id)
    if not new_prize or new_prize.status != "on" or new_prize.cost_points <= 0:
        raise HTTPException(status_code=400, detail="目标奖品不可兑换")
    if new_prize.stock == 0:
        raise HTTPException(status_code=400, detail="目标奖品已兑完")

    # 原奖品回滚库存
    old_prize = db.get(Prize, old.prize_id)
    if old_prize and old_prize.stock is not None and old_prize.stock >= 0:
        old_prize.stock += 1

    # 退还原积分
    user.points = (user.points or 0) + old.cost_points

    # 计算差价
    diff = new_prize.cost_points - old.cost_points
    if diff > 0 and user.points < new_prize.cost_points:
        # 积分不足以覆盖新奖品（已退还旧分），回滚
        if old_prize and old_prize.stock is not None and old_prize.stock >= 0:
            old_prize.stock -= 1
        user.points -= old.cost_points
        raise HTTPException(
            status_code=400,
            detail=f"积分不足以兑换「{new_prize.name}」，还需 {diff} 分",
        )

    # 扣新积分、减新库存
    user.points -= new_prize.cost_points
    if new_prize.stock is not None and new_prize.stock > 0:
        new_prize.stock -= 1

    old.status = "replaced"
    old.note = f"已替换为「{new_prize.name}」"

    new_rec = Redemption(
        user_id=user.id,
        prize_id=new_prize.id,
        prize_name=new_prize.name,
        cost_points=new_prize.cost_points,
        status="pending",
        replaced_by=None,
    )
    db.add(new_rec)
    db.commit()
    db.refresh(new_rec)
    old.replaced_by = new_rec.id
    db.commit()

    notify(
        db, user.id, "student", "redeem",
        f"🔄 已替换为「{new_prize.name}」",
        f"原「{old.prize_name}」已替换，当前剩余积分 {user.points}。",
        new_rec.id,
    )
    return new_rec, user.points
