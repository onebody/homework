"""回归测试：报表模块（学生报表、HTML 报表、家长查看孩子报表）。"""

import pytest

from test_utils import (
    api_url, json_post, json_get,
    assert_ok, assert_http, TEST_PREFIX,
)

STU_USERNAME = f"{TEST_PREFIX}_rpt_stu"
STU_PASSWORD = "test123456"
PAR_USERNAME = f"{TEST_PREFIX}_rpt_par"
PAR_PASSWORD = "par123456"

STUDENT_ID = None
STUDENT_TOKEN = None
PARENT_TOKEN = None
BIND_CODE = None


def _setup():
    """创建测试学生、家长并绑定。"""
    global STUDENT_TOKEN, STUDENT_ID, PARENT_TOKEN, BIND_CODE

    # 学生
    r = json_post("/api/auth/register", {
        "username": STU_USERNAME, "password": STU_PASSWORD,
        "nickname": "报表测试学生", "role": "student", "grade": 3,
    })
    if r.status_code == 200:
        STUDENT_TOKEN = r.json()["access_token"]
        STUDENT_ID = r.json()["user"]["id"]
        BIND_CODE = r.json()["user"]["bind_code"]
    else:
        r = json_post("/api/auth/login", {"username": STU_USERNAME, "password": STU_PASSWORD})
        if r.status_code == 200:
            STUDENT_TOKEN = r.json()["access_token"]
            STUDENT_ID = r.json()["user"]["id"]
            me = assert_ok(json_get("/api/auth/me", STUDENT_TOKEN))
            BIND_CODE = me.get("bind_code")

    # 家长
    r = json_post("/api/auth/register", {
        "username": PAR_USERNAME, "password": PAR_PASSWORD,
        "nickname": "报表测试家长", "role": "parent",
    })
    if r.status_code == 200:
        PARENT_TOKEN = r.json()["access_token"]
    else:
        r = json_post("/api/auth/login", {"username": PAR_USERNAME, "password": PAR_PASSWORD})
        if r.status_code == 200:
            PARENT_TOKEN = r.json()["access_token"]

    # 绑定
    if BIND_CODE:
        json_post("/api/parent/bind", {
            "child_username": STU_USERNAME, "bind_code": BIND_CODE,
        }, PARENT_TOKEN)


class TestReport:
    """报表功能回归测试。"""

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        _setup()

    def test_01_my_report(self):
        """学生个人报表：应返回完整统计数据。"""
        data = assert_ok(json_get("/api/report/me", STUDENT_TOKEN), "个人报表")
        assert data["student_id"] == STUDENT_ID
        assert data["nickname"] == "报表测试学生"
        assert "total_days" in data
        assert "checked_days" in data
        assert "completion_rate" in data
        assert "current_streak" in data
        assert "longest_streak" in data
        assert "weekly_buckets" in data

    def test_02_my_report_html(self):
        """学生 HTML 报表：应返回 HTML 内容。"""
        import requests as _req
        headers = {"Authorization": f"Bearer {STUDENT_TOKEN}"}
        r = _req.get(api_url("/api/report/me/html"), headers=headers)
        assert r.status_code == 200, f"HTML报表 HTTP {r.status_code}"
        content_type = r.headers.get("content-type", "")
        assert "html" in content_type.lower()

    def test_03_report_by_non_student(self):
        """非学生访问报表：应返回 403。"""
        r = json_get("/api/report/me", PARENT_TOKEN)
        assert_http(403, r, "非学生报表")

    def test_04_parent_child_report(self):
        """家长查看孩子报表：应返回孩子数据。"""
        data = assert_ok(json_get(f"/api/parent/child-report/{STUDENT_ID}", PARENT_TOKEN), "孩子报表")
        assert data["student_id"] == STUDENT_ID
        assert "total_days" in data
        assert "completion_rate" in data

    def test_05_parent_child_report_html(self):
        """家长查看孩子 HTML 报表：应返回 HTML。"""
        import requests as _req
        headers = {"Authorization": f"Bearer {PARENT_TOKEN}"}
        r = _req.get(api_url(f"/api/parent/child-report/{STUDENT_ID}/html"), headers=headers)
        assert r.status_code == 200, f"孩子HTML报表 HTTP {r.status_code}"
        content_type = r.headers.get("content-type", "")
        assert "html" in content_type.lower()
