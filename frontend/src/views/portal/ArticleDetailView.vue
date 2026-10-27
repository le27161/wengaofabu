<template>
  <div class="container detail">
    <article ref="detailDocRef" v-loading="loading" class="detail__doc">
      <template v-if="article">
        <!-- 面包屑 -->
        <nav class="detail__crumb" aria-label="面包屑">
          <router-link to="/">首页</router-link>
          <template v-if="article.categories[0]">
            <span aria-hidden="true">/</span>
            <router-link :to="{ name: 'category', params: { slug: article.categories[0].slug } }">
              {{ article.categories[0].name }}
            </router-link>
          </template>
        </nav>

        <!-- 标题块 -->
        <header class="detail__head">
          <h1 class="detail__title">{{ article.title }}</h1>
          <p v-if="article.summary" class="detail__lead">{{ article.summary }}</p>
          <div class="detail__meta">
            <span class="detail__author">作者：{{ article.author_name }}</span>
            <span>{{ article.published_at }}</span>
            <span>{{ article.view_count }} 阅读</span>
          </div>
        </header>

        <figure v-if="article.cover_url" class="detail__cover">
          <img :src="article.cover_url" :alt="article.title" />
        </figure>

        <!-- 正文（编辑器以 HTML 形式编写，生产环境建议对 content 做 XSS 过滤） -->
        <div
          ref="contentRef"
          class="article-content detail__content"
          v-html="article.content"
        ></div>

        <!-- 关键词知识链（从 article_main_tags / article_sub_tags 双表读取） -->
        <KeywordPanel
          v-if="aiReadingEnabled"
          ref="keywordPanelRef"
          :keywords="keywords"
          :article-id="article?.id"
          @scroll-to-keyword="scrollToKeyword"
        />

        <!-- 互动栏：点赞 / 收藏 / 不感兴趣 / 转发 -->
        <footer class="detail__actions" role="group" aria-label="文稿互动">
          <button class="action-btn" :class="{ 'action-btn--active': liked }" :disabled="!auth.isLoggedIn" @click="toggleLike">
            <svg v-if="!liked" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M7 10v12M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
            </svg>
            <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
              <path d="M7 10v12M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
            </svg>
            <span>点赞 {{ article.like_count }}</span>
          </button>

          <button class="action-btn" :class="{ 'action-btn--active': favorited }" :disabled="!auth.isLoggedIn" @click="toggleFavorite">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            </svg>
            <span>收藏 {{ article.favorite_count }}</span>
          </button>

          <button class="action-btn" :class="{ 'action-btn--active': disliked }" :disabled="!auth.isLoggedIn" @click="toggleDislike">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
              <line x1="1" y1="1" x2="23" y2="23" />
            </svg>
            <span>不感兴趣</span>
          </button>

          <button class="action-btn"  :disabled="!auth.isLoggedIn" @click="share">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
              <path d="m8.59 13.51 6.83 3.98M15.41 6.51l-6.82 3.98" />
            </svg>
            <span>转发 {{ article.share_count }}</span>
          </button>
        </footer>
        <p v-if="!auth.isLoggedIn" class="detail__login-tip">
          <router-link to="/login">登录</router-link> 后可点赞、收藏、转发；<!--无需登录，同一浏览器只统计一次!-->
        </p>

        <!-- 评论区：登录可发表/回复，未登录提示登录；评论内容按纯文本插值渲染 -->
        <section class="comments" aria-label="文稿评论">
          <h2 class="comments__title">评论（{{ commentTotal }}）</h2>

          <!-- 发表区 -->
          <div v-if="auth.isLoggedIn" class="comments__composer">
            <el-avatar :size="36" :src="auth.user?.avatar || undefined">
              {{ (auth.user?.nickname || auth.user?.username || '我').slice(0, 1) }}
            </el-avatar>
            <div class="comments__composer-main">
              <el-input
                v-model="newComment"
                type="textarea"
                :rows="3"
                maxlength="2000"
                show-word-limit
                placeholder="写下你的评论…"
                resize="none"
              />
              <div class="comments__composer-foot">
                <el-button
                  type="primary"
                  :loading="submitting"
                  :disabled="!newComment.trim()"
                  @click="submitComment"
                >发表评论</el-button>
              </div>
            </div>
          </div>
          <div v-else class="comments__login-tip">
            <router-link :to="{ name: 'login', query: { redirect: route.fullPath } }">登录</router-link>
            后可参与评论
          </div>

          <!-- 评论列表 -->
          <div v-loading="commentLoading" class="comments__list-wrap">
            <ul v-if="comments.length" class="comments__list">
              <li v-for="c in comments" :key="c.id" class="comment">
                <el-avatar :size="36" :src="c.avatar || undefined">
                  {{ (c.nickname || '?').slice(0, 1) }}
                </el-avatar>
                <div class="comment__body">
                  <div class="comment__meta">
                    <span class="comment__name">{{ c.nickname }}</span>
                    <time class="comment__time">{{ c.created_at }}</time>
                    <button
                      v-if="c.is_mine || auth.user?.role === 'admin'"
                      class="comment__del"
                      @click="removeComment(c)"
                    >删除</button>
                  </div>
                  <p class="comment__content">{{ c.content }}</p>

                  <button
                    v-if="auth.isLoggedIn"
                    class="comment__reply-btn"
                    @click="toggleReply(c)"
                  >{{ replyTargetId === c.id ? '收起回复' : '回复' }}</button>

                  <!-- 回复输入框 -->
                  <div v-if="replyTargetId === c.id" class="comment__reply-composer">
                    <el-input
                      v-model="replyContent"
                      type="textarea"
                      :rows="2"
                      maxlength="2000"
                      :placeholder="`回复 ${c.nickname}…`"
                      resize="none"
                    />
                    <div class="comment__reply-actions">
                      <el-button size="small" @click="cancelReply">取消</el-button>
                      <el-button
                        size="small"
                        type="primary"
                        :loading="submitting"
                        :disabled="!replyContent.trim()"
                        @click="submitReply(c)"
                      >回复</el-button>
                    </div>
                  </div>

                  <!-- 回复列表 -->
                  <ul v-if="c.replies && c.replies.length" class="comment__replies">
                    <li v-for="r in c.replies" :key="r.id" class="comment__reply">
                      <el-avatar :size="30" :src="r.avatar || undefined">
                        {{ (r.nickname || '?').slice(0, 1) }}
                      </el-avatar>
                      <div class="comment__reply-main">
                        <div class="comment__meta">
                          <span class="comment__name">{{ r.nickname }}</span>
                          <time class="comment__time">{{ r.created_at }}</time>
                          <button
                            v-if="r.is_mine || auth.user?.role === 'admin'"
                            class="comment__del"
                            @click="removeReply(c, r)"
                          >删除</button>
                        </div>
                        <p class="comment__content">{{ r.content }}</p>
                      </div>
                    </li>
                  </ul>
                </div>
              </li>
            </ul>
            <p v-else-if="!commentLoading" class="comments__empty">还没有评论，来抢沙发～</p>
          </div>

          <!-- 加载更多 -->
          <div v-if="commentTotal > comments.length" class="comments__more">
            <el-button link type="primary" @click="loadMoreComments">加载更多评论</el-button>
          </div>
        </section>
      </template>
    </article>

    <!-- 相关推荐：同栏目文稿，按发布时间新到旧 -->
    <aside v-if="related.length" class="panel related">
      <h2 class="related__title">相关推荐</h2>
      <p class="related__subtitle">同栏目 · 最新发布</p>
      <ul class="related__list">
        <li v-for="a in related" :key="a.id">
          <router-link :to="{ name: 'article-detail', params: { id: a.id } }" class="related__item">
            <img
              v-if="a.cover_url"
              :src="a.cover_url"
              :alt="a.title"
              class="related__thumb"
              loading="lazy"
            />
            <span v-else class="related__thumb related__thumb--placeholder">
              {{ (a.categories[0]?.name || '文').slice(0, 1) }}
            </span>
            <span class="related__info">
              <span class="related__name">{{ a.title }}</span>
              <span class="related__meta">
                <span v-if="a.categories[0]" class="related__cat">{{ a.categories[0].name }}</span>
                <time>{{ (a.published_at || a.created_at || '').slice(0, 10) }}</time>
              </span>
            </span>
          </router-link>
        </li>
      </ul>
    </aside>

    <!-- 同一 AI 悬浮入口：未划选正文时总结全文，划选正文后解释选中内容。 -->
    <Teleport to="body">
      <button
        v-if="article && aiReadingEnabled"
        type="button"
        class="ai-summary-fab"
        :aria-expanded="aiSummaryOpen"
        aria-controls="ai-summary-panel"
        :aria-label="`打开 ${aiTaskTitle}`"
        :title="`拖动或打开 ${aiTaskTitle}`"
        :class="{ 'ai-summary-fab--dragging': aiFabDragging }"
        :style="aiFabStyle"
        @pointerdown="startAiFabDrag"
        @click="toggleAiSummary"
      >
        <el-icon><MagicStick /></el-icon>
      </button>

      <section
        v-if="article && aiSummaryOpen && aiReadingEnabled"
        id="ai-summary-panel"
        class="ai-summary-panel"
        :aria-label="aiTaskTitle"
        :style="aiSummaryPanelStyle"
      >
        <header class="ai-summary-panel__head">
          <div class="ai-summary-panel__title-group">
            <span class="ai-summary-panel__mark" aria-hidden="true"><el-icon><MagicStick /></el-icon></span>
            <h2>{{ aiTaskTitle }}</h2>
          </div>
          <div class="ai-summary-panel__tools">
            <button type="button" class="ai-summary-panel__close" :disabled="aiSummaryLoading" title="重新生成" @click="generateAiResponse">
              <el-icon><Refresh /></el-icon>
            </button>
            <button type="button" class="ai-summary-panel__close" aria-label="关闭 AI 助手" title="关闭" @click="aiSummaryOpen = false">
              <el-icon><Close /></el-icon>
            </button>
          </div>
        </header>
        <p v-if="aiSummaryLoading" class="ai-summary-panel__status">
          <el-icon class="is-loading"><Loading /></el-icon>{{ aiTaskLoadingText }}
        </p>
        <template v-else-if="aiSummary">
          <p v-if="aiSelectionText" class="ai-summary-panel__selection">“{{ aiSelectionText }}”</p>
          <p class="ai-summary-panel__content">{{ aiSummary }}</p>
        </template>
        <div v-else class="ai-summary-panel__status ai-summary-panel__status--error">
          <p>{{ aiSummaryError || `暂未生成${aiTaskTitle}` }}</p>
          <button type="button" class="ai-summary-panel__retry" @click="generateAiResponse">重新生成</button>
        </div>
      </section>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, Loading, MagicStick, Refresh } from '@element-plus/icons-vue'
