"""人脸识别服务（1:1 本人比对）。

设计说明：
- 采用 insightface 预训练模型（buffalo_l）做检测 + 512 维特征提取。
- 1:1 模式：每名学生账号对应一张「人脸底图」（注册时采集的正脸照），
  打卡时实时拍摄的现场照与其底图做余弦相似度比对，超过阈值即判定为本人。
- 该模式天然预留多用户扩展：face_embedding 字段已就位，未来若要做 1:N
  （从全班人脸库中检索身份），只需把 verify 改为对全部已注册底图批量比对即可，
  业务主流程（打卡/抽奖/报表）无需改动。
- 模型首次调用时按需下载到 ~/.insightface；若环境无 insightface 或下载失败，
  服务自动降级为「模型不可用」，已采集底图的账号在比对失败时会得到明确提示，
  而不会静默放行（防代打卡不被绕过）。
- 安全加固：人脸特征向量使用 AES-CTR 加密后存储，保护生物特征数据。
"""
import os
import json
import threading

import numpy as np

from ..config import FACE_MATCH_THRESHOLD, FACE_DET_SIZE, FACE_MODEL_NAME
from ..utils.storage import save_upload, public_url
from ..security import encrypt_face_embedding, decrypt_face_embedding

_lock = threading.Lock()
_analyzer = None
_available = None  # None=未探测, True/False


def _get_analyzer():
    """懒加载 insightface 分析器（线程安全，仅加载一次）。"""
    global _analyzer, _available
    if _analyzer is not None:
        return _analyzer
    with _lock:
        if _analyzer is not None:
            return _analyzer
        try:
            from insightface.app import FaceAnalysis
        except Exception:
            _available = False
            return None
        app = FaceAnalysis(name=FACE_MODEL_NAME,
                           root=os.path.expanduser("~/.insightface"))
        app.prepare(ctx_id=-1, det_size=FACE_DET_SIZE)  # ctx_id=-1 强制 CPU
        _analyzer = app
        _available = True
        return _analyzer


def _embed(image_bytes: bytes):
    """提取最大人脸的 512 维 embedding。返回 (emb|None, face_count, note)。"""
    import cv2
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None, 0, "图像无法解码，请重新拍摄"
    analyzer = _get_analyzer()
    if analyzer is None:
        return None, 0, "人脸识别模型不可用"
    with _lock:
        faces = analyzer.get(img)
    if not faces:
        return None, 0, "未检测到人脸，请正对镜头拍摄"
    faces = sorted(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )
    return faces[0].embedding.astype(np.float32), len(faces), None


def enroll(user, image_bytes, db):
    """采集人脸底图：要求检测到且仅检测到一张人脸。"""
    emb, count, note = _embed(image_bytes)
    if emb is None:
        return {"ok": False, "has_face": False, "face_count": count,
                "message": note or "未检测到人脸，请上传清晰正脸照"}
    if count > 1:
        return {"ok": False, "has_face": True, "face_count": count,
                "message": "检测到多张人脸，请单独拍摄孩子本人正脸照"}
    path = save_upload(image_bytes, user.id, "face")
    user.face_id_path = path
    # 安全加固：加密存储人脸特征向量
    embedding_json = json.dumps(emb.tolist())
    user.face_embedding = encrypt_face_embedding(embedding_json)
    user.face_enrolled = True
    db.commit()
    return {"ok": True, "has_face": True, "face_count": 1,
            "face_id_url": public_url(path),
            "message": "人脸底图已采集，打卡时将自动比对是否为本人"}


def unenroll(user, db):
    """撤销人脸底图。"""
    user.face_enrolled = False
    user.face_embedding = None
    user.face_id_path = None
    db.commit()
    return {"face_enrolled": False, "message": "已撤销人脸底图"}


def verify(user, image_bytes):
    """1:1 比对现场照与已采集底图。返回结构化结果。"""
    if not user.face_enrolled or not user.face_embedding:
        return {"status": "not_enrolled", "match": None, "score": None,
                "has_face": None, "face_count": None,
                "message": "尚未采集人脸底图，建议先到「我的」采集"}
    emb_b, count, note = _embed(image_bytes)
    if emb_b is None:
        return {"status": "no_face", "match": False, "score": None,
                "has_face": False, "face_count": count,
                "message": note or "未检测到人脸"}
    if count > 1:
        return {"status": "multiple_faces", "match": False, "score": None,
                "has_face": True, "face_count": count,
                "message": "检测到多张人脸，请单独拍摄"}
    # 安全加固：解密人脸特征向量
    try:
        decrypted_json = decrypt_face_embedding(user.face_embedding)
        ref = np.array(json.loads(decrypted_json), dtype=np.float32)
    except Exception:
        # 兼容旧数据：尝试直接解析（未加密的旧格式）
        try:
            ref = np.array(json.loads(user.face_embedding), dtype=np.float32)
        except Exception:
            return {"status": "mismatch", "match": False, "score": None,
                    "has_face": True, "face_count": 1,
                    "message": "人脸数据解密失败，请重新采集人脸底图"}
    sim = float(np.dot(ref, emb_b) /
                (np.linalg.norm(ref) * np.linalg.norm(emb_b) + 1e-8))
    match = sim >= FACE_MATCH_THRESHOLD
    return {
        "status": "match" if match else "mismatch",
        "match": match,
        "score": round(sim, 4),
        "has_face": True,
        "face_count": 1,
        "message": "人脸校验通过 ✅" if match else f"人脸比对不通过（相似度 {sim:.2f}）",
    }


def is_available():
    """供健康检查/降级提示使用。"""
    if _available is None:
        return _get_analyzer() is not None
    return _available
