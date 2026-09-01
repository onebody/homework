"""学习成长计划模块单元测试。

覆盖场景（沿用 test_pet_growth.py 的 unittest + 内存 SQLite 范式）：
1. computed_status 四态边界（todo/doing/done/overdue 查询时计算）
2. 模板可见性：年级/班级隔离
3. instantiate_plan 幂等 + 任务复制回链
4. submit_task：重复提交 400 / 空内容 400 / auto 模式即过
5. approve_submission 联动：积分 + 宠物 XP（feed_type=task）+ 通知 + 勋章
6. 并发重复审核：部分唯一索引兜底，恰 1 条 approved、积分只发一次
7. reject_submission 驳回与重提
8. recompute_study_streak 连续天数
9. 勋章授予幂等
10. 模式切换不影响暑期打卡数据
"""
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from unittest.mock import patch

# 确保能导入 app 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    CheckIn, ClassGroup, LearningConfig, LearningPlan, LearningTask,
    Notification, PetAdoption, PetFeedLog, PetSpecies, ProgressRecord,
    Semester, StudentParent, Subject, TaskSubmission, User, UserBadge,
)
from app.services import learning_service as ls
from app.utils.timeutil import now_local


class LearningTestBase(unittest.TestCase):
    """测试基类：内存数据库 + 全表创建（与 migrate.py 首部署 create_all 一致）。"""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def _set_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        self._seed_base()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    # ---------- 造数辅助 ----------

    def _seed_base(self):
        """预设学科 + 学期 + 全局配置（对齐 seed.py 结构）。"""
        self.subjects = {}
        for name, emoji in (("语文", "📖"), ("数学", "🔢"), ("英语", "🔤")):
            s = Subject(name=name, emoji=emoji, grade_min=1, grade_max=6,
                        sort_order=len(self.subjects) + 1, status="on", is_preset=True)
            self.db.add(s)
            self.subjects[name] = s
        sem = Semester(name="2026秋季学期", type="semester",
                       start_date=date(2026, 9, 1), end_date=date(2027, 1, 31),
                       status="active")
        self.db.add(sem)
        self.db.add(LearningConfig(mode="semester", review_mode="admin",
                                   current_semester_id=None))
        self.db.commit()
        self.semester = sem

    def _make_user(self, username, role="student", grade=3, class_id=None, nickname=None):
        u = User(username=username, password_hash="x", password_salt="s",
                 role=role, nickname=nickname or username,
                 grade=grade, class_id=class_id)
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _make_template(self, name="每周成长计划", grade=None, class_id=None,
                       semester_id=None, status="published", tasks=2):
        t = LearningPlan(plan_type="template", name=name, semester_id=semester_id,
                         grade=grade, class_id=class_id, period_type="week",
                         status=status, created_by=None)
        self.db.add(t)
        self.db.flush()
        for i in range(tasks):
            self.db.add(LearningTask(
                plan_id=t.id, title=f"{name}任务{i + 1}",
                subject_id=self.subjects["语文"].id,
                est_minutes=20, due_date=date.today() + timedelta(days=3 + i),
                reward_points=10, reward_xp=10, sort_order=i + 1,
            ))
        self.db.commit()
        self.db.refresh(t)
        return t

    def _make_pet(self, user, nickname="小橘"):
        sp = self.db.query(PetSpecies).first()
        if not sp:
            sp = PetSpecies(name="学习猫", description="测试",
                            emoji_baby="🐱", emoji_youth="😺",
                            emoji_adult="😸", emoji_legend="🦁")
            self.db.add(sp)
            self.db.commit()
            self.db.refresh(sp)
        pet = PetAdoption(user_id=user.id, species_id=sp.id, nickname=nickname,
                          current_xp=0, current_stage="baby", is_active=True)
        self.db.add(pet)
        self.db.commit()
        self.db.refresh(pet)
        return pet


