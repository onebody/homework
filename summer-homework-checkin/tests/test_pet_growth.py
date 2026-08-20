"""宠物成长系统单元测试。

覆盖场景：
1. calc_stage() 阈值边界判定
2. 正常打卡 → 宠物 +5 XP
3. 补卡 → 宠物 +2 XP
4. 无宠物时返回 None（优雅降级）
5. XP 累积触发阶段升级
6. 升级时发送通知
7. User 冗余字段同步更新
8. 喂养流水正确记录
9. 打卡审核 → 宠物成长完整链路集成测试
"""
import os
import sys
import unittest
from datetime import date
from unittest.mock import patch

# 确保能导入 app 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, CheckIn, PetSpecies, PetAdoption, PetFeedLog, Notification
from app.services.pet_service import calc_stage, on_checkin_approved, get_active_pet
from app.config import PET_CHECKIN_XP_NORMAL, PET_CHECKIN_XP_MAKEUP, PET_STAGE_THRESHOLDS


class PetTestBase(unittest.TestCase):
    """测试基类：内存数据库 + 表结构创建。"""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        # 启用 WAL 模式（内存数据库无实际效果，保持与生产一致）
        @event.listens_for(self.engine, "connect")
        def _set_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        self._seed_species()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _seed_species(self):
        """插入默认宠物种类。"""
        species = PetSpecies(
            name="学习猫", description="测试用",
            emoji_baby="🐱", emoji_youth="😺", emoji_adult="😸", emoji_legend="🦁",
        )
        self.db.add(species)
        self.db.commit()
        self.species_id = species.id

    def _make_student(self, username="student1"):
        """创建学生用户。"""
        user = User(username=username, password_hash="x", password_salt="s",
                    role="student", nickname="测试学生")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _make_pet(self, user_id, nickname="小橘", xp=0, stage="baby"):
        """创建宠物领养记录。"""
        pet = PetAdoption(
            user_id=user_id, species_id=self.species_id,
            nickname=nickname, current_xp=xp, current_stage=stage,
            is_active=True,
        )
        self.db.add(pet)
        self.db.commit()
        self.db.refresh(pet)
        # 同步 User 冗余字段
        user = self.db.get(User, user_id)
        user.pet_id = pet.id
        user.pet_level = stage
        user.pet_xp = xp
        self.db.commit()
        return pet

    def _make_checkin(self, user_id, check_type="normal"):
        """创建一条打卡记录（模拟已提交待审核）。"""
        ci = CheckIn(
            user_id=user_id, check_date=date.today(),
            photo_path=f"{user_id}/test.jpg",
            check_type=check_type,
            review_status="pending", is_effective=False,
        )
        self.db.add(ci)
        self.db.commit()
        self.db.refresh(ci)
        return ci


class TestCalcStage(PetTestBase):
    """测试 calc_stage() 阶段判定逻辑。"""

    def test_baby_at_zero(self):
        self.assertEqual(calc_stage(0), "baby")

    def test_baby_at_49(self):
        self.assertEqual(calc_stage(49), "baby")

    def test_youth_at_50(self):
        self.assertEqual(calc_stage(50), "youth")

    def test_youth_at_149(self):
        self.assertEqual(calc_stage(149), "youth")

    def test_adult_at_150(self):
        self.assertEqual(calc_stage(150), "adult")

    def test_adult_at_299(self):
        self.assertEqual(calc_stage(299), "adult")

    def test_legend_at_300(self):
        self.assertEqual(calc_stage(300), "legend")

    def test_legend_at_large_number(self):
        self.assertEqual(calc_stage(99999), "legend")

    def test_negative_xp_returns_baby(self):
        """负数 XP 应回退到 baby。"""
        self.assertEqual(calc_stage(-1), "baby")


