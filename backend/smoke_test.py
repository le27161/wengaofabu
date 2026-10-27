# -*- coding: utf-8 -*-
"""接口冒烟测试：验证核心业务流程，可随时重跑（python smoke_test.py）"""
import sys
import time
import io as _io

from openpyxl import Workbook

import httpx

BASE = "http://127.0.0.1:8000/api"

# 组选择参数：python smoke_test.py（全量，默认）/ --only 1,18 / --skip 12,14
_RUN_ONLY = None
_RUN_SKIP = set()
_argv = sys.argv[1:]
if '--only' in _argv:
    _RUN_ONLY = {int(x) for x in _argv[_argv.index('--only') + 1].split(',')}
if '--skip' in _argv:
    _RUN_SKIP = {int(x) for x in _argv[_argv.index('--skip') + 1].split(',')}


def should_run(n: int) -> bool:
    """是否执行第 n 组测试（--only 未指定时全量；--skip 优先级最高）"""
    if _RUN_ONLY is not None and n not in _RUN_ONLY:
        return False
    if n in _RUN_SKIP:
        return False
    return True


def login(client, username, password):
    r = client.post(f"{BASE}/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["access_token"]


def wait_ai_task(client, headers, task_id, max_wait=30):
    """轮询 AI 任务直到 success/failed，超时抛断言失败（假实现秒级完成）"""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r = client.get(f"{BASE}/ai/assist/tasks/{task_id}", headers=headers)
        assert r.status_code == 200, f"查询任务失败: {r.text}"
        data = r.json()
        if data["status"] in ("success", "failed"):
            return data
        time.sleep(0.3)
    raise AssertionError(f"AI 任务 {task_id} 轮询超时（{max_wait}s）")


def main():
    mode = '全量' if _RUN_ONLY is None else f'仅 {sorted(_RUN_ONLY)}'
    if _RUN_SKIP:
        mode += f'（跳过 {sorted(_RUN_SKIP)}）'
    print(f'[run] 冒烟测试模式：{mode}')
    aid = None  # 文稿ID：由第 1 组创建，后续组复用（独立运行依赖组时保持 None）
    uniq = int(time.time())  # 唯一后缀：各测试组共用，避免命名冲突
    client = httpx.Client(timeout=10)
    ed_token = login(client, "editor", "editor123")
    admin_token = login(client, "admin", "admin123")
    user_token = login(client, "user", "user123")
    ed_h, admin_h, user_h = (
        {"Authorization": f"Bearer {t}"} for t in (ed_token, admin_token, user_token)
    )

    # 0. 创建二审管理员（审核业务要求一审二审由不同管理员完成；已存在则忽略）
    r = client.post(f"{BASE}/users", headers=admin_h, json={
        "username": "admin2", "password": "admin123", "nickname": "二审管理员", "role": "admin",
    })
    assert r.status_code in (200, 400), f"创建二审管理员失败: {r.text}"
    admin2_token = login(client, "admin2", "admin123")
    admin2_h = {"Authorization": f"Bearer {admin2_token}"}
    print("[0] 二审管理员就绪 OK")

    # 动态获取可用栏目 id（数据库可能被重置，避免硬编码失效的栏目 id）
    r = client.get(f"{BASE}/categories")
    assert r.status_code == 200 and r.json()["items"], "无可用栏目"
    cat_ids = [c["id"] for c in r.json()["items"]][:2]
    print(f"[0] 栏目就绪 OK ids={cat_ids}")

    # 确保走人工两级审核流程：显式关闭自动审核（不依赖外部配置状态）
    r = client.put(f"{BASE}/settings/auto_review", headers=admin_h, json={"value": False, "value_type": "bool"})
    assert r.status_code == 200, f"关闭自动审核失败: {r.text}"
    print("[0] 自动审核已关闭 OK")

    if should_run(1):
        # 1. 编辑创建文稿（timeout=60：创建钩子首次可能触发向量模型加载）
        r = httpx.post(f"{BASE}/articles", headers=ed_h, timeout=60, json={
            "title": "测试文稿：人工智能如何改变新闻业",
            "summary": "这是一篇用于系统联调的测试文稿。",
            "content": "<p>这是正文内容。</p>",
            "cover_url": "",
            "category_ids": cat_ids,
        })
        assert r.status_code == 200, f"创建失败: {r.text}"
        aid = r.json()["article"]["id"]
        print(f"[1] 创建草稿 OK  id={aid}")
    
        # 1.1 创建向量化钩子：新文稿自动向量化入库
        r = client.get(f"{BASE}/embeddings/article/{aid}", headers=admin_h)
        assert r.status_code == 200, f"新文稿应自动向量化: {r.text}"
        emb = r.json()["embedding"]
        assert emb["model_version"] == "BAAI_bge-small-zh" and emb["dim"] == 512, f"向量化记录异常: {emb}"
        emb_hash_before_edit = emb["source_hash"]
        print(f"[1.1] 文稿创建向量化钩子 OK  article_id={aid}")
    
    if should_run(2):
        # 2. 提交审核
        r = client.post(f"{BASE}/articles/{aid}/submit", headers=ed_h)
        assert r.status_code == 200, f"提交失败: {r.text}"
        print("[2] 提交一审 OK ->", r.json()["article"]["status"])
    
    if should_run(3):
        # 3. 管理员一审
        r = client.post(f"{BASE}/reviews", headers=admin_h,
                        json={"article_id": aid, "level": 1, "action": "approve", "comment": "内容合格，通过一审"})
        assert r.status_code == 200, f"一审失败: {r.text}"
        print("[3] 一审通过 OK ->", r.json()["article"]["status"])
    
    if should_run(4):
        # 4. 二审管理员二审（不同审核人）
        r = client.post(f"{BASE}/reviews", headers=admin2_h,
                        json={"article_id": aid, "level": 2, "action": "approve", "comment": "准予发布"})
        assert r.status_code == 200, f"二审失败: {r.text}"
        print("[4] 二审通过 OK ->", r.json()["article"]["status"])
    
    if should_run(5):
        # 5. 前台列表可见
        r = client.get(f"{BASE}/articles", params={"category_id": cat_ids[0]})
        assert any(a["id"] == aid for a in r.json()["items"]), "文稿未出现在栏目列表中"
        print("[5] 前台列表可见 OK  total =", r.json()["total"])
    
        # 5.1 后台文稿列表：栏目筛选 + 服务端排序（sort_by/sort_order 白名单）
        r = client.get(f"{BASE}/articles/admin", headers=admin_h,
                       params={"category_id": cat_ids[0], "sort_by": "view_count", "sort_order": "desc"})
        assert r.status_code == 200, f"后台列表筛选失败: {r.text}"
        items = r.json()["items"]
        assert items, "栏目筛选结果为空"
        assert all(cat_ids[0] in [c["id"] for c in a["categories"]] for a in items), "栏目筛选结果不正确"
        views = [a["view_count"] for a in items]
        assert views == sorted(views, reverse=True), "按浏览量降序排序不正确"
        # 非法排序字段应被参数校验拦截（422）
        r = client.get(f"{BASE}/articles/admin", headers=admin_h, params={"sort_by": "title"})
        assert r.status_code == 422, "非法排序字段未拦截"
        # 默认排序：创建时间降序（新文稿优先）
        r = client.get(f"{BASE}/articles/admin", headers=admin_h, params={"page_size": 5})
        default_times = [a["created_at"] for a in r.json()["items"]]
        assert default_times == sorted(default_times, reverse=True), f"默认应按创建时间倒序: {default_times}"
        print("[5.1] 后台列表栏目筛选 + 服务端排序 OK（默认创建时间降序）")
    
    if should_run(6):
        # 6. 用户观看埋点（view 计数累加不应刷新 updated_at）
        before_updated = client.get(f"{BASE}/articles/{aid}", headers=admin_h).json()["updated_at"]
        r = client.post(f"{BASE}/events", headers=user_h, json={"event_type": "view", "article_id": aid})
        assert r.json()["ok"], "观看埋点失败"
        after_updated = client.get(f"{BASE}/articles/{aid}", headers=admin_h).json()["updated_at"]
        assert after_updated == before_updated, f"view 不应刷新 updated_at: {before_updated} -> {after_updated}"
        print("[6] 观看埋点 OK（updated_at 不变）")
        # 观看时长累计上限：每篇每用户 30 分钟（1800 秒），达上限后不再累计
        for _ in range(3):
            r = client.post(f"{BASE}/history/{aid}/duration", headers=user_h, json={"seconds": 600})
            assert r.status_code == 200, f"时长上报失败: {r.text}"
        assert r.json()["watch_seconds"] == 1800 and r.json()["reached_limit"] is True
        r = client.post(f"{BASE}/history/{aid}/duration", headers=user_h, json={"seconds": 600})
        assert r.json()["watch_seconds"] == 1800 and r.json()["reached_limit"] is True, f"达上限后不应再累计: {r.text}"
        print("[6] 观看时长 30 分钟上限 OK")
    
    if should_run(7):
        # 7. 点赞 / 收藏 / 转发（计数更新不应刷新 updated_at）
        before_updated = client.get(f"{BASE}/articles/{aid}", headers=admin_h).json()["updated_at"]
        for ep in ("like", "favorite", "share"):
            r = client.post(f"{BASE}/interactions/{ep}?article_id={aid}", headers=user_h)
            assert r.status_code == 200, f"{ep} 失败: {r.text}"
            print(f"[7] {ep} OK ->", r.json()["message"])
        after_updated = client.get(f"{BASE}/articles/{aid}", headers=admin_h).json()["updated_at"]
        assert after_updated == before_updated, f"互动计数不应刷新 updated_at: {before_updated} -> {after_updated}"
    
        r = client.get(f"{BASE}/interactions/status?article_id={aid}", headers=user_h)
        assert r.json() == {"liked": True, "favorited": True, "disliked": False}, f"互动状态异常: {r.text}"
        print("[7] 互动状态 OK ->", r.json())
    
    if should_run(8):
        # 8. 审核记录
        r = client.get(f"{BASE}/reviews/history", headers=admin_h)
        assert r.json()["total"] >= 2, "审核记录数量异常"
        print("[8] 审核记录 OK  total =", r.json()["total"])
    
    if should_run(9):
        # 9. 统计概览
        r = client.get(f"{BASE}/stats/overview", headers=admin_h)
        stats = r.json()
        assert stats["total_views"] >= 1 and stats["total_likes"] >= 1, "统计数据异常"
        print("[9] 统计概览 OK ->", {k: stats[k] for k in ("published_articles", "total_views", "total_likes", "total_shares")})
    
    if should_run(10):
        # 10. 趋势与用户活跃
        r = client.get(f"{BASE}/stats/trends", headers=admin_h, params={"days": 7})
        assert len(r.json()["items"]) == 7
        r = client.get(f"{BASE}/stats/user-activity", headers=admin_h, params={"days": 7})
        assert len(r.json()["items"]) == 7
        print("[10] 趋势/活跃统计 OK")
    
    if should_run(11):
        # 11. 评论：未登录不可发表；登录可发表/回复；本人与管理员可删除；后台可检索
        r = client.post(f"{BASE}/comments", json={"article_id": aid, "content": "游客评论"})
        assert r.status_code == 401, f"未登录发表评论应被拒绝: {r.text}"
        print("[11] 未登录发表评论被拒绝 OK")
    
        r = client.post(f"{BASE}/comments", headers=user_h, json={"article_id": aid, "content": "这是一条测试评论"})
        assert r.status_code == 200, f"发表评论失败: {r.text}"
        cid = r.json()["comment"]["id"]
        print(f"[11] 发表评论 OK  id={cid}")
    
        r = client.post(f"{BASE}/comments", headers=user_h,
                        json={"article_id": aid, "content": "这是回复内容", "parent_id": cid})
        assert r.status_code == 200, f"发表回复失败: {r.text}"
        reply_id = r.json()["comment"]["id"]
        assert r.json()["comment"]["parent_id"] == cid
        print(f"[11] 发表回复 OK  id={reply_id}")
    
        r = client.get(f"{BASE}/comments", params={"article_id": aid})
        assert r.status_code == 200 and r.json()["total"] >= 1, "评论列表异常"
        top = next(c for c in r.json()["items"] if c["id"] == cid)
        assert any(c["id"] == reply_id for c in top["replies"]), "回复未嵌套在父评论下"
        print("[11] 评论列表（含回复嵌套）OK  total =", r.json()["total"])
    
        # 非法输入：空内容 / 对不存在的评论回复
        r = client.post(f"{BASE}/comments", headers=user_h, json={"article_id": aid, "content": "   "})
        assert r.status_code == 400, f"空评论应被拒绝: {r.text}"
        r = client.post(f"{BASE}/comments", headers=user_h,
                        json={"article_id": aid, "content": "回复不存在的评论", "parent_id": 999999})
        assert r.status_code == 404, f"回复不存在的评论应被拒绝: {r.text}"
        print("[11] 评论非法输入校验 OK")
    
        # 后台列表（管理员）可见该评论
        r = client.get(f"{BASE}/admin/comments", headers=admin_h, params={"keyword": "测试评论"})
        assert r.status_code == 200 and any(c["id"] == cid for c in r.json()["items"]), "后台评论列表异常"
        print("[11] 后台评论列表/检索 OK  total =", r.json()["total"])
    
        # 普通用户不能删别人的评论；作者本人可删自己的回复；管理员可删任意评论
        r = client.post(f"{BASE}/comments", headers=user_h, json={"article_id": aid, "content": "待管理员删除"})
        victim_id = r.json()["comment"]["id"]
        r = client.delete(f"{BASE}/comments/{victim_id}", headers=ed_h)
        assert r.status_code == 403, f"非作者/管理员删除应被拒绝: {r.text}"
        r = client.delete(f"{BASE}/comments/{victim_id}", headers=admin_h)
        assert r.status_code == 200, f"管理员删除失败: {r.text}"
        print("[11] 评论删除权限 OK（本人/管理员可删，其他人 403）")
    
        r = client.delete(f"{BASE}/comments/{reply_id}", headers=user_h)
        assert r.status_code == 200, "作者删除自己的回复失败"
        print("[11] 作者删除自己的回复 OK")
    
    if should_run(12):
        # 12. 积分：未登录不可查/不可签；签到每天一次；后台可查看与调整
        r = client.get(f"{BASE}/points/me")
        assert r.status_code == 401, f"未登录查询积分应被拒绝: {r.text}"
        r = client.post(f"{BASE}/points/checkin")
        assert r.status_code == 401, f"未登录签到应被拒绝: {r.text}"
        print("[12] 未登录积分接口鉴权 OK")
    
        # 签到：当天未签则首次成功（1~5 随机），已签则返回"今日已签到"（幂等，测试可重复跑）
        r = client.post(f"{BASE}/points/checkin", headers=user_h)
        if r.status_code == 200:
            gained = r.json()["gained"]
            assert 1 <= gained <= 5, f"签到积分应在 1~5 之间: {gained}"
            assert r.json()["today_checked_in"] is True
            print(f"[12] 签到 OK  gained={gained} points={r.json()['points']}")
        else:
            assert r.status_code == 400 and "已签到" in r.text, f"签到异常: {r.text}"
            print("[12] 今日已签到（幂等通过）")
    
        # 每日一次限制：无论上面结果如何，再次签到必须被拒绝
        r = client.post(f"{BASE}/points/checkin", headers=user_h)
        assert r.status_code == 400, f"重复签到应被拒绝: {r.text}"
        r = client.get(f"{BASE}/points/me", headers=user_h)
        assert r.json()["today_checked_in"] is True
        print("[12] 每日一次签到限制 OK")
    
        # 后台积分列表可见该用户及其签到记录
        r = client.get(f"{BASE}/admin/points", headers=admin_h, params={"keyword": "user"})
        assert r.status_code == 200, f"后台积分列表失败: {r.text}"
        row = next((u for u in r.json()["items"] if u["username"] == "user"), None)
        assert row and row["checkin_count"] >= 1, "后台积分列表缺少签到统计"
        print("[12] 后台积分列表 OK  checkin_count =", row["checkin_count"])
    
        # 非管理员访问后台积分接口应 403
        r = client.get(f"{BASE}/admin/points", headers=user_h)
        assert r.status_code == 403, f"非管理员访问后台积分应被拒绝: {r.text}"
    
        # 管理员调整积分：+10 与负数超扣
        r = client.put(f"{BASE}/admin/points/{row['id']}", headers=admin_h, json={"delta": 10})
        assert r.status_code == 200, f"加分失败: {r.text}"
        assert r.json()["points"] == row["points"] + 10
        r = client.put(f"{BASE}/admin/points/{row['id']}", headers=admin_h, json={"delta": -100000})
        assert r.status_code == 400, f"超量扣分应被拒绝: {r.text}"
        print("[12] 后台调整积分 OK（正加负减 + 下限保护）")
    
    if should_run(13):
        # 13. 编辑注册开关：默认开启可注册编辑；关闭后编辑注册被拒、普通用户注册正常
        r = client.put(f"{BASE}/portal/register-editor", headers=admin_h, json={"enabled": True})
        assert r.status_code == 200, f"开启编辑注册失败: {r.text}"
        r = client.post(f"{BASE}/auth/register", json={
            "username": f"ed_reg_{uniq}", "password": "pass123", "role": "editor",
        })
        assert r.status_code == 200, f"开启时注册编辑应成功: {r.text}"
        print("[13] 编辑注册开启状态 OK")
    
        r = client.put(f"{BASE}/portal/register-editor", headers=admin_h, json={"enabled": False})
        assert r.status_code == 200
        r = client.post(f"{BASE}/auth/register", json={
            "username": f"ed_reg2_{uniq}", "password": "pass123", "role": "editor",
        })
        assert r.status_code == 400 and "编辑注册已关闭" in r.text, f"关闭时注册编辑应被拒绝: {r.text}"
        r = client.post(f"{BASE}/auth/register", json={
            "username": f"u_reg_{uniq}", "password": "pass123", "role": "user",
        })
        assert r.status_code == 200, f"关闭时注册普通用户应成功: {r.text}"
        print("[13] 编辑注册关闭状态 OK（编辑被拒、普通用户正常）")
    
        # 恢复开启，避免影响后续测试/演示环境
        r = client.put(f"{BASE}/portal/register-editor", headers=admin_h, json={"enabled": True})
        assert r.status_code == 200
        print("[13] 编辑注册策略已恢复开启")
    
    if should_run(14):
        # 14. OSS 配置：备份 → 验证上传分支 → 恢复原配置（不破坏真实环境的 OSS/MinIO 配置）
        saved = client.get(f"{BASE}/portal/oss-config", headers=admin_h)
        assert saved.status_code == 200
        saved_cfg = saved.json()["config"]
        was_configured = bool(saved_cfg["endpoint"])
        print(f"[14] OSS 配置读取 OK（当前{'已配置' if was_configured else '未配置'}）")
    
        files = {"file": ("test_oss.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")}
        if not was_configured:
            # 未配置：上传走本地，回归原逻辑
            r = client.post(f"{BASE}/resources/upload", headers=ed_h, files=files)
            assert r.status_code == 200, f"本地上传失败: {r.text}"
            assert r.json()["resource"]["storage"] == "local"
            assert "/static/" in r.json()["resource"]["url"], f"本地资源 URL 异常: {r.json()['resource']['url']}"
            print("[14] 未配置 OSS 上传走本地 OK")
        else:
            # 已配置：跳过本地回归，避免向真实 OSS 上传测试文件
            print("[14] 当前已配置 OSS，跳过本地上传回归（避免污染真实存储）")
    
        # 用无效 endpoint 覆盖配置，验证上传走 OSS 分支且明确报错；secret_key 传 **** 保留原值
        r = client.put(f"{BASE}/portal/oss-config", headers=admin_h, json={
            "endpoint": "http://127.0.0.1:9",
            "bucket": "test-bucket",
            "region": "us-east-1",
            "access_key": "test",
            "secret_key": "****",
            "path_prefix": "articles/",
            "public_base_url": "",
        })
        assert r.status_code == 200 and r.json()["configured"] is True
        assert r.json()["config"]["secret_key"] == "****", "secret_key 应脱敏"
        print("[14] OSS 配置保存/脱敏 OK")
    
        r = client.post(f"{BASE}/resources/upload", headers=ed_h, files=files)
        assert r.status_code == 502 and "对象存储上传失败" in r.text, f"应报 OSS 上传失败: {r.text}"
        print("[14] OSS 上传失败明确报错 OK")
    
        # 恢复原配置：secret_key 传 **** 保留原值，保证真实环境的密钥不受影响
        r = client.put(f"{BASE}/portal/oss-config", headers=admin_h, json={
            **saved_cfg,
            "secret_key": "****",
        })
        assert r.status_code == 200 and r.json()["configured"] == was_configured
        restored = client.get(f"{BASE}/portal/oss-config", headers=admin_h).json()["config"]
        assert restored["endpoint"] == saved_cfg["endpoint"] and restored["bucket"] == saved_cfg["bucket"]
        print("[14] OSS 配置已恢复原值 OK")
    
    if should_run(15):
        # 15. 下线文稿重新编辑并再次发布：offline → 编辑 → 提审 → 一审 → 二审 → published
        r = client.post(f"{BASE}/articles/{aid}/offline", headers=admin_h)
        assert r.status_code == 200 and r.json()["article"]["status"] == "offline", f"下线失败: {r.text}"
        print("[15] 已发布文稿下线 OK")
    
        # 作者编辑已下线文稿，状态保持 offline
        r = client.put(f"{BASE}/articles/{aid}", headers=ed_h, json={
            "title": "测试文稿：人工智能如何改变新闻业（修订版）",
            "summary": "下线后重新编辑并再次发布",
            "content": "<p>修订后的正文内容。</p>",
            "cover_url": "",
            "category_ids": cat_ids,
        })
        assert r.status_code == 200 and r.json()["article"]["status"] == "offline", f"下线稿编辑失败: {r.text}"
        assert "修订版" in r.json()["article"]["title"]
        print("[15] 下线稿编辑 OK（状态保持已下线）")
    
        # 15.1 编辑向量化钩子：标题已变化，向量源文本哈希应同步更新
        r = client.get(f"{BASE}/embeddings/article/{aid}", headers=admin_h)
        assert r.status_code == 200, f"编辑后文稿应有向量化记录: {r.text}"
        assert r.json()["embedding"]["source_hash"] != emb_hash_before_edit, "标题变化后向量未更新"
        print("[15.1] 文稿编辑向量化钩子 OK（source_hash 已更新）")
    
        # 重新提审 → 两级审核 → 再发布
        r = client.post(f"{BASE}/articles/{aid}/submit", headers=ed_h)
        assert r.status_code == 200 and r.json()["article"]["status"] == "pending_first", f"重新提审失败: {r.text}"
        print("[15] 下线稿重新提审 OK ->", r.json()["article"]["status"])
    
        r = client.post(f"{BASE}/reviews", headers=admin_h, json={
            "article_id": aid, "level": 1, "action": "approve", "comment": "修订版一审通过",
        })
        assert r.status_code == 200 and r.json()["article"]["status"] == "pending_second", f"修订版一审失败: {r.text}"
        r = client.post(f"{BASE}/reviews", headers=admin2_h, json={
            "article_id": aid, "level": 2, "action": "approve", "comment": "修订版二审通过",
        })
        assert r.status_code == 200 and r.json()["article"]["status"] == "published", f"修订版二审失败: {r.text}"
        assert r.json()["article"]["published_at"], "再发布后应更新时间"
        print("[15] 重新审核通过并再发布 OK ->", r.json()["article"]["status"])
    
    if should_run(16):
        # 16. 批量导入：构造 xlsx 覆盖成功/重复/栏目不匹配/封面缺失/标题为空分支
        wb = Workbook()
        ws = wb.active
        ws.append(["封面", "标题", "分类", "正文"])
        ws.append(["", f"导入测试文稿A_{uniq}", "游戏", "这是正文第一段。\n这是正文第二段。"])
        ws.append(["", f"导入测试文稿A_{uniq}", "游戏", "重复标题"])
        ws.append(["", f"导入测试文稿B_{uniq}", "游戏/不存在栏目", "正文B"])
        ws.append(["", f"导入测试文稿C_{uniq}", "", "正文C"])
        ws.append(["", "", "游戏", "标题为空"])
        buf = _io.BytesIO()
        wb.save(buf)
        r = httpx.post(f"{BASE}/articles/import", headers=ed_h, timeout=120, files={
            "file": ("import_test.xlsx", buf.getvalue(),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        })
        assert r.status_code == 200, f"批量导入失败: {r.text}"
        res = r.json()
        assert res["imported"] == 3, f"应导入 3 篇: {res}"
        assert len(res["skipped"]) == 1 and res["skipped"][0]["reason"] == "标题已存在"
        assert len(res["failed"]) == 1 and res["failed"][0]["reason"] == "标题为空"
        assert any("栏目未匹配" in w["reason"] for w in res["warnings"])
        print(f"[16] 批量导入 OK imported={res['imported']} skipped={len(res['skipped'])} failed={len(res['failed'])}")
    
        # 导入的文稿为草稿且栏目正确（导入测试文稿B → 游戏栏目）
        r = client.get(f"{BASE}/articles/mine", headers=ed_h, params={"page_size": 50})
        imported_a = next((a for a in r.json()["items"] if a["title"] == f"导入测试文稿A_{uniq}"), None)
        assert imported_a and imported_a["status"] == "draft", "导入文稿应为草稿"
        assert imported_a["summary"] == "", "导入文稿摘要应留空（不自动截取正文首段）"
        print("[16] 导入文稿状态/摘要（留空） OK")
    
        # 16.1 批量导入向量化钩子：导入的文稿已向量化入库
        r = client.get(f"{BASE}/embeddings/article/{imported_a['id']}", headers=admin_h)
        assert r.status_code == 200, f"导入文稿应自动向量化: {r.text}"
        print("[16.1] 批量导入向量化钩子 OK")
    
        # 非 xlsx 文件拒绝
        r = client.post(f"{BASE}/articles/import", headers=ed_h, files={"file": ("bad.txt", b"hello", "text/plain")})
        assert r.status_code == 400 and ".xlsx" in r.text, f"非 xlsx 应被拒绝: {r.text}"
        print("[16] 非 xlsx 文件拒绝 OK")
    
    if should_run(17):
        # 17. 轮播随机选取：候选池=已发布且带封面文稿；发布带封面文稿后 total 精确 +1
        r = client.get(f"{BASE}/portal/banner/random", headers=admin_h, params={"count": 5})
        assert r.status_code == 200, f"随机选取接口失败: {r.text}"
        assert "total" in r.json(), "随机接口应返回候选总数 total"
        total_before = r.json()["total"]
        assert 0 <= len(r.json()["items"]) <= 5, f"随机结果数量异常: {len(r.json()['items'])}"
        assert all(i["cover_url"] for i in r.json()["items"]), "随机结果必须全部带封面"
        assert all(i["link"].startswith("/article/") for i in r.json()["items"]), "随机结果应带文稿链接"
        print(f"[17] 轮播随机选取接口 OK  total={total_before} items={len(r.json()['items'])}")
    
        r = client.post(f"{BASE}/articles", headers=ed_h, json={
            "title": f"带封面文稿_{uniq}",
            "summary": "用于轮播随机选取测试",
            "content": "<p>带封面正文。</p>",
            "cover_url": "https://example.com/cover.jpg",
            "category_ids": cat_ids,
        })
        assert r.status_code == 200, f"创建带封面文稿失败: {r.text}"
        cover_aid = r.json()["article"]["id"]
        r = client.post(f"{BASE}/articles/{cover_aid}/submit", headers=ed_h)
        assert r.status_code == 200 and r.json()["article"]["status"] == "pending_first"
        r = client.post(f"{BASE}/reviews", headers=admin_h,
                        json={"article_id": cover_aid, "level": 1, "action": "approve", "comment": "带封面文稿一审"})
        assert r.status_code == 200 and r.json()["article"]["status"] == "pending_second"
        r = client.post(f"{BASE}/reviews", headers=admin2_h,
                        json={"article_id": cover_aid, "level": 2, "action": "approve", "comment": "带封面文稿二审"})
        assert r.status_code == 200 and r.json()["article"]["status"] == "published"
        print(f"[17] 带封面文稿发布 OK  id={cover_aid}")
    
        r = client.get(f"{BASE}/portal/banner/random", headers=admin_h, params={"count": 5})
        assert r.status_code == 200, f"随机选取接口失败: {r.text}"
        assert r.json()["total"] == total_before + 1, \
            f"发布带封面文稿后候选池应 +1: {total_before} -> {r.json()['total']}"
        assert 0 <= len(r.json()["items"]) <= 5
        assert all(i["cover_url"] for i in r.json()["items"]), "随机结果必须全部带封面"
        print(f"[17] 发布带封面文稿后候选池 OK  total={r.json()['total']}")
    
        # 边界：count 越界拒绝；非管理员 403
        r = client.get(f"{BASE}/portal/banner/random", headers=admin_h, params={"count": 0})
        assert r.status_code in (400, 422), f"count=0 应被拒绝: {r.text}"
        r = client.get(f"{BASE}/portal/banner/random", headers=admin_h, params={"count": 11})
        assert r.status_code in (400, 422), f"count=11 应被拒绝: {r.text}"
        r = client.get(f"{BASE}/portal/banner/random", headers=user_h)
        assert r.status_code == 403, f"非管理员应 403: {r.text}"
        print("[17] 随机选取边界/权限校验 OK")
    
    if should_run(18):
        # 18. AI 协作台异步任务：提交立即返回 task_id，轮询后拿到与假实现一致的结果
        ai_title = f"AI异步测试文稿_{uniq}"
        ai_content = "<p>这是一篇用于 AI 异步任务测试的正文。</p>"
    
        # 未登录提交拒绝
        r = client.post(f"{BASE}/ai/assist/classify", json={"title": ai_title})
        assert r.status_code == 401, f"未登录提交 AI 任务应 401: {r.text}"
        print("[18] AI 任务未登录拒绝 OK")
    
        # 缺前置输入拒绝（分类必须有标题）
        r = client.post(f"{BASE}/ai/assist/classify", headers=ed_h, json={"title": ""})
        assert r.status_code == 400, f"缺少标题应 400: {r.text}"
        print("[18] AI 任务入参校验 OK")
    
        # 在线知识库：写入冒烟关键词（→科学），分类断言走知识库强兜底，不依赖模型效果
        ai_classify_title = "smoke_kb_person 出席国际会议"
        r = client.put(f"{BASE}/settings/ai_knowledge_base", headers=admin_h, json={
            "value": {"smoke_kb_person": {"title": "冒烟测试人物", "category": "科学"}},
            "value_type": "json",
        })
        assert r.status_code == 200, f"写入在线知识库失败: {r.text}"
        print("[18] 在线知识库写入 OK")
    
        # 逐个提交 5 类任务并轮询到成功，校验结果结构（classify 命中知识库返回科学）
        cases = [
            ("classify", {"title": ai_classify_title}, lambda d: d["category_name"] == "科学"),
            # 摘要已接入真实 Dify 工作流，断言返回非空摘要文本（占位/真实实现均成立）
            ("summary", {"title": ai_title, "content": ai_content}, lambda d: bool(str(d.get("summary", "")).strip())),
            # 多维度审核已接入真实 Dify 工作流 article_weidu，断言返回结构化结果
            ("review", {"title": ai_title, "content": ai_content}, lambda d: "overall_risk" in d and isinstance(d.get("risk_list"), list)),
            # 内容校验已接入真实 Dify 工作流 article_neirong，断言返回 items 列表即可（条数取决于模型）
            ("check", {"content": ai_content}, lambda d: isinstance(d.get("items"), list)),
            # 文稿打分已接入真实 Dify 工作流 article_pingfen，入参标题+正文，断言返回结构化结果
            ("score", {"title": ai_title, "content": ai_content}, lambda d: "总分" in d and isinstance(d.get("分项评分"), list)),
        ]
        for name, payload, check in cases:
            r = client.post(f"{BASE}/ai/assist/{name}", headers=ed_h, json=payload)
            assert r.status_code == 200, f"{name} 提交任务失败: {r.text}"
            task_id = r.json()["task_id"]
            assert r.json()["status"] == "pending", f"{name} 初始状态应为 pending: {r.text}"
            # 摘要走真实 Dify 工作流，耗时可能较长，放宽轮询上限
            done = wait_ai_task(client, ed_h, task_id, max_wait=180 if name == "summary" else 30)
            assert done["status"] == "success", f"{name} 任务失败: {done}"
            assert done["feature_name"], f"{name} 应返回功能中文名"
            assert check(done["result"]), f"{name} 结果不符合占位实现: {done['result']}"
            print(f"[18] AI {name} 异步任务 OK  task_id={task_id} status={done['status']}")
    
        # 恢复在线知识库为「删除配置」，回退到本地 knowledge_base.json（斯塔默→政治等），不污染演示数据
        r = client.delete(f"{BASE}/settings/ai_knowledge_base", headers=admin_h)
        assert r.status_code == 200, f"恢复在线知识库失败: {r.text}"
        print("[18] 在线知识库已恢复（回退本地文件）")
    
        # 权限：普通用户查询他人任务 403；查询不存在的任务 404；本人可查
        first_task_id = None
        r = client.post(f"{BASE}/ai/assist/classify", headers=ed_h, json={"title": ai_title})
        first_task_id = r.json()["task_id"]
        r = client.get(f"{BASE}/ai/assist/tasks/{first_task_id}", headers=user_h)
        assert r.status_code == 403, f"普通用户查他人任务应 403: {r.text}"
        r = client.get(f"{BASE}/ai/assist/tasks/99999999", headers=ed_h)
        assert r.status_code == 404, f"不存在的任务应 404: {r.text}"
        r = client.get(f"{BASE}/ai/assist/tasks/{first_task_id}", headers=ed_h)
        assert r.status_code == 200, f"本人查询任务失败: {r.text}"
        print("[18] AI 任务权限/404/本人查询 OK")
    
        # 后台 AI 调用记录应包含本次异步任务产生的成功记录（最近一条分类记录入参匹配）
        r = client.get(f"{BASE}/admin/ai-calls", headers=admin_h, params={"feature_type": 1, "page_size": 5})
        assert r.status_code == 200, f"查询 AI 调用记录失败: {r.text}"
        logs = r.json()["items"]
        assert any(
            (log.get("input_params") or {}).get("title") == ai_classify_title
            for log in logs
        ), "后台 AI 调用记录应包含异步任务产生的记录"
        print(f"[18] AI 调用记录落库 OK  total={r.json()['total']}")
    
    if should_run(19):
        # 19. AI 分类纠正数据集：登录用户提交纠正 → 后台列表/导出；权限边界
        corr_title = f"AI分类纠正样本_{uniq}"
        r = client.post(f"{BASE}/ai/assist/corrections", json={
            "title": corr_title, "content": "这是纠正样本正文。",
            "model_category": "游戏", "corrected_category": "科学",
        })
        assert r.status_code == 401, f"未登录提交纠正应 401: {r.text}"
        print("[19] 纠正未登录拒绝 OK")
    
        r = client.post(f"{BASE}/ai/assist/corrections", headers=ed_h, json={
            "title": "", "content": "", "model_category": "游戏", "corrected_category": "科学",
        })
        assert r.status_code in (400, 422), f"缺标题应 400/422: {r.text}"
        r = client.post(f"{BASE}/ai/assist/corrections", headers=ed_h, json={
            "title": corr_title, "content": "这是纠正样本正文。",
            "model_category": "游戏", "corrected_category": "",
        })
        assert r.status_code in (400, 422), f"缺纠正分类应 400/422: {r.text}"
        print("[19] 纠正入参校验 OK")
    
        r = client.post(f"{BASE}/ai/assist/corrections", headers=ed_h, json={
            "title": corr_title, "content": "这是纠正样本正文。",
            "model_category": "游戏", "corrected_category": "科学",
            "article_id": aid,
        })
        assert r.status_code == 200 and r.json()["id"], f"提交纠正失败: {r.text}"
        print(f"[19] 提交纠正 OK  id={r.json()['id']}")
    
        # 后台列表：非管理员 403；管理员可检索到刚提交的样本
        r = client.get(f"{BASE}/admin/ai-corrections", headers=user_h)
        assert r.status_code == 403, f"非管理员访问数据集应 403: {r.text}"
        r = client.get(f"{BASE}/admin/ai-corrections", headers=admin_h, params={"keyword": corr_title})
        assert r.status_code == 200 and r.json()["total"] >= 1, f"数据集列表异常: {r.text}"
        row = r.json()["items"][0]
        assert row["title"] == corr_title and row["corrected_category"] == "科学"
        assert row["model_category"] == "游戏" and row["article_id"] == aid
        print("[19] 后台数据集列表/检索 OK")
    
        # 导出 JSON（全量训练样本）
        r = client.get(f"{BASE}/admin/ai-corrections/export", headers=admin_h)
        assert r.status_code == 200 and "application/json" in r.headers.get("content-type", "")
        exported = r.json()
        assert any(x["title"] == corr_title and x["corrected_category"] == "科学" for x in exported)
        print(f"[19] 数据集导出 OK  共 {len(exported)} 条")
    
        # 导出按日期区间过滤：未来区间应为空，不传参数为全量
        r = client.get(f"{BASE}/admin/ai-corrections/export", headers=admin_h,
                       params={"start_date": "2027-01-01", "end_date": "2027-01-02"})
        assert r.status_code == 200 and r.json() == [], f"未来日期区间导出应为空: {r.text[:200]}"
        print("[19] 导出日期区间过滤 OK（未来区间为空）")
    
    if should_run(20):
        # 20. 文稿向量化：全量向量化入库（仅管理员；幂等可重跑，upsert 覆盖旧向量）
        r = client.post(f"{BASE}/embeddings/vectorize", headers=ed_h)
        assert r.status_code == 403, f"非管理员调用向量化应 403: {r.text}"
        r = httpx.post(f"{BASE}/embeddings/vectorize", headers=admin_h, timeout=120)
        assert r.status_code == 200, f"向量化失败: {r.text}"
        res = r.json()
        assert res["total"] > 0, "向量化数量应大于 0"
        assert res["stats"]["by_version"].get("BAAI_bge-small-zh", 0) >= res["total"], "向量化记录未入库"
        print(f"[20] 文稿向量化入库 OK  total={res['total']} model={res['model_version']}")

    if should_run(21):
        # 21. 用户个性化推荐：未登录通用推荐；登录后排除已观看/不感兴趣；
        #     观看历史满 20 篇后触发向量召回（KNN top-50 + 热门兜底）
        r = client.get(f"{BASE}/articles/recommend")
        assert r.status_code == 200, f"未登录推荐失败: {r.text}"
        anon_items = r.json()["items"]
        assert anon_items, "推荐结果不应为空"
        assert r.json()["total"] == len(anon_items) and len(anon_items) <= 8, f"推荐数量异常: {r.text}"
        ids = [a["id"] for a in anon_items]
        assert len(ids) == len(set(ids)), "推荐结果不应包含重复文稿"
        assert all(a["status"] == "published" for a in anon_items), "推荐必须是已发布文稿"
        print(f"[21] 未登录通用推荐 OK  items={len(anon_items)}")

        # limit 参数：指定数量与越界校验
        r = client.get(f"{BASE}/articles/recommend", params={"limit": 3})
        assert r.status_code == 200 and 1 <= len(r.json()["items"]) <= 3, f"limit=3 推荐异常: {r.text}"
        r = client.get(f"{BASE}/articles/recommend", params={"limit": 0})
        assert r.status_code == 422, f"limit=0 应 422: {r.text}"
        r = client.get(f"{BASE}/articles/recommend", params={"limit": 21})
        assert r.status_code == 422, f"limit=21 应 422: {r.text}"
        print("[21] 推荐 limit 参数/越界校验 OK")

        # 登录用户：访问详情页（写入 view_history）后，推荐不应再包含该篇
        watch_target = ids[0]
        r = client.get(f"{BASE}/articles/{watch_target}", headers=user_h)
        assert r.status_code == 200, f"访问详情页失败: {r.text}"
        r = client.get(f"{BASE}/articles/recommend", headers=user_h, params={"limit": 20}, timeout=120)
        assert r.status_code == 200 and r.json()["items"], f"登录推荐失败: {r.text}"
        assert all(a["id"] != watch_target for a in r.json()["items"]), "推荐不应包含已观看文稿"
        print(f"[21] 登录推荐排除已观看 OK  watch_target={watch_target}")

        # 给 user 补足 20 条观看历史（访问详情页写入 view_history），触发向量召回分支
        r = client.get(f"{BASE}/articles", params={"page_size": 20})
        assert r.status_code == 200 and len(r.json()["items"]) >= 20, "需要至少 20 篇已发布文稿用于向量召回测试"
        history_ids = [a["id"] for a in r.json()["items"]]
        for article_id in history_ids:
            r = client.get(f"{BASE}/articles/{article_id}", headers=user_h)
            assert r.status_code == 200, f"补观看历史失败 article_id={article_id}"
        r = client.get(f"{BASE}/articles/recommend", headers=user_h, timeout=120)
        assert r.status_code == 200, f"向量召回推荐失败: {r.text}"
        vec_items = r.json()["items"]
        assert vec_items, "向量召回推荐结果不应为空"
        assert len(vec_items) <= 8, f"向量召回推荐数量异常: {len(vec_items)}"
        vec_ids = [a["id"] for a in vec_items]
        assert len(vec_ids) == len(set(vec_ids)), "向量召回推荐不应包含重复文稿"
        assert all(a["status"] == "published" for a in vec_items), "向量召回推荐必须是已发布文稿"
        assert not (set(vec_ids) & set(history_ids)), "向量召回推荐不应包含最近观看过的文稿"
        print(f"[21] 向量召回推荐 OK（观看历史≥20 篇，items={len(vec_items)}）")

        # 标记不感兴趣后排除，再取消恢复（不污染演示数据）
        if len(ids) >= 2:
            dislike_target = ids[1]
            r = client.post(f"{BASE}/interactions/dislike?article_id={dislike_target}", headers=user_h)
            assert r.status_code == 200, f"标记不感兴趣失败: {r.text}"
            r = client.get(f"{BASE}/articles/recommend", headers=user_h, params={"limit": 20}, timeout=120)
            assert all(a["id"] != dislike_target for a in r.json()["items"]), "推荐不应包含不感兴趣文稿"
            r = client.delete(f"{BASE}/interactions/dislike?article_id={dislike_target}", headers=user_h)
            assert r.status_code == 200, f"取消不感兴趣失败: {r.text}"
            print(f"[21] 登录推荐排除不感兴趣 OK  dislike_target={dislike_target}")
        else:
            print("[21] 候选不足，跳过不感兴趣排除断言")

    if should_run(22):
        # 22. 门户"为你推荐"模块开关：管理员可读全部模块；关闭后前台不再返回；
        #     非管理员访问后台模块接口 403
        r = client.get(f"{BASE}/portal/modules/admin", headers=user_h)
        assert r.status_code == 403, f"非管理员读取全量模块应 403: {r.text}"
        print("[22] 全量模块接口权限校验 OK（普通用户 403）")

        r = client.get(f"{BASE}/portal/modules/admin", headers=admin_h)
        assert r.status_code == 200, f"管理员读取全量模块失败: {r.text}"
        modules = r.json()["items"]
        assert any(m["module_key"] == "recommend" for m in modules), "缺少 recommend 模块（需先跑 init_db.py）"
        print("[22] 管理员读取全量模块 OK（含 recommend 开关）")

        # 关闭 recommend → 前台公开接口不再返回该模块；恢复开启
        r = client.put(f"{BASE}/portal/modules/recommend", headers=admin_h,
                       json={"module_key": "recommend", "title": "个性化推荐", "content": {}, "enabled": False})
        assert r.status_code == 200 and r.json()["module"]["enabled"] is False, f"关闭推荐模块失败: {r.text}"
        r = client.get(f"{BASE}/portal/modules")
        assert r.status_code == 200 and not any(
            m["module_key"] == "recommend" for m in r.json()["items"]
        ), "关闭后前台仍返回 recommend 模块"
        print("[22] 关闭推荐模块后前台不再返回 OK")

        r = client.put(f"{BASE}/portal/modules/recommend", headers=admin_h,
                       json={"module_key": "recommend", "title": "个性化推荐", "content": {}, "enabled": True})
        assert r.status_code == 200 and r.json()["module"]["enabled"] is True, f"恢复推荐模块失败: {r.text}"
        print("[22] 推荐模块已恢复开启 OK")

    if should_run(23):
        # 23. AI 协作台 draft_key：未保存草稿按草稿会话恢复；保存后任务/调用记录/纠正样本回填文稿ID
        dk = f"draft_{uniq}_{int(time.time() * 1000) % 1000000}"
        kb_key = f"smoke_dk_{uniq}"
        # 写入知识库关键词保证分类成功且结果确定（冒烟后删除，不污染演示数据）
        r = client.put(f"{BASE}/settings/ai_knowledge_base", headers=admin_h, json={
            "value": {kb_key: {"title": "冒烟草稿键", "category": "科学"}},
            "value_type": "json",
        })
        assert r.status_code == 200, f"写入知识库失败: {r.text}"
        kb_title = f"{kb_key} 出席国际会议"

        # 未保存草稿（无 article_id，带 draft_key）提交分类任务并轮询成功
        r = client.post(f"{BASE}/ai/assist/classify", headers=ed_h,
                        json={"title": kb_title, "draft_key": dk})
        assert r.status_code == 200, f"提交分类任务失败: {r.text}"
        dk_task_id = r.json()["task_id"]
        done = wait_ai_task(client, ed_h, dk_task_id)
        assert done["status"] == "success" and done["result"]["category_name"] == "科学", f"分类任务异常: {done}"
        print(f"[23] 未保存草稿提交分类任务 OK  task_id={dk_task_id}")

        # 未保存草稿按 draft_key 恢复最近任务；两者都无时 404
        r = client.get(f"{BASE}/ai/assist/tasks/latest", headers=ed_h,
                       params={"feature_type": 1, "draft_key": dk})
        assert r.status_code == 200 and r.json()["task_id"] == dk_task_id, f"按 draft_key 恢复失败: {r.text}"
        r = client.get(f"{BASE}/ai/assist/tasks/latest", headers=ed_h, params={"feature_type": 1})
        assert r.status_code == 404, f"无 article_id/draft_key 应 404: {r.text}"
        print("[23] 未保存草稿按 draft_key 恢复 OK（无键 404）")

        # 草稿会话提交一条分类纠正（无 article_id，带 draft_key）
        corr_title = f"AI草稿键纠正_{uniq}"
        r = client.post(f"{BASE}/ai/assist/corrections", headers=ed_h, json={
            "title": corr_title, "content": "草稿键纠正正文", "model_category": "游戏",
            "corrected_category": "科学", "draft_key": dk,
        })
        assert r.status_code == 200, f"提交纠正失败: {r.text}"
        print("[23] 草稿会话提交分类纠正 OK")

        # 用 draft_key 创建文稿：保存后任务/调用记录/纠正样本自动回填文稿ID
        r = client.post(f"{BASE}/articles", headers=ed_h, json={
            "title": f"draft_key绑定测试_{uniq}", "summary": "草稿键绑定", "content": "<p>正文</p>",
            "content_source": "正文", "category_ids": cat_ids[:1], "channel_ids": [],
            "draft_key": dk,
        })
        assert r.status_code == 200, f"创建文稿失败: {r.text}"
        bound_aid = r.json()["article"]["id"]
        assert bound_aid, "创建文稿未返回 ID"
        print(f"[23] 携带 draft_key 创建文稿 OK  article_id={bound_aid}")

        # 后台调用记录：分类任务对应记录已回填文稿ID
        r = client.get(f"{BASE}/admin/ai-calls", headers=admin_h,
                       params={"feature_type": 1, "page_size": 20})
        assert r.status_code == 200, f"查询调用记录失败: {r.text}"
        log_row = next((x for x in r.json()["items"]
                        if (x.get("input_params") or {}).get("title") == kb_title), None)
        assert log_row and log_row.get("article_id") == bound_aid, f"调用记录未回填文稿ID: {log_row}"
        print("[23] 调用记录已回填文稿ID OK")

        # 纠正样本已回填文稿ID
        r = client.get(f"{BASE}/admin/ai-corrections", headers=admin_h, params={"keyword": corr_title})
        assert r.status_code == 200 and r.json()["total"] >= 1, "纠正样本列表异常"
        assert r.json()["items"][0]["article_id"] == bound_aid, "纠正样本未回填文稿ID"
        print("[23] 纠正样本已回填文稿ID OK")

        # 恢复知识库配置（回退本地文件），不污染演示数据
        r = client.delete(f"{BASE}/settings/ai_knowledge_base", headers=admin_h)
        assert r.status_code == 200, f"恢复知识库失败: {r.text}"
        print("[23] 知识库已恢复（回退本地文件）")

    if should_run(24):
        # 24. Dify 工作流：编辑时留空/掩码 Key 不覆盖真实 Key（回归 5927cc2 + 自动填充防护）
        wf_name = f"smoke_dify_{uniq}"
        wf_key = "app-smoke-test-key-1234567890"
        wf_payload = {
            "name": wf_name,
            "api_base": "http://127.0.0.1:8080/v1",
            "api_key": wf_key,
            "description": "冒烟测试工作流",
            "input_schema": {"title": "标题"},
            "enabled": True,
            "timeout": 30,
        }
        r = client.post(f"{BASE}/dify/workflows", headers=admin_h, json=wf_payload)
        assert r.status_code == 200, f"创建 Dify 工作流失败: {r.text}"
        wf_id = r.json()["workflow"]["id"]
        print(f"[24] 创建临时 Dify 工作流 OK  id={wf_id}")

        # 列表返回掩码 Key（**** 后四位）
        r = client.get(f"{BASE}/dify/workflows", headers=admin_h)
        row = next(x for x in r.json()["items"] if x["id"] == wf_id)
        assert row["api_key"] == "****7890", f"掩码 Key 异常: {row['api_key']}"
        masked_before = row["api_key"]

        edit_payload = {
            "name": wf_name, "api_base": "http://127.0.0.1:8080/v1",
            "description": "冒烟测试工作流（编辑）", "input_schema": {"title": "标题"},
            "enabled": True, "timeout": 30,
        }
        # 掩码占位 Key 提交：不覆盖真实 Key
        r = client.put(f"{BASE}/dify/workflows/{wf_id}", headers=admin_h,
                       json={**edit_payload, "api_key": "****FAKE"})
        assert r.status_code == 200, f"掩码 Key 编辑失败: {r.text}"
        assert r.json()["workflow"]["api_key"] == masked_before, "掩码 Key 不应覆盖真实 Key"
        # 空 Key 提交：不覆盖真实 Key
        r = client.put(f"{BASE}/dify/workflows/{wf_id}", headers=admin_h,
                       json={**edit_payload, "api_key": ""})
        assert r.status_code == 200, f"空 Key 编辑失败: {r.text}"
        assert r.json()["workflow"]["api_key"] == masked_before, "空 Key 不应覆盖真实 Key"
        print("[24] 留空/掩码 Key 不覆盖真实 Key OK")

        # 清理临时工作流
        r = client.delete(f"{BASE}/dify/workflows/{wf_id}", headers=admin_h)
        assert r.status_code == 200, f"删除临时工作流失败: {r.text}"
        print("[24] 临时工作流已清理 OK")

    if should_run(25):
        # 25. AI 新闻助手：默认 RAG 未启用时返回稳定的 503，不影响新闻系统。
        r = client.post(f"{BASE}/ai-news/chat", json={"question": "最近有哪些科技新闻？"})
        assert r.status_code == 503, f"RAG 未启用时 AI 新闻助手应返回 503: {r.text}"
        print("[25] AI 新闻助手未启用时的降级响应 OK")

    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"测试失败: {e}")
        sys.exit(1)
