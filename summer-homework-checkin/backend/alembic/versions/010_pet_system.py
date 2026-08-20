"""pet system - add pet tables and user pet fields

新增宠物领养系统：
- users 表增加 pet_id / pet_level / pet_xp 冗余字段
- 新建 pet_species（种类配置）、pet_adoption（领养记录）、pet_feed_log（成长流水）

Revision ID: 010_pet_system
Revises: 009_wecom_bot
Create Date: 2026-08-20 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_pet_system'
down_revision: Union[str, None] = '009_wecom_bot'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ---- 1. users 表增加宠物冗余字段 ----
    if 'users' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('users')}
        if 'pet_id' not in columns:
            op.add_column('users', sa.Column('pet_id', sa.Integer(), nullable=True))
        if 'pet_level' not in columns:
            op.add_column('users', sa.Column('pet_level', sa.String(16), nullable=True))
        if 'pet_xp' not in columns:
            op.add_column('users', sa.Column('pet_xp', sa.Integer(), server_default='0'))

    # ---- 2. 新建 pet_species 表 ----
    if 'pet_species' not in inspector.get_table_names():
        op.create_table(
            'pet_species',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(32), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('emoji_baby', sa.String(16), server_default='🐣'),
            sa.Column('emoji_youth', sa.String(16), server_default='🐥'),
            sa.Column('emoji_adult', sa.String(16), server_default='🐔'),
            sa.Column('emoji_legend', sa.String(16), server_default='🦄'),
            sa.Column('status', sa.String(8), server_default='on'),
            sa.Column('sort_order', sa.Integer(), server_default='0'),
            sa.Column('created_at', sa.DateTime()),
        )
        # 插入默认种类：学习猫
        op.execute(
            "INSERT INTO pet_species (name, description, emoji_baby, emoji_youth, emoji_adult, emoji_legend, sort_order) "
            "VALUES ('学习猫', '爱读书的小猫咪，陪你一起成长', '🐱', '😺', '😸', '🦁', 0)"
        )

    # ---- 3. 新建 pet_adoption 表 ----
    if 'pet_adoption' not in inspector.get_table_names():
        op.create_table(
            'pet_adoption',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('species_id', sa.Integer(), sa.ForeignKey('pet_species.id'), nullable=False),
            sa.Column('nickname', sa.String(32), nullable=True),
            sa.Column('current_xp', sa.Integer(), server_default='0'),
            sa.Column('current_stage', sa.String(16), server_default='baby'),
            sa.Column('last_fed_at', sa.DateTime(), nullable=True),
            sa.Column('adopted_at', sa.DateTime()),
            sa.Column('is_active', sa.Boolean(), server_default='1'),
            sa.Column('abandoned_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_pet_adoption_user_id', 'pet_adoption', ['user_id'])

    # ---- 4. 新建 pet_feed_log 表 ----
    if 'pet_feed_log' not in inspector.get_table_names():
        op.create_table(
            'pet_feed_log',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('adoption_id', sa.Integer(), sa.ForeignKey('pet_adoption.id'), nullable=False),
            sa.Column('feed_type', sa.String(16), nullable=False),
            sa.Column('xp_gained', sa.Integer(), nullable=False),
            sa.Column('total_xp_after', sa.Integer(), nullable=False),
            sa.Column('stage_before', sa.String(16), nullable=True),
            sa.Column('stage_after', sa.String(16), nullable=True),
            sa.Column('trigger_checkin_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime()),
        )
        op.create_index('ix_pet_feed_log_user_id', 'pet_feed_log', ['user_id'])
        op.create_index('ix_pet_feed_log_adoption_id', 'pet_feed_log', ['adoption_id'])
        op.create_index('ix_pet_feed_log_created_at', 'pet_feed_log', ['created_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 逆序删除
    if 'pet_feed_log' in inspector.get_table_names():
        op.drop_table('pet_feed_log')

    if 'pet_adoption' in inspector.get_table_names():
        op.drop_table('pet_adoption')

    if 'pet_species' in inspector.get_table_names():
        op.drop_table('pet_species')

    # 删除 users 表的宠物字段
    if 'users' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('users')}
        if 'pet_xp' in columns:
            op.drop_column('users', 'pet_xp')
        if 'pet_level' in columns:
            op.drop_column('users', 'pet_level')
        if 'pet_id' in columns:
            op.drop_column('users', 'pet_id')
