# -*- coding: utf-8 -*-
"""智能采编接口：临时搜索、持久化任务、历史列表与任务详情。"""
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..core.deps import require_roles
from ..core.pagination import paginate
from ..database import SessionLocal, get_db
from ..models.smart_collect import SmartCollectTask
from ..models.user import User
from ..schemas.smart_collect import (
    SmartCollectEventAddCluesRequest,
    SmartCollectEventCreateRequest,
    SmartCollectEventDeleteResponse,
    SmartCollectEventListResponse,
    SmartCollectEventMutationResponse,
    SmartCollectEventUpdateRequest,
    EventEvidencePack,
    SmartCollectContentDetail,
    SmartCollectContentPrepareResponse,
    SmartCollectArticleCreateResponse,
    SmartCollectEvaluationOutliers,
    SmartCollectEvaluationSummary,
    SmartCollectSearchRequest,
    SmartCollectSearchResponse,
    SmartCollectSynthesisListResponse,
    SmartCollectSynthesisResponse,
    SmartCollectSimilarityResponse,
    SmartCollectRelevanceUpdateRequest,
    SmartCollectRelevanceUpdateResponse,
    SmartCollectTaskCreateResponse,
    SmartCollectTaskDetail,
    SmartCollectTaskListResponse,
)
from ..services.embedding_service import EmbeddingServiceError, get_embedding_service
from ..services.content_provider import TavilyContentProvider
from ..services.search_service import SearchService, SearchServiceError
from ..services.smart_collect_evaluation_service import SmartCollectEvaluationService
from ..services.smart_collect_content_service import (
    SmartCollectContentNotFoundError,
    SmartCollectContentPersistenceError,
    SmartCollectContentService,
)
from ..services.smart_collect_article_service import (
    SmartCollectArticleAlreadyExistsError,
    SmartCollectArticleDataError,
    SmartCollectArticleError,
    SmartCollectArticleNotFoundError,
    SmartCollectArticlePersistenceError,
    SmartCollectArticleService,
    SmartCollectArticleStatusError,
    SmartCollectArticleValidationError,
)
from ..services.smart_collect_event_service import (
    SmartCollectEventClueNotFoundError,
    SmartCollectEventConflictError,
    SmartCollectEventNotFoundError,
    SmartCollectEventPersistenceError,
    SmartCollectEventService,
    SmartCollectEventValidationError,
)
from ..services.smart_collect_evidence_service import SmartCollectEvidenceService
from ..services.smart_collect_similarity_service import SmartCollectSimilarityService
from ..services.llm_provider import OpenAICompatibleLLMProvider
from ..services.smart_collect_synthesis_service import (
    SmartCollectSynthesisConfigError,
    SmartCollectSynthesisConflictError,
    SmartCollectSynthesisDataError,
    SmartCollectSynthesisEmptyResponseError,
    SmartCollectSynthesisError,
    SmartCollectSynthesisGroundingError,
    SmartCollectSynthesisJsonError,
    SmartCollectSynthesisModelError,
    SmartCollectSynthesisNoEvidenceError,
    SmartCollectSynthesisNotFoundError,
    SmartCollectSynthesisPersistenceError,
    SmartCollectSynthesisSchemaError,
    SmartCollectSynthesisService,
    SmartCollectSynthesisTimeoutError,
)
from ..services.smart_collect_service import (
    SmartCollectPersistenceError,
    SmartCollectRelevanceForbiddenError,
    SmartCollectTaskClueNotFoundError,
    SmartCollectTaskNotFoundError,
    SmartCollectTaskService,
)

router = APIRouter(prefix="/smart-collect", tags=["智能采编"])
logger = logging.getLogger(__name__)


def get_content_provider() -> TavilyContentProvider:
    """正文Provider工厂；测试可注入Fake，上层不依赖第三方响应格式。"""
    return TavilyContentProvider(
        api_key=settings.TAVILY_API_KEY,
        timeout=settings.TAVILY_TIMEOUT,
    )


def get_llm_provider() -> OpenAICompatibleLLMProvider:
    """LLM Provider工厂；测试注入Fake，真实供应商格式不进入Router。"""
    return OpenAICompatibleLLMProvider(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
    )


