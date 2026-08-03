"""简易内存速率限制器（防暴力破解 / 批量注册）。"""
import os
import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, HTTPException

# 是否启用速率限制（测试环境可关闭）
_RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "1") == "1"

# 配置：(路径前缀, 最大请求数, 时间窗口秒数)
# 安全加固：扩展覆盖更多敏感接口
_RATE_LIMIT_RULES: list[tuple[str, int, int]] = [
    ("/api/auth/login", 10, 60),         # 每分钟最多 10 次登录
    ("/api/auth/register", 5, 60),       # 每分钟最多 5 次注册
    ("/api/auth/password", 5, 300),      # 每 5 分钟最多 5 次密码修改
    ("/api/face/enroll", 5, 300),        # 每 5 分钟最多 5 次人脸采集
    ("/api/checkin", 30, 60),            # 每分钟最多 30 次打卡请求
]

_lock = Lock()
# {client_ip: {path_prefix: [(timestamp, ...)]}}
_hits: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP（兼容反向代理）。

    安全：取 X-Forwarded-For 链的**最后一跳**。本系统 nginx 以
    `$proxy_add_x_forwarded_for` 将真实下游 IP 追加到链尾，因此最后一段
    是可信的；而客户端自带的伪造值只会排在前面，不会被采信（防止
    通过伪造 XFF 绕过限流）。
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request):
    """在路由处理前调用，超限则抛出 HTTPException(429)。"""
    if not _RATE_LIMIT_ENABLED:
        return
    path = request.url.path
    client_ip = _get_client_ip(request)
    now = time.time()

    for prefix, max_requests, window in _RATE_LIMIT_RULES:
        if not path.startswith(prefix):
            continue
        with _lock:
            timestamps = _hits[client_ip][prefix]
            # 清除过期记录
            cutoff = now - window
            _hits[client_ip][prefix] = [t for t in timestamps if t > cutoff]
            timestamps = _hits[client_ip][prefix]
            if len(timestamps) >= max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"请求过于频繁，请在 {window} 秒后重试",
                )
            timestamps.append(now)


# ── 登录失败锁定（按用户名维度，弥补 IP 限流可被伪造 XFF 绕过的缺陷）────
# 阈值：连续失败达 _LOGIN_MAX_FAILS 次则锁定 _LOGIN_LOCK_WINDOW 秒
LOGIN_MAX_FAILS = int(os.environ.get("LOGIN_MAX_FAILS", "5"))
LOGIN_LOCK_WINDOW = int(os.environ.get("LOGIN_LOCK_WINDOW", "900"))
# {username_lower: [failure_timestamps]}
_login_fails: dict[str, list[float]] = defaultdict(list)


def check_login_locked(username: str):
    """登录前调用：若该用户名因多次失败处于锁定期则抛 429。"""
    if not _RATE_LIMIT_ENABLED:
        return
    key = (username or "").strip().lower()
    now = time.time()
    with _lock:
        cutoff = now - LOGIN_LOCK_WINDOW
        recent = [t for t in _login_fails[key] if t > cutoff]
        _login_fails[key] = recent
        if len(recent) >= LOGIN_MAX_FAILS:
            raise HTTPException(
                status_code=429,
                detail=f"登录失败次数过多，请在 {LOGIN_LOCK_WINDOW // 60} 分钟后重试",
            )


def record_login_failure(username: str):
    """登录密码错误时调用，记录一次失败。"""
    if not _RATE_LIMIT_ENABLED:
        return
    key = (username or "").strip().lower()
    with _lock:
        _login_fails[key].append(time.time())


def reset_login_failures(username: str):
    """登录成功时调用，清零该用户名的失败计数。"""
    key = (username or "").strip().lower()
    with _lock:
        _login_fails.pop(key, None)
