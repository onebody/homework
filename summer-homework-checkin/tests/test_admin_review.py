"""回归测试：管理端审核模块（统计数据、打卡审核、积分发放、兑换审核）。"""

import io
import pytest

from test_utils import (
    api_url, json_post, json_get, json_put,
    assert_ok, assert_http, TEST_PREFIX,
    ADMIN_PASSWORD,
)
from test_checkin import _make_photo_bytes, requests_post

STU_USERNAME = f"{TEST_PREFIX}_admin_stu"
STU_PASSWORD = "test123456"

# ── 辅助：创建测试学生并打卡 ────────────────────────────────────────────────


def _create_student_and_checkin() -> tuple[str, int]:
    """注册测试学生、打卡，返回 (student_token, checkin_id)。"""
    r = json_post("/api/auth/register", {
        "username": STU_USERNAME, "password": STU_PASSWORD,
        "nickname": "审核测试学生", "role": "student", "grade": 3,
    })
    if r.status_code != 200:
        # 已存在则登录
        r = json_post("/api/auth/login", {
            "username": STU_USERNAME, "password": STU_PASSWORD,
        })
    token = r.json()["access_token"]

    # 打卡
    photo_data = _make_photo_bytes()
    r = requests_post("/api/checkin", token, files={
        "photo": ("review_test.jpg", photo_data, "image/jpeg"),
    }, data={"location_lat": "39.9", "location_lng": "116.4"})
    checkin_id = r.json()["id"]
    return token, checkin_id


class TestAdminReview:
    """管理端审核回归测试。"""

    ADMIN_TOKEN = None
    STU_TOKEN = None
    CHECKIN_ID = None

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        """登录管理员 + 创建测试学生打卡。"""
        if TestAdminReview.ADMIN_TOKEN is None:
            r = json_post("/api/auth/login", {
                "username": "admin", "password": ADMIN_PASSWORD,
            })
            if r.status_code == 200:
                TestAdminReview.ADMIN_TOKEN = r.json()["access_token"]

        if TestAdminReview.STU_TOKEN is None:
            token, cid = _create_student_and_checkin()
            TestAdminReview.STU_TOKEN = token
            TestAdminReview.CHECKIN_ID = cid

    def test_01_admin_stats(self):
        """管理统计：应包含各项统计数据。"""
        data = assert_ok(json_get("/api/admin/stats", self.ADMIN_TOKEN), "管理统计")
        assert "students" in data
        assert "parents" in data
        assert "effective_checkins" in data
        assert "bindings" in data
        assert "summer_window" in data

    def test_02_pending_count(self):
        """待审核数量：应大于 0。"""
        data = assert_ok(json_get("/api/admin/checkins/pending-count", self.ADMIN_TOKEN), "待审核数")
        assert data["count"] > 0

    def test_03_admin_checkins_list(self):
        """打卡列表：应包含测试学生的打卡记录。"""
        data = assert_ok(json_get("/api/admin/checkins", self.ADMIN_TOKEN), "打卡列表")
        ids = [c["id"] for c in data]
        assert self.CHECKIN_ID in ids, "测试打卡应在管理员列表中"

    def test_04_approve_checkin(self):
        """审核通过打卡：积分应发放。"""
        # 先查看学生当前积分
        me = assert_ok(json_get("/api/auth/me", self.STU_TOKEN), "审核前积分")
        points_before = me["points"]

        # 审核通过
        r = json_put(f"/api/admin/checkins/{self.CHECKIN_ID}/review", {
            "status": "approved", "note": "照片清晰，通过测试",
        }, self.ADMIN_TOKEN)
        data = assert_ok(r, "审核通过")
        assert data["review_status"] == "approved"

        # 验证积分增加
        me = assert_ok(json_get("/api/auth/me", self.STU_TOKEN), "审核后积分")
        assert me["points"] > points_before, "审核通过后积分应增加"

    def test_05_effective_checkin_count(self):
        """有效打卡数：审核通过后应增加。"""
        data = assert_ok(json_get("/api/checkin/streak", self.STU_TOKEN), "有效打卡数")
        assert data["effective_checkins"] >= 1

    def test_06_approve_already_reviewed(self):
        """重复审核：应返回 400。"""
        r = json_put(f"/api/admin/checkins/{self.CHECKIN_ID}/review", {
            "status": "rejected", "note": "重复审核测试",
        }, self.ADMIN_TOKEN)
        assert_http(400, r, "重复审核")
        assert "已审核" in r.json()["detail"]

    def test_07_admin_users_list(self):
        """用户列表：应包含各角色用户。"""
        data = assert_ok(json_get("/api/admin/users", self.ADMIN_TOKEN), "用户列表")
        usernames = [u["username"] for u in data]
        assert STU_USERNAME in usernames, "测试学生应在列表"
        assert "admin" in usernames

    def test_08_reject_new_checkin(self):
        """拒绝新打卡：积分不发放。"""
        # 再打一次卡
        photo_data = _make_photo_bytes()
        r = requests_post("/api/checkin", self.STU_TOKEN, files={
            "photo": ("reject_test.jpg", photo_data, "image/jpeg"),
        }, data={"location_lat": "39.9", "location_lng": "116.4"})
        checkin2_id = r.json()["id"]

        me_before = assert_ok(json_get("/api/auth/me", self.STU_TOKEN), "拒绝前积分")
        points_before = me_before["points"]

        # 拒绝
        r = json_put(f"/api/admin/checkins/{checkin2_id}/review", {
            "status": "rejected", "note": "照片模糊",
        }, self.ADMIN_TOKEN)
        assert_ok(r, "拒绝打卡")

        # 积分不变
        me_after = assert_ok(json_get("/api/auth/me", self.STU_TOKEN), "拒绝后积分")
        assert me_after["points"] == points_before, "拒绝后积分不应变化"

    def test_09_history_status_after_review(self):
        """审核后打卡历史状态应正确更新。"""
        data = assert_ok(json_get("/api/checkin/history", self.STU_TOKEN), "审核后历史")
        status_map = {d["id"]: d["review_status"] for d in data}
        assert status_map.get(self.CHECKIN_ID) == "approved"
