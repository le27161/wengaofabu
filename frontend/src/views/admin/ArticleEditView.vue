<template>
  <div class="article-edit">
    <!-- 吸顶工具栏：返回 + 标题 + 保存/提交 -->
    <header class="edit-toolbar">
      <div class="edit-toolbar__left">
        <AdminBackLink to="/admin/articles" label="返回列表" />
        <h1 class="edit-title">{{ isEdit ? '编辑文稿' : '写新文稿' }}</h1>
      </div>
      <div class="edit-toolbar__actions">
        <el-button
          v-if="canUseAiWriting"
          type="success"
          :loading="aiWritingLoading"
          @click="generateAiWriting"
        >
          AI写作助手
        </el-button>
        <el-button v-if="!smartCollectReview" class="ai-assist-btn" @click="aiVisible = true">
          <el-icon><MagicStick /></el-icon>
          <span>AI 协作台</span>
        </el-button>
        <el-button :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button type="primary" :loading="submitting" @click="save(true)">提交审核</el-button>
      </div>
    </header>

    <el-alert
      v-if="aiWritingLoading"
      title="Qwen正在根据已确认事实生成文章草稿……"
      type="info"
      show-icon
      :closable="false"
      class="ai-writing-loading"
    />

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="edit-layout"
      @submit.prevent
    >
      <!-- 左侧主编辑区 -->
      <div class="edit-main">
        <section class="edit-card">
          <h2 class="edit-card__title">文稿信息</h2>
          <el-form-item label="标题" prop="title" class="field-title">
            <el-input
              v-model="form.title"
              maxlength="200"
              show-word-limit
              placeholder="一句话说清这篇文稿讲什么"
            />
          </el-form-item>
          <el-form-item label="摘要" prop="summary">
            <el-input
              v-model="form.summary"
              maxlength="500"
              show-word-limit
              type="textarea"
              :rows="3"
              placeholder="列表页展示的一句话摘要，建议 50 字以内"
            />
          </el-form-item>
        </section>

        <section class="edit-card edit-card--editor">
          <div class="edit-card__head">
            <h2 class="edit-card__title">正文内容</h2>
            <div class="editor-tools">
              <span class="editor-tools__count">{{ contentStats }}</span>
              <div class="mode-toggle" role="group" aria-label="编辑模式切换">
                <button
                  type="button"
                  class="mode-btn"
                  :class="{ 'is-active': !previewMode }"
                  @click="previewMode = false"
                >
                  编辑
                </button>
                <button
                  type="button"
                  class="mode-btn"
                  :class="{ 'is-active': previewMode }"
                  @click="previewMode = true"
                >
                  预览
                </button>
              </div>
            </div>
          </div>
          <RichTextEditor
            v-if="!aiVisible && !previewMode"
            v-model="form.content"
            class="content-editor"
            @text-change="onContentChange"
          />
          <div v-else class="content-preview article-content" v-html="form.content || '<p style=&quot;color:#94a3b8&quot;>暂无内容</p>'"></div>
        </section>
      </div>

      <!-- 右侧设置栏 -->
      <aside class="edit-rail">
        <section class="edit-card">
          <h2 class="edit-card__title">发布设置</h2>
          <el-form-item label="所属栏目（可多选）" prop="category_ids">
            <el-select v-model="form.category_ids" multiple placeholder="选择栏目" class="rail-select">
              <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="分发渠道（可多选）" prop="channel_ids">
            <el-checkbox-group v-model="form.channel_ids" class="channel-chips">
              <el-checkbox
                v-for="ch in channels"
                :key="ch.id"
                :value="ch.id"
                :disabled="ch.is_default"
                class="channel-chip"
              >
                {{ ch.name }}
                <el-tag v-if="ch.is_default" size="small" type="info" class="channel-default-tag">基础</el-tag>
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="城市（同城搜索使用）" prop="city">
            <el-select
              v-model="form.city"
              placeholder="选择城市（留空表示全国/不限定）"
              clearable
              filterable
              allow-create
              default-first-option
              class="rail-select"
            >
              <el-option v-for="c in cityPreset" :key="c" :label="c" :value="c" />
            </el-select>
          </el-form-item>
        </section>

        <section class="edit-card">
          <h2 class="edit-card__title">封面图</h2>
          <p class="edit-card__hint">从资源库选择一张封面，用于列表与头条展示</p>
          <ResourcePicker v-model="form.cover_url" />
        </section>

        <section class="edit-card edit-card--checklist">
          <h2 class="edit-card__title">提交前检查</h2>
          <ul class="check-list">
            <li :class="{ 'is-done': checklist.title }">
              <span class="check-list__dot" aria-hidden="true"></span>
              <span>标题已填写</span>
              <span class="check-list__state">{{ checklist.title ? '已满足' : '待完善' }}</span>
            </li>
            <li :class="{ 'is-done': checklist.category }">
              <span class="check-list__dot" aria-hidden="true"></span>
              <span>至少选择一个栏目</span>
              <span class="check-list__state">{{ checklist.category ? '已满足' : '待完善' }}</span>
            </li>
            <li :class="{ 'is-done': checklist.content }">
              <span class="check-list__dot" aria-hidden="true"></span>
              <span>正文内容非空（提交审核需要）</span>
              <span class="check-list__state">{{ checklist.content ? '已满足' : '待完善' }}</span>
            </li>
          </ul>
        </section>
      </aside>
    </el-form>

    <section v-if="aiWritingPreview" class="ai-writing-preview">
      <div class="ai-writing-preview__head">
        <div>
          <h2>AI写作建议</h2>
          <p>当前仅为预览；采用后仍需点击“保存草稿”才会写入数据库。</p>
        </div>
        <div class="ai-writing-preview__meta">
          <el-tag type="success">{{ aiWritingPreview.model }}</el-tag>
          <el-tag type="info">Synthesis v{{ aiWritingPreview.synthesis_version }}</el-tag>
          <el-tag type="info">core_facts {{ aiWritingPreview.approved_core_fact_count }} 条</el-tag>
          <el-tag type="info">{{ aiWritingPreview.elapsed_ms }} ms</el-tag>
          <el-tag type="info">
            Token {{ aiWritingPreview.input_tokens ?? '-' }} + {{ aiWritingPreview.output_tokens ?? '-' }}
            = {{ aiWritingPreview.total_tokens ?? '-' }}
          </el-tag>
          <el-tag type="info">正文 {{ aiWritingPreview.result.content_html.length }} 字符</el-tag>
        </div>
      </div>

      <div class="ai-writing-suggestion">
        <div class="ai-writing-suggestion__label">
          <h3>AI建议标题</h3>
          <el-button size="small" @click="adoptAiTitle">采用标题</el-button>
        </div>
        <p>{{ aiWritingPreview.result.title }}</p>
      </div>

      <div class="ai-writing-suggestion">
        <div class="ai-writing-suggestion__label">
          <h3>AI建议摘要</h3>
          <el-button size="small" @click="adoptAiSummary">采用摘要</el-button>
        </div>
        <p>{{ aiWritingPreview.result.summary }}</p>
      </div>

      <div class="ai-writing-suggestion">
        <div class="ai-writing-suggestion__label">
          <h3>AI建议正文</h3>
          <el-button size="small" @click="adoptAiContent">采用正文</el-button>
        </div>
        <div class="article-content ai-writing-content" v-html="aiWritingPreview.result.content_html"></div>
      </div>

      <div class="ai-writing-preview__actions">
        <el-button type="primary" @click="adoptAllAiWriting">全部采用</el-button>
        <el-button @click="aiWritingPreview = null">关闭</el-button>
      </div>
    </section>

    <section v-if="smartCollectReview" class="smart-collect-review">
      <div class="smart-collect-review__head">
        <div>
          <h2>智能采编来源</h2>
          <p>来源与 AI 审核提示仅供编辑查看，不会写入文稿正文。</p>
        </div>
        <el-tag type="info">来源数量 {{ smartCollectReview.source_count }}</el-tag>
      </div>

      <div class="smart-collect-sources">
        <article
          v-for="source in smartCollectReview.sources"
          :key="source.clue_id"
          class="smart-collect-source"
        >
          <div class="smart-collect-source__title">
            <strong>SOURCE[{{ source.clue_id }}]</strong>
            <span>{{ source.title }}</span>
          </div>
          <dl>
            <div>
              <dt>clue_id</dt>
              <dd>{{ source.clue_id }}</dd>
            </div>
            <div>
              <dt>来源网站</dt>
              <dd>{{ source.source || '未记录' }}</dd>
            </div>
            <div>
              <dt>原始 URL</dt>
              <dd>
                <a
                  v-if="isHttpUrl(source.url)"
                  :href="source.url"
                  target="_blank"
                  rel="noopener noreferrer"
                >{{ source.url }}</a>
                <span v-else>{{ source.url || '未记录' }}</span>
              </dd>
            </div>
          </dl>
          <el-button
            link
            type="primary"
            :disabled="source.content_status !== 'completed'"
            @click="viewCleanContent(source)"
          >
            {{ source.content_status === 'completed' ? '查看清洗正文' : '清洗正文不可用' }}
          </el-button>
        </article>
      </div>

      <div class="ai-review-notes">
        <h3>AI 审核提示</h3>
        <div>
          <h4>conflicts</h4>
          <p v-if="!smartCollectReview.conflicts.length">未识别到明确冲突。</p>
          <ul v-else>
            <li v-for="(conflict, index) in smartCollectReview.conflicts" :key="`conflict-${index}`">
              {{ conflict.description }}
              <small>
                涉及 {{ conflict.source_clue_ids.map((id) => `SOURCE[${id}]`).join('、') }}
              </small>
            </li>
          </ul>
        </div>
        <div>
          <h4>insufficient_evidence</h4>
          <p v-if="!smartCollectReview.insufficient_evidence.length">未识别到证据不足项。</p>
          <ul v-else>
            <li v-for="(item, index) in smartCollectReview.insufficient_evidence" :key="`insufficient-${index}`">
              {{ item }}
            </li>
          </ul>
        </div>
      </div>
    </section>

    <el-dialog v-model="contentDialog.visible" title="清洗后的新闻正文" width="820px" top="5vh">
      <div v-loading="contentDialog.loading" class="clean-content-dialog">
        <div v-if="contentDialog.detail" class="article-content" v-html="contentDialog.detail.content || ''"></div>
        <el-empty v-else-if="!contentDialog.loading" description="暂无清洗正文" />
      </div>
    </el-dialog>

    <!-- AI 协作台：页面内部窗口，与上方 form 双向绑定 -->
    <AIAssistDrawer v-model="aiVisible" :form="form" :categories="categories" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { articleApi, categoryApi, channelApi, smartCollectApi } from '../../api'
