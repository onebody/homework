import hashlib
import hmac
import json
import time
import base64

from .config import SECRET, TOKEN_EXPIRE_DAYS


def hash_password(password: str) -> str:
    """使用 PBKDF2 对密码做单向哈希，盐固定（演示用）。"""
    salt = b"summer-checkin-salt"
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password), password_hash)


def create_token(user_id: int, role: str) -> str:
    """生成一个 HMAC 签名的无状态 token（body.signature）。"""
    payload = {
        "uid": user_id,
        "role": role,
        "exp": int(time.time()) + TOKEN_EXPIRE_DAYS * 86400,
    }
    raw = json.dumps(payload, separators=(",", ":"))
    body = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def decode_token(token: str):
    """校验签名与过期时间，返回 payload 或 None。"""
    try:
        body, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        pad = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
