<template>
  <aside v-if="keywords.length" class="kw-panel" aria-label="文章关键词">
    <!-- 几乎不可见的引语：像文章排版中的自然呼吸 -->
    <div class="kw-panel__bar">
      <span class="kw-panel__label">核心术语</span>
      <span class="kw-panel__dot" aria-hidden="true">·</span>
      <span class="kw-panel__count">{{ keywords.length }}</span>
    </div>

    <!-- 主关键词：三段式卡片 — #跳正文 / 关键词AI解释 / ▾知识链 -->
    <div class="kw-main-row">
      <div
        v-for="(group, idx) in keywords"
        :key="group.id"
        :ref="el => setMainTagRef(group.id, el)"
        class="kw-main-tag"
        :class="{
          'kw-main-tag--on': expanded[group.id],
        }"
        :style="{ '--card-i': idx }"
      >
        <!-- 第一段：# 跳转到正文 -->
        <button
          class="kw-main-tag__hash"
          @click.stop="locateKeyword(group.keyword)"
          title="跳转到正文中「{{ group.keyword }}」的位置"
          :aria-label="'定位「' + group.keyword + '」'"
        >
          <span class="kw-main-tag__hash-ring">#</span>
        </button>

        <!-- 第二段：关键词文字 → AI 解释 -->
        <button
          class="kw-main-tag__text"
          @click.stop="openExplain(group.keyword, false)"
          title="AI 解释「{{ group.keyword }}」"
        >
          <span>{{ group.keyword }}</span>
          <span class="kw-main-tag__text-ripple" aria-hidden="true"></span>
        </button>

        <!-- 第三段：下拉箭头 → 知识链 -->
        <button
          class="kw-main-tag__caret"
          @click.stop="toggleGroup(group.id)"
          :title="expanded[group.id] ? '收起知识链' : '展开知识链'"
          :aria-label="expanded[group.id] ? '收起' : '展开'"
        >
          <svg class="kw-main-tag__caret-svg" viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
            <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 知识链丝带：从卡片下方自然延展 -->
    <Transition name="chain-reveal">
      <div v-if="activeGroup != null" :key="'chain-area-' + activeGroup" class="kw-chains">
        <!-- 知识链头部：标题 + 步骤数 + 分类徽章 -->
        <div class="kw-chains__head">
          <div class="kw-chains__head-left">
            <svg class="kw-chains__head-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
            </svg>
            <span class="kw-chains__head-title">知识链</span>
            <span class="kw-chains__head-steps">{{ activeGroupData.chain.length }} 步递进</span>
          </div>
          <span v-if="activeGroupData.category" class="kw-chains__head-cat">{{ activeGroupData.category }}</span>
        </div>

        <div
          v-for="group in keywords"
          :key="'chain-' + group.id"
          v-show="expanded[group.id]"
          class="kw-chain"
        >
          <template v-for="(tag, ti) in group.chain" :key="ti">
            <span
              class="kw-tag"
              :class="{
                'kw-tag--deep': ti === 0,
                'kw-tag--mid': ti > 0 && ti < group.chain.length - 1,
                'kw-tag--shallow': ti === group.chain.length - 2,
                'kw-tag--end': ti === group.chain.length - 1,
                'kw-tag--live': activeTag === tag,
              }"
              :ref="el => setTagRef(tag, el)"
              @click.stop="openExplain(tag, false)"
              :title="'AI 解释「' + tag + '」'"
            >
              <span class="kw-tag__dot">{{ ti + 1 }}</span>
              <span>{{ tag }}</span>
            </span>
            <span
              v-if="ti < group.chain.length - 1"
              class="kw-tag__link"
              aria-hidden="true"
            >
              <svg viewBox="0 0 18 10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 5h12M12 1l4 4-4 4" />
              </svg>
            </span>
          </template>
        </div>

        <!-- 底部提示 -->
        <p class="kw-chains__hint">点击标签查看 AI 解释</p>
        <!-- 底部进度条 -->
        <div class="kw-chains__progress" aria-hidden="true"></div>
      </div>
    </Transition>
  </aside>

  <!-- 弹窗 -->
  <Teleport to="body">
    <Transition name="popup">
      <div v-if="popup.visible" class="explain-popup" :style="popupStyle" @click.stop>
        <div class="explain-popup__header">
          <div class="explain-popup__header-inner">
            <svg class="explain-popup__icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10" /><path d="M12 16v-4M12 8h.01" />
            </svg>
            <span class="explain-popup__tag">{{ popup.tag }}</span>
          </div>
          <button class="explain-popup__close" @click="closeExplain" aria-label="关闭">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div v-if="!popup.text && popup.streaming" class="explain-popup__loading">
          <div class="loading-pulse">
            <span class="loading-dot"></span><span class="loading-dot"></span><span class="loading-dot"></span>
          </div>
          <p class="loading-hint">AI 正在分析「{{ popup.tag }}」...</p>
          <span class="skeleton-line skeleton-line--1"></span>
          <span class="skeleton-line skeleton-line--2"></span>
          <span class="skeleton-line skeleton-line--3"></span>
          <span class="skeleton-line skeleton-line--4"></span>
        </div>
        <div v-else class="explain-popup__body">
          <p class="explain-popup__text" v-html="renderedText"></p>
          <span v-if="popup.streaming" class="explain-popup__cursor"></span>
        </div>

        <!-- 推荐文章（横向滑动切换） -->
        <div v-if="recItems.length && !recLoading" class="explain-popup__rec">
          <div class="rec-header">
            <svg class="rec-header__icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
            <span class="rec-header__label">相关推荐</span>
            <span class="rec-header__pager">{{ recIndex + 1 }} / {{ recItems.length }}</span>
          </div>

          <!-- 滑动容器 -->
          <div class="rec-slider" ref="recSlider" @touchstart="onTouchStart" @touchend="onTouchEnd">
            <div
              class="rec-slider__track"
              :style="{ transform: `translateX(-${recIndex * 100}%)` }"
            >
              <div
                v-for="(item, i) in recItems"
                :key="i"
                class="rec-slider__item"
              >
                <div class="rec-card">
                  <!-- 来源徽章 -->
                  <span class="rec-card__badge" :class="'rec-card__badge--' + (item.source || 'authority')">
                    {{ sourceLabel(item.source, item.url) }}
                  </span>
                  <!-- 站内文章：router-link -->
                  <router-link
                    v-if="item.source === 'local'"
                    :to="item.url"
                    class="rec-card__link"
                    @click.stop="closeExplain"
                  >
                    <span class="rec-card__title">{{ item.title }}</span>
                    <span v-if="item.summary" class="rec-card__summary">{{ item.summary }}</span>
                  </router-link>
                  <!-- 外部链接 -->
                  <a v-else :href="item.url" target="_blank" rel="noopener" class="rec-card__link rec-card__link--external" @click.stop>
                    <span class="rec-card__title">{{ item.title }}</span>
                    <span v-if="item.summary" class="rec-card__summary">{{ item.summary }}</span>
                  </a>
                  <!-- 进度点 -->
                  <div class="rec-card__dots">
                    <span
                      v-for="(_, di) in recItems"
                      :key="di"
                      class="rec-card__dot"
                      :class="{ 'rec-card__dot--active': di === i }"
                    ></span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 左右箭头 -->
          <button
            v-if="recIndex > 0"
            class="rec-arrow rec-arrow--left"
            @click.stop="prevRecommend"
            aria-label="上一篇推荐"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <button
            v-if="recIndex < recItems.length - 1"
            class="rec-arrow rec-arrow--right"
            :class="{ 'rec-arrow--hint': recIndex === 0 && recItems.length > 1 }"
            @click.stop="nextRecommend"
            aria-label="下一篇推荐"
            :title="'下一篇 (' + (recIndex + 2) + '/' + recItems.length + ')'"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>

        <div v-else-if="!recItems.length && !recLoading && recMessage" class="explain-popup__rec explain-popup__rec--empty">
          <span class="rec-empty-text">{{ recMessage }}</span>
        </div>

        <div v-if="recLoading" class="explain-popup__rec explain-popup__rec--loading">
          <span class="rec-loading-dot"></span>
          <span class="rec-loading-dot"></span>
          <span class="rec-loading-dot"></span>
        </div>

        <div class="explain-popup__footer"></div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { reactive, ref, computed, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { keywordApi, tagApi } from '../api'

const emit = defineEmits(['scroll-to-keyword'])
const props = defineProps({
  articleId: { type: [Number, String], default: null },
  keywords: { type: Array, default: () => [] },
})

const expanded = reactive({})
const mainTagRefs = reactive({})

function setMainTagRef(id, el) { if (el) mainTagRefs[id] = el }

/** 当前激活的组 ID（null 表示全部收起） */
const activeGroup = computed(() => {
  const id = Object.keys(expanded).find(k => expanded[k])
  return id != null ? Number(id) : null
})

/** 当前激活组的数据（category, chain 等） */
const activeGroupData = computed(() => {
  const gid = activeGroup.value
  if (gid == null) return { chain: [], category: '' }
  return props.keywords.find(k => k.id === gid) || { chain: [], category: '' }
})

/** 一次只展开一个，再次点击则收起 */
function toggleGroup(id) {
  const wasOpen = expanded[id]
  // 先全部收起
  Object.keys(expanded).forEach(k => { expanded[k] = false })
  // 如果之前没展开，则展开当前
  if (!wasOpen) expanded[id] = true
}

/** 点击 # 号 → 定位到正文中该关键词位置并闪烁 */
function locateKeyword(keyword) {
  emit('scroll-to-keyword', keyword)
}

const tagRefs = reactive({})
function setTagRef(tag, el) { if (el) tagRefs[tag] = el }

const popup = reactive({ visible: false, tag: '', text: '', streaming: false, top: 0, left: 0, fromInline: false, manuallyMoved: false, dragging: false })
const activeTag = computed(() => popup.visible ? popup.tag : null)
let abortController = null, scrollHandler = null, minLoadingTimer = null
let switchLock = false
let popupDragState = null

// ── 标签推荐文章 ──
const recItems = ref([])          // 当前标签的推荐文章列表
const recIndex = ref(0)           // 当前展示的索引
const recLoading = ref(false)     // 加载中
const recMessage = ref('')        // 无结果时的提示
const recSlider = ref(null)       // 滑动容器 ref

/** 来源标签映射（解析域名，显示中文名称） */
function sourceLabel(source, url) {
  if (source === 'local') return '站内'
  if (source === 'baike') return '百科'

  // 对 authority 来源，解析域名显示具体来源
  if (!url) return '来源'
  try {
    const host = new URL(url).hostname.toLowerCase()
    const domainMap = [
      // 优先匹配更长/更具体的域名
      ['cankaoxiaoxi.com', '参考消息'],
      ['chinanews.com', '中国新闻网'],
      ['people.com.cn', '人民网'],
      ['xinhuanet.com', '新华网'],
      ['huanqiu.com', '环球网'],
      ['china.com.cn', '中国网'],
      ['cctv.com', '央视网'],
      ['most.gov.cn', '科技部'],
      ['moe.gov.cn', '教育部'],
      ['stats.gov.cn', '统计局'],
      ['gov.cn', '政府网'],
      ['edu.cn', '教育网'],
      ['gmw.cn', '光明网'],
      ['youth.cn', '中国青年网'],
      ['ce.cn', '经济网'],
      ['81.cn', '解放军报'],
      ['cas.cn', '中科院'],
    ]
    for (const [key, label] of domainMap) {
      if (host.includes(key)) return label
    }
    // 未匹配到，取主域名
    const parts = host.split('.')
    if (parts.length >= 2) return parts[parts.length - 2]
    return host
  } catch {
    return '来源'
  }
}

/** 请求标签推荐文章 */
async function fetchRecommend(tag) {
  recLoading.value = true
  recItems.value = []
  recIndex.value = 0
  recMessage.value = ''
  try {
    const res = await tagApi.recommend(tag, props.articleId)
    recItems.value = res.items || []
    recMessage.value = res.message || ''
  } catch (e) {
    console.error('标签推荐请求失败：', e)
    recMessage.value = '推荐加载失败'
  } finally {
    recLoading.value = false
  }
}

/** 切换到上一篇推荐 */
function prevRecommend() {
  if (recIndex.value > 0) {
    recIndex.value--
  }
}

/** 切换到下一篇推荐 */
function nextRecommend() {
  if (recIndex.value < recItems.value.length - 1) {
    recIndex.value++
  }
}

/** 触摸滑动支持 */
let touchStartX = 0
function onTouchStart(e) {
  touchStartX = e.touches[0].clientX
}
function onTouchEnd(e) {
  const diff = touchStartX - e.changedTouches[0].clientX
  if (Math.abs(diff) > 50) {
    if (diff > 0) nextRecommend()
    else prevRecommend()
  }
}

const popupStyle = computed(() => ({ top: popup.top + 'px', left: popup.left + 'px' }))

function repositionPopup() {
  if (!popup.visible || popup.manuallyMoved) return
  const popupW = 420
  const gap = 12
  const estH = 360

  if (popup.fromInline) {
    const contentEl = document.querySelector('.detail__content')
    if (contentEl) {
      const rect = contentEl.getBoundingClientRect()
      if (rect.right + popupW + gap <= window.innerWidth) {
        popup.left = rect.right + gap
        popup.top = Math.max(8, Math.min(rect.top, window.innerHeight - estH - gap))
      } else {
        popup.left = Math.max(8, rect.left)
        popup.top = Math.max(8, rect.top - estH - gap)
        if (popup.top < 8) popup.top = 8
      }
    }
  } else {
    const el = tagRefs[popup.tag]
    if (el) {
      const rect = el.getBoundingClientRect()
      popup.left = Math.max(8, Math.min(rect.left, window.innerWidth - popupW - gap))
      popup.top = rect.bottom + gap
      if (popup.top + estH > window.innerHeight) {
        popup.top = Math.max(8, rect.top - estH - gap)
      }
    }
  }
  if (popup.top < 8) popup.top = 8
}

/** 只允许通过解释卡片头部拖动，避免影响正文选择和卡片内部滚动。 */
function startPopupDrag(event) {
  if (event.button !== 0 || event.target.closest('button')) return
  popup.dragging = true
  popupDragState = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    originLeft: popup.left,
    originTop: popup.top,
  }
  event.currentTarget.setPointerCapture?.(event.pointerId)
  window.addEventListener('pointermove', movePopup)
  window.addEventListener('pointerup', stopPopupDrag)
  window.addEventListener('pointercancel', stopPopupDrag)
}

