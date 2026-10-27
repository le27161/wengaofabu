<template>
  <div class="stats-page">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><TrendCharts /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">数据统计</h1>
        <p class="admin-head__sub">行为趋势、栏目数据、热门文稿与埋点明细</p>
      </div>
    </div>

    <!-- 概览卡片 -->
    <div class="stat-cards">
      <div v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-card__label">{{ card.label }}</span>
        <strong class="stat-card__value">{{ card.value }}</strong>
      </div>
    </div>

    <!-- 趋势折线图 -->
    <section class="panel">
      <div class="panel__head">
        <h2>行为趋势</h2>
        <div class="panel__controls">
          <el-select v-model="trendType" style="width: 110px" @change="loadTrends">
            <el-option label="观看" value="view" />
            <el-option label="点赞" value="like" />
            <el-option label="收藏" value="favorite" />
            <el-option label="转发" value="share" />
          </el-select>
          <el-select v-model="trendDays" style="width: 110px" @change="loadTrends">
            <el-option label="7 天" :value="7" />
            <el-option label="30 天" :value="30" />
            <el-option label="90 天" :value="90" />
          </el-select>
        </div>
      </div>
      <div ref="trendRef" class="chart"></div>
    </section>

    <div class="stats-grid">
      <!-- 栏目数据 -->
      <section class="panel">
        <div class="panel__head"><h2>栏目数据（近30天浏览）</h2></div>
        <div ref="categoryRef" class="chart"></div>
      </section>

      <!-- 用户活跃 -->
      <section class="panel">
        <div class="panel__head"><h2>用户活跃与新增（7天）</h2></div>
        <div ref="activityRef" class="chart"></div>
      </section>
    </div>

    <!-- Top 文稿 -->
    <section class="panel">
      <div class="panel__head">
        <h2>热门文稿 TOP10</h2>
        <el-select v-model="topSort" style="width: 130px" @change="loadTop">
          <el-option label="按浏览" value="view_count" />
          <el-option label="按点赞" value="like_count" />
          <el-option label="按收藏" value="favorite_count" />
          <el-option label="按转发" value="share_count" />
        </el-select>
      </div>
      <el-table :data="topArticles" size="small">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="author_name" label="作者" width="110" />
        <el-table-column prop="view_count" label="浏览" width="90" />
        <el-table-column prop="like_count" label="点赞" width="80" />
        <el-table-column prop="favorite_count" label="收藏" width="80" />
        <el-table-column prop="share_count" label="转发" width="80" />
      </el-table>
    </section>

    <!-- 埋点明细 -->
    <section class="panel">
      <div class="panel__head">
        <h2>埋点明细</h2>
        <div class="panel__controls">
          <el-select v-model="eventFilter" placeholder="全部类型" clearable style="width: 110px" @change="reloadEvents">
            <el-option label="观看" value="view" />
            <el-option label="点赞" value="like" />
            <el-option label="收藏" value="favorite" />
            <el-option label="转发" value="share" />
          </el-select>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 250px"
            @change="reloadEvents"
          />
        </div>
      </div>
      <el-table :data="events" size="small" v-loading="eventsLoading">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column label="事件" width="90">
          <template #default="{ row }">
            <span class="mini-tag" :class="eventBadge[row.event_type] || 'mini-tag--empty'">
              {{ eventLabel[row.event_type] || row.event_type }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="user_id" label="用户ID" width="90" />
        <el-table-column prop="article_id" label="文稿ID" width="90" />
        <el-table-column prop="ip" label="IP" width="130" />
        <el-table-column prop="referer" label="来源" min-width="160" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="160" />
      </el-table>
      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next"
          :total="eventTotal"
          :page-size="eventPageSize"
          :current-page="eventPage"
          @current-change="changeEventPage"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
// 按需引入 ECharts，显著减小统计页打包体积
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { TrendCharts } from '@element-plus/icons-vue'
import { statsApi } from '../../api'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const overview = ref({})
const trendType = ref('view')
const trendDays = ref(30)
const topSort = ref('view_count')
const topArticles = ref([])
const events = ref([])
const eventTotal = ref(0)
const eventPage = ref(1)
const eventPageSize = 10
const eventFilter = ref('')
const dateRange = ref([])
const eventsLoading = ref(false)

const eventLabel = { view: '观看', like: '点赞', favorite: '收藏', share: '转发' }
const eventBadge = { view: 'mini-tag--blue', like: 'mini-tag--green', favorite: 'mini-tag--violet', share: 'mini-tag--orange' }

const cards = computed(() => [
  { label: '注册用户', value: overview.value.total_users ?? '-' },
  { label: '文稿总数', value: overview.value.total_articles ?? '-' },
  { label: '累计浏览', value: overview.value.total_views ?? '-' },
  { label: '累计点赞', value: overview.value.total_likes ?? '-' },
  { label: '累计收藏', value: overview.value.total_favorites ?? '-' },
  { label: '累计转发', value: overview.value.total_shares ?? '-' },
])

const trendRef = ref()
const categoryRef = ref()
const activityRef = ref()
let trendChart, categoryChart, activityChart

function initCharts() {
  trendChart = echarts.init(trendRef.value)
  categoryChart = echarts.init(categoryRef.value)
  activityChart = echarts.init(activityRef.value)
  window.addEventListener('resize', resizeCharts)
}

function resizeCharts() {
  trendChart?.resize()
  categoryChart?.resize()
  activityChart?.resize()
}

function renderLine(el, labels, seriesList, colors, legend) {
  el.setOption({
    tooltip: { trigger: 'axis' },
    legend: legend ? { data: legend } : undefined,
    grid: { left: 40, right: 16, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: labels, boundaryGap: false },
    yAxis: { type: 'value', minInterval: 1 },
    series: seriesList.map((s, i) => ({
      name: s.name,
      type: 'line',
      smooth: true,
      data: s.data,
      itemStyle: { color: colors[i] },
      areaStyle: i === 0 ? { opacity: 0.08 } : undefined,
    })),
  })
}

async function loadOverview() {
  overview.value = await statsApi.overview()
}

async function loadTrends() {
  const res = await statsApi.trends({ days: trendDays.value, event_type: trendType.value })
  renderLine(
    trendChart,
    res.items.map((i) => i.date.slice(5)),
    [{ name: eventLabel[trendType.value], data: res.items.map((i) => i.count) }],
    ['#2563EB'],
  )
}

async function loadCategories() {
  const res = await statsApi.categories({ days: 30 })
  categoryChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['浏览量', '文稿数'] },
    grid: { left: 40, right: 16, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: res.items.map((i) => i.category_name) },
    yAxis: [{ type: 'value', minInterval: 1 }],
    series: [
      { name: '浏览量', type: 'bar', data: res.items.map((i) => i.views), itemStyle: { color: '#2563EB' } },
      { name: '文稿数', type: 'bar', data: res.items.map((i) => i.article_count), itemStyle: { color: '#F97316' } },
    ],
  })
}

