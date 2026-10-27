<template>
  <div class="search-wrap">
    <form class="search-box" role="search" @submit.prevent="doSearch">
      <input
        v-model="keyword"
        type="search"
        name="keyword"
        placeholder="搜索文稿"
        aria-label="搜索文稿"
        @focus="openPanel"
      />
      <button type="submit" aria-label="搜索">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.35-4.35" stroke-linecap="round" />
        </svg>
      </button>
    </form>

    <!-- 搜索下拉面板：历史搜索（10条）+ 浅色分割线 + 个性化推荐 -->
    <transition name="panel">
      <div v-if="panelOpen" class="search-panel" v-loading="recommendLoading">
        <template v-if="history.length">
          <div class="search-panel__section">
            <div class="search-panel__head">
              <span class="search-panel__title">历史搜索</span>
              <button class="search-panel__clear" type="button" @click="clearHistory">清空</button>
            </div>
            <ul class="search-panel__tags">
              <li v-for="(h, index) in history" :key="h + '-' + index">
                <button class="search-panel__tag" type="button" @click="applyKeyword(h)">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="8" />
                    <path d="M12 8v4l2.5 2.5" stroke-linecap="round" />
                  </svg>
                  {{ h }}
                </button>
              </li>
            </ul>
          </div>
          <div class="search-panel__divider"></div>
        </template>

        <div class="search-panel__section">
          <div class="search-panel__head">
            <span class="search-panel__title">猜你喜欢</span>
            <span class="search-panel__reason">{{ recommendReason }}</span>
          </div>
          <ul v-if="recommends.length" class="search-panel__recs">
            <li v-for="art in recommends" :key="art.id">
              <router-link
                :to="{ name: 'article-detail', params: { id: art.id } }"
                @click="closePanel"
              >
                <span class="rec-title">{{ art.title }}</span>
                <span class="rec-meta">{{ art.view_count }} 阅读</span>
              </router-link>
            </li>
          </ul>
          <div v-else-if="!recommendLoading" class="search-panel__empty">暂无推荐内容</div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { articleApi } from '../../api'

const router = useRouter()

// ---- 搜索状态 ----
const keyword = ref('')
const panelOpen = ref(false)
const history = ref([]) // 历史搜索词（最新在前，最多10条）
const recommends = ref([]) // 推荐文稿
const recommendReason = ref('') // 推荐说明文案
const recommendLoading = ref(false)
const HISTORY_KEY = 'wg_search_history'

// 读取历史搜索（localStorage，最新在前，去重，最多10条）
function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    history.value = raw ? JSON.parse(raw) : []
    if (!Array.isArray(history.value)) history.value = []
  } catch {
    history.value = []
  }
}

// 记录一次搜索：去重后放最前，只保留10条
function saveKeyword(kw) {
  const text = String(kw || '').trim()
  if (!text) return
  const list = history.value.filter((x) => x !== text)
  list.unshift(text)
  history.value = list.slice(0, 10)
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
  } catch {
    // 存储失败（如隐私模式）不影响搜索
  }
}

function clearHistory() {
  history.value = []
  try {
    localStorage.removeItem(HISTORY_KEY)
  } catch {
    // ignore
  }
}

// 点击历史词：填入输入框并立即搜索
function applyKeyword(kw) {
  keyword.value = kw
  doSearch()
}

function openPanel() {
  panelOpen.value = true
  loadHistory()
  loadRecommends()
}

function closePanel() {
  panelOpen.value = false
}

// 点击面板外部任意位置关闭（检查是否在 search-wrap 内）
function onDocClick(e) {
  if (!e.target.closest('.search-wrap')) closePanel()
}

// 拉取个性化推荐（后端按用户偏好栏目返回热文；未登录为全站热文）
async function loadRecommends() {
  recommendLoading.value = true
  try {
    const res = await articleApi.recommend({ limit: 6 })
    recommends.value = res.items || []
    recommendReason.value = res.reason || ''
  } catch {
    recommends.value = []
    recommendReason.value = ''
  } finally {
    recommendLoading.value = false
  }
}

function doSearch() {
  if (!keyword.value.trim()) return
  saveKeyword(keyword.value)
  closePanel()
  router.push({ name: 'search', query: { q: keyword.value.trim() } })
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.search-wrap {
  position: relative;
  flex: 1;
  max-width: 420px;
  margin-left: auto;
}

.search-box {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 2px;
  border-bottom: var(--rule) solid var(--color-rule-strong);
  transition: border-color var(--dur-base) var(--ease-out);
}

.search-box:focus-within {
  border-color: var(--color-accent);
}

.search-box input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--color-ink);
}

.search-box button {
  border: none;
  background: none;
  color: var(--color-ink-2);
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-sm);
  transition: color var(--dur-base) var(--ease-out), background var(--dur-base) var(--ease-out);
}

.search-box button:hover {
  color: var(--color-accent);
  background: var(--color-primary-soft);
}

/* ---- 搜索下拉面板 ---- */
.search-panel {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: var(--color-paper);
  border: var(--rule) solid var(--color-rule);
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
  z-index: 200;
  padding: var(--space-3) var(--space-4);
  min-height: 60px;
}

.search-panel__section + .search-panel__section {
  margin-top: var(--space-1);
}

.search-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: 8px;
}

.search-panel__title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--color-ink-2);
}

.search-panel__reason {
  font-size: 12px;
  color: var(--color-ink-3);
}

.search-panel__clear {
  border: none;
  background: none;
  color: var(--color-ink-3);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}

.search-panel__clear:hover {
  color: var(--color-accent);
}

.search-panel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.search-panel__tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border: var(--rule) solid var(--color-rule);
  border-radius: 999px;
  background: var(--color-paper-2);
  font-size: 12px;
  color: var(--color-ink-2);
  cursor: pointer;
  transition: color var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out);
}

.search-panel__tag:hover {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

/* 浅色分割线：划分历史搜索与喜好推荐 */
.search-panel__divider {
  height: 1px;
  background: var(--color-rule);
  margin: 10px 0;
}

.search-panel__recs {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.search-panel__recs a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-ink);
  transition: background var(--dur-base) var(--ease-out), color var(--dur-base) var(--ease-out);
}

.search-panel__recs a:hover {
  background: var(--color-primary-soft);
  color: var(--color-accent);
}

.rec-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rec-meta {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-ink-3);
}

.search-panel__empty {
  padding: 10px 0;
  font-size: 12px;
  color: var(--color-ink-3);
  text-align: center;
}

/* 面板展开动画 */
.panel-enter-active,
.panel-leave-active {
  transition: opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out);
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 768px) {
  .search-wrap {
    order: 3;
    flex-basis: 100%;
    max-width: none;
    margin-left: 0;
  }

  .search-box button {
    width: var(--size-touch);
    height: var(--size-touch);
  }
}
</style>
