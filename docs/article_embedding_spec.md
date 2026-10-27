# 文稿向量化（article_embeddings）规格

> 状态：已确认（2026-08-14）。切片一（表结构 + CRUD 服务）已实现；
> 生成时机挂钩、内存计算层、推荐接口为后续切片。

## 1. 目标

将文稿"标题 + 分类"向量化并持久化，支撑基于用户最近浏览历史的个性化推荐召回链路：

- 文稿塔：文稿"标题 + 分类"的句向量（bge-small-zh，512 维，L2 归一化）
- 用户塔：view_history 最近 20 篇文稿向量的聚合（均值，可选观看时长加权）
- 召回：用户向量与已发布文稿向量余弦相似度 → 排除已读/不感兴趣 → top-K

## 2. 总体架构

- **MySQL `article_embeddings` 表为事实源**：持久化、多实例一致、重启可恢复；
  文稿创建/编辑/删除时同步维护。
- **运行时内存 numpy 矩阵为计算层**：启动时加载已发布文稿向量，
  发布/下线/编辑时增量刷新；推荐请求一次矩阵乘法完成召回。
- 当前规模（约 500 篇，512 维 ≈ 1MB）无需 Redis / 专用向量库；
  10 万篇量级（≈200MB）仍在 MySQL + numpy 暴力检索的可行范围内。

## 3. 数据结构

新表 `article_embeddings`（与 articles 一对一）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| article_id | INT，主键 + 外键→articles.id（ON DELETE CASCADE） | 文稿ID，删文稿自动级联清理向量 |
| embedding | BLOB，NOT NULL | 向量：float32 小端字节流（512 维 ≈ 2KB） |
| dim | INT，NOT NULL | 向量维度 |
| model_version | VARCHAR(50)，NOT NULL，索引 | 嵌入模型版本，如 `bge-small-zh-v1` |
| source_hash | VARCHAR(64)，NOT NULL | 源文本（标题+分类）SHA-256，未变更时跳过重算 |
| updated_at | DATETIME | 最近一次向量化时间 |

表由 `Base.metadata.create_all` 创建（`init_db.py` 与后端启动均幂等）。
向量独立于 articles 表的原因：避免 SQLAlchemy 全列加载拖累 Article 常规查询、
隔离热点行写入、派生数据独立版本管理（详见评审记录）。

## 4. 服务契约（app/services/embedding_service.py）

约定：所有函数**不 commit**，由调用方统一 `db.commit()`（项目事务约定）。

| 函数 | 签名 | 说明 |
| --- | --- | --- |
| upsert_embedding | (db, article_id, vector, model_version, source_hash) → ArticleEmbedding | 新建/覆盖向量（增/改） |
| get_embedding | (db, article_id) → ArticleEmbedding \| None | 单篇读取 |
| list_embeddings | (db, article_ids) → {article_id: 记录} | 批量读取 |
| load_published_matrix | (db, model_version=None) → [(article_id, vector)] | 加载全部已发布向量，供建内存矩阵 |
| delete_embedding | (db, article_id) → bool | 删除（删） |
| stats | (db) → {"total": n, "by_version": {...}} | 向量化统计（后台管理用） |
| find_missing_article_ids | (db, model_version, limit=None) → [article_id] | 指定版本未向量化的文稿（回填补丁用） |
| pack_vector / unpack_vector | list[float] ↔ bytes | float32 字节流互转；批量解码可用 np.frombuffer(dtype='<f4') |
| hash_source_text | (text) → sha256 hex | 源文本哈希 |

## 5. 预留事项（后续切片）

1. **生成时机**：articles.py 创建/编辑/删除处挂钩同步向量；管理员回填接口
   （find_missing_article_ids 取清单 → 模型编码 → upsert_embedding 批量写入）。
2. **内存计算层**：启动时 load_published_matrix 建矩阵；发布/下线/编辑成功后增量刷新。
3. **推荐接口**：`GET /api/articles/recommend`（需登录）——用户塔取 view_history
   最近 20 篇加权均值，余弦召回，排除已读/不感兴趣；匿名用户兜底热门/最新。
4. **模型切换流程**：model_version bump → find_missing_article_ids 全量重算 →
   upsert 覆盖旧行，表结构不变。

## 6. 成功标准

- [x] 切片一：init_db.py 幂等建表（新旧库均可）；CRUD 往返验证通过
- [ ] 切片二：生成时机挂钩 + 存量回填接口
- [ ] 切片三：内存计算层 + 个性化推荐接口（smoke_test 同步补充断言）