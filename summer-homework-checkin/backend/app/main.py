from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse

from .config import UPLOAD_DIR, STUDENT_DIR, ADMIN_DIR, ALLOWED_ORIGINS
from .database import engine
from . import models  # noqa: F401 确保模型被加载
from .routers import auth, checkin, lottery, prize, parent, report, admin, face, redeem, challenge
from .utils.rate_limit import check_rate_limit

app = FastAPI(title="暑假作业打卡系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(checkin.router)
app.include_router(lottery.router)
app.include_router(prize.router)
app.include_router(parent.router)
app.include_router(report.router)
app.include_router(admin.router)
app.include_router(face.router)
app.include_router(redeem.router)
app.include_router(challenge.router)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """对登录/注册等敏感接口执行速率限制。"""
    from fastapi import HTTPException
    try:
        check_rate_limit(request)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup():
    # 数据库迁移和种子数据由 migrate.py 在启动前完成
    # 此处保留 create_all 作为兜底，确保表结构存在
    from .database import Base
    Base.metadata.create_all(bind=engine)


# 静态资源：上传照片
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
# 独立后台管理页
app.mount("/admin", StaticFiles(directory=ADMIN_DIR, html=True), name="admin")
# H5 学生端（默认根路径）
app.mount("/", StaticFiles(directory=STUDENT_DIR, html=True), name="student")