function movePopup(event) {
  const state = popupDragState
  if (!state || event.pointerId !== state.pointerId) return
  const popupEl = document.querySelector('.explain-popup')
  const width = popupEl?.offsetWidth || 400
  const height = popupEl?.offsetHeight || 360
  popup.manuallyMoved = true
  popup.left = Math.max(8, Math.min(state.originLeft + event.clientX - state.startX, window.innerWidth - width - 8))
  popup.top = Math.max(8, Math.min(state.originTop + event.clientY - state.startY, window.innerHeight - height - 8))
}

function stopPopupDrag() {
  if (!popupDragState) return
  popupDragState = null
  popup.dragging = false
  window.removeEventListener('pointermove', movePopup)
  window.removeEventListener('pointerup', stopPopupDrag)
  window.removeEventListener('pointercancel', stopPopupDrag)
}

function handleClickOutside(e) {
  if (!popup.visible) return
  const el = document.querySelector('.explain-popup')
  if (!el || el.contains(e.target)) return
  const tagEl = tagRefs[popup.tag]
  if (tagEl && tagEl.contains(e.target)) return
  closeExplain()
}

function escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') }
function parseBold(t) { return escapeHtml(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }
const renderedText = computed(() => parseBold(popup.text))

function openExplain(tag, fromInline = false) {
  if (popup.visible && popup.tag === tag) { closeExplain(); return }
  if (switchLock) return
  switchLock = true
  setTimeout(() => { switchLock = false }, 300)

  if (abortController) { abortController.abort(); abortController = null }
  if (minLoadingTimer) { clearTimeout(minLoadingTimer); minLoadingTimer = null }
  if (scrollHandler) { window.removeEventListener('scroll', scrollHandler); scrollHandler = null }
  document.removeEventListener('click', handleClickOutside)

  popup.tag = tag
  popup.text = ''
  popup.streaming = true
  popup.visible = true
  popup.fromInline = fromInline
  popup.manuallyMoved = false

  // 同时拉取推荐文章
  fetchRecommend(tag)

  nextTick(() => repositionPopup())

  scrollHandler = () => repositionPopup()
  window.addEventListener('scroll', scrollHandler, { passive: true })
  setTimeout(() => document.addEventListener('click', handleClickOutside), 100)

  abortController = new AbortController()
  if (!props.articleId) { popup.text = '无法获取文章 ID'; popup.streaming = false; return }
  let minDone = false
  minLoadingTimer = setTimeout(() => { minDone = true }, 600)
  keywordApi.explainStream(props.articleId, tag).then(async (resp) => {
    if (!resp.ok) { popup.text = '请求失败'; popup.streaming = false; return }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = '', accumulated = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n'); buffer = lines.pop()
        for (const line of lines) {
          if (line.startsWith('data: [DONE]')) { popup.streaming = false; return }
          if (line.startsWith('data: [ERROR]')) { popup.text = line.slice(13).trim(); popup.streaming = false; return }
          if (line.startsWith('data: ')) { accumulated += line.slice(6); if (minDone) popup.text = accumulated }
        }
      }
      popup.text = accumulated
    } catch (e) { if (e.name !== 'AbortError') popup.text = accumulated || '读取中断' }
    finally { popup.streaming = false }
  }).catch(() => { popup.text = '网络请求失败'; popup.streaming = false })
}

