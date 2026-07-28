"""push config templates - add message template columns

push_config 表在旧库中已由 create_all 建出（无模板列），故防御性补 5 个模板列；
空值表示使用内置默认模板，行为与历史版本完全一致。

Revision ID: 006_push_templates
Revises: 005_push_challenge
Create Date: 2026-08-01 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_push_templates'
down_revision: Union[str, None] = '005_push_challenge'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ('tpl_daily_title', sa.String(256)),
    ('tpl_daily_body', sa.Text()),
    ('tpl_challenge_title', sa.String(256)),
    ('tpl_challenge_body', sa.Text()),
    ('tpl_signature', sa.String(256)),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'push_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('push_config')}
    for name, type_ in _COLUMNS:
        if name not in columns:
            op.add_column('push_config', sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'push_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('push_config')}
    for name, _ in _COLUMNS:
        if name in columns:
            op.drop_column('push_config', name)
