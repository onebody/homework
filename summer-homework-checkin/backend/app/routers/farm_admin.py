"""成长农场 - 管理端 API（prefix /api/admin/farm）。

数据概览 + 站点默认乐园名配置 + 内置模板启停。
独立成文件避免 routers/admin.py 继续膨胀。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_role
from ..models import Farm, FarmTemplate, SiteConfig, User
from ..utils.timeutil import now_local

router = APIRouter(prefix="/api/admin/farm", tags=["farm-admin"])

_admin = require_role("admin")

DEFAULT_FARM_NAME = "我的成长乐园"


# ---------- 概览 ----------

@router.get("/overview")
def overview(_user: User = Depends(_admin), db: Session = Depends(get_db)):
    total_farms = db.query(Farm).count()
    sums = db.query(
        func.coalesce(func.sum(Farm.energy_balance), 0),
        func.coalesce(func.sum(Farm.total_energy_earned), 0),
        func.coalesce(func.sum(Farm.forest_count), 0),
    ).one()
    top = (
        db.query(Farm, User.nickname)
        .join(User, User.id == Farm.user_id)
        .order_by(Farm.total_energy_earned.desc())
        .limit(10).all()
    )
    return {
        "total_farms": total_farms,
        "total_energy_balance": int(sums[0]),
        "total_energy_earned": int(sums[1]),
        "total_forest": int(sums[2]),
        "top_farms": [{
            "nickname": nick or f"学生{f.user_id}",
            "name": f.name,
            "total_energy_earned": f.total_energy_earned or 0,
            "forest_count": f.forest_count or 0,
        } for f, nick in top],
    }


# ---------- 站点默认乐园名 ----------

class FarmConfigIn(BaseModel):
    farm_default_name: str | None = Field(None, max_length=64)


@router.get("/config")
def get_config(_user: User = Depends(_admin), db: Session = Depends(get_db)):
    cfg = db.query(SiteConfig).first()
    return {"farm_default_name": (getattr(cfg, "farm_default_name", None) if cfg else None) or DEFAULT_FARM_NAME}


@router.put("/config")
def update_config(req: FarmConfigIn, _user: User = Depends(_admin), db: Session = Depends(get_db)):
    cfg = db.query(SiteConfig).first()
    if not cfg:
        cfg = SiteConfig()
        db.add(cfg)
    name = (req.farm_default_name or "").strip()
    if name and len(name) > 32:
        raise HTTPException(status_code=400, detail="默认乐园名过长（≤32 字符）")
    cfg.farm_default_name = name or None   # 空=回退内置默认
    cfg.updated_at = now_local()
    db.commit()
    return {"ok": True, "farm_default_name": cfg.farm_default_name or DEFAULT_FARM_NAME}


# ---------- 模板管理 ----------

class FarmTemplateStatusIn(BaseModel):
    status: str  # on|off


@router.get("/templates")
def templates(_user: User = Depends(_admin), db: Session = Depends(get_db)):
    items = db.query(FarmTemplate).order_by(FarmTemplate.sort_order, FarmTemplate.id).all()
    return {"items": [{
        "id": t.id, "key": t.key, "name": t.name, "status": t.status,
        "sort_order": t.sort_order or 0,
        "farm_count": db.query(Farm).filter_by(template_id=t.id).count(),
    } for t in items]}


@router.put("/templates/{tpl_id}")
def update_template(tpl_id: int, req: FarmTemplateStatusIn,
                    _user: User = Depends(_admin), db: Session = Depends(get_db)):
    """启用/停用模板：停用后不可新选，已开通农场不受影响。"""
    if req.status not in ("on", "off"):
        raise HTTPException(status_code=400, detail="status 仅支持 on|off")
    tpl = db.get(FarmTemplate, tpl_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    tpl.status = req.status
    db.commit()
    return {"ok": True, "id": tpl.id, "status": tpl.status}
