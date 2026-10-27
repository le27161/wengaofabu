# -*- coding: utf-8 -*-
"""文稿接口：前台浏览 + 编辑写作 + 管理列表

审核状态机：draft(草稿) → pending_first(待一审) → pending_second(待二审) → published(已发布)
                                                              ↘ rejected(已驳回，可修改后重新提交)
              published → offline(已下线，可重新编辑后再次提审) → pending_first → ... → published
开启系统配置 auto_review（自动审核）后，提审即自动通过两级审核并发布。
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import settings
from ..core.deps import get_current_user, get_optional_user, require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.article import Article, article_categories
from ..models.category import Category
from ..models.channel import Channel
from ..models.ai_call import AICallLog
from ..models.ai_correction import AICorrection
from ..models.ai_task import AITask
from ..models.review import ArticleReview
from ..models.user import User
from ..models.view_history import ViewHistory
from ..schemas.article import ArticleIn, ArticleSelectionExplainIn
from ..schemas.article_writing import ArticleWritingResponse
from ..services import embedding_service
from ..services.ai_service import AIServiceError
from ..services.article_import_service import import_excel
from ..services.article_summary_service import explain_article_selection, summarize_article
from ..services.llm_provider import OpenAICompatibleLLMProvider
from ..services.settings_service import get_setting
from ..services.smart_collect_article_service import SmartCollectArticleService
from ..services.smart_collect_article_writing_service import (
    SmartCollectArticleWritingConfigError,
    SmartCollectArticleWritingDataError,
    SmartCollectArticleWritingEmptyResponseError,
    SmartCollectArticleWritingError,
    SmartCollectArticleWritingJsonError,
    SmartCollectArticleWritingModelError,
    SmartCollectArticleWritingNotFoundError,
    SmartCollectArticleWritingPermissionError,
    SmartCollectArticleWritingSafetyError,
    SmartCollectArticleWritingSchemaError,
    SmartCollectArticleWritingService,
    SmartCollectArticleWritingStatusError,
    SmartCollectArticleWritingSynthesisStatusError,
    SmartCollectArticleWritingTimeoutError,
    SmartCollectArticleWritingUnsupportedError,
)
from ..services.text_utils import strip_html
from ..services.rag_news_service import (
    remove_article_from_rag_safely,
    sync_published_article_safely,
)
from ..services.recommendation_service import recommend_articles as legacy_recommend_articles
from .recommend import recommend_articles as preference_recommend_articles

router = APIRouter(prefix="/articles", tags=["文稿"])

# 可编辑状态：草稿 / 驳回稿 / 已下线稿（下线稿编辑后状态保持 offline，重新提审再进入审核流）
EDITABLE_STATUS = ("draft", "rejected", "offline")

# 后台列表可排序字段白名单（sort_by 参数 → ORM 列），防止注入任意排序列
ADMIN_SORT_FIELDS = {
    "updated_at": Article.updated_at,
    "created_at": Article.created_at,
    "published_at": Article.published_at,
    "view_count": Article.view_count,
    "like_count": Article.like_count,
    "favorite_count": Article.favorite_count,
    "share_count": Article.share_count,
}

# sort_by 查询参数校验模式（与 ADMIN_SORT_FIELDS 保持同步）
SORT_BY_PATTERN = "^(updated_at|created_at|published_at|view_count|like_count|favorite_count|share_count)$"


def _can_manage(article: Article, user: User) -> bool:
    """判断用户是否为作者或管理员"""
    if user is None:
        return False
    return user.role == "admin" or article.author_id == user.id


def get_article_writing_llm_provider() -> OpenAICompatibleLLMProvider:
    """复用现有OpenAI兼容LLMProvider；测试可在任何模型调用前注入Fake。"""
    return OpenAICompatibleLLMProvider(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
    )


def _raise_article_writing_http_error(exc: Exception) -> None:
    """只向编辑返回稳定业务提示，不泄露供应商响应或密钥。"""
    if isinstance(exc, SmartCollectArticleWritingNotFoundError):
        raise HTTPException(404, exc.message) from None
    if isinstance(exc, SmartCollectArticleWritingPermissionError):
        raise HTTPException(403, exc.message) from None
    if isinstance(
        exc,
        (
            SmartCollectArticleWritingStatusError,
            SmartCollectArticleWritingUnsupportedError,
            SmartCollectArticleWritingSynthesisStatusError,
        ),
    ):
        raise HTTPException(409, exc.message) from None
    if isinstance(exc, SmartCollectArticleWritingConfigError):
        raise HTTPException(503, exc.message) from None
    if isinstance(exc, SmartCollectArticleWritingTimeoutError):
        raise HTTPException(504, exc.message) from None
    if isinstance(exc, SmartCollectArticleWritingDataError):
        raise HTTPException(500, exc.message) from None
    if isinstance(
        exc,
        (
            SmartCollectArticleWritingEmptyResponseError,
            SmartCollectArticleWritingJsonError,
            SmartCollectArticleWritingSchemaError,
            SmartCollectArticleWritingModelError,
            SmartCollectArticleWritingSafetyError,
        ),
    ):
        raise HTTPException(502, exc.message) from None
    raise HTTPException(502, SmartCollectArticleWritingError.message) from None


def _apply_categories(db: Session, article: Article, category_ids: list[int]):
    """重新设置文稿所属栏目（多对多）"""
    ids = list(dict.fromkeys(category_ids))  # 去重
    cats = db.query(Category).filter(Category.id.in_(ids)).all() if ids else []
    article.categories = cats


def _apply_channels(db: Session, article: Article, channel_ids: list[int]):
    """重置文稿分发渠道：基础渠道（is_default）始终包含且不可移除"""
    default = db.query(Channel).filter(Channel.is_default.is_(True)).first()
    ids = list(dict.fromkeys([*(channel_ids or []), default.id])) if default else list(dict.fromkeys(channel_ids or []))
    channels = db.query(Channel).filter(Channel.id.in_(ids), Channel.status == "active").all() if ids else []
    if default and default not in channels:
        channels.append(default)
    article.channels = channels


@router.get("", summary="前台文稿列表（仅已发布）")
def list_articles(
    category_id: int | None = Query(default=None, description="按栏目筛选"),
    keyword: str | None = Query(default=None, description="标题/摘要关键词"),
    city: str | None = Query(default=None, description="按城市筛选（同城搜索），如 深圳"),
    sort: str = Query(default="latest", pattern="^(latest|hot)$", description="latest 最新 / hot 最热"),
    page: int = 1,
    page_size: int = 12,
    db: Session = Depends(get_db),
):
    query = db.query(Article).filter(Article.status == "published")
    if category_id:
        query = query.join(article_categories, Article.id == article_categories.c.article_id) \
                     .filter(article_categories.c.category_id == category_id)
    if keyword:
        query = query.filter(or_(Article.title.like(f"%{keyword}%"), Article.summary.like(f"%{keyword}%")))
    if city:
        query = query.filter(Article.city == city)

    if sort == "hot":
        query = query.order_by(Article.view_count.desc(), Article.published_at.desc())
    else:
        query = query.order_by(Article.published_at.desc())

    rows, total = paginate(query, page, page_size)
    return {"items": [a.to_dict() for a in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/cities", summary="已发布文稿覆盖的城市列表（同城搜索下拉）")
def list_cities(db: Session = Depends(get_db)):
    """返回所有已发布文稿中出现过的城市（去重、非空），供前台城市下拉选择。"""
    rows = (
        db.query(Article.city)
        .filter(
            Article.status == "published",
            Article.city.isnot(None),
            Article.city != "",
        )
        .distinct()
        .order_by(Article.city.asc())
        .all()
    )
    return {"items": [r[0] for r in rows]}


@router.get("/mine", summary="我的文稿（编辑/管理员）")
def my_articles(
    status: str | None = Query(default=None, description="按状态筛选"),
    keyword: str | None = Query(default=None, description="标题/摘要关键词"),
    category_id: int | None = Query(default=None, description="按栏目筛选"),
    sort_by: str = Query(default="created_at", pattern=SORT_BY_PATTERN, description="排序字段"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="排序方向"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 编辑功能：编辑 / 管理员（moderator）/ 系统管理员
    if user.role not in ("editor", "moderator", "admin"):
        raise HTTPException(403, "仅编辑可写作文稿")
    query = db.query(Article).filter(Article.author_id == user.id)
    if status:
        query = query.filter(Article.status == status)
    if keyword:
        query = query.filter(or_(Article.title.like(f"%{keyword}%"), Article.summary.like(f"%{keyword}%")))
    if category_id:
        query = query.join(article_categories, Article.id == article_categories.c.article_id) \
                     .filter(article_categories.c.category_id == category_id)
    sort_column = ADMIN_SORT_FIELDS.get(sort_by, Article.created_at)
    query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())
    rows, total = paginate(query, page, page_size)
    return {"items": [a.to_dict() for a in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/admin", summary="后台全部文稿（管理员）")
def admin_articles(
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    category_id: int | None = Query(default=None),
    sort_by: str = Query(default="created_at", pattern=SORT_BY_PATTERN, description="排序字段"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="排序方向"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    query = db.query(Article)
    if status:
        query = query.filter(Article.status == status)
    if keyword:
        query = query.filter(or_(Article.title.like(f"%{keyword}%"), Article.summary.like(f"%{keyword}%")))
    if category_id:
        query = query.join(article_categories, Article.id == article_categories.c.article_id) \
                     .filter(article_categories.c.category_id == category_id)
    # 服务端排序：白名单字段 + 方向，默认 created_at 降序（新文稿优先）
    sort_column = ADMIN_SORT_FIELDS.get(sort_by, Article.created_at)
    query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())
    rows, total = paginate(query, page, page_size)
    return {"items": [a.to_dict() for a in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/recommend/portal", summary="门户为你推荐（原dev向量/通用推荐逻辑）")
def portal_recommend_articles(
    limit: int = Query(default=8, ge=1, le=20, description="返回推荐文稿数量"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """门户“为你推荐”使用原dev推荐链路，避免被偏好/行为推荐逻辑替换。"""
    items = legacy_recommend_articles(db, user, limit)
    if not items:
        raise HTTPException(400, "暂无已发布文稿可推荐")
    return {"items": [a.to_dict() for a in items], "total": len(items)}


@router.get("/recommend", summary="用户个性化推荐（可选登录，默认 8 篇）")
def user_recommend_articles(
    limit: int = Query(default=8, ge=1, le=20, description="返回推荐文稿数量"),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """个性化推荐已发布文稿（四段式：向量召回 KNN + 精排预留 + 热门兜底）

    接口说明：
    - 可选登录：请求头携带 Bearer Token 时按用户画像推荐；不携带时走通用推荐。
    - 登录且观看历史 >= 20 篇：取最近 20 篇观看文稿，用与入库相同的向量模型
      （BAAI_bge-small-zh）和文本规则（"分类：标题"）向量化，按观看时长加权平均
      得到用户向量，再与进程内存中的全量已发布文稿向量做 KNN 余弦相似度召回 top-50；
      过滤已观看/不感兴趣后，候选不足时按热度补齐，最终返回 limit 篇。
    - 未登录或观看历史不足 20 篇：走通用推荐（偏好 0.3 + 新鲜度 0.4 + 热度 0.3
      + 随机扰动 + 分类多样性）。
    - 每次请求对相似度/热度加入随机扰动，保证不同用户、不同请求的结果尽量不同。

    请求参数：
    - limit: 返回推荐文稿数量，默认 8，取值 1~20，越界返回 422。

    成功响应（200）：
        {
          "items": [Article.to_dict() 列表],  // 不含正文/审核记录，含标题/摘要/封面/计数/栏目/发布时间
          "total": 8                          // 实际返回条数（候选不足时 < limit）
        }

    错误语义：
    - 400: 没有任何已发布文稿可推荐
    - 422: limit 不在 1~20 区间

    注意事项：
    - 观看历史（view_history）只在访问文稿详情页 GET /articles/{id} 时写入，
      POST /events 埋点不写历史，仅累加浏览量。
    - 首次触发向量分支会加载向量模型（约几十秒），之后模型常驻内存；
      若向量化失败会自动回退通用推荐，不阻断接口。
    - 算法细节与调参说明见 docs/article_recommend_spec.md。
    """
    return preference_recommend_articles(db=db, user=user, limit=limit)


@router.post(
    "/{article_id}/ai-writing",
    response_model=ArticleWritingResponse,
    summary="根据关联的已确认事实生成文稿写作建议",
)
async def generate_article_writing_suggestion(
    article_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """只返回预览建议；不保存Article、不修改Synthesis、不触发审核。"""
    service = SmartCollectArticleWritingService(get_article_writing_llm_provider())
    try:
        return await service.generate(db, article_id, user)
    except SmartCollectArticleWritingError as exc:
        _raise_article_writing_http_error(exc)


@router.get("/{article_id}", summary="文稿详情（未发布稿仅作者/系统管理员/审核管理员可见）")
def get_article(article_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")
    # 未发布文稿仅作者、系统管理员、审核管理员（moderator）可见：
    # 审核人需要读取待审/待二审稿件的正文内容，否则无法执行审核
    if article.status != "published" and not (
        _can_manage(article, user) or (user is not None and user.role in ("admin", "moderator"))
    ):
        raise HTTPException(403, "该文稿尚未发布")
    # 记录观看历史：登录用户浏览已发布文稿时写入/更新 view_history
    # （同一文稿重复观看仅更新时间，历史列表按最近观看时间倒序）
    if user is not None and article.status == "published":
        history = db.query(ViewHistory).filter_by(user_id=user.id, article_id=article.id).first()
        if history:
            history.viewed_at = datetime.now()
        else:
            db.add(ViewHistory(user_id=user.id, article_id=article.id, viewed_at=datetime.now()))
        db.commit()
    can_manage = _can_manage(article, user)
    data = article.to_dict(include_content=True, include_reviews=can_manage)
    if can_manage:
        data["smart_collect"] = SmartCollectArticleService.get_editorial_context(
            db,
            article,
        )
    return data


@router.post("/{article_id}/ai-summary", summary="按需生成文章全文总结")
async def generate_article_summary(
    article_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """用户主动点击后生成总结，结果不写入数据库。"""
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")
    if not get_setting(db, "portal_ai_reading_enabled", default=True):
        raise HTTPException(403, "门户 AI 阅读功能已关闭")
    if article.status != "published" and not (_can_manage(article, user) or (user is not None and user.role == "moderator")):
        raise HTTPException(403, "该文稿尚未发布")
    try:
        result = await summarize_article(article)
    except AIServiceError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception:
        # 不向前端暴露模型供应商的原始异常，避免页面显示 500 技术错误。
        raise HTTPException(503, "AI 服务暂时不可用，请稍后重新尝试") from None
    return {"message": "AI 全文总结生成成功", "data": result}


@router.post("/{article_id}/ai-selection-explanation", summary="解释用户划选的文章正文")
async def generate_article_selection_explanation(
    article_id: int,
    body: ArticleSelectionExplainIn,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """只解释当前文章正文中的划选文字，结果不写入数据库。"""
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")
    if not get_setting(db, "portal_ai_reading_enabled", default=True):
        raise HTTPException(403, "门户 AI 阅读功能已关闭")
    if article.status != "published" and not (_can_manage(article, user) or (user is not None and user.role == "moderator")):
        raise HTTPException(403, "该文稿尚未发布")
    try:
        result = await explain_article_selection(article, body.selected_text)
    except AIServiceError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception:
        # 保持与全文总结一致的安全兜底，避免异常中断文章阅读页面。
        raise HTTPException(503, "AI 服务暂时不可用，请稍后重新尝试") from None
    return {"message": "AI 划选内容解释生成成功", "data": result}


@router.get("/{article_id}/related", summary="相关推荐（同栏目已发布文稿，按发布时间新到旧）")
def related_articles(
    article_id: int,
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """查找与当前文稿同栏目的其他已发布文稿，按发布时间倒序返回。
    若文稿未挂任何栏目，则兜底返回最新发布的文稿，避免推荐区为空。
    """
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")

    query = db.query(Article).filter(
        Article.status == "published",
        Article.id != article_id,
    )
    category_ids = [c.id for c in article.categories]
    if category_ids:
        # 同栏目：与该文稿共享任一栏目的其他已发布文稿（join 会重复，需去重）
        query = (
            query.join(article_categories, Article.id == article_categories.c.article_id)
            .filter(article_categories.c.category_id.in_(category_ids))
            .distinct()
        )

    rows = (
        query.order_by(Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return {"items": [a.to_dict() for a in rows]}


def _bind_ai_records_by_draft_key(db: Session, article_id: int, draft_key: str | None) -> None:
    """把草稿会话（draft_key）产生的 AI 任务/调用记录/纠正样本回填到正式文稿ID（幂等，仅回填未绑定行）"""
    if not draft_key:
        return
    for model in (AITask, AICallLog, AICorrection):
        db.query(model).filter(
            model.draft_key == draft_key,
            model.article_id.is_(None),
        ).update({"article_id": article_id}, synchronize_session=False)


@router.post("", summary="创建文稿（编辑/管理员，先存为草稿）")
def create_article(body: ArticleIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # 编辑功能：编辑 / 管理员（moderator）/ 系统管理员
    if user.role not in ("editor", "moderator", "admin"):
        raise HTTPException(403, "仅编辑可写作文稿")
    article = Article(
        title=body.title,
        summary=body.summary,
        content=body.content,
        # 纯文本正文：前端随稿提交，缺失时后端从 HTML 剥离兜底
        content_source=body.content_source or strip_html(body.content),
        cover_url=body.cover_url,
        author_id=user.id,
        status="draft",
    )
    db.add(article)
    db.flush()
    _apply_categories(db, article, body.category_ids)
    _apply_channels(db, article, body.channel_ids)
    # 回填 AI 协作台在未保存阶段产生的记录（同事务，保存即关联）
    _bind_ai_records_by_draft_key(db, article.id, body.draft_key)
    db.commit()
    db.refresh(article)
    # 向量化入库：尽力而为，向量化失败不影响草稿保存（全量回填接口可修复）
    if embedding_service.sync_article_embedding(db, article):
        db.commit()
    # 新文章入库后异步触发 AI 关键词提取（不阻塞创建流程，内部独立 session）
    content = article.content_source or strip_html(article.content or "")
    if content and content.strip():
        from .keywords import extract_and_save_keywords
        background_tasks.add_task(extract_and_save_keywords, article.id, content)
    return {"message": "草稿已保存", "article": article.to_dict()}


@router.post("/import", summary="批量导入文稿（Excel：封面/标题/分类/正文，编辑/管理员）")
def import_articles(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description=".xlsx 文件"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传 Excel 批量创建草稿；封面缺失/下载失败不丢弃文稿（封面留空），结果逐行统计"""
    if user.role not in ("editor", "moderator", "admin"):
        raise HTTPException(403, "仅编辑可导入文稿")
    data = file.file.read()
    result = import_excel(db, user, data, file.filename or "")
    # 导入成功后异步触发关键词提取（不阻塞导入流程，内部独立 session）
    from .keywords import extract_keywords_by_article_id
    for article_id in result.get("created_ids", []):
        background_tasks.add_task(extract_keywords_by_article_id, article_id)
    return {
        "message": f"导入完成：成功 {result['imported']}，跳过 {len(result['skipped'])}，失败 {len(result['failed'])}",
        **result,
    }