import { articleApi, commentApi, eventApi, historyApi, interactionApi, keywordApi, portalApi } from '../../api'
import { useAuthStore } from '../../stores/auth'
import KeywordPanel from '../../components/KeywordPanel.vue'

const route = useRoute()
const auth = useAuthStore()
const article = ref(null)
const related = ref([])
const loading = ref(true)
const liked = ref(false)
const favorited = ref(false)
const disliked = ref(false)
// AI 阅读助手状态
const keywords = ref([])
const aiSummaryOpen = ref(false)
const aiSummary = ref('')
const aiSummaryLoading = ref(false)
const aiSummaryError = ref('')
const aiSummaryRequestId = ref(0)
const aiSelectionText = ref('')
const detailDocRef = ref(null)
const aiFabPosition = ref(null)
const aiFabDragging = ref(false)
const aiFabDragState = ref(null)
const aiFabDragged = ref(false)
const aiViewport = ref({ width: window.innerWidth, height: window.innerHeight })
const contentRef = ref(null)
const keywordPanelRef = ref(null)
const aiReadingEnabled = ref(true)
const aiTaskTitle = computed(() => aiSelectionText.value ? 'AI 划选解释' : 'AI 全文总结')
const aiTaskLoadingText = computed(() => aiSelectionText.value ? '正在解释划选内容…' : '正在生成总结…')
const aiFabStyle = computed(() => aiFabPosition.value ? {
  left: `${aiFabPosition.value.x}px`, top: `${aiFabPosition.value.y}px`, right: 'auto', bottom: 'auto',
} : {})
const aiSummaryPanelStyle = computed(() => {
  if (!aiFabPosition.value) return {}
  const { width, height } = aiViewport.value
  const panelWidth = Math.min(340, width - 32)
  const left = clamp(aiFabPosition.value.x, 16, Math.max(16, width - panelWidth - 16))
  if (aiFabPosition.value.y < height / 2) {
    const top = Math.min(aiFabPosition.value.y + 64, Math.max(16, height - 180))
    return { left: `${left}px`, top: `${top}px`, right: 'auto', bottom: 'auto', maxHeight: `${Math.max(164, height - top - 16)}px` }
  }
  return { left: `${left}px`, right: 'auto', top: 'auto', bottom: `${Math.max(16, height - aiFabPosition.value.y + 12)}px`, maxHeight: `${Math.max(164, aiFabPosition.value.y - 28)}px` }
})
// 评论状态
const comments = ref([])
const commentTotal = ref(0)
const commentPage = ref(1)
const commentPageSize = 10
const commentLoading = ref(false)
const newComment = ref('')
const replyTargetId = ref(null)
const replyContent = ref('')
const submitting = ref(false)

