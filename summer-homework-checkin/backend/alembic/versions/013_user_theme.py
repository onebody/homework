"""user theme preference - cloud persisted theme choice

用户界面主题偏好云端持久化：
- users 增加 theme（default/cartoon，NULL 表示未设置，前端回退 default）

Revision ID: 013_user_theme
Revises: 012_pet_suitability
Create Date: 2026-08-28 21:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '013_user_theme'
down_revision: Union[str, None] = '012_pet_suitability'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # users: theme（幂等：已存在则跳过）
    if 'users' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('users')}
        if 'theme' not in columns:
            op.add_column('users', sa.Column('theme', sa.String(16), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'users' in inspector.get_table_names():
        columns = {c['name'] for c in inspector.get_columns('users')}
        if 'theme' in columns:
            op.drop_column('users', 'theme')
