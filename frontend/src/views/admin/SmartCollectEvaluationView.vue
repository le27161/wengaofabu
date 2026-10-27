<template>
  <div class="evaluation-page">
    <div class="page-head">
      <div>
        <AdminBackLink :to="{ name: 'admin-smart-collect' }" label="返回智能采编" />
        <h1 class="page-title">相关性评估</h1>
        <p class="page-description">对照人工判断，观察Tavily搜索分数和E5语义分数的表现。</p>
      </div>
      <el-button :loading="loading" @click="loadEvaluation">刷新统计</el-button>
    </div>

    <el-alert
      title="当前统计仅用于模型效果观察，不作为自动过滤标准。"
      type="warning"
      show-icon
      :closable="false"
      class="boundary-alert"
    />
    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="boundary-alert"
    />

    <div v-loading="loading" class="evaluation-content">
      <section class="overview-grid" aria-label="人工标注概览">
        <el-card v-for="item in overviewItems" :key="item.label" shadow="never" class="overview-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </el-card>
      </section>

      <el-card shadow="never" class="section-card">
        <template #header><strong>三类人工判断的分数统计</strong></template>
        <el-table :data="statRows" empty-text="暂无已标注数据">
          <el-table-column prop="label" label="人工判断" min-width="120" />
          <el-table-column prop="count" label="样本数" width="90" />
          <el-table-column label="Tavily平均分" min-width="130">
            <template #default="{ row }">{{ formatScore(row.searchAverage) }}</template>
          </el-table-column>
          <el-table-column label="E5平均分" min-width="120">
            <template #default="{ row }">{{ formatScore(row.semanticAverage) }}</template>
          </el-table-column>
          <el-table-column label="Tavily最低 / 最高" min-width="170">
            <template #default="{ row }">{{ formatRange(row.searchMinimum, row.searchMaximum) }}</template>
          </el-table-column>
          <el-table-column label="E5最低 / 最高" min-width="170">
            <template #default="{ row }">{{ formatRange(row.semanticMinimum, row.semanticMaximum) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header><strong>同任务排序一致率</strong></template>
        <div class="agreement-grid">
          <div v-for="item in agreementItems" :key="item.key" class="agreement-item">
            <span>{{ item.label }}</span>
            <strong>{{ formatRate(item.data?.rate) }}</strong>
            <p>{{ item.data?.correct || 0 }} / {{ item.data?.total || 0 }} 个有效pair方向正确</p>
            <small v-if="item.data?.ties">另有 {{ item.data.ties }} 个同分pair未计入比率</small>
          </div>
        </div>
        <p class="plain-tip">
          排序一致率表示在同一次采编任务中，模型是否把人工认为更相关的新闻排在更前面。
        </p>
      </el-card>

      <section class="outlier-section">
        <h2>模型判断偏差较大的新闻</h2>
        <div class="outlier-grid">
          <el-card v-for="group in outlierGroups" :key="group.key" shadow="never" class="outlier-card">
            <template #header>
              <div class="outlier-card__head">
                <strong>{{ group.title }}</strong>
                <span>{{ group.items.length }} 条</span>
              </div>
            </template>
            <el-empty v-if="!group.items.length" description="暂无符合条件的样本" :image-size="70" />
            <div v-else class="outlier-list">
              <article v-for="item in group.items" :key="`${group.key}-${item.task_id}-${item.clue_id}`" class="outlier-item">
                <span class="task-query">任务 #{{ item.task_id }} · {{ item.query }}</span>
                <h3>{{ item.title }}</h3>
                <div class="outlier-meta">
                  <span>来源：{{ item.source || '未知' }}</span>
                  <span>Tavily：{{ formatScore(item.search_score) }}</span>
                  <span>E5：{{ formatScore(item.semantic_score) }}</span>
                  <span>人工：{{ formatLabel(item.relevance_label) }}</span>
                </div>
                <el-button link type="primary" @click="openTask(item.task_id)">查看原任务</el-button>
              </article>
            </div>
          </el-card>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { smartCollectApi } from '../../api'
