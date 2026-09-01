"""成长农场服务层：能量转化、种植养殖、成长树与森林。

能量规则（学习行为 → 成长能量 → 农场养成）：
- 学习任务审核通过 +10 能量（实时联动 + 首次开通一次性历史回填）
- 暑期打卡审核通过 +5 能量（同上）
- 种菜消耗 20 能量，成熟收获 +30（正向循环）
- 养殖消耗 50 能量，成熟收获 +80
- 浇树每次消耗 50 能量注入成长树；累计 1500 能量育成一棵大树（森林 +1），
  成长树重新生长，循环催生更大的森林

所有能量变更落 farm_energy_log 全量审计（含余额快照），数值操作先校验后落库。
"""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    CheckIn, Farm, FarmEnergyLog, FarmPlot, FarmTemplate, SiteConfig,
    TaskSubmission, User,
)
from ..utils.timeutil import now_local
from .notify_service import notify

# ---------- 数值配置（游戏平衡） ----------
ENERGY_PER_TASK = 10        # 学习任务审核通过
ENERGY_PER_CHECKIN = 5      # 打卡审核通过
CROP_COST, CROP_REWARD = 20, 30
CROP_MINUTES = 120          # 作物成熟时间（2 小时，养成节奏）
ANIMAL_COST, ANIMAL_REWARD = 50, 80
ANIMAL_MINUTES = 480        # 动物成熟时间（8 小时）
WATER_COST = 50             # 单次浇树注入能量
TREE_MAX_ENERGY = 1500      # 育成一棵大树（森林 +1）所需累计能量
TREE_STAGE_THRESHOLDS = (0, 100, 400, 900)  # tree_stage 0-3 门槛，>=1500 育成后归零循环
TREE_EMOJIS = ("🌱", "🌿", "🪴", "🌳")
MAX_PLOTS_BASE = 4          # 基础地块数，成长树每升 1 阶段 +1

DEFAULT_FARM_NAME = "我的成长乐园"


def get_default_farm_name(db: Session) -> str:
    """站点级默认乐园名（管理员可在后台配置），空则用内置默认。"""
    cfg = db.query(SiteConfig).first()
    name = getattr(cfg, "farm_default_name", None) if cfg else None
    return (name or "").strip() or DEFAULT_FARM_NAME


def get_farm(db: Session, user_id: int) -> Farm | None:
    return db.query(Farm).filter_by(user_id=user_id).first()


def _resolve_farm(db: Session, user_id: int) -> Farm:
    farm = get_farm(db, user_id)
    if not farm:
        raise HTTPException(status_code=404, detail="尚未开通成长农场")
    return farm


def _log(db: Session, farm: Farm, source: str, delta: int, ref_id=None, note=None):
    db.add(FarmEnergyLog(
        user_id=farm.user_id, farm_id=farm.id, source=source,
        delta=delta, balance_after=farm.energy_balance,
        ref_id=ref_id, note=note,
    ))


def _add_energy(db: Session, farm: Farm, source: str, amount: int, ref_id=None, note=None):
    if amount <= 0:
        return
    farm.energy_balance = (farm.energy_balance or 0) + amount
    farm.total_energy_earned = (farm.total_energy_earned or 0) + amount
    farm.updated_at = now_local()
    _log(db, farm, source, amount, ref_id, note)


def _spend_energy(db: Session, farm: Farm, source: str, amount: int, ref_id=None, note=None):
    if (farm.energy_balance or 0) < amount:
        raise HTTPException(status_code=400, detail=f"能量不足（需 {amount}，当前 {farm.energy_balance or 0}）")
    farm.energy_balance -= amount
    farm.updated_at = now_local()
    _log(db, farm, source, -amount, ref_id, note)


def max_plots(farm: Farm) -> int:
    return MAX_PLOTS_BASE + (farm.tree_stage or 0) + (farm.forest_count or 0)


