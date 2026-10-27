<template>
  <div class="article-admin">
    <div class="admin-head">
      <span class="admin-head__icon" aria-hidden="true">
        <el-icon><Document /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">文稿管理</h1>
        <p class="admin-head__sub">管理全站文稿的编写、审核与发布状态</p>
      </div>
      <div class="admin-head__actions">
        <el-button @click="importDialogVisible = true">
          <el-icon><Upload /></el-icon>
          批量导入
        </el-button>
        <el-button type="primary" @click="router.push('/admin/articles/new')">
          <el-icon><EditPen /></el-icon>
          写新文稿
        </el-button>
        <el-button type="success" plain :disabled="!selectedRows.length" @click="batchSubmit">
          <el-icon><Promotion /></el-icon>
          批量提交审核{{ selectedRows.length ? `（${selectedRows.length}）` : '' }}
        </el-button>
        <el-button type="danger" plain :disabled="!selectedRows.length" @click="batchRemove">
          <el-icon><Delete /></el-icon>
          批量删除{{ selectedRows.length ? `（${selectedRows.length}）` : '' }}
        </el-button>
      </div>
    </div>

    <!-- 批量导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="批量导入文稿" width="640px" top="8vh">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="支持 .xlsx 格式，四列：封面 / 标题 / 分类 / 正文；最多 500 行；导入后为草稿"
        class="import-tip"
      />
      <el-upload
        drag
        accept=".xlsx"
        :auto-upload="false"
        :limit="1"
        :file-list="importFileList"
        :on-change="onImportFileChange"
        :on-remove="onImportFileRemove"
        :on-exceed="onImportFileExceed"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 Excel 拖到此处，或 <em>点击选择文件</em></div>
        <template #tip>
          <div class="el-upload__tip">
            封面列为图片链接；为空或无法下载时封面留空，文稿仍会导入
          </div>
        </template>
      </el-upload>
      <div class="import-actions">
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="doImport">
          开始导入
        </el-button>
      </div>

      <div v-if="importResult" class="import-result">
        <el-result icon="success" :title="importResult.message" />
        <div
          v-if="importResult.skipped?.length || importResult.failed?.length || importResult.warnings?.length"
          class="import-detail"
        >
          <h4 class="import-detail__title">导入明细</h4>
          <div class="import-detail__item" v-for="(w, i) in importResult.warnings" :key="'w' + i">
            <span class="import-detail__row">第 {{ w.row }} 行</span>
            <span class="import-detail__reason import-detail__reason--warn">{{ w.reason }}</span>
          </div>
          <div class="import-detail__item" v-for="(s, i) in importResult.skipped" :key="'s' + i">
            <span class="import-detail__row">第 {{ s.row }} 行</span>
            <span class="import-detail__reason import-detail__reason--skip">{{ s.reason }}</span>
          </div>
          <div class="import-detail__item" v-for="(f, i) in importResult.failed" :key="'f' + i">
            <span class="import-detail__row">第 {{ f.row }} 行</span>
            <span class="import-detail__reason import-detail__reason--fail">{{ f.reason }}</span>
          </div>
        </div>
      </div>
    </el-dialog>

    <div class="admin-card">
      <!-- 筛选栏 -->
      <div class="admin-card__toolbar">
        <el-input
          v-model="filters.keyword"
          placeholder="标题关键词"
          clearable
          style="width: 240px"
          @keyup.enter="reload"
        />
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px" @change="reload">
          <el-option v-for="(label, value) in statusMap" :key="value" :label="label" :value="value" />
        </el-select>
        <el-select v-model="filters.category_id" placeholder="全部栏目" clearable style="width: 150px" @change="reload">
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-button @click="reload">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
      </div>

      <el-table
        :data="articles"
        v-loading="loading"
        style="width: 100%"
        :default-sort="{ prop: 'created_at', order: 'descending' }"
        @selection-change="handleSelectionChange"
        @sort-change="handleSortChange"
      >
        <el-table-column type="selection" width="48" :selectable="isSelectable" />
        <el-table-column label="文稿" min-width="280">
          <template #default="{ row }">
            <div
              class="cell-media cell-media--clickable"
              tabindex="0"
              role="button"
              :aria-label="`预览《${row.title}》`"
              @click="openPreview(row)"
              @keyup.enter="openPreview(row)"
            >
              <img v-if="row.cover_url" :src="row.cover_url" :alt="row.title" class="cell-thumb" loading="lazy" />
              <span v-else class="cell-thumb cell-thumb--empty">
                {{ (row.categories[0]?.name || '文').slice(0, 1) }}
              </span>
              <div class="cell-title">
                <span class="cell-title__main" :title="row.title">{{ row.title }}</span>
                <span class="cell-title__sub">#{{ row.id }} · {{ row.author_name }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="栏目" width="170">
          <template #default="{ row }">
            <div class="tag-list">
              <span v-for="c in row.categories" :key="c.id" class="mini-tag">{{ c.name }}</span>
              <span v-if="!row.categories.length" class="mini-tag mini-tag--empty">未分类</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <span class="status-badge" :class="statusBadgeClass(row.status)">
              {{ statusMap[row.status] || row.status }}
            </span>
          </template>
        </el-table-column>
        <!-- 数值/时间列支持列头点击排序（服务端排序，见 handleSortChange） -->
        <el-table-column label="浏览" prop="view_count" width="100" sortable="custom" />
        <el-table-column label="点赞" prop="like_count" width="90" sortable="custom" />
        <el-table-column label="收藏" prop="favorite_count" width="90" sortable="custom" />
        <el-table-column label="转发" prop="share_count" width="90" sortable="custom" />
        <el-table-column label="创建时间" prop="created_at" width="165" sortable="custom" />
        <el-table-column label="更新时间" prop="updated_at" width="165" sortable="custom" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button v-if="isEditable(row)" link type="primary" @click="router.push(`/admin/articles/${row.id}/edit`)">
                <el-icon><EditPen /></el-icon>
                编辑
              </el-button>
              <el-button v-if="canSubmit(row)" link type="warning" @click="submit(row)">
                <el-icon><Promotion /></el-icon>
                提交审核
              </el-button>
              <el-button v-if="isAdmin && row.status === 'published'" link type="info" @click="offline(row)">
                <el-icon><SwitchButton /></el-icon>
                下线
              </el-button>
              <el-button v-if="canDelete(row)" link type="danger" @click="remove(row)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 <strong>{{ total }}</strong> 篇文稿</span>
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="changePage"
        />
      </div>
    </div>

    <!-- 文稿预览抽屉 -->
    <ArticlePreviewDrawer v-model:visible="previewVisible" :article-id="previewId" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete, Document, EditPen, Promotion, Search, SwitchButton, Upload, UploadFilled,
} from '@element-plus/icons-vue'
import { articleApi, categoryApi } from '../../api'
import { useAuthStore } from '../../stores/auth'
import ArticlePreviewDrawer from '../../components/ArticlePreviewDrawer.vue'

