<template>
  <el-dialog
    v-model="visible"
    class="ai-assist-dialog"
    width="min(1160px, 95vw)"
    top="4vh"
    :close-on-click-modal="false"
    :show-close="false"
    append-to-body
    destroy-on-close
  >
    <!-- 自定义头部 -->
    <template #header>
      <div class="ai-head">
        <span class="ai-head__icon" aria-hidden="true">
          <el-icon><MagicStick /></el-icon>
        </span>
        <div class="ai-head__text">
          <h2 class="ai-head__title">AI 协作台</h2>
          <p class="ai-head__sub">窗口内的修改会实时同步到写稿页面；AI 调用记录自动留存在后台</p>
        </div>
      </div>
    </template>

    <div class="ai-body">
      <!-- 左栏：文稿编辑区（与写稿页双向绑定） -->
      <section class="ai-edit">
        <div class="ai-edit__head">
          <h3 class="ai-section-title">文稿内容</h3>
          <div class="ai-tabs" role="group" aria-label="正文显示模式">
            <button
              type="button"
              class="ai-tabs__btn"
              :class="{ 'is-active': editTab === 'edit' }"
              @click="editTab = 'edit'"
            >
              编辑
            </button>
            <button
              type="button"
              class="ai-tabs__btn"
              :class="{ 'is-active': editTab === 'preview' }"
              :disabled="!hasHighlight"
              @click="editTab = 'preview'"
            >
              高亮预览
            </button>
          </div>
        </div>

        <div class="ai-field">
          <label class="ai-label" for="ai-title">标题</label>
          <el-input
            id="ai-title"
            v-model="form.title"
            maxlength="200"
            show-word-limit
            placeholder="输入文稿标题"
          />
        </div>

        <div class="ai-field">
          <label class="ai-label" for="ai-summary">摘要</label>
          <el-input
            id="ai-summary"
            v-model="form.summary"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="输入文稿摘要"
          />
        </div>

        <div class="ai-field">
          <label class="ai-label" for="ai-categories">栏目（可多选）</label>
          <el-select
            id="ai-categories"
            v-model="form.category_ids"
            multiple
            placeholder="选择栏目"
            class="ai-category-select"
          >
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </div>

        <div class="ai-field ai-field--content">
          <div class="ai-field__row">
            <label class="ai-label" for="ai-content">正文</label>
            <span v-if="editTab === 'edit' && locateHint" class="ai-highlight-hint">{{ locateHint }}</span>
            <span v-else-if="editTab === 'preview' && highlightHint" class="ai-highlight-hint">{{ highlightHint }}</span>
          </div>
          <RichTextEditor
            v-if="editTab === 'edit'"
            v-model="form.content"
            :min-height="300"
            @text-change="onContentChange"
          />
          <div v-else class="ai-content-preview" v-html="previewHtml || escapedContent"></div>
        </div>
      </section>

      <!-- 右栏：AI 功能面板 -->
      <aside class="ai-tools">
        <div class="ai-tools__head">
          <h3 class="ai-section-title">AI 辅助功能</h3>
          <span class="ai-tools__note">占用资源，按需调用</span>
        </div>

        <!-- 1. AI 分类 -->
        <article class="ai-tool">
          <div class="ai-tool__bar">
            <span class="ai-tool__icon ai-tool__icon--violet" aria-hidden="true">
              <el-icon><Collection /></el-icon>
            </span>
            <div class="ai-tool__meta">
              <span class="ai-tool__name">AI 智能分类</span>
              <span class="ai-tool__desc">根据标题判断所属栏目并自动选中</span>
            </div>
            <el-button
              type="primary"
              size="small"
              :disabled="!canUse('classify')"
              :loading="loading.classify"
              @click="run('classify')"
            >
              调用
            </el-button>
          </div>
          <div v-if="classifyResult" class="ai-tool__result">
            <el-icon class="ai-result-icon ai-result-icon--ok"><CircleCheck /></el-icon>
            <span>识别栏目：<strong>{{ classifyResult }}</strong>（已自动选中）</span>
          </div>
          <!-- 分类纠正：AI 分类不准时手动纠正，沉淀训练数据集并立即选中正确栏目 -->
          <div v-if="classifyResult" class="ai-correction">
            <span class="ai-correction__label">分类不准？选择正确栏目：</span>
            <el-select
              v-model="correctionCategoryId"
              placeholder="选择正确栏目"
              size="small"
              class="ai-correction__select"
            >
              <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-button
              type="warning"
              size="small"
              :disabled="!correctionCategoryId"
              :loading="correcting"
              @click="submitCorrection"
            >
              纠正
            </el-button>
          </div>
        </article>

        <!-- 2. AI 生成摘要 -->
        <article class="ai-tool">
          <div class="ai-tool__bar">
            <span class="ai-tool__icon ai-tool__icon--blue" aria-hidden="true">
              <el-icon><Document /></el-icon>
            </span>
            <div class="ai-tool__meta">
              <span class="ai-tool__name">AI 生成摘要</span>
              <span class="ai-tool__desc">根据标题与正文生成一句话摘要</span>
            </div>
            <el-button
              type="primary"
              size="small"
              :disabled="!canUse('summary')"
              :loading="loading.summary"
              @click="run('summary')"
            >
              调用
            </el-button>
          </div>
          <div v-if="summaryResult" class="ai-tool__result">
            <el-icon class="ai-result-icon ai-result-icon--ok"><CircleCheck /></el-icon>
            <span>摘要已生成并回写：<strong>{{ summaryResult }}</strong></span>
          </div>
        </article>

        <!-- 3. AI 多维度审核 -->
        <article class="ai-tool">
          <div class="ai-tool__bar">
            <span class="ai-tool__icon ai-tool__icon--amber" aria-hidden="true">
              <el-icon><Warning /></el-icon>
            </span>
            <div class="ai-tool__meta">
              <span class="ai-tool__name">AI 多维度审核</span>
              <span class="ai-tool__desc">检查色情、暴力、文明用语、涉政风险</span>
            </div>
            <el-button
              type="primary"
              size="small"
              :disabled="!canUse('review')"
              :loading="loading.review"
              @click="run('review')"
            >
              调用
            </el-button>
          </div>
          <div v-if="hasReview" class="ai-tool__result ai-review">
            <div class="ai-review__overall">
              <span class="ai-review__badge" :class="riskClass(reviewItems.overall_risk)">
                {{ reviewItems.overall_risk || '未评估' }}
              </span>
              <span class="ai-review__overall-label">总体风险</span>
            </div>

            <div v-for="(item, index) in reviewItems.risk_list" :key="index" class="ai-review__item">
              <div class="ai-review__item-head">
                <span class="ai-review__dim" :class="riskLevelClass(item.risk_level)">{{ item.risk_dimension }}</span>
                <span class="ai-review__level">{{ item.risk_level }}</span>
              </div>
              <p v-if="item.source_text" class="ai-review__source"><b>原文证据：</b>{{ item.source_text }}</p>
              <p v-if="item.risk_desc" class="ai-review__desc">{{ item.risk_desc }}</p>
              <p v-if="item.suggestion" class="ai-review__suggestion"><b>处置建议：</b>{{ item.suggestion }}</p>
            </div>

            <p
              v-if="Array.isArray(reviewItems.risk_list) && reviewItems.risk_list.length === 0"
              class="ai-review__empty"
            >
              未发现明显风险项
            </p>

            <p v-if="reviewItems.summary" class="ai-review__summary">{{ reviewItems.summary }}</p>
          </div>
        </article>

        <!-- 4. AI 内容校验 -->
        <article class="ai-tool">
          <div class="ai-tool__bar">
            <span class="ai-tool__icon ai-tool__icon--red" aria-hidden="true">
              <el-icon><EditPen /></el-icon>
            </span>
            <div class="ai-tool__meta">
              <span class="ai-tool__name">AI 内容校验</span>
              <span class="ai-tool__desc">检测错别字、标点等错误，点击可定位高亮</span>
            </div>
            <el-button
              type="primary"
              size="small"
              :disabled="!canUse('check')"
              :loading="loading.check"
              @click="run('check')"
            >
              调用
            </el-button>
          </div>
          <!-- checkDone：调用已成功返回（含空结果）；未调用/失败时不展示 -->
          <div v-if="checkDone" class="ai-tool__result ai-check">
            <p v-if="checkItems.length" class="ai-check__hint">点击条目：在正文中定位选中错误位置，并复制「修改结果」</p>
            <template v-if="checkItems.length">
              <button
                v-for="(item, index) in checkItems"
                :key="index"
                type="button"
                class="ai-check__item"
                :class="{ 'is-active': activeCheckIndex === index }"
                @click="locateError(index)"
              >
                <span class="ai-check__type">{{ item['错误类型'] }}</span>
                <span class="ai-check__pos">原文：{{ item['原文位置'] }}</span>
                <span class="ai-check__fix">改：{{ item['修改结果'] }}</span>
                <span class="ai-check__tip">{{ item['修改建议'] }}</span>
              </button>
            </template>
            <p v-else class="ai-check__empty">未检测到明显问题，正文内容通过校验</p>
          </div>
        </article>

        <!-- 5. AI 文稿打分 -->
        <article class="ai-tool">
          <div class="ai-tool__bar">
            <span class="ai-tool__icon ai-tool__icon--green" aria-hidden="true">
              <el-icon><Trophy /></el-icon>
            </span>
            <div class="ai-tool__meta">
              <span class="ai-tool__name">AI 文稿打分</span>
              <span class="ai-tool__desc">从适配度、用语规范等维度为文稿评分</span>
            </div>
            <el-button
              type="primary"
              size="small"
              :disabled="!canUse('score')"
              :loading="loading.score"
              @click="run('score')"
            >
              调用
            </el-button>
          </div>
          <div v-if="hasScore" class="ai-tool__result ai-score">
            <!-- 综合等级 + 总分 -->
            <div class="ai-score__head">
              <div class="ai-score__grade-box">
                <span class="ai-score__label">综合等级</span>
                <span class="ai-score__grade">{{ scoreGrade || '未评级' }}</span>
              </div>
              <div class="ai-score__total">
                <span class="ai-score__label">总分</span>
                <span class="ai-score__value">{{ scoreTotal }}</span>
              </div>
            </div>

            <!-- 整体总结 -->
            <p v-if="scoreSummary" class="ai-score__summary">{{ scoreSummary }}</p>

            <!-- 分项评分 -->
            <div v-for="(item, index) in scoreItems" :key="index" class="ai-score__row">
              <div class="ai-score__row-head">
                <span>{{ item['维度'] }}</span>
                <span class="ai-score__point">{{ item['得分'] }}</span>
              </div>
              <el-progress
                :percentage="scorePercent(item['得分'])"
                :show-text="false"
                :stroke-width="6"
                class="ai-score__bar"
              />
              <p v-if="item['建议']" class="ai-score__tip">建议：{{ item['建议'] }}</p>
            </div>

            <!-- 现存问题清单 -->
            <div v-if="scoreIssues.length" class="ai-score__list">
              <div class="ai-score__list-title">现存问题清单</div>
              <p v-for="(issue, i) in scoreIssues" :key="`issue-${i}`" class="ai-score__issue">{{ issue }}</p>
            </div>

            <!-- 标题优化建议 -->
            <div v-if="scoreSuggestions.length" class="ai-score__list">
              <div class="ai-score__list-title">标题优化建议</div>
              <p v-for="(sug, i) in scoreSuggestions" :key="`sug-${i}`" class="ai-score__suggestion">{{ sug }}</p>
            </div>
          </div>
        </article>
      </aside>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" @click="visible = false">完成</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheck, Collection, Document, EditPen, MagicStick, Trophy, Warning,
} from '@element-plus/icons-vue'
import { aiAssistApi, aiCorrectionApi } from '../api'
import RichTextEditor from './RichTextEditor.vue'
import { stripHtml } from '../utils/text'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 写稿页的 form 响应式对象：直接编辑其属性，天然双向绑定
  form: { type: Object, required: true },
  categories: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

