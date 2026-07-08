"""initial schema - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-07-07 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用户表
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('username', sa.String(64), unique=True, index=True, nullable=False),
        sa.Column('password_hash', sa.String(128), nullable=False),
        sa.Column('password_salt', sa.String(64), nullable=True),
        sa.Column('role', sa.String(16), nullable=False, server_default='student'),
        sa.Column('nickname', sa.String(64), nullable=False),
        sa.Column('grade', sa.Integer(), server_default='3'),
        sa.Column('home_lat', sa.Float(), nullable=True),
        sa.Column('home_lng', sa.Float(), nullable=True),
        sa.Column('bind_code', sa.String(16), nullable=True),
        sa.Column('face_enrolled', sa.Boolean(), server_default='0'),
        sa.Column('face_embedding', sa.Text(), nullable=True),
        sa.Column('face_id_path', sa.String(256), nullable=True),
        sa.Column('phone', sa.String(32), nullable=True),
        sa.Column('current_streak', sa.Integer(), server_default='0'),
        sa.Column('longest_streak', sa.Integer(), server_default='0'),
        sa.Column('effective_checkins', sa.Integer(), server_default='0'),
        sa.Column('lottery_tickets', sa.Integer(), server_default='0'),
        sa.Column('points', sa.Integer(), server_default='0'),
        sa.Column('last_7_milestone', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 家长-孩子绑定关系
    op.create_table(
        'student_parent',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 打卡记录
    op.create_table(
        'checkins',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('check_date', sa.Date(), nullable=False, index=True),
        sa.Column('check_time', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('photo_path', sa.String(256), nullable=False),
        sa.Column('location_lat', sa.Float(), nullable=True),
        sa.Column('location_lng', sa.Float(), nullable=True),
        sa.Column('check_type', sa.String(16), server_default='normal'),
        sa.Column('makeup_reason', sa.String(256), nullable=True),
        sa.Column('makeup_proof_path', sa.String(256), nullable=True),
        sa.Column('geo_distance', sa.Float(), nullable=True),
        sa.Column('geo_flag', sa.Boolean(), server_default='0'),
        sa.Column('scene_check', sa.String(16), server_default='pending'),
        sa.Column('face_status', sa.String(16), nullable=True),
        sa.Column('face_score', sa.Float(), nullable=True),
        sa.Column('face_flag', sa.Boolean(), server_default='0'),
        sa.Column('review_status', sa.String(16), server_default='pending'),
        sa.Column('review_note', sa.String(256), nullable=True),
        sa.Column('is_effective', sa.Boolean(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 奖品表
    op.create_table(
        'prizes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(16), server_default='stationery'),
        sa.Column('probability', sa.Float(), server_default='0.1'),
        sa.Column('stock', sa.Integer(), server_default='-1'),
        sa.Column('status', sa.String(8), server_default='on'),
        sa.Column('cost_points', sa.Integer(), server_default='0'),
        sa.Column('is_lottery_ticket', sa.Boolean(), server_default='0'),
        sa.Column('ticket_qty', sa.Integer(), server_default='1'),
        sa.Column('image_url', sa.String(256), nullable=True),
        sa.Column('is_preset', sa.Boolean(), server_default='0'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 抽奖记录
    op.create_table(
        'lottery_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('prize_id', sa.Integer(), sa.ForeignKey('prizes.id'), nullable=True),
        sa.Column('prize_name', sa.String(128), nullable=True),
        sa.Column('is_win', sa.Boolean(), server_default='0'),
        sa.Column('drawn_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 兑换记录
    op.create_table(
        'redemptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('prize_id', sa.Integer(), sa.ForeignKey('prizes.id'), nullable=False),
        sa.Column('prize_name', sa.String(128), nullable=False),
        sa.Column('cost_points', sa.Integer(), server_default='0'),
        sa.Column('redeemed_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column('status', sa.String(16), server_default='pending'),
        sa.Column('replaced_by', sa.Integer(), sa.ForeignKey('redemptions.id'), nullable=True),
        sa.Column('note', sa.String(256), nullable=True),
        sa.Column('review_note', sa.String(256), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    )

    # 通知表
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('recipient_role', sa.String(16), nullable=False),
        sa.Column('type', sa.String(16), server_default='system'),
        sa.Column('title', sa.String(128), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('read', sa.Boolean(), server_default='0'),
        sa.Column('related_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 闯关任务
    op.create_table(
        'challenge_tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('reward_points', sa.Integer(), server_default='10'),
        sa.Column('status', sa.String(16), server_default='locked'),
        sa.Column('unlock_at', sa.DateTime(), nullable=True),
        sa.Column('unlock_condition', sa.String(256), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # 闯关打卡记录
    op.create_table(
        'challenge_checkins',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('challenge_tasks.id'), nullable=False, index=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('attachments', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(16), server_default='pending'),
        sa.Column('review_note', sa.String(256), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table('challenge_checkins')
    op.drop_table('challenge_tasks')
    op.drop_table('notifications')
    op.drop_table('redemptions')
    op.drop_table('lottery_records')
    op.drop_table('prizes')
    op.drop_table('checkins')
    op.drop_table('student_parent')
    op.drop_table('users')
