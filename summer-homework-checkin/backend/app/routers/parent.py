from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..models import User, StudentParent, Notification, Prize, LotteryRecord, Redemption
from ..database import get_db
from ..schemas import (
    BindRequest, ChildSummary, NotificationOut, ReportOut,
    RedeemRequest, RedeemReplaceRequest, RedemptionOut, MallOut, LotteryRecordOut,
)
from ..routers.redeem import RedeemResult
from ..deps import get_current_user, require_role
from ..services import report_service, checkin_service, redeem_service, lottery_service
from ..config import SUMMER_START, SUMMER_END

router = APIRouter(prefix="/api/parent", tags=["parent"])


@router.post("/bind")
def bind(payload: BindRequest, parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if parent.role != "parent":
        raise HTTPException(status_code=403, detail="仅家长可绑定孩子")
    child = db.query(User).filter_by(username=payload.child_username, role="student").first()
    if not child or child.bind_code != payload.bind_code:
        raise HTTPException(status_code=400, detail="孩子账号或绑定码错误")
    exists = db.query(StudentParent).filter_by(student_id=child.id, parent_id=parent.id).first()
    if exists:
        return {"ok": True, "message": "已绑定"}
    db.add(StudentParent(student_id=child.id, parent_id=parent.id))
    db.commit()
    return {"ok": True, "message": "绑定成功"}


@router.delete("/unbind/{student_id}")
def unbind(student_id: int, parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if parent.role != "parent":
        raise HTTPException(status_code=403, detail="仅家长可解绑孩子")
    bind = db.query(StudentParent).filter_by(
        student_id=student_id, parent_id=parent.id
    ).first()
    if not bind:
        return {"ok": True, "message": "该孩子已解绑"}
    db.delete(bind)
    db.commit()
    return {"ok": True, "message": "解绑成功"}


@router.get("/children", response_model=list[ChildSummary])
def children(parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    binds = db.query(StudentParent).filter_by(parent_id=parent.id).all()
    out = []
    for b in binds:
        s = db.get(User, b.student_id)
        if not s:
            continue
        status = checkin_service.get_today_status(db, s)
        out.append(ChildSummary(
            student_id=s.id, nickname=s.nickname,
            current_streak=s.current_streak, longest_streak=s.longest_streak,
            effective_checkins=s.effective_checkins, lottery_tickets=s.lottery_tickets,
            points=s.points or 0, today_checked=status["today_checked"],
            today_pending=status["today_pending"],
        ))
    return out


def _resolve_child(child_id: int, parent: User, db: Session) -> User:
    """校验家长是否绑定该孩子，返回孩子账号（用于代操作）。"""
    if parent.role != "parent":
        raise HTTPException(status_code=403, detail="无权限")
    bind = db.query(StudentParent).filter_by(student_id=child_id, parent_id=parent.id).first()
    if not bind:
        raise HTTPException(status_code=403, detail="未绑定该孩子")
    child = db.get(User, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="孩子账号不存在")
    return child


@router.get("/child-streak/{child_id}", response_model=ChildSummary)
def child_streak(child_id: int, parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = _resolve_child(child_id, parent, db)
    status = checkin_service.get_today_status(db, child)
    return ChildSummary(
        student_id=child.id, nickname=child.nickname,
        current_streak=child.current_streak, longest_streak=child.longest_streak,
        effective_checkins=child.effective_checkins, lottery_tickets=child.lottery_tickets,
        points=child.points or 0, today_checked=status["today_checked"],
        today_pending=status["today_pending"],
    )


@router.post("/checkin")
async def parent_checkin(
    child_id: int = Form(...),
    photo: UploadFile = File(...),
    proof: UploadFile = File(None),
    location_lat: float = Form(None),
    location_lng: float = Form(None),
    check_type: str = Form("normal"),
    makeup_reason: str = Form(None),
    makeup_for_date: str = Form(None),
    parent: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """家长代孩子打卡 —— 关联同一学生账号，打卡积分计入孩子余额。"""
    child = _resolve_child(child_id, parent, db)
    photo_bytes = await photo.read()
    proof_bytes = await proof.read() if proof and proof.filename else b""
    ci, ver = checkin_service.create_checkin(
        db, child, photo_bytes, location_lat, location_lng,
        check_type, makeup_reason, proof_bytes, makeup_for_date,
    )
    return {
        "ok": True, "child_id": child.id, "checkin_id": ci.id,
        "points": child.points, "message": "打卡已提交，等待管理员审核",
    }


@router.get("/mall/{child_id}", response_model=MallOut)
def child_mall(child_id: int, parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = _resolve_child(child_id, parent, db)
    prizes = redeem_service.list_prizes_for_mall(db)
    redemptions = redeem_service.list_redemptions(db, child)
    lottery_records = (
        db.query(LotteryRecord).filter_by(user_id=child.id)
        .order_by(LotteryRecord.drawn_at.desc()).all()
    )
    return MallOut(
        points=child.points or 0,
        lottery_tickets=child.lottery_tickets or 0,
        prizes=[{
            "id": p.id, "name": p.name, "description": p.description,
            "category": p.category, "cost_points": p.cost_points,
            "stock": p.stock, "image_url": p.image_url,
            "is_lottery_ticket": p.is_lottery_ticket,
            "ticket_qty": p.ticket_qty,
        } for p in prizes],
        redemptions=[RedemptionOut.model_validate(r) for r in redemptions],
        lottery_records=[LotteryRecordOut.model_validate(r) for r in lottery_records],
    )


@router.post("/redeem", response_model=RedeemResult)
def child_redeem(
    child_id: int, req: RedeemRequest,
    parent: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    child = _resolve_child(child_id, parent, db)
    prize = db.query(Prize).filter(Prize.id == req.prize_id).first()
    is_lottery = prize.is_lottery_ticket if prize else False
    rec, bal = redeem_service.redeem(db, child, req.prize_id)
    if is_lottery:
        return RedeemResult(
            redemption=None,
            balance=bal,
            lottery_tickets=child.lottery_tickets or 0,
            is_lottery_ticket=True,
            message=f"成功兑换抽奖机会，当前抽奖券：{child.lottery_tickets or 0} 张",
        )
    return RedeemResult(
        redemption=RedemptionOut.model_validate(rec),
        balance=bal,
        lottery_tickets=child.lottery_tickets or 0,
        is_lottery_ticket=False,
        message=f"兑换成功：{prize.name if prize else '奖品'}",
    )


@router.post("/redeem/{rid}/replace", response_model=RedemptionOut)
def child_replace_redeem(
    rid: int, req: RedeemReplaceRequest,
    parent: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    rec0 = db.get(Redemption, rid)
    if not rec0:
        raise HTTPException(status_code=404, detail="兑换记录不存在")
    child = _resolve_child(rec0.user_id, parent, db)
    rec, _ = redeem_service.replace_redemption(db, child, rid, req.new_prize_id)
    return RedemptionOut.model_validate(rec)


@router.get("/lottery/{child_id}")
def child_lottery(child_id: int, parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    child = _resolve_child(child_id, parent, db)
    records = (
        db.query(LotteryRecord).filter_by(user_id=child.id)
        .order_by(LotteryRecord.drawn_at.desc()).all()
    )
    return {
        "tickets": child.lottery_tickets or 0,
        "records": [LotteryRecordOut.model_validate(r) for r in records],
    }


@router.post("/lottery/{child_id}/draw")
def child_lottery_draw(child_id: int, parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """家长代孩子抽奖。"""
    child = _resolve_child(child_id, parent, db)
    return lottery_service.draw(db, child)


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = (
        db.query(Notification).filter_by(user_id=parent.id, recipient_role="parent")
        .order_by(Notification.created_at.desc()).all()
    )
    return [NotificationOut.model_validate(n) for n in items]


@router.patch("/notifications/{nid}/read")
def read_notify(nid: int, parent: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n and n.user_id == parent.id:
        n.read = True
        db.commit()
    return {"ok": True}


def _check_child_access(child_id: int, parent: User, db: Session):
    if parent.role != "parent":
        raise HTTPException(status_code=403, detail="无权限")
    bind = db.query(StudentParent).filter_by(student_id=child_id, parent_id=parent.id).first()
    if not bind:
        raise HTTPException(status_code=403, detail="未绑定该孩子")
    return db.get(User, child_id)


@router.get("/child-report/{child_id}", response_model=ReportOut)
def child_report(
    child_id: int,
    start: date = SUMMER_START, end: date = SUMMER_END,
    parent: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    child = _check_child_access(child_id, parent, db)
    return ReportOut(**report_service.build_report(db, child, start, end))


@router.get("/child-report/{child_id}/html")
def child_report_html(
    child_id: int,
    start: date = SUMMER_START, end: date = SUMMER_END,
    parent: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    from fastapi.responses import HTMLResponse
    child = _check_child_access(child_id, parent, db)
    rep = report_service.build_report(db, child, start, end)
    return HTMLResponse(report_service.build_html(rep))
