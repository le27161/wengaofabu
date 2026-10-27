<template>
  <div class="container category-page">
    <!-- 栏目头 -->
    <header v-if="current" class="cat-head">
      <h1>{{ current.name }}</h1>
      <p v-if="current.description">{{ current.description }}</p>
    </header>
    <header v-else class="cat-head">
      <h1>全部文稿</h1>
      <p>全站已发布内容索引</p>
    </header>

    <!-- 排序切换：最新 / 最热 -->
    <div class="sort-bar" role="tablist" aria-label="排序方式">
      <button
        v-for="opt in sortOptions"
        :key="opt.value"
        role="tab"
        :aria-selected="sort === opt.value"
        :class="{ active: sort === opt.value }"
        @click="changeSort(opt.value)"
      >
        {{ opt.label }}
      </button>
      <span v-if="cityStore.active" class="sort-bar__city">同城 · {{ cityStore.label }}</span>
    </div>

    <div v-loading="loading" class="article-grid">
      <ArticleCard v-for="a in articles" :key="a.id" :article="a" />
    </div>
    <el-empty v-if="!loading && !articles.length" description="该分类暂无文稿" />

    <div class="pager">
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="changePage"
      />
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { articleApi, categoryApi } from '../../api'
import { useCityStore } from '../../stores/city'
import ArticleCard from '../../components/ArticleCard.vue'

const route = useRoute()
const router = useRouter()
const cityStore = useCityStore()
const categories = ref([])
const current = ref(null)
const articles = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const sort = ref('latest')
const loading = ref(false)
const sortOptions = [
  { label: '最新', value: 'latest' },
  { label: '最热', value: 'hot' },
]

const LIST_STATE_PREFIX = 'wg_category_list_state:'
const pendingScrollY = ref(0)

function listStateKey() {
  const slug = route.params.slug || 'all'
  return `${LIST_STATE_PREFIX}${slug}`
}

function saveListState() {
  try {
    sessionStorage.setItem(listStateKey(), JSON.stringify({
      page: page.value,
      sort: sort.value,
      city: cityStore.city || '',
      scrollY: window.scrollY,
    }))
  } catch {
    // 保存失败不影响正常浏览
  }
}

function restoreListState() {
  try {
    const raw = sessionStorage.getItem(listStateKey())
    if (!raw) return
    const saved = JSON.parse(raw)
    if (!saved || saved.city !== (cityStore.city || '')) return
    const savedPage = Number(saved.page)
    if (Number.isFinite(savedPage) && savedPage > 0) page.value = savedPage
    sort.value = saved.sort === 'hot' ? 'hot' : 'latest'
    pendingScrollY.value = Number(saved.scrollY) || 0
  } catch {
    sessionStorage.removeItem(listStateKey())
  }
}

async function load() {
  loading.value = true
  try {
    const slug = route.params.slug
    if (!categories.value.length) {
      const res = await categoryApi.list()
      categories.value = res.items
    }
    current.value = categories.value.find((c) => c.slug === slug) || null
    const params = { sort: sort.value, page: page.value, page_size: pageSize }
    if (current.value) params.category_id = current.value.id
    // 同城搜索：选择城市后栏目列表仅展示该城市内容
    if (cityStore.city) params.city = cityStore.city
    const res = await articleApi.list(params)
    articles.value = res.items
    total.value = res.total
    if (pendingScrollY.value) {
      const y = pendingScrollY.value
      pendingScrollY.value = 0
      await nextTick()
      window.scrollTo(0, y)
    }
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

function changeSort(v) {
  sort.value = v
  page.value = 1
  load()
}

function changePage(p) {
  page.value = p
  load()
}

watch(() => route.params.slug, () => {
  // 切换栏目时重置到第一页，避免把上一个栏目的页码带过来
  page.value = 1
  pendingScrollY.value = 0
  load()
})
// 城市变化（导航条选择/清除）→ 当前栏目页同步刷新
watch(() => cityStore.city, () => {
  // 切换城市时也回到第一页，避免页码超出当前城市数据范围
  page.value = 1
  load()
})
onBeforeRouteLeave(saveListState)
onMounted(() => {
  restoreListState()
  load()
})
</script>

<style scoped>
/* Hallmark · genre: editorial · macrostructure: Catalogue · design-system: design.md · designed-as-app */
/* Hallmark · pre-emit critique: P4 H4 E4 S4 R4 V4 */
.category-page {
  padding-top: var(--space-5);
}

.cat-head {
  border-bottom: 2px solid var(--color-ink);
  padding-bottom: var(--space-3);
  margin-bottom: var(--space-4);
}

.cat-head h1 {
  font-family: var(--font-heading);
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--color-ink);
}

.cat-head p {
  color: var(--color-ink-2);
  font-size: var(--text-sm);
  margin: var(--space-2) 0 0;
}

.sort-bar {
  display: flex;
  gap: var(--space-5);
  margin-bottom: var(--space-4);
}

.sort-bar button {
  position: relative;
  border: none;
  background: none;
  padding: 6px 2px;
  color: var(--color-ink-3);
  font-size: var(--text-sm);
  font-weight: 500;
  transition: color var(--dur-base) var(--ease-out);
}

.sort-bar button:hover {
  color: var(--color-accent);
}

.sort-bar button.active {
  color: var(--color-ink);
  font-weight: 700;
}

.sort-bar button.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  background: var(--color-accent);
}

.sort-bar__city {
  margin-left: auto;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-accent);
  border: var(--rule) solid var(--color-accent);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  background: var(--color-primary-soft);
}

.article-grid {
  display: flex;
  flex-direction: column;
  min-height: 200px;
}

.pager {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}

/* 目录页分页按钮触控高度 */
.pager :deep(.el-pagination button),
.pager :deep(.el-pagination .el-pager li) {
  min-height: 32px;
}
</style>
