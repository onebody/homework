import os
import uuid

from ..config import UPLOAD_DIR


def _safe_upload_path(user_id: int, prefix: str) -> str:
    """生成安全的上传路径，防止路径穿越。"""
    user_dir = os.path.realpath(os.path.join(UPLOAD_DIR, str(user_id)))
    real_upload_dir = os.path.realpath(UPLOAD_DIR)
    if not user_dir.startswith(real_upload_dir):
        raise ValueError("非法的用户目录路径")
    os.makedirs(user_dir, exist_ok=True)
    ext = ".jpg"
    fname = f"{prefix}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(user_dir, fname)
    return path


def save_upload(file_bytes: bytes, user_id: int, prefix: str = "c") -> str:
    """保存上传文件，返回相对 UPLOAD_DIR 的路径，如 '12/2026-07-07_xxxx.jpg'。"""
    path = _safe_upload_path(user_id, prefix)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return os.path.relpath(path, UPLOAD_DIR)


def validate_upload_path(relative_path: str) -> bool:
    """校验相对路径是否在允许的上传目录内（防路径穿越）。"""
    if not relative_path:
        return False
    # 禁止路径穿越字符
    if ".." in relative_path or relative_path.startswith("/"):
        return False
    real = os.path.realpath(os.path.join(UPLOAD_DIR, relative_path))
    return real.startswith(os.path.realpath(UPLOAD_DIR))


def public_url(relative_path: str) -> str:
    """将相对路径转为可访问的 HTTP 路径。"""
    if not relative_path:
        return ""
    return "/uploads/" + relative_path.replace(os.sep, "/")
