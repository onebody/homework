"""回归测试：打卡模块（创建打卡、今日状态、连续天数、历史记录、补卡）。"""

import io
import pytest

from test_utils import (
    api_url, json_post, json_get, assert_ok, assert_http, TEST_PREFIX,
)

STU_USERNAME = f"{TEST_PREFIX}_ck_stu"
STU_PASSWORD = "test123456"


def _make_photo_bytes(size=(800, 600), color='lightblue'):
    """生成测试图片字节（确保体积 > 5KB 且尺寸 > 200px）。"""
    try:
        from PIL import Image
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        # 使用较低压缩率确保文件大于 5KB
        img.save(buf, format="JPEG", quality=95)
        data = buf.getvalue()
        if len(data) < 6 * 1024:
            # 尺寸仍不足时，用更大尺寸重试
            return _make_photo_bytes((size[0] * 2, size[1] * 2), color)
        return data
    except ImportError:
        # 无 Pillow 时生成 >= 6KB 的假图片
        return b"FAKE_PHOTO_DATA" * 500


def _upload_photo(token: str) -> tuple[str, str]:
    """上传一张测试照片，返回 (path, url)。"""
    data = _make_photo_bytes()
    r = requests_post("/api/checkin/upload", token, files={"photo": ("test.jpg", data, "image/jpeg")})
    if r.status_code == 200:
        j = r.json()
        return j.get("photo_path", ""), j.get("photo_url", "")
    return "", ""


# 使用底层 requests 以支持 multipart/form-data
import requests as _requests  # noqa: E402


def requests_post(path: str, token: str, **kwargs) -> _requests.Response:
    """发送 multipart POST（用于文件上传）。"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return _requests.post(api_url(path), headers=headers, **kwargs)


class TestCheckin:
    """打卡功能回归测试。"""

    TOKEN = None
    CHECKIN_IDS = []
    PHOTO_PATH = ""
    PHOTO_URL = ""

    @pytest.fixture(autouse=True, scope="class")
    def ensure_user(self):
        """确保测试学生存在。"""
        if TestCheckin.TOKEN is None:
            # 尝试注册
            r = json_post("/api/auth/register", {
                "username": STU_USERNAME, "password": STU_PASSWORD,
                "nickname": "打卡测试学生", "role": "student", "grade": 3,
            })
            if r.status_code == 200:
                TestCheckin.TOKEN = r.json()["access_token"]

    def test_01_today_status_initial(self):
        """初始今日状态：未打卡、无待审核。"""
        data = assert_ok(json_get("/api/checkin/today", self.TOKEN), "今日状态")
        assert data["today_checked"] is False
        assert data["today_pending"] is False
        assert data["today_count"] == 0
        assert "can_makeup_this_month" in data

    def test_02_upload_photo(self):
        """上传照片：应返回可访问路径。"""
        data = _make_photo_bytes()
        r = requests_post("/api/checkin/upload", self.TOKEN,
                          files={"photo": ("test.jpg", data, "image/jpeg")})
        d = assert_ok(r, "上传照片")
        assert "photo_path" in d
        assert "photo_url" in d
        TestCheckin.PHOTO_PATH = d["photo_path"]
        TestCheckin.PHOTO_URL = d["photo_url"]

    def test_03_checkin_normal(self):
        """正常打卡：应成功并返回打卡记录。"""
        photo_data = _make_photo_bytes()
        r = requests_post("/api/checkin", self.TOKEN, files={
            "photo": ("checkin.jpg", photo_data, "image/jpeg"),
        }, data={
            "location_lat": "39.9", "location_lng": "116.4",
            "check_type": "normal",
        })
        d = assert_ok(r, "正常打卡")
        assert "id" in d
        assert d["review_status"] == "pending"
        assert d["is_effective"] is False  # 新打卡默认待审核，不计为有效
        TestCheckin.CHECKIN_IDS.append(d["id"])

    def test_04_checkin_second_same_day(self):
        """同一天再次打卡：应成功（允许每天多次打卡）。"""
        photo_data = _make_photo_bytes()
        r = requests_post("/api/checkin", self.TOKEN, files={
            "photo": ("checkin2.jpg", photo_data, "image/jpeg"),
        }, data={
            "location_lat": "39.9", "location_lng": "116.4",
            "check_type": "normal",
        })
        d = assert_ok(r, "同天再次打卡")
        TestCheckin.CHECKIN_IDS.append(d["id"])

    def test_05_checkin_by_non_student(self):
        """非学生打卡（家长/管理员）：应返回 403。"""
        # 先注册家长
        parent_user = f"{TEST_PREFIX}_ck_parent"
        r = json_post("/api/auth/register", {
            "username": parent_user, "password": "test123",
            "nickname": "打卡测试家长", "role": "parent",
        })
        if r.status_code == 200:
            parent_token = r.json()["access_token"]
        else:
            # 已存在则登录
            r2 = json_post("/api/auth/login", {
                "username": parent_user, "password": "test123",
            })
            parent_token = r2.json()["access_token"] if r2.status_code == 200 else None

        if parent_token:
            photo_data = _make_photo_bytes()
            r = requests_post("/api/checkin", parent_token, files={
                "photo": ("parent_checkin.jpg", photo_data, "image/jpeg"),
            }, data={"location_lat": "39.9", "location_lng": "116.4"})
            assert_http(403, r, "家长打卡应拒绝")

    def test_06_today_status_after_checkin(self):
        """打卡后今日状态：应有待审核记录。"""
        data = assert_ok(json_get("/api/checkin/today", self.TOKEN), "打卡后状态")
        assert data["today_pending"] is True  # 新打卡默认为待审核
        assert data["today_count"] >= 2

    def test_07_checkin_history(self):
        """打卡历史：应包含刚才的打卡记录。"""
        data = assert_ok(json_get("/api/checkin/history", self.TOKEN), "打卡历史")
        assert len(data) >= 2
        ids = [d["id"] for d in data]
        for cid in TestCheckin.CHECKIN_IDS:
            assert cid in ids, f"打卡记录 {cid} 应在历史中"

    def test_08_checkin_streak(self):
        """连续天数：打卡后 streak 信息应正常。"""
        data = assert_ok(json_get("/api/checkin/streak", self.TOKEN), "连续天数")
        assert "current_streak" in data
        assert "longest_streak" in data
        assert "effective_checkins" in data
        assert "today_checked" in data
        # 因未审核，effective_checkins 应为 0
        assert data["effective_checkins"] == 0

    def test_09_checkin_by_role_student_only(self):
        """仅学生可访问打卡端点确认。"""
        # 管理员登录
        admin_pw = __import__("test_utils").ADMIN_PASSWORD
        r = json_post("/api/auth/login", {
            "username": "admin", "password": admin_pw,
        })
        if r.status_code != 200:
            pytest.skip("管理员登录失败，跳过角色检查")
        admin_token = r.json()["access_token"]

        photo_data = _make_photo_bytes()
        r = requests_post("/api/checkin", admin_token, files={
            "photo": ("admin_checkin.jpg", photo_data, "image/jpeg"),
        }, data={"location_lat": "39.9", "location_lng": "116.4"})
        assert_http(403, r, "管理员打卡应拒绝")