class TestOnCheckinApproved(PetTestBase):
    """测试 on_checkin_approved() 打卡触发宠物成长。"""

    def test_normal_checkin_grants_xp(self):
        """正常打卡应增加 PET_CHECKIN_XP_NORMAL 点经验。"""
        user = self._make_student()
        pet = self._make_pet(user.id, xp=0)
        ci = self._make_checkin(user.id, "normal")

        result = on_checkin_approved(self.db, user, ci)
        self.db.commit()  # 服务不自行 commit，测试手动提交

        self.assertIsNotNone(result)
        self.assertEqual(result["xp_gained"], PET_CHECKIN_XP_NORMAL)
        self.assertFalse(result["stage_changed"])

        # 验证宠物 XP 已更新
        self.db.refresh(pet)
        self.assertEqual(pet.current_xp, PET_CHECKIN_XP_NORMAL)

        # 验证 User 冗余字段已同步
        self.db.refresh(user)
        self.assertEqual(user.pet_xp, PET_CHECKIN_XP_NORMAL)

    def test_makeup_checkin_grants_less_xp(self):
        """补卡应增加 PET_CHECKIN_XP_MAKEUP 点经验（少于正常打卡）。"""
        user = self._make_student()
        pet = self._make_pet(user.id, xp=10)
        ci = self._make_checkin(user.id, "makeup")

        result = on_checkin_approved(self.db, user, ci)
        self.db.commit()  # 服务不自行 commit，测试手动提交

        self.assertEqual(result["xp_gained"], PET_CHECKIN_XP_MAKEUP)
        self.assertLess(result["xp_gained"], PET_CHECKIN_XP_NORMAL)

        self.db.refresh(pet)
        self.assertEqual(pet.current_xp, 10 + PET_CHECKIN_XP_MAKEUP)

    def test_no_pet_returns_none(self):
        """用户无活跃宠物时应返回 None，不影响打卡流程。"""
        user = self._make_student()
        ci = self._make_checkin(user.id, "normal")

        result = on_checkin_approved(self.db, user, ci)
        self.assertIsNone(result)

    def test_stage_upgrade_triggered(self):
        """XP 累积超过阈值时应触发阶段升级。"""
        user = self._make_student()
        # 设置宠物 XP 刚好差 1 点升级
        threshold = PET_STAGE_THRESHOLDS["youth"]
        pet = self._make_pet(user.id, xp=threshold - 1, stage="baby")
        ci = self._make_checkin(user.id, "normal")

        result = on_checkin_approved(self.db, user, ci)

        self.assertTrue(result["stage_changed"])
        self.assertEqual(result["old_stage"], "baby")
        self.assertEqual(result["new_stage"], "youth")

        # 验证宠物阶段已更新
        self.db.refresh(pet)
        self.assertEqual(pet.current_stage, "youth")

        # 验证 User 冗余字段
        self.db.refresh(user)
        self.assertEqual(user.pet_level, "youth")

    def test_feed_log_created(self):
        """每次成长都应写入喂养流水。"""
        user = self._make_student()
        pet = self._make_pet(user.id, xp=0)
        ci = self._make_checkin(user.id, "normal")

        before_count = self.db.query(PetFeedLog).count()
        on_checkin_approved(self.db, user, ci)
        self.db.commit()
        after_count = self.db.query(PetFeedLog).count()

        self.assertEqual(after_count, before_count + 1)

        # 验证流水内容
        log = self.db.query(PetFeedLog).order_by(PetFeedLog.id.desc()).first()
        self.assertEqual(log.feed_type, "checkin")
        self.assertEqual(log.xp_gained, PET_CHECKIN_XP_NORMAL)
        self.assertEqual(log.total_xp_after, PET_CHECKIN_XP_NORMAL)
        self.assertEqual(log.trigger_checkin_id, ci.id)
        self.assertEqual(log.stage_before, "baby")
        self.assertEqual(log.stage_after, "baby")  # 未升级

    def test_feed_log_records_stage_change(self):
        """升级时流水应记录阶段变化。"""
        user = self._make_student()
        threshold = PET_STAGE_THRESHOLDS["youth"]
        pet = self._make_pet(user.id, xp=threshold - 1, stage="baby")
        ci = self._make_checkin(user.id, "normal")

        on_checkin_approved(self.db, user, ci)
        self.db.commit()

        log = self.db.query(PetFeedLog).order_by(PetFeedLog.id.desc()).first()
        self.assertEqual(log.stage_before, "baby")
        self.assertEqual(log.stage_after, "youth")

    def test_notification_on_stage_up(self):
        """阶段升级时应创建通知记录。"""
        user = self._make_student()
        threshold = PET_STAGE_THRESHOLDS["youth"]
        pet = self._make_pet(user.id, xp=threshold - 1, stage="baby")
        ci = self._make_checkin(user.id, "normal")

        before_count = self.db.query(Notification).count()
        on_checkin_approved(self.db, user, ci)
        self.db.commit()
        after_count = self.db.query(Notification).count()

        # 升级时应新增 1 条通知
        self.assertEqual(after_count, before_count + 1)

        n = self.db.query(Notification).order_by(Notification.id.desc()).first()
        self.assertIn("升级", n.title)
        self.assertEqual(n.type, "system")

    def test_no_notification_without_upgrade(self):
        """未升级时不应创建通知。"""
        user = self._make_student()
        pet = self._make_pet(user.id, xp=0, stage="baby")
        ci = self._make_checkin(user.id, "normal")

        before_count = self.db.query(Notification).count()
        on_checkin_approved(self.db, user, ci)
        self.db.commit()
        after_count = self.db.query(Notification).count()

        self.assertEqual(after_count, before_count)

    def test_legend_stage_special_notification(self):
        """达到传奇形态时应发送特殊通知。"""
        user = self._make_student()
        threshold = PET_STAGE_THRESHOLDS["legend"]
        pet = self._make_pet(user.id, xp=threshold - 1, stage="adult")
        ci = self._make_checkin(user.id, "normal")

        on_checkin_approved(self.db, user, ci)
        self.db.commit()

        n = self.db.query(Notification).order_by(Notification.id.desc()).first()
        self.assertIn("传奇", n.title)

    def test_multiple_checkins_accumulate(self):
        """多次打卡应正确累积 XP。"""
        user = self._make_student()
        pet = self._make_pet(user.id, xp=0)

        total_xp = 0
        for i in range(5):
            ci = self._make_checkin(user.id, "normal")
            result = on_checkin_approved(self.db, user, ci)
            self.db.commit()
            total_xp += PET_CHECKIN_XP_NORMAL

        self.db.refresh(pet)
        self.assertEqual(pet.current_xp, total_xp)
        self.assertEqual(pet.current_xp, 5 * PET_CHECKIN_XP_NORMAL)

    def test_xp_does_not_decrease(self):
        """XP 不应减少。"""
        user = self._make_student()
        pet = self._make_pet(user.id, xp=100)
        ci = self._make_checkin(user.id, "normal")

        on_checkin_approved(self.db, user, ci)
        self.db.refresh(pet)

        self.assertGreater(pet.current_xp, 100)


