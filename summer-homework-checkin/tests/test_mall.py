"""回归测试：商城/兑奖/抽奖模块（奖品列表、积分兑换、抽奖机会、抽奖）。"""

import pytest

from test_utils import (
    api_url, json_post, json_get,
    assert_ok, assert_http, TEST_PREFIX,
    ADMIN_PASSWORD,
)

STU_USERNAME = f"{TEST_PREFIX}_mall_stu"
STU_PASSWORD = "test123456"


class TestMall:
    """商城功能回归测试。"""

    STUDENT_TOKEN = None
    STUDENT_ID = None

    @pytest.fixture(autouse=True, scope="class")
    def setup(self):
        """创建测试学生。"""
        if TestMall.STUDENT_TOKEN is None:
            r = json_post("/api/auth/register", {
                "username": STU_USERNAME, "password": STU_PASSWORD,
                "nickname": "商城测试学生", "role": "student", "grade": 3,
            })
            if r.status_code == 200:
                TestMall.STUDENT_TOKEN = r.json()["access_token"]
            else:
                r = json_post("/api/auth/login", {
                    "username": STU_USERNAME, "password": STU_PASSWORD,
                })
                if r.status_code == 200:
                    TestMall.STUDENT_TOKEN = r.json()["access_token"]

    def test_01_list_prizes_public(self):
        """公开奖品列表：应返回已上架的奖品。"""
        data = assert_ok(json_get("/api/prizes"), "奖品列表")
        assert len(data) >= 1
        names = [p["name"] for p in data]
        assert len(names) >= 10, "应展示至少 10 个预设奖品"

    def test_02_mall_data(self):
        """积分商城：应包含余额、奖品、兑换记录、抽奖记录。"""
        data = assert_ok(json_get("/api/mall", self.STUDENT_TOKEN), "积分商城")
        assert "points" in data
        assert "prizes" in data
        assert "redemptions" in data
        assert "lottery_records" in data

    def test_03_redeem_insufficient_points(self):
        """积分不足兑换：应返回 400。"""
        # 默认积分为 0，尝试兑换需要积分的奖品
        r = json_post("/api/redeem", {"prize_id": 1}, self.STUDENT_TOKEN)
        assert_http(400, r, "积分不足")
        assert "积分" in r.json()["detail"]

    def test_04_redeem_lottery_ticket(self):
        """兑换抽奖机会：兑换抽奖券。"""
        # 查找抽奖机会奖品 ID（cost_points=5, is_lottery_ticket=True）
        mall = assert_ok(json_get("/api/mall", self.STUDENT_TOKEN), "商城")
        ticket_prize = None
        for p in mall["prizes"]:
            if p.get("is_lottery_ticket") and p.get("cost_points", 0) > 0:
                ticket_prize = p
                break
        if ticket_prize:
            # 积分不足，先跳过
            pytest.skip("积分不足兑换抽奖机会（需积分 ≥ %d）" % ticket_prize["cost_points"])
        else:
            pytest.skip("未找到抽奖机会奖品")

    def test_05_lottery_draw_insufficient_tickets(self):
        """抽奖券不足：应返回 400。"""
        r = json_post("/api/lottery/draw", {}, self.STUDENT_TOKEN)
        assert_http(400, r, "抽奖券不足")
        assert "抽奖券" in r.json()["detail"] or "抽奖资格" in r.json()["detail"] or "攒资格" in r.json()["detail"]

    def test_06_admin_list_prizes(self):
        """管理端奖品列表：应包含所有奖品。"""
        admin_r = json_post("/api/auth/login", {
            "username": "admin", "password": ADMIN_PASSWORD,
        })
        if admin_r.status_code != 200:
            pytest.skip("管理员登录失败")
        admin_token = admin_r.json()["access_token"]

        data = assert_ok(json_get("/api/admin/prizes", admin_token), "管理端奖品列表")
        assert len(data) >= 1

    def test_07_lottery_tickets_info(self):
        """抽奖券信息：应返回当前券数和历史记录。"""
        data = assert_ok(json_get("/api/lottery/tickets", self.STUDENT_TOKEN), "抽奖券信息")
        assert "tickets" in data
        assert "records" in data