@router.put("/{article_id}", summary="编辑文稿（作者或管理员，草稿/驳回稿/已下线稿可编辑）")
def update_article(
    article_id: int,
    body: ArticleIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")
    if not _can_manage(article, user):
        raise HTTPException(403, "只能编辑自己的文稿")
    if article.status not in EDITABLE_STATUS:
        raise HTTPException(400, f"当前状态（{article.status}）不允许编辑，请先驳回或新建草稿")

    old_content = article.content_source or strip_html(article.content or "")
    article.title = body.title
    article.summary = body.summary
    article.content = body.content
    article.content_source = body.content_source or strip_html(body.content)
    article.cover_url = body.cover_url
    _apply_categories(db, article, body.category_ids)
    _apply_channels(db, article, body.channel_ids)
    # 回填 AI 协作台记录（防多步保存场景；不传 draft_key 时无副作用）
    _bind_ai_records_by_draft_key(db, article.id, body.draft_key)
    db.commit()
    db.refresh(article)
    # 向量化入库：标题/分类未变时跳过；尽力而为，失败不影响保存
    if embedding_service.sync_article_embedding(db, article):
        db.commit()
    # 正文变化后异步重新提取关键词（失败保留旧知识链，不阻塞保存）
    new_content = article.content_source or strip_html(article.content or "")
    if new_content and new_content != old_content:
        from .keywords import extract_and_save_keywords
        background_tasks.add_task(extract_and_save_keywords, article.id, new_content, True)
    return {"message": "保存成功", "article": article.to_dict()}


@router.post("/{article_id}/submit", summary="提交审核（草稿/驳回稿/已下线稿 → 待一审）")
def submit_article(
    article_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")
    if not _can_manage(article, user):
        raise HTTPException(403, "只能提交自己的文稿")
    if article.status not in ("draft", "rejected", "offline"):
        raise HTTPException(400, f"当前状态（{article.status}）不能提交审核")
    if not article.categories:
        raise HTTPException(400, "请先选择至少一个栏目再提交审核")

    # 自动审核开关：开启后提审即自动通过一审、二审并发布，同时写入两条系统审核记录
    if get_setting(db, "auto_review", default=False):
        article.status = "published"
        article.published_at = datetime.now()
        db.add(ArticleReview(
            article_id=article.id, reviewer_id=None, review_level=1,
            action="approve", comment="系统自动审核：一审通过",
        ))
        db.add(ArticleReview(
            article_id=article.id, reviewer_id=None, review_level=2,
            action="approve", comment="系统自动审核：二审通过",
        ))
        db.commit()
        # 自动审核直接发布：事务提交成功后再异步同步新闻知识库。
        background_tasks.add_task(sync_published_article_safely, article.id)
        return {"message": "自动审核已开启，文稿已自动通过并发布", "article": article.to_dict()}

    article.status = "pending_first"
    db.commit()
    return {"message": "已提交一审", "article": article.to_dict()}


@router.post("/{article_id}/offline", summary="下线已发布文稿（管理员）")
def offline_article(
    article_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")
    if article.status != "published":
        raise HTTPException(400, "仅已发布文稿可下线")
    article.status = "offline"
    db.commit()
    # 下线成功后清理向量，避免 AI 继续引用已下线新闻。
    background_tasks.add_task(remove_article_from_rag_safely, article_id)
    return {"message": "文稿已下线", "article": article.to_dict()}


@router.delete("/{article_id}", summary="删除文稿（作者或管理员）")
def delete_article(
    article_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "文稿不存在")
    if not _can_manage(article, user):
        raise HTTPException(403, "只能删除自己的文稿")
    db.delete(article)
    db.commit()
    # 数据库删除成功后异步清理 RAG，RAG 故障不影响删除结果。
    background_tasks.add_task(remove_article_from_rag_safely, article_id)
    return {"message": "删除成功"}
