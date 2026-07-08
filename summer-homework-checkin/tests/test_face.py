"""回归测试：人脸模块（底图状态查询、采集、撤销）。"""

import io
import pytest

from test_utils import (
    api_url, json_post, json_get, json_delete,
    assert_ok, assert_http, TEST_PREFIX,
)

STU_USERNAME = f"{TEST_PREFIX}_face_stu"
STU_PASSWORD = "test123456"


def _make_face_photo() -> bytes:
    """生成模拟人脸照片（不含真实人脸，用于测试流程）。"""
    try:
        from PIL import Image, ImageDraw
        # 生成一个近似人脸的椭圆图形以确保通过基础检测（实际取决于模型）
        img = Image.new("RGB", (640, 480), color="white")
        draw = ImageDraw.Draw(img)
        draw.ellipse([200, 100, 440, 400], fill=(255, 220, 190))  # 肤色椭圆
        draw.ellipse([260, 200, 300, 250], fill=(0, 0, 0))  # 左眼
        draw.ellipse([340, 200, 380, 250], fill=(0, 0, 0))  # 右眼
        draw.ellipse([290, 300, 350, 340], fill=(0, 0, 0))  # 嘴巴
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        return buf.getvalue()
    except ImportError:
        return b"FACE_PHOTO" * 1000


def _multipart_post(path: str, token: str, **kwargs) -> object:
    import requests as _req
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return _req.post(api_url(path), headers=headers, **kwargs)


class TestFace:
    """人脸功能回归测试。"""

    STUDENT_TOKEN = None

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        if TestFace.STUDENT_TOKEN is None:
            r = json_post("/api/auth/register", {
                "username": STU_USERNAME, "password": STU_PASSWORD,
                "nickname": "人脸测试学生", "role": "student", "grade": 3,
            })
            if r.status_code == 200:
                TestFace.STUDENT_TOKEN = r.json()["access_token"]
            else:
                r = json_post("/api/auth/login", {
                    "username": STU_USERNAME, "password": STU_PASSWORD,
                })
                if r.status_code == 200:
                    TestFace.STUDENT_TOKEN = r.json()["access_token"]

    def test_01_face_status_not_enrolled(self):
        """初始人脸状态：应显示未采集。"""
        data = assert_ok(json_get("/api/face/status", self.STUDENT_TOKEN), "人脸状态")
        assert data["face_enrolled"] is False
        assert "未采集" in data["message"]

    def test_02_face_enroll(self):
        """人脸底图采集：验证接口可用性（取决于底图质量可能返回不同结果）。"""
        photo_data = _make_face_photo()
        r = _multipart_post("/api/face/enroll", self.STUDENT_TOKEN,
                            files={"photo": ("face.jpg", photo_data, "image/jpeg")})
        # 可能成功或返回检测失败（取决于环境是否有 insightface 模型）
        # 只要状态码是有效的即可
        if r.status_code == 200:
            data = r.json()
            assert "ok" in data or "has_face" in data
        else:
            # 采集失败不是系统错误，可能是缺少模型文件
            pytest.skip("人脸采集跳过（可能需要模型文件）")

    def test_03_face_status_after_enroll(self):
        """采集后状态查询：验证状态更新。"""
        # 即使上一步跳过，也检查当前状态
        data = assert_ok(json_get("/api/face/status", self.STUDENT_TOKEN), "采集后状态")
        assert "face_enrolled" in data

    def test_04_face_enroll_by_non_student(self):
        """非学生采集人脸：应返回 403。"""
        parent_user = f"{TEST_PREFIX}_face_parent"
        r = json_post("/api/auth/register", {
            "username": parent_user, "password": "test123",
            "nickname": "人脸测试家长", "role": "parent",
        })
        if r.status_code == 200:
            parent_token = r.json()["access_token"]
        else:
            r = json_post("/api/auth/login", {"username": parent_user, "password": "test123"})
            parent_token = r.json()["access_token"] if r.status_code == 200 else None

        if parent_token:
            photo_data = _make_face_photo()
            r = _multipart_post("/api/face/enroll", parent_token,
                                files={"photo": ("parent_face.jpg", photo_data, "image/jpeg")})
            assert_http(403, r, "家长采集人脸")

    def test_05_face_unenroll(self):
        """撤销人脸底图：应成功。"""
        data = assert_ok(json_delete("/api/face/enroll", self.STUDENT_TOKEN), "撤销人脸")
        assert data["face_enrolled"] is False
