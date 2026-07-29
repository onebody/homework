"""site config points - add checkin_points / makeup_points columns

site_config 表在旧库中可能已由 create_all 建出（无积分列），
故防御性补列；表不存在则交给启动时 create_all 建全表。
列为空表示沿用 config 默认分值，不改变既有发分行为。

Revision ID: 008_site_points
Revises: 007_seed_push_templates
Create Date: 2026-08-08 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_site_points'
down_revision: Union[str, None] = '007_seed_push_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'site_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('site_config')}
    if 'checkin_points' not in columns:
        op.add_column('site_config', sa.Column('checkin_points', sa.Integer(), nullable=True))
    if 'makeup_points' not in columns:
        op.add_column('site_config', sa.Column('makeup_points', sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'site_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('site_config')}
    if 'makeup_points' in columns:
        op.drop_column('site_config', 'makeup_points')
    if 'checkin_points' in columns:
        op.drop_column('site_config', 'checkin_points')