// 各功能需要满足的输入条件
const NEEDS = {
  classify: ['title'],
  summary: ['title', 'content'],
  review: ['title', 'content'],
  check: ['content'],
  score: ['title', 'content'],
}

// 功能键→后端 feature_type 的映射（用于恢复最近一次任务）
const FEATURE_TYPE = { classify: 1, summary: 2, review: 3, check: 4, score: 5 }

const editTab = ref('edit')
const loading = reactive({ classify: false, summary: false, review: false, check: false, score: false })
const classifyResult = ref('')
const correctionCategoryId = ref(null)
const correcting = ref(false)
const summaryResult = ref('')
const reviewItems = ref([])
const checkItems = ref([])
const checkDone = ref(false)
const activeCheckIndex = ref(-1)
const locateHint = ref('')
const scoreItems = ref([])
const scoreTotal = ref('')
const scoreGrade = ref('')
const scoreSummary = ref('')
const scoreIssues = ref([])
const scoreSuggestions = ref([])

// 异步任务轮询：每 2 秒一次，最长 5 分钟（当前假实现秒级完成，接入真实模型后保持即可）
const POLL_INTERVAL_MS = 2000
const POLL_MAX_TIMES = 150
let pollAbort = false

// 正文纯文本（优先用编辑器同步的 content_source，缺失时剥离 HTML，用于启用判断与高亮定位）
const contentText = computed(() => {
  const source = props.form?.content_source || ''
  return (source.trim() || stripHtml(props.form?.content || '')).trim()
})

