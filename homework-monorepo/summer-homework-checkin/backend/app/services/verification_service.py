"""防代打卡校验服务。
说明：人脸与作业同框识别属于视觉 AI 能力，生产环境应接入人脸识别/
图像理解服务。本实现提供完整的校验骨架与可插拔接口，当前以
"图像真实性 + 场景合规性 + 地理位置一致性"三重校验降低代打卡风险，
人脸同框检测接口 detect_face_in_frame 预留给真实模型服务接入。
"""
from ..config import MIN_PHOTO_BYTES, MIN_PHOTO_DIM
from ..utils.image import validate_photo, inspect_image
from ..utils.geo import haversine, is_far_from_home
from .face_service import verify as face_verify


def detect_face_in_frame(image_bytes: bytes) -> dict:
    """兼容历史调用：人脸能力已升级为 1:1 本人比对（见 face_service）。"""
    return {"has_face": None, "confidence": None,
            "note": "已升级为 1:1 本人比对，见 face_service.verify"}


def verify_checkin(user, photo_bytes: bytes, lat, lng) -> dict:
    """综合校验，返回结构化结果（含人脸 1:1 比对）。"""
    result = {
        "photo_ok": False,
        "photo_detail": "",
        "geo_distance": None,
        "geo_flag": False,
        "face": {"status": "model_unavailable", "match": None, "message": ""},
        "scene_check": "warn",
        "risk": "low",
    }
    ok, detail = validate_photo(photo_bytes)
    result["photo_ok"] = ok
    result["photo_detail"] = detail

    # 地理位置一致性
    if None not in (user.home_lat, user.home_lng, lat, lng):
        d = haversine(user.home_lat, user.home_lng, lat, lng)
        result["geo_distance"] = round(d, 1) if d is not None else None
        result["geo_flag"] = is_far_from_home(user.home_lat, user.home_lng, lat, lng)

    # 人脸 1:1 比对（防代打卡核心）
    try:
        result["face"] = face_verify(user, photo_bytes)
    except Exception as e:
        result["face"] = {"status": "model_unavailable", "match": None,
                          "message": f"人脸识别服务暂不可用：{e}"}

    face = result["face"]
    fstatus = face.get("status")

    # 综合风险判定
    if not ok:
        result["scene_check"] = "warn"
        result["risk"] = "high"
    elif result["geo_flag"]:
        result["scene_check"] = "warn"
        result["risk"] = "medium"
    else:
        result["scene_check"] = "pass"
        result["risk"] = "low"

    # 已采集底图但人脸不通过 -> 标记高风险（代打卡风险）
    if user.face_enrolled and fstatus in ("mismatch", "multiple_faces", "no_face"):
        result["scene_check"] = "warn"
        result["risk"] = "high"
    elif user.face_enrolled and fstatus == "model_unavailable":
        # 已采集但模型不可用：降级为待复核，不静默放行
        result["scene_check"] = "warn"
        result["risk"] = "medium"

    return result
