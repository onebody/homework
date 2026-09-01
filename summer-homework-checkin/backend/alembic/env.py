"""Alembic migration environment configuration.

支持自动检测 SQLAlchemy 模型变更并生成迁移脚本。
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 导入所有模型以确保 Base.metadata 包含完整表结构
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import Base
from app import models  # noqa: F401
from app.config import DATABASE_URL

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DB 路径以 DB_PATH 环境变量为准（与 migrate.py/应用一致）：
# alembic.ini 内的 sqlite:///app.db 仅是占位默认值，
# 避免直接运行 alembic upgrade 时误操作错误数据库。
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    # 空库且无版本记录：历史迁移 001 依赖既有库，直接重放会漏建早期表；
    # 与 migrate.py 首部署对齐：create_all 建全表后 stamp head。
    # 注意：检查必须用独立连接，避免 inspect 触发 autobegin 污染迁移事务。
    from sqlalchemy import inspect as sa_inspect, text as sa_text
    with connectable.connect() as check_conn:
        tables = sa_inspect(check_conn).get_table_names()
    if not tables or ("alembic_version" not in tables and "users" not in tables):
        with connectable.begin() as conn:
            Base.metadata.create_all(bind=conn)
            from alembic.script import ScriptDirectory
            script = ScriptDirectory.from_config(config)
            head = script.get_current_head()
            conn.execute(sa_text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
            conn.execute(sa_text("DELETE FROM alembic_version"))
            conn.execute(sa_text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head})
        return
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