// 弹窗内编辑器纯文本回调：同步到 content_source（写稿页编辑器同样会更新）
function onContentChange(text) {
  if (props.form) props.form.content_source = text
}

function canUse(key) {
  return NEEDS[key].every((field) => {
    if (field === 'title') return Boolean(props.form?.title?.trim())
    if (field === 'content') return contentText.value.length > 0
    return true
  })
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// 高亮预览：把正文转为纯文本，再将当前选中错误的「原文位置」包上红色 mark
const hasHighlight = computed(() => activeCheckIndex.value >= 0)
const highlightHint = computed(() => {
  if (!hasHighlight.value) return ''
  const item = checkItems.value[activeCheckIndex.value]
  if (!item) return ''
  return `已定位「${item['原文位置']}」，红色标记为错误位置`
})
const previewHtml = computed(() => {
  if (activeCheckIndex.value < 0) return ''
  const item = checkItems.value[activeCheckIndex.value]
  const pos = item?.['原文位置'] || ''
  const plain = contentText.value
  const found = findTargetInText(plain, pos)
  if (!found) return ''
  const matched = plain.slice(found.start, found.end)
  return (
    escHtml(plain.slice(0, found.start)) +
    `<mark class="ai-mark">${escHtml(matched)}</mark>` +
    escHtml(plain.slice(found.end))
  )
})
const escapedContent = computed(() => escHtml(contentText.value))

// 在文本中定位目标：优先精确匹配，失败时忽略空白差异（换行/连续空格）继续匹配
function findTargetInText(total, target) {
  if (!total || !target) return null
  const exact = total.indexOf(target)
  if (exact >= 0) return { start: exact, end: exact + target.length }
  const normTarget = target.replace(/\s+/g, ' ').trim()
  if (!normTarget) return null
  const escaped = normTarget.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+')
  const m = total.match(new RegExp(escaped))
  if (!m || typeof m.index !== 'number') return null
  return { start: m.index, end: m.index + m[0].length }
}

// 在可编辑正文中定位并选中指定文本（跨文本节点查找，滚动到可见区域）
function selectTextInEditor(text) {
  const editorEl =
    document.querySelector('.ai-edit [data-slate-editor]') ||
    document.querySelector('.ai-edit [contenteditable="true"]')
  if (!editorEl || !text) return false
  const textNodes = []
  const walker = document.createTreeWalker(editorEl, NodeFilter.SHOW_TEXT)
  let node
  while ((node = walker.nextNode())) {
    const v = node.nodeValue || ''
    if (v.length) textNodes.push({ node, v })
  }
  let total = ''
  const starts = []
  for (const t of textNodes) {
    starts.push(total.length)
    total += t.v
  }
  const found = findTargetInText(total, text)
  if (!found) return false
  const pos = found.start
  const end = found.end
  let startIdx = 0
  while (startIdx < starts.length - 1 && starts[startIdx + 1] <= pos) startIdx += 1
  let endIdx = startIdx
  while (endIdx < starts.length - 1 && starts[endIdx + 1] < end) endIdx += 1
  const range = document.createRange()
  range.setStart(textNodes[startIdx].node, pos - starts[startIdx])
  range.setEnd(textNodes[endIdx].node, end - starts[endIdx])
  const sel = window.getSelection()
  sel.removeAllRanges()
  sel.addRange(range)
  const rect = range.getBoundingClientRect()
  if (rect) {
    ;(editorEl.closest('.ai-edit') || editorEl).scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  return true
}

// wangEditor 挂载是异步的，等待编辑区 DOM 出现后再定位
function waitForEditorElement() {
  return new Promise((resolve) => {
    let tries = 0
    const timer = setInterval(() => {
      const el =
        document.querySelector('.ai-edit [data-slate-editor]') ||
        document.querySelector('.ai-edit [contenteditable="true"]')
      tries += 1
      if (el || tries >= 20) {
        clearInterval(timer)
        resolve(el)
      }
    }, 100)
  })
}

// 复制文本到剪贴板（优先 Clipboard API，降级 execCommand）
async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // 继续走兜底
  }
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.left = '-9999px'
  document.body.appendChild(ta)
  ta.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(ta)
  return ok
}

