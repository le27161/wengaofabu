<template>
  <div class="settings-page">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><Setting /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">系统设置</h1>
        <p class="admin-head__sub">按业务域分组管理全局配置，保存后立即生效</p>
      </div>
    </div>

    <el-skeleton v-if="loading" :rows="4" animated class="settings-skeleton" />

    <template v-else>
      <!-- 内容与发布 -->
      <section class="admin-card settings-card">
        <header class="settings-card__head">
          <span class="settings-card__icon" aria-hidden="true">
            <el-icon><Document /></el-icon>
          </span>
          <div class="settings-card__head-text">
            <h2 class="settings-card__title">内容与发布</h2>
            <p class="settings-card__sub">文稿审核流程与 AI 辅助能力</p>
          </div>
        </header>
        <div class="settings-card__body">
          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">提交自动审核</div>
              <p class="settings-row__desc">开启后文稿提交审核即自动通过两级审核并发布，无需人工审核</p>
            </div>
            <div class="settings-row__control">
              <el-switch
                v-model="autoReview"
                active-text="开启"
                inactive-text="关闭"
                @change="saveBool('auto_review', autoReview)"
              />
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">AI 知识库</div>
              <p class="settings-row__desc">关键词 → 分类强兜底，AI 分类前优先命中；当前共 {{ kbCount }} 条关键词</p>
            </div>
            <div class="settings-row__control">
              <span class="status-badge" :class="kbCount ? 'status-badge--blue' : 'status-badge--gray'">
                {{ kbCount ? `${kbCount} 条规则` : '未配置' }}
              </span>
              <el-button type="primary" plain size="small" @click="openKbDialog">编辑</el-button>
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">文稿向量化</div>
              <p class="settings-row__desc">将全部文稿的"分类：标题"向量化存入 article_embeddings，供个性化推荐召回；重复执行覆盖旧向量</p>
            </div>
            <div class="settings-row__control">
              <el-button type="primary" plain size="small" :loading="vectorizing" @click="vectorizeArticles">执行向量化</el-button>
            </div>
          </div>
        </div>
      </section>

      <!-- 门户与外观 -->
      <section class="admin-card settings-card">
        <header class="settings-card__head">
          <span class="settings-card__icon settings-card__icon--violet" aria-hidden="true">
            <el-icon><Monitor /></el-icon>
          </span>
          <div class="settings-card__head-text">
            <h2 class="settings-card__title">门户与外观</h2>
            <p class="settings-card__sub">前台门户的主题与全局展示效果</p>
          </div>
        </header>
        <div class="settings-card__body">
          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">门户主题</div>
              <p class="settings-row__desc">经典编辑、赛博霓虹、漫画波普三套前台风格</p>
            </div>
            <div class="settings-row__control">
              <el-select v-model="portalTheme" class="settings-select" @change="savePortalTheme">
                <el-option label="经典编辑" value="editorial" />
                <el-option label="赛博霓虹" value="cyber" />
                <el-option label="漫画波普" value="comic" />
                <el-option label="山水墨韵" value="shan-shui" />
              </el-select>
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">哀悼灰度模式</div>
              <p class="settings-row__desc">开启后前台门户全站显示为黑白（用于名人逝世等场景）</p>
            </div>
            <div class="settings-row__control">
              <el-switch
                v-model="siteGrayscale"
                active-text="开启"
                inactive-text="关闭"
                @change="saveBool('site_grayscale', siteGrayscale)"
              />
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">开屏动画</div>
              <p class="settings-row__desc">登录后是否播放 3D 地球开屏动画；关闭后直接进入门户首页</p>
            </div>
            <div class="settings-row__control">
              <el-switch
                v-model="splashEnabled"
                active-text="开启"
                inactive-text="关闭"
                @change="saveBool('splash_enabled', splashEnabled)"
              />
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">门户 AI 阅读功能</div>
              <p class="settings-row__desc">控制门户文稿详情页的 AI 全文总结、划词分析、核心术语知识链是否展示</p>
            </div>
            <div class="settings-row__control">
              <el-switch
                v-model="aiReadingEnabled"
                active-text="开启"
                inactive-text="关闭"
                @change="saveBool('portal_ai_reading_enabled', aiReadingEnabled)"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- 账号与积分 -->
      <section class="admin-card settings-card">
        <header class="settings-card__head">
          <span class="settings-card__icon settings-card__icon--amber" aria-hidden="true">
            <el-icon><Wallet /></el-icon>
          </span>
          <div class="settings-card__head-text">
            <h2 class="settings-card__title">账号与积分</h2>
            <p class="settings-card__sub">注册策略与用户积分体系</p>
          </div>
        </header>
        <div class="settings-card__body">
          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">注册成为编辑</div>
              <p class="settings-row__desc">开启后用户可直接注册为编辑写手；关闭后编辑账号仅可在后台创建</p>
            </div>
            <div class="settings-row__control">
              <el-switch
                v-model="registerEditorEnabled"
                active-text="开启"
                inactive-text="关闭"
                @change="saveRegisterEditor"
              />
            </div>
          </div>

          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">每日签到积分范围</div>
              <p class="settings-row__desc">用户每日签到随机获得的积分区间，自动校验最小 ≤ 最大</p>
            </div>
            <div class="settings-row__control settings-row__control--range">
              <el-input-number v-model="signinMin" :min="0" :max="signinMax" controls-position="right" />
              <span class="settings-range-sep">至</span>
              <el-input-number v-model="signinMax" :min="signinMin" :max="99999" controls-position="right" />
              <el-button type="primary" size="small" :loading="savingPoints" @click="savePointsRange">保存</el-button>
            </div>
          </div>
        </div>
      </section>

      <!-- 存储与资源 -->
      <section class="admin-card settings-card">
        <header class="settings-card__head">
          <span class="settings-card__icon settings-card__icon--green" aria-hidden="true">
            <el-icon><Coin /></el-icon>
          </span>
          <div class="settings-card__head-text">
            <h2 class="settings-card__title">存储与资源</h2>
            <p class="settings-card__sub">资源上传的目标存储位置</p>
          </div>
        </header>
        <div class="settings-card__body">
          <div class="settings-row">
            <div class="settings-row__info">
              <div class="settings-row__title">对象存储（OSS）</div>
              <p class="settings-row__desc">
                endpoint 留空时上传到本地服务器；配置后新上传文件写入 S3 兼容对象存储（bucket 需公开读）
              </p>
            </div>
            <div class="settings-row__control">
              <span class="status-badge" :class="ossConfigured ? 'status-badge--blue' : 'status-badge--gray'">
                {{ ossConfigured ? '已启用' : '本地存储' }}
              </span>
              <el-button type="primary" plain size="small" @click="openOssDialog">配置</el-button>
            </div>
          </div>
        </div>
      </section>
    </template>

    <!-- AI 知识库配置弹窗 -->
    <el-dialog v-model="kbDialogVisible" title="AI 知识库配置" width="640px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="JSON 对象：键为关键词，值为 { title, category } 结构，保存前自动校验格式"
        class="kb-dialog__tip"
      />
      <el-input
        v-model="kbText"
        type="textarea"
        :rows="12"
        spellcheck="false"
        class="kb-dialog__textarea"
        placeholder='{ "关键词": { "title": "描述", "category": "分类名" } }'
      />
      <template #footer>
        <el-button @click="kbDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingKb" @click="saveKnowledgeBase">保存</el-button>
      </template>
    </el-dialog>

    <!-- 对象存储配置弹窗 -->
    <el-dialog v-model="ossDialogVisible" title="对象存储（OSS）配置" width="560px" destroy-on-close>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="支持阿里云 OSS、腾讯云 COS、MinIO、AWS S3 等；bucket 需设置为公开读"
        class="oss-dialog__tip"
      />
      <el-form label-position="top">
        <div class="oss-form__grid">
          <el-form-item label="Endpoint（服务地址）">
            <el-input v-model="ossForm.endpoint" placeholder="如 https://oss-cn-hangzhou.aliyuncs.com 或 http://127.0.0.1:9000" />
          </el-form-item>
          <el-form-item label="Bucket（存储桶）">
            <el-input v-model="ossForm.bucket" placeholder="需允许公开读" />
          </el-form-item>
          <el-form-item label="Region">
            <el-input v-model="ossForm.region" placeholder="默认 us-east-1（MinIO 可随意）" />
          </el-form-item>
          <el-form-item label="Access Key">
            <el-input v-model="ossForm.access_key" placeholder="Access Key" />
          </el-form-item>
          <el-form-item label="Secret Key">
            <el-input v-model="ossForm.secret_key" type="password" show-password placeholder="已设置显示 ****，留空保留原值" autocomplete="new-password" />
          </el-form-item>
          <el-form-item label="Path Prefix（可选）">
            <el-input v-model="ossForm.path_prefix" placeholder="如 articles/" />
          </el-form-item>
          <el-form-item label="公开访问前缀（可选）" class="oss-form__wide">
            <el-input
              v-model="ossForm.public_base_url"
              placeholder="留空按 endpoint/bucket/key 拼接；虚拟主机风格或 CDN 时填写完整前缀"
            />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button v-if="ossConfigured" @click="clearOssConfig">清空（切回本地）</el-button>
        <el-button @click="ossDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingOss" @click="saveOssConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Coin, Document, Monitor, Setting, Wallet } from '@element-plus/icons-vue'
