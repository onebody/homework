"""learning plan module - existing table links

学习计划模块与既有表的关联（全部可空 ADD COLUMN，零数据影响）：
- users: +class_id（班级归属）、+study_streak / study_longest_streak（连续学习天数冗余字段）
- pet_feed_log: +trigger_task_submission_id（任务 XP 流水溯源；feed_type 新增取值 task）
- 复合索引：learning_tasks(plan_id, due_date)、progress_records(task_id, created_at)

Revision ID: 015_learning_links
Revises: 014_learning_tables
Create Date: 2026-08-29 10:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '015_learning_links'
down_revision: Union[str, None] = '014_learning_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # users: class_id / study_streak / study_longest_streak（幂等）
    if 'users' in tables:
        columns = {c['name'] for c in inspector.get_columns('users')}
        if 'class_id' not in columns:
            op.add_column('users', sa.Column('class_id', sa.Integer(), nullable=True))
        if 'study_streak' not in columns:
            op.add_column('users', sa.Column('study_streak', sa.Integer(), server_default='0'))
        if 'study_longest_streak' not in columns:
            op.add_column('users', sa.Column('study_longest_streak', sa.Integer(), server_default='0'))

    # pet_feed_log: trigger_task_submission_id（幂等）
    if 'pet_feed_log' in tables:
        columns = {c['name'] for c in inspector.get_columns('pet_feed_log')}
        if 'trigger_task_submission_id' not in columns:
            op.add_column(
                'pet_feed_log',
                sa.Column('trigger_task_submission_id', sa.Integer(), nullable=True),
            )

    # 复合索引（幂等）
    if 'learning_tasks' in tables:
        idx = {i['name'] for i in inspector.get_indexes('learning_tasks')}
        if 'ix_learning_tasks_plan_due' not in idx:
            op.create_index('ix_learning_tasks_plan_due', 'learning_tasks', ['plan_id', 'due_date'])

    if 'progress_records' in tables:
        idx = {i['name'] for i in inspector.get_indexes('progress_records')}
        if 'ix_progress_records_task_time' not in idx:
            op.create_index('ix_progress_records_task_time', 'progress_records', ['task_id', 'created_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'progress_records' in tables:
        idx = {i['name'] for i in inspector.get_indexes('progress_records')}
        if 'ix_progress_records_task_time' in idx:
            op.drop_index('ix_progress_records_task_time', table_name='progress_records')

    if 'learning_tasks' in tables:
        idx = {i['name'] for i in inspector.get_indexes('learning_tasks')}
        if 'ix_learning_tasks_plan_due' in idx:
            op.drop_index('ix_learning_tasks_plan_due', table_name='learning_tasks')

    # SQLite 删列需 batch 模式（保留列映射）
    if 'pet_feed_log' in tables:
        columns = {c['name'] for c in inspector.get_columns('pet_feed_log')}
        if 'trigger_task_submission_id' in columns:
            with op.batch_alter_table('pet_feed_log') as batch:
                batch.drop_column('trigger_task_submission_id')

    if 'users' in tables:
        columns = {c['name'] for c in inspector.get_columns('users')}
        with op.batch_alter_table('users') as batch:
            if 'study_longest_streak' in columns:
                batch.drop_column('study_longest_streak')
            if 'study_streak' in columns:
                batch.drop_column('study_streak')
            if 'class_id' in columns:
                batch.drop_column('class_id')
