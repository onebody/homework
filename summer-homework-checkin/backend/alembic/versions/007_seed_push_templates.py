"""seed default push templates - backfill NULL template columns

存量库的模板字段从未保存过（NULL）时回填内置默认模板，
使后台界面展示可编辑的预填内容；已自定义（非 NULL）的行不受影响。
渲染结果与回填前完全一致（空值本就回退到同样的内置默认，签名除外——
回填后消息末尾会追加默认签名，后台可自行清空）。

Revision ID: 007_seed_push_templates
Revises: 006_push_templates
Create Date: 2026-08-02 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_seed_push_templates'
down_revision: Union[str, None] = '006_push_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 与 app/config.py 的 DEFAULT_PUSH_TEMPLATES 保持一致
# （迁移脚本不 import 应用代码，避免未来常量变更影响历史迁移的可重放性）
_DEFAULTS = (
    ('tpl_daily_title', '【暑假打卡】{nickname} {type} {status}'),
    ('tpl_daily_body', '时间：{time}\n{geo_warn}\n{photo_line}'),
    ('tpl_challenge_title', '【暑假打卡】{nickname} 闯关「{task}」{status}'),
    ('tpl_challenge_body', '时间：{time}\n{points_line}\n{reason_line}'),
    ('tpl_signature', '—— 暑假作业打卡系统'),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'push_config' not in inspector.get_table_names():
        return

    columns = {c['name'] for c in inspector.get_columns('push_config')}
    for name, default in _DEFAULTS:
        if name in columns:
            bind.execute(
                sa.text(f"UPDATE push_config SET {name} = :val WHERE {name} IS NULL"),
                {"val": default},
            )


def downgrade() -> None:
    # 无法区分回填值与用户自定义值，降级不做处理（保留现有模板内容）
    pass
