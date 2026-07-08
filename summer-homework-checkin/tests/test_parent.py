"""回归测试：家长模块（绑定、解绑、孩子列表、代打卡、代操作）。"""

import pytest

from test_utils import (
    api_url, json_post, json_get, json_delete,
    assert_ok, assert_http, TEST_PREFIX,
)
from test_checkin import _make_photo_bytes, requests_post as multipart_post

STU_USERNAME = f"{TEST_PREFIX}_par_stu"
STU_PASSWORD = "stu123456"
PAR_USERNAME = f"{TEST_PREFIX}_par_par"
PAR_PASSWORD = "par123456"

# 保存绑定码
BIND_CODE = None
STUDENT_TOKEN = None
PARENT_TOKEN = None
STUDENT_ID = None


def _setup_users():
    """创建测试学生和家长（幂等，跨测试类共享）。"""
    global STUDENT_TOKEN, PARENT_TOKEN, BIND_CODE, STUDENT_ID

    # 注册学生
    r = json_post("/api/auth/register", {
        "username": STU_USERNAME, "password": STU_PASSWORD,
        "nickname": "家长测试学生", "role": "student", "grade": 3,
    })
    if r.status_code == 200:
        STUDENT_TOKEN = r.json()["access_token"]
        STUDENT_ID = r.json()["user"]["id"]
        BIND_CODE = r.json()["user"]["bind_code"]
    else:
        # 已存在则登录
        r = json_post("/api/auth/login", {
            "username": STU_USERNAME, "password": STU_PASSWORD,
        })
        if r.status_code == 200:
            STUDENT_TOKEN = r.json()["access_token"]
            STUDENT_ID = r.json()["user"]["id"]
            # 获取绑定码
            me = assert_ok(json_get("/api/auth/me", STUDENT_TOKEN))
            BIND_CODE = me.get("bind_code")

    # 注册家长
    r = json_post("/api/auth/register", {
        "username": PAR_USERNAME, "password": PAR_PASSWORD,
        "nickname": "家长测试家长", "role": "parent",
    })
    if r.status_code == 200:
        PARENT_TOKEN = r.json()["access_token"]
    else:
        r = json_post("/api/auth/login", {
            "username": PAR_USERNAME, "password": PAR_PASSWORD,
        })
        if r.status_code == 200:
            PARENT_TOKEN = r.json()["access_token"]


class TestParentBind:
    """家长绑定回归测试。"""

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        _setup_users()

    def test_01_bind_success(self):
        """正常绑定：应成功。"""
        data = assert_ok(json_post("/api/parent/bind", {
            "child_username": STU_USERNAME, "bind_code": BIND_CODE,
        }, PARENT_TOKEN), "绑定")
        assert data["message"] in ("绑定成功", "已绑定")

    def test_02_bind_duplicate(self):
        """重复绑定：应返回"已绑定"。"""
        data = assert_ok(json_post("/api/parent/bind", {
            "child_username": STU_USERNAME, "bind_code": BIND_CODE,
        }, PARENT_TOKEN), "重复绑定")
        assert "已绑定" in data["message"]

    def test_03_bind_wrong_code(self):
        """错误绑定码：应返回 400。"""
        r = json_post("/api/parent/bind", {
            "child_username": STU_USERNAME, "bind_code": "WRONG_CODE",
        }, PARENT_TOKEN)
        assert_http(400, r, "错误绑定码")

    def test_04_bind_nonexistent_user(self):
        """不存在的孩子：应返回 400。"""
        r = json_post("/api/parent/bind", {
            "child_username": f"{TEST_PREFIX}_nonexistent",
            "bind_code": "S00001",
        }, PARENT_TOKEN)
        assert_http(400, r, "不存在的用户")

    def test_05_bind_by_non_parent(self):
        """非家长用户绑定：应返回 403。"""
        r = json_post("/api/parent/bind", {
            "child_username": STU_USERNAME, "bind_code": BIND_CODE,
        }, STUDENT_TOKEN)
        assert r.status_code in (403, 401), f"期望 403/401，实际 {r.status_code}"


class TestParentChildren:
    """家长孩子列表回归测试。"""

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        _setup_users()
        # 确保已绑定
        json_post("/api/parent/bind", {
            "child_username": STU_USERNAME, "bind_code": BIND_CODE,
        }, PARENT_TOKEN)

    def test_01_children_list(self):
        """孩子列表：应包含刚绑定的学生。"""
        data = assert_ok(json_get("/api/parent/children", PARENT_TOKEN), "孩子列表")
        assert len(data) >= 1
        usernames = [c["nickname"] for c in data]
        assert "家长测试学生" in usernames

    def test_02_child_streak(self):
        """孩子连续天数：应返回统计数据。"""
        data = assert_ok(json_get(f"/api/parent/child-streak/{STUDENT_ID}", PARENT_TOKEN), "孩子连续天数")
        assert data["student_id"] == STUDENT_ID
        assert "current_streak" in data
        assert "effective_checkins" in data

    def test_03_child_streak_unauthorized(self):
        """未绑定的孩子连续天数：应返回 403。"""
        r = json_get(f"/api/parent/child-streak/99999", PARENT_TOKEN)
        assert r.status_code in (403, 404), f"期望 403/404，实际 {r.status_code}"


class TestParentCheckin:
    """家长代打卡回归测试。"""

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        _setup_users()

    def test_01_parent_checkin(self):
        """家长代孩子打卡：应成功。"""
        photo_data = _make_photo_bytes()
        r = multipart_post("/api/parent/checkin", PARENT_TOKEN, files={
            "photo": ("par_checkin.jpg", photo_data, "image/jpeg"),
        }, data={
            "child_id": str(STUDENT_ID),
            "location_lat": "39.9", "location_lng": "116.4",
            "check_type": "normal",
        })
        d = assert_ok(r, "家长代打卡")
        assert d["ok"] is True
        assert d["child_id"] == STUDENT_ID
        assert "checkin_id" in d
        assert "打卡已提交" in d["message"]


class TestParentUnbind:
    """家长解绑回归测试。"""

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        _setup_users()

    def test_01_unbind_success(self):
        """正常解绑：应成功。"""
        data = assert_ok(json_delete(f"/api/parent/unbind/{STUDENT_ID}", PARENT_TOKEN), "解绑")
        assert data["message"] == "解绑成功"

    def test_02_children_after_unbind(self):
        """解绑后孩子列表不应包含该学生。"""
        data = assert_ok(json_get("/api/parent/children", PARENT_TOKEN), "解绑后列表")
        ids = [c["student_id"] for c in data]
        assert STUDENT_ID not in ids, "解绑后孩子不应在列表中"

    def test_03_unbind_again_idempotent(self):
        """重复解绑：应幂等返回"已解绑"。"""
        data = assert_ok(json_delete(f"/api/parent/unbind/{STUDENT_ID}", PARENT_TOKEN), "重复解绑")
        assert "已解绑" in data["message"]

    def test_04_rebind_after_unbind(self):
        """重新绑定：应成功。"""
        data = assert_ok(json_post("/api/parent/bind", {
            "child_username": STU_USERNAME, "bind_code": BIND_CODE,
        }, PARENT_TOKEN), "重新绑定")
        assert data["message"] == "绑定成功"