async def process_smart_collect_task(task_id: int) -> None:
    """FastAPI后台入口：每个任务独占新Session，并在任何路径下关闭。"""
    db = SessionLocal()
    try:
        service = SmartCollectTaskService(
            SearchService(
                api_key=settings.TAVILY_API_KEY,
                timeout=settings.TAVILY_TIMEOUT,
            ),
            get_embedding_service(),
        )
        await service.process_task(db, task_id)
    except (SearchServiceError, EmbeddingServiceError, SmartCollectPersistenceError):
        # 预期业务失败已由process_task写入failed和安全error_message。
        return
    except Exception:
        logger.exception("采编后台任务发生未预期异常：task_id=%s", task_id)
        try:
            SmartCollectTaskService._mark_failed(
                db,
                task_id,
                "采编任务执行失败，请稍后重试",
            )
        except SmartCollectPersistenceError:
            logger.exception("采编后台任务失败状态保存失败：task_id=%s", task_id)
    finally:
        db.close()


def _raise_synthesis_http_error(exc: Exception) -> None:
    """统一映射AI整理生成、读取和人工确认的安全错误响应。"""
    if isinstance(
        exc,
        (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError),
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None
    if isinstance(exc, SmartCollectSynthesisNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None
    if isinstance(
        exc,
        (SmartCollectSynthesisNoEvidenceError, SmartCollectSynthesisConflictError),
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from None
    if isinstance(exc, SmartCollectSynthesisConfigError):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, exc.message) from None
    if isinstance(exc, SmartCollectSynthesisTimeoutError):
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, exc.message) from None
    if isinstance(
        exc,
        (SmartCollectSynthesisPersistenceError, SmartCollectSynthesisDataError),
    ):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, exc.message) from None
    raise HTTPException(status.HTTP_502_BAD_GATEWAY, exc.message) from None


