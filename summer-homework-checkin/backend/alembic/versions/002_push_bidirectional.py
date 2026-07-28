"""push config bidirectional - add outgoing_token / allow_bot_review

Revision ID: 002_push_bidirectional
Revises: 001_initial
Create Date: 2026-07-28 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_push_bidirectional'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'push_config' not in tables:
        # 表不存在时由 create_all 兜底创建（含全部新列），此处跳过
        return

    columns = {c['name'] for c in inspector.get_columns('push_config')}
    if 'outgoing_token' not in columns:
        op.add_column('push_config', sa.Column('outgoing_token', sa.String(128), nullable=True))
    if 'allow_bot_review' not in columns:
        op.add_column('push_config', sa.Column('allow_bot_review', sa.Boolean(), server_default='0'))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'push_config' not in inspector.get_table_names():
        return
    columns = {c['name'] for c in inspector.get_columns('push_config')}
    if 'allow_bot_review' in columns:
        op.drop_column('push_config', 'allow_bot_review')
    if 'outgoing_token' in columns:
        op.drop_column('push_config', 'outgoing_token')