async function loadActivity() {
  const res = await statsApi.userActivity({ days: 7 })
  renderLine(
    activityChart,
    res.items.map((i) => i.date.slice(5)),
    [
      { name: '活跃用户', data: res.items.map((i) => i.active_users) },
      { name: '新增用户', data: res.items.map((i) => i.new_users) },
    ],
    ['#2563EB', '#F97316'],
    ['活跃用户', '新增用户'],
  )
}

async function loadTop() {
  const res = await statsApi.topArticles({ sort: topSort.value, limit: 10 })
  topArticles.value = res.items
}

async function loadEvents() {
  eventsLoading.value = true
  try {
    const params = { page: eventPage.value, page_size: eventPageSize }
    if (eventFilter.value) params.event_type = eventFilter.value
    if (dateRange.value?.length === 2) {
      params.start = dateRange.value[0]
      params.end = dateRange.value[1]
    }
    const res = await statsApi.events(params)
    events.value = res.items
    eventTotal.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    eventsLoading.value = false
  }
}

function reloadEvents() {
  eventPage.value = 1
  loadEvents()
}

function changeEventPage(p) {
  eventPage.value = p
  loadEvents()
}

onMounted(async () => {
  initCharts()
  try {
    await Promise.all([loadOverview(), loadTrends(), loadCategories(), loadActivity(), loadTop(), loadEvents()])
  } catch (e) {
    ElMessage.error(String(e))
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  trendChart?.dispose()
  categoryChart?.dispose()
  activityChart?.dispose()
})
</script>

<style scoped>
.stat-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-card__label {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.stat-card__value {
  font-size: 26px;
  font-family: var(--font-heading);
  color: var(--color-primary);
}

.panel {
  background: var(--color-surface);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-card);
  margin-bottom: 20px;
}

.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
  margin-bottom: 14px;
}

.panel__head h2 {
  font-size: 18px;
}

.panel__controls {
  display: flex;
  gap: 10px;
}

.chart {
  width: 100%;
  height: 320px;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.stats-grid .chart {
  height: 300px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

@media (max-width: 1200px) {
  .stat-cards {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
