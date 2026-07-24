from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse

from .config import (
    UPLOAD_DIR, STUDENT_DIR, ADMIN_DIR,
    ALLOWED_ORIGINS, ALLOWED_METHODS, ALLOWED_HEADERS
)
from .database import engine
from . import models  # noqa: F401 确保模型被加载
from .routers import auth, checkin, lottery, prize, parent, report, admin, face, redeem, challenge
from .utils.rate_limit import check_rate_limit

app = FastAPI(title="暑假作业打卡系统", version="1.2.0")

# CORS 中间件（安全加固：收窄方法和头部）
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
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


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """添加安全响应头，防止常见 Web 攻击。"""
    response = await call_next(request)
    # 防止点击劫持
    response.headers["X-Frame-Options"] = "DENY"
    # 防止 MIME 类型嗅探
    response.headers["X-Content-Type-Options"] = "nosniff"
    # 启用 XSS 过滤（兼容旧浏览器）
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # 内容安全策略：缓解 XSS（限制脚本/样式来源；CDN 依赖与内联样式已显式放行）
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-eval' https://cdn.bootcdn.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.bootcdn.net; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'"
    )
    # 禁止引用泄露敏感 URL
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # 限制浏览器功能：允许本站使用定位（防代打卡核心功能），禁用摄像头/麦克风
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    return response


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
