import hashlib
import hmac
import json
import os
import time
import base64

from .config import SECRET, TOKEN_EXPIRE_DAYS, FACE_ENCRYPT_KEY


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """使用 PBKDF2 对密码做单向哈希，每用户随机盐。
    返回 (hash_hex, salt_hex)。
    """
    if salt is None:
        salt = os.urandom(16).hex()
    salt_bytes = bytes.fromhex(salt)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 100_000).hex()
    return h, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    computed, _ = hash_password(password, salt)
    return hmac.compare_digest(computed, password_hash)


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


# ── 人脸特征向量加密（保护生物特征数据）────────────────────────────────────

def encrypt_face_embedding(embedding_json: str) -> str:
    """加密人脸特征向量（512 维浮点数组的 JSON 字符串）。
    使用 AES-GCM 认证加密（同时保证机密性与完整性），返回 Base64 编码的密文。
    格式: nonce(12) + ciphertext + tag(16)。
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes.fromhex(FACE_ENCRYPT_KEY)  # 16 字节 -> AES-128
    nonce = os.urandom(12)  # GCM 推荐 96 位 nonce
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, embedding_json.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_face_embedding(encrypted_b64: str) -> str:
    """解密人脸特征向量，返回原始 JSON 字符串。
    依次尝试 AES-GCM（新格式）→ AES-CTR（旧格式），保证向后兼容。
    篡改的 GCM 密文会因认证失败而抛出异常（完整性保护）。
    """
    key = bytes.fromhex(FACE_ENCRYPT_KEY)
    data = base64.b64decode(encrypted_b64)

    # 新格式：AES-GCM（nonce[12] + ciphertext + tag[16]）
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if len(data) >= 12 + 16:
        try:
            nonce, ct = data[:12], data[12:]
            return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
        except Exception:
            pass  # 非 GCM 格式或认证失败，回退旧格式

    # 旧格式：AES-CTR（iv[16] + ciphertext），仅用于解密历史数据
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    if len(data) < 17:
        raise ValueError("加密数据格式错误")
    iv = data[:16]
    ciphertext = data[16:]
    cipher = Cipher(
        algorithms.AES(key),
        modes.CTR(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext.decode("utf-8")
