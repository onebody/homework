"""宠物成长服务：打卡自动成长、阶段升级判定、通知、食物适配性。"""
from ..models import PetAdoption, PetFeedLog, PetFeedItem, PetSpecies, User
from ..config import PET_CHECKIN_XP_NORMAL, PET_CHECKIN_XP_MAKEUP, PET_STAGE_THRESHOLDS, PET_SPECIES_DEFAULT
from .notify_service import notify
from ..utils.timeutil import now_local

# 饮食类型与食物默认适配规则
# diet_type -> {food_category -> default_suitability}
# food_category 由食物的 emoji 和名称推断
_DIET_FOOD_MATRIX = {
    "carnivore": {  # 食肉动物：肉类=perfect，奶类=suitable，水果=caution，蔬菜=warning，甜食=warning
        "meat": "perfect", "fish": "perfect", "dairy": "suitable",
        "fruit": "caution", "veg": "caution", "sweet": "warning",
        "candy": "warning", "sushi": "suitable",
    },
    "herbivore": {  # 食草动物：蔬菜=perfect，水果=perfect，奶类=suitable，肉=warning，甜食=caution
        "meat": "warning", "fish": "warning", "dairy": "suitable",
        "fruit": "perfect", "veg": "perfect", "sweet": "caution",
        "candy": "caution", "sushi": "warning",
    },
    "omnivore": {  # 杂食动物：大部分=suitable，肉/蔬菜=perfect，糖果=caution
        "meat": "suitable", "fish": "suitable", "dairy": "suitable",
        "fruit": "suitable", "veg": "suitable", "sweet": "suitable",
        "candy": "caution", "sushi": "suitable",
    },
    "special": {  # 特殊饮食：大部分=caution
        "meat": "caution", "fish": "caution", "dairy": "caution",
        "fruit": "caution", "veg": "caution", "sweet": "caution",
        "candy": "caution", "sushi": "caution",
    },
}

# 食物分类（根据 emoji 和名称推断）
_FOOD_CATEGORY_MAP = {
    "🐟": "fish", "🍗": "meat", "🥛": "dairy", "🍎": "fruit",
    "🍰": "sweet", "🥕": "veg", "🍯": "sweet", "🥩": "meat",
    "🍣": "sushi", "🍦": "sweet", "🍬": "candy", "🌿": "veg",
}

# 不适配后果描述
_SICKNESS_EFFECTS = {
    "warning": "肚子疼",
    "danger": "严重不适，精神不振",
}

# 完美适配连击奖励阈值
_STREAK_BONUS_THRESHOLD = 3  # 连续 3 次完美适配触发加成
_STREAK_BONUS_RATE = 1.2     # 额外 20% XP


# 阶段名称中文映射（用于通知消息）
_STAGE_LABEL = {
    "baby": "幼年期",
    "youth": "少年期",
    "adult": "成年期",
    "legend": "传奇期",
}

# 阶段 emoji 映射（从默认配置读取，后续可扩展为从 pet_species 表读取）
_STAGE_EMOJI = {
    "baby": PET_SPECIES_DEFAULT["emoji_baby"],
    "youth": PET_SPECIES_DEFAULT["emoji_youth"],
    "adult": PET_SPECIES_DEFAULT["emoji_adult"],
    "legend": PET_SPECIES_DEFAULT["emoji_legend"],
}


def calc_stage(xp: int) -> str:
    """根据累计 XP 计算当前应处的成长阶段。

    阈值由 config.PET_STAGE_THRESHOLDS 定义，支持环境变量覆盖。
    从高到低匹配，返回第一个 xp >= threshold 的阶段。
    """
    # 按阈值降序排列，找到第一个 xp >= 阈值的阶段
    for stage in sorted(PET_STAGE_THRESHOLDS, key=lambda s: PET_STAGE_THRESHOLDS[s], reverse=True):
        if xp >= PET_STAGE_THRESHOLDS[stage]:
            return stage
    return "baby"


def get_active_pet(db, user_id: int) -> PetAdoption:
    """获取用户当前活跃的宠物，无则返回 None。"""
    return db.query(PetAdoption).filter_by(
        user_id=user_id, is_active=True
    ).first()


def on_checkin_approved(db, user: User, checkin) -> dict:
    """打卡审核通过时，自动为活跃宠物增加成长经验。

    由 checkin_service.approve_checkin() 在积分发放后调用，
    确保在同一事务中执行。

    参数：
        db: 数据库会话
        user: 当前用户 ORM 对象
        checkin: 审核通过的 CheckIn 记录

    返回：
        dict: {"xp_gained": int, "stage_changed": bool, "old_stage": str, "new_stage": str}
              若无活跃宠物则返回 None
    """
    pet = get_active_pet(db, user.id)
    if not pet:
        return None

    # 根据打卡类型确定 XP 增量
    xp = PET_CHECKIN_XP_NORMAL if checkin.check_type == "normal" else PET_CHECKIN_XP_MAKEUP

    old_stage = pet.current_stage

    # 复用共享的 XP 增长逻辑
    result = apply_xp_gain(db, pet, user, xp)

    # 写成长流水（便于对账和追溯）
    log = PetFeedLog(
        user_id=user.id,
        adoption_id=pet.id,
        feed_type="checkin",
        xp_gained=xp,
        total_xp_after=pet.current_xp,
        stage_before=old_stage,
        stage_after=result["new_stage"],
        trigger_checkin_id=checkin.id,
    )
    db.add(log)

    # 阶段升级时发送通知
    if result["stage_changed"]:
        _notify_stage_up(db, user, pet, old_stage, result["new_stage"])

    # 注意：此处不 commit，由调用方（approve_checkin）统一 commit

    return result


