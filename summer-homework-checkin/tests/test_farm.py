"""成长农场模块单元测试。

覆盖场景：
1. 开通农场：默认名/自定义名 + 历史打卡能量回填 + backfilled 守卫
2. 重复开通拒绝（400）
3. 实时联动：任务审核 +10 / 打卡审核 +5；无农场静默跳过
4. 种植：能量不足/模板外素材/地块上限拦截；正常扣能量
5. 收获：未成熟/重复收获拦截；成熟收获回能
6. 浇树：能量不足拦截；阶段提升；育满 1500 森林 +1 归零；地块扩容
7. 改名：空名/超长拦截
8. 模板切换：停用模板不可选
"""
import json
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    User, CheckIn, Farm, FarmPlot, FarmTemplate, FarmEnergyLog,
)
from app.services import farm_service as fs


class FarmTestBase(unittest.TestCase):
    """测试基类：内存数据库 + 农场模板种子。"""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        self._seed_templates()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def _seed_templates(self):
        self.tpl = FarmTemplate(
            key="pastoral", name="田园风", description="测试",
            style_class="tpl-pastoral", tree_emoji="🌳",
            crop_items=json.dumps([{"key": "carrot", "name": "胡萝卜", "emoji": "🥕"}]),
            animal_items=json.dumps([{"key": "chick", "name": "小鸡", "emoji": "🐔"}]),
            status="on", sort_order=1,
        )
        self.tpl2 = FarmTemplate(
            key="scifi", name="科幻风", description="测试2",
            style_class="tpl-scifi", tree_emoji="🌌",
            crop_items=json.dumps([{"key": "starfruit", "name": "星光果", "emoji": "⭐"}]),
            animal_items=json.dumps([{"key": "robotpet", "name": "机器宠", "emoji": "🤖"}]),
            status="on", sort_order=2,
        )
        self.db.add_all([self.tpl, self.tpl2])
        self.db.commit()

    def _make_student(self, username="stu1"):
        u = User(username=username, password_hash="x", password_salt="s",
                 role="student", nickname="测试学生")
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _add_approved_checkins(self, user, n):
        today = date.today()
        for i in range(n):
            self.db.add(CheckIn(
                user_id=user.id, check_date=today - timedelta(days=i),
                photo_path="t.jpg", review_status="approved", is_effective=True,
            ))
        self.db.commit()

    def _open_farm(self, user, energy=0):
        """开通农场并直接充值能量（跳过种植/浇树的能量门槛）。"""
        farm = fs.init_farm(self.db, user, None, "pastoral")
        if energy:
            farm.energy_balance = energy
            farm.total_energy_earned = (farm.total_energy_earned or 0) + energy
            self.db.commit()
            self.db.refresh(farm)
        return farm


class TestFarmInit(FarmTestBase):
    def test_init_backfill_and_guard(self):
        u = self._make_student()
        self._add_approved_checkins(u, 2)
        # 无农场时实时钩子静默跳过
        self.assertIsNone(fs.on_checkin_approved(self.db, u.id, 999))

        farm = fs.init_farm(self.db, u, "梦想田园", "pastoral")
        self.assertEqual(farm.name, "梦想田园")
        self.assertEqual(farm.energy_balance, 2 * fs.ENERGY_PER_CHECKIN)
        self.assertTrue(farm.backfilled)
        # 回填流水存在
        logs = self.db.query(FarmEnergyLog).filter_by(user_id=u.id, source="backfill").all()
        self.assertEqual(len(logs), 1)

        # 重复开通 400
        with self.assertRaises(HTTPException) as cm:
            fs.init_farm(self.db, u, None, None)
        self.assertEqual(cm.exception.status_code, 400)

    def test_init_default_name_and_template(self):
        u = self._make_student("stu2")
        farm = fs.init_farm(self.db, u, None, None)
        self.assertEqual(farm.name, fs.DEFAULT_FARM_NAME)
        self.assertEqual(farm.template_id, self.tpl.id)  # 默认取排序第一
        self.assertEqual(farm.energy_balance, 0)

    def test_init_invalid_template(self):
        u = self._make_student("stu3")
        with self.assertRaises(HTTPException):
            fs.init_farm(self.db, u, None, "not-exist")

    def test_realtime_hooks(self):
        u = self._make_student("stu4")
        farm = self._open_farm(u)
        self.assertEqual(fs.on_task_approved(self.db, u.id, 1, "任务"), fs.ENERGY_PER_TASK)
        self.assertEqual(fs.on_checkin_approved(self.db, u.id, 2), fs.ENERGY_PER_CHECKIN)
        self.db.refresh(farm)
        self.assertEqual(farm.energy_balance, fs.ENERGY_PER_TASK + fs.ENERGY_PER_CHECKIN)
        sources = {l.source for l in self.db.query(FarmEnergyLog).filter_by(user_id=u.id)}
        self.assertIn("task_approval", sources)
        self.assertIn("checkin_approval", sources)


