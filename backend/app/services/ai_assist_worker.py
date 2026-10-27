# -*- coding: utf-8 -*-
"""AI 协作台异步任务执行器

职责：
- 后台线程池执行 AI 任务（当前为占位假实现，秒级完成；后续接入真实模型/Dify 工作流时
  只需替换 dispatch() 内部逻辑，接口契约与前端无需改动）
- 任务状态持久化到 ai_tasks（pending → running → success / failed）
- 任务执行完成后向 ai_call_logs 写调用记录（成功写返回值，失败写错误信息）

注意：后台线程不能复用请求级数据库 Session，必须自行通过 SessionLocal 开新会话。
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from ..database import SessionLocal
from ..models.ai_task import AITask
from ..models.user import User
from ..services.ai_call_service import log_ai_call
from ..services.dify_service import DifyError, run_workflow

logger = logging.getLogger(__name__)

# 功能类型常量：与 ai_call_logs / ai_tasks.feature_type 注释保持一致
FEATURE_CLASSIFY = 1  # AI 分类
FEATURE_SUMMARY = 2   # AI 生成摘要
FEATURE_REVIEW = 3    # AI 多维度审核
FEATURE_CHECK = 4     # AI 内容校验
FEATURE_SCORE = 5     # AI 文稿打分

# 后台任务并发数：单机场景 4 个 worker 足够，可按需通过环境变量 AI_TASK_MAX_WORKERS 调大
_MAX_WORKERS = int(os.environ.get("AI_TASK_MAX_WORKERS", "4"))
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="ai-assist")




def _extract_summary_from_outputs(outputs) -> str:
    """从 Dify outputs 中提取可展示的摘要文本。

    Dify 工作流结束节点常返回 {"text": "..."}，text 可能是纯文本或 JSON 字符串；
    同时兼容 summary/text/result/one_sentence_summary 等常见字段。
    """
    if isinstance(outputs, str):
        text = outputs
    elif isinstance(outputs, dict):
        text = outputs.get("text") or outputs.get("summary") or outputs.get("result") or ""
        if not text and isinstance(outputs.get("outputs"), (str, dict)):
            text = outputs.get("outputs")
    else:
        text = ""

    if isinstance(text, dict):
        text = text.get("one_sentence_summary") or text.get("summary") or text.get("text") or ""
    if isinstance(text, str) and text.strip().startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                text = parsed.get("one_sentence_summary") or parsed.get("summary") or parsed.get("text") or text
        except (ValueError, TypeError):
            pass

    result = " ".join(str(text).split()).strip()
    return result



def _try_json(text: str):
    """尝试把字符串按 JSON 解析，失败返回 None"""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _fallback_result(feature_type: int) -> dict:
    """Dify 输出异常/格式非法时的安全兜底：任务仍标记成功，前端不报错"""
    if feature_type == FEATURE_SUMMARY:
        return {"summary": ""}
    if feature_type == FEATURE_REVIEW:
        return {"overall_risk": "", "risk_list": [], "summary": ""}
    if feature_type == FEATURE_CHECK:
        return {"items": []}
    if feature_type == FEATURE_SCORE:
        return {
            "综合等级": "",
            "整体总结": "",
            "现存问题清单": [],
            "标题优化建议": [],
            "分项评分": [],
            "总分": "",
        }
    return {}


def _load_prev_check(task_id, article_id, draft_key):
    """查询同一文稿上次内容校验的结果与正文，作为 last_llm / old_text 入参

    按当前任务归属的文稿（已保存用 article_id，未保存草稿用 draft_key）取最近一次成功任务；
    首次调用或没有历史时返回空串，避免把无关文稿的历史带进来。
    """
    db = SessionLocal()
    try:
        query = db.query(AITask).filter(
            AITask.feature_type == FEATURE_CHECK,
            AITask.status == "success",
        )
        if article_id is not None:
            query = query.filter(AITask.article_id == article_id)
        elif draft_key:
            query = query.filter(AITask.draft_key == draft_key)
        else:
            return "", ""
        if task_id is not None:
            query = query.filter(AITask.id != task_id)
        prev = query.order_by(AITask.id.desc()).first()
        if not prev:
            return "", ""
        # last_llm = 上次 Dify 工作流返回结果（JSON 串）；old_text = 上次调用时的正文
        last_llm = json.dumps(prev.result_data, ensure_ascii=False) if prev.result_data else ""
        old_text = (prev.input_params or {}).get("content") or ""
        return last_llm, old_text
    finally:
        db.close()


def _extract_check_items(outputs) -> list:
    """从 Dify outputs 中提取内容校验错误列表（[{错误类型,原文位置,修改结果,修改建议}, ...]）

    Dify 结束节点可能直接返回数组，也可能返回 {"text": "[...json 数组...]"} 等包装结构，统一解析。
    """
    raw = outputs
    if isinstance(raw, str):
        raw = _try_json(raw) or raw
    if isinstance(raw, dict):
        for key in ("items", "result", "outputs", "data", "text"):
            if isinstance(raw.get(key), (list, str)):
                raw = raw[key]
                break
    if isinstance(raw, str):
        raw = _try_json(raw) or []
    if not isinstance(raw, list):
        return []
    normalized = []
    for it in raw:
        if isinstance(it, dict):
            normalized.append({
                "错误类型": str(it.get("错误类型") or ""),
                "原文位置": str(it.get("原文位置") or ""),
                "修改结果": str(it.get("修改结果") or ""),
                "修改建议": str(it.get("修改建议") or ""),
            })
    return normalized


def _extract_review_result(outputs) -> dict:
    """从 Dify outputs 中提取多维度审核结果

    返回结构固定为 {"overall_risk": str, "risk_list": [...], "summary": str}；
    risk_list 元素含 risk_dimension / risk_level / source_text / risk_desc / suggestion。
    Dify 结束节点可能返回直接对象或 {"text": "<json 字符串>"} 包装，统一解析。
    """
    raw = outputs
    if isinstance(raw, str):
        raw = _try_json(raw) or raw
    if isinstance(raw, dict):
        for key in ("result", "outputs", "data", "text"):
            if isinstance(raw.get(key), (str, dict)):
                raw = raw[key]
                break
    if isinstance(raw, str):
        raw = _try_json(raw) or {}
    if not isinstance(raw, dict):
        return {"overall_risk": "", "risk_list": [], "summary": ""}
    risk_list = raw.get("risk_list") or []
    if not isinstance(risk_list, list):
        risk_list = []
    return {
        "overall_risk": str(raw.get("overall_risk") or "").strip(),
        "risk_list": [it for it in risk_list if isinstance(it, dict)],
        "summary": str(raw.get("summary") or "").strip(),
    }


def _extract_score_result(outputs) -> dict:
    """从 Dify outputs 中提取文稿打分结果

    返回结构固定为 {综合等级, 整体总结, 现存问题清单, 标题优化建议, 分项评分, 总分}；
    分项评分元素含 维度/得分/建议，两个清单为字符串数组。

    工作流由 LLM 生成 JSON，字段名存在漂移（分项评分/分项/分项得分/维度评分 均出现过，
    个别运行还会缺某个清单）。解析采用「已知键名优先 + 结构兜底」：
    - 分项评分：识别含「维度/得分」的字典数组；
    - 现存问题/标题优化建议：识别字符串数组（问题在前、建议在后）；
    - 总分：识别形如 90/100 的字符串。
    """
    raw = outputs
    if isinstance(raw, str):
        raw = _try_json(raw) or raw
    if isinstance(raw, dict):
        for key in ("result", "outputs", "data", "text"):
            if isinstance(raw.get(key), (str, dict)):
                raw = raw[key]
                break
    if isinstance(raw, str):
        raw = _try_json(raw) or {}
    if not isinstance(raw, dict):
        return {"综合等级": "", "整体总结": "", "现存问题清单": [], "标题优化建议": [], "分项评分": [], "总分": ""}

    def _first_str(*keys):
        for k in keys:
            v = raw.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def _first_list(*keys):
        for k in keys:
            v = raw.get(k)
            if isinstance(v, list):
                return k, v
        return None, None

    def _strs(value):
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        return []

    # 1) 分项评分：已知键名 + 结构兜底（含「维度/得分」的字典数组）
    _k, items = _first_list("分项评分", "分项", "分项得分", "维度评分")
    if items is None:
        for v in raw.values():
            if isinstance(v, list) and v and all(
                isinstance(x, dict) and ("维度" in x or "得分" in x) for x in v
            ):
                items = v
                break
    if not isinstance(items, list):
        items = []

    # 2) 字符串清单：已知键名优先；缺失时按出现顺序兜底（排除已识别键）
    prob_key, problems = _first_list("现存问题清单", "存在问题", "问题清单")
    sug_key, suggestions = _first_list("标题优化建议", "优化建议", "建议清单")
    if problems is None or suggestions is None:
        remaining = [
            v for k, v in raw.items()
            if isinstance(v, list) and v
            and all(isinstance(x, str) and x.strip() for x in v)
            and k not in (prob_key, sug_key)
        ]
        if problems is None and remaining:
            problems = remaining.pop(0)
        if suggestions is None and remaining:
            suggestions = remaining.pop(0)

    # 3) 总分：已知键名；缺失时扫描含 "数字/数字" 的字符串
    total = _first_str("总分", "总得分", "最终得分")
    if not total:
        for v in raw.values():
            if isinstance(v, str):
                m = re.search(r"\d{1,3}\s*/\s*\d{1,3}", v)
                if m:
                    total = m.group(0)
                    break

    return {
        "综合等级": _first_str("综合等级", "综合评级", "等级"),
        "整体总结": _first_str("整体总结", "总结", "综合总结"),
        "现存问题清单": _strs(problems),
        "标题优化建议": _strs(suggestions),
        "分项评分": [it for it in items if isinstance(it, dict)],
        "总分": total,
    }


def dispatch(feature_type: int, inputs: dict, context: dict | None = None) -> dict:
    """AI 功能执行入口（占位假实现）

    接入真实 AI 能力时，仅需在本函数内按 feature_type 调用真实模型 / Dify 工作流
    （如 run_workflow），保持返回值结构与假实现一致即可。
    context 可选：携带当前任务信息（task_id 等），用于查询同一文稿的历史调用。
    """
    title = (inputs.get("title") or "").strip()
    content = (inputs.get("content") or "").strip()

    if feature_type == FEATURE_CLASSIFY:
        #ai文稿分类功能
        if not title:
            raise ValueError("请先填写文稿标题")
        # 调用 BERT 模型做标题分类；模型延迟加载（首次调用约 20 秒，之后复用），
        # 避免后端启动时加载模型拖慢启动并干扰 uvicorn reload
        from ..aimodel.predict import predict_fun
        result=predict_fun(title)

        return {"category_name": result}

    if feature_type == FEATURE_SUMMARY:
        if not title or not content:
            raise ValueError("请先填写文稿标题和正文")
        # 登记的工作流输入变量为 title + context（见 dify_workflows.input_schema）
        try:
            db = SessionLocal()
            try:
                data = run_workflow(
                    db,
                    inputs={"title": title, "context": content},
                    name="article_summary",
                )
            finally:
                db.close()
            summary = _extract_summary_from_outputs(data.get("outputs") or {})
            return {"summary": summary}
        except Exception as exc:
            logger.warning("AI 摘要 Dify 输出异常，已兜底：%s", exc)
            return _fallback_result(FEATURE_SUMMARY)

    if feature_type == FEATURE_REVIEW:
        if not title or not content:
            raise ValueError("请先填写文稿标题和正文")

        # 多维度审核：入参 original_text = 标题 + 正文（见 dify_workflows.input_schema）
        try:
            db = SessionLocal()
            try:
                data = run_workflow(
                    db,
                    inputs={"original_text": f"{title}\n{content}"},
                    name="article_weidu",
                )
            finally:
                db.close()
            # 返回结构固定为 {overall_risk, risk_list, summary}，前端直接渲染
            return _extract_review_result(data.get("outputs") or {})
        except Exception as exc:
            logger.warning("AI 多维度审核 Dify 输出异常，已兜底：%s", exc)
            return _fallback_result(FEATURE_REVIEW)

    if feature_type == FEATURE_CHECK:
        if not content:
            raise ValueError("请先填写文稿正文")

        # 内容校验：把上一次校验的结果(last_llm)与当时正文(old_text)连同本次正文(now_text)
        # 一起传给 Dify 工作流 article_neirong，支持基于历史错误的增量纠错；首次调用历史为空串
        article_id = inputs.get("article_id") or None
        draft_key = inputs.get("draft_key") or None
        last_llm, old_text = _load_prev_check((context or {}).get("task_id"), article_id, draft_key)
        try:
            db = SessionLocal()
            try:
                data = run_workflow(
                    db,
                    inputs={
                        "last_llm": last_llm,
                        "now_text": content,
                        "old_text": old_text,
                    },
                    name="article_neirong",
                )
            finally:
                db.close()
            # 返回结构固定为 {"items": [...]}，前端 checkItems 直接渲染并支持高亮定位
            return {"items": _extract_check_items(data.get("outputs") or {})}
        except Exception as exc:
            logger.warning("AI 内容校验 Dify 输出异常，已兜底：%s", exc)
            return _fallback_result(FEATURE_CHECK)

    if feature_type == FEATURE_SCORE:
        if not title or not content:
            raise ValueError("请先填写文稿标题和正文")
        # 文稿打分：入参 article_title + article_content（见 dify_workflows.input_schema）
        try:
            db = SessionLocal()
            try:
                data = run_workflow(
                    db,
                    inputs={"article_title": title, "article_content": content},
                    name="article_pingfen",
                )
            finally:
                db.close()
            return _extract_score_result(data.get("outputs") or {})
        except Exception as exc:
            logger.warning("AI 文稿打分 Dify 输出异常，已兜底：%s", exc)
            return _fallback_result(FEATURE_SCORE)

    raise ValueError(f"未知的 AI 功能类型：{feature_type}")


def _execute_task(task_id: int) -> None:
    """后台线程执行单个 AI 任务（自建 Session，流程见规格文档第 4 节）"""
    db = SessionLocal()
    try:
        task = db.get(AITask, task_id)
        if not task:
            return
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()

        user = db.get(User, task.user_id)
        try:
            result = dispatch(task.feature_type, task.input_params or {}, context={"task_id": task.id})
            task.status = "success"
            task.result_data = result
            task.error_message = None
            db.commit()
            # 成功调用记录（若用户已被删除则跳过记录，任务结果仍保留）
            if user:
                log_ai_call(db, user, task.feature_type, task.input_params or {}, result, article_id=task.article_id, draft_key=task.draft_key)
        except Exception as exc:  # noqa: BLE001 - 任务失败需完整落库供后台排查
            db.rollback()
            task = db.get(AITask, task_id)
            task.status = "failed"
            task.error_message = str(exc)[:500]
            db.commit()
            if user:
                try:
                    log_ai_call(
                        db, user, task.feature_type,
                        task.input_params or {},
                        {"error": task.error_message},
                        article_id=task.article_id,
                        draft_key=task.draft_key,
                    )
                except Exception:  # noqa: BLE001 - 记录失败不阻塞任务状态更新
                    db.rollback()
    finally:
        db.close()


def submit_task(task_id: int) -> None:
    """提交任务到后台线程池执行（提交接口调用）"""
    _executor.submit(_execute_task, task_id)
