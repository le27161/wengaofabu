# -*- coding: utf-8 -*-
"""分页小工具：返回 (当前页数据, 总数)"""
from sqlalchemy import func


def paginate(query, page: int = 1, page_size: int = 10):
    """对查询对象执行分页。注意：query 需为 Query 对象，计数使用子查询去重，避免 join 导致总数虚高"""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    total = query.order_by(None).count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return rows, total


def count_group(db, model, column, filters=None):
    """通用分组计数：返回 {key: count}"""
    query = db.query(column, func.count()).group_by(column)
    if filters is not None:
        query = query.filter(filters)
    return dict(query.all())

