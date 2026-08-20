"""种子数据：建表、写入预设奖品池、创建管理员账号、创建示例闯关任务。"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.models import Prize, User, ChallengeTask, PetSpecies, PetFeedItem, PetAdoption, PetFeedLog
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


# ---------- 宠物种类种子数据（30+ 种，涵盖多类动物） ----------
# (name, description, emoji_baby, emoji_youth, emoji_adult, emoji_legend, sort_order, diet_type)
# diet_type: carnivore/herbivore/omnivore/special
PET_SPECIES_SEED = [
    # —— 常见宠物 ——
    ("仓鼠", "毛茸茸的小家伙，最爱嗑瓜子", "🐹", "🐹", "🐹", "👑🐹", 1, "omnivore"),
    ("金鱼", "水中精灵，摆尾间带走烦恼", "🐟", "🐠", "🐡", "🐉", 2, "omnivore"),
    ("小猫", "软萌喵星人，呼噜呼噜伴你成长", "🐱", "😺", "😸", "🦁", 3, "carnivore"),
    ("小狗", "忠诚的小伙伴，摇尾巴迎接你回家", "🐶", "🐕", "🦮", "🐺", 4, "omnivore"),
    ("兔子", "长耳短尾，蹦蹦跳跳活力满满", "🐰", "🐇", "🐇", "🌙🐇", 5, "herbivore"),
    ("鹦鹉", "学舌小能手，叽叽喳喳说不停", "🐦", "🦜", "🦜", "🦅", 6, "omnivore"),
    ("乌龟", "慢而坚定，长寿的象征", "🐢", "🐢", "🐢", "🐲", 7, "omnivore"),
    ("小熊猫", "圆滚滚的身体，最爱吃竹子", "🐼", "🐼", "🐼", "🐼✨", 8, "herbivore"),
    # —— 海洋生物 ——
    ("小丑鱼", "尼莫的亲戚，珊瑚丛中捉迷藏", "🐟", "🐠", "🐠", "🔱🐠", 10, "omnivore"),
    ("海豚", "海洋智者，跃出水面划出彩虹", "🐬", "🐬", "🐬", "🌊🐬", 11, "carnivore"),
    ("海龟", "穿越大洋的旅行者，见证百年沧桑", "🐢", "🐢", "🐢", "🏝️🐢", 12, "omnivore"),
    ("章鱼", "八条腿的天才，变色伪装大师", "🐙", "🐙", "🐙", "🧠🐙", 13, "carnivore"),
    ("水母", "透明舞者，在深海中闪烁光芒", "🪼", "🪼", "🪼", "✨🪼", 14, "special"),
    # —— 爬行动物 ——
    ("霸王龙", "远古霸主，一声咆哮震天动地", "🦕", "🦖", "🦖", "👑🦖", 20, "carnivore"),
    ("三角龙", "头顶三刃的温和巨人", "🦕", "🦕", "🦖", "🛡️🦖", 21, "herbivore"),
    ("蜥蜴", "冷血小猎手，晒太阳是日常", "🦎", "🦎", "🦎", "🐉", 22, "carnivore"),
    ("蛇", "无声潜行，蜕皮即重生", "🐍", "🐍", "🐍", "🐲", 23, "carnivore"),
    # —— 野生动物 ——
    ("狐狸", "聪明伶俐，尾巴毛茸茸", "🦊", "🦊", "🦊", "🌟🦊", 30, "carnivore"),
    ("狼", "群居猎手，月下长嚎", "🐺", "🐺", "🐺", "🌕🐺", 31, "carnivore"),
    ("熊", "力量与温暖的结合体", "🐻", "🐻", "🐻", "🐻‍❄️", 32, "omnivore"),
    ("老虎", "百兽之王，斑纹独一无二", "🐯", "🐅", "🐅", "👑🐅", 33, "carnivore"),
    ("狮子", "草原之王，鬃毛威风凛凛", "🦁", "🦁", "🦁", "👑🦁", 34, "carnivore"),
    ("大象", "长鼻家族，记忆力超群", "🐘", "🐘", "🐘", "🏔️🐘", 35, "herbivore"),
    ("长颈鹿", "世界上最高的动物，伸长脖子看世界", "🦒", "🦒", "🦒", "⭐🦒", 36, "herbivore"),
    # —— 昆虫类 ——
    ("蝴蝶", "破茧成蝶，展翅飞舞", "🐛", "🦋", "🦋", "🌈🦋", 40, "special"),
    ("蜜蜂", "勤劳小工匠，酿造甜蜜生活", "🐝", "🐝", "🐝", "🍯🐝", 41, "special"),
    ("萤火虫", "暗夜小灯笼，点亮夏夜梦想", "✨", "✨", "🪲", "🌟🪲", 42, "special"),
    ("瓢虫", "七星小卫士，守护花园安宁", "🐞", "🐞", "🐞", "💎🐞", 43, "special"),
    # —— 奇幻生物 ——
    ("独角兽", "纯洁与力量的化身，角尖闪烁星光", "🦄", "🦄", "🦄", "🌈🦄", 50, "herbivore"),
    ("龙", "东方神兽，腾云驾雾呼风唤雨", "🐣", "🐲", "🐉", "🐉🔥", 51, "carnivore"),
    ("凤凰", "浴火重生，羽翼燃烧不灭之焰", "🐤", "🐦‍🔥", "🐦‍🔥", "🔥🐦‍🔥", 52, "special"),
    ("精灵", "森林守护者，聆听万物之声", "🧚", "🧚", "🧚", "🌿🧚", 53, "special"),
]


# ---------- 宠物食物种子数据 ----------
# (name, description, emoji, price, xp_value, sort_order, suitability_level, suitability_note)
PET_FEED_ITEMS_SEED = [
    ("小鱼干", "新鲜晒制，宠物最爱", "🐟", 3, 3, 1, "suitable", "大多数宠物都喜欢"),
    ("猫薄荷", "提神醒脑，快乐成长", "🌿", 2, 2, 2, "suitable", "猫咪特别喜欢的草本植物"),
    ("牛奶", "营养丰富的新鲜牛奶", "🥛", 4, 4, 3, "suitable", "大多数宠物都能喝"),
    ("鸡腿", "香喷喷的大鸡腿，补充蛋白质", "🍗", 5, 5, 4, "suitable", "食肉动物的最爱"),
    ("苹果", "新鲜水果，维生素满满", "🍎", 3, 3, 5, "suitable", "食草动物很喜欢"),
    ("蛋糕", "甜点时间，开心成长", "🍰", 8, 8, 6, "suitable", "甜食大家都爱"),
    ("胡萝卜", "营养蔬菜，明目又健康", "🥕", 3, 3, 7, "suitable", "食草动物的最爱"),
    ("蜂蜜", "天然甜味，增强免疫力", "🍯", 6, 6, 8, "suitable", "天然营养佳品"),
    ("牛排", "高级料理，大幅补充经验", "🥩", 12, 12, 9, "suitable", "食肉动物的高级料理"),
    ("寿司", "精致日料，宠物新体验", "🍣", 10, 10, 10, "suitable", "精致的海鲜料理"),
    ("冰淇淋", "冰凉爽口，夏日限定", "🍦", 8, 8, 11, "suitable", "夏日甜品，适量食用"),
    ("彩虹糖", "五彩缤纷的魔法糖果", "🍬", 15, 15, 12, "suitable", "神奇的魔法糖果"),
]


# ---------- 饮食类型与食物适配规则 ----------
# 用于更新已有种子数据的 diet_type
_DIET_TYPE_BY_NAME = {
    "仓鼠": "omnivore", "金鱼": "omnivore", "小猫": "carnivore", "小狗": "omnivore",
    "兔子": "herbivore", "鹦鹉": "omnivore", "乌龟": "omnivore", "小熊猫": "herbivore",
    "小丑鱼": "omnivore", "海豚": "carnivore", "海龟": "omnivore", "章鱼": "carnivore",
    "水母": "special", "霸王龙": "carnivore", "三角龙": "herbivore", "蜥蜴": "carnivore",
    "蛇": "carnivore", "狐狸": "carnivore", "狼": "carnivore", "熊": "omnivore",
    "老虎": "carnivore", "狮子": "carnivore", "大象": "herbivore", "长颈鹿": "herbivore",
    "蝴蝶": "special", "蜜蜂": "special", "萤火虫": "special", "瓢虫": "special",
    "独角兽": "herbivore", "龙": "carnivore", "凤凰": "special", "精灵": "special",
    # 兼容旧数据名称
    "学习猫": "carnivore", "知识犬": "omnivore",
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
            # 从环境变量读取初始管理员密码，未设置则自动生成随机密码
            init_password = os.environ.get("ADMIN_INIT_PASSWORD", "")
            if not init_password:
                import secrets
                init_password = secrets.token_urlsafe(8)
                print(f"️  未设置 ADMIN_INIT_PASSWORD 环境变量，已自动生成随机密码: {init_password}")
                print("⚠️  请妥善保存此密码，后续无法找回！")
            pw_hash, pw_salt = hash_password(init_password)
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
        # ---------- 🛡️ 宠物种类种子数据（受保护） ----------
        # 保护策略：
        #   1. 表非空时绝不重新插入（避免 ID 漂移导致领养记录外键断裂）
        #   2. 若 pet_adoption 表有记录，连 diet_type 补全也跳过（避免意外修改影响已领养宠物）
        #   3. 仅补全空字段，不覆盖已有配置
        has_adoptions = db.query(PetAdoption).count() > 0
        species_count = db.query(PetSpecies).count()

        if species_count == 0:
            for name, desc, e_baby, e_youth, e_adult, e_legend, order, diet in PET_SPECIES_SEED:
                db.add(PetSpecies(
                    name=name, description=desc,
                    emoji_baby=e_baby, emoji_youth=e_youth,
                    emoji_adult=e_adult, emoji_legend=e_legend,
                    status="on", sort_order=order, diet_type=diet,
                ))
            db.commit()
            print(f"✅ 已写入 {len(PET_SPECIES_SEED)} 种宠物种子数据")
        elif has_adoptions:
            # 有领养记录时：仅补全缺失的 diet_type，不修改任何已有字段
            updated = 0
            for sp in db.query(PetSpecies).all():
                if not sp.diet_type:
                    dt = _DIET_TYPE_BY_NAME.get(sp.name)
                    if not dt:
                        if '猫' in sp.name or '虎' in sp.name or '狮' in sp.name or '狼' in sp.name or '狐' in sp.name:
                            dt = 'carnivore'
                        elif '兔' in sp.name or '鹿' in sp.name or '象' in sp.name:
                            dt = 'herbivore'
                        elif '鱼' in sp.name or '龙' in sp.name or '龟' in sp.name:
                            dt = 'omnivore'
                        else:
                            dt = 'omnivore'
                    sp.diet_type = dt
                    updated += 1
            if updated:
                db.commit()
                print(f"✅ 已补全 {updated} 种宠物的饮食类型（领养数据受保护，未修改其他字段）")
            else:
                print(f"ℹ️ 宠物种类已存在（{species_count} 种），领养数据受保护，跳过")
        else:
            # 无领养记录时：可安全补全 diet_type
            updated = 0
            for sp in db.query(PetSpecies).all():
                if not sp.diet_type:
                    dt = _DIET_TYPE_BY_NAME.get(sp.name)
                    if not dt:
                        if '猫' in sp.name or '虎' in sp.name or '狮' in sp.name or '狼' in sp.name or '狐' in sp.name:
                            dt = 'carnivore'
                        elif '兔' in sp.name or '鹿' in sp.name or '象' in sp.name:
                            dt = 'herbivore'
                        elif '鱼' in sp.name or '龙' in sp.name or '龟' in sp.name:
                            dt = 'omnivore'
                        else:
                            dt = 'omnivore'
                    sp.diet_type = dt
                    updated += 1
            if updated:
                db.commit()
                print(f"✅ 已更新 {updated} 种宠物的饮食类型")
            else:
                print("ℹ️ 宠物种类已存在，跳过")

        # ---------- 🛡️ 宠物食物种子数据（受保护） ----------
        # 保护策略：表非空时绝不重新插入，避免 ID 漂移影响 pet_feed_log 外键
        if db.query(PetFeedItem).count() == 0:
            for name, desc, emoji, price, xp, order, suit_level, suit_note in PET_FEED_ITEMS_SEED:
                db.add(PetFeedItem(
                    name=name, description=desc, emoji=emoji,
                    price=price, xp_value=xp, sort_order=order,
                    suitability_level=suit_level, suitability_note=suit_note,
                ))
            db.commit()
            print(f"✅ 已写入 {len(PET_FEED_ITEMS_SEED)} 种食物种子数据")
        else:
            print("ℹ️ 宠物食物已存在，跳过")

        # ---------- 🛡️ 宠物业务数据保护声明 ----------
        # 以下表的数据在任何情况下都不应被 seed 脚本修改或删除：
        #   - pet_adoption   领养记录（含 XP、阶段、连击、生病状态等）
        #   - pet_feed_log   成长流水（含每次 XP 变动记录）
        # seed 脚本不操作这两张表的数据，仅做存在性检查。
        adoption_count = db.query(PetAdoption).count()
        feed_log_count = db.query(PetFeedLog).count()
        if adoption_count > 0 or feed_log_count > 0:
            print(f"🛡️ 宠物业务数据受保护: {adoption_count} 条领养记录, {feed_log_count} 条成长流水（未修改）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