function closeExplain() {
  stopPopupDrag()
  if (abortController) { abortController.abort(); abortController = null }
  if (scrollHandler) { window.removeEventListener('scroll', scrollHandler); scrollHandler = null }
  if (minLoadingTimer) { clearTimeout(minLoadingTimer); minLoadingTimer = null }
  document.removeEventListener('click', handleClickOutside)
  popup.visible = false; popup.text = ''; popup.streaming = false
  recItems.value = []; recIndex.value = 0
}

function handleKeydown(e) {
  if (!popup.visible) return
  if (e.key === 'Escape') { closeExplain(); return }
  // 左右箭头切换推荐文章
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    e.preventDefault()
    if (e.key === 'ArrowLeft') prevRecommend()
    else nextRecommend()
  }
}
onMounted(() => document.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => { closeExplain(); document.removeEventListener('keydown', handleKeydown) })
defineExpose({ openExplain })
</script>

<style scoped>
/* ═══════════════════════════════════════════════════════════════
   经典编辑主题 —「编辑室卡片集群」
   设计理念：无分隔线、无容器边框、无"节"感。
   标签像文章排版中的自然批注，每张卡片有独立色彩个性，
   知识链以丝带形式从卡片下方自然延展。
   ═══════════════════════════════════════════════════════════════ */

/* ── 面板：只有间距，没有"容器" ── */
.kw-panel {
  margin-top: 32px;
  padding: 0;
  position: relative;
}

/* ── 引语栏：几乎不可见，像文章中的轻声呼吸 ── */
.kw-panel__bar {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 14px;
}

.kw-panel__label {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-ink-3);
  letter-spacing: .1em;
  text-transform: uppercase;
}

.kw-panel__dot {
  color: var(--color-ink-3);
  opacity: .4;
  font-size: 10px;
}

.kw-panel__count {
  font-size: 10px;
  font-weight: 600;
  color: var(--color-ink-3);
  background: #f1f3f6;
  padding: 1px 7px;
  border-radius: 999px;
  line-height: 1.6;
}

/* ═══════════════════════════════════════════════════════════════
   主关键词：三段式卡片
   ┌────┬──────────────────┬────┐
   │ #  │  关键词文字      │ ▾  │
   │跳转│  AI 解释         │知识链│
   └────┴──────────────────┴────┘
   每段独立交互，hover 各有专属动效
   ═══════════════════════════════════════════════════════════════ */

/* ── 主关键词容器：不规整的有机排列，标签宽度自适应文字 ── */
.kw-main-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  position: relative;
  justify-content: flex-start;
  align-items: flex-start;
  padding: 4px 0;
}

/* ── 卡片：有机排列 — 微旋转 + 微偏移 + 色系轮换 ── */
.kw-main-tag {
  --_bg: #f5f7fa;
  --_accent: var(--color-primary);
  --_accent-soft: var(--color-primary-soft);
  --_text: var(--color-ink);
  --_rot: 0deg;
  --_y: 0px;

  display: inline-flex;
  align-items: center;
  gap: 0;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: var(--_bg);
  background: linear-gradient(135deg, var(--_bg) 0%, color-mix(in srgb, var(--_bg) 94%, #fff) 100%);
  font-family: inherit;
  position: relative;
  transform: rotate(var(--_rot)) translateY(var(--_y));
  transition: all .4s cubic-bezier(.34,1.56,.64,1);
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
  overflow: visible;
  flex: 0 0 auto;
  max-width: 100%;
  --_divider: rgba(0,0,0,.06);
}

/* 卡片内光：微妙的顶部高光，模拟纸张质感 */
.kw-main-tag::after {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255,255,255,.5) 0%, transparent 40%);
  pointer-events: none;
  opacity: 0;
  transition: opacity .3s;
}