// 观看时长统计：进入页面记起点，离开/切后台时上报（单次会话上限 600 秒，每篇累计上限 30 分钟）
const watchStart = ref(Date.now())
const durationReported = ref(false)
const watchLimitReached = ref(false)

// 加载文章数据（首屏与相关推荐切换时都会调用）
async function loadArticle(id) {
  // 切换文章前，先上报上一篇文章的观看时长
  reportWatchDuration()
  loading.value = true
  article.value = null
  related.value = []
  liked.value = false
  favorited.value = false
  disliked.value = false
  durationReported.value = false
  watchLimitReached.value = false
  resetComments()
  stopKeywordPoll()
  try {
    const [detail, statusRes, aiReadingRes] = await Promise.all([
      articleApi.detail(id),
      auth.isLoggedIn ? interactionApi.status(id) : Promise.resolve({ liked: false, favorited: false, disliked: false }),
      portalApi.aiReading().catch(() => ({ enabled: true })),
    ])
    article.value = detail
    liked.value = statusRes.liked
    favorited.value = statusRes.favorited
    disliked.value = statusRes.disliked
    watchStart.value = Date.now()
    aiSummary.value = ''
    aiSummaryError.value = ''
    aiSelectionText.value = ''
    keywords.value = []
    aiReadingEnabled.value = aiReadingRes.enabled
    if (!aiReadingEnabled.value) aiSummaryOpen.value = false
    await nextTick()
    positionAiFabAtArticleStart()

    // 观看埋点：进入详情页即上报
    eventApi.report({ event_type: 'view', article_id: id }).catch(() => {})
    article.value.view_count += 1 // 本地乐观加一，避免刷新

    // 相关推荐：同栏目已发布文稿（后端按发布时间新到旧返回）
    const res = await articleApi.related(id, { limit: 6 })
    related.value = res.items
    // 加载关键词（静默失败，不影响主流程）
    if (aiReadingEnabled.value) {
      loadKeywords(id)
    }
    // 评论区：首次进入加载第一页
    loadComments()
    // 先移除再添加，避免多次切换文章时重复绑定
    window.removeEventListener('pagehide', onPageHide)
    window.addEventListener('pagehide', onPageHide)
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  window.addEventListener('resize', updateAiViewport)
  document.addEventListener('selectionchange', captureArticleSelection)
  loadArticle(Number(route.params.id))
})

// 相关推荐/同路由跳转：监听文章 id 变化，重新加载对应文章
watch(
  () => route.params.id,
  (val) => loadArticle(Number(val)),
)

onBeforeUnmount(() => {
  reportWatchDuration()
  window.removeEventListener('pagehide', onPageHide)
  window.removeEventListener('resize', updateAiViewport)
  document.removeEventListener('selectionchange', captureArticleSelection)
  stopAiFabDrag()
  stopKeywordPoll()
})

function onPageHide() {
  reportWatchDuration()
}

let keywordPollTimer = null
let keywordPollAttempts = 0
const KEYWORD_POLL_INTERVAL = 5000
const KEYWORD_POLL_LIMIT = 12

function stopKeywordPoll() {
  if (keywordPollTimer) {
    clearTimeout(keywordPollTimer)
    keywordPollTimer = null
  }
  keywordPollAttempts = 0
}

function loadKeywords(id) {
  if (!aiReadingEnabled.value || !article.value || Number(article.value.id) !== Number(id)) return
  keywordApi.get(id)
    .then((r) => {
      keywords.value = r.keywords || []
      if (keywords.value.length) {
        stopKeywordPoll()
      } else {
        keywordPollAttempts += 1
        scheduleKeywordRetry(id)
      }
    })
    .catch(() => {
      keywordPollAttempts += 1
      scheduleKeywordRetry(id)
    })
}

