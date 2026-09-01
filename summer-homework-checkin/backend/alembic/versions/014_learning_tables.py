"""learning plan module - core tables

多学段学习成长计划核心表（9 张）：
- subjects / class_groups / semesters：基础数据（学科/班级/学期周期）
- learning_plans：单表双角色（template 模板 / instance 学生实例）
- learning_tasks / progress_records / task_submissions：任务、进展流水、成果提交审核
- user_badges：成就勋章
- learning_config：单行全局配置（模式/审核模式/当前学期）

并发重复发奖兜底：task_submissions 建部分唯一索引
UNIQUE(task_id) WHERE review_status='approved'。

Revision ID: 014_learning_tables
Revises: 013_user_theme
Create Date: 2026-08-29 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '014_learning_tables'
down_revision: Union[str, None] = '013_user_theme'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 建表顺序（按外键依赖），删表取反序
_TABLES = [
    "subjects", "class_groups", "semesters", "learning_plans",
    "learning_tasks", "progress_records", "task_submissions",
    "user_badges", "learning_config",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "subjects" not in existing:
        op.create_table(
            "subjects",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(32), nullable=False),
            sa.Column("emoji", sa.String(16), default="📚"),
            sa.Column("grade_min", sa.Integer(), default=1),
            sa.Column("grade_max", sa.Integer(), default=6),
            sa.Column("sort_order", sa.Integer(), default=0),
            sa.Column("status", sa.String(8), default="on"),
            sa.Column("is_preset", sa.Boolean(), default=False),
            sa.Column("created_at", sa.DateTime()),
        )

    if "class_groups" not in existing:
        op.create_table(
            "class_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("grade", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime()),
        )

    if "semesters" not in existing:
        op.create_table(
            "semesters",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("type", sa.String(16), default="semester"),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(16), default="archived"),
            sa.Column("created_at", sa.DateTime()),
        )

    if "learning_plans" not in existing:
        op.create_table(
            "learning_plans",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("plan_type", sa.String(16), nullable=False, server_default="template"),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("semester_id", sa.Integer(), sa.ForeignKey("semesters.id"), nullable=True),
            sa.Column("grade", sa.Integer(), nullable=True),
            sa.Column("class_id", sa.Integer(), sa.ForeignKey("class_groups.id"), nullable=True),
            sa.Column("period_type", sa.String(8), default="week"),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("instantiated_from", sa.Integer(), sa.ForeignKey("learning_plans.id"), nullable=True),
            sa.Column("status", sa.String(16), default="draft"),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_learning_plans_semester_id", "learning_plans", ["semester_id"])
        op.create_index("ix_learning_plans_student_id", "learning_plans", ["student_id"])

    if "learning_tasks" not in existing:
        op.create_table(
            "learning_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("plan_id", sa.Integer(), sa.ForeignKey("learning_plans.id"), nullable=False),
            sa.Column("template_task_id", sa.Integer(), nullable=True),
            sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=True),
            sa.Column("title", sa.String(128), nullable=False),
            sa.Column("completion_criteria", sa.Text(), nullable=True),
            sa.Column("est_minutes", sa.Integer(), default=30),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("reward_points", sa.Integer(), default=10),
            sa.Column("reward_xp", sa.Integer(), default=10),
            sa.Column("sort_order", sa.Integer(), default=0),
            sa.Column("status", sa.String(8), default="todo"),
            sa.Column("done_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_learning_tasks_plan_id", "learning_tasks", ["plan_id"])

    if "progress_records" not in existing:
        op.create_table(
            "progress_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("learning_tasks.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("minutes_spent", sa.Integer(), default=0),
            sa.Column("percent", sa.Integer(), default=0),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_progress_records_task_id", "progress_records", ["task_id"])
        op.create_index("ix_progress_records_user_id", "progress_records", ["user_id"])

    if "task_submissions" not in existing:
        op.create_table(
            "task_submissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("learning_tasks.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("photo_path", sa.String(256), nullable=True),
            sa.Column("review_status", sa.String(16), default="pending"),
            sa.Column("review_note", sa.String(256), nullable=True),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("reviewer_role", sa.String(16), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("is_effective", sa.Boolean(), default=False),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_task_submissions_task_id", "task_submissions", ["task_id"])
        op.create_index("ix_task_submissions_user_id", "task_submissions", ["user_id"])
        # 部分唯一索引：同一任务最多一条 approved，并发重复发奖的硬兜底
        op.create_index(
            "ux_task_submissions_approved",
            "task_submissions",
            ["task_id"],
            unique=True,
            sqlite_where=sa.text("review_status='approved'"),
        )

    if "user_badges" not in existing:
        op.create_table(
            "user_badges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("badge_key", sa.String(32), nullable=False),
            sa.Column("badge_name", sa.String(64), nullable=False),
            sa.Column("earned_at", sa.DateTime()),
        )
        op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])
        op.create_index("ix_user_badges_badge_key", "user_badges", ["badge_key"])

    if "learning_config" not in existing:
        op.create_table(
            "learning_config",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("mode", sa.String(16), default="summer"),
            sa.Column("review_mode", sa.String(16), default="admin"),
            sa.Column("current_semester_id", sa.Integer(), sa.ForeignKey("semesters.id"), nullable=True),
            sa.Column("updated_at", sa.DateTime()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    for table in reversed(_TABLES):
        if table in existing:
            op.drop_table(table)
