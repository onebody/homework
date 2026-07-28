"""push config challenge - add push_on_challenge column

push_config 表在旧库中已由 create_all 建出（无 push_on_challenge 列），
故防御性补列，默认 1（开启）与模型默认值一致；表不存在则交给启动时 create_all 建全表。

Revision ID: 005_push_challenge
Revises: 004_site_slogan
Create Date: 2026-08-01 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_push_challenge'
down_revision: Union[str, None] = '004_site_slogan'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'push_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('push_config')}
    if 'push_on_challenge' not in columns:
        op.add_column('push_config', sa.Column(
            'push_on_challenge', sa.Boolean(), nullable=True, server_default=sa.text('1')))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'push_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('push_config')}
    if 'push_on_challenge' in columns:
        op.drop_column('push_config', 'push_on_challenge')
