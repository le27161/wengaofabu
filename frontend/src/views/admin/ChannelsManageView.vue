<template>
  <div class="channels-admin">
    <div class="admin-head">
      <span class="admin-head__icon" aria-hidden="true">
        <el-icon><Share /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">渠道管理</h1>
        <p class="admin-head__sub">维护文稿分发渠道，第三方平台通过 RSS 订阅获取稿件</p>
      </div>
      <div class="admin-head__actions">
        <el-button type="primary" @click="openForm()">
          <el-icon><Plus /></el-icon>
          新增渠道
        </el-button>
        <el-button type="danger" plain :disabled="!selectedRows.length" @click="batchRemove">
          <el-icon><Delete /></el-icon>
          批量删除{{ selectedRows.length ? `（${selectedRows.length}）` : '' }}
        </el-button>
      </div>
    </div>

    <el-alert
      class="channels-tip"
      type="info"
      :closable="false"
      show-icon
      title="渠道用于文稿分发：第三方平台可通过每个渠道的 RSS 链接订阅最近 7 天勾选该渠道的文稿。基础渠道（门户）所有文稿默认包含且不可删除。"
    />

    <div class="admin-card">
      <el-table :data="channels" v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="48" :selectable="(row) => !row.is_default" />
        <el-table-column label="渠道" min-width="200">
          <template #default="{ row }">
            <div class="cell-media">
              <span class="cell-avatar" :class="row.is_default ? 'cell-avatar--default' : ''" aria-hidden="true">
                <el-icon v-if="row.is_default"><Star /></el-icon>
                <template v-else>{{ row.name.slice(0, 1) }}</template>
              </span>
              <div class="cell-title">
                <span class="cell-title__main">
                  {{ row.name }}
                  <span v-if="row.is_default" class="mini-tag mini-tag--orange">基础渠道</span>
                </span>
                <span class="cell-title__sub">slug: {{ row.slug }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="简介" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="cell-desc">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="article_count" label="文稿数" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="status-badge" :class="row.status === 'active' ? 'status-badge--green' : 'status-badge--gray'">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="RSS 订阅" width="170">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openRss(row)">
                <el-icon><Link /></el-icon>
                打开
              </el-button>
              <el-button link type="success" @click="copyRss(row)">
                <el-icon><CopyDocument /></el-icon>
                复制
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openForm(row)">
                <el-icon><EditPen /></el-icon>
                编辑
              </el-button>
              <el-button v-if="!row.is_default" link type="danger" @click="remove(row)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 <strong>{{ channels.length }}</strong> 个渠道</span>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑渠道' : '新增渠道'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="渠道名称" prop="name">
          <el-input v-model="form.name" maxlength="50" />
        </el-form-item>
        <el-form-item label="渠道标识（英文/数字/下划线，用于 RSS 地址）" prop="slug">
          <el-input v-model="form.slug" maxlength="50" :disabled="isDefaultEditing" />
        </el-form-item>
        <el-form-item label="渠道简介" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="排序（越小越靠前）">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status" :disabled="isDefaultEditing">
            <el-radio value="active">启用</el-radio>
            <el-radio value="disabled">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CopyDocument, Delete, EditPen, Link, Plus, Share, Star } from '@element-plus/icons-vue'
import { channelApi } from '../../api'

const channels = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref(null)
const saving = ref(false)
const formRef = ref()
const form = reactive({ name: '', slug: '', description: '', sort_order: 0, status: 'active' })
const isDefaultEditing = computed(() => Boolean(editing.value?.is_default))
const selectedRows = ref([])
const rules = {
  name: [{ required: true, message: '请输入渠道名称', trigger: 'blur' }],
  slug: [
    { required: true, message: '请输入渠道标识', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅支持英文、数字、下划线、短横线', trigger: 'blur' },
  ],
}

async function load() {
  loading.value = true
  try {
    const res = await channelApi.manage()
    channels.value = res.items
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

function openForm(row) {
  editing.value = row || null
  Object.assign(form, row
    ? {
        name: row.name,
        slug: row.slug,
        description: row.description || '',
        sort_order: row.sort_order,
        status: row.status,
      }
    : { name: '', slug: '', description: '', sort_order: 0, status: 'active' })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = { ...form }
    if (editing.value) {
      await channelApi.update(editing.value.id, payload)
    } else {
      await channelApi.create(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除渠道「${row.name}」吗？删除后将解除与文稿的关联。`, '删除确认', {
      type: 'warning',
    })
    await channelApi.remove(row.id)
    ElMessage.success('删除成功')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(String(e))
  }
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

async function batchRemove() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedRows.value.length} 个渠道？删除后将解除与文稿的关联。`,
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
      await channelApi.remove(row.id)
      ok++
    } catch {
      fail++
    }
  }
  selectedRows.value = []
  if (fail) {
    ElMessage.warning(`已删除 ${ok} 个，失败 ${fail} 个`)
  } else {
    ElMessage.success(`已删除 ${ok} 个渠道`)
  }
  load()
}

function copyRss(row) {
  const url = channelApi.rssUrl(row.id)
  // HTTPS 下优先用 Clipboard API；HTTP 下 Clipboard API 不可用，降级 execCommand 复制
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard
      .writeText(url)
      .then(() => ElMessage.success('RSS 链接已复制'))
      .catch(() => fallbackCopy(url))
  } else {
    fallbackCopy(url)
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.left = '-9999px'
  ta.style.top = '0'
  document.body.appendChild(ta)
  ta.select()
  ta.setSelectionRange(0, text.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(ta)
  if (ok) {
    ElMessage.success('RSS 链接已复制')
  } else {
    ElMessage.error('复制失败，请手动复制')
  }
}

function openRss(row) {
  window.open(channelApi.rssUrl(row.id), '_blank', 'noopener')
}

onMounted(load)
</script>

<style scoped>
.channels-tip {
  margin-bottom: 16px;
}

.cell-desc {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.cell-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 10px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 16px;
  font-weight: 700;
}

.cell-avatar--default {
  background: #ffedd5;
  color: #c2410c;
}
</style>