def _raise_article_http_error(exc: Exception) -> None:
    """把Synthesis转CMS草稿的业务错误映射为稳定中文响应。"""
    if isinstance(
        exc,
        (
            SmartCollectTaskNotFoundError,
            SmartCollectEventNotFoundError,
            SmartCollectArticleNotFoundError,
        ),
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None
    if isinstance(
        exc,
        (SmartCollectArticleStatusError, SmartCollectArticleAlreadyExistsError),
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from None
    if isinstance(exc, SmartCollectArticleValidationError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message) from None
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, exc.message) from None


def _raise_event_http_error(exc: Exception) -> None:
    """把人工事件业务异常统一转换为中文HTTP响应。"""
    if isinstance(exc, SmartCollectEventConflictError):
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from None
    if isinstance(exc, SmartCollectEventValidationError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from None
    if isinstance(
        exc,
        (
            SmartCollectTaskNotFoundError,
            SmartCollectEventNotFoundError,
            SmartCollectEventClueNotFoundError,
        ),
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None
    if isinstance(exc, SmartCollectEventPersistenceError):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, exc.message) from None
    raise exc


@router.get(
    "/evaluation/summary",
    response_model=SmartCollectEvaluationSummary,
    summary="查看人工标签与两个相关性分数的汇总评估",
)
def get_evaluation_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """管理员统计全部；编辑只统计自己任务，不写库也不触发模型。"""
    return SmartCollectEvaluationService.get_summary(db, user)


@router.get(
    "/evaluation/outliers",
    response_model=SmartCollectEvaluationOutliers,
    summary="查看人工判断与单项模型分数偏差较大的新闻",
)
def get_evaluation_outliers(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """四组结果分别排序，不设阈值，也不混合Tavily与E5分数。"""
    return SmartCollectEvaluationService.get_outliers(db, user, limit)


@router.post(
    "/search",
    response_model=SmartCollectSearchResponse,
    summary="搜索候选新闻资料（编辑/管理员）",
    deprecated=True,
)
async def search_news(
    body: SmartCollectSearchRequest,
    user: User = Depends(require_roles("editor", "admin")),
):
    """旧临时搜索接口：只调用 Tavily，不创建任务、也不写数据库。"""
    service = SearchService(
        api_key=settings.TAVILY_API_KEY,
        timeout=settings.TAVILY_TIMEOUT,
    )
    try:
        return await service.search(body.query, body.time_range, body.max_results)
    except SearchServiceError as exc:
        raise HTTPException(exc.status_code, exc.message) from None


@router.post(
    "/tasks",
    response_model=SmartCollectTaskCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建采编任务并安排后台执行（编辑/管理员）",
)
def create_task(
    body: SmartCollectSearchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """请求内只落库running记录；完整采编在响应发送后使用独立Session执行。"""
    try:
        created = SmartCollectTaskService.create_running_task(db, user, body)
    except SmartCollectPersistenceError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, exc.message) from None
    background_tasks.add_task(process_smart_collect_task, created["task_id"])
    return {
        "message": "采编任务已创建，正在处理中",
        **created,
    }


@router.get(
    "/tasks",
    response_model=SmartCollectTaskListResponse,
    summary="查看历史采编任务（编辑看自己，管理员看全部）",
)
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    task_status: Literal["running", "completed", "failed"] | None = Query(None, alias="status"),
    creator_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """编辑只能读取自己的任务；管理员可按创建人和状态筛选全部任务。"""
    query = db.query(SmartCollectTask).options(joinedload(SmartCollectTask.creator))
    if user.role == "admin":
        if creator_id is not None:
            query = query.filter(SmartCollectTask.creator_id == creator_id)
    else:
        if creator_id is not None and creator_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "编辑只能查看自己的采编任务")
        query = query.filter(SmartCollectTask.creator_id == user.id)
    if task_status is not None:
        query = query.filter(SmartCollectTask.status == task_status)

    query = query.order_by(SmartCollectTask.created_at.desc(), SmartCollectTask.id.desc())
    rows, total = paginate(query, page, page_size)
    return {
        "items": [task.to_dict() for task in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/tasks/{task_id}/similarity-pairs",
    response_model=SmartCollectSimilarityResponse,
    summary="分析同一任务内语义最相似的新闻线索对",
)
async def get_similarity_pairs(
    task_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """分析同一采编任务内语义最相似的新闻线索对。

    功能：
    - 用于编辑判断“哪两条新闻内容最像”，可作为人工分组事件的参考；
    - 只读操作，不会修改 semantic_score、线索、事件或任何数据。

    请求参数：
    - task_id：采编任务ID；
    - limit：返回最多多少条最相似 pair，默认10，范围1~50。

    权限：编辑/管理员。管理员可看全部任务；
    编辑只能看自己创建的任务，否则返回404。

    返回：
    - clue_count：参与分析的线索数量；
    - pair_count：理论两两组合数；
    - items：按 similarity_score 降序的前 limit 条线索对。

    错误语义：
    - 404：任务不存在或当前编辑无权查看；
    - 503：语义计算服务不可用。
    """
    service = SmartCollectSimilarityService(get_embedding_service())
    try:
        return await service.analyze(db, task_id, user, limit)
    except SmartCollectTaskNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None
    except EmbeddingServiceError as exc:
        raise HTTPException(exc.status_code, exc.message) from None


@router.get(
    "/tasks/{task_id}/events",
    response_model=SmartCollectEventListResponse,
    summary="查看任务的人工事件及未分组线索",
)
def list_task_events(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        return SmartCollectEventService.list_events(db, task_id, user)
    except Exception as exc:
        _raise_event_http_error(exc)


@router.post(
    "/tasks/{task_id}/events",
    response_model=SmartCollectEventMutationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="手工创建新闻事件分组",
)
def create_task_event(
    task_id: int,
    body: SmartCollectEventCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        event = SmartCollectEventService.create_event(
            db,
            task_id,
            user,
            body.title,
            body.clue_ids,
        )
        return {"message": "人工事件已创建", "event": event}
    except Exception as exc:
        _raise_event_http_error(exc)


@router.patch(
    "/tasks/{task_id}/events/{event_id}",
    response_model=SmartCollectEventMutationResponse,
    summary="修改人工事件标题",
)
def rename_task_event(
    task_id: int,
    event_id: int,
    body: SmartCollectEventUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        event = SmartCollectEventService.rename_event(
            db,
            task_id,
            event_id,
            user,
            body.title,
        )
        return {"message": "人工事件标题已更新", "event": event}
    except Exception as exc:
        _raise_event_http_error(exc)


@router.post(
    "/tasks/{task_id}/events/{event_id}/clues",
    response_model=SmartCollectEventMutationResponse,
    summary="向人工事件增加任务线索",
)
def add_task_event_clues(
    task_id: int,
    event_id: int,
    body: SmartCollectEventAddCluesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        event = SmartCollectEventService.add_clues(
            db,
            task_id,
            event_id,
            user,
            body.clue_ids,
        )
        return {"message": "线索已加入人工事件", "event": event}
    except Exception as exc:
        _raise_event_http_error(exc)


@router.post(
    "/tasks/{task_id}/events/{event_id}/prepare-content",
    response_model=SmartCollectContentPrepareResponse,
    summary="准备人工事件的来源正文材料",
)
async def prepare_task_event_content(
    task_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """已完成正文默认复用；其余来源事务外批量提取并逐条短事务保存。"""
    service = SmartCollectContentService(get_content_provider())
    try:
        return await service.prepare_event(db, task_id, event_id, user)
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None
    except SmartCollectContentPersistenceError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, exc.message) from None


@router.get(
    "/tasks/{task_id}/events/{event_id}/evidence",
    response_model=EventEvidencePack,
    summary="查看人工事件的实时证据包",
)
def get_task_event_evidence(
    task_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """只读构造证据包，不获取正文、不触发搜索或任何模型。"""
    try:
        return SmartCollectEvidenceService.build_evidence_pack(
            db,
            task_id,
            event_id,
            user,
        )
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None


@router.post(
    "/tasks/{task_id}/events/{event_id}/synthesize",
    response_model=SmartCollectSynthesisResponse,
    summary="根据当前事件证据生成并保存新的AI整理版本",
)
async def synthesize_task_event(
    task_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """权限和证据检查先于模型调用；仅校验通过的结果会新增版本。"""
    service = SmartCollectSynthesisService(get_llm_provider())
    try:
        return await service.synthesize(db, task_id, event_id, user)
    except SmartCollectSynthesisError as exc:
        _raise_synthesis_http_error(exc)
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        _raise_synthesis_http_error(exc)


@router.get(
    "/tasks/{task_id}/events/{event_id}/syntheses",
    response_model=SmartCollectSynthesisListResponse,
    summary="查看人工事件的AI整理历史",
)
def list_task_event_syntheses(
    task_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        return SmartCollectSynthesisService.list_syntheses(
            db, task_id, event_id, user
        )
    except SmartCollectSynthesisError as exc:
        _raise_synthesis_http_error(exc)
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        _raise_synthesis_http_error(exc)


@router.get(
    "/tasks/{task_id}/events/{event_id}/syntheses/{synthesis_id}",
    response_model=SmartCollectSynthesisResponse,
    summary="查看一个AI整理历史版本",
)
def get_task_event_synthesis(
    task_id: int,
    event_id: int,
    synthesis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        return SmartCollectSynthesisService.get_synthesis(
            db, task_id, event_id, synthesis_id, user
        )
    except SmartCollectSynthesisError as exc:
        _raise_synthesis_http_error(exc)
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        _raise_synthesis_http_error(exc)


@router.post(
    "/tasks/{task_id}/events/{event_id}/syntheses/{synthesis_id}/approve",
    response_model=SmartCollectSynthesisResponse,
    summary="人工确认采用一个AI整理版本",
)
def approve_task_event_synthesis(
    task_id: int,
    event_id: int,
    synthesis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        return SmartCollectSynthesisService.approve(
            db, task_id, event_id, synthesis_id, user
        )
    except SmartCollectSynthesisError as exc:
        _raise_synthesis_http_error(exc)
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        _raise_synthesis_http_error(exc)


@router.post(
    "/tasks/{task_id}/events/{event_id}/syntheses/{synthesis_id}/reject",
    response_model=SmartCollectSynthesisResponse,
    summary="人工废弃一个AI整理版本",
)
def reject_task_event_synthesis(
    task_id: int,
    event_id: int,
    synthesis_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        return SmartCollectSynthesisService.reject(
            db, task_id, event_id, synthesis_id, user
        )
    except SmartCollectSynthesisError as exc:
        _raise_synthesis_http_error(exc)
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        _raise_synthesis_http_error(exc)


@router.post(
    "/tasks/{task_id}/events/{event_id}/syntheses/{synthesis_id}/create-article",
    response_model=SmartCollectArticleCreateResponse,
    summary="把已确认AI事件整理转换为CMS草稿",
)
def create_article_from_task_event_synthesis(
    task_id: int,
    event_id: int,
    synthesis_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """不调用模型；Article与来源关联在同一个短事务中创建。"""
    try:
        result = SmartCollectArticleService.create_article(
            db,
            task_id,
            event_id,
            synthesis_id,
            user,
        )
        from .keywords import extract_keywords_by_article_id
        background_tasks.add_task(extract_keywords_by_article_id, result["article"]["id"])
        return result
    except SmartCollectArticleError as exc:
        _raise_article_http_error(exc)
    except (SmartCollectTaskNotFoundError, SmartCollectEventNotFoundError) as exc:
        _raise_article_http_error(exc)


@router.get(
    "/clues/{clue_id}/content",
    response_model=SmartCollectContentDetail,
    summary="查看有权限事件线索的清洗正文",
)
def get_clue_content(
    clue_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """编辑必须至少通过自己任务中的一个人工事件拥有该线索。"""
    try:
        return SmartCollectContentService.get_content(db, clue_id, user)
    except SmartCollectContentNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None


@router.delete(
    "/tasks/{task_id}/events/{event_id}/clues/{clue_id}",
    response_model=SmartCollectEventDeleteResponse,
    summary="从人工事件移除任务线索",
)
def remove_task_event_clue(
    task_id: int,
    event_id: int,
    clue_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        SmartCollectEventService.remove_clue(db, task_id, event_id, clue_id, user)
        return {"message": "线索已移出人工事件"}
    except Exception as exc:
        _raise_event_http_error(exc)


@router.delete(
    "/tasks/{task_id}/events/{event_id}",
    response_model=SmartCollectEventDeleteResponse,
    summary="删除人工事件及其关联关系",
)
def delete_task_event(
    task_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    try:
        SmartCollectEventService.delete_event(db, task_id, event_id, user)
        return {"message": "人工事件已删除，新闻线索保持不变"}
    except Exception as exc:
        _raise_event_http_error(exc)


@router.get(
    "/tasks/{task_id}",
    response_model=SmartCollectTaskDetail,
    summary="重新查看某次采编任务及已保存线索",
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """编辑访问别人的任务时也返回404，避免泄露任务是否存在。"""
    task = SmartCollectTaskService.get_task(db, task_id)
    if not task or (user.role != "admin" and task.creator_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "采编任务不存在")
    return task.to_dict(include_items=True)


@router.patch(
    "/tasks/{task_id}/clues/{clue_id}/relevance",
    response_model=SmartCollectRelevanceUpdateResponse,
    summary="设置或取消任务新闻的人工相关性标签",
)
def update_relevance_label(
    task_id: int,
    clue_id: int,
    body: SmartCollectRelevanceUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("editor", "admin")),
):
    """人工标签只属于TaskClue，不改搜索分数、语义分数或NewsClue。"""
    try:
        link = SmartCollectTaskService.update_relevance_label(
            db,
            task_id,
            clue_id,
            user,
            body.relevance_label,
        )
    except SmartCollectRelevanceForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.message) from None
    except (SmartCollectTaskNotFoundError, SmartCollectTaskClueNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, exc.message) from None
    except SmartCollectPersistenceError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, exc.message) from None
    return {
        "message": "人工相关性标签已更新",
        "task_id": link.task_id,
        "clue_id": link.clue_id,
        "relevance_label": link.relevance_label,
    }