class TestComputedStatus(LearningTestBase):
    """四态：存库三态 + 逾期查询时计算，绝不写库。"""

    def _task(self, status="todo", due=None):
        return LearningTask(plan_id=1, title="t", status=status, due_date=due)

    def test_todo(self):
        self.assertEqual(ls.computed_status(self._task("todo", date.today())), "todo")

    def test_doing(self):
        self.assertEqual(ls.computed_status(self._task("doing", date.today())), "doing")

    def test_done_wins_over_overdue(self):
        """已完成任务即使过了截止日也必须是 done。"""
        t = self._task("done", date.today() - timedelta(days=3))
        self.assertEqual(ls.computed_status(t), "done")

    def test_overdue(self):
        t = self._task("todo", date.today() - timedelta(days=1))
        self.assertEqual(ls.computed_status(t), "overdue")

    def test_due_today_not_overdue(self):
        t = self._task("todo", date.today())
        self.assertEqual(ls.computed_status(t), "todo")

    def test_no_due_date_never_overdue(self):
        self.assertEqual(ls.computed_status(self._task("doing", None)), "doing")


class TestTemplateVisibility(LearningTestBase):
    """班级/年级隔离：模板按 (grade, class_id) 过滤可见性。"""

    def test_grade_filter(self):
        self._make_template(grade=5)
        stu3 = self._make_user("stu3", grade=3)
        stu5 = self._make_user("stu5", grade=5)
        self.assertEqual(len(ls.visible_templates(self.db, stu3)), 0)
        self.assertEqual(len(ls.visible_templates(self.db, stu5)), 1)

    def test_class_filter(self):
        c1 = ClassGroup(name="三年级1班", grade=3)
        c2 = ClassGroup(name="三年级2班", grade=3)
        self.db.add_all([c1, c2])
        self.db.commit()
        self._make_template(class_id=c1.id)
        in_c1 = self._make_user("inc1", class_id=c1.id)
        in_c2 = self._make_user("inc2", class_id=c2.id)
        no_class = self._make_user("noclass")
        self.assertEqual(len(ls.visible_templates(self.db, in_c1)), 1)
        self.assertEqual(len(ls.visible_templates(self.db, in_c2)), 0)
        self.assertEqual(len(ls.visible_templates(self.db, no_class)), 0)

    def test_draft_template_invisible(self):
        self._make_template(status="draft")
        stu = self._make_user("stu")
        self.assertEqual(len(ls.visible_templates(self.db, stu)), 0)

    def test_instantiate_hidden_template_forbidden(self):
        tpl = self._make_template(grade=5)
        stu = self._make_user("stu", grade=3)
        with self.assertRaises(HTTPException) as ctx:
            ls.instantiate_plan(self.db, tpl, stu)
        self.assertEqual(ctx.exception.status_code, 403)


class TestInstantiate(LearningTestBase):
    """模板实例化：复制任务 + 回链 + 幂等。"""

    def test_copies_tasks_with_backlink(self):
        tpl = self._make_template(tasks=3)
        stu = self._make_user("stu")
        inst = ls.instantiate_plan(self.db, tpl, stu)
        self.assertEqual(inst.plan_type, "instance")
        self.assertEqual(inst.student_id, stu.id)
        self.assertEqual(inst.instantiated_from, tpl.id)
        self.assertEqual(inst.status, "active")
        tasks = self.db.query(LearningTask).filter_by(plan_id=inst.id).all()
        self.assertEqual(len(tasks), 3)
        self.assertTrue(all(t.status == "todo" for t in tasks))
        self.assertTrue(all(t.template_task_id for t in tasks))

    def test_idempotent(self):
        tpl = self._make_template()
        stu = self._make_user("stu")
        a = ls.instantiate_plan(self.db, tpl, stu)
        b = ls.instantiate_plan(self.db, tpl, stu)
        self.assertEqual(a.id, b.id)
        instances = self.db.query(LearningPlan).filter_by(
            plan_type="instance", student_id=stu.id).all()
        self.assertEqual(len(instances), 1)

    def test_resolve_student_task_forbids_cross_student(self):
        tpl = self._make_template()
        stu = self._make_user("stu")
        other = self._make_user("other")
        inst = ls.instantiate_plan(self.db, tpl, stu)
        task = self.db.query(LearningTask).filter_by(plan_id=inst.id).first()
        with self.assertRaises(HTTPException) as ctx:
            ls.resolve_student_task(self.db, other, task.id)
        self.assertEqual(ctx.exception.status_code, 403)