async function locateError(index) {
  activeCheckIndex.value = index
  const item = checkItems.value[index]
  if (!item) return
  const pos = item['原文位置'] || ''
  const fix = item['修改结果'] || ''
  // 切回可编辑模式并在正文中选中错误位置，便于用户直接修改
  editTab.value = 'edit'
  await nextTick()
  await waitForEditorElement()
  const located = selectTextInEditor(pos)
  const copied = await copyText(fix)
  locateHint.value = `已选中「${pos}」，可直接修改；修改结果${copied ? '已复制' : '复制失败，请手动复制'}`
  if (located) {
    ElMessage.success(copied ? `已定位「${pos}」并复制修改结果「${fix}」` : `已定位「${pos}」，修改结果复制失败`)
  } else {
    ElMessage.warning('正文中未找到该原文位置（可能已被修改）')
  }
}

function scorePercent(point) {
  const match = String(point || '').match(/(\d+)\s*\/\s*(\d+)/)
  if (!match) return 0
  return Math.round((Number(match[1]) / Number(match[2])) * 100)
}

// 文稿打分结果：有总分/等级/总结/分项任一即展示
const hasScore = computed(() => {
  return Boolean(scoreTotal.value || scoreGrade.value || scoreSummary.value)
    || (Array.isArray(scoreItems.value) && scoreItems.value.length > 0)
})

