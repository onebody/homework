"""回归测试共享配置与辅助函数。

所有测试均通过 HTTP API 执行，需要运行中的后端服务器。
服务器地址可通过环境变量 API_BASE_URL 设定，默认为 http://localhost:8000。

使用方法：
    # 确保后端已启动
    cd backend && python migrate.py && uvicorn app.main:app --host 0.0.0.0 --port 8000

    # 运行全部回归测试
    python -m pytest tests/ -v

    # 运行单个模块
    python -m pytest tests/test_auth.py -v

    # 通过 shell 脚本（自动检查服务状态）
    bash tests/run_tests.sh
"""

import os
import time

import requests

# 建议：运行测试时设置 RATE_LIMIT_ENABLED=0 以绕过速率限制
# 在运行测试前设置：export RATE_LIMIT_ENABLED=0 或使用 run_all.py

# ── 环境配置 ────────────────────────────────────────────────────────────────
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

# 管理员密码（需与服务端 ADMIN_INIT_PASSWORD 一致，否则测试中会使用自动生成密码）
ADMIN_PASSWORD = os.environ.get("ADMIN_INIT_PASSWORD", "admin123")

# 测试用户前缀（确保不与其他环境冲突）
TEST_PREFIX = f"regtest_{int(time.time())}"


# ── 通用辅助函数 ────────────────────────────────────────────────────────────

def api_url(path: str) -> str:
    """拼接完整 API URL。"""
    return f"{API_BASE}{path}"


def json_post(path: str, data: dict, token: str | None = None) -> requests.Response:
    """POST JSON 请求。"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.post(api_url(path), json=data, headers=headers)


def json_put(path: str, data: dict, token: str | None = None) -> requests.Response:
    """PUT JSON 请求。"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.put(api_url(path), json=data, headers=headers)


def json_get(path: str, token: str | None = None) -> requests.Response:
    """GET 请求。"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.get(api_url(path), headers=headers)


def json_delete(path: str, token: str | None = None) -> requests.Response:
    """DELETE 请求。"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.delete(api_url(path), headers=headers)


def assert_ok(r: requests.Response, msg: str = ""):
    """断言 HTTP 200 且 JSON 包含 ok 或 status ok。"""
    assert r.status_code == 200, f"[{msg}] HTTP {r.status_code}: {r.text[:200]}"
    return r.json()


def assert_http(status: int, r: requests.Response, msg: str = ""):
    """断言指定 HTTP 状态码。"""
    assert r.status_code == status, f"[{msg}] 期望 {status}，实际 {r.status_code}: {r.text[:200]}"
    return r.json()


def check_service() -> bool:
    """检查后端服务是否可访问。"""
    try:
        r = requests.get(api_url("/api/health"), timeout=5)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False
