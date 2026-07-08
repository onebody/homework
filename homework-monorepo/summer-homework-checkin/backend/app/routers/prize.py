from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import User, Prize
from ..database import get_db
from ..schemas import PrizeCreate, PrizeUpdate, PrizeOut
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/api", tags=["prize"])


@router.get("/prizes", response_model=list[PrizeOut])
def list_public_prizes(db: Session = Depends(get_db)):
    """面向学生端：仅展示上架奖品。"""
    items = db.query(Prize).filter(Prize.status == "on").order_by(Prize.category, Prize.id).all()
    return [PrizeOut.model_validate(p) for p in items]


@router.get("/admin/prizes", response_model=list[PrizeOut])
def list_all_prizes(_: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    items = db.query(Prize).order_by(Prize.category, Prize.id).all()
    return [PrizeOut.model_validate(p) for p in items]


@router.post("/admin/prizes", response_model=PrizeOut)
def create_prize(
    payload: PrizeCreate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    if payload.category not in ("stationery", "outdoor", "interest"):
        raise HTTPException(status_code=400, detail="奖品类别不合法")
    if not (0 <= payload.probability <= 1):
        raise HTTPException(status_code=400, detail="概率需在 0~1 之间")
    p = Prize(**payload.model_dump(), is_preset=False, created_by=admin.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return PrizeOut.model_validate(p)


@router.put("/admin/prizes/{pid}", response_model=PrizeOut)
def update_prize(
    pid: int, payload: PrizeUpdate,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    p = db.get(Prize, pid)
    if not p:
        raise HTTPException(status_code=404, detail="奖品不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return PrizeOut.model_validate(p)


@router.delete("/admin/prizes/{pid}")
def delete_prize(pid: int, _: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    p = db.get(Prize, pid)
    if not p:
        raise HTTPException(status_code=404, detail="奖品不存在")
    db.delete(p)
    db.commit()
    return {"ok": True}
