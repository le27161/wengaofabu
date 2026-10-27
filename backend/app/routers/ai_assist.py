# -*- coding: utf-8 -*-
"""AI 协作台接口：写稿页面的 AI 辅助功能（异步任务 + 轮询）

说明：
- 5 个 AI 功能接口改为"提交任务"：入参校验通过后立即返回 task_id，由后台线程池执行
  （见 services/ai_assist_worker.py），前端每 2 秒轮询任务状态获取结果。
- 当前任务执行体为占位假实现（秒级完成）；后续接入真实 AI 能力时只需替换
  services/ai_assist_worker.py 的 dispatch()，接口契约与前端无需改动。
- 任务执行完成后自动写入 ai_call_logs（成功写返回值、失败写错误信息），后台可查看调用记录。
- 接口要求登录（写手 / 管理员），用于记录调用人与任务归属。
- 规格文档：docs/ai_assist_async.md
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
import json
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, require_roles
from ..core.pagination import paginate
from ..database import get_db
from ..models.ai_correction import AICorrection
from ..models.ai_call import AICallLog
from ..models.ai_task import AITask
from ..models.user import User
from ..schemas.ai import AIAssistIn, AICorrectionIn, AITaskOut, AITaskStatusOut
from ..services.ai_assist_worker import submit_task

# 功能类型常量：与 ai_call_logs.feature_type 注释保持一致
FEATURE_CLASSIFY = 1  # AI 分类
FEATURE_SUMMARY = 2   # AI 生成摘要
FEATURE_REVIEW = 3    # AI 多维度审核
FEATURE_CHECK = 4     # AI 内容校验
FEATURE_SCORE = 5     # AI 文稿打分

FEATURE_NAMES = {
    FEATURE_CLASSIFY: "AI 分类",
    FEATURE_SUMMARY: "AI 生成摘要",
    FEATURE_REVIEW: "AI 多维度审核",
    FEATURE_CHECK: "AI 内容校验",
    FEATURE_SCORE: "AI 文稿打分",
}

# 各功能的前置输入条件：与前端 AIAssistDrawer.vue 的 canUse 保持一致
FEATURE_NEEDS = {
    FEATURE_CLASSIFY: ["title"],
    FEATURE_SUMMARY: ["title", "content"],
    FEATURE_REVIEW: ["title", "content"],
    FEATURE_CHECK: ["content"],
    FEATURE_SCORE: ["title", "content"],  # 打分需要标题+正文（见 article_pingfen.input_schema）
}

router = APIRouter(prefix="/ai/assist", tags=["AI 协作台"])
admin_router = APIRouter(prefix="/admin/ai-calls", tags=["后台-AI 调用记录"])
admin_corrections_router = APIRouter(prefix="/admin/ai-corrections", tags=["后台-AI 分类纠正数据集"])


def _check_ai_inputs(feature_type: int, body: AIAssistIn) -> None:
    """提交任务前的前置校验：与前端按钮禁用条件一致，缺输入直接拒绝"""
    text_map = {
        "title": body.title.strip(),
        "content": body.content.strip(),
    }
    for field in FEATURE_NEEDS.get(feature_type, []):
        if not text_map.get(field):
            names = {"title": "文稿标题", "content": "文稿正文"}
            raise HTTPException(400, f"请先填写{names[field]}再调用 AI 功能")


def _create_task(db: Session, user: User, feature_type: int, body: AIAssistIn) -> AITask:
    """落库任务（pending）并提交到后台线程池，返回任务实体"""
    task = AITask(
        user_id=user.id,
        feature_type=feature_type,
        status="pending",
        article_id=body.article_id,
        draft_key=body.draft_key,
        input_params=body.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    submit_task(task.id)
    return task


@router.post("/classify", summary="AI 分类：提交任务，根据标题自动选择栏目（异步执行）")
def ai_classify(
    body: AIAssistIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AITaskOut:
    """入参仅需标题；提交异步任务，前端轮询后按栏目中文名自动选中对应栏目"""
    _check_ai_inputs(FEATURE_CLASSIFY, body)
    task = _create_task(db, user, FEATURE_CLASSIFY, body)
    return {"task_id": task.id, "status": task.status}


@router.post("/summary", summary="AI 生成摘要：提交任务，根据标题与正文生成摘要（异步执行）")
def ai_summary(
    body: AIAssistIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AITaskOut:
    """入参为标题 + 正文；提交异步任务，前端轮询后把摘要回写到摘要输入框"""
    _check_ai_inputs(FEATURE_SUMMARY, body)
    task = _create_task(db, user, FEATURE_SUMMARY, body)
    return {"task_id": task.id, "status": task.status}


@router.post("/review", summary="AI 多维度审核：提交任务（异步执行）")
def ai_review(
    body: AIAssistIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AITaskOut:
    """入参为标题 + 正文；提交异步任务，前端轮询后展示各审核维度结论"""
    _check_ai_inputs(FEATURE_REVIEW, body)
    task = _create_task(db, user, FEATURE_REVIEW, body)
    return {"task_id": task.id, "status": task.status}


@router.post("/check", summary="AI 内容校验：提交任务，错别字/标点等错误检测（异步执行）")
def ai_check(
    body: AIAssistIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AITaskOut:
    """入参为正文；提交异步任务，前端轮询后展示错误列表并支持定位高亮"""
    _check_ai_inputs(FEATURE_CHECK, body)
    task = _create_task(db, user, FEATURE_CHECK, body)
    return {"task_id": task.id, "status": task.status}


@router.post("/score", summary="AI 文稿打分：提交任务（异步执行）")
def ai_score(
    body: AIAssistIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AITaskOut:
    """入参为正文（可带标题）；提交异步任务，前端轮询后展示评分卡片"""
    _check_ai_inputs(FEATURE_SCORE, body)
    task = _create_task(db, user, FEATURE_SCORE, body)
    return {"task_id": task.id, "status": task.status}


@router.get("/tasks/latest", response_model=AITaskStatusOut, summary="查询当前用户某 AI 功能最近一次任务（用于重新打开 AI 协作台时恢复上次结果）")
def ai_task_latest(
    feature_type: int = Query(..., ge=1, le=5, description="AI功能类型：1~5"),
    article_id: int | None = Query(default=None, description="关联文稿ID，新建未保存时不恢复历史结果"),
    draft_key: str | None = Query(default=None, max_length=64, description="草稿会话标识：未保存草稿按此恢复（article_id 为空时生效）"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """只查当前用户自己的任务：优先按文稿绑定；未保存草稿按 draft_key 恢复，避免新建文稿恢复到旧结果。"""
    query = db.query(AITask).filter(
        AITask.user_id == user.id,
        AITask.feature_type == feature_type,
    )
    if article_id is not None:
        query = query.filter(AITask.article_id == article_id)
    elif draft_key:
        query = query.filter(AITask.draft_key == draft_key, AITask.article_id.is_(None))
    else:
        raise HTTPException(404, "新建文稿尚未保存，不恢复历史 AI 结果")
    task = query.order_by(AITask.id.desc()).first()
    if not task:
        raise HTTPException(404, "暂无 AI 任务记录")
    return {
        "task_id": task.id,
        "article_id": task.article_id,
        "feature_type": task.feature_type,
        "feature_name": FEATURE_NAMES.get(task.feature_type, "未知"),
        "status": task.status,
        "result": task.result_data,
        "error": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
    }


@router.get("/tasks/{task_id}", summary="查询 AI 任务状态（本人或管理员）", response_model=AITaskStatusOut)
def ai_task_status(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """前端轮询任务状态；仅任务发起人本人或管理员可查看"""
    task = db.get(AITask, task_id)
    if not task:
        raise HTTPException(404, "AI 任务不存在")
    if task.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "无权查看他人的 AI 任务")
    return {
        "task_id": task.id,
        "article_id": task.article_id,
        "feature_type": task.feature_type,
        "feature_name": FEATURE_NAMES.get(task.feature_type, "未知"),
        "status": task.status,
        "result": task.result_data,
        "error": task.error_message,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
    }


@router.post("/corrections", summary="提交 AI 分类纠正（沉淀训练数据集，纠正后前端自动选中栏目）")
def ai_correction_create(
    body: AICorrectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """保存一条「标题 + 正文 + 模型分类 + 纠正分类」训练样本，供二次训练使用"""
    title = body.title.strip()
    corrected = body.corrected_category.strip()
    if not title:
        raise HTTPException(400, "文稿标题不能为空")
    if not corrected:
        raise HTTPException(400, "纠正分类不能为空")
    row = AICorrection(
        user_id=user.id,
        article_id=body.article_id,
        draft_key=body.draft_key,
        title=title,
        content=body.content or "",
        model_category=body.model_category.strip(),
        corrected_category=corrected,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "纠正已记录，感谢贡献训练样本", "id": row.id}


@admin_router.get("", summary="AI 调用记录列表（管理员，可按用户/功能类型筛选）")
def admin_ai_calls(
    keyword: str | None = Query(default=None, description="按用户名/昵称模糊搜索"),
    feature_type: int | None = Query(default=None, description="AI 功能类型（1=AI分类 2=AI生成摘要 3=AI多维度审核 4=AI内容校验 5=AI文稿打分）"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """后台查看 AI 调用记录：入参、返回值、调用人与时间"""
    query = db.query(AICallLog, User).join(User, User.id == AICallLog.user_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(User.username.like(like), User.nickname.like(like)))
    if feature_type is not None:
        query = query.filter(AICallLog.feature_type == feature_type)
    query = query.order_by(AICallLog.created_at.desc(), AICallLog.id.desc())
    rows, total = paginate(query, page, page_size)

    items = []
    for log, user in rows:
        items.append({
            "id": log.id,
            "article_id": log.article_id,
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "feature_type": log.feature_type,
            "feature_name": FEATURE_NAMES.get(log.feature_type, "未知"),
            "input_params": log.input_params,
            "output_data": log.output_data,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_corrections_router.get("", summary="AI 分类纠正数据集列表（管理员）")
def admin_ai_corrections(
    keyword: str | None = Query(default=None, description="按标题/纠正分类模糊搜索"),
    corrected_category: str | None = Query(default=None, description="按纠正分类精确筛选"),
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """后台查看纠正数据集，支持标题搜索与纠正分类筛选"""
    query = db.query(AICorrection, User).join(User, User.id == AICorrection.user_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            or_(AICorrection.title.like(like), AICorrection.corrected_category.like(like))
        )
    if corrected_category:
        query = query.filter(AICorrection.corrected_category == corrected_category)
    query = query.order_by(AICorrection.created_at.desc(), AICorrection.id.desc())
    rows, total = paginate(query, page, page_size)
    items = []
    for corr, user in rows:
        items.append({
            "id": corr.id,
            "article_id": corr.article_id,
            "title": corr.title,
            "content": corr.content,
            "model_category": corr.model_category,
            "corrected_category": corr.corrected_category,
            "username": user.username,
            "nickname": user.nickname,
            "created_at": corr.created_at.strftime("%Y-%m-%d %H:%M:%S") if corr.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_corrections_router.get("/export", summary="导出 AI 分类纠正数据集 JSON（管理员，供二次训练）")
def admin_ai_corrections_export(
    start_date: str | None = Query(default=None, description="开始日期（YYYY-MM-DD，可选）"),
    end_date: str | None = Query(default=None, description="结束日期（YYYY-MM-DD，可选）"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """导出训练样本（标题/正文/模型分类/纠正分类），可按提交日期区间过滤；
    不传 start_date/end_date 时导出全量，可直接用于模型二次训练"""
    query = db.query(AICorrection)
    if start_date:
        query = query.filter(AICorrection.created_at >= f"{start_date} 00:00:00")
    if end_date:
        query = query.filter(AICorrection.created_at <= f"{end_date} 23:59:59")
    rows = query.order_by(AICorrection.id).all()
    data = [
        {
            "id": r.id,
            "title": r.title,
            "content": r.content,
            "model_category": r.model_category,
            "corrected_category": r.corrected_category,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
        }
        for r in rows
    ]
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=ai_corrections.json"},
    )
