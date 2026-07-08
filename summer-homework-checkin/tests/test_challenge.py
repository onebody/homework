"""回归测试：闯关任务模块（任务列表、任务详情、提交打卡、审核）。"""

import json
import pytest

from test_utils import (
    api_url, json_post, json_get, json_put,
    assert_ok, assert_http, TEST_PREFIX,
    ADMIN_PASSWORD,
)

STU_USERNAME = f"{TEST_PREFIX}_chall_stu"
STU_PASSWORD = "test123456"


def _form_post(path: str, token: str, data: dict) -> object:
    """发送 application/x-www-form-urlencoded POST。"""
    import requests as _req
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return _req.post(api_url(path), data=data, headers=headers)


class TestChallenge:
    """闯关任务回归测试。"""

    STUDENT_TOKEN = None
    ADMIN_TOKEN = None
    TASK_IDS = []
    CHECKIN_IDS = []

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        """创建测试学生 + 管理员登录。"""
        if TestChallenge.STUDENT_TOKEN is None:
            r = json_post("/api/auth/register", {
                "username": STU_USERNAME, "password": STU_PASSWORD,
                "nickname": "闯关测试学生", "role": "student", "grade": 3,
            })
            if r.status_code == 200:
                TestChallenge.STUDENT_TOKEN = r.json()["access_token"]
            else:
                r = json_post("/api/auth/login", {
                    "username": STU_USERNAME, "password": STU_PASSWORD,
                })
                if r.status_code == 200:
                    TestChallenge.STUDENT_TOKEN = r.json()["access_token"]

        if TestChallenge.ADMIN_TOKEN is None:
            r = json_post("/api/auth/login", {
                "username": "admin", "password": ADMIN_PASSWORD,
            })
            if r.status_code == 200:
                TestChallenge.ADMIN_TOKEN = r.json()["access_token"]

    def test_01_list_tasks(self):
        """学生端任务列表：应返回已开放的任务。"""
        data = assert_ok(json_get("/api/challenge/tasks", self.STUDENT_TOKEN), "任务列表")
        assert len(data) >= 1
        for t in data:
            assert "id" in t
            assert "name" in t
            assert "status" in t
            assert "user_status" in t
        TestChallenge.TASK_IDS = [t["id"] for t in data if t["status"] == "active"]

    def test_02_task_detail(self):
        """任务详情：应返回完整信息。"""
        if not self.TASK_IDS:
            pytest.skip("无可用任务")
        task_id = self.TASK_IDS[0]
        data = assert_ok(json_get(f"/api/challenge/tasks/{task_id}", self.STUDENT_TOKEN), "任务详情")
        assert data["id"] == task_id
        assert "description" in data
        assert "reward_points" in data
        assert "status" in data
        assert "user_status" in data

    def test_03_submit_checkin(self):
        """提交闯关打卡：应成功。"""
        if not self.TASK_IDS:
            pytest.skip("无可用任务")
        task_id = self.TASK_IDS[0]
        r = _form_post(f"/api/challenge/tasks/{task_id}/checkin", self.STUDENT_TOKEN, {
            "content": json.dumps({"text": "测试闯关打卡内容", "date": "2026-07-08"}, ensure_ascii=False),
        })
        data = assert_ok(r, "提交闯关打卡")
        assert "checkin_id" in data or "id" in data
        cid = data.get("checkin_id") or data.get("id")
        TestChallenge.CHECKIN_IDS.append(cid)

    def test_04_my_checkins(self):
        """我的闯关打卡记录：应包含刚提交的记录。"""
        data = assert_ok(json_get("/api/challenge/my-checkins", self.STUDENT_TOKEN), "我的闯关打卡")
        assert len(data) >= 1
        ids = [c["id"] for c in data]
        for cid in TestChallenge.CHECKIN_IDS:
            assert cid in ids, f"打卡记录 {cid} 应在列表中"

    def test_05_admin_list_tasks(self):
        """管理端任务列表：应包含统计信息。"""
        data = assert_ok(json_get("/api/challenge/admin/tasks", self.ADMIN_TOKEN), "管理端任务列表")
        assert len(data) >= 1
        for t in data:
            assert "total_checkins" in t
            assert "pending_reviews" in t

    def test_06_admin_pending_count(self):
        """管理端待审核闯关打卡数量。"""
        data = assert_ok(json_get("/api/challenge/admin/checkins/pending-count", self.ADMIN_TOKEN), "待审核数")
        assert "count" in data

    def test_07_admin_list_checkins(self):
        """管理端闯关打卡记录列表。"""
        data = assert_ok(json_get("/api/challenge/admin/checkins", self.ADMIN_TOKEN), "闯关打卡列表")
        if len(data) > 0:
            assert "task_id" in data[0]
            assert "review_status" in data[0]

    def test_08_upload_challenge_file(self):
        """上传闯关附件：应返回可访问 URL。"""
        import io
        try:
            from PIL import Image
            img = Image.new("RGB", (200, 200), color="red")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            data = buf.getvalue()
        except ImportError:
            data = b"FAKE_FILE_DATA" * 200

        import requests as _req
        headers = {"Authorization": f"Bearer {self.STUDENT_TOKEN}"}
        r = _req.post(api_url("/api/challenge/upload"), headers=headers,
                      files={"file": ("attachment.jpg", data, "image/jpeg")})
        d = assert_ok(r, "上传附件")
        assert "url" in d