import AdminBackLink from '../../components/AdminBackLink.vue'

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const summary = ref(null)
const outliers = ref({
  semantic_label_0_high: [],
  semantic_label_2_low: [],
  search_label_0_high: [],
  search_label_2_low: [],
})

const labelDefinitions = [
  { key: '2', label: '明显相关' },
  { key: '1', label: '一般相关' },
  { key: '0', label: '明显偏题' },
]

const overviewItems = computed(() => [
  { label: '人工标注总数', value: summary.value?.total_labeled || 0 },
  { label: '明显相关', value: summary.value?.label_counts?.['2'] || 0 },
  { label: '一般相关', value: summary.value?.label_counts?.['1'] || 0 },
  { label: '明显偏题', value: summary.value?.label_counts?.['0'] || 0 },
])

const statRows = computed(() => labelDefinitions.map((definition) => {
  const search = summary.value?.search_score_stats?.[definition.key] || {}
  const semantic = summary.value?.semantic_score_stats?.[definition.key] || {}
  return {
    label: definition.label,
    count: summary.value?.label_counts?.[definition.key] || 0,
    searchAverage: search.average,
    searchMinimum: search.minimum,
    searchMaximum: search.maximum,
    semanticAverage: semantic.average,
    semanticMinimum: semantic.minimum,
    semanticMaximum: semantic.maximum,
  }
}))

const agreementItems = computed(() => [
  { key: 'search_score', label: 'Tavily', data: summary.value?.ranking_agreement?.search_score },
  { key: 'semantic_score', label: 'E5', data: summary.value?.ranking_agreement?.semantic_score },
])

const outlierGroups = computed(() => [
  { key: 'semantic_label_0_high', title: '人工偏题但E5高分', items: outliers.value.semantic_label_0_high || [] },
  { key: 'semantic_label_2_low', title: '人工相关但E5低分', items: outliers.value.semantic_label_2_low || [] },
  { key: 'search_label_0_high', title: '人工偏题但Tavily高分', items: outliers.value.search_label_0_high || [] },
  { key: 'search_label_2_low', title: '人工相关但Tavily低分', items: outliers.value.search_label_2_low || [] },
])

function formatScore(value) {
  if (value === null || value === undefined || value === '') return '—'
  return Number.isFinite(Number(value)) ? Number(value).toFixed(3) : '—'
}

function formatRange(minimum, maximum) {
  if (minimum === null || minimum === undefined || maximum === null || maximum === undefined) {
    return '—'
  }
  return `${formatScore(minimum)} / ${formatScore(maximum)}`
}

function formatRate(rate) {
  return rate === null || rate === undefined ? '暂无可比较样本' : `${(rate * 100).toFixed(1)}%`
}

function formatLabel(label) {
  return { 0: '明显偏题', 1: '一般相关', 2: '明显相关' }[label] || '未标注'
}

function openTask(taskId) {
  router.push({ name: 'admin-smart-collect-task', params: { id: taskId } })
}

