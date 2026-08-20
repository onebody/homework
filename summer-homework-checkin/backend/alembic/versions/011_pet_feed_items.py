"""pet feed items - add pet food shop and feed log extensions

新增宠物食物商店：
- 新建 pet_feed_items（食物商品表）
- pet_feed_log 增加 feed_item_id / points_cost 字段
- pet_species 增加 feeding_reminder_enabled 字段

Revision ID: 011_pet_feed_items
Revises: 010_pet_system
Create Date: 2026-08-20 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_pet_feed_items'
down_revision: Union[str, None] = '010_pet_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ---- 1. 新建 pet_feed_items 表 ----
    if 'pet_feed_items' not in inspector.get_table_names():
        op.create_table(
            'pet_feed_items',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(64), nullable=False),
            sa.Column('description', sa.String(256), nullable=True),
            sa.Column('emoji', sa.String(16), server_default='🍎'),
            sa.Column('price', sa.Integer, nullable=False, server_default='5'),
            sa.Column('xp_value', sa.Integer, nullable=False, server_default='5'),
            sa.Column('species_id', sa.Integer, sa.ForeignKey('pet_species.id'), nullable=True),
            sa.Column('status', sa.String(8), server_default='on'),
            sa.Column('sort_order', sa.Integer, server_default='0'),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )
        print("✅ 已创建 pet_feed_items 表")

    # ---- 2. pet_feed_log 增加 feed_item_id / points_cost 字段 ----
    if 'pet_feed_log' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_feed_log')}
        if 'feed_item_id' not in columns:
            op.add_column('pet_feed_log', sa.Column('feed_item_id', sa.Integer, nullable=True))
        if 'points_cost' not in columns:
            op.add_column('pet_feed_log', sa.Column('points_cost', sa.Integer, server_default='0'))

    # ---- 3. pet_species 增加 feeding_reminder_enabled 字段 ----
    if 'pet_species' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_species')}
        if 'feeding_reminder_enabled' not in columns:
            op.add_column('pet_species', sa.Column('feeding_reminder_enabled', sa.Boolean, server_default=sa.false()))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'pet_species' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_species')}
        if 'feeding_reminder_enabled' in columns:
            op.drop_column('pet_species', 'feeding_reminder_enabled')

    if 'pet_feed_log' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_feed_log')}
        if 'points_cost' in columns:
            op.drop_column('pet_feed_log', 'points_cost')
        if 'feed_item_id' in columns:
            op.drop_column('pet_feed_log', 'feed_item_id')

    if 'pet_feed_items' in inspector.get_table_names():
        op.drop_table('pet_feed_items')
