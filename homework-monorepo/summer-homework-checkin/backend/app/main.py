from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from .config import UPLOAD_DIR, STUDENT_DIR, ADMIN_DIR
from .database import Base, engine
from . import models  # noqa: F401 确保模型被加载
from .routers import auth, checkin, lottery, prize, parent, report, admin, face, redeem, challenge

app = FastAPI(title="暑假作业打卡系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


# 静态资源：上传照片
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
# 独立后台管理页
app.mount("/admin", StaticFiles(directory=ADMIN_DIR, html=True), name="admin")
# H5 学生端（默认根路径）
app.mount("/", StaticFiles(directory=STUDENT_DIR, html=True), name="student")