class TestSubmitAndReview(LearningTestBase):
    """提交与审核：三模式 + 边界。"""

    def _setup(self, review_mode="admin"):
        cfg = ls.get_or_create_config(self.db)
        cfg.review_mode = review_mode
        self.db.commit()
        tpl = self._make_template(tasks=1)
        stu = self._make_user("stu")
        inst = ls.instantiate_plan(self.db, tpl, stu)
        task = self.db.query(LearningTask).filter_by(plan_id=inst.id).first()
        return stu, task

    def test_submit_pending_under_admin_mode(self):
        stu, task = self._setup("admin")
        sub = ls.submit_task(self.db, stu, task, "完成了", None)
        self.assertEqual(sub.review_status, "pending")
        # 学生本人收到提交通知
        n = self.db.query(Notification).filter_by(user_id=stu.id).all()
        self.assertTrue(any("已提交" in x.title for x in n))

    def test_submit_auto_mode_approves_immediately(self):
        stu, task = self._setup("auto")
        sub = ls.submit_task(self.db, stu, task, "完成了", None)
        self.assertEqual(sub.review_status, "approved")
        self.assertEqual(sub.reviewer_role, "auto")
        self.db.refresh(stu)
        self.assertEqual(stu.points, task.reward_points)
        self.db.refresh(task)
        self.assertEqual(task.status, "done")

    def test_empty_submission_rejected(self):
        stu, task = self._setup("admin")
        with self.assertRaises(HTTPException) as ctx:
            ls.submit_task(self.db, stu, task, "   ", None)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_duplicate_pending_rejected(self):
        stu, task = self._setup("admin")
        ls.submit_task(self.db, stu, task, "第一次", None)
        with self.assertRaises(HTTPException) as ctx:
            ls.submit_task(self.db, stu, task, "第二次", None)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_resubmit_after_reject_allowed(self):
        stu, task = self._setup("admin")
        sub = ls.submit_task(self.db, stu, task, "第一次", None)
        ls.reject_submission(self.db, sub, reviewer=None, reviewer_role="admin", note="重拍")
        sub2 = ls.submit_task(self.db, stu, task, "第二次", None)
        self.assertEqual(sub2.review_status, "pending")
        self.assertNotEqual(sub2.id, sub.id)

    def test_approve_full_link(self):
        """审核通过联动：积分 + 宠物流水（feed_type=task）+ 双向通知。"""
        stu, task = self._setup("admin")
        pet = self._make_pet(stu)
        parent = self._make_user("p1", role="parent")
        self.db.add(StudentParent(student_id=stu.id, parent_id=parent.id))
        self.db.commit()

        sub = ls.submit_task(self.db, stu, task, "完成了", None)
        admin = self._make_user("boss", role="admin")
        ls.approve_submission(self.db, sub, reviewer=admin, reviewer_role="admin")

        self.db.refresh(stu)
        self.assertEqual(stu.points, task.reward_points)
        self.assertEqual(stu.study_streak, 1)

        self.db.refresh(pet)
        self.assertEqual(pet.current_xp, task.reward_xp)
        log = self.db.query(PetFeedLog).filter_by(user_id=stu.id).one()
        self.assertEqual(log.feed_type, "task")
        self.assertEqual(log.trigger_task_submission_id, sub.id)

        # 学生 + 家长各至少 1 条审核结果通知
        stu_notes = self.db.query(Notification).filter_by(user_id=stu.id).all()
        par_notes = self.db.query(Notification).filter_by(user_id=parent.id).all()
        self.assertTrue(any("审核通过" in n.title for n in stu_notes))
        self.assertTrue(any("通过审核" in n.title for n in par_notes))
        # 勋章：首个任务通过授予 plan_first
        self.assertIsNotNone(self.db.query(UserBadge).filter_by(
            user_id=stu.id, badge_key="plan_first").first())

    def test_double_approve_idempotent_guard(self):
        stu, task = self._setup("admin")
        sub = ls.submit_task(self.db, stu, task, "完成了", None)
        ls.approve_submission(self.db, sub, reviewer=None, reviewer_role="admin")
        with self.assertRaises(HTTPException) as ctx:
            ls.approve_submission(self.db, sub, reviewer=None, reviewer_role="admin")
        self.assertEqual(ctx.exception.status_code, 400)
        # 积分只发一次
        self.db.refresh(stu)
        self.assertEqual(stu.points, task.reward_points)

    def test_badge_award_idempotent(self):
        stu, task = self._setup("auto")
        ls.submit_task(self.db, stu, task, "完成了", None)
        # 再次判定不应重复授予
        self.assertEqual(ls.check_and_award_badges(self.db, stu), [])
        cnt = self.db.query(UserBadge).filter_by(user_id=stu.id, badge_key="plan_first").count()
        self.assertEqual(cnt, 1)


