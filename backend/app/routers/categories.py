# -*- coding: utf-8 -*-
"""栏目管理接口：前台读取启用栏目，后台（管理员）增删改查"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..database import get_db
from ..models.article import Article, article_categories
from ..models.category import Category
from ..schemas.category import CategoryIn

router = APIRouter(prefix="/categories", tags=["栏目"])


def _category_counts(db: Session, status_filter=None):
    """统计每个栏目下的已发布文稿数量"""
    query = (
        db.query(article_categories.c.category_id, func.count(article_categories.c.article_id))
        .join(Article, Article.id == article_categories.c.article_id)
    )
    if status_filter:
        query = query.filter(Article.status == status_filter)
    return dict(query.group_by(article_categories.c.category_id).all())


@router.get("", summary="前台栏目列表（仅启用）")
def public_categories(db: Session = Depends(get_db)):
    cats = db.query(Category).filter(Category.status == "active").order_by(Category.sort_order).all()
    counts = _category_counts(db, "published")
    return {"items": [c.to_dict(counts.get(c.id, 0)) for c in cats]}


@router.get("/manage", summary="后台栏目管理列表（含隐藏栏目与文稿数）")
def manage_categories(db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    cats = db.query(Category).order_by(Category.sort_order).all()
    counts = _category_counts(db)
    return {"items": [c.to_dict(counts.get(c.id, 0)) for c in cats]}


@router.post("", summary="创建栏目")
def create_category(body: CategoryIn, db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    if db.query(Category).filter(Category.slug == body.slug).first():
        raise HTTPException(400, "栏目标识已存在")
    cat = Category(name=body.name, slug=body.slug, description=body.description,
                   sort_order=body.sort_order, status=body.status)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"message": "创建成功", "category": cat.to_dict()}


@router.put("/{category_id}", summary="编辑栏目")
def update_category(category_id: int, body: CategoryIn, db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "栏目不存在")
    dup = db.query(Category).filter(Category.slug == body.slug, Category.id != category_id).first()
    if dup:
        raise HTTPException(400, "栏目标识已存在")
    cat.name = body.name
    cat.slug = body.slug
    cat.description = body.description
    cat.sort_order = body.sort_order
    cat.status = body.status
    db.commit()
    db.refresh(cat)
    return {"message": "保存成功", "category": cat.to_dict()}


@router.delete("/{category_id}", summary="删除栏目（自动解除与文稿的关联）")
def delete_category(category_id: int, db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "栏目不存在")
    db.delete(cat)
    db.commit()
    return {"message": "删除成功"}

