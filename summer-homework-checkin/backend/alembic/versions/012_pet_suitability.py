"""pet suitability - add diet type, food suitability, sick state

新增食物适配性与生态反馈：
- pet_species 增加 diet_type（饮食类型）
- pet_feed_items 增加 suitability_level / suitability_note
- pet_feed_log 增加 suitability_result
- pet_adoption 增加 sick_until / perfect_streak

Revision ID: 012_pet_suitability
Revises: 011_pet_feed_items
Create Date: 2026-08-20 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '012_pet_suitability'
down_revision: Union[str, None] = '011_pet_feed_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # pet_species: diet_type
    if 'pet_species' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_species')}
        if 'diet_type' not in columns:
            op.add_column('pet_species', sa.Column('diet_type', sa.String(50), nullable=True))

    # pet_feed_items: suitability_level / suitability_note
    if 'pet_feed_items' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_feed_items')}
        if 'suitability_level' not in columns:
            op.add_column('pet_feed_items', sa.Column('suitability_level', sa.String(20), server_default='suitable'))
        if 'suitability_note' not in columns:
            op.add_column('pet_feed_items', sa.Column('suitability_note', sa.String(256), nullable=True))

    # pet_feed_log: suitability_result
    if 'pet_feed_log' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_feed_log')}
        if 'suitability_result' not in columns:
            op.add_column('pet_feed_log', sa.Column('suitability_result', sa.String(20), nullable=True))

    # pet_adoption: sick_until / perfect_streak
    if 'pet_adoption' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_adoption')}
        if 'sick_until' not in columns:
            op.add_column('pet_adoption', sa.Column('sick_until', sa.DateTime, nullable=True))
        if 'perfect_streak' not in columns:
            op.add_column('pet_adoption', sa.Column('perfect_streak', sa.Integer, server_default='0'))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'pet_adoption' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_adoption')}
        if 'perfect_streak' in columns:
            op.drop_column('pet_adoption', 'perfect_streak')
        if 'sick_until' in columns:
            op.drop_column('pet_adoption', 'sick_until')

    if 'pet_feed_log' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_feed_log')}
        if 'suitability_result' in columns:
            op.drop_column('pet_feed_log', 'suitability_result')

    if 'pet_feed_items' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_feed_items')}
        if 'suitability_note' in columns:
            op.drop_column('pet_feed_items', 'suitability_note')
        if 'suitability_level' in columns:
            op.drop_column('pet_feed_items', 'suitability_level')

    if 'pet_species' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('pet_species')}
        if 'diet_type' in columns:
            op.drop_column('pet_species', 'diet_type')
