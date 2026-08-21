"""宠物乐园 API 路由：领养、状态、成长记录、喂养、放弃、适配性。"""
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..models import User, PetSpecies, PetAdoption, PetFeedLog, PetFeedItem
from ..database import get_db
from ..deps import require_role
from ..services.pet_service import (
    get_active_pet, calc_stage, get_stage_emoji, get_stage_label,
    apply_xp_gain, compute_suitability, is_pet_sick, get_sick_remaining,
    get_food_category,
    _DIET_FOOD_MATRIX, _SICKNESS_EFFECTS, _STREAK_BONUS_THRESHOLD, _STREAK_BONUS_RATE,
)
from ..config import PET_STAGE_THRESHOLDS
from ..utils.timeutil import now_local
from ..utils.pagination import paginate, CLIENT_PAGE_SIZE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pet", tags=["pet"])

# 每用户最多可同时拥有的活跃宠物数量
MAX_PETS_PER_USER = 3


# ---------- 请求/响应模型 ----------

class AdoptRequest(BaseModel):
    species_id: int
    nickname: str = ""


class AbandonRequest(BaseModel):
    reason: str = ""


class FeedRequest(BaseModel):
    food_id: int
    quantity: int = 1


# ---------- 学生端接口 ----------

@router.get("/species")
def list_species(
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """获取可领养的宠物种类列表。"""
    species = db.query(PetSpecies).filter_by(status="on").order_by(PetSpecies.sort_order).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "emoji_baby": s.emoji_baby,
            "emoji_youth": s.emoji_youth,
            "emoji_adult": s.emoji_adult,
            "emoji_legend": s.emoji_legend,
        }
        for s in species
    ]


@router.get("/species/list")
def list_species_paged(
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=60),
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """获取宠物种类分页列表（形态图鉴页使用）。"""
    q = db.query(PetSpecies).filter_by(status="on").order_by(PetSpecies.sort_order)
    items, meta = paginate(q, page, size, default_size=CLIENT_PAGE_SIZE)
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "emoji_baby": s.emoji_baby,
                "emoji_youth": s.emoji_youth,
                "emoji_adult": s.emoji_adult,
                "emoji_legend": s.emoji_legend,
            }
            for s in items
        ],
        **meta,
    }


@router.post("/adopt")
def adopt_pet(
    req: AdoptRequest,
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """领养一只宠物（每用户最多同时拥有 3 只活跃宠物）。"""
    # 统计当前活跃宠物数量
    active_count = db.query(PetAdoption).filter_by(
        user_id=user.id, is_active=True
    ).count()
    if active_count >= MAX_PETS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"您已拥有最大数量的宠物（{MAX_PETS_PER_USER} 只），请先放弃一只后再领养",
        )

    # 检查种类是否存在且可领养
    species = db.query(PetSpecies).filter_by(id=req.species_id, status="on").first()
    if not species:
        raise HTTPException(status_code=400, detail="该宠物种类不可领养")

    # 创建领养记录
    adoption = PetAdoption(
        user_id=user.id,
        species_id=species.id,
        nickname=req.nickname.strip() or species.name,
        current_xp=0,
        current_stage="baby",
        adopted_at=now_local(),
        is_active=True,
    )
    db.add(adoption)
    db.flush()

    # 同步 User 冗余字段
    user.pet_id = adoption.id
    user.pet_level = "baby"
    user.pet_xp = 0

    db.commit()

    return {
        "message": f"成功领养 {species.name}！取个好名字吧~",
        "active_pets_count": active_count + 1,
        "max_pets": MAX_PETS_PER_USER,
        "pet": {
            "id": adoption.id,
            "species_id": species.id,
            "species_name": species.name,
            "nickname": adoption.nickname,
            "current_xp": 0,
            "current_stage": "baby",
            "emoji": species.emoji_baby,
            "stage_label": "幼年期",
        },
    }


