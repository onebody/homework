"""时间工具：系统统一使用北京时间（UTC+8）。

设计约定：
- 数据库所有 DateTime 列统一存储 naive 北京时间（历史 UTC 数据已由
  alembic 003 迁移整体 +8 小时）；
- 写库/比较一律使用 now_local()，避免 offset-naive 与 offset-aware
  datetime 混用引发比较错误；
- 容器同时设置 TZ=Asia/Shanghai，保证 date.today() 等隐式本地调用一致。
"""
from datetime import datetime, timedelta, timezone

BJT = timezone(timedelta(hours=8))


def now_local() -> datetime:
    """当前北京时间（naive，用于写库与展示）。"""
    return datetime.now(BJT).replace(tzinfo=None)
