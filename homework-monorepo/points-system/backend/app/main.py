from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from app.database import init_db
from app.routers import checkin, points, prize, redeem, users, convert, lottery

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # 启动时建表
    yield


app = FastAPI(title="打卡积分兑换系统", version="1.0.0", lifespan=lifespan)

# API 路由（需在静态文件挂载之前注册，保证优先匹配）
app.include_router(checkin.router)
app.include_router(points.router)
app.include_router(prize.router)
app.include_router(redeem.router)
app.include_router(users.router)
app.include_router(convert.router)
app.include_router(lottery.router)

# 静态前端：/ 提供 index.html，/styles.css、/app.js 等静态资源
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