@router.get("/status")
def pet_status(
    pet_id: int = Query(None, description="指定宠物 ID，不传则返回第一只活跃宠物"),
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """获取当前宠物状态（含种类信息、升级进度、生病状态、连击信息）。
    返回 active_pets_count / max_pets 供前端判断领养上限。"""
    active_count = db.query(PetAdoption).filter_by(
        user_id=user.id, is_active=True
    ).count()

    if pet_id:
        pet = db.query(PetAdoption).filter_by(
            id=pet_id, user_id=user.id, is_active=True
        ).first()
    else:
        pet = get_active_pet(db, user.id)
    if not pet:
        return {"has_pet": False, "pet": None, "active_pets_count": active_count, "max_pets": MAX_PETS_PER_USER}

    species = pet.species
    stage = pet.current_stage
    emoji = get_stage_emoji(stage)
    label = get_stage_label(stage)

    # 计算下一阶段所需 XP
    next_stage = None
    next_xp = None
    sorted_stages = sorted(PET_STAGE_THRESHOLDS.items(), key=lambda x: x[1])
    for i, (s, threshold) in enumerate(sorted_stages):
        if s == stage and i + 1 < len(sorted_stages):
            next_stage = sorted_stages[i + 1][0]
            next_xp = sorted_stages[i + 1][1]
            break

    # 生病状态
    sick = is_pet_sick(pet)
    remaining = get_sick_remaining(pet) if sick else 0

    # 饮食类型
    diet_type = species.diet_type or "omnivore"
    _DIET_LABEL = {
        "carnivore": "食肉动物",
        "herbivore": "食草动物",
        "omnivore": "杂食动物",
        "special": "特殊饮食",
    }

    return {
        "has_pet": True,
        "active_pets_count": active_count,
        "max_pets": MAX_PETS_PER_USER,
        "pet": {
            "id": pet.id,
            "species_id": species.id,
            "species_name": species.name,
            "description": species.description,
            "nickname": pet.nickname,
            "current_xp": pet.current_xp,
            "current_stage": stage,
            "stage_label": label,
            "emoji": emoji,
            "emoji_baby": species.emoji_baby,
            "emoji_youth": species.emoji_youth,
            "emoji_adult": species.emoji_adult,
            "emoji_legend": species.emoji_legend,
            "adopted_at": pet.adopted_at.isoformat() if pet.adopted_at else None,
            "last_fed_at": pet.last_fed_at.isoformat() if pet.last_fed_at else None,
            "next_stage": next_stage,
            "next_stage_label": get_stage_label(next_stage) if next_stage else None,
            "next_stage_xp": next_xp,
            "xp_to_next": max(0, next_xp - pet.current_xp) if next_xp else 0,
            "diet_type": diet_type,
            "diet_label": _DIET_LABEL.get(diet_type, "杂食动物"),
            "sick": sick,
            "sick_remaining_seconds": remaining,
            "perfect_streak": pet.perfect_streak or 0,
        },
    }


@router.get("/feed-log")
def pet_feed_log(
    page: int = Query(1, ge=1),
    size: int = Query(CLIENT_PAGE_SIZE, ge=1, le=50),
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """获取宠物成长流水记录。"""
    pet = get_active_pet(db, user.id)
    if not pet:
        return {"items": [], "total": 0, "page": 1, "size": size, "pages": 0}

    q = (
        db.query(PetFeedLog)
        .filter_by(adoption_id=pet.id)
        .order_by(PetFeedLog.created_at.desc())
    )
    items, meta = paginate(q, page, size, default_size=CLIENT_PAGE_SIZE)

    return {
        "items": [
            {
                "id": log.id,
                "feed_type": log.feed_type,
                "xp_gained": log.xp_gained,
                "total_xp_after": log.total_xp_after,
                "stage_before": log.stage_before,
                "stage_after": log.stage_after,
                "stage_changed": log.stage_before != log.stage_after if log.stage_before and log.stage_after else False,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in items
        ],
        **meta,
    }


@router.get("/list")
def pet_list(
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """获取用户所有活跃宠物列表。"""
    pets = db.query(PetAdoption).filter_by(
        user_id=user.id, is_active=True
    ).order_by(PetAdoption.adopted_at.desc()).all()

    return {
        "active_pets": [
            {
                "id": p.id,
                "species_id": p.species_id,
                "species_name": p.species.name if p.species else "",
                "nickname": p.nickname,
                "emoji": get_stage_emoji(p.current_stage),
                "current_xp": p.current_xp,
                "current_stage": p.current_stage,
                "stage_label": get_stage_label(p.current_stage),
                "sick": is_pet_sick(p),
                "perfect_streak": p.perfect_streak or 0,
                "adopted_at": p.adopted_at.isoformat() if p.adopted_at else None,
            }
            for p in pets
        ],
        "active_pets_count": len(pets),
        "max_pets": MAX_PETS_PER_USER,
    }


@router.post("/abandon")
def abandon_pet(
    req: AbandonRequest,
    pet_id: int = Query(None, description="要放弃的宠物 ID，不传则放弃唯一的活跃宠物"),
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """放弃指定宠物（支持多宠物场景）。"""
    if pet_id:
        pet = db.query(PetAdoption).filter_by(
            id=pet_id, user_id=user.id, is_active=True
        ).first()
    else:
        pet = get_active_pet(db, user.id)
    if not pet:
        raise HTTPException(status_code=400, detail="你当前没有该宠物")

    pet_name = pet.nickname
    pet.is_active = False
    pet.abandoned_at = now_local()

    # 如果放弃的是 User 冗余字段关联的宠物，清空
    if user.pet_id == pet.id:
        user.pet_id = None
        user.pet_level = None
        user.pet_xp = 0

    db.commit()

    remaining = db.query(PetAdoption).filter_by(
        user_id=user.id, is_active=True
    ).count()

    return {"message": f"已放弃 {pet_name}，你还可以领养 {MAX_PETS_PER_USER - remaining} 只宠物"}


# ---------- 食物商店 + 喂养 ----------

@router.get("/foods")
def list_foods(
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """获取可购买的宠物食物列表（含适配性标识）。"""
    pet = get_active_pet(db, user.id)
    items = db.query(PetFeedItem).filter_by(status="on").order_by(PetFeedItem.sort_order).all()
    result = []
    for f in items:
        item_data = {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "emoji": f.emoji,
            "price": f.price,
            "xp_value": f.xp_value,
            "species_id": f.species_id,
            "species_name": f.species.name if f.species else None,
        }
        # 如果有活跃宠物，计算适配性
        if pet:
            suit = compute_suitability(pet.species, f)
            item_data["suitability"] = suit
        result.append(item_data)
    return result


@router.get("/food-suitability")
def food_suitability(
    species_id: int = Query(...),
    food_id: int = Query(...),
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """查询食物对特定宠物的适配等级。"""
    species = db.query(PetSpecies).filter_by(id=species_id).first()
    if not species:
        raise HTTPException(400, "宠物种类不存在")
    food = db.query(PetFeedItem).filter_by(id=food_id).first()
    if not food:
        raise HTTPException(400, "食物不存在")
    suit = compute_suitability(species, food)
    return suit


@router.post("/feed")
def feed_pet(
    req: FeedRequest,
    user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    """使用积分购买食物喂养宠物（含适配性校验、生病机制、连击加成）。

    流程：
    1. 校验活跃宠物 + 食物有效性
    2. 计算适配性等级
    3. danger 级别直接拒绝，warning/caution 允许但触发不适
    4. 原子操作：扣积分 → 加 XP（含连击加成）→ 写流水 → 同步冗余字段
    """
    if req.quantity < 1 or req.quantity > 99:
        raise HTTPException(status_code=400, detail="数量无效（1-99）")

    # 1. 检查活跃宠物
    pet = get_active_pet(db, user.id)
    if not pet:
        raise HTTPException(status_code=400, detail="你当前没有活跃宠物，请先领养")

    # 1b. 检查宠物是否生病
    if is_pet_sick(pet):
        remaining = get_sick_remaining(pet)
        mins = max(1, remaining // 60)
        raise HTTPException(status_code=400,
            detail=f"{pet.nickname} 现在不太舒服，需要休息 {mins} 分钟后再喂养")

    # 2. 检查食物
    food = db.query(PetFeedItem).filter_by(id=req.food_id, status="on").first()
    if not food:
        raise HTTPException(status_code=400, detail="该食物不可用")

    # 3. 计算适配性
    suit = compute_suitability(pet.species, food)
    suit_level = suit["level"]

    # danger 级别直接拒绝
    if suit_level == "danger":
        raise HTTPException(status_code=400,
            detail=f"该食物不适合 {pet.nickname}，强行喂食可能导致生病！{suit['note']}")

    # 4. 计算总消耗和总 XP
    total_cost = food.price * req.quantity
    total_xp = food.xp_value * req.quantity

    # 完美适配连击加成
    streak_bonus = 0
    if suit_level == "perfect":
        pet.perfect_streak = (pet.perfect_streak or 0) + 1
        if pet.perfect_streak >= _STREAK_BONUS_THRESHOLD:
            streak_bonus = round(total_xp * (_STREAK_BONUS_RATE - 1))
            total_xp += streak_bonus
    else:
        pet.perfect_streak = 0  # 非完美适配重置连击

    # 5. 检查积分余额
    if user.points < total_cost:
        raise HTTPException(status_code=400,
            detail=f"积分不足，需要 {total_cost} 积分，当前余额 {user.points} 积分")

    # 6. 记录操作前状态
    old_stage = pet.current_stage

    try:
        # 7. 扣减积分
        user.points -= total_cost

        # 8. 累加 XP 并判定升级
        result = apply_xp_gain(db, pet, user, total_xp)

        # 9. 不适配触发疾病（warning/caution 级别）
        sick_triggered = False
        if suit_level in ("warning", "caution"):
            # 生病 2 小时（模拟时间）
            pet.sick_until = now_local() + timedelta(hours=2)
            sick_triggered = True

        # 10. 写喂养流水
        log = PetFeedLog(
            user_id=user.id,
            adoption_id=pet.id,
            feed_type="item",
            xp_gained=total_xp,
            total_xp_after=pet.current_xp,
            stage_before=old_stage,
            stage_after=result["new_stage"],
            feed_item_id=food.id,
            points_cost=total_cost,
            suitability_result=suit_level,
        )
        db.add(log)

        # 11. 更新最后喂养时间
        pet.last_fed_at = now_local()

        # 12. 提交事务
        db.commit()

        logger.info(
            f"喂养成功: user={user.username} food={food.name}x{req.quantity} "
            f"suit={suit_level} cost={total_cost} xp={total_xp} "
            f"streak={pet.perfect_streak} bonus={streak_bonus}"
        )

        resp = {
            "message": f"喂养成功！{pet.nickname} 吃了 {food.emoji}{food.name}x{req.quantity}",
            "points_cost": total_cost,
            "xp_gained": total_xp,
            "stage_changed": result["stage_changed"],
            "old_stage": old_stage,
            "new_stage": result["new_stage"],
            "current_xp": pet.current_xp,
            "points_remaining": user.points,
            "suitability": suit,
            "perfect_streak": pet.perfect_streak,
        }
        if streak_bonus > 0:
            resp["streak_bonus"] = streak_bonus
            resp["message"] += f" ✨连击加成 +{streak_bonus}XP！"
        if sick_triggered:
            resp["sick"] = True
            resp["message"] += f" ⚠️ {pet.nickname} 吃了不太合适的食物，有点不舒服了..."

        return resp

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"喂养失败: user={user.username} food={food.id} error={e}")
        raise HTTPException(status_code=500, detail="喂养操作失败，请重试")
