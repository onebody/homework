"""自动迁移入口：在应用启动前执行数据库迁移和种子数据初始化。

用法：
    python migrate.py              # 执行迁移 + 种子数据（Docker CMD 默认）
    python migrate.py --migrate    # 仅执行迁移
    python migrate.py --seed       # 仅执行种子数据
    python migrate.py --backup     # 仅备份数据库
"""
import os
import sys
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DB_PATH
from app.database import engine, Base


def backup_db():
    """备份当前数据库文件。"""
    if not os.path.exists(DB_PATH):
        print("ℹ️  数据库文件不存在，跳过备份")
        return
    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"app_{ts}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ 数据库已备份到: {backup_path}")


def run_migrations():
    """执行 Alembic 数据库迁移。"""
    print("🔄 开始数据库迁移...")
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory

    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")

    # 检查数据库是否已有表（非首次部署）
    db_exists = os.path.exists(DB_PATH)
    has_alembic_version = False
    has_alembic_record = False  # alembic_version 表是否有版本记录
    has_users_table = False

    if db_exists:
        import sqlite3
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            # 检查 alembic_version 表
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
            )
            has_alembic_version = cursor.fetchone() is not None
            # 检查是否有版本记录
            if has_alembic_version:
                cursor.execute("SELECT COUNT(*) FROM alembic_version")
                has_alembic_record = cursor.fetchone()[0] > 0
            # 检查 users 表（核心表）
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            has_users_table = cursor.fetchone() is not None
            conn.close()
        except Exception:
            pass

    if not db_exists or not has_users_table:
        # 首次部署：数据库不存在或无表，用 create_all 建表
        print(" 首次部署，使用 create_all 创建表结构...")
        Base.metadata.create_all(bind=engine)
        _stamp_initial_revision()
        print("✅ 表结构创建完成")
    elif not has_alembic_record:
        # 已有数据但未追踪迁移版本（表存在但 alembic_version 为空）：stamp 到初始版本
        print(" 已有数据库但未追踪迁移版本，标记为初始版本...")
        _stamp_initial_revision()
        print("✅ 迁移版本已标记，表结构已存在，跳过迁移")
    else:
        # 正常迁移流程
        try:
            command.upgrade(alembic_cfg, "head")
            print("✅ 数据库迁移完成")
        except Exception as e:
            if "no such table" in str(e).lower():
                # 迁移脚本引用了不存在的表，兜底用 create_all
                print("ℹ️  部分表缺失，使用 create_all 补充...")
                Base.metadata.create_all(bind=engine)
                print("✅ 表结构已补充")
            else:
                print(f"⚠️  迁移异常: {e}")
                print("ℹ️  使用 create_all 确保表结构存在...")
                Base.metadata.create_all(bind=engine)
                print("✅ 表结构已确保存在")


def _stamp_initial_revision():
    """为数据库标记初始迁移版本。"""
    try:
        from alembic.script import ScriptDirectory
        from alembic.config import Config
        alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "alembic.ini"))
        alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_PATH}")
        script = ScriptDirectory.from_config(alembic_cfg)
        head = script.get_current_head()
        if not head:
            print(" 未找到迁移版本，跳过 stamp")
            return
        # 直接使用 sqlite3 写入版本记录，避免 alembic stamp 的编码问题
        import sqlite3
        db_path_str = str(DB_PATH)
        conn = sqlite3.connect(db_path_str)
        conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("DELETE FROM alembic_version")
        conn.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (head,))
        conn.commit()
        conn.close()
        print(f" 已标记迁移版本: {head}")
    except Exception as e:
        print(f"⚠️  stamp 失败: {e}")


def run_seed():
    """执行种子数据初始化（幂等）。"""
    print("🌱 开始种子数据初始化...")
    from seed import seed
    seed()


def main():
    args = sys.argv[1:]

    if "--backup" in args:
        backup_db()
        return

    if "--migrate" in args:
        run_migrations()
        return

    if "--seed" in args:
        run_seed()
        return

    # 默认：完整流程（迁移 + 种子数据）
    backup_db()
    run_migrations()
    run_seed()
    print("🚀 数据库准备就绪")


if __name__ == "__main__":
    main()
