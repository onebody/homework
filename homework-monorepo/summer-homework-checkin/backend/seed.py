"""种子数据：建表、写入预设奖品池、创建管理员账号、创建示例闯关任务。"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.models import Prize, User, ChallengeTask
from app.security import hash_password


PRESET_PRIZES = [
    # 学习文具（cost_points 为积分兑换所需积分）
    ("卡通铅笔礼盒", "一盒12支卡通图案铅笔", "stationery", 0.18, 50, "on", 30),
    ("多功能文具套装", "含尺子、橡皮、卷笔刀", "stationery", 0.15, 40, "on", 50),
    ("精美手账笔记本", "暑假计划专属笔记本", "stationery", 0.12, 60, "on", 70),
    ("24色油画棒", "安全无毒绘画工具", "stationery", 0.10, -1, "on", 40),
    # 户外活动权益
    ("公园亲子半日票", "城市公园亲子门票", "outdoor", 0.10, 30, "on", 90),
    ("儿童游泳体验券", "室内恒温泳池单次", "outdoor", 0.08, 20, "on", 120),
    ("趣味攀岩体验", "儿童攀岩馆体验券", "outdoor", 0.06, 15, "on", 150),
    ("户外野餐装备包", "含野餐垫与飞盘", "outdoor", 0.05, 10, "on", 200),
    # 兴趣拓展礼包
    ("科学小实验套装", "10个入门科学实验", "interest", 0.06, 25, "on", 80),
    ("经典绘本阅读包", "5册精装绘本", "interest", 0.05, -1, "on", 60),
    ("乐高拼装小套装", "益智拼装模型", "interest", 0.03, 12, "on", 160),
    ("少儿编程体验课", "线上编程启蒙1节", "interest", 0.02, 8, "on", 220),
]

# 特殊奖品：积分兑换抽奖机会（默认配置）
LOTTERY_TICKET_PRIZE = {
    "name": " 抽奖机会",
    "description": "消耗5积分兑换1次抽奖机会，可反复兑换",
    "category": "interest",
    "probability": 0.0,
    "stock": -1,
    "status": "on",
    "cost_points": 5,
    "is_lottery_ticket": True,
    "ticket_qty": 1,
}


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Prize).count() == 0:
            for name, desc, cat, prob, stock, status, cost in PRESET_PRIZES:
                db.add(Prize(
                    name=name, description=desc, category=cat,
                    probability=prob, stock=stock, status=status,
                    cost_points=cost, is_preset=True,
                ))
            # 添加抽奖机会特殊奖品
            db.add(Prize(**LOTTERY_TICKET_PRIZE, is_preset=True))
            print("✅ 已写入预设奖品池（12 项 + 1 抽奖机会）")
        else:
            print("ℹ️ 奖品池已存在，跳过")

        if not db.query(User).filter_by(username="admin").first():
            init_password = os.environ.get("ADMIN_INIT_PASSWORD", "")
            if not init_password:
                import secrets
                init_password = secrets.token_urlsafe(8)
                print(f"⚠️  未设置 ADMIN_INIT_PASSWORD，已自动生成随机密码: {init_password}")
            from app.security import hash_password as _hp
            pw_hash, pw_salt = _hp(init_password)
            admin = User(
                username="admin", password_hash=pw_hash, password_salt=pw_salt,
                role="admin", nickname="系统管理员",
            )
            db.add(admin)
            db.commit()
            print("✅ 已创建管理员账号 admin（密码见上方输出）")
        else:
            print("ℹ️ 管理员账号已存在，跳过")

        # 创建示例闯关任务
        if db.query(ChallengeTask).count() == 0:
            admin_user = db.query(User).filter_by(username="admin").first()
            sample_tasks = [
                {
                    "name": "完成暑假作业第一章",
                    "description": "认真完成第一章的数学题，拍照上传作业照片",
                    "sort_order": 1,
                    "reward_points": 20,
                    "status": "active",
                    "created_by": admin_user.id,
                },
                {
                    "name": "阅读一本课外书",
                    "description": "阅读一本你喜欢的课外书，并拍照上传封面",
                    "sort_order": 2,
                    "reward_points": 15,
                    "status": "active",
                    "created_by": admin_user.id,
                },
                {
                    "name": "参加一次户外活动",
                    "description": "和家人一起去公园或户外运动，拍照记录",
                    "sort_order": 3,
                    "reward_points": 25,
                    "status": "scheduled",
                    "unlock_at": datetime(2026, 7, 15, 0, 0, 0),
                    "created_by": admin_user.id,
                },
                {
                    "name": "学会一项新技能",
                    "description": "学习一项新技能（如跳绳、画画、唱歌等），并展示成果",
                    "sort_order": 4,
                    "reward_points": 30,
                    "status": "locked",
                    "created_by": admin_user.id,
                },
            ]
            for task_data in sample_tasks:
                db.add(ChallengeTask(**task_data))
            db.commit()
            print("✅ 已创建 4 个示例闯关任务")
        else:
            print("ℹ️ 闯关任务已存在，跳过")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
