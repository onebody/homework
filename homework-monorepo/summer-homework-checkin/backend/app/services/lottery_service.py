import random

from fastapi import HTTPException

from ..models import Prize, LotteryRecord, Redemption
from .notify_service import notify, notify_parents_of_student


def draw(db, user):
    """消耗 1 次抽奖资格，按概率与库存加权随机抽取。"""
    if user.lottery_tickets <= 0:
        raise HTTPException(status_code=400, detail="暂无可用抽奖资格，先去连续打卡攒资格吧")

    candidates = [p for p in db.query(Prize).filter(Prize.status == "on").all()
                  if p.stock == -1 or p.stock > 0]
    prize = None
    is_win = False

    if candidates:
        weights = [max(float(p.probability), 0.0) for p in candidates]
        total = sum(weights)
        if total > 0:
            r = random.random() * total
            acc = 0.0
            for p, w in zip(candidates, weights):
                acc += w
                if r <= acc:
                    prize = p
                    break
            if prize is not None:
                is_win = True
                if prize.stock > 0:
                    prize.stock -= 1

    user.lottery_tickets -= 1
    rec = LotteryRecord(
        user_id=user.id,
        prize_id=prize.id if prize else None,
        prize_name=prize.name if prize else None,
        is_win=is_win,
    )
    db.add(rec)

    # 中奖时同时创建 Redemption 记录，使学生端"我的兑换"和管理端"兑换记录"可见
    if is_win and prize:
        red = Redemption(
            user_id=user.id,
            prize_id=prize.id,
            prize_name=prize.name,
            cost_points=0,
            status="pending",
            note="抽奖获得",
        )
        db.add(red)

    db.commit()
    db.refresh(rec)

    if is_win:
        notify(db, user.id, "student", "lottery", "🎉 抽奖中奖啦",
               f"恭喜你抽中【{prize.name}】！", rec.id)
        notify_parents_of_student(db, user, "lottery", "孩子抽奖中奖",
                                   f"孩子抽中了【{prize.name}】", rec.id)
        message = f"恭喜抽中【{prize.name}】"
    else:
        notify(db, user.id, "student", "lottery", "抽奖结果",
               "本次未中奖，继续打卡攒资格还有机会哦~", rec.id)
        message = "本次未中奖，再接再厉"

    return {
        "is_win": is_win,
        "prize_name": prize.name if prize else None,
        "prize_id": prize.id if prize else None,
        "tickets_left": user.lottery_tickets,
        "message": message,
    }
