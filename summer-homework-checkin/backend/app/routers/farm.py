"""成长农场 - 学生端 API（prefix /api/farm）。

能量由学习任务/打卡审核通过转化而来；种植、养殖、浇树消耗能量，
收获与阶段升级带来正向反馈。全量流水可查（/energy-log）。
"""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_role
from ..models import Farm, FarmEnergyLog, FarmPlot, FarmTemplate, User
from ..services import farm_service as fs
from ..utils.timeutil import now_local

router = APIRouter(prefix="/api/farm", tags=["farm"])


# ---------- 入参 ----------

class FarmInitIn(BaseModel):
    name: str | None = Field(None, max_length=32)
    template_key: str | None = None


class FarmRenameIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=32)


class FarmTemplateIn(BaseModel):
    template_key: str


class FarmPlantIn(BaseModel):
    plot_type: str          # crop|animal
    item_key: str


# ---------- 序列化 ----------

def _tpl_out(t: FarmTemplate) -> dict:
    def _items(raw):
        try:
            return json.loads(raw) if raw else []
        except (ValueError, TypeError):
            return []
    return {
        "id": t.id, "key": t.key, "name": t.name, "description": t.description,
        "style_class": t.style_class, "tree_emoji": t.tree_emoji,
        "crop_items": _items(t.crop_items), "animal_items": _items(t.animal_items),
        "status": t.status,
    }


def _plot_out(p: FarmPlot) -> dict:
    return {
        "id": p.id, "plot_type": p.plot_type, "item_key": p.item_key,
        "status": p.status,
        "is_mature": bool(p.mature_at and now_local() >= p.mature_at and p.status != "harvested"),
        "mature_at": p.mature_at.isoformat() if p.mature_at else None,
        "energy_cost": p.energy_cost or 0, "reward_energy": p.reward_energy or 0,
        "planted_at": p.planted_at.isoformat() if p.planted_at else None,
    }


def _rules_out() -> dict:
    return {
        "energy_per_task": fs.ENERGY_PER_TASK,
        "energy_per_checkin": fs.ENERGY_PER_CHECKIN,
        "crop_cost": fs.CROP_COST, "crop_reward": fs.CROP_REWARD,
        "animal_cost": fs.ANIMAL_COST, "animal_reward": fs.ANIMAL_REWARD,
        "water_cost": fs.WATER_COST, "tree_max_energy": fs.TREE_MAX_ENERGY,
    }


def _farm_payload(db: Session, farm: Farm) -> dict:
    tpl = db.get(FarmTemplate, farm.template_id) if farm.template_id else None
    plots = (
        db.query(FarmPlot).filter(FarmPlot.farm_id == farm.id)
        .order_by(FarmPlot.id.desc()).all()
    )
    return {
        "has_farm": True,
        "farm": {
            "id": farm.id, "name": farm.name,
            "energy_balance": farm.energy_balance or 0,
            "total_energy_earned": farm.total_energy_earned or 0,
            "max_plots": fs.max_plots(farm),
            **fs.tree_progress(farm),
        },
        "template": _tpl_out(tpl) if tpl else None,
        "plots": [_plot_out(p) for p in plots],
        "rules": _rules_out(),
    }


# ---------- 接口 ----------

@router.get("/status")
def farm_status(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """农场总览；未开通时返回模板清单与站点默认名，供前端展示开通引导。"""
    farm = fs.get_farm(db, user.id)
    if not farm:
        tpls = db.query(FarmTemplate).filter_by(status="on").order_by(
            FarmTemplate.sort_order, FarmTemplate.id).all()
        return {
            "has_farm": False,
            "default_name": fs.get_default_farm_name(db),
            "templates": [_tpl_out(t) for t in tpls],
            "rules": _rules_out(),
        }
    # 顺路刷新成熟状态（状态字段保持，前端按 mature_at 判断）
    return _farm_payload(db, farm)


@router.get("/templates")
def templates(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    items = db.query(FarmTemplate).filter_by(status="on").order_by(
        FarmTemplate.sort_order, FarmTemplate.id).all()
    return {"items": [_tpl_out(t) for t in items]}


@router.post("/init")
def init(req: FarmInitIn, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """开通农场：历史学习成果一次性转化为成长能量（去重守卫）。"""
    farm = fs.init_farm(db, user, req.name, req.template_key)
    return {"ok": True, "message": "成长农场已开通", **_farm_payload(db, farm)}


@router.put("/rename")
def rename(req: FarmRenameIn, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    farm = fs.rename_farm(db, user, req.name)
    return {"ok": True, "name": farm.name}


@router.put("/template")
def switch_template(req: FarmTemplateIn, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    farm = fs.switch_template(db, user, req.template_key)
    return {"ok": True, **_farm_payload(db, farm)}


@router.post("/plant")
def plant(req: FarmPlantIn, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    plot = fs.plant(db, user, req.plot_type, req.item_key)
    farm = fs.get_farm(db, user.id)
    return {"ok": True, "plot": _plot_out(plot), "energy_balance": farm.energy_balance}


@router.post("/harvest/{plot_id}")
def harvest(plot_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    plot = fs.harvest(db, user, plot_id)
    farm = fs.get_farm(db, user.id)
    return {"ok": True, "gained": plot.reward_energy or 0,
            "plot": _plot_out(plot), "energy_balance": farm.energy_balance}


@router.post("/water")
def water(user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    result = fs.water_tree(db, user)
    farm = fs.get_farm(db, user.id)
    return {"ok": True, "energy_balance": farm.energy_balance, "max_plots": fs.max_plots(farm), **result}


@router.get("/energy-log")
def energy_log(page: int = 1, size: int = 20,
               user: User = Depends(require_role("student")), db: Session = Depends(get_db)):
    """能量流水（分页，最新在前）。"""
    page, size = max(1, page), max(1, min(50, size))
    q = db.query(FarmEnergyLog).filter_by(user_id=user.id)
    total = q.count()
    items = (
        q.order_by(FarmEnergyLog.id.desc())
        .offset((page - 1) * size).limit(size).all()
    )
    return {
        "total": total, "page": page, "size": size,
        "items": [{
            "id": l.id, "source": l.source, "delta": l.delta,
            "balance_after": l.balance_after, "note": l.note,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        } for l in items],
    }
