"""回归测试：认证模块（注册、登录、个人信息、密码修改）。"""

import pytest

from test_utils import (
    API_BASE, api_url, json_post, json_get, json_put,
    assert_ok, assert_http, TEST_PREFIX,
)

# ── 测试数据 ─────────────────────────────────────────────────────────────────
STU_USERNAME = f"{TEST_PREFIX}_auth_stu"
STU_PASSWORD = "test123456"
STU_NICKNAME = "认证测试学生"

PARENT_USERNAME = f"{TEST_PREFIX}_auth_parent"
PARENT_PASSWORD = "parent888"
PARENT_NICKNAME = "认证测试家长"


class TestRegister:
    """注册功能回归测试。"""

    def test_01_register_student(self):
        """学生注册：正常流程。"""
        r = json_post("/api/auth/register", {
            "username": STU_USERNAME, "password": STU_PASSWORD,
            "nickname": STU_NICKNAME, "role": "student", "grade": 3,
        })
        data = assert_ok(r, "学生注册")
        assert "access_token" in data
        assert data["user"]["role"] == "student"
        assert data["user"]["username"] == STU_USERNAME
        assert data["user"]["bind_code"] is not None  # 学生注册后应有绑定码

    def test_02_register_parent(self):
        """家长注册：正常流程。"""
        r = json_post("/api/auth/register", {
            "username": PARENT_USERNAME, "password": PARENT_PASSWORD,
            "nickname": PARENT_NICKNAME, "role": "parent",
        })
        data = assert_ok(r, "家长注册")
        assert data["user"]["role"] == "parent"

    def test_03_register_duplicate_username(self):
        """重复注册：同一用户名应返回 400。"""
        r = json_post("/api/auth/register", {
            "username": STU_USERNAME, "password": STU_PASSWORD,
            "nickname": "另一个学生", "role": "student",
        })
        assert_http(400, r, "重复注册")
        assert "已存在" in r.json()["detail"]

    def test_04_register_invalid_role(self):
        """非法角色注册：应返回 400。"""
        r = json_post("/api/auth/register", {
            "username": f"{TEST_PREFIX}_invalid",
            "password": "test123", "nickname": "无效角色",
            "role": "superadmin",
        })
        assert_http(400, r, "非法角色")
        assert "角色" in r.json()["detail"]


class TestLogin:
    """登录功能回归测试。"""

    @pytest.fixture(autouse=True)
    def ensure_user(self):
        """确保测试用户已存在。"""
        # 尝试登录，失败则不处理（注册测试会创建用户）
        r = json_post("/api/auth/login", {
            "username": STU_USERNAME, "password": STU_PASSWORD,
        })
        if r.status_code == 200:
            self.student_token = r.json()["access_token"]
        else:
            self.student_token = None

    def test_01_login_success(self):
        """正常登录：应返回 token 和用户信息。"""
        r = json_post("/api/auth/login", {
            "username": STU_USERNAME, "password": STU_PASSWORD,
        })
        data = assert_ok(r, "登录")
        assert "access_token" in data
        assert data["user"]["username"] == STU_USERNAME

    def test_02_login_wrong_password(self):
        """错误密码：应返回 401。"""
        r = json_post("/api/auth/login", {
            "username": STU_USERNAME, "password": "wrong_password_xxx",
        })
        assert_http(401, r, "错误密码")

    def test_03_login_nonexistent_user(self):
        """不存在的用户：应返回 401。"""
        r = json_post("/api/auth/login", {
            "username": f"{TEST_PREFIX}_nobody", "password": "test123",
        })
        assert_http(401, r, "不存在的用户")


class TestMe:
    """个人信息查询回归测试。"""

    TOKEN = None

    @pytest.fixture(autouse=True)
    def ensure_login(self):
        if TestMe.TOKEN is None:
            r = json_post("/api/auth/login", {
                "username": STU_USERNAME, "password": STU_PASSWORD,
            })
            if r.status_code == 200:
                TestMe.TOKEN = r.json()["access_token"]

    def test_01_me_success(self):
        """获取个人信息：应返回完整用户数据。"""
        data = assert_ok(json_get("/api/auth/me", self.TOKEN), "个人信息")
        assert data["username"] == STU_USERNAME
        assert data["role"] == "student"
        assert "points" in data
        assert "current_streak" in data
        assert "effective_checkins" in data

    def test_02_me_no_token(self):
        """未提供 token：应返回 401。"""
        r = json_get("/api/auth/me")
        assert_http(401, r, "未认证")

    def test_03_me_invalid_token(self):
        """无效 token：应返回 401。"""
        r = json_get("/api/auth/me", token="invalid_token_xxx")
        assert_http(401, r, "无效令牌")


class TestPasswordChange:
    """密码修改功能回归测试。"""

    TOKEN = None
    NEW_PASSWORD = "newpass999"

    @pytest.fixture(autouse=True)
    def ensure_login(self):
        if TestPasswordChange.TOKEN is None:
            r = json_post("/api/auth/login", {
                "username": STU_USERNAME, "password": STU_PASSWORD,
            })
            if r.status_code == 200:
                TestPasswordChange.TOKEN = r.json()["access_token"]

    def test_01_change_password_success(self):
        """正常修改密码：应成功。"""
        data = assert_ok(json_put("/api/auth/password", {
            "old_password": STU_PASSWORD,
            "new_password": self.NEW_PASSWORD,
        }, self.TOKEN), "修改密码")
        assert data["ok"] is True

    def test_02_login_with_new_password(self):
        """新密码登录：应成功。"""
        r = json_post("/api/auth/login", {
            "username": STU_USERNAME, "password": self.NEW_PASSWORD,
        })
        data = assert_ok(r, "新密码登录")
        # 更新缓存 token
        TestPasswordChange.TOKEN = data["access_token"]

    def test_03_login_with_old_password_fails(self):
        """旧密码登录：应返回 401。"""
        r = json_post("/api/auth/login", {
            "username": STU_USERNAME, "password": STU_PASSWORD,
        })
        assert_http(401, r, "旧密码登录应失败")

    def test_04_change_password_wrong_old(self):
        """错误原密码：应返回 400。"""
        r = json_put("/api/auth/password", {
            "old_password": "wrong_old",
            "new_password": "newpass888",
        }, self.TOKEN)
        assert_http(400, r, "原密码错误")
        assert "原密码" in r.json()["detail"]

    def test_05_change_password_too_short(self):
        """新密码太短：应返回 400。"""
        r = json_put("/api/auth/password", {
            "old_password": self.NEW_PASSWORD,
            "new_password": "ab",
        }, self.TOKEN)
        assert_http(400, r, "新密码太短")

    def test_06_change_password_same_as_old(self):
        """新密码与原密码相同：应能通过（取决于业务规则，允许不修改）。"""
        data = assert_ok(json_put("/api/auth/password", {
            "old_password": self.NEW_PASSWORD,
            "new_password": self.NEW_PASSWORD,
        }, self.TOKEN), "相同密码")
        assert data["ok"] is True

    def test_07_restore_password(self):
        """恢复原密码（保持测试一致性）。"""
        data = assert_ok(json_put("/api/auth/password", {
            "old_password": self.NEW_PASSWORD,
            "new_password": STU_PASSWORD,
        }, self.TOKEN), "恢复密码")
        assert data["ok"] is True
