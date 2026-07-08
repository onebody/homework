import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta, timezone
from app.database import SessionLocal, init_db
from app import models

DEMO_USERS = [("xiaoming", "小明", 260), ("xiaohong", "小红", 120)]

DEMO_PRIZES = [
    ("卡通铅笔礼盒", "一套 12 色卡通铅笔", 30, 10),
    ("精装注音绘本", "适合三年级的课外阅读", 50, 5),
    ("乐高迷你套装", "积木小礼物，动手又动脑", 120, 3),
    ("科技馆门票", "单次入场券，探索科学", 200, 2),
]

# 抽奖奖池：(名称, 描述, 权重, 库存, 是否中奖, 排序)
# 库存为 None 表示不限量（「谢谢参与」保底，确保奖池永远可抽）
# 至少提供 10 个中奖奖品，供前端转盘随机取 10 个 + 1 个"谢谢惠顾" = 11 扇区
DEMO_LOTTERY_PRIZES = [
    ("谢谢参与", "再接再厉，下次好运", 50, None, 0, 0),
    ("文具大礼包", "抽奖专属·实用文具套装", 20, 10, 1, 1),
    ("卡通雨伞", "晴雨两用·可爱造型", 15, 5, 1, 2),
    ("益智拼图", "300 片·锻炼思维", 10, 8, 1, 3),
    ("神秘大奖", "终极大奖·惊喜好礼", 5, 2, 1, 4),
    ("彩色蜡笔套装", "24 色安全蜡笔", 12, 6, 1, 5),
    ("故事绘本", "精装童话故事书", 10, 7, 1, 6),
    ("小夜灯", "可爱动物造型 LED 灯", 8, 5, 1, 7),
    ("笔记本礼盒", "创意手账本套装", 9, 8, 1, 8),
    ("钥匙扣挂件", "卡通人物钥匙链", 11, 15, 1, 9),
    ("贴纸包", "100 张精美贴纸", 14, 20, 1, 10),
    ("橡皮擦套装", "创意造型橡皮擦", 7, 12, 1, 11),
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        for username, name, start_points in DEMO_USERS:
            if not db.query(models.User).filter(models.User.username == username).first():
                u = models.User(username=username, display_name=name)
                db.add(u)
                db.flush()
                db.add(models.PointAccount(
                    user_id=u.id,
                    balance=start_points,
                    total_earned=start_points,
                ))
        db.flush()

        now = datetime.now(timezone.utc)
        valid_to = now + timedelta(days=60)
        for name, desc, cost, stock in DEMO_PRIZES:
            if not db.query(models.Prize).filter(models.Prize.name == name).first():
                db.add(
                    models.Prize(
                        name=name,
                        description=desc,
                        cost_points=cost,
                        stock=stock,
                        valid_from=now,
                        valid_to=valid_to,
                    )
                )
        for name, desc, weight, stock, is_win, order in DEMO_LOTTERY_PRIZES:
            if not db.query(models.LotteryPrize).filter(models.LotteryPrize.name == name).first():
                db.add(models.LotteryPrize(
                    name=name,
                    description=desc,
                    weight=weight,
                    stock=stock,
                    is_win=is_win,
                    sort_order=order,
                ))

        db.commit()
        print("✅ 演示数据初始化完成：2 个用户 + 4 个奖品 + " + str(len(DEMO_LOTTERY_PRIZES)) + " 个抽奖奖池")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