// 多维度审核结果：有总体风险或明细即展示
const hasReview = computed(() => {
  const r = reviewItems.value || {}
  return Boolean(r.overall_risk) || (Array.isArray(r.risk_list) && r.risk_list.length > 0)
})

// 总体风险 → 徽章颜色：高风险红 / 中风险橙 / 低风险黄 / 安全绿
function riskClass(overall) {
  const s = String(overall || '')
  if (s.includes('高')) return 'is-red'
  if (s.includes('中')) return 'is-orange'
  if (s.includes('低')) return 'is-yellow'
  return 'is-green'
}

// 单项风险等级 → 颜色：🔴确定违规 / 🟠高风险疑似 / 🟡低风险疑似
function riskLevelClass(level) {
  const s = String(level || '')
  if (s.includes('🔴') || s.includes('确定违规')) return 'is-red'
  if (s.includes('🟠') || s.includes('高风险')) return 'is-orange'
  if (s.includes('🟡') || s.includes('低风险')) return 'is-yellow'
  return 'is-gray'
}

// 提交分类纠正：保存训练样本（标题+正文+模型分类+纠正分类），并把纠正栏目选中到当前文稿
async function submitCorrection() {
  const hit = props.categories.find((c) => c.id === correctionCategoryId.value)
  if (!hit) return
  correcting.value = true
  try {
    await aiCorrectionApi.submit({
      title: props.form.title || '',
      content: contentText.value,
      model_category: classifyResult.value,
      corrected_category: hit.name,
      article_id: props.form.id || null,
      draft_key: props.form?.draft_key || null,
    })
    // 纠正结果应用到当前文稿：自动选中纠正栏目
    if (!props.form.category_ids.includes(hit.id)) props.form.category_ids.push(hit.id)
    ElMessage.success(`已纠正为「${hit.name}」并自动选中，样本已加入训练数据集`)
    correctionCategoryId.value = null
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    correcting.value = false
  }
}

function applyResult(key, data, silent = false) {
  if (key === 'classify') {
    classifyResult.value = data.category_name
    const hit = props.categories.find((c) => c.name === data.category_name)
    if (hit) {
      if (!props.form.category_ids.includes(hit.id)) props.form.category_ids.push(hit.id)
      if (!silent) ElMessage.success(`已自动选中栏目「${hit.name}」`)
    } else if (!silent) {
      ElMessage.warning(`识别到栏目「${data.category_name}」，但栏目列表中不存在`)
    }
  } else if (key === 'summary') {
    const summaryText = (data && data.summary) || ''
    summaryResult.value = summaryText
    if (summaryText) {
      props.form.summary = summaryText
      if (!silent) ElMessage.success('摘要已回写到摘要输入框')
    } else if (!silent) {
      ElMessage.warning('AI 未返回有效摘要，请重新尝试')
    }
  } else if (key === 'review') {
    reviewItems.value = data
  } else if (key === 'check') {
    checkItems.value = data.items || []
    checkDone.value = true
    activeCheckIndex.value = -1
  } else if (key === 'score') {
    scoreItems.value = data['分项评分'] || []
    scoreTotal.value = data['总分'] || ''
    scoreGrade.value = data['综合等级'] || ''
    scoreSummary.value = data['整体总结'] || ''
    scoreIssues.value = data['现存问题清单'] || []
    scoreSuggestions.value = data['标题优化建议'] || []
  }
}