.kw-main-tag:hover::after {
  opacity: 1;
}

/* 顶部彩色装饰条：每张卡片独一无二的个性标记 */
.kw-main-tag::before {
  content: '';
  position: absolute;
  top: 0; left: 8px; right: 8px;
  height: 3px;
  background: var(--_accent);
  border-radius: 0 0 3px 3px;
  opacity: .35;
  transition: all .35s cubic-bezier(.34,1.56,.64,1);
  transform-origin: center;
  z-index: 1;
}

.kw-main-tag:hover::before {
  opacity: .7;
  left: 4px; right: 4px;
  height: 4px;
}

/* 展开态：装饰条完全点亮 */
.kw-main-tag--on::before {
  opacity: .85 !important;
  left: 4px !important; right: 4px !important;
  height: 4px !important;
}

/* 每张卡片独立色彩（8 色轮） */
.kw-main-tag:nth-child(8n+1) { --_bg: #eef2ff; --_accent: #4f6ef7; --_accent-soft: rgba(79,110,247,.14); }
.kw-main-tag:nth-child(8n+2) { --_bg: #f0fdf4; --_accent: #16a34a; --_accent-soft: rgba(22,163,74,.12); }
.kw-main-tag:nth-child(8n+3) { --_bg: #fef9ef; --_accent: #d97706; --_accent-soft: rgba(217,119,6,.12); }
.kw-main-tag:nth-child(8n+4) { --_bg: #fdf2f8; --_accent: #db2777; --_accent-soft: rgba(219,39,119,.12); }
.kw-main-tag:nth-child(8n+5) { --_bg: #f0f9ff; --_accent: #0284c7; --_accent-soft: rgba(2,132,199,.12); }
.kw-main-tag:nth-child(8n+6) { --_bg: #faf5ff; --_accent: #9333ea; --_accent-soft: rgba(147,51,234,.12); }
.kw-main-tag:nth-child(8n+7) { --_bg: #fff7ed; --_accent: #ea580c; --_accent-soft: rgba(234,88,12,.12); }
.kw-main-tag:nth-child(8n+8) { --_bg: #ecfdf5; --_accent: #059669; --_accent-soft: rgba(5,150,105,.12); }

/* 有机旋转：每张卡片微微倾斜，像随手贴在纸上的标签 */
.kw-main-tag:nth-child(odd)  { --_rot: -0.6deg; }
.kw-main-tag:nth-child(even) { --_rot: 0.8deg; }
.kw-main-tag:nth-child(3n)   { --_rot: 0.4deg; }
.kw-main-tag:nth-child(5n+2) { --_rot: -0.9deg; }
.kw-main-tag:nth-child(7n+3) { --_rot: 0.7deg; }
.kw-main-tag:nth-child(4n+1) { --_rot: -0.4deg; }

/* 微垂直偏移：打破基线对齐 */
.kw-main-tag:nth-child(3n+1) { --_y: 1px; }
.kw-main-tag:nth-child(3n+2) { --_y: -2px; }
.kw-main-tag:nth-child(5n)   { --_y: 3px; }
.kw-main-tag:nth-child(7n+4) { --_y: -1px; }

/* 个性化圆角：每张卡片略有不同，像手工裁剪 */
.kw-main-tag:nth-child(4n)   { border-radius: 12px 14px 10px 14px; }
.kw-main-tag:nth-child(4n+1) { border-radius: 14px 10px 14px 12px; }
.kw-main-tag:nth-child(4n+2) { border-radius: 10px 14px 12px 14px; }
.kw-main-tag:nth-child(4n+3) { border-radius: 13px 12px 14px 10px; }

/* hover：回归齐整 + 浮起 + accent 色辉光，像被手指按住 */
.kw-main-tag:hover {
  transform: rotate(0deg) translateY(-4px) scale(1.03);
  box-shadow: 0 0 0 3px var(--_accent-soft), 0 10px 30px rgba(0,0,0,.1), 0 0 20px var(--_accent-soft);
  background: #fff;
  z-index: 2;
  transition: all .35s cubic-bezier(.34,1.56,.64,1);
}

/* 展开态：更明显站稳 */
.kw-main-tag--on {
  transform: rotate(0deg) translateY(0px) !important;
  box-shadow: 0 4px 16px rgba(0,0,0,.08), 0 0 0 2px var(--_accent-soft) !important;
  background: #fff !important;
  z-index: 2;
}

/* ═══════════════════════════════════════════════════════════════
   三段通用 button 基础
   ═══════════════════════════════════════════════════════════════ */

.kw-main-tag__hash,
.kw-main-tag__text,
.kw-main-tag__caret {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: none;
  cursor: pointer;
  font-family: inherit;
  outline: none;
  position: relative;
  transition: all .25s cubic-bezier(.4,0,.2,1);
}

/* ═══════════════════════════════════════════════════════════════
   第一段：# 跳转 — 左侧小方块，hover 时旋转/变色
   ═══════════════════════════════════════════════════════════════ */

.kw-main-tag__hash {
  padding: 10px 6px 10px 10px;
  border-right: 1px solid var(--_divider);
  flex-shrink: 0;
  border-radius: 12px 0 0 12px;
}

.kw-main-tag__hash-ring {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: #fff;
  color: var(--_accent);
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0;
  transition: all .3s cubic-bezier(.34,1.56,.64,1);
  box-shadow: 0 0 0 1px var(--_accent-soft);
  line-height: 1;
}

.kw-main-tag__hash:hover .kw-main-tag__hash-ring {
  background: var(--_accent);
  color: #fff;
  transform: scale(1.15) rotate(12deg);
  box-shadow: 0 0 0 5px var(--_accent-soft), 0 3px 8px rgba(0,0,0,.1);
}

.kw-main-tag__hash:active .kw-main-tag__hash-ring {
  transform: scale(.92);
  transition: transform .06s;
}

/* hash zone 自身 hover 给卡片一个微妙的左边框 */
.kw-main-tag__hash:hover {
  background: rgba(255,255,255,.4);
}

/* ═══════════════════════════════════════════════════════════════
   第二段：关键词文字 — 主体，hover 时下划线滑入 + 波纹
   ═══════════════════════════════════════════════════════════════ */

.kw-main-tag__text {
  padding: 10px 10px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--_text);
  letter-spacing: .02em;
  white-space: nowrap;
  flex: 1 1 auto;
  min-width: 0;
  border-radius: 0;
  gap: 0;
}

/* 文字下划线从左侧滑入 */
.kw-main-tag__text::after {
  content: '';
  position: absolute;
  bottom: 11px;
  left: 12px;
  right: 12px;
  height: 2px;
  background: var(--_accent);
  border-radius: 1px;
  transform: scaleX(0);
  transform-origin: left;
  transition: transform .3s cubic-bezier(.4,0,.2,1);
  opacity: .5;
}

.kw-main-tag__text:hover {
  color: var(--_accent);
  background: linear-gradient(180deg, var(--_accent-soft) 0%, transparent 100%);
}

.kw-main-tag__text:hover::after {
  transform: scaleX(1);
}

.kw-main-tag__text:active {
  transform: scale(.97);
  transition: transform .06s;
}

/* 波纹扩散元素 */
.kw-main-tag__text-ripple {
  display: none;
  position: absolute;
  inset: 0;
  border-radius: 0;
  pointer-events: none;
}

.kw-main-tag__text:active .kw-main-tag__text-ripple {
  display: block;
  animation: text-ripple .5s ease-out;
  background: radial-gradient(circle, var(--_accent-soft) 0%, transparent 70%);
}

@keyframes text-ripple {
  from { opacity: .6; transform: scale(.8); }
  to { opacity: 0; transform: scale(1.4); }
}

/* ═══════════════════════════════════════════════════════════════
   第三段：▾ 下拉 — 右侧，hover 弹跳，展开时旋转 180°
   ═══════════════════════════════════════════════════════════════ */

.kw-main-tag__caret {
  padding: 10px 12px 10px 6px;
  border-left: 1px solid var(--_divider);
  flex-shrink: 0;
  border-radius: 0 12px 12px 0;
  color: var(--color-ink-3);
  transition: all .3s cubic-bezier(.4,0,.2,1);
}

.kw-main-tag__caret-svg {
  transition: transform .35s cubic-bezier(.34,1.56,.64,1);
  opacity: .4;
}

.kw-main-tag__caret:hover {
  color: var(--_accent);
  background: rgba(255,255,255,.4);
}

.kw-main-tag__caret:hover .kw-main-tag__caret-svg {
  opacity: 1;
  transform: translateY(2px);
}

.kw-main-tag__caret:active .kw-main-tag__caret-svg {
  transform: translateY(4px);
  transition: transform .06s;
}

/* ═══════════════════════════════════════════════════════════════
   展开态：卡片整体高亮，各段响应
   ═══════════════════════════════════════════════════════════════ */

.kw-main-tag--on {
  background: #fff !important;
  box-shadow: 0 4px 20px rgba(0,0,0,.1), 0 0 0 2px var(--_accent) !important;
  transform: translateY(-1px);
}

.kw-main-tag--on .kw-main-tag__hash-ring {
  background: var(--_accent);
  color: #fff;
  animation: hash-pop .4s cubic-bezier(.34,1.56,.64,1);
}

@keyframes hash-pop {
  0% { box-shadow: 0 0 0 0 var(--_accent-soft); }
  60% { box-shadow: 0 0 0 10px var(--_accent-soft); }
  100% { box-shadow: 0 0 0 3px var(--_accent-soft); }
}

.kw-main-tag--on .kw-main-tag__text {
  color: var(--_accent);
  font-weight: 700;
}

.kw-main-tag--on .kw-main-tag__text::after {
  transform: scaleX(1);
  opacity: .3;
}

.kw-main-tag--on .kw-main-tag__caret {
  color: var(--_accent);
}

.kw-main-tag--on .kw-main-tag__caret-svg {
  opacity: 1;
  transform: rotate(180deg);
}

.kw-main-tag--on .kw-main-tag__caret:hover .kw-main-tag__caret-svg {
  transform: rotate(180deg) translateY(2px);
}

/* ═══════════════════════════════════════════════════════════════
   知识链丝带 — 经典编辑「稿纸手札」风格
   设计语言：笔记本横线纸 + 红色编辑标记 + 纸角折痕 + 撕边
   ═══════════════════════════════════════════════════════════════ */

.kw-chains {
  margin-top: 10px;
  padding: 0 0 18px;
  background: 
    /* 横线稿纸 */
    repeating-linear-gradient(
      0deg,
      transparent 0 27px,
      #eef1f6 27px 28px
    ),
    linear-gradient(135deg, #fdfbf7 0%, #f9f6f0 100%);
  border: 1px solid #e8e2d5;
  border-radius: 8px 8px 0 0;
  position: relative;
  overflow: hidden;
  box-shadow: 0 1px 6px rgba(0,0,0,.04), inset 0 1px 0 rgba(255,255,255,.9);
}

/* 纸角折痕：右上角小三角 */
.kw-chains::before {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 24px; height: 24px;
  background: linear-gradient(135deg, transparent 50%, #f0ebe0 50%, #e8e2d5 100%);
  border-radius: 0 8px 0 0;
  z-index: 2;
  opacity: .7;
}

/* 红色编辑标记线：左侧竖线，模拟审稿红线 */
.kw-chains::after {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, #e0556a 0%, #d94a5a 60%, #c0392b 100%);
  border-radius: 0;
  opacity: .35;
  transition: opacity .3s;
}

.kw-chains:hover::after {
  opacity: .55;
}

/* ── 知识链头部 ── */
.kw-chains__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px 12px 24px;
  border-bottom: 1px dashed #e0d8c8;
  margin-bottom: 8px;
  position: relative;
  z-index: 1;
}

.kw-chains__head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kw-chains__head-icon {
  color: #e0556a;
  opacity: .7;
  flex-shrink: 0;
}

.kw-chains__head-title {
  font-size: 13px;
  font-weight: 700;
  color: #4a4a4a;
  letter-spacing: .03em;
}

.kw-chains__head-steps {
  font-size: 11px;
  font-weight: 500;
  color: #8a8a8a;
  background: #f5f0e8;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid #e8e2d5;
}

.kw-chains__head-cat {
  font-size: 11px;
  font-weight: 600;
  color: #e0556a;
  background: rgba(224,85,106,.08);
  padding: 2px 10px;
  border-radius: 999px;
  letter-spacing: .04em;
  border: 1px solid rgba(224,85,106,.15);
}

/* ── 底部提示 ── */
.kw-chains__hint {
  margin: 10px 20px 0;
  font-size: 11px;
  color: #b0a898;
  text-align: right;
  opacity: .7;
  letter-spacing: .02em;
  position: relative;
  z-index: 1;
}

/* 底部撕边：锯齿状撕纸效果 */
.kw-chains__progress {
  position: absolute;
  bottom: 0;
  left: 0; right: 0;
  height: 8px;
  background: none;
  overflow: visible;
  z-index: 0;
}

.kw-chains__progress::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0; right: 0;
  height: 8px;
  background:
    linear-gradient(45deg, #f9f6f0 25%, transparent 25%) 0 0,
    linear-gradient(-45deg, #f9f6f0 25%, transparent 25%) 0 0,
    linear-gradient(45deg, transparent 75%, #f9f6f0 75%) 4px 0,
    linear-gradient(-45deg, transparent 75%, #f9f6f0 75%) 4px 0;
  background-size: 8px 8px;
  background-color: #e8e2d5;
  opacity: .5;
  mask-image: linear-gradient(to bottom, rgba(0,0,0,.3) 0%, rgba(0,0,0,1) 100%);
  -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,.3) 0%, rgba(0,0,0,1) 100%);
}

/* 链行：hover 时整行微亮 */
.kw-chain {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
  padding: 8px 20px 8px 24px;
  border-radius: 0 6px 6px 0;
  transition: background .25s, border-color .25s;
  animation: chain-fade .5s cubic-bezier(.34,1.56,.64,1) both;
  position: relative;
  border-left: 2px solid transparent;
}

.kw-chain:hover {
  background: rgba(255,255,255,.55);
  border-left-color: #e0556a;
}

.kw-chain:nth-child(2) { animation-delay: .05s; }
.kw-chain:nth-child(3) { animation-delay: .1s; }
.kw-chain:nth-child(4) { animation-delay: .15s; }
.kw-chain:nth-child(5) { animation-delay: .2s; }
.kw-chain:nth-child(n+6) { animation-delay: .25s; }

@keyframes chain-fade {
  from { opacity: 0; transform: translateY(-10px) scale(.95); }
  60% { transform: translateY(2px) scale(1.01); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── 分支标签：深度渐变药丸 ── */
.kw-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 13px;
  border-radius: 999px;
  font-size: 12.5px;
  background: #fff;
  color: var(--color-ink-2);
  border: 1px solid #e8ecf1;
  cursor: pointer;
  transition: all .3s cubic-bezier(.4,0,.2,1);
  user-select: none;
  white-space: nowrap;
  position: relative;
  font-weight: 500;
  flex-shrink: 0;
}

/* 深度渐变：越靠近主标签越突出 */
.kw-tag--deep {
  background: #f8f9fb;
  color: var(--color-ink-3);
  font-size: 12px;
  padding: 4px 11px;
  border-color: #eef1f6;
}

.kw-tag--mid {
  background: #fff;
  font-size: 12.5px;
}

.kw-tag--shallow {
  background: #fff;
  font-size: 13px;
  font-weight: 550;
  border-color: #dde3ed;
  box-shadow: 0 1px 3px rgba(0,0,0,.03);
}

.kw-tag:hover {
  color: var(--color-primary);
  border-color: var(--color-primary-soft);
  background: #fff;
  box-shadow: 0 4px 16px rgba(0,0,0,.07), 0 0 0 3px var(--color-primary-soft);
  transform: translateY(-2px);
  z-index: 1;
}

.kw-tag--shallow:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,.08), 0 0 0 4px var(--color-primary-soft);
  transform: translateY(-3px);
}

.kw-tag:active {
  transform: scale(.93);
  transition: transform .06s;
}

.kw-tag__dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #f1f3f6;
  color: var(--color-ink-3);
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
  transition: all .3s cubic-bezier(.34,1.56,.64,1);
}

.kw-tag--deep .kw-tag__dot {
  width: 16px;
  height: 16px;
  font-size: 9px;
  background: #eef1f6;
}

.kw-tag--shallow .kw-tag__dot {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.kw-tag:hover .kw-tag__dot {
  background: var(--color-primary);
  color: #fff;
  transform: scale(1.2);
  box-shadow: 0 2px 8px var(--color-primary-soft);
}

/* 链末尾：主关键词终点 */
.kw-tag--end {
  background: var(--color-primary);
  color: #fff;
  font-weight: 650;
  border-color: transparent;
  padding: 5px 15px;
  box-shadow: 0 2px 8px var(--color-primary-soft);
}

.kw-tag--end:hover {
  background: var(--color-primary-dark);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 6px 22px rgba(0,0,0,.15), 0 0 0 4px var(--color-primary-soft);
  transform: translateY(-2px);
}

.kw-tag--end .kw-tag__dot {
  background: rgba(255,255,255,.25);
  color: #fff;
}

.kw-tag--end:hover .kw-tag__dot {
  background: rgba(255,255,255,.45);
  transform: scale(1.15);
  box-shadow: 0 0 8px rgba(255,255,255,.3);
}

/* 激活态 */
.kw-tag--live {
  border-color: var(--color-primary) !important;
  box-shadow: 0 0 0 3px var(--color-primary-soft) !important;
  background: #fff !important;
  color: var(--color-primary) !important;
  animation: live-pulse 1.5s ease-in-out infinite;
}

@keyframes live-pulse {
  0%, 100% { box-shadow: 0 0 0 3px var(--color-primary-soft); }
  50% { box-shadow: 0 0 0 6px var(--color-primary-soft); }
}

.kw-tag--end.kw-tag--live {
  box-shadow: 0 0 0 4px var(--color-primary-soft), 0 4px 16px rgba(0,0,0,.12) !important;
  animation: live-pulse-end 1.5s ease-in-out infinite;
}

@keyframes live-pulse-end {
  0%, 100% { box-shadow: 0 0 0 4px var(--color-primary-soft), 0 4px 16px rgba(0,0,0,.12); }
  50% { box-shadow: 0 0 0 7px var(--color-primary-soft), 0 4px 24px rgba(0,0,0,.18); }
}

/* 标签间连接流动箭头 */
.kw-tag__link {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  margin: 0 1px;
  color: #dde3ed;
  transition: all .3s;
  width: 18px;
  height: 10px;
}

.kw-tag__link svg {
  width: 18px;
  height: 10px;
}

.kw-chain:hover .kw-tag__link {
  color: var(--color-primary);
  opacity: .5;
  transform: translateX(2px);
}

/* ── 链区过渡：丝带展开 ── */
.chain-reveal-enter-active {
  transition: all .4s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
}
.chain-reveal-leave-active {
  transition: all .2s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
}
.chain-reveal-enter-from {
  opacity: 0;
  transform: translateY(-10px);
  max-height: 0;
}
.chain-reveal-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  max-height: 0;
}

/* ── 弹窗 ── */
.explain-popup {
  position: fixed; z-index: 9999; width: 400px;
  max-width: calc(100vw - 24px); max-height: calc(100vh - 16px);
  display: flex; flex-direction: column;
  background: #fff; border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0,0,0,.12), 0 0 0 1px rgba(0,0,0,.05);
  overflow: hidden;
}

.explain-popup__header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; background: #f8faff;
  border-bottom: 1px solid #eef1f6;
}

.explain-popup__header-inner { display: flex; align-items: center; gap: 8px; }
.explain-popup__icon { color: var(--color-primary); flex-shrink: 0; }
.explain-popup__tag { font-size: 14px; font-weight: 700; color: var(--color-primary-dark); letter-spacing: .02em; }

.explain-popup__close {
  width: 32px; height: 32px; border: none; background: transparent;
  color: var(--color-ink-3); cursor: pointer; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  transition: all .2s;
}
.explain-popup__close:hover { background: rgba(0,0,0,.05); color: var(--color-ink); }

.explain-popup__loading {
  padding: 24px 18px 20px; max-height: 360px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 12px;
}

.loading-pulse { display: flex; align-items: center; justify-content: center; gap: 6px; padding-bottom: 2px; }
.loading-dot {
  display: block; width: 8px; height: 8px; border-radius: 50%;
  background: var(--color-primary); opacity: .35;
  animation: dot-pulse 1.4s ease-in-out infinite;
}
.loading-dot:nth-child(2) { animation-delay: .2s; }
.loading-dot:nth-child(3) { animation-delay: .4s; }

@keyframes dot-pulse {
  0%, 80%, 100% { opacity: .2; transform: scale(.8); }
  40% { opacity: .9; transform: scale(1.2); }
}

.loading-hint { margin: 0; text-align: center; font-size: 12px; color: var(--color-ink-3); padding-bottom: 2px; font-weight: 500; }

.skeleton-line {
  display: block; height: 12px; border-radius: 6px;
  background: linear-gradient(90deg, var(--color-rule) 25%, var(--color-primary-soft) 50%, var(--color-rule) 75%);
  background-size: 200% 100%; animation: shimmer 1.5s ease-in-out infinite;
}
.skeleton-line--1 { width: 75%; } .skeleton-line--2 { width: 100%; }
.skeleton-line--3 { width: 90%; } .skeleton-line--4 { width: 60%; }

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.explain-popup__body {
  padding: 20px 18px; min-height: 80px; max-height: 360px; overflow-y: auto;
  font-size: 14px; line-height: 1.85; color: var(--color-ink);
}
.explain-popup__text { margin: 0; white-space: pre-wrap; word-break: break-word; }
.explain-popup__text :deep(strong) { font-weight: 700; color: var(--color-primary-dark); }

.explain-popup__cursor {
  display: inline-block; width: 2px; height: 1em;
  background: var(--color-primary); margin-left: 2px;
  vertical-align: text-bottom; border-radius: 1px;
  animation: blink .7s steps(1) infinite;
}
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

.explain-popup__footer {
  height: 3px; width: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-secondary), var(--color-primary));
}

.popup-enter-active { transition: opacity .2s cubic-bezier(.4,0,.2,1), transform .2s cubic-bezier(.4,0,.2,1); }
.popup-leave-active { transition: opacity .12s cubic-bezier(.4,0,.2,1), transform .12s cubic-bezier(.4,0,.2,1); }
.popup-enter-from { opacity: 0; transform: translateY(-8px) scale(.95); }
.popup-leave-to { opacity: 0; transform: translateY(-4px) scale(.97); }

/* ── 标签推荐文章 ── */
.explain-popup__rec {
  padding: 12px 18px 14px;
  border-top: 1px solid #eef1f6;
  background: #fafbfc;
}

.explain-popup__rec--empty {
  padding: 10px 18px;
  text-align: center;
}

.rec-empty-text {
  font-size: 12px;
  color: var(--color-ink-3);
}

.explain-popup__rec--loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 14px 18px;
}

.rec-loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  opacity: .35;
  animation: rec-dot-pulse 1.2s ease-in-out infinite;
}
.rec-loading-dot:nth-child(2) { animation-delay: .2s; }
.rec-loading-dot:nth-child(3) { animation-delay: .4s; }

@keyframes rec-dot-pulse {
  0%, 80%, 100% { opacity: .2; transform: scale(.7); }
  40% { opacity: .8; transform: scale(1.1); }
}

.rec-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.rec-header__icon {
  color: var(--color-primary);
  flex-shrink: 0;
  opacity: .6;
}

.rec-header__label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-ink-3);
  letter-spacing: .04em;
  text-transform: uppercase;
  flex: 1;
}

