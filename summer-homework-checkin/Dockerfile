# 使用 DaoCloud 镜像代理拉取基础镜像（Docker Hub 直连在当前网络超时）
FROM docker.m.daocloud.io/library/python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 先复制依赖清单并安装，充分利用镜像层缓存
COPY backend/requirements.docker.txt /app/backend/requirements.docker.txt
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com -r /app/backend/requirements.docker.txt

# 复制应用源码（前端与后端）
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

WORKDIR /app/backend
EXPOSE 8000

# 首次启动写入管理员/奖品/闯关任务示例数据（幂等），随后启动服务
CMD ["sh", "-c", "python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