async function pollTaskResult(key, taskId) {
  let data = null
  for (let i = 0; i < POLL_MAX_TIMES; i++) {
    if (pollAbort) return null
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
    if (pollAbort) return null
    const status = await aiAssistApi.getTask(taskId)
    if (status.status === 'success') {
      data = status.result
      break
    }
    if (status.status === 'failed') {
      throw new Error(status.error || 'AI 任务执行失败，请稍后重试')
    }
  }
  if (!data) throw new Error('AI 任务处理超时，可稍后在后台「AI 调用记录」中查看')
  applyResult(key, data)
  return data
}

async function run(key) {
  loading[key] = true
  pollAbort = false
  try {
    const payload = {
      title: props.form.title || '',
      summary: props.form.summary || '',
      // AI 入参使用纯文本正文（content_source），避免把 HTML 标签交给模型
      content: contentText.value,
      article_id: props.form.id || null,
      draft_key: props.form?.draft_key || null,
      category_ids: props.form.category_ids || [],
    }
    const submitRes = await aiAssistApi[key](payload)
    const taskId = submitRes?.task_id
    if (!taskId) throw new Error('AI 任务提交失败，请稍后重试')
    await pollTaskResult(key, taskId)
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading[key] = false
  }
}

// 重新打开弹窗时恢复最近一次任务：已成功直接回写；失败允许重调；running 继续轮询
async function restoreLatestResults() {
  // 恢复依据：已有文稿按 ID；未保存的新建草稿按 draft_key（关闭重开不丢上次结果）
  const articleId = props.form?.id || null
  const draftKey = props.form?.draft_key || null
  if (!articleId && !draftKey) return
  const running = []
  for (const [key, featureType] of Object.entries(FEATURE_TYPE)) {
    try {
      const latest = await aiAssistApi.latestTask(featureType, articleId, draftKey)
      if (latest.status === 'success') {
        applyResult(key, latest.result, true)
      } else if (latest.status === 'pending' || latest.status === 'running') {
        loading[key] = true
        running.push({ key, taskId: latest.task_id })
      }
    } catch {
      // 无历史任务，正常展示空状态
    }
  }
  await Promise.all(
    running.map(async ({ key, taskId }) => {
      try { await pollTaskResult(key, taskId) } catch { /* 错误已提示 */ } finally { loading[key] = false }
    }),
  )
}

// 每次打开弹窗时：清空临时状态后尝试恢复最近一次结果
watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      pollAbort = false
      editTab.value = 'edit'
      classifyResult.value = ''
      correctionCategoryId.value = null
      summaryResult.value = ''
      reviewItems.value = []
      checkItems.value = []
      checkDone.value = false
      activeCheckIndex.value = -1
      locateHint.value = ''
      scoreItems.value = []
      scoreTotal.value = ''
      scoreGrade.value = ''
      scoreSummary.value = ''
      scoreIssues.value = []
      scoreSuggestions.value = []
      Object.keys(loading).forEach((key) => { loading[key] = false })
      restoreLatestResults()
    } else {
      // 关闭弹窗：中止进行中的轮询，避免组件销毁后仍在后台查询
      pollAbort = true
    }
  },
)
</script>

<style scoped>
/* AI 协作台弹窗：flat 风格 + 项目设计令牌，左编辑 / 右 AI 功能双栏 */
.ai-assist-dialog :deep(.el-dialog) {
  border-radius: var(--radius-lg, 16px);
  overflow: hidden;
  box-shadow: var(--shadow-float, 0 10px 30px rgba(30, 41, 59, 0.12));
}

.ai-assist-dialog :deep(.el-dialog__header) {
  padding: 18px 24px;
  margin: 0;
  border-bottom: 1px solid var(--color-rule, #e2e8f0);
}

.ai-assist-dialog :deep(.el-dialog__body) {
  padding: 0;
  max-height: calc(100dvh - 220px);
  overflow: hidden;
}

.ai-assist-dialog :deep(.el-dialog__footer) {
  padding: 12px 24px;
  border-top: 1px solid var(--color-rule, #e2e8f0);
}

.ai-head {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ai-head__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 12px;
  color: #fff;
  font-size: 22px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
}

.ai-head__title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-ink, #1e293b);
  line-height: 1.2;
}

.ai-head__sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-ink-3, #94a3b8);
}

.ai-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  min-height: 480px;
}