.rec-header__pager {
  font-size: 11px;
  color: var(--color-ink-4);
  font-variant-numeric: tabular-nums;
  background: #f0f2f5;
  padding: 2px 8px;
  border-radius: 999px;
}

/* ── 滑动容器 ── */
.rec-slider {
  position: relative;
  overflow: hidden;
  border-radius: 10px;
}

.rec-slider__track {
  display: flex;
  transition: transform .4s cubic-bezier(.25,.8,.25,1);
}

.rec-slider__item {
  flex: 0 0 100%;
  min-width: 0;
}

/* ── 推荐卡片 ── */
.rec-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #eef1f6;
  border-radius: 10px;
  transition: all .25s;
  cursor: default;
}

.rec-card:hover {
  border-color: #d0d7e2;
  box-shadow: 0 4px 20px rgba(0,0,0,.07);
}

/* 来源徽章 */
.rec-card__badge {
  align-self: flex-start;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  letter-spacing: .03em;
  transition: all .2s;
}

.rec-card__badge--local {
  background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
  color: #2e7d32;
}

.rec-card__badge--authority {
  background: linear-gradient(135deg, #e3f2fd, #bbdefb);
  color: #1565c0;
}

.rec-card__badge--baike {
  background: linear-gradient(135deg, #fff3e0, #ffe0b2);
  color: #e65100;
}

/* 链接 */
.rec-card__link {
  text-decoration: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rec-card__link--external {
  cursor: pointer;
}

.rec-card__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color .2s;
}

.rec-card__link:hover .rec-card__title {
  color: var(--color-primary);
}

.rec-card__summary {
  font-size: 11px;
  color: var(--color-ink-3);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 进度点 */
.rec-card__dots {
  display: flex;
  justify-content: center;
  gap: 5px;
  margin-top: 4px;
}

.rec-card__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #d0d7e2;
  transition: all .3s;
}

.rec-card__dot--active {
  background: var(--color-primary);
  width: 14px;
  border-radius: 999px;
}

/* ── 左右箭头 ── */
.rec-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid #e0e5ec;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-ink-2);
  transition: all .2s;
  z-index: 2;
  font-family: inherit;
  padding: 0;
}

.rec-arrow:hover {
  background: #fff;
  border-color: var(--color-primary);
  color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(0,0,0,.1);
  transform: translateY(-50%) scale(1.1);
}

.rec-arrow:active {
  transform: translateY(-50%) scale(.95);
}

.rec-arrow--left  { left: 4px; }
.rec-arrow--right { right: 4px; }

/* 首次加载时右侧箭头提示动画 */
.rec-arrow--hint {
  animation: arrow-bounce 1.5s ease-in-out 3;
}

@keyframes arrow-bounce {
  0%, 100% { transform: translateY(-50%) translateX(0); }
  50% { transform: translateY(-50%) translateX(4px); }
}

/* 推荐区域容器需要 relative（为箭头定位） */
.explain-popup__rec {
  position: relative;
}

/* ── 滑动提示动画 ── */
@keyframes swipe-hint {
  0%, 100% { transform: translateX(0); opacity: .6; }
  50% { transform: translateX(6px); opacity: 1; }
}

.rec-arrow--right::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid transparent;
  animation: swipe-hint-ripple 2s ease-in-out infinite;
  pointer-events: none;
}