class TestConcurrentApprove(LearningTestBase):
    """并发重复审核兜底：部分唯一索引保证恰 1 条 approved、积分只发一次。
    用文件库 + 多线程真并发（内存库单连接无隔离，无法模拟竞态）。"""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._dbpath = os.path.join(self._tmpdir.name, "concurrent.db")
        self.engine = create_engine(
            f"sqlite:///{self._dbpath}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def _set_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()
        self._seed_base()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self._tmpdir.cleanup()

    def test_only_one_approved_among_duplicates(self):
        cfg = ls.get_or_create_config(self.db)
        cfg.review_mode = "admin"
        self.db.commit()
        tpl = self._make_template(tasks=1)
        stu = self._make_user("stu")
        inst = ls.instantiate_plan(self.db, tpl, stu)
        task = self.db.query(LearningTask).filter_by(plan_id=inst.id).first()

        # 直接造 10 条 pending（绕过 submit_task 的重复校验，模拟历史脏数据/竞争）
        subs = []
        for _ in range(10):
            s = TaskSubmission(task_id=task.id, user_id=stu.id,
                               content="c", review_status="pending")
            self.db.add(s)
            subs.append(s)
        self.db.commit()
        for s in subs:
            self.db.refresh(s)

        Session = sessionmaker(bind=self.engine)

        def try_approve(sid):
            db = Session()
            try:
                sub = db.get(TaskSubmission, sid)
                ls.approve_submission(db, sub, reviewer=None, reviewer_role="admin")
                return True
            except HTTPException:
                return False
            except Exception:
                return False
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(try_approve, [s.id for s in subs]))

        self.db.expire_all()
        approved = self.db.query(TaskSubmission).filter_by(
            task_id=task.id, review_status="approved").count()
        self.assertEqual(approved, 1)
        self.assertEqual(sum(results), 1)
        # 积分只发一次
        self.db.refresh(stu)
        self.assertEqual(stu.points, task.reward_points)


