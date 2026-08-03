"""wecom bot - add wecom_bot_token / wecom_bot_aes_key

Revision ID: 009_wecom_bot
Revises: 008_site_points
Create Date: 2026-08-24 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_wecom_bot'
down_revision: Union[str, None] = '008_site_points'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'push_config' not in inspector.get_table_names():
        # 表不存在时由 create_all 兜底创建（含全部新列），此处跳过
        return

    columns = {c['name'] for c in inspector.get_columns('push_config')}
    if 'wecom_bot_token' not in columns:
        op.add_column('push_config', sa.Column('wecom_bot_token', sa.String(128), nullable=True))
    if 'wecom_bot_aes_key' not in columns:
        op.add_column('push_config', sa.Column('wecom_bot_aes_key', sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'push_config' not in inspector.get_table_names():
        return
    columns = {c['name'] for c in inspector.get_columns('push_config')}
    if 'wecom_bot_aes_key' in columns:
        op.drop_column('push_config', 'wecom_bot_aes_key')
    if 'wecom_bot_token' in columns:
        op.drop_column('push_config', 'wecom_bot_token')
