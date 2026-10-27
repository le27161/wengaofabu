# -*- coding: utf-8 -*-
"""门户模块接口：前台读取，后台（管理员）配置轮播/公告；门户主题切换"""
import random

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.deps import require_roles
from ..database import get_db
from ..models.article import Article
from ..models.portal import PortalModule
from ..models.user import User
from ..schemas.portal import AiReadingSwitchIn, OssConfigIn, PortalModuleIn, RegisterEditorIn, SplashSwitchIn, ThemeSwitchIn
from ..services.settings_service import get_setting, set_setting

router = APIRouter(prefix="/portal", tags=["门户"])

# 门户可选主题：扩充新风格时在此登记，并同步 frontend/src/styles/themes.css 的 .theme-* 覆盖块
PORTAL_THEMES = ["editorial", "cyber", "comic", "shan-shui"]


@router.get("/banner/random", summary="随机选取带封面的已发布文稿（管理员，用于轮播图）")
def random_banner_candidates(
    count: int = Query(default=5, ge=1, le=10, description="随机数量"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """从所有已发布且带封面的文稿中随机抽取 count 篇，供后台一键填充首页轮播图。
    候选不足 count 时返回全部可用文稿。"""
    candidates = (
        db.query(Article)
        .filter(
            Article.status == "published",
            Article.cover_url.isnot(None),
            Article.cover_url != "",
        )
        .all()
    )
    picked = random.sample(candidates, min(count, len(candidates)))
    return {
        "total": len(candidates),
        "items": [
            {
                "id": a.id,
                "title": a.title,
                "cover_url": a.cover_url,
                "categories": [{"id": c.id, "name": c.name} for c in a.categories],
                "link": f"/article/{a.id}",
            }
            for a in picked
        ]
    }


@router.get("/theme", summary="获取当前门户主题（公开）")
def get_portal_theme(db: Session = Depends(get_db)):
    theme = get_setting(db, "portal_theme", default="editorial")
    if theme not in PORTAL_THEMES:
        theme = "editorial"
    return {"theme": theme}


@router.get("/grayscale", summary="查询门户哀悼灰度模式开关（公开）")
def get_grayscale(db: Session = Depends(get_db)):
    """名人逝世等场景下，管理员在后台系统设置开启后，前台门户全站显示为黑白"""
    return {"enabled": bool(get_setting(db, "site_grayscale", default=False))}


@router.get("/splash", summary="查询登录后开屏动画开关（公开）")
def get_splash(db: Session = Depends(get_db)):
    """控制登录后是否跳转到 3D 地球开屏页；关闭时直接进入门户首页。"""
    return {"enabled": bool(get_setting(db, "splash_enabled", default=True))}


@router.put("/splash", summary="更新登录后开屏动画开关（管理员）")
def set_splash(
    body: SplashSwitchIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    set_setting(
        db,
        "splash_enabled",
        body.enabled,
        value_type="bool",
        description="登录后是否播放 3D 地球开屏动画；关闭后直接进入门户首页",
    )
    db.commit()
    return {"message": "保存成功", "enabled": body.enabled}


@router.get("/register-editor", summary="查询是否允许用户注册为编辑写手（公开）")
def get_register_editor_policy(db: Session = Depends(get_db)):
    """注册页读取此策略：开启时展示"编辑（可写稿）"选项，关闭时仅能注册普通用户"""
    return {"enabled": bool(get_setting(db, "register_editor_enabled", default=True))}


@router.put("/register-editor", summary="更新注册为编辑的开放策略（管理员）")
def set_register_editor_policy(
    body: RegisterEditorIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    set_setting(
        db,
        "register_editor_enabled",
        body.enabled,
        value_type="bool",
        description="允许用户注册为编辑写手；关闭后编辑账号仅可后台创建",
    )
    db.commit()
    return {"message": "保存成功", "enabled": body.enabled}


@router.get("/ai-reading", summary="查询门户 AI 阅读功能开关（公开）")
def get_ai_reading(db: Session = Depends(get_db)):
    """控制门户文稿详情页的 AI 全文总结、划词分析、核心术语知识链是否展示"""
    return {"enabled": bool(get_setting(db, "portal_ai_reading_enabled", default=True))}


@router.put("/ai-reading", summary="更新门户 AI 阅读功能开关（管理员）")
def set_ai_reading(
    body: AiReadingSwitchIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    set_setting(
        db,
        "portal_ai_reading_enabled",
        body.enabled,
        value_type="bool",
        description="门户 AI 阅读功能总开关：控制 AI 全文总结、划词分析、核心术语知识链的显示",
    )
    db.commit()
    return {"message": "保存成功", "enabled": body.enabled}


@router.get("/oss-config", summary="读取 OSS 配置（管理员，secret_key 脱敏）")
def get_oss_config(
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """读取 S3 兼容对象存储配置；secret_key 只回显占位符，防止明文泄露"""
    cfg = get_setting(db, "oss_config", default=None)
    cfg = cfg if isinstance(cfg, dict) else {}
    masked = {
        "endpoint": cfg.get("endpoint", ""),
        "bucket": cfg.get("bucket", ""),
        "region": cfg.get("region", ""),
        "access_key": cfg.get("access_key", ""),
        "secret_key": "****" if cfg.get("secret_key") else "",
        "path_prefix": cfg.get("path_prefix", ""),
        "public_base_url": cfg.get("public_base_url", ""),
    }
    return {"configured": bool(str(cfg.get("endpoint", "")).strip()), "config": masked}


@router.put("/oss-config", summary="保存 OSS 配置（管理员；secret_key 传 **** 或空保留原值）")
def set_oss_config(
    body: OssConfigIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    old = get_setting(db, "oss_config", default=None)
    old = old if isinstance(old, dict) else {}
    secret = body.secret_key
    # 只有显式传 **** 表示保留原值；传空字符串则清空（用于"清空配置"场景）
    if secret == "****":
        secret = old.get("secret_key", "")
    cfg = {
        "endpoint": body.endpoint.strip(),
        "bucket": body.bucket.strip(),
        "region": body.region.strip(),
        "access_key": body.access_key.strip(),
        "secret_key": secret,
        "path_prefix": body.path_prefix.strip(),
        "public_base_url": body.public_base_url.strip(),
    }
    set_setting(
        db,
        "oss_config",
        cfg,
        value_type="json",
        description="S3 兼容对象存储配置（endpoint 为空则上传到本地）",
    )
    db.commit()
    masked = {**cfg, "secret_key": "****" if cfg["secret_key"] else ""}
    return {"message": "保存成功", "configured": bool(cfg["endpoint"]), "config": masked}


@router.put("/theme", summary="切换门户主题（管理员）")
def set_portal_theme(
    body: ThemeSwitchIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if body.theme not in PORTAL_THEMES:
        raise HTTPException(400, f"不支持的风格：{body.theme}，可选：{', '.join(PORTAL_THEMES)}")
    set_setting(
        db,
        "portal_theme",
        body.theme,
        value_type="string",
        description="前台门户主题：editorial 经典编辑 / cyber 赛博霓虹 / comic 漫画波普",
    )
    db.commit()
    return {"message": "主题已切换", "theme": body.theme}


@router.get("/modules", summary="获取启用的门户模块（前台）")
def get_modules(db: Session = Depends(get_db)):
    modules = db.query(PortalModule).filter(PortalModule.enabled.is_(True)).all()
    return {"items": [m.to_dict() for m in modules]}


@router.get("/modules/admin", summary="获取全部门户模块（含已禁用，管理员，用于后台设置页）")
def get_all_modules(
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """后台门户设置页读取全部模块（前台 /modules 只返回启用的模块，
    若某模块被关闭则前台接口不再返回，设置页必须能读到它才能重新开启）。"""
    modules = db.query(PortalModule).order_by(PortalModule.id).all()
    return {"items": [m.to_dict() for m in modules]}


@router.post("/modules", summary="新建门户模块（管理员）")
def create_module(body: PortalModuleIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    if db.query(PortalModule).filter(PortalModule.module_key == body.module_key).first():
        raise HTTPException(400, "模块标识已存在")
    module = PortalModule(module_key=body.module_key, title=body.title,
                          content=body.content if body.content is not None else {}, enabled=body.enabled)
    db.add(module)
    db.commit()
    db.refresh(module)
    return {"message": "创建成功", "module": module.to_dict()}


@router.put("/modules/{module_key}", summary="编辑门户模块（管理员，如首页轮播）")
def update_module(module_key: str, body: PortalModuleIn, db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    module = db.query(PortalModule).filter(PortalModule.module_key == module_key).first()
    if not module:
        raise HTTPException(404, "模块不存在")
    module.title = body.title
    module.content = body.content if body.content is not None else module.content
    module.enabled = body.enabled
    db.commit()
    db.refresh(module)
    return {"message": "保存成功", "module": module.to_dict()}