def apply_xp_gain(db, pet: PetAdoption, user: User, xp: int) -> dict:
    """为宠物累加 XP 并判定升级，同步 User 冗余字段。

    共享函数：打卡自动成长 / 道具喂养 / 管理员调整均复用此逻辑。
    注意：本函数不 commit，由调用方决定事务边界。

    返回：
        dict: {"xp_gained", "stage_changed", "old_stage", "new_stage", "current_xp"}
    """
    old_stage = pet.current_stage

    # 累加 XP
    pet.current_xp += xp
    pet.last_fed_at = now_local()

    # 计算新阶段
    new_stage = calc_stage(pet.current_xp)
    stage_changed = new_stage != old_stage

    if stage_changed:
        pet.current_stage = new_stage

    # 同步 User 冗余字段
    user.pet_xp = pet.current_xp
    user.pet_level = pet.current_stage

    return {
        "xp_gained": xp,
        "stage_changed": stage_changed,
        "old_stage": old_stage,
        "new_stage": new_stage,
        "current_xp": pet.current_xp,
    }


def _notify_stage_up(db, user: User, pet: PetAdoption, old_stage: str, new_stage: str):
    """阶段升级通知。"""
    old_label = _STAGE_LABEL.get(old_stage, old_stage)
    new_label = _STAGE_LABEL.get(new_stage, new_stage)
    old_emoji = _STAGE_EMOJI.get(old_stage, "🐾")
    new_emoji = _STAGE_EMOJI.get(new_stage, "🐾")

    pet_name = pet.nickname or "你的宠物"

    if new_stage == "legend":
        # 传奇形态特殊通知（成就解锁）
        notify(
            db, user.id, "student", "system",
            f"🎉 {pet_name} 进化为传奇形态！",
            f"恭喜！{pet_name} 从 {old_emoji}{old_label} 成长为 {new_emoji}{new_label}！"
            f"它已经陪伴你积累了 {pet.current_xp} 点成长经验，继续加油！",
        )
    else:
        notify(
            db, user.id, "student", "system",
            f"✨ {pet_name} 升级啦！",
            f"{pet_name} 从 {old_emoji}{old_label} 成长为 {new_emoji}{new_label}！"
            f"当前成长经验 {pet.current_xp}，继续打卡让它变得更强大吧！",
        )


def get_stage_emoji(stage: str) -> str:
    """获取指定阶段的 emoji。"""
    return _STAGE_EMOJI.get(stage, "🐾")


def get_stage_label(stage: str) -> str:
    """获取指定阶段的中文名称。"""
    return _STAGE_LABEL.get(stage, stage)


# ---------- 食物适配性服务 ----------

def get_food_category(food: PetFeedItem) -> str:
    """根据食物 emoji 推断食物分类。"""
    return _FOOD_CATEGORY_MAP.get(food.emoji, "sweet")  # 默认归为甜食


def compute_suitability(species: PetSpecies, food: PetFeedItem) -> dict:
    """计算食物对特定宠物的适配等级。

    返回：
        dict: {
            "level": "perfect"|"suitable"|"caution"|"warning"|"danger",
            "label": 中文标签,
            "emoji": 标识 emoji,
            "note": 说明文案,
        }
    """
    # 如果食物本身有明确的适配等级和备注（管理员手动设置），优先使用
    if food.suitability_level and food.suitability_level != "suitable":
        # 管理员手动设置的优先级最高
        level = food.suitability_level
        note = food.suitability_note or ""
    elif food.species_id and food.species_id != species.id:
        # 食物绑定了其他种类 -> danger
        level = "danger"
        note = f"该食物专为{food.species.name}设计，不适合{species.name}"
    else:
        # 根据饮食类型矩阵计算默认适配
        diet = species.diet_type or "omnivore"
        category = get_food_category(food)
        matrix = _DIET_FOOD_MATRIX.get(diet, _DIET_FOOD_MATRIX["omnivore"])
        level = matrix.get(category, "suitable")
        note = food.suitability_note or ""

    _LEVEL_INFO = {
        "perfect": ("完美适配", "✅"),
        "suitable": ("适合", "👍"),
        "caution": ("注意", "⚠️"),
        "warning": ("警告", "❗"),
        "danger": ("不适合", "🚫"),
    }
    label, emoji = _LEVEL_INFO.get(level, ("适合", "👍"))
    if not note:
        note = f"{species.name}{'很喜欢' if level in ('perfect','suitable') else '不太适合'}这个食物"

    return {"level": level, "label": label, "emoji": emoji, "note": note}


def is_pet_sick(pet: PetAdoption) -> bool:
    """检查宠物是否处于生病状态。"""
    if not pet.sick_until:
        return False
    return now_local() < pet.sick_until


def get_sick_remaining(pet: PetAdoption) -> int:
    """获取生病剩余秒数，健康返回 0。"""
    if not pet.sick_until:
        return 0
    diff = (pet.sick_until - now_local()).total_seconds()
    return max(0, int(diff))
