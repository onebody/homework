from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..models import User
from ..database import get_db
from ..schemas import ReportOut
from ..deps import get_current_user
from ..services import report_service
from ..config import SUMMER_START, SUMMER_END

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("/me", response_model=ReportOut)
def my_report(
    start: date = SUMMER_START, end: date = SUMMER_END,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="仅学生可查看自己的报告")
    return ReportOut(**report_service.build_report(db, user, start, end))


@router.get("/me/html", response_class=HTMLResponse)
def my_report_html(
    start: date = SUMMER_START, end: date = SUMMER_END,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="仅学生可查看自己的报告")
    rep = report_service.build_report(db, user, start, end)
    return HTMLResponse(report_service.build_html(rep))