@keyframes swipe-hint-ripple {
  0%, 100% { border-color: transparent; transform: scale(1); }
  50% { border-color: var(--color-primary); transform: scale(1.6); opacity: 0; }
}

/* ── 多卡片时有滑动提示 ── */
.rec-slider__item:first-child:not(:last-child) .rec-card::after {
  content: '← 滑动查看更多 →';
  position: absolute;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 9px;
  color: var(--color-ink-4);
  letter-spacing: .04em;
  pointer-events: none;
  opacity: 0;
  animation: fade-hint 3s ease-in-out 1s both;
}

@keyframes fade-hint {
  0% { opacity: 0; }
  20% { opacity: .7; }
  80% { opacity: .7; }
  100% { opacity: 0; }
}

/* ============================================================
 * 霓虹主题（.theme-cyber）：暗底 + 青/品红辉光 + 科技感
 * ============================================================ */
.theme-cyber .explain-popup__rec {
  border-top-color: rgba(0, 229, 255, .18);
  background: linear-gradient(180deg, #0b1020 0%, #0d1322 100%);
}

.theme-cyber .rec-header__label {
  color: #00e5ff;
  text-shadow: 0 0 8px rgba(0, 229, 255, .4);
}

.theme-cyber .rec-header__pager {
  background: rgba(0, 229, 255, .1);
  color: #00e5ff;
  border: 1px solid rgba(0, 229, 255, .2);
}

.theme-cyber .rec-header__icon {
  color: #00e5ff;
  opacity: .8;
}

.theme-cyber .rec-slider {
  border-radius: 6px;
}

.theme-cyber .rec-card {
  background: linear-gradient(135deg, #101528 0%, #0d1322 100%);
  border-color: rgba(0, 229, 255, .15);
  box-shadow: 0 0 0 1px rgba(0, 229, 255, .08), 0 0 20px rgba(0, 229, 255, .05);
}

.theme-cyber .rec-card:hover {
  border-color: rgba(0, 229, 255, .4);
  box-shadow: 0 0 0 1px rgba(0, 229, 255, .2), 0 0 30px rgba(0, 229, 255, .15);
}

.theme-cyber .rec-card__title {
  color: #e6f7ff;
}

.theme-cyber .rec-card__link:hover .rec-card__title {
  color: #00e5ff;
  text-shadow: 0 0 6px rgba(0, 229, 255, .3);
}

.theme-cyber .rec-card__summary {
  color: #64748b;
}

.theme-cyber .rec-card__badge--local {
  background: rgba(0, 229, 255, .12);
  color: #00e5ff;
  border: 1px solid rgba(0, 229, 255, .25);
}

.theme-cyber .rec-card__badge--authority {
  background: rgba(124, 77, 255, .12);
  color: #b388ff;
  border: 1px solid rgba(124, 77, 255, .25);
}

.theme-cyber .rec-card__badge--baike {
  background: rgba(255, 45, 120, .12);
  color: #ff6b8a;
  border: 1px solid rgba(255, 45, 120, .25);
}

.theme-cyber .rec-card__dot {
  background: rgba(0, 229, 255, .2);
}

.theme-cyber .rec-card__dot--active {
  background: #00e5ff;
  box-shadow: 0 0 6px rgba(0, 229, 255, .5);
}

.theme-cyber .rec-arrow {
  background: rgba(16, 21, 40, .92);
  border-color: rgba(0, 229, 255, .25);
  color: #00e5ff;
  backdrop-filter: blur(8px);
}

.theme-cyber .rec-arrow:hover {
  background: rgba(0, 229, 255, .12);
  border-color: #00e5ff;
  box-shadow: 0 0 16px rgba(0, 229, 255, .3);
  color: #00e5ff;
}

.theme-cyber .rec-empty-text {
  color: #64748b;
}

.theme-cyber .rec-loading-dot {
  background: #00e5ff;
  box-shadow: 0 0 6px rgba(0, 229, 255, .4);
}

/* ============================================================
 * 漫画主题（.theme-comic）：奶黄底 + 高饱和 + 粗黑描边 + 硬投影
 * ============================================================ */
.theme-comic .explain-popup__rec {
  border-top: 2px solid #1a1a2e;
  background: #fffdf5;
}

.theme-comic .rec-header__label {
  color: #1a1a2e;
  font-family: 'Bangers', 'Comic Neue', sans-serif;
  font-size: 13px;
  letter-spacing: .06em;
}

.theme-comic .rec-header__pager {
  background: #ffd400;
  color: #1a1a2e;
  border: 2px solid #1a1a2e;
  font-weight: 800;
  font-family: 'Comic Neue', sans-serif;
}

.theme-comic .rec-header__icon {
  color: #ff3b30;
  opacity: 1;
}

.theme-comic .rec-slider {
  border-radius: 0;
}

.theme-comic .rec-card {
  background: #ffffff;
  border: 2px solid #1a1a2e;
  border-radius: 0;
  box-shadow: 4px 4px 0 rgba(26, 26, 46, .85);
  transform: translate(-1px, -1px);
  transition: all .15s cubic-bezier(.34,1.56,.64,1);
}

.theme-comic .rec-card:hover {
  border-color: #ff3b30;
  box-shadow: 6px 6px 0 rgba(255, 59, 48, .45);
  transform: translate(-2px, -2px);
}

.theme-comic .rec-card__title {
  color: #1a1a2e;
  font-family: 'Comic Neue', 'Bangers', sans-serif;
  font-weight: 700;
}

.theme-comic .rec-card__link:hover .rec-card__title {
  color: #ff3b30;
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
}

.theme-comic .rec-card__summary {
  color: #4a4a68;
  font-family: 'Comic Neue', sans-serif;
}

.theme-comic .rec-card__badge {
  border: 2px solid #1a1a2e;
  border-radius: 0;
  font-family: 'Bangers', 'Comic Neue', sans-serif;
  font-size: 11px;
  text-transform: uppercase;
  transform: rotate(-1deg);
}

.theme-comic .rec-card__badge--local {
  background: #c8e6c9;
  color: #1b5e20;
}

.theme-comic .rec-card__badge--authority {
  background: #bbdefb;
  color: #0d47a1;
}

.theme-comic .rec-card__badge--baike {
  background: #ffe0b2;
  color: #bf360c;
}

.theme-comic .rec-card__dot {
  background: #1a1a2e;
  opacity: .25;
  border-radius: 0;
}

.theme-comic .rec-card__dot--active {
  background: #ff3b30;
  opacity: 1;
  width: 12px;
  height: 5px;
  border-radius: 0;
  transform: skewX(-15deg);
}

.theme-comic .rec-arrow {
  background: #ffffff;
  border: 2px solid #1a1a2e;
  border-radius: 0;
  color: #1a1a2e;
  box-shadow: 2px 2px 0 rgba(26, 26, 46, .5);
}

.theme-comic .rec-arrow:hover {
  background: #ffd400;
  border-color: #1a1a2e;
  color: #1a1a2e;
  box-shadow: 4px 4px 0 rgba(26, 26, 46, .7);
  transform: translateY(-50%) scale(1.1);
}

.theme-comic .rec-arrow:active {
  box-shadow: 0px 0px 0 rgba(26, 26, 46, .5);
  transform: translateY(-50%) scale(.95) translate(2px, 2px);
}

.theme-comic .rec-empty-text {
  color: #7a7a98;
  font-family: 'Comic Neue', sans-serif;
}

.theme-comic .rec-loading-dot {
  background: #ff3b30;
  border-radius: 0;
  animation: rec-dot-pulse-comic 1.2s ease-in-out infinite;
}

@keyframes rec-dot-pulse-comic {
  0%, 80%, 100% { opacity: .2; transform: scale(.7) rotate(0deg); }
  40% { opacity: 1; transform: scale(1.2) rotate(45deg); }
}
</style>
