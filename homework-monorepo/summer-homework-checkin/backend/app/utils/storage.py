import os
import uuid

from ..config import UPLOAD_DIR


def save_upload(file_bytes: bytes, user_id: int, prefix: str = "c") -> str:
    """保存上传文件，返回相对 UPLOAD_DIR 的路径，如 '12/2026-07-07_xxxx.jpg'。"""
    user_dir = os.path.join(UPLOAD_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    ext = ".jpg"
    fname = f"{prefix}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(user_dir, fname)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return os.path.relpath(path, UPLOAD_DIR)


def public_url(relative_path: str) -> str:
    """将相对路径转为可访问的 HTTP 路径。"""
    if not relative_path:
        return ""
    return "/uploads/" + relative_path.replace(os.sep, "/")
