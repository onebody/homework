"""timezone fix - shift stored UTC timestamps to Beijing time (+8h)

历史数据此前以 naive UTC 写入；自本版本起应用统一写入 naive 北京时间
（app/utils/timeutil.now_local），故将存量时间戳整体 +8 小时，并按新的
check_time 重算 checkins.check_date（修复早上 8 点前打卡被记到前一天的问题）。

注意：challenge_tasks.unlock_at 为管理员按本地时间输入，不参与偏移。

Revision ID: 003_tz_beijing
Revises: 002_push_bidirectional
Create Date: 2026-07-28 16:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_tz_beijing'
down_revision: Union[str, None] = '002_push_bidirectional'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 表 -> 需 +8h 的时间列（unlock_at 除外）
_SHIFT_COLUMNS = {
    'users': ['created_at'],
    'student_parent': ['created_at'],
    'checkins': ['check_time', 'created_at'],
    'prizes': ['created_at'],
    'lottery_records': ['drawn_at'],
    'redemptions': ['redeemed_at', 'reviewed_at'],
    'notifications': ['created_at'],
    'challenge_tasks': ['created_at'],
    'challenge_checkins': ['created_at', 'reviewed_at'],
    'push_config': ['updated_at'],
    'push_logs': ['created_at'],
}


def _shift(bind, tables, inspector, hours: int) -> None:
    for table, cols in _SHIFT_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c['name'] for c in inspector.get_columns(table)}
        for col in cols:
            if col not in existing:
                continue
            bind.execute(sa.text(
                f"UPDATE {table} SET {col} = datetime({col}, '{hours:+d} hours') "
                f"WHERE {col} IS NOT NULL"
            ))
    # 按修正后的 check_time 重算打卡自然日
    if 'checkins' in tables:
        bind.execute(sa.text(
            "UPDATE checkins SET check_date = date(check_time) "
            "WHERE check_time IS NOT NULL"
        ))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _shift(bind, inspector.get_table_names(), inspector, 8)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _shift(bind, inspector.get_table_names(), inspector, -8)