function scheduleKeywordRetry(id) {
  if (keywordPollTimer || keywordPollAttempts > KEYWORD_POLL_LIMIT) return
  if (!aiReadingEnabled.value || !article.value || Number(article.value.id) !== Number(id)) return
  keywordPollTimer = setTimeout(() => {
    keywordPollTimer = null
    loadKeywords(id)
  }, KEYWORD_POLL_INTERVAL)
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function updateAiViewport() {
  aiViewport.value = { width: window.innerWidth, height: window.innerHeight }
  if (aiFabPosition.value) {
    aiFabPosition.value = { x: clamp(aiFabPosition.value.x, 16, Math.max(16, window.innerWidth - 68)), y: clamp(aiFabPosition.value.y, 16, Math.max(16, window.innerHeight - 68)) }
  }
}

function positionAiFabAtArticleStart() {
  if (aiFabPosition.value || !detailDocRef.value) return
  const rect = detailDocRef.value.getBoundingClientRect()
  aiFabPosition.value = { x: clamp(rect.right - 68, 16, Math.max(16, window.innerWidth - 68)), y: clamp(rect.top + 16, 16, Math.max(16, window.innerHeight - 68)) }
}

function startAiFabDrag(event) {
  if (event.button !== 0 || !aiFabPosition.value) return
  aiFabDragging.value = true
  aiFabDragged.value = false
  aiFabDragState.value = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, originX: aiFabPosition.value.x, originY: aiFabPosition.value.y }
  event.currentTarget.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', moveAiFab)
  window.addEventListener('pointerup', stopAiFabDrag)
  window.addEventListener('pointercancel', stopAiFabDrag)
}

function moveAiFab(event) {
  const state = aiFabDragState.value
  if (!state || event.pointerId !== state.pointerId) return
  const dx = event.clientX - state.startX
  const dy = event.clientY - state.startY
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) aiFabDragged.value = true
  aiFabPosition.value = { x: clamp(state.originX + dx, 16, Math.max(16, aiViewport.value.width - 68)), y: clamp(state.originY + dy, 16, Math.max(16, aiViewport.value.height - 68)) }
}

function stopAiFabDrag() {
  if (!aiFabDragState.value) return
  aiFabDragState.value = null
  aiFabDragging.value = false
  window.removeEventListener('pointermove', moveAiFab)
  window.removeEventListener('pointerup', stopAiFabDrag)
  window.removeEventListener('pointercancel', stopAiFabDrag)
  window.setTimeout(() => { aiFabDragged.value = false }, 0)
}

function captureArticleSelection() {
  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0 || !contentRef.value || selection.isCollapsed) return
  const range = selection.getRangeAt(0)
  const root = range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE ? range.commonAncestorContainer : range.commonAncestorContainer.parentElement
  if (!root || !contentRef.value.contains(root)) return
  const text = selection.toString().replace(/\s+/g, ' ').trim().slice(0, 1200)
  if (!text || text === aiSelectionText.value) return
  aiSelectionText.value = text
  aiSummaryRequestId.value += 1
  aiSummary.value = ''
  aiSummaryError.value = ''
  aiSummaryLoading.value = false
}

function syncArticleSelection() {
  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed || !contentRef.value) {
    aiSelectionText.value = ''
    return
  }
  const range = selection.getRangeAt(0)
  const root = range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE ? range.commonAncestorContainer : range.commonAncestorContainer.parentElement
  if (!root || !contentRef.value.contains(root)) aiSelectionText.value = ''
}

function toggleAiSummary() {
  if (aiFabDragged.value) return
  syncArticleSelection()
  aiSummaryOpen.value = !aiSummaryOpen.value
  if (aiSummaryOpen.value && !aiSummary.value && !aiSummaryLoading.value) generateAiResponse()
}

async function generateAiResponse() {
  if (!article.value || aiSummaryLoading.value) return
  const requestId = aiSummaryRequestId.value + 1
  aiSummaryRequestId.value = requestId
  aiSummaryLoading.value = true
  aiSummaryError.value = ''
  try {
    const isSelection = Boolean(aiSelectionText.value)
    const result = isSelection
      ? await articleApi.explainSelection(article.value.id, aiSelectionText.value)
      : await articleApi.aiSummary(article.value.id)
    const responseText = isSelection ? result?.data?.explanation : result?.data?.summary
    if (!responseText) throw new Error('AI 返回内容不完整，请重新尝试')
    if (requestId === aiSummaryRequestId.value) aiSummary.value = responseText
  } catch (error) {
    if (requestId === aiSummaryRequestId.value) {
      aiSummary.value = ''
      aiSummaryError.value = typeof error === 'string' && error.trim() ? error : 'AI 服务暂时不可用，请稍后重新尝试'
    }
  } finally {
    if (requestId === aiSummaryRequestId.value) aiSummaryLoading.value = false
  }
}

// 切换文章时重置评论区
function resetComments() {
  comments.value = []
  commentTotal.value = 0
  commentPage.value = 1
  newComment.value = ''
  replyTargetId.value = null
  replyContent.value = ''
}

// 加载评论列表（分页追加顶层评论，回复随顶层评论一起返回）
async function loadComments() {
  if (!article.value) return
  commentLoading.value = true
  try {
    const res = await commentApi.list({
      article_id: article.value.id,
      page: commentPage.value,
      page_size: commentPageSize,
    })
    comments.value = commentPage.value === 1 ? res.items : [...comments.value, ...res.items]
    commentTotal.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    commentLoading.value = false
  }
}

function loadMoreComments() {
  commentPage.value += 1
  loadComments()
}

// 发表顶层评论
async function submitComment() {
  const content = newComment.value.trim()
  if (!content) return
  submitting.value = true
  try {
    const res = await commentApi.create({ article_id: article.value.id, content })
    comments.value.unshift({ ...res.comment, replies: [] })
    commentTotal.value += 1
    newComment.value = ''
    ElMessage.success('评论成功')
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    submitting.value = false
  }
}

