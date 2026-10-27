# -*- coding: utf-8 -*-
"""Dify 工作流调用服务

对接 Dify 外部 API（Workflow 应用，阻塞模式）：
    POST {api_base}/workflows/run
    Headers: Authorization: Bearer {api_key}
    Body:    {"inputs": {...}, "response_mode": "blocking", "user": "..."}

配置来源优先级：
    1. 数据库 dify_workflows 表按 name/id 指定（后台 /api/dify/workflows 管理）
    2. 未指定时取库中第一条启用记录
    3. 兜底读取 .env 的 DIFY_API_BASE / DIFY_API_KEY / DIFY_TIMEOUT

业务接入示例（如在文稿发布后调用摘要工作流）：
    from ..services.dify_service import run_workflow
    result = run_workflow(db, inputs={"title": article.title, "content": article.content}, name="article_summary")
    summary = result["outputs"].get("summary")
"""
import httpx

from ..config import settings
from ..models.dify_workflow import DifyWorkflow


class DifyError(Exception):
    """Dify 调用异常（中文提示，便于直接转成 HTTP 错误返回）"""


class DifyClient:
    """单个 Dify 应用（工作流）的 HTTP 客户端，一个实例对应一组 api_base + api_key"""

    def __init__(self, api_base: str, api_key: str, timeout: int = 30):
        if not api_base or not api_key:
            raise DifyError("未配置 Dify API 地址或 API Key，请先在 .env 中填写或在后台登记工作流")
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def run_workflow(self, inputs: dict, user: str = "dify-user", response_mode: str = "blocking") -> dict:
        """阻塞模式运行工作流，返回 Dify 响应中的 data（含 outputs）"""
        url = f"{self.api_base}/workflows/run"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": inputs or {},
            "response_mode": response_mode,  # blocking 阻塞 / streaming 流式
            "user": user,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise DifyError(f"Dify 调用超时（{self.timeout}s），请检查网络或调大超时") from None
        except httpx.RequestError as e:
            raise DifyError(f"无法连接 Dify 服务：{e}") from None

        if resp.status_code != 200:
            try:
                message = resp.json().get("message") or resp.text
            except ValueError:
                message = resp.text
            raise DifyError(f"Dify 返回错误（HTTP {resp.status_code}）：{message}")

        data = resp.json().get("data") or {}
        if data.get("status") and data.get("status") != "succeeded":
            raise DifyError(f"Dify 工作流执行失败：{data.get('error') or data.get('status')}")
        return data


def get_dify_config(db, name: str | None = None, workflow_id: int | None = None) -> dict:
    """解析 Dify 配置：数据库优先，env 兜底"""
    row = None
    if workflow_id:
        row = db.get(DifyWorkflow, workflow_id)
    elif name:
        row = (
            db.query(DifyWorkflow)
            .filter(DifyWorkflow.name == name, DifyWorkflow.enabled.is_(True))
            .first()
        )
    if row is None or not row.enabled:
        # 未指定或指定项未启用时，取库中第一条启用记录
        row = (
            db.query(DifyWorkflow)
            .filter(DifyWorkflow.enabled.is_(True))
            .order_by(DifyWorkflow.id)
            .first()
        )
    if row:
        return {"api_base": row.api_base, "api_key": row.api_key, "timeout": row.timeout}
    return {
        "api_base": settings.DIFY_API_BASE,
        "api_key": settings.DIFY_API_KEY,
        "timeout": settings.DIFY_TIMEOUT,
    }


def run_workflow(
    db,
    inputs: dict,
    name: str | None = None,
    workflow_id: int | None = None,
    user: str = "dify-user",
) -> dict:
    """业务代码统一入口：按配置调用 Dify 工作流，返回 data（含 outputs）"""
    conf = get_dify_config(db, name=name, workflow_id=workflow_id)
    client = DifyClient(conf["api_base"], conf["api_key"], conf["timeout"])
    return client.run_workflow(inputs, user=user)
