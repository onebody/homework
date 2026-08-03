"""列表分页统一工具。

约定所有分页接口的响应结构一致，便于前端复用同一套分页控件：

    {"items": [...], "total": 123, "page": 1, "size": 20, "pages": 7}

- page 从 1 开始；size 受 MAX_PAGE_SIZE 限制，防止被构造超大 size 拖垮数据库；
- page 越界时向有效区间收敛（如删到只剩 1 页时停留在末页），不返回 4xx，
  避免前端停在空页需要额外处理。
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

# 默认每页条数：后台管理 20 条，学生/家长端 5 条
ADMIN_PAGE_SIZE = 20
CLIENT_PAGE_SIZE = 5
MAX_PAGE_SIZE = 100

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """分页响应模型（供 response_model 使用）。"""

    items: list[T] = []
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 1


def normalize(page: int, size: int, total: int, default_size: int = ADMIN_PAGE_SIZE) -> tuple[int, int, int]:
    """规整分页参数，返回 (page, size, pages)。"""
    size = size if size and size > 0 else default_size
    size = min(size, MAX_PAGE_SIZE)
    pages = max(1, -(-total // size))  # 向上取整
    page = max(1, min(page or 1, pages))
    return page, size, pages


def paginate(query, page: int, size: int, default_size: int = ADMIN_PAGE_SIZE) -> tuple[list, dict]:
    """对 SQLAlchemy Query 分页，返回 (当页对象列表, 分页元信息)。

    调用方负责先完成 filter/order_by，本函数只做 count + offset/limit。
    """
    total = query.count()
    page, size, pages = normalize(page, size, total, default_size)
    items = query.offset((page - 1) * size).limit(size).all()
    return items, {"total": total, "page": page, "size": size, "pages": pages}


def paginate_list(rows: list, page: int, size: int, default_size: int = ADMIN_PAGE_SIZE) -> tuple[list, dict]:
    """对内存中已聚合的列表分页（服务层返回 dict 列表时使用）。"""
    total = len(rows)
    page, size, pages = normalize(page, size, total, default_size)
    start = (page - 1) * size
    return rows[start:start + size], {"total": total, "page": page, "size": size, "pages": pages}