import { CITY_PRESET } from '../../stores/city'
import AIAssistDrawer from '../../components/AIAssistDrawer.vue'
import RichTextEditor from '../../components/RichTextEditor.vue'
import ResourcePicker from '../../components/ResourcePicker.vue'
import AdminBackLink from '../../components/AdminBackLink.vue'
import { stripHtml } from '../../utils/text'

const route = useRoute()
const router = useRouter()
const isEdit = Boolean(route.params.id)
const formRef = ref()
const categories = ref([])
const channels = ref([])
const cityPreset = CITY_PRESET
const saving = ref(false)
const submitting = ref(false)
const previewMode = ref(false)
const aiVisible = ref(false)
const smartCollectReview = ref(null)
const aiWritingLoading = ref(false)
const aiWritingPreview = ref(null)
const articleStatus = ref('')
const contentDialog = ref({ visible: false, loading: false, detail: null })

const form = reactive({
  title: '',
  summary: '',
  cover_url: '',
  category_ids: [],
  channel_ids: [],
  city: '',
  content: '',
  content_source: '',
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  category_ids: [{ required: true, type: 'array', min: 1, message: '请至少选择一个栏目', trigger: 'change' }],
}

// 正文纯文本字数（优先用 content_source，缺失时兜底剥离 HTML）
const contentStats = computed(() => {
  const text = form.content_source?.trim() || stripHtml(form.content)
  return `正文 ${text.length} 字`
})

// 富文本编辑器纯文本回调：同步到 content_source（保存时后端也会兜底）
function onContentChange(text) {
  form.content_source = text
}

// 提交前检查清单（仅展示用，提交校验仍在 save() 中执行）
const checklist = computed(() => ({
  title: Boolean(form.title.trim()),
  category: form.category_ids.length > 0,
  content: Boolean((form.content_source || '').trim() || stripHtml(form.content)),
}))

const canUseAiWriting = computed(() =>
  isEdit
  && smartCollectReview.value
  && ['draft', 'rejected'].includes(articleStatus.value)
  && !aiWritingLoading.value
)

// 新建文稿的草稿会话标识：AI 协作台调用记录先挂此键，保存拿到正式 ID 后回填 article_id
function genDraftKey() {
  try {
    return crypto.randomUUID()
  } catch {
    return `draft_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
  }
}

onMounted(async () => {
  try {
    const [catRes, chRes] = await Promise.all([categoryApi.list(), channelApi.list()])
    categories.value = catRes.items
    channels.value = chRes.items
    const defaultChannel = channels.value.find((c) => c.is_default)
    if (isEdit) {
      const detail = await articleApi.detail(route.params.id)
      Object.assign(form, {
        // 已有文稿的 ID：AI 协作台提交/恢复/纠正都靠它绑定 article_id（新建草稿走 draft_key）
        id: detail.id,
        title: detail.title,
        summary: detail.summary,
        cover_url: detail.cover_url,
        content: detail.content || '',
        content_source: detail.content_source || '',
        category_ids: detail.categories.map((c) => c.id),
        channel_ids: (detail.channels || []).map((c) => c.id),
        city: detail.city || '',
      })
      articleStatus.value = detail.status
      smartCollectReview.value = detail.smart_collect || null
    } else {
      // 新文稿：生成草稿会话标识（AI 协作台记录先挂此键，保存后回填正式文稿ID）
      form.draft_key = genDraftKey()
      // 新文稿默认勾选基础渠道（后端也会强制包含，这里保证界面一致）
      if (defaultChannel) form.channel_ids = [defaultChannel.id]
    }
  } catch (e) {
    ElMessage.error(String(e))
  }
})

function isHttpUrl(value) {
  return typeof value === 'string' && /^https?:\/\//i.test(value)
}

async function viewCleanContent(source) {
  contentDialog.value = { visible: true, loading: true, detail: null }
  try {
    contentDialog.value.detail = await smartCollectApi.getClueContent(source.clue_id)
  } catch (error) {
    contentDialog.value.visible = false
    ElMessage.error(String(error || '正文读取失败'))
  } finally {
    contentDialog.value.loading = false
  }
}

async function generateAiWriting() {
  if (!canUseAiWriting.value) return
  aiWritingLoading.value = true
  try {
    aiWritingPreview.value = await articleApi.aiWriting(route.params.id)
    ElMessage.success('AI写作建议已生成，请预览后选择采用')
  } catch (error) {
    ElMessage.error(String(error || 'AI写作助手生成失败，请稍后重试'))
  } finally {
    aiWritingLoading.value = false
  }
}

function adoptAiTitle() {
  if (!aiWritingPreview.value) return
  form.title = aiWritingPreview.value.result.title
  ElMessage.success('已采用AI建议标题，尚未保存')
}

function adoptAiSummary() {
  if (!aiWritingPreview.value) return
  form.summary = aiWritingPreview.value.result.summary
  ElMessage.success('已采用AI建议摘要，尚未保存')
}

async function confirmContentReplacement() {
  if (!form.content.trim()) return true
  try {
    await ElMessageBox.confirm(
      '采用AI正文将替换当前编辑器内容，是否继续？',
      '替换确认',
      { type: 'warning' },
    )
    return true
  } catch {
    return false
  }
}

async function adoptAiContent() {
  if (!aiWritingPreview.value || !(await confirmContentReplacement())) return
  form.content = aiWritingPreview.value.result.content_html
  form.content_source = stripHtml(form.content)
  previewMode.value = false
  ElMessage.success('已采用AI建议正文，尚未保存')
}

async function adoptAllAiWriting() {
  if (!aiWritingPreview.value || !(await confirmContentReplacement())) return
  form.title = aiWritingPreview.value.result.title
  form.summary = aiWritingPreview.value.result.summary
  form.content = aiWritingPreview.value.result.content_html
  form.content_source = stripHtml(form.content)
  previewMode.value = false
  ElMessage.success('已采用全部AI写作建议，尚未保存')
}

async function save(submitReview) {
  await formRef.value.validate()
  if (submitReview && !checklist.value.content) {
    ElMessage.warning('正文不能为空')
    return
  }
  const fn = submitReview ? submitting : saving
  fn.value = true
  try {
    const payload = {
      title: form.title,
      summary: form.summary,
      cover_url: form.cover_url,
      content: form.content,
      content_source: form.content_source || stripHtml(form.content),
      category_ids: form.category_ids,
      channel_ids: form.channel_ids,
      city: form.city || '',
      draft_key: form.draft_key || '',
    }
    const res = isEdit
      ? await articleApi.update(route.params.id, payload)
      : await articleApi.create(payload)
    const id = res.article?.id
    if (submitReview) {
      await articleApi.submit(id)
      ElMessage.success('已提交审核（待一审）')
    } else {
      ElMessage.success('草稿已保存')
    }
    router.push('/admin/articles')
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    fn.value = false
  }
}
</script>

<style scoped>
/* 触发热重载注释：确保 vite 重新编译 scoped 样式 */
/* Hallmark · component: article-edit-form · genre: editorial · theme: existing tokens (tokens.css)
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass (40–41) · tokens: pass (48) · responsive: pass (34, 49, 50–57)
 * pre-emit critique: P5 H4 E5 S4 R5 V5
 */
.article-edit {
  max-width: 1280px;
  margin: 0 auto;
}

/* ---- 吸顶工具栏 ---- */
.edit-toolbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-1);
  margin-bottom: var(--space-5);
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-rule);
}

.edit-toolbar__left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.back-btn {
  flex-shrink: 0;
  color: var(--color-ink-3);
}

.back-btn:hover {
  color: var(--color-primary);
}

.edit-title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: var(--tracking-tight);
  color: var(--color-ink);
  font-style: normal;
  overflow-wrap: anywhere;
  min-width: 0;
}

.edit-toolbar__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.edit-toolbar__actions :deep(.el-button) {
  min-height: var(--size-touch);
  padding: 0 var(--space-5);
  white-space: nowrap;
}

.ai-assist-btn {
  color: var(--color-primary);
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.ai-assist-btn:hover {
  color: #fff;
  border-color: var(--color-primary);
  background: var(--color-primary);
}

/* ---- 双栏布局 ---- */
.edit-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: var(--space-5);
  align-items: start;
}

.edit-main,
.edit-rail {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-width: 0;
}

/* ---- 卡片 ---- */
.edit-card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  box-shadow: var(--shadow-card);
}

.edit-card__title {
  margin: 0 0 var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-rule);
  font-family: var(--font-heading);
  font-size: var(--text-base);
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--color-ink);
  font-style: normal;
}

.edit-card__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  line-height: var(--leading-normal);
}

.edit-card--checklist {
  background: var(--color-paper-2);
}

/* ---- 标题字段：放大输入 ---- */
.field-title :deep(.el-input__wrapper) {
  padding: var(--space-2) var(--space-3);
}

.field-title :deep(.el-input__inner) {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--color-ink);
}

.field-title :deep(.el-input__count) {
  font-size: var(--text-xs);
}

/* ---- 正文卡片头部：字数 + 编辑/预览切换 ---- */
.edit-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-rule);
}

.edit-card__head .edit-card__title {
  margin: 0;
  padding: 0;
  border: none;
}

.editor-tools {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.editor-tools__count {
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.mode-toggle {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  background: var(--color-paper-2);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-sm);
}

.mode-btn {
  border: none;
  background: transparent;
  color: var(--color-ink-2);
  font-size: var(--text-xs);
  font-weight: 600;
  min-height: 28px;
  padding: 0 var(--space-3);
  border-radius: calc(var(--radius-sm) - 1px);
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.mode-btn:hover {
  color: var(--color-ink);
}

.mode-btn:active {
  transform: translateY(1px);
}

.mode-btn:focus-visible {
  outline: 2px solid var(--color-focus, var(--color-primary));
  outline-offset: 1px;
}

.mode-btn.is-active {
  background: var(--color-surface);
  color: var(--color-primary);
  box-shadow: var(--shadow-card);
}

/* ---- 正文编辑器（wangEditor） / 预览 ---- */
.content-editor :deep(.w-e-text-container) {
  min-height: 420px;
}

.content-preview {
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-sm);
  padding: var(--space-5);
  min-height: 420px;
  background: var(--color-paper);
  color: var(--color-ink);
}

/* ---- 右侧：栏目选择 ---- */
.rail-select {
  width: 100%;
}

/* ---- 右侧：分发渠道 chips ---- */
.channel-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.channel-chip {
  margin-right: 0;
}

/* 隐藏原生复选框但保留可聚焦（a11y），chip 形态由 label 呈现 */
.channel-chip :deep(.el-checkbox__input) {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.channel-chip :deep(.el-checkbox__label) {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px 14px;
  border: 1px solid var(--color-rule-strong);
  border-radius: 999px;
  background: var(--color-paper);
  color: var(--color-ink-2);
  font-size: var(--text-sm);
  font-weight: 500;
  line-height: 1;
  cursor: pointer;
  transition: background-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}

.channel-chip :deep(.el-checkbox__label:hover) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.channel-chip.is-checked :deep(.el-checkbox__label) {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
  color: var(--color-primary);
  font-weight: 600;
}

.channel-chip.is-disabled :deep(.el-checkbox__label) {
  opacity: 0.55;
  cursor: not-allowed;
  background: var(--color-paper-2);
  border-color: var(--color-rule);
  color: var(--color-ink-3);
}

.channel-chip.is-focus :deep(.el-checkbox__label) {
  outline: 2px solid var(--color-focus, var(--color-primary));
  outline-offset: 2px;
}

.channel-default-tag {
  margin-left: 0;
}

/* ---- 提交前检查清单 ---- */
.check-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.check-list li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--color-ink-3);
}

.check-list li.is-done {
  color: var(--color-ink-2);
}

.check-list__dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--color-rule-strong);
  transition: background-color var(--dur-fast) var(--ease-out);
}

.check-list li.is-done .check-list__dot {
  background: var(--color-success);
}

.check-list__state {
  margin-left: auto;
  font-size: var(--text-xs);
  color: var(--color-ink-3);
  white-space: nowrap;
}

.check-list li.is-done .check-list__state {
  color: var(--color-success);
}

/* ---- 智能采编：AI写作建议与来源审核 ---- */
.ai-writing-loading {
  margin-bottom: var(--space-4);
}

.ai-writing-preview,
.smart-collect-review {
  margin-top: var(--space-5);
  padding: var(--space-5);
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

.ai-writing-preview__head,
.smart-collect-review__head,
.smart-collect-source__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.ai-writing-preview__head h2,
.ai-writing-preview__head p,
.smart-collect-review__head h2,
.smart-collect-review__head p,
.ai-review-notes h3,
.ai-review-notes h4 {
  margin: 0;
}

.ai-writing-preview__head p,
.smart-collect-review__head p {
  margin-top: var(--space-1);
  color: var(--color-ink-3);
}

.ai-writing-preview__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}

.ai-writing-suggestion {
  margin-top: var(--space-4);
}

.ai-writing-suggestion__label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.ai-writing-suggestion p {
  margin: var(--space-2) 0 0;
  color: var(--color-ink-2);
}

.ai-writing-content {
  margin-top: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-sm);
  background: var(--color-paper);
}

.ai-writing-preview__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.smart-collect-sources {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.smart-collect-source,
.ai-review-notes {
  padding: var(--space-4);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-sm);
}

.smart-collect-source__title {
  justify-content: flex-start;
}

.smart-collect-source dl {
  display: grid;
  gap: var(--space-2);
  margin: var(--space-3) 0 var(--space-2);
}

.smart-collect-source dl > div {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
  gap: var(--space-3);
}

.smart-collect-source dt {
  color: var(--color-ink-3);
}

.smart-collect-source dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.ai-review-notes {
  display: grid;
  gap: var(--space-4);
  margin-top: var(--space-4);
}

.ai-review-notes ul {
  margin: var(--space-2) 0 0;
  padding-left: var(--space-4);
  color: var(--color-ink-2);
}

.ai-review-notes small {
  display: block;
  color: var(--color-ink-3);
}

.clean-content-dialog {
  min-height: 240px;
}

/* ---- 响应式 ---- */
@media (max-width: 1024px) {
  .edit-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .edit-toolbar {
    flex-wrap: wrap;
    padding-top: var(--space-2);
  }

  .edit-toolbar__actions {
    width: 100%;
  }

  .edit-toolbar__actions :deep(.el-button) {
    flex: 1;
    justify-content: center;
  }

  .edit-card {
    padding: var(--space-4);
  }

  .edit-card__head {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-2);
  }

  .editor-tools {
    width: 100%;
    justify-content: space-between;
  }

  .content-editor :deep(.w-e-text-container),
  .content-preview {
    min-height: 300px;
  }
}
</style>