const router = useRouter()
const auth = useAuthStore()
const isAdmin = auth.isAdmin

const statusMap = {
  draft: '草稿',
  pending_first: '待一审',
  pending_second: '待二审',
  published: '已发布',
  rejected: '已驳回',
  offline: '已下线',
}

const articles = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const filters = reactive({ keyword: '', status: '', category_id: '' })
// 栏目下拉数据（进入页面时加载）
const categories = ref([])
// 服务端排序：与后端 sort_by/sort_order 对应，默认创建时间降序
const sort = reactive({ by: 'created_at', order: 'desc' })
const selectedRows = ref([])
// 批量导入
const importDialogVisible = ref(false)
const importFileList = ref([])
const importFile = ref(null)
const importing = ref(false)
const importResult = ref(null)
// 文稿预览
const previewVisible = ref(false)
const previewId = ref(null)

function openPreview(row) {
  previewId.value = row.id
  previewVisible.value = true
}

function onImportFileChange(file) {
  importFile.value = file.raw
  importResult.value = null
  importFileList.value = [file]
}

function onImportFileRemove() {
  importFile.value = null
  importResult.value = null
  importFileList.value = []
}

function onImportFileExceed(files) {
  // 只保留最新选择的文件
  const file = files[0]
  importFile.value = file
  importResult.value = null
  importFileList.value = [file]
}

async function doImport() {
  if (!importFile.value) return
  importing.value = true
  const formData = new FormData()
  formData.append('file', importFile.value)
  try {
    const res = await articleApi.importExcel(formData)
    importResult.value = res
    reload()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '导入失败')
  } finally {
    importing.value = false
  }
}

function statusBadgeClass(s) {
  return {
    draft: 'status-badge--gray',
    pending_first: 'status-badge--orange',
    pending_second: 'status-badge--red',
    published: 'status-badge--green',
    rejected: 'status-badge--red',
    offline: 'status-badge--gray',
  }[s] || 'status-badge--gray'
}

function isEditable(row) {
  // 草稿 / 驳回稿 / 已下线稿可编辑（下线稿编辑后重新提审再发布）
  return (row.status === 'draft' || row.status === 'rejected' || row.status === 'offline')
    && (isAdmin || row.author_id === auth.user?.id)
}

