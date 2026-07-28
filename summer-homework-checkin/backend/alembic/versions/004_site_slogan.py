"""site config slogan - add student_slogan column

site_config 表在旧库中可能已由 create_all 建出（无 student_slogan 列），
故防御性补列；表不存在则交给启动时 create_all 建全表。

Revision ID: 004_site_slogan
Revises: 003_tz_beijing
Create Date: 2026-07-28 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_site_slogan'
down_revision: Union[str, None] = '003_tz_beijing'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'site_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('site_config')}
    if 'student_slogan' not in columns:
        op.add_column('site_config', sa.Column('student_slogan', sa.String(128), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'site_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('site_config')}
    if 'student_slogan' in columns:
        op.drop_column('site_config', 'student_slogan')