// 展开/收起某条评论的回复输入框
function toggleReply(c) {
  replyTargetId.value = replyTargetId.value === c.id ? null : c.id
  replyContent.value = ''
}

function cancelReply() {
  replyTargetId.value = null
  replyContent.value = ''
}

// 发表回复
async function submitReply(c) {
  const content = replyContent.value.trim()
  if (!content) return
  submitting.value = true
  try {
    const res = await commentApi.create({
      article_id: article.value.id,
      content,
      parent_id: c.id,
    })
    c.replies = [...(c.replies || []), res.comment]
    commentTotal.value += 1
    cancelReply()
    ElMessage.success('回复成功')
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    submitting.value = false
  }
}

// 删除顶层评论（其回复由后端级联删除）
async function removeComment(c) {
  try {
    await ElMessageBox.confirm('删除该评论会同时删除其全部回复，确定删除吗？', '删除评论', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  try {
    await commentApi.remove(c.id)
    comments.value = comments.value.filter((x) => x.id !== c.id)
    commentTotal.value = Math.max(0, commentTotal.value - 1 - (c.replies?.length || 0))
    if (replyTargetId.value === c.id) cancelReply()
    ElMessage.success('评论已删除')
  } catch (e) {
    ElMessage.error(String(e))
  }
}

// 删除单条回复
async function removeReply(c, r) {
  try {
    await ElMessageBox.confirm('确定删除这条回复吗？', '删除回复', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await commentApi.remove(r.id)
    c.replies = c.replies.filter((x) => x.id !== r.id)
    commentTotal.value = Math.max(0, commentTotal.value - 1)
    ElMessage.success('回复已删除')
  } catch (e) {
    ElMessage.error(String(e))
  }
}

// 上报本次观看时长：取实际停留秒数并封顶 600 秒（10 分钟），只上报一次
function reportWatchDuration() {
  if (durationReported.value || watchLimitReached.value || !article.value || !auth.isLoggedIn) return
  durationReported.value = true
  const seconds = Math.min(600, Math.max(1, Math.floor((Date.now() - watchStart.value) / 1000)))
  historyApi.reportDuration(article.value.id, seconds)
    .then((res) => {
      // 后端返回已达累计上限（30 分钟）时，本会话不再重复上报
      if (res?.reached_limit) watchLimitReached.value = true
    })
    .catch(() => {})
}

// ── 关键词与正文联动 ──

// 监听 keywords 变化，自动标记正文中的主关键词
watch(keywords, () => {
  nextTick(() => markKeywordsInArticle())
})

// 监听 article.content 变化（路由切换时），重新标记
watch(() => article.value?.content, () => {
  nextTick(() => markKeywordsInArticle())
})

// 在正文中标记主关键词（虚线下划线 + 点击弹出解释）
function markKeywordsInArticle() {
  const container = contentRef.value
  if (!container || !keywords.value.length) return

  // 先清除旧标记
  const oldMarks = container.querySelectorAll('.keyword-mark')
  oldMarks.forEach(el => {
    const parent = el.parentNode
    if (parent) {
      parent.replaceChild(document.createTextNode(el.textContent), el)
      parent.normalize()
    }
  })

  // 构建主关键词集合（按长度降序，避免短词覆盖长词）
  const kwSet = new Set()
  for (const g of keywords.value) {
    const mainKw = g.chain[g.chain.length - 1]
    if (mainKw) kwSet.add(mainKw)
  }
  const sortedKws = [...kwSet].sort((a, b) => b.length - a.length)

  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false)
  const textNodes = []
  while (walker.nextNode()) textNodes.push(walker.currentNode)

  for (const node of textNodes) {
    // 跳过已在 keyword-mark 内的文本节点
    if (node.parentElement?.closest('.keyword-mark, .keyword-group__label, .keyword-panel, .detail__head, .detail__crumb, .detail__cover, .detail__actions, .detail__login-tip')) continue

    let text = node.textContent
    let replaced = false
    const fragments = []
    let lastIdx = 0

    // 找文本中所有匹配的关键词位置
    const matches = []
    for (const kw of sortedKws) {
      let pos = 0
      while ((pos = text.indexOf(kw, pos)) !== -1) {
        matches.push({ start: pos, end: pos + kw.length, kw })
        pos += kw.length
      }
    }
    if (!matches.length) continue

    // 按位置排序，处理重叠（取范围大的）
    matches.sort((a, b) => a.start - b.start || b.end - a.end)
    const filtered = []
    let prevEnd = 0
    for (const m of matches) {
      if (m.start >= prevEnd) {
        filtered.push(m)
        prevEnd = m.end
      }
    }

    for (const m of filtered) {
      if (m.start > lastIdx) {
        fragments.push(document.createTextNode(text.slice(lastIdx, m.start)))
      }
      const span = document.createElement('span')
      span.className = 'keyword-mark'
      span.dataset.tag = m.kw
      span.textContent = m.kw
      span.title = `点击查看「${m.kw}」的解释`
      span.onclick = (e) => {
        e.stopPropagation()
        if (keywordPanelRef.value) {
          keywordPanelRef.value.openExplain(m.kw, true)
        }
      }
      fragments.push(span)
      lastIdx = m.end
      replaced = true
    }

    if (replaced) {
      if (lastIdx < text.length) {
        fragments.push(document.createTextNode(text.slice(lastIdx)))
      }
      const parent = node.parentNode
      if (parent) {
        for (const frag of fragments) {
          parent.insertBefore(frag, node)
        }
        parent.removeChild(node)
      }
    }
  }
}

// 滚动到关键词首次出现位置并闪烁 2 秒
function scrollToKeyword(keyword) {
  const container = contentRef.value
  if (!container) return

  // 找到正文中第一个匹配的关键词标记
  const mark = container.querySelector(`.keyword-mark[data-tag="${CSS.escape(keyword)}"]`)
  if (!mark) {
    ElMessage.info(`正文中未找到「${keyword}」`)
    return
  }

  // 清除之前的闪烁
  const prevFlashes = container.querySelectorAll('.keyword-mark--flash')
  prevFlashes.forEach(el => el.classList.remove('keyword-mark--flash'))

  // 滚动到目标位置
  mark.scrollIntoView({ behavior: 'smooth', block: 'center' })

  // 闪烁 2 秒
  mark.classList.add('keyword-mark--flash')
  setTimeout(() => mark.classList.remove('keyword-mark--flash'), 2000)
}

async function toggleLike() {
  try {
    const res = liked.value ? await interactionApi.unlike(article.value.id) : await interactionApi.like(article.value.id)
    liked.value = res.liked
    article.value.like_count = res.like_count ?? article.value.like_count
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function toggleFavorite() {
  try {
    const res = favorited.value
      ? await interactionApi.unfavorite(article.value.id)
      : await interactionApi.favorite(article.value.id)
    favorited.value = res.favorited
    article.value.favorite_count = res.favorite_count ?? article.value.favorite_count
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function toggleDislike() {
  try {
    const res = disliked.value
      ? await interactionApi.undislike(article.value.id)
      : await interactionApi.dislike(article.value.id)
    disliked.value = res.disliked
    if (res.disliked) {
      ElMessage.info('已标记不感兴趣，后续推荐将减少此类内容')
    } else {
      ElMessage.success('已取消不感兴趣')
    }
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function share() {
  try {
    // 登录用户按账号去重，未登录用户按设备指纹去重，是否首次转发由后端判定
    const res = await interactionApi.share(
      article.value.id,
      auth.isLoggedIn ? undefined : getFingerprint(),
    )
    article.value.share_count = res.share_count ?? article.value.share_count
    // 复制链接到剪贴板（失败时降级提示）
    try {
      await navigator.clipboard.writeText(window.location.href)
      ElMessage.success(res.shared === false ? '已转发过，链接仍可复制' : '转发成功，链接已复制')
    } catch {
      ElMessage.success(res.shared === false ? '已转发过，仅统计一次' : '转发成功')
    }
  } catch (e) {
    ElMessage.error(String(e))
  }
}

// 设备指纹：存 localStorage，稳定且不采集隐私；未登录用户以此识别同一浏览器
function getFingerprint() {
  let fp = localStorage.getItem('wgf_device_fp')
  if (!fp) {
    fp = window.crypto?.randomUUID?.() || `fp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    localStorage.setItem('wgf_device_fp', fp)
  }
  return fp
}
</script>

<style scoped>
/* Hallmark · genre: editorial · macrostructure: Long Document · design-system: design.md · designed-as-app */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 */
.detail {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--space-6);
  padding-top: var(--space-5);
  align-items: start;
}

.detail__doc {
  min-width: 0;
  background: var(--color-paper);
  padding: var(--space-6);
}

.detail__crumb {
  display: flex;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  margin-bottom: var(--space-5);
}

.detail__crumb a {
  /* 扩展触控热区，视觉位置不变 */
  padding: 10px 12px;
  margin: -10px -12px;
  color: var(--color-ink-3);
  transition: color var(--dur-base) var(--ease-out);
}

.detail__crumb a:hover {
  color: var(--color-accent);
}

.detail__head {
  border-bottom: var(--rule) solid var(--color-rule);
  margin-bottom: var(--space-5);
}

.detail__title {
  font-family: var(--font-heading);
  font-size: var(--text-display);
  line-height: var(--leading-tight);
  letter-spacing: var(--tracking-tight);
  color: var(--color-ink);
  margin-bottom: var(--space-4);
}

.detail__lead {
  color: var(--color-ink-2);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
  border-left: 3px solid var(--color-accent-2);
  padding-left: var(--space-4);
  margin: 0 0 var(--space-4);
}

.detail__meta {
  display: flex;
  gap: var(--space-4);
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  padding-bottom: var(--space-4);
}

.detail__author {
  color: var(--color-accent);
  font-weight: 500;
}

.detail__cover {
  margin: 0 0 var(--space-5);
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.detail__cover img {
  width: 100%;
  object-fit: cover;
}

.detail__content {
  max-width: var(--measure);
  color: var(--color-ink);
}

/* 长文首段首字下沉（仅当正文第一个元素是段落时生效） */
.detail__content > p:first-child::first-letter {
  font-family: var(--font-heading);
  font-size: 3.1em;
  line-height: 0.85;
  font-weight: 700;
  float: left;
  padding-right: 8px;
  color: var(--color-ink);
}

.ai-summary-fab {
  --ai-fab-bg: var(--color-accent);
  --ai-fab-border: var(--color-accent);
  --ai-fab-text: var(--color-paper);
  --ai-fab-hover-bg: var(--color-paper);
  --ai-fab-hover-text: var(--color-accent);
  position: fixed;
  z-index: 40;
  right: 28px;
  bottom: 28px;
  display: grid;
  width: 52px;
  height: 52px;
  place-items: center;
  border: var(--rule) solid var(--ai-fab-border);
  border-radius: 50%;
  background: var(--ai-fab-bg);
  color: var(--ai-fab-text);
  box-shadow: var(--shadow-float);
  cursor: grab;
  font-size: 24px;
  touch-action: none;
  user-select: none;
}

.ai-summary-fab:hover,
.ai-summary-fab:focus-visible {
  background: var(--ai-fab-hover-bg);
  color: var(--ai-fab-hover-text);
  transform: translateY(-2px);
}

.ai-summary-fab--dragging,
.ai-summary-fab--dragging:hover { cursor: grabbing; transform: none; }

.ai-summary-panel {
  position: fixed;
  z-index: 40;
  right: 28px;
  bottom: 92px;
  width: min(340px, calc(100vw - 32px));
  max-height: min(520px, calc(100vh - 120px));
  overflow-y: auto;
  border: var(--rule) solid var(--color-rule-strong);
  border-radius: var(--radius-sm);
  background: var(--color-paper);
  box-shadow: var(--shadow-float);
}

.ai-summary-panel__head,
.ai-summary-panel__title-group,
.ai-summary-panel__tools,
.ai-summary-panel__status { display: flex; align-items: center; }

.ai-summary-panel__head { justify-content: space-between; gap: var(--space-3); padding: var(--space-4); border-bottom: var(--rule) solid var(--color-rule); }
.ai-summary-panel__title-group { min-width: 0; gap: var(--space-2); }
.ai-summary-panel__tools { flex: 0 0 auto; gap: 2px; }
.ai-summary-panel__mark { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 50%; background: var(--color-primary-soft); color: var(--color-accent); }
.ai-summary-panel__title-group h2 { margin: 0; color: var(--color-ink); font-family: inherit; font-size: var(--text-base); }
.ai-summary-panel__close { display: grid; width: 32px; height: 32px; place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--color-ink-3); font-size: 18px; }
.ai-summary-panel__close:hover, .ai-summary-panel__close:focus-visible { background: var(--color-primary-soft); color: var(--color-accent); }
.ai-summary-panel__close:disabled { cursor: wait; opacity: .5; }
.ai-summary-panel__content, .ai-summary-panel__status { margin: 0; padding: var(--space-4); color: var(--color-ink-2); font-size: var(--text-sm); line-height: var(--leading-relaxed); }
.ai-summary-panel__status { gap: var(--space-2); color: var(--color-ink-3); }
.ai-summary-panel__status--error { display: block; }
.ai-summary-panel__status--error p { margin: 0 0 var(--space-3); }
.ai-summary-panel__selection { margin: var(--space-4) var(--space-4) 0; padding: var(--space-2) var(--space-3); border-left: 3px solid var(--color-accent); background: var(--color-primary-soft); color: var(--color-ink-2); font-size: var(--text-xs); line-height: var(--leading-relaxed); }
.ai-summary-panel__selection + .ai-summary-panel__content { padding-top: var(--space-3); }
.ai-summary-panel__retry { min-height: 32px; padding: 5px 10px; border: 1px solid var(--color-accent); border-radius: var(--radius-sm); background: var(--color-paper); color: var(--color-accent); font-size: var(--text-xs); font-weight: 600; }
.ai-summary-panel__retry:hover, .ai-summary-panel__retry:focus-visible { background: var(--color-primary-soft); }

/* 悬浮层使用 body 上同步的主题类：Teleport 到 body 后仍可随门户换肤。 */
:global(body.theme-cyber) .ai-summary-fab {
  --ai-fab-bg: var(--color-primary);
  --ai-fab-border: var(--color-primary);
  --ai-fab-text: #06111e;
  --ai-fab-hover-bg: var(--color-paper);
  --ai-fab-hover-text: var(--color-primary);
  box-shadow: 0 0 0 1px rgba(0, 229, 255, .3), 0 0 24px rgba(0, 229, 255, .46);
}

:global(body.theme-cyber) .ai-summary-panel {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px rgba(0, 229, 255, .2), 0 0 28px rgba(0, 229, 255, .18);
}

:global(body.theme-cyber) .ai-summary-panel__head { border-bottom-color: rgba(0, 229, 255, .35); }
:global(body.theme-cyber) .ai-summary-panel__mark { background: rgba(0, 229, 255, .14); color: var(--color-primary); }
:global(body.theme-cyber) .ai-summary-panel__selection { border-left-color: var(--color-primary); background: rgba(0, 229, 255, .1); }
:global(body.theme-cyber) .ai-summary-panel__retry { border-color: var(--color-primary); color: var(--color-primary); }

:global(body.theme-comic) .ai-summary-fab {
  --ai-fab-bg: var(--color-secondary);
  --ai-fab-border: var(--color-ink);
  --ai-fab-text: var(--color-ink);
  --ai-fab-hover-bg: var(--color-accent);
  --ai-fab-hover-text: #fff;
  border-width: 3px;
  border-radius: 8px;
  box-shadow: 4px 4px 0 var(--color-ink);
}

:global(body.theme-comic) .ai-summary-panel { border-width: 3px; border-color: var(--color-ink); border-radius: 10px; box-shadow: 7px 7px 0 var(--color-ink); }
:global(body.theme-comic) .ai-summary-panel__head { background: var(--color-secondary); border-bottom-width: 3px; border-bottom-color: var(--color-ink); }
:global(body.theme-comic) .ai-summary-panel__mark { background: var(--color-accent); color: #fff; border: 2px solid var(--color-ink); }
:global(body.theme-comic) .ai-summary-panel__selection { border-left-color: var(--color-accent); background: var(--color-accent-soft); }
:global(body.theme-comic) .ai-summary-panel__retry { border: 2px solid var(--color-ink); border-radius: 4px; color: var(--color-ink); box-shadow: 2px 2px 0 var(--color-ink); }

.detail__actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: var(--rule) solid var(--color-rule);
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: var(--rule) solid var(--color-rule-strong);
  background: var(--color-paper);
  color: var(--color-ink-2);
  border-radius: 999px;
  padding: 8px 18px;
  font-size: var(--text-sm);
  min-height: 40px;
  transition: border-color var(--dur-base) var(--ease-out),
    color var(--dur-base) var(--ease-out),
    background var(--dur-base) var(--ease-out);
}

.action-btn:hover:not(:disabled) {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.action-btn--active {
  background: var(--color-primary-soft);
  border-color: var(--color-accent);
  color: var(--color-accent);
  font-weight: 600;
}

.action-btn:disabled {
  opacity: 0.55;
}

.detail__login-tip {
  margin: var(--space-3) 0 0;
  font-size: var(--text-xs);
  color: var(--color-ink-3);
}

/* ---------- 评论区 ---------- */
.comments {
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 2px solid var(--color-ink);
}

.comments__title {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 var(--space-4);
}

.comments__composer {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}

.comments__composer-main {
  flex: 1;
  min-width: 0;
}

.comments__composer-foot {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-2);
}

.comments__login-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-4);
  border: var(--rule) dashed var(--color-rule-strong);
  border-radius: var(--radius-sm);
  color: var(--color-ink-3);
  font-size: var(--text-sm);
  margin-bottom: var(--space-5);
}

.comments__login-tip a {
  color: var(--color-accent);
  font-weight: 600;
}

.comments__list-wrap {
  min-height: 40px;
}

.comments__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.comments__list > li + li {
  border-top: var(--rule) solid var(--color-rule);
}

.comment {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4) 0;
}

.comment__body {
  flex: 1;
  min-width: 0;
}

.comment__meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.comment__name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-ink);
}

.comment__time {
  font-size: var(--text-xs);
  color: var(--color-ink-3);
}

.comment__del {
  margin-left: auto;
  border: none;
  background: none;
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  cursor: pointer;
  padding: 4px 8px;
  transition: color var(--dur-base) var(--ease-out);
}

.comment__del:hover {
  color: var(--color-danger, #c0392b);
  text-decoration: underline;
}

.comment__content {
  margin: 0 0 var(--space-2);
  color: var(--color-ink-2);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  white-space: pre-wrap;
  word-break: break-word;
}

.comment__reply-btn {
  border: none;
  background: none;
  color: var(--color-accent);
  font-size: var(--text-xs);
  cursor: pointer;
  padding: 2px 0;
}

.comment__reply-composer {
  margin: var(--space-3) 0 var(--space-2);
  padding: var(--space-3);
  background: var(--color-primary-soft);
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-sm);
}

.comment__reply-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.comment__replies {
  list-style: none;
  margin: var(--space-3) 0 0;
  padding: var(--space-3);
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
}

.comment__reply {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) 0;
}

.comment__reply + .comment__reply {
  border-top: var(--rule) solid var(--color-rule);
}

.comment__reply-main {
  flex: 1;
  min-width: 0;
}

.comment__reply-main .comment__del {
  margin-left: auto;
}

.comments__empty {
  padding: var(--space-5) 0;
  text-align: center;
  color: var(--color-ink-3);
  font-size: var(--text-sm);
}

.comments__more {
  display: flex;
  justify-content: center;
  padding-top: var(--space-3);
}

.related {
  align-self: start;
  position: sticky;
  top: 96px;
  background: var(--color-paper);
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-sm);
  padding: var(--space-5);
}

.related__title {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-ink);
  padding-bottom: var(--space-3);
  border-bottom: 2px solid var(--color-ink);
  margin: 0 0 var(--space-2);
}

.related__subtitle {
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  margin: 0 0 var(--space-3);
}

.related__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.related__list li + li {
  border-top: var(--rule) solid var(--color-rule);
}

.related__item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  color: var(--color-ink);
}

.related__item:hover .related__name {
  color: var(--color-accent);
}

.related__thumb {
  flex: 0 0 76px;
  width: 76px;
  height: 52px;
  border-radius: var(--radius-sm);
  object-fit: cover;
  background: var(--color-primary-soft);
}

.related__thumb--placeholder {
  display: grid;
  place-items: center;
  font-family: var(--font-heading);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-accent);
}

.related__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.related__name {
  font-size: var(--text-sm);
  line-height: var(--leading-snug);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color var(--dur-base) var(--ease-out);
}

.related__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
}

.related__cat {
  color: var(--color-accent);
  background: var(--color-primary-soft);
  padding: 1px 8px;
  border-radius: 2px;
  font-weight: 500;
}

.related__meta time {
  flex-shrink: 0;
}

@media (max-width: 1024px) {
  .detail {
    grid-template-columns: 1fr;
  }

  .related {
    position: static;
  }
}

@media (max-width: 768px) {
  .detail__doc {
    padding: var(--space-4);
  }

  .detail__title {
    font-size: clamp(1.7rem, 8vw, 2.3rem);
  }

  .detail__actions {
    flex-wrap: wrap;
  }

  .action-btn {
    flex: 1;
    justify-content: center;
    min-height: var(--size-touch);
  }

  .ai-summary-fab { right: 16px; bottom: 20px; }
  .ai-summary-panel { right: 16px; bottom: 84px; max-height: min(480px, calc(100vh - 108px)); }
}
</style>

<!-- 非 scoped 样式：关键词标记（动态插入的 DOM 元素不能使用 scoped 样式） -->
<style>
/* 正文中的关键词标记 — 仅虚线下划线，不改变颜色 */
.keyword-mark {
  cursor: pointer;
  border-bottom: 2px dashed var(--color-primary);
  transition: border-color 0.15s ease;
  padding-bottom: 1px;
}

.keyword-mark:hover {
  border-bottom-style: solid;
  border-bottom-width: 2.5px;
}

/* 闪烁动画 */
.keyword-mark--flash {
  animation: kw-flash 2s ease-in-out;
  border-radius: 4px;
}

@keyframes kw-flash {
  0%   { background: transparent; box-shadow: none; }
  15%  { background: rgba(255, 193, 7, 0.35); box-shadow: 0 0 12px rgba(255, 193, 7, 0.3); }
  30%  { background: transparent; box-shadow: none; }
  45%  { background: rgba(255, 193, 7, 0.35); box-shadow: 0 0 12px rgba(255, 193, 7, 0.3); }
  60%  { background: transparent; box-shadow: none; }
  75%  { background: rgba(255, 193, 7, 0.2); box-shadow: 0 0 8px rgba(255, 193, 7, 0.15); }
  100% { background: transparent; box-shadow: none; }
}
</style>
