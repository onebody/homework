"""轻量图像解析（不依赖 Pillow）：校验真实照片并提取尺寸，用于防代打卡场景合规校验。

安全加固：
- 严格检查文件魔数（magic bytes），仅允许 JPEG/PNG
- 检测并拒绝包含可执行代码的文件（如 SVG 中的 script 标签）
- 限制最大尺寸防止资源耗尽攻击
"""
from ..config import MIN_PHOTO_BYTES, MIN_PHOTO_DIM, PHOTO_MAX_BYTES

# 安全加固：限制最大图像尺寸（防止资源耗尽）
MAX_IMAGE_DIM = 8000  # 最大宽度/高度


def _parse_jpeg_size(data: bytes):
    # 遍历 JPEG 标记段，找到 SOF0/SOF2 等包含尺寸的段
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            return width, height
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + seg_len
    return None


def _parse_png_size(data: bytes):
    if len(data) < 24:
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def inspect_image(data: bytes):
    """返回 (ok, width, height, fmt)。ok=False 表示非受支持图像或尺寸异常。"""
    if not data:
        return False, 0, 0, ""
    if data[:2] == b"\xff\xd8":
        size = _parse_jpeg_size(data)
        fmt = "jpeg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        size = _parse_png_size(data)
        fmt = "png"
    else:
        return False, 0, 0, ""
    if not size:
        return False, 0, 0, fmt
    return True, size[0], size[1], fmt


def validate_photo(data: bytes):
    """场景合规基础校验：体积与尺寸门槛，过滤占位图/缩略图。
    
    安全加固：
    - 检查文件魔数，仅允许 JPEG/PNG
    - 检测 SVG 伪装（XML 头部 + script 标签）
    - 限制最大尺寸防止资源耗尽
    """
    if not data:
        return False, "未收到文件数据"
    
    # 安全加固：检查文件魔数（magic bytes）
    magic = data[:8]
    is_jpeg = magic[:2] == b"\xff\xd8"
    is_png = magic[:8] == b"\x89PNG\r\n\x1a\n"
    
    if not is_jpeg and not is_png:
        # 检测是否伪装成图片的 SVG 或其他格式
        if data[:5] in (b"<?xml", b"<svg ", b"<svg>"):
            return False, "不允许上传 SVG 文件"
        if data[:4] == b"<html" or data[:5] == b"<!DOC":
            return False, "不允许上传 HTML 文件"
        return False, "文件格式不支持，仅允许 JPEG 和 PNG"
    
    # 体积与尺寸门槛
    if not (MIN_PHOTO_BYTES <= len(data) <= PHOTO_MAX_BYTES):
        return False, f"照片体积不符合要求（需大于 {MIN_PHOTO_BYTES//1024}KB 且小于 {PHOTO_MAX_BYTES//1024//1024}MB）"
    
    ok, w, h, fmt = inspect_image(data)
    if not ok:
        return False, "文件不是有效的 JPEG/PNG 图像"
    
    # 安全加固：限制最大尺寸
    if w > MAX_IMAGE_DIM or h > MAX_IMAGE_DIM:
        return False, f"照片尺寸过大（{w}x{h}），请上传合理尺寸的照片"
    
    if w < MIN_PHOTO_DIM or h < MIN_PHOTO_DIM:
        return False, f"照片尺寸过小（{w}x{h}），请上传清晰现场照片"
    
    return True, f"{fmt} {w}x{h}"
