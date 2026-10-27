// 统一 API 定义：按模块分组，方便二次开发维护
import client from './client'

// ---- 认证与个人中心 ----
export const authApi = {
  register: (data) => client.post('/auth/register', data),
  login: (data) => client.post('/auth/login', data),
  me: () => client.get('/auth/me'),
  updateMe: (data) => client.put('/auth/me', data),
}

// ---- 栏目 ----
export const categoryApi = {
  list: () => client.get('/categories'),
  manage: () => client.get('/categories/manage'),
  create: (data) => client.post('/categories', data),
  update: (id, data) => client.put(`/categories/${id}`, data),
  remove: (id) => client.delete(`/categories/${id}`),
}

// ---- 分发渠道 ----
export const channelApi = {
  list: () => client.get('/channels'),
  manage: () => client.get('/channels/manage'),
  create: (data) => client.post('/channels', data),
  update: (id, data) => client.put(`/channels/${id}`, data),
  remove: (id) => client.delete(`/channels/${id}`),
  // RSS 订阅地址（第三方平台读取用）
  rssUrl: (id) => `${window.location.origin}/api/channels/${id}/rss`,
}

// ---- 文稿 ----
export const articleApi = {
  list: (params) => client.get('/articles', { params }),
  cities: () => client.get('/articles/cities'),
  detail: (id) => client.get(`/articles/${id}`),
  aiSummary: (id) => client.post(`/articles/${id}/ai-summary`, null, { timeout: 180000 }),
  explainSelection: (id, selectedText) => client.post(`/articles/${id}/ai-selection-explanation`, { selected_text: selectedText }, { timeout: 180000 }),
  related: (id, params) => client.get(`/articles/${id}/related`, { params }),
  // 个性化推荐：可选登录，登录且历史足量时返回向量召回结果，否则通用推荐
  recommend: (params) => client.get('/articles/recommend', { params }),
  // 门户“为你推荐”：使用原dev向量/通用推荐逻辑
  portalRecommend: (params) => client.get('/articles/recommend/portal', { params }),
  mine: (params) => client.get('/articles/mine', { params }),
  adminList: (params) => client.get('/articles/admin', { params }),
  create: (data) => client.post('/articles', data),
  update: (id, data) => client.put(`/articles/${id}`, data),
  aiWriting: (id) => client.post(`/articles/${id}/ai-writing`, null, { timeout: 120000 }),
  submit: (id) => client.post(`/articles/${id}/submit`),
  offline: (id) => client.post(`/articles/${id}/offline`),
  remove: (id) => client.delete(`/articles/${id}`),
  // 批量导入：上传 Excel（封面/标题/分类/正文），返回导入统计
  importExcel: (formData) =>
    client.post('/articles/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    }),
}

// ---- AI 新闻助手 ----
export const aiNewsApi = {
  chat: (data) => client.post('/ai-news/chat', data, { timeout: 90000 }),
}

// ---- 审核 ----
export const reviewApi = {
  pending: (params) => client.get('/reviews/pending', { params }),
  history: (params) => client.get('/reviews/history', { params }),
  review: (data) => client.post('/reviews', data),
}

// ---- 互动（点赞/收藏/转发）----
export const interactionApi = {
  like: (articleId) => client.post('/interactions/like', null, { params: { article_id: articleId } }),
  unlike: (articleId) => client.delete('/interactions/like', { params: { article_id: articleId } }),
  favorite: (articleId) => client.post('/interactions/favorite', null, { params: { article_id: articleId } }),
  unfavorite: (articleId) => client.delete('/interactions/favorite', { params: { article_id: articleId } }),
  dislike: (articleId) => client.post('/interactions/dislike', null, { params: { article_id: articleId } }),
  undislike: (articleId) => client.delete('/interactions/dislike', { params: { article_id: articleId } }),
  share: (articleId, fingerprint) =>
    client.post('/interactions/share', null, { params: { article_id: articleId, fingerprint } }),
  status: (articleId) => client.get('/interactions/status', { params: { article_id: articleId } }),
  favorites: (params) => client.get('/interactions/favorites', { params }),
}

// ---- 观看历史（记录由后端在文章详情接口中自动写入，这里只做查询）----
export const historyApi = {
  list: (params) => client.get('/history', { params }),
  reportDuration: (articleId, seconds) => client.post(`/history/${articleId}/duration`, { seconds }),
}

// ---- 评论（前台：公开列表；发表/删除需登录）----
export const commentApi = {
  list: (params) => client.get('/comments', { params }),
  create: (data) => client.post('/comments', data),
  remove: (id) => client.delete(`/comments/${id}`),
}

// ---- 后台评论管理（管理员）----
export const adminCommentApi = {
  list: (params) => client.get('/admin/comments', { params }),
}

// ---- 积分（前台：签到与我的积分；均需登录）----
export const pointsApi = {
  me: () => client.get('/points/me'),
  checkin: () => client.post('/points/checkin'),
}

// ---- 后台积分管理（管理员）----
export const adminPointsApi = {
  list: (params) => client.get('/admin/points', { params }),
  adjust: (userId, delta) => client.put(`/admin/points/${userId}`, { delta }),
}

// ---- 后台用户行为（管理员）----
export const behaviorApi = {
  viewHistory: (params) => client.get('/admin/behavior/history', { params }),
  dislikes: (params) => client.get('/admin/behavior/dislikes', { params }),
}

// ---- 埋点 ----
export const eventApi = {
  report: (data) => client.post('/events', data),
}

// ---- 用户兴趣偏好（登录后多选栏目）----
export const preferenceApi = {
  get: () => client.get('/preferences'),
  save: (categoryIds) => client.put('/preferences', { category_ids: categoryIds }),
}

// ---- 资源 ----
export const resourceApi = {
  upload: (formData) =>
    client.post('/resources/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    }),
  // 通过线上图片链接下载入库（后端流式下载，限制大小与图片类型）
  uploadByUrl: (data) => client.post('/resources/upload-by-url', data, { timeout: 60000 }),
  list: (params) => client.get('/resources', { params }),
  remove: (id) => client.delete(`/resources/${id}`),
}

// ---- 门户模块 ----
export const portalApi = {
  modules: () => client.get('/portal/modules'),
  allModules: () => client.get('/portal/modules/admin'),
  create: (data) => client.post('/portal/modules', data),
  update: (key, data) => client.put(`/portal/modules/${key}`, data),
  // 随机选取带封面的已发布文稿（后台一键填充轮播）
  bannerRandom: (count = 5) => client.get('/portal/banner/random', { params: { count } }),
  grayscale: () => client.get('/portal/grayscale'),
  splash: () => client.get('/portal/splash'),
  setSplash: (enabled) => client.put('/portal/splash', { enabled }),
  // 注册为编辑的开放策略（公开读；管理员写）
  registerEditor: () => client.get('/portal/register-editor'),
  setRegisterEditor: (enabled) => client.put('/portal/register-editor', { enabled }),
  // 门户 AI 阅读功能总开关（公开读；管理员写）
  aiReading: () => client.get('/portal/ai-reading'),
  setAiReading: (enabled) => client.put('/portal/ai-reading', { enabled }),
  // S3 兼容对象存储配置（管理员；endpoint 留空 = 本地存储）
  ossConfig: () => client.get('/portal/oss-config'),
  setOssConfig: (data) => client.put('/portal/oss-config', data),
}

// ---- 门户主题 ----
export const themeApi = {
  get: () => client.get('/portal/theme'),
  set: (theme) => client.put('/portal/theme', { theme }),
}

// ---- 用户管理 ----
export const userApi = {
  list: (params) => client.get('/users', { params }),
  create: (data) => client.post('/users', data),
  update: (id, data) => client.put(`/users/${id}`, data),
  remove: (id) => client.delete(`/users/${id}`),
}

// ---- 统计 ----
export const statsApi = {
  overview: () => client.get('/stats/overview'),
  trends: (params) => client.get('/stats/trends', { params }),
  topArticles: (params) => client.get('/stats/articles', { params }),
  categories: (params) => client.get('/stats/categories', { params }),
  events: (params) => client.get('/stats/events', { params }),
  userActivity: (params) => client.get('/stats/user-activity', { params }),
}

// ---- 系统设置 ----
export const settingsApi = {
  list: () => client.get('/settings'),
  create: (data) => client.post('/settings', data),
  update: (key, data) => client.put(`/settings/${key}`, data),
  remove: (key) => client.delete(`/settings/${key}`),
}

// ---- 文稿向量化（个性化推荐召回，管理员）----
export const embeddingApi = {
  // 全量文稿向量化入库：首次调用含模型加载，耗时可达数十秒，单独放宽超时
  vectorize: () => client.post('/embeddings/vectorize', null, { timeout: 180000 }),
}

// ---- Dify 工作流 ----
export const difyApi = {
  list: () => client.get('/dify/workflows'),
  create: (data) => client.post('/dify/workflows', data),
  update: (id, data) => client.put(`/dify/workflows/${id}`, data),
  remove: (id) => client.delete(`/dify/workflows/${id}`),
  run: (id, data, timeoutMs = 3600000) => client.post(`/dify/workflows/${id}/run`, data, { timeout: timeoutMs }),
}

// ---- AI 协作台（写稿页 AI 辅助功能：提交异步任务后轮询状态）----
export const aiAssistApi = {
  classify: (data) => client.post('/ai/assist/classify', data),
  summary: (data) => client.post('/ai/assist/summary', data),
  review: (data) => client.post('/ai/assist/review', data),
  check: (data) => client.post('/ai/assist/check', data),
  score: (data) => client.post('/ai/assist/score', data),
  latestTask: (featureType, articleId, draftKey) => client.get('/ai/assist/tasks/latest', { params: { feature_type: featureType, article_id: articleId || undefined, draft_key: draftKey || undefined } }),
  getTask: (taskId) => client.get(`/ai/assist/tasks/${taskId}`),
}

// ---- 后台 AI 调用记录（管理员）----
export const aiLogApi = {
  list: (params) => client.get('/admin/ai-calls', { params }),
}

// ---- AI 分类纠正数据集（写手提交纠正 / 管理员查看导出）----
export const aiCorrectionApi = {
  submit: (data) => client.post('/ai/assist/corrections', data),
  list: (params) => client.get('/admin/ai-corrections', { params }),
  exportJson: (params) => client.get('/admin/ai-corrections/export', { params, responseType: 'blob' }),
}

// ---- 智能采编：临时搜索保留；正式页面使用持久化任务接口 ----
export const smartCollectApi = {
  search: (data) => client.post('/smart-collect/search', data, { timeout: 20000 }),
  createTask: (data) => client.post('/smart-collect/tasks', data),
  listTasks: (params) => client.get('/smart-collect/tasks', { params }),
  getTask: (id) => client.get(`/smart-collect/tasks/${id}`),
  updateRelevance: (taskId, clueId, data) =>
    client.patch(`/smart-collect/tasks/${taskId}/clues/${clueId}/relevance`, data),
  similarityPairs: (taskId, params) =>
    client.get(`/smart-collect/tasks/${taskId}/similarity-pairs`, { params }),
  listEvents: (taskId) => client.get(`/smart-collect/tasks/${taskId}/events`),
  createEvent: (taskId, data) => client.post(`/smart-collect/tasks/${taskId}/events`, data),
  updateEvent: (taskId, eventId, data) =>
    client.patch(`/smart-collect/tasks/${taskId}/events/${eventId}`, data),
  addEventClues: (taskId, eventId, data) =>
    client.post(`/smart-collect/tasks/${taskId}/events/${eventId}/clues`, data),
  removeEventClue: (taskId, eventId, clueId) =>
    client.delete(`/smart-collect/tasks/${taskId}/events/${eventId}/clues/${clueId}`),
  deleteEvent: (taskId, eventId) =>
    client.delete(`/smart-collect/tasks/${taskId}/events/${eventId}`),
  prepareEventContent: (taskId, eventId) =>
    client.post(`/smart-collect/tasks/${taskId}/events/${eventId}/prepare-content`, null, {
      timeout: 60000,
    }),
  getEventEvidence: (taskId, eventId) =>
    client.get(`/smart-collect/tasks/${taskId}/events/${eventId}/evidence`),
  synthesizeEvent: (taskId, eventId) =>
    client.post(`/smart-collect/tasks/${taskId}/events/${eventId}/synthesize`, null, {
      timeout: 120000,
    }),
  listEventSyntheses: (taskId, eventId) =>
    client.get(`/smart-collect/tasks/${taskId}/events/${eventId}/syntheses`),
  getEventSynthesis: (taskId, eventId, synthesisId) =>
    client.get(`/smart-collect/tasks/${taskId}/events/${eventId}/syntheses/${synthesisId}`),
  approveEventSynthesis: (taskId, eventId, synthesisId) =>
    client.post(
      `/smart-collect/tasks/${taskId}/events/${eventId}/syntheses/${synthesisId}/approve`,
    ),
  rejectEventSynthesis: (taskId, eventId, synthesisId) =>
    client.post(
      `/smart-collect/tasks/${taskId}/events/${eventId}/syntheses/${synthesisId}/reject`,
    ),
  createArticleFromSynthesis: (taskId, eventId, synthesisId) =>
    client.post(
      `/smart-collect/tasks/${taskId}/events/${eventId}/syntheses/${synthesisId}/create-article`,
    ),
  getClueContent: (clueId) => client.get(`/smart-collect/clues/${clueId}/content`),
  evaluationSummary: () => client.get('/smart-collect/evaluation/summary'),
  evaluationOutliers: (params) => client.get('/smart-collect/evaluation/outliers', { params }),
}

// ---- 文章关键词（AI 提取的知识链，门户阅读页展示）----
export const keywordApi = {
  get: (articleId) => client.get(`/articles/${articleId}/keywords`),
  remove: (articleId) => client.delete(`/articles/${articleId}/keywords`),
  /** 流式解释标签，返回 ReadableStream */
  explainStream: (articleId, tag) =>
    fetch(`/api/articles/${articleId}/keywords/explain?tag=${encodeURIComponent(tag)}`),
}

// ---- 标签推荐（根据标签推荐关联文章）----
export const tagApi = {
  /** 根据标签推荐关联文章，返回 { source, tag, items, total, message } */
  recommend: (tag, articleId = null) => {
    const params = articleId ? { exclude_article_id: articleId } : {}
    return client.get(`/tags/${encodeURIComponent(tag)}/recommend`, { params, timeout: 20000 })
  },
}