class TestStudyStreak(LearningTestBase):
    """连续学习天数：基于已批准提交的审核日期。"""

    def _approved_sub(self, user, task, reviewed):
        s = TaskSubmission(task_id=task.id, user_id=user.id, content="c",
                           review_status="approved", is_effective=True,
                           reviewer_role="admin", reviewed_at=reviewed)
        self.db.add(s)
        self.db.commit()
        return s

    def test_consecutive_days(self):
        stu = self._make_user("stu")
        tpl = self._make_template(tasks=3)
        inst = ls.instantiate_plan(self.db, tpl, stu)
        tasks = self.db.query(LearningTask).filter_by(plan_id=inst.id).all()
        today = now_local()
        self._approved_sub(stu, tasks[0], today - timedelta(days=2))
        self._approved_sub(stu, tasks[1], today - timedelta(days=1))
        self._approved_sub(stu, tasks[2], today)
        current, longest = ls.recompute_study_streak(self.db, stu)
        self.assertEqual(current, 3)
        self.assertEqual(longest, 3)

    def test_gap_breaks_streak(self):
        stu = self._make_user("stu")
        tpl = self._make_template(tasks=2)
        inst = ls.instantiate_plan(self.db, tpl, stu)
        tasks = self.db.query(LearningTask).filter_by(plan_id=inst.id).all()
        today = now_local()
        self._approved_sub(stu, tasks[0], today - timedelta(days=5))
        self._approved_sub(stu, tasks[1], today)
        current, longest = ls.recompute_study_streak(self.db, stu)
        self.assertEqual(current, 1)
        self.assertEqual(longest, 1)

    def test_longest_never_decreases(self):
        stu = self._make_user("stu")
        stu.study_longest_streak = 9
        self.db.commit()
        current, longest = ls.recompute_study_streak(self.db, stu)
        self.db.refresh(stu)
        self.assertEqual(stu.study_longest_streak, 9)


class TestModeSwitchRegression(LearningTestBase):
    """跨模式切换：暑期打卡数据零触碰。"""

    def test_switch_back_to_summer_keeps_checkins(self):
        stu = self._make_user("stu")
        ci = CheckIn(user_id=stu.id, check_date=date.today(),
                     photo_path=f"{stu.id}/a.jpg", check_type="normal",
                     review_status="approved", is_effective=True)
        self.db.add(ci)
        stu.points = 10
        self.db.commit()
        before = {
            "checkins": self.db.query(CheckIn).count(),
            "points": stu.points,
            "streak": stu.current_streak,
        }

        cfg = ls.get_or_create_config(self.db)
        for mode in ("semester", "holiday", "summer"):
            cfg.mode = mode
            self.db.commit()

        self.assertEqual(self.db.query(CheckIn).count(), before["checkins"])
        self.db.refresh(stu)
        self.assertEqual(stu.points, before["points"])
        self.assertEqual(stu.current_streak, before["streak"])
        self.assertEqual(cfg.mode, "summer")


class TestProgressRecords(LearningTestBase):
    """进展记录：todo→doing 流转 + 完成后拒绝。"""

    def _setup(self):
        tpl = self._make_template(tasks=1)
        stu = self._make_user("stu")
        inst = ls.instantiate_plan(self.db, tpl, stu)
        task = self.db.query(LearningTask).filter_by(plan_id=inst.id).first()
        return stu, task

    def test_progress_moves_todo_to_doing(self):
        stu, task = self._setup()
        ls.add_progress(self.db, stu, task, "写了一半", 10, 50)
        self.db.refresh(task)
        self.assertEqual(task.status, "doing")
        rec = self.db.query(ProgressRecord).filter_by(task_id=task.id).one()
        self.assertEqual(rec.percent, 50)

    def test_percent_clamped(self):
        stu, task = self._setup()
        rec = ls.add_progress(self.db, stu, task, "", 10, 150)
        self.assertEqual(rec.percent, 100)

    def test_done_task_rejects_progress(self):
        stu, task = self._setup()
        task.status = "done"
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            ls.add_progress(self.db, stu, task, "x", 10, 50)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_done_task_rejects_submit(self):
        stu, task = self._setup()
        task.status = "done"
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            ls.submit_task(self.db, stu, task, "x", None)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