def tree_progress(farm: Farm) -> dict:
    e = farm.tree_energy or 0
    return {
        "tree_energy": e,
        "tree_stage": farm.tree_stage or 0,
        "tree_emoji": TREE_EMOJIS[min(farm.tree_stage or 0, len(TREE_EMOJIS) - 1)],
        "next_threshold": TREE_MAX_ENERGY,
        "percent": min(100, int(e * 100 / TREE_MAX_ENERGY)),
        "forest_count": farm.forest_count or 0,
    }


def tree_stage_for(energy: int) -> int:
    stage = 0
    for i, th in enumerate(TREE_STAGE_THRESHOLDS):
        if energy >= th:
            stage = i
    return stage


# ---------- 开通与历史回填 ----------

def init_farm(db: Session, user: User, name: str | None, template_key: str | None) -> Farm:
    """开通农场：默认模板 + 站点默认名；历史已审核任务/打卡一次性回填能量（去重守卫）。"""
    if get_farm(db, user.id):
        raise HTTPException(status_code=400, detail="成长农场已开通")

    tpl = None
    if template_key:
        tpl = db.query(FarmTemplate).filter_by(key=template_key, status="on").first()
        if not tpl:
            raise HTTPException(status_code=400, detail="所选农场模板不存在或已停用")
    else:
        tpl = db.query(FarmTemplate).filter_by(status="on").order_by(
            FarmTemplate.sort_order, FarmTemplate.id).first()

    farm = Farm(
        user_id=user.id,
        name=(name or "").strip() or get_default_farm_name(db),
        template_id=tpl.id if tpl else None,
        backfilled=False,
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)

    # 历史回填：已审核通过的任务提交 ×10 + 有效打卡 ×5（一次性，backfilled 守卫）
    tasks = db.query(TaskSubmission).filter_by(
        user_id=user.id, review_status="approved", is_effective=True).count()
    checkins = db.query(CheckIn).filter_by(
        user_id=user.id, review_status="approved", is_effective=True).count()
    backfill = tasks * ENERGY_PER_TASK + checkins * ENERGY_PER_CHECKIN
    if backfill > 0:
        _add_energy(db, farm, "backfill", backfill,
                    note=f"历史学习成果转化：{tasks} 个任务 + {checkins} 次打卡")
    farm.backfilled = True
    db.commit()
    db.refresh(farm)
    return farm


# ---------- 实时联动挂钩（审核通过后调用；无农场则静默跳过，能量在开通时回填） ----------

def on_task_approved(db: Session, user_id: int, submission_id: int, task_title: str = ""):
    farm = get_farm(db, user_id)
    if not farm or not farm.backfilled:
        return None
    _add_energy(db, farm, "task_approval", ENERGY_PER_TASK, submission_id,
                note=task_title or None)
    db.commit()
    return ENERGY_PER_TASK


def on_checkin_approved(db: Session, user_id: int, checkin_id: int):
    farm = get_farm(db, user_id)
    if not farm or not farm.backfilled:
        return None
    _add_energy(db, farm, "checkin_approval", ENERGY_PER_CHECKIN, checkin_id)
    db.commit()
    return ENERGY_PER_CHECKIN


# ---------- 种植 / 养殖 / 收获 ----------

def _item_of(tpl: FarmTemplate, plot_type: str, item_key: str) -> dict | None:
    import json
    raw = tpl.crop_items if plot_type == "crop" else tpl.animal_items
    try:
        items = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        items = []
    return next((it for it in items if it.get("key") == item_key), None)


def plant(db: Session, user: User, plot_type: str, item_key: str) -> FarmPlot:
    if plot_type not in ("crop", "animal"):
        raise HTTPException(status_code=400, detail="地块类型无效（crop/animal）")
    farm = _resolve_farm(db, user.id)
    active = db.query(FarmPlot).filter(
        FarmPlot.farm_id == farm.id, FarmPlot.status != "harvested").count()
    if active >= max_plots(farm):
        raise HTTPException(
            status_code=400,
            detail=f"地块已满（{active}/{max_plots(farm)}），收获或浇树升级后可扩容")

    tpl = db.get(FarmTemplate, farm.template_id) if farm.template_id else None
    item = _item_of(tpl, plot_type, item_key) if tpl else None
    if not item:
        raise HTTPException(status_code=400, detail="所选作物/动物不在当前模板素材中")

    cost, reward, minutes = (
        (CROP_COST, CROP_REWARD, CROP_MINUTES) if plot_type == "crop"
        else (ANIMAL_COST, ANIMAL_REWARD, ANIMAL_MINUTES)
    )
    source = "plant" if plot_type == "crop" else "adopt"
    _spend_energy(db, farm, source, cost, note=item.get("name"))
    plot = FarmPlot(
        farm_id=farm.id, plot_type=plot_type, item_key=item_key,
        status="growing", energy_cost=cost, reward_energy=reward,
        planted_at=now_local(), mature_at=now_local() + timedelta(minutes=minutes),
    )
    db.add(plot)
    db.commit()
    db.refresh(plot)
    return plot


