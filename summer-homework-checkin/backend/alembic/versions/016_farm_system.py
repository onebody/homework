"""farm system - growth farm module

成长农场模块（游戏化养成）：4 张全新表，零既有表改动，零数据影响。
- farm_templates：农场模板（田园/科幻/卡通，种子数据预置）
- farms：学生农场（一人一场，含自定义名称/能量余额/成长树/森林）
- farm_plots：地块（种菜 crop / 养殖 animal，成熟收获返还能量）
- farm_energy_log：能量流水（任务/打卡/回填获得，种植/养殖/浇树消耗）

Revision ID: 016_farm_system
Revises: 015_learning_links
Create Date: 2026-08-30 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '016_farm_system'
down_revision: Union[str, None] = '015_learning_links'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'farm_templates' not in tables:
        op.create_table(
            'farm_templates',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('key', sa.String(32), nullable=False, unique=True),
            sa.Column('name', sa.String(64), nullable=False),
            sa.Column('description', sa.String(256), nullable=True),
            sa.Column('style_class', sa.String(32), nullable=False),
            sa.Column('tree_emoji', sa.String(16), server_default='🌳'),
            sa.Column('crop_items', sa.Text(), nullable=True),
            sa.Column('animal_items', sa.Text(), nullable=True),
            sa.Column('status', sa.String(16), server_default='on'),
            sa.Column('sort_order', sa.Integer(), server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    if 'farms' not in tables:
        op.create_table(
            'farms',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True),
            sa.Column('name', sa.String(64), nullable=False),
            sa.Column('template_id', sa.Integer(), sa.ForeignKey('farm_templates.id'), nullable=True),
            sa.Column('energy_balance', sa.Integer(), server_default='0'),
            sa.Column('total_energy_earned', sa.Integer(), server_default='0'),
            sa.Column('tree_energy', sa.Integer(), server_default='0'),
            sa.Column('tree_stage', sa.Integer(), server_default='0'),
            sa.Column('forest_count', sa.Integer(), server_default='0'),
            sa.Column('backfilled', sa.Boolean(), server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_farms_user_id', 'farms', ['user_id'])

    if 'farm_plots' not in tables:
        op.create_table(
            'farm_plots',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('farm_id', sa.Integer(), sa.ForeignKey('farms.id'), nullable=False),
            sa.Column('plot_type', sa.String(8), nullable=False),
            sa.Column('item_key', sa.String(32), nullable=False),
            sa.Column('status', sa.String(16), server_default='growing'),
            sa.Column('energy_cost', sa.Integer(), server_default='0'),
            sa.Column('reward_energy', sa.Integer(), server_default='0'),
            sa.Column('planted_at', sa.DateTime(), nullable=True),
            sa.Column('mature_at', sa.DateTime(), nullable=True),
            sa.Column('harvested_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_farm_plots_farm_id', 'farm_plots', ['farm_id'])

    if 'farm_energy_log' not in tables:
        op.create_table(
            'farm_energy_log',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('farm_id', sa.Integer(), sa.ForeignKey('farms.id'), nullable=False),
            sa.Column('source', sa.String(24), nullable=False),
            sa.Column('delta', sa.Integer(), nullable=False),
            sa.Column('balance_after', sa.Integer(), nullable=False),
            sa.Column('ref_id', sa.Integer(), nullable=True),
            sa.Column('note', sa.String(128), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_farm_energy_log_user_id', 'farm_energy_log', ['user_id'])
        op.create_index('ix_farm_energy_log_farm_id', 'farm_energy_log', ['farm_id'])
        op.create_index('ix_farm_energy_log_user_time', 'farm_energy_log', ['user_id', 'created_at'])

    # site_config: farm_default_name（站点级默认乐园名，可空，幂等）
    if 'site_config' in tables:
        columns = {c['name'] for c in inspector.get_columns('site_config')}
        if 'farm_default_name' not in columns:
            op.add_column('site_config', sa.Column('farm_default_name', sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'site_config' in tables:
        columns = {c['name'] for c in inspector.get_columns('site_config')}
        if 'farm_default_name' in columns:
            with op.batch_alter_table('site_config') as batch:
                batch.drop_column('farm_default_name')

    if 'farm_energy_log' in tables:
        op.drop_table('farm_energy_log')
    if 'farm_plots' in tables:
        op.drop_table('farm_plots')
    if 'farms' in tables:
        op.drop_table('farms')
    if 'farm_templates' in tables:
        op.drop_table('farm_templates')