class TestFullCheckinChain(PetTestBase):
    """集成测试：模拟 approve_checkin 的完整调用链路。"""

    def test_approve_checkin_with_pet_growth(self):
        """模拟 approve_checkin 中调用宠物成长的完整流程。"""
        user = self._make_student()
        user.points = 0
        self.db.commit()

        pet = self._make_pet(user.id, xp=0)
        ci = self._make_checkin(user.id, "normal")

        # 模拟 approve_checkin 的关键步骤
        gained = 10  # CHECKIN_POINTS
        ci.review_status = "approved"
        ci.is_effective = True
        self.db.commit()

        user.points = (user.points or 0) + gained
        self.db.commit()

        # 调用宠物成长
        pet_result = on_checkin_approved(self.db, user, ci)
        self.db.commit()

        # 验证积分和宠物都正确更新
        self.db.refresh(user)
        self.assertEqual(user.points, gained)
        self.assertEqual(user.pet_xp, PET_CHECKIN_XP_NORMAL)

        self.db.refresh(pet)
        self.assertEqual(pet.current_xp, PET_CHECKIN_XP_NORMAL)

        # 验证流水
        logs = self.db.query(PetFeedLog).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].feed_type, "checkin")
        self.assertEqual(logs[0].xp_gained, PET_CHECKIN_XP_NORMAL)

    def test_approve_checkin_without_pet_still_works(self):
        """无宠物时 approve_checkin 流程不受影响。"""
        user = self._make_student()
        user.points = 0
        self.db.commit()

        ci = self._make_checkin(user.id, "normal")

        gained = 10
        ci.review_status = "approved"
        ci.is_effective = True
        self.db.commit()

        user.points = (user.points or 0) + gained
        self.db.commit()

        pet_result = on_checkin_approved(self.db, user, ci)
        self.db.commit()

        # 宠物成长返回 None，但积分正常发放
        self.assertIsNone(pet_result)
        self.db.refresh(user)
        self.assertEqual(user.points, gained)


class TestGetActivePet(PetTestBase):
    """测试 get_active_pet() 查询。"""

    def test_returns_active_pet(self):
        user = self._make_student()
        pet = self._make_pet(user.id)

        result = get_active_pet(self.db, user.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, pet.id)

    def test_returns_none_when_no_pet(self):
        user = self._make_student()
        result = get_active_pet(self.db, user.id)
        self.assertIsNone(result)

    def test_returns_none_when_abandoned(self):
        user = self._make_student()
        pet = self._make_pet(user.id)
        pet.is_active = False
        self.db.commit()

        result = get_active_pet(self.db, user.id)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