class TestFarmPlay(FarmTestBase):
    def test_plant_and_harvest_cycle(self):
        u = self._make_student()
        farm = self._open_farm(u, energy=100)

        # 模板外素材 400
        with self.assertRaises(HTTPException) as cm:
            fs.plant(self.db, u, "crop", "starfruit")
        self.assertEqual(cm.exception.status_code, 400)

        plot = fs.plant(self.db, u, "crop", "carrot")
        self.db.refresh(farm)
        self.assertEqual(farm.energy_balance, 100 - fs.CROP_COST)
        self.assertEqual(plot.status, "growing")

        # 未成熟收获 400
        with self.assertRaises(HTTPException) as cm:
            fs.harvest(self.db, u, plot.id)
        self.assertEqual(cm.exception.status_code, 400)

        # 模拟成熟后收获回能
        plot.mature_at = fs.now_local() - timedelta(minutes=1)
        self.db.commit()
        fs.harvest(self.db, u, plot.id)
        self.db.refresh(farm)
        self.assertEqual(farm.energy_balance, 100 - fs.CROP_COST + fs.CROP_REWARD)

        # 重复收获 400
        with self.assertRaises(HTTPException) as cm:
            fs.harvest(self.db, u, plot.id)
        self.assertEqual(cm.exception.status_code, 400)

    def test_plant_energy_and_plot_limits(self):
        u = self._make_student("stu5")
        farm = self._open_farm(u, energy=0)
        # 能量不足 400
        with self.assertRaises(HTTPException) as cm:
            fs.plant(self.db, u, "crop", "carrot")
        self.assertEqual(cm.exception.status_code, 400)

        # 地块上限：基础 4 块
        farm.energy_balance = 1000
        self.db.commit()
        for _ in range(fs.MAX_PLOTS_BASE):
            fs.plant(self.db, u, "crop", "carrot")
        with self.assertRaises(HTTPException) as cm:
            fs.plant(self.db, u, "crop", "carrot")
        self.assertEqual(cm.exception.status_code, 400)

        # 他人地块不可收获（404 防探测）
        u2 = self._make_student("stu6")
        self._open_farm(u2, energy=100)
        plot2 = fs.plant(self.db, u2, "crop", "carrot")
        plot2.mature_at = fs.now_local() - timedelta(minutes=1)
        self.db.commit()
        with self.assertRaises(HTTPException) as cm:
            fs.harvest(self.db, u, plot2.id)
        self.assertEqual(cm.exception.status_code, 404)

    def test_water_tree_stage_and_forest(self):
        u = self._make_student("stu7")
        farm = self._open_farm(u, energy=0)
        with self.assertRaises(HTTPException) as cm:
            fs.water_tree(self.db, u)
        self.assertEqual(cm.exception.status_code, 400)

        # 两次浇树：100 能量 → 阶段 1，地块 +1
        farm.energy_balance = fs.WATER_COST * 2
        self.db.commit()
        fs.water_tree(self.db, u)
        r2 = fs.water_tree(self.db, u)
        self.db.refresh(farm)
        self.assertEqual(farm.tree_energy, 100)
        self.assertEqual(farm.tree_stage, 1)
        self.assertTrue(r2["leveled"])
        self.assertEqual(fs.max_plots(farm), fs.MAX_PLOTS_BASE + 1)

        # 育满大树：累计需 1500 能量（30 次浇水），已浇 2 次，补 28 次；森林 +1，成长树归零
        farm.energy_balance = fs.WATER_COST * 28
        self.db.commit()
        r3 = None
        for _ in range(28):
            r3 = fs.water_tree(self.db, u)
        self.db.refresh(farm)
        self.assertTrue(r3["forest_grown"])
        self.assertEqual(farm.forest_count, 1)
        self.assertEqual(farm.tree_energy, 0)
        self.assertEqual(farm.tree_stage, 0)

    def test_rename_and_switch_template(self):
        u = self._make_student("stu8")
        farm = self._open_farm(u)

        with self.assertRaises(HTTPException):
            fs.rename_farm(self.db, u, "   ")
        with self.assertRaises(HTTPException):
            fs.rename_farm(self.db, u, "名" * 33)
        farm = fs.rename_farm(self.db, u, "星际小菜园")
        self.assertEqual(farm.name, "星际小菜园")

        farm = fs.switch_template(self.db, u, "scifi")
        self.assertEqual(farm.template_id, self.tpl2.id)
        # 停用模板不可选
        self.tpl.status = "off"
        self.db.commit()
        with self.assertRaises(HTTPException) as cm:
            fs.switch_template(self.db, u, "pastoral")
        self.assertEqual(cm.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