import { embeddingApi, portalApi, settingsApi } from '../../api'

const loading = ref(true)

// 内容与发布
const autoReview = ref(false)
const knowledgeBase = ref({})
const kbCount = computed(() => Object.keys(knowledgeBase.value || {}).length)

// 门户与外观
const portalTheme = ref('editorial')
const siteGrayscale = ref(false)
const splashEnabled = ref(true)
const aiReadingEnabled = ref(true)

// 账号与积分
const registerEditorEnabled = ref(true)
const signinMin = ref(1)
const signinMax = ref(5)
const savingPoints = ref(false)

// 存储与资源
const ossConfigured = ref(false)
const ossDialogVisible = ref(false)
const savingOss = ref(false)
const ossForm = ref({
  endpoint: '', bucket: '', region: '', access_key: '', secret_key: '', path_prefix: '', public_base_url: '',
})

// AI 知识库弹窗
const kbDialogVisible = ref(false)
const kbText = ref('')
const savingKb = ref(false)
// 文稿向量化执行状态
const vectorizing = ref(false)

onMounted(async () => {
  try {
    const res = await settingsApi.list()
    const find = (key) => res.items.find((s) => s.config_key === key)
    autoReview.value = find('auto_review')?.value ?? false
    portalTheme.value = find('portal_theme')?.value || 'editorial'
    siteGrayscale.value = find('site_grayscale')?.value ?? false
    splashEnabled.value = find('splash_enabled')?.value ?? true
    aiReadingEnabled.value = find('portal_ai_reading_enabled')?.value ?? true
    signinMin.value = find('signin_min_points')?.value ?? 1
    signinMax.value = find('signin_max_points')?.value ?? 5
    knowledgeBase.value = find('ai_knowledge_base')?.value ?? {}
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
  try {
    const res = await portalApi.registerEditor()
    registerEditorEnabled.value = res.enabled
  } catch {
    // 拉取失败按开启处理
  }
  try {
    const res = await portalApi.ossConfig()
    ossConfigured.value = res.configured
    ossForm.value = { ...res.config }
  } catch {
    // 拉取失败按本地模式处理
  }
})

// 通用 bool 配置保存（失败回滚开关）
async function saveBool(key, val) {
  try {
    await settingsApi.update(key, { value: val, value_type: 'bool' })
    ElMessage.success('已保存')
  } catch (e) {
    if (key === 'auto_review') autoReview.value = !val
    if (key === 'site_grayscale') siteGrayscale.value = !val
    if (key === 'splash_enabled') splashEnabled.value = !val
    if (key === 'portal_ai_reading_enabled') aiReadingEnabled.value = !val
    ElMessage.error(String(e))
  }
}

async function savePortalTheme() {
  try {
    await settingsApi.update('portal_theme', { value: portalTheme.value, value_type: 'string' })
    ElMessage.success('门户主题已更新')
  } catch (e) {
    ElMessage.error(String(e))
  }
}

// 签到积分范围：保存前校验 最小 ≤ 最大
async function savePointsRange() {
  if (signinMin.value > signinMax.value) {
    ElMessage.error('最小积分不能大于最大积分')
    return
  }
  savingPoints.value = true
  try {
    await settingsApi.update('signin_min_points', { value: signinMin.value, value_type: 'int' })
    await settingsApi.update('signin_max_points', { value: signinMax.value, value_type: 'int' })
    ElMessage.success('签到积分范围已保存')
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    savingPoints.value = false
  }
}

// 全量文稿向量化：耗时较长（首次调用含模型加载），确认后执行
async function vectorizeArticles() {
  try {
    await ElMessageBox.confirm(
      '将全部文稿向量化并写入向量库？首次执行包含模型加载，可能需要数十秒。',
      '文稿向量化',
      { type: 'warning', confirmButtonText: '开始执行', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  vectorizing.value = true
  try {
    const res = await embeddingApi.vectorize()
    ElMessage.success(`${res.message}，当前库内向量 ${res.stats?.total ?? res.total} 条`)
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    vectorizing.value = false
  }
}

function openKbDialog() {
  kbText.value = JSON.stringify(knowledgeBase.value || {}, null, 2)
  kbDialogVisible.value = true
}

async function saveKnowledgeBase() {
  let parsed
  try {
    parsed = JSON.parse(kbText.value || '{}')
  } catch {
    ElMessage.error('JSON 格式不正确，请检查后重试')
    return
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    ElMessage.error('知识库需为 JSON 对象：{ "关键词": { "title": "...", "category": "..." } }')
    return
  }
  savingKb.value = true
  try {
    await settingsApi.update('ai_knowledge_base', { value: parsed, value_type: 'json' })
    knowledgeBase.value = parsed
    kbDialogVisible.value = false
    ElMessage.success(`AI 知识库已保存（${Object.keys(parsed).length} 条关键词）`)
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    savingKb.value = false
  }
}

// 注册成为编辑
async function saveRegisterEditor() {
  try {
    await portalApi.setRegisterEditor(registerEditorEnabled.value)
    ElMessage.success(registerEditorEnabled.value ? '已开放编辑注册' : '已关闭编辑注册')
  } catch (e) {
    registerEditorEnabled.value = !registerEditorEnabled.value
    ElMessage.error(String(e))
  }
}

function openOssDialog() {
  ossDialogVisible.value = true
}

// 保存 OSS 配置（secret_key 传 **** 保留原值，传空清空）
async function saveOssConfig() {
  savingOss.value = true
  try {
    const res = await portalApi.setOssConfig(ossForm.value)
    ossConfigured.value = res.configured
    ossForm.value = { ...res.config }
    ossDialogVisible.value = false
    ElMessage.success(res.configured ? 'OSS 配置已保存，新上传文件将写入对象存储' : '已切换为本地存储')
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    savingOss.value = false
  }
}

// 清空 OSS 配置，切回本地存储
async function clearOssConfig() {
  try {
    await ElMessageBox.confirm('清空后将恢复为本地存储，已上传到 OSS 的文件不会自动迁移。确定清空吗？', '提示', {
      type: 'warning',
    })
  } catch {
    return
  }
  ossForm.value = {
    endpoint: '', bucket: '', region: '', access_key: '', secret_key: '', path_prefix: '', public_base_url: '',
  }
  await saveOssConfig()
}
</script>

<style scoped>
/* 系统设置页：按业务域分组的卡片布局，遵循项目设计令牌 */
.settings-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5, 24px);
}

.settings-skeleton {
  padding: var(--space-5, 24px);
}

.settings-card {
  border-radius: var(--radius-lg, 16px);
}

.settings-card__head {
  display: flex;
  align-items: center;
  gap: var(--space-3, 12px);
  padding: var(--space-4, 16px) var(--space-5, 24px);
  border-bottom: 1px solid var(--color-rule, #e2e8f0);
  background: var(--color-paper-2, #f8fafc);
}

.settings-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 10px;
  font-size: 19px;
  color: var(--color-primary, #2563eb);
  background: var(--color-primary-soft, #dbeafe);
}

.settings-card__icon--violet {
  color: #7c3aed;
  background: #ede9fe;
}

.settings-card__icon--amber {
  color: #d97706;
  background: #fef3c7;
}

.settings-card__icon--green {
  color: #16a34a;
  background: #dcfce7;
}

.settings-card__head-text {
  min-width: 0;
}

.settings-card__title {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-ink, #1e293b);
  line-height: 1.3;
}

.settings-card__sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
}

.settings-card__body {
  padding: 0 var(--space-5, 24px);
}

.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4, 16px);
  padding: var(--space-4, 16px) 0;
  border-bottom: 1px solid var(--color-rule, #e2e8f0);
}

.settings-row:last-child {
  border-bottom: none;
}

.settings-row__info {
  min-width: 0;
}

.settings-row__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink, #1e293b);
  margin-bottom: 4px;
}

.settings-row__desc {
  margin: 0;
  font-size: 12px;
  color: var(--color-ink-3, #94a3b8);
  line-height: 1.6;
  max-width: 560px;
}

.settings-row__control {
  display: flex;
  align-items: center;
  gap: var(--space-3, 12px);
  flex-shrink: 0;
}

.settings-select {
  width: 200px;
}

.settings-range-sep {
  font-size: 13px;
  color: var(--color-ink-3, #94a3b8);
}

/* AI 知识库弹窗 */
.kb-dialog__tip {
  margin-bottom: var(--space-4, 16px);
}

.kb-dialog__textarea :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

/* OSS 弹窗 */
.oss-dialog__tip {
  margin-bottom: var(--space-4, 16px);
}

.oss-form__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--space-4, 16px);
}

.oss-form__wide {
  grid-column: 1 / -1;
}

@media (max-width: 900px) {
  .settings-row {
    flex-direction: column;
    align-items: stretch;
  }

  .settings-row__control {
    justify-content: flex-end;
  }

  .settings-select {
    width: 100%;
  }

  .settings-row__control--range {
    flex-wrap: wrap;
  }

  .oss-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