function canSubmit(row) {
  return (row.status === 'draft' || row.status === 'rejected' || row.status === 'offline')
    && (isAdmin || row.author_id === auth.user?.id)
}

function canDelete(row) {
  return isAdmin || row.author_id === auth.user?.id
}

// 仅可删除的文稿行允许勾选（管理员或作者本人）
function isSelectable(row) {
  return canDelete(row)
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, ...filters, sort_by: sort.by, sort_order: sort.order }
    if (!params.category_id) delete params.category_id
    const res = isAdmin ? await articleApi.adminList(params) : await articleApi.mine(params)
    articles.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

// 列头点击排序（服务端排序）：升序/降序/清空（第三击恢复默认创建时间降序）
function handleSortChange({ prop, order }) {
  if (!order) {
    sort.by = 'created_at'
    sort.order = 'desc'
  } else {
    sort.by = prop
    sort.order = order === 'ascending' ? 'asc' : 'desc'
  }
  page.value = 1
  load()
}

async function loadCategories() {
  try {
    const res = await categoryApi.list()
    categories.value = res.items
  } catch (e) {
    ElMessage.error(String(e))
  }
}

function changePage(p) {
  page.value = p
  load()
}

async function submit(row) {
  try {
    await articleApi.submit(row.id)
    ElMessage.success('已提交审核（待一审）')
    load()
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function offline(row) {
  try {
    await articleApi.offline(row.id)
    ElMessage.success('文稿已下线')
    load()
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除《${row.title}》？删除后不可恢复。`, '删除确认', { type: 'warning' })
    await articleApi.remove(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(String(e))
  }
}

async function batchRemove() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedRows.value.length} 篇文稿？删除后不可恢复。`,
      '批量删除确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  let ok = 0
  let fail = 0
  for (const row of selectedRows.value) {
    try {
      await articleApi.remove(row.id)
      ok++
    } catch {
      fail++
    }
  }
  selectedRows.value = []
  if (fail) {
    ElMessage.warning(`已删除 ${ok} 篇，失败 ${fail} 篇`)
  } else {
    ElMessage.success(`已删除 ${ok} 篇文稿`)
  }
  load()
}

// 批量提交审核：仅提交可提交状态（草稿/已驳回/已下线）且作者本人或管理员，复用单篇提交接口
async function batchSubmit() {
  if (!selectedRows.value.length) return
  const submittable = selectedRows.value.filter(canSubmit)
  const skipped = selectedRows.value.length - submittable.length
  if (!submittable.length) {
    ElMessage.warning('选中的文稿均不可提交审核（仅草稿 / 已驳回 / 已下线可提交）')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将提交 ${submittable.length} 篇文稿进入一审审核` +
        (skipped ? `，另有 ${skipped} 篇当前不可提交将被跳过` : '') +
        '。确定提交吗？',
      '批量提交审核',
      { type: 'info', confirmButtonText: '提交审核', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  let ok = 0
  const fails = []
  for (const row of submittable) {
    try {
      await articleApi.submit(row.id)
      ok++
    } catch (e) {
      fails.push({ title: row.title, reason: e?.response?.data?.detail || e?.message || '提交失败' })
    }
  }
  selectedRows.value = []
  const skipTip = skipped ? `，跳过 ${skipped} 篇不可提交` : ''
  if (fails.length) {
    ElMessage.warning(`已提交 ${ok} 篇，失败 ${fails.length} 篇${skipTip}（如：${fails[0].reason}）`)
  } else {
    ElMessage.success(`已提交 ${ok} 篇文稿进入审核${skipTip}`)
  }
  load()
}

onMounted(async () => {
  await loadCategories()
  load()
})
</script>

<style scoped>
/* ---- 文稿列可点击预览 ---- */
.cell-media--clickable {
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.15s ease;
}

.cell-media--clickable:hover {
  background: var(--color-primary-soft);
}

.cell-media--clickable:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* ---- 批量导入弹窗 ---- */
.import-tip {
  margin-bottom: 14px;
}

.import-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.import-result {
  margin-top: 8px;
  border-top: 1px solid var(--color-border);
  padding-top: 8px;
}

.import-result :deep(.el-result) {
  padding: 16px 0;
}

.import-detail {
  max-height: 220px;
  overflow-y: auto;
  background: var(--color-paper);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}

.import-detail__title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
}

.import-detail__item {
  display: flex;
  gap: 8px;
  padding: 3px 0;
  font-size: 13px;
}

.import-detail__row {
  flex-shrink: 0;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.import-detail__reason--warn {
  color: #b45309;
}

.import-detail__reason--skip {
  color: #1d4ed8;
}

.import-detail__reason--fail {
  color: #b91c1c;
}

.no-city {
  color: var(--color-text-3, #999);
}
</style>