/* ---- 左栏：文稿编辑 ---- */
.ai-edit {
  padding: 20px 24px;
  border-right: 1px solid var(--color-rule, #e2e8f0);
  overflow-y: auto;
  max-height: calc(100dvh - 220px);
}

.ai-edit__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.ai-section-title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 15px;
  font-weight: 700;
  color: var(--color-ink, #1e293b);
}

.ai-tabs {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--color-paper-2, #f1f5f9);
  border: 1px solid var(--color-rule, #e2e8f0);
  border-radius: 8px;
}

.ai-tabs__btn {
  border: none;
  background: transparent;
  color: var(--color-ink-2, #64748b);
  font-size: 12px;
  font-weight: 600;
  min-height: 28px;
  padding: 0 14px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
    color 150ms cubic-bezier(0.16, 1, 0.3, 1);
}

.ai-tabs__btn:hover:not(:disabled) {
  color: var(--color-ink, #1e293b);
}

.ai-tabs__btn:focus-visible {
  outline: 2px solid var(--color-primary, #2563eb);
  outline-offset: 1px;
}

.ai-tabs__btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.ai-tabs__btn.is-active {
  background: var(--color-surface, #fff);
  color: var(--color-primary, #2563eb);
  box-shadow: 0 1px 3px rgba(30, 41, 59, 0.08);
}

.ai-field {
  margin-bottom: 14px;
}

.ai-label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-2, #64748b);
}

.ai-field__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ai-highlight-hint {
  font-size: 12px;
  color: var(--color-danger, #dc2626);
}

.ai-category-select {
  width: 100%;
}

.ai-content-preview {
  min-height: 240px;
  border: 1px solid var(--color-rule, #e2e8f0);
  border-radius: var(--radius-sm, 6px);
  padding: 12px 14px;
  background: var(--color-paper, #fff);
  color: var(--color-ink, #1e293b);
  font-size: 14px;
  line-height: var(--leading-normal, 1.6);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-y: auto;
  max-height: 300px;
}

/* 错误高亮标记 */
.ai-content-preview :deep(.ai-mark) {
  background: rgba(220, 38, 38, 0.16);
  color: #b91c1c;
  font-weight: 700;
  padding: 0 2px;
  border-radius: 3px;
  box-shadow: 0 0 0 1px rgba(220, 38, 38, 0.35);
}

/* ---- 右栏：AI 功能面板 ---- */
.ai-tools {
  padding: 20px 20px 24px;
  background: var(--color-paper-2, #f8fafc);
  overflow-y: auto;
  max-height: calc(100dvh - 220px);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-tools__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

.ai-tools__note {
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
}

.ai-tool {
  background: var(--color-surface, #fff);
  border: 1px solid var(--color-rule, #e2e8f0);
  border-radius: 12px;
  padding: 12px 14px;
  transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 150ms cubic-bezier(0.16, 1, 0.3, 1);
}

.ai-tool:hover {
  border-color: var(--color-rule-strong, #cbd5e1);
  box-shadow: 0 2px 8px rgba(30, 41, 59, 0.05);
}

.ai-tool__bar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ai-tool__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 10px;
  font-size: 18px;
}

.ai-tool__icon--violet { background: #ede9fe; color: #7c3aed; }
.ai-tool__icon--blue { background: #dbeafe; color: #2563eb; }
.ai-tool__icon--amber { background: #fef3c7; color: #d97706; }
.ai-tool__icon--red { background: #fee2e2; color: #dc2626; }
.ai-tool__icon--green { background: #dcfce7; color: #16a34a; }

.ai-tool__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.ai-tool__name {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-ink, #1e293b);
}

.ai-tool__desc {
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
  line-height: 1.4;
}

.ai-tool :deep(.el-button) {
  flex-shrink: 0;
  min-height: 32px;
}

.ai-tool__result {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--color-rule, #e2e8f0);
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-ink-2, #64748b);
}

.ai-result-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.ai-result-icon--ok {
  color: var(--color-success, #16a34a);
}

/* 分类纠正区 */
.ai-correction {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--color-rule, #e2e8f0);
  flex-wrap: wrap;
}

.ai-correction__label {
  font-size: 12px;
  color: var(--color-ink-2, #64748b);
}

.ai-correction__select {
  width: 140px;
  flex-shrink: 0;
}

/* 多维度审核结果：总体风险徽章 + 风险明细卡片 + 总结 */
.ai-review {
  flex-direction: column;
  align-items: stretch;
  width: 100%;
}

.ai-review__overall {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.ai-review__overall-label {
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
}

.ai-review__badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.ai-review__badge.is-green { background: #dcfce7; color: #15803d; }
.ai-review__badge.is-yellow { background: #fef9c3; color: #a16207; }
.ai-review__badge.is-orange { background: #ffedd5; color: #c2410c; }
.ai-review__badge.is-red { background: #fee2e2; color: #b91c1c; }

.ai-review__item {
  border: 1px solid var(--color-rule, #e2e8f0);
  border-radius: 10px;
  background: var(--color-paper, #fff);
  padding: 10px 12px;
  margin-bottom: 8px;
}

.ai-review__item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.ai-review__dim {
  font-size: 13px;
  font-weight: 700;
}

.ai-review__dim.is-red { color: #b91c1c; }
.ai-review__dim.is-orange { color: #c2410c; }
.ai-review__dim.is-yellow { color: #a16207; }
.ai-review__dim.is-gray { color: var(--color-ink-2, #64748b); }

.ai-review__level {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-2, #64748b);
}

.ai-review__source,
.ai-review__desc,
.ai-review__suggestion {
  margin: 4px 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-2, #64748b);
}

.ai-review__source b,
.ai-review__suggestion b {
  color: var(--color-ink, #1e293b);
  font-weight: 600;
}

.ai-review__desc {
  color: var(--color-ink, #1e293b);
}

.ai-review__empty {
  margin: 0 0 6px;
  font-size: 12px;
  color: #15803d;
}

.ai-review__summary {
  margin: 6px 0 0;
  padding-top: 8px;
  border-top: 1px dashed var(--color-rule, #e2e8f0);
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-2, #64748b);
}

/* 校验错误列表 */
.ai-check {
  flex-direction: column;
  width: 100%;
}

.ai-check__item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  text-align: left;
  border: 1px solid var(--color-rule, #e2e8f0);
  border-radius: 8px;
  background: var(--color-paper, #fff);
  padding: 8px 10px;
  font-size: 12px;
  color: var(--color-ink-2, #64748b);
  cursor: pointer;
  transition: border-color 150ms cubic-bezier(0.16, 1, 0.3, 1),
    background-color 150ms cubic-bezier(0.16, 1, 0.3, 1);
}

.ai-check__item:hover {
  border-color: var(--color-danger, #dc2626);
}

.ai-check__item:focus-visible {
  outline: 2px solid var(--color-danger, #dc2626);
  outline-offset: 1px;
}

.ai-check__item.is-active {
  border-color: var(--color-danger, #dc2626);
  background: #fef2f2;
}

.ai-check__hint {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
}

.ai-check__empty {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #15803d;
}

.ai-check__type {
  font-weight: 700;
  color: var(--color-danger, #dc2626);
}

.ai-check__pos,
.ai-check__fix {
  color: var(--color-ink, #1e293b);
}

.ai-check__tip {
  color: var(--color-ink-3, #94a3b8);
}

/* 打分结果 */
.ai-score {
  flex-direction: column;
  width: 100%;
}

.ai-score__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.ai-score__grade-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ai-score__grade {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 800;
  color: var(--color-primary, #2563eb);
  line-height: 1.2;
}

.ai-score__total {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.ai-score__summary {
  margin: 0 0 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--color-rule, #e2e8f0);
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-2, #64748b);
}

.ai-score__list {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--color-rule, #e2e8f0);
}

.ai-score__list-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-ink, #1e293b);
  margin-bottom: 4px;
}

.ai-score__issue,
.ai-score__suggestion {
  margin: 0 0 4px;
  padding-left: 10px;
  position: relative;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-2, #64748b);
}

.ai-score__issue::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-danger, #dc2626);
}

.ai-score__suggestion::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-success, #16a34a);
}

.ai-score__label {
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
}

.ai-score__value {
  font-family: var(--font-heading);
  font-size: 26px;
  font-weight: 800;
  color: var(--color-primary, #2563eb);
  line-height: 1;
}

.ai-score__row {
  margin-bottom: 8px;
}

.ai-score__row-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--color-ink-2, #64748b);
  margin-bottom: 4px;
}

.ai-score__point {
  font-weight: 700;
  color: var(--color-ink, #1e293b);
  font-variant-numeric: tabular-nums;
}

.ai-score__bar :deep(.el-progress-bar__outer) {
  background: var(--color-rule, #e2e8f0);
}

.ai-score__tip {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
}

/* ---- 响应式 ---- */
@media (max-width: 900px) {
  .ai-body {
    grid-template-columns: 1fr;
  }

  .ai-edit {
    border-right: none;
    border-bottom: 1px solid var(--color-rule, #e2e8f0);
    max-height: none;
  }
}
</style>
