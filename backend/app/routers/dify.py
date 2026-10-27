# -*- coding: utf-8 -*-
"""Dify 工作流管理接口（仅管理员）：登记/管理 Dify 应用信息，并提供试运行接口"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..database import get_db
from ..models.dify_workflow import DifyWorkflow
from ..models.user import User
from ..schemas.dify import DifyRunIn, DifyWorkflowIn
from ..services.dify_service import DifyClient, DifyError

router = APIRouter(prefix="/dify", tags=["Dify 工作流"])


@router.get("/workflows", summary="工作流列表（管理员，API Key 脱敏）")
def list_workflows(db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    rows = db.query(DifyWorkflow).order_by(DifyWorkflow.id).all()
    return {"items": [r.to_dict() for r in rows]}


@router.post("/workflows", summary="登记 Dify 工作流（管理员）")
def create_workflow(
    body: DifyWorkflowIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if db.query(DifyWorkflow).filter(DifyWorkflow.name == body.name).first():
        raise HTTPException(400, "工作流标识已存在")
    if not body.api_key or not body.api_key.strip():
        raise HTTPException(422, "API Key 不能为空")
    row = DifyWorkflow(
        name=body.name,
        api_base=body.api_base,
        api_key=body.api_key,
        description=body.description,
        input_schema=body.input_schema,
        enabled=body.enabled,
        timeout=body.timeout,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "创建成功", "workflow": row.to_dict()}


@router.put("/workflows/{workflow_id}", summary="编辑 Dify 工作流（管理员）")
def update_workflow(
    workflow_id: int,
    body: DifyWorkflowIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = db.get(DifyWorkflow, workflow_id)
    if not row:
        raise HTTPException(404, "工作流不存在")
    dup = db.query(DifyWorkflow).filter(DifyWorkflow.name == body.name, DifyWorkflow.id != workflow_id).first()
    if dup:
        raise HTTPException(400, "工作流标识已存在")
    row.name = body.name
    row.api_base = body.api_base
    # 仅当传入非空且非掩码占位（**** 开头）的 Key 时才覆盖，编辑时留空/掩码保留原 Key
    new_key = (body.api_key or "").strip()
    if new_key and not new_key.startswith("****"):
        row.api_key = new_key
    row.description = body.description
    row.input_schema = body.input_schema
    row.enabled = body.enabled
    row.timeout = body.timeout
    db.commit()
    db.refresh(row)
    return {"message": "保存成功", "workflow": row.to_dict()}


@router.delete("/workflows/{workflow_id}", summary="删除 Dify 工作流登记（管理员）")
def delete_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = db.get(DifyWorkflow, workflow_id)
    if not row:
        raise HTTPException(404, "工作流不存在")
    db.delete(row)
    db.commit()
    return {"message": "删除成功"}


@router.post("/workflows/{workflow_id}/run", summary="试运行工作流（管理员，阻塞模式）")
def run_workflow(
    workflow_id: int,
    body: DifyRunIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    row = db.get(DifyWorkflow, workflow_id)
    if not row:
        raise HTTPException(404, "工作流不存在")
    if not row.enabled:
        raise HTTPException(400, "工作流未启用")
    try:
        client = DifyClient(row.api_base, row.api_key, row.timeout)
        data = client.run_workflow(body.inputs, user=body.user)
    except DifyError as e:
        raise HTTPException(502, f"Dify 调用失败：{e}") from None
    return {
        "message": "执行成功",
        "workflow_run_id": data.get("workflow_run_id"),
        "status": data.get("status"),
        "outputs": data.get("outputs"),
        "elapsed_time": data.get("elapsed_time"),
        "total_tokens": data.get("total_tokens"),
    }
