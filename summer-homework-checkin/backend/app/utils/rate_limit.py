"""简易内存速率限制器（防暴力破解 / 批量注册）。"""
import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, HTTPException

# 配置：(路径前缀, 最大请求数, 时间窗口秒数)
_RATE_LIMIT_RULES: list[tuple[str, int, int]] = [
    ("/api/auth/login", 10, 60),       # 每分钟最多 10 次登录
    ("/api/auth/register", 5, 60),     # 每分钟最多 5 次注册
]

_lock = Lock()
# {client_ip: {path_prefix: [(timestamp, ...)]}}
_hits: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))


def _get_client_ip(request: Request) -> str:
    """提取客户端 IP（兼容反向代理）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request):
    """在路由处理前调用，超限则抛出 HTTPException(429)。"""
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