def harvest(db: Session, user: User, plot_id: int) -> FarmPlot:
    farm = _resolve_farm(db, user.id)
    plot = db.get(FarmPlot, plot_id)
    if not plot or plot.farm_id != farm.id:
        raise HTTPException(status_code=404, detail="地块不存在")  # 404 防探测
    if plot.status == "harvested":
        raise HTTPException(status_code=400, detail="该地块已收获")
    if plot.mature_at and now_local() < plot.mature_at:
        raise HTTPException(status_code=400, detail="尚未成熟，再等等哦")
    plot.status = "harvested"
    plot.harvested_at = now_local()
    _add_energy(db, farm, "harvest", plot.reward_energy or 0, plot.id)
    db.commit()
    db.refresh(plot)
    return plot


# ---------- 成长树 ----------

def water_tree(db: Session, user: User) -> dict:
    """浇树：消耗能量注入成长树；阶段自动提升，育满一棵大树则森林 +1 并重新生长。"""
    farm = _resolve_farm(db, user.id)
    _spend_energy(db, farm, "water", WATER_COST, note="浇灌成长树")
    farm.tree_energy = (farm.tree_energy or 0) + WATER_COST

    leveled = False
    forest_grown = False
    if farm.tree_energy >= TREE_MAX_ENERGY:
        # 育成大树：森林 +1，成长树归零重新生长（循环催生森林）
        farm.forest_count = (farm.forest_count or 0) + 1
        farm.tree_energy = 0
        farm.tree_stage = 0
        forest_grown = True
    else:
        new_stage = tree_stage_for(farm.tree_energy)
        if new_stage > (farm.tree_stage or 0):
            farm.tree_stage = new_stage
            leveled = True
    db.commit()
    db.refresh(farm)

    if forest_grown:
        notify(
            db, user.id, "student", "farm",
            "🌲 成长树育成，森林 +1！",
            f"你的「{farm.name}」育成第 {farm.forest_count} 棵大树！"
            f"地块上限扩容至 {max_plots(farm)}，成长树开始新一轮生长。",
            farm.id,
        )
    elif leveled:
        notify(
            db, user.id, "student", "farm",
            f"🌿 成长树长到了新阶段！",
            f"「{farm.name}」的成长树升级了（当前 {tree_progress(farm)['tree_emoji']}），"
            f"地块上限 +1（{max_plots(farm)} 块）。",
            farm.id,
        )
    return {"leveled": leveled, "forest_grown": forest_grown, **tree_progress(farm)}


# ---------- 个性化命名 / 模板切换 ----------

def rename_farm(db: Session, user: User, name: str) -> Farm:
    farm = _resolve_farm(db, user.id)
    name = (name or "").strip()
    if not name or len(name) > 32:
        raise HTTPException(status_code=400, detail="乐园名称需为 1-32 个字符")
    farm.name = name
    farm.updated_at = now_local()
    db.commit()
    db.refresh(farm)
    return farm


def switch_template(db: Session, user: User, template_key: str) -> Farm:
    farm = _resolve_farm(db, user.id)
    tpl = db.query(FarmTemplate).filter_by(key=template_key, status="on").first()
    if not tpl:
        raise HTTPException(status_code=400, detail="所选农场模板不存在或已停用")
    farm.template_id = tpl.id
    farm.updated_at = now_local()
    db.commit()
    db.refresh(farm)
    return farm