async function loadEvaluation() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [summaryResult, outlierResult] = await Promise.all([
      smartCollectApi.evaluationSummary(),
      smartCollectApi.evaluationOutliers({ limit: 5 }),
    ])
    summary.value = summaryResult
    outliers.value = outlierResult
  } catch (error) {
    errorMessage.value = String(error || '相关性评估加载失败')
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

onMounted(loadEvaluation)
</script>

<style scoped>
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.page-title { margin: 8px 0 0; font-size: 24px; }
.page-description { margin: 6px 0 0; color: var(--color-text-muted); font-size: 14px; }
.boundary-alert { margin-bottom: 16px; }
.evaluation-content { min-height: 240px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.overview-card :deep(.el-card__body) { display: flex; flex-direction: column; gap: 8px; }
.overview-card span { color: var(--color-text-muted); font-size: 14px; }
.overview-card strong { color: var(--color-text); font-size: 28px; }
.section-card { margin-bottom: 16px; }
.agreement-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.agreement-item { padding: 18px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); background: var(--color-bg); }
.agreement-item > span { color: var(--color-text-secondary); }
.agreement-item > strong { display: block; margin: 8px 0; color: var(--el-color-primary); font-size: 30px; }
.agreement-item p { margin: 0; color: var(--color-text-secondary); font-size: 14px; }
.agreement-item small { display: block; margin-top: 6px; color: var(--color-text-muted); }
.plain-tip { margin: 14px 0 0; color: var(--color-text-secondary); font-size: 14px; line-height: 1.7; }
.outlier-section > h2 { margin: 22px 0 12px; font-size: 18px; }
.outlier-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.outlier-card__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.outlier-card__head span { color: var(--color-text-muted); font-size: 13px; }
.outlier-list { display: grid; gap: 12px; }
.outlier-item { padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.outlier-item:last-child { padding-bottom: 0; border-bottom: 0; }
.task-query { color: var(--el-color-primary); font-size: 12px; }
.outlier-item h3 { margin: 6px 0; color: var(--color-text); font-size: 15px; line-height: 1.5; }
.outlier-meta { display: flex; flex-wrap: wrap; gap: 5px 12px; color: var(--color-text-muted); font-size: 12px; }
@media (max-width: 900px) {
  .page-head { align-items: flex-start; }
  .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .outlier-grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .page-head { flex-direction: column; }
  .agreement-grid, .overview-grid { grid-template-columns: 1fr; }
}

/* 与智能采编工作台统一的后台视觉覆盖（业务逻辑不变） */
.evaluation-page {
  display: grid;
  gap: var(--space-5);
}

.page-head {
  align-items: center;
  padding: var(--space-2) 0;
}

.page-title {
  color: var(--color-ink);
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 700;
}

.page-description {
  color: var(--color-ink-3);
  font-size: var(--text-sm);
}

.overview-grid {
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.overview-card,
.section-card,
.outlier-card {
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

.overview-card :deep(.el-card__body) {
  gap: var(--space-1);
}

.overview-card span {
  color: var(--color-ink-3);
  font-size: var(--text-xs);
  font-weight: 600;
}

.overview-card strong {
  color: var(--color-ink);
  font-size: var(--text-2xl);
  font-variant-numeric: tabular-nums;
}

.section-card {
  margin-bottom: var(--space-4);
}

.section-card :deep(.el-card__header),
.outlier-card :deep(.el-card__header) {
  border-bottom-color: var(--color-rule);
  color: var(--color-ink);
  font-weight: 700;
}

.agreement-item {
  padding: var(--space-4);
  background: var(--color-paper-2);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
}

.agreement-item > strong {
  color: var(--color-primary);
  font-size: var(--text-3xl);
}

.outlier-section > h2 {
  margin: var(--space-5) 0 var(--space-3);
  color: var(--color-ink);
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: 700;
}

.outlier-item {
  padding: var(--space-3);
  border-bottom-color: var(--color-rule);
}

.outlier-item h3 {
  color: var(--color-ink);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
}

.task-query {
  color: var(--color-primary);
  font-size: var(--text-xs);
  font-weight: 700;
}

/* 缩放安全：小屏/浏览器缩放时不允许横向溢出 */
.evaluation-page {
  width: 100%;
  min-width: 0;
  overflow-x: hidden;
  box-sizing: border-box;
}

.page-head {
  flex-wrap: wrap;
  min-width: 0;
}

.page-head > div {
  min-width: 0;
}

.page-title,
.page-description {
  overflow-wrap: anywhere;
}

.overview-grid {
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
}

.overview-card,
.section-card,
.outlier-card,
.outlier-item,
.agreement-item {
  min-width: 0;
}

.section-card :deep(.el-table) {
  width: 100%;
  min-width: 0;
  overflow-x: auto;
}

.outlier-meta {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
