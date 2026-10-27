<template>
  <div class="category-admin">
    <div class="admin-head">
      <span class="admin-head__icon" aria-hidden="true">
        <el-icon><FolderOpened /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">栏目管理</h1>
        <p class="admin-head__sub">维护门户内容分类，管理栏目显示状态与排序</p>
      </div>
      <div class="admin-head__actions">
        <el-button type="primary" @click="openForm()">
          <el-icon><Plus /></el-icon>
          新增栏目
        </el-button>
        <el-button type="danger" plain :disabled="!selectedRows.length" @click="batchRemove">
          <el-icon><Delete /></el-icon>
          批量删除{{ selectedRows.length ? `（${selectedRows.length}）` : '' }}
        </el-button>
      </div>
    </div>

    <div class="admin-card">
      <el-table :data="categories" v-loading="loading" style="width: 100%" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="48" />
        <el-table-column label="栏目" min-width="220">
          <template #default="{ row }">
            <div class="cell-media">
              <span class="cell-avatar" :style="{ background: avatarColor(row.id) }" aria-hidden="true">
                {{ row.name.slice(0, 1) }}
              </span>
              <div class="cell-title">
                <span class="cell-title__main">{{ row.name }}</span>
                <span class="cell-title__sub">slug: {{ row.slug }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="简介" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="cell-desc">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column prop="article_count" label="文稿数" width="90">
          <template #default="{ row }">
            <span class="stat-line__item">{{ row.article_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="status-badge" :class="row.status === 'active' ? 'status-badge--green' : 'status-badge--gray'">
              {{ row.status === 'active' ? '启用' : '隐藏' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openForm(row)">
                <el-icon><EditPen /></el-icon>
                编辑
              </el-button>
              <el-button link type="danger" @click="remove(row)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 <strong>{{ categories.length }}</strong> 个栏目</span>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑栏目' : '新增栏目'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="栏目名称" prop="name">
          <el-input v-model="form.name" maxlength="50" />
        </el-form-item>
        <el-form-item label="栏目标识（英文/数字/下划线，用于网址）" prop="slug">
          <el-input v-model="form.slug" maxlength="50" :disabled="Boolean(editing)" />
        </el-form-item>
        <el-form-item label="栏目简介" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="排序（越小越靠前）">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="active">启用</el-radio>
            <el-radio value="hidden">隐藏</el-radio>
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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, EditPen, FolderOpened, Plus } from '@element-plus/icons-vue'
import { categoryApi } from '../../api'

const categories = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref(null)
const saving = ref(false)
const formRef = ref()
const form = reactive({ name: '', slug: '', description: '', sort_order: 0, status: 'active' })
const selectedRows = ref([])

// 栏目头像色：按 id 取一组柔和色中的固定色，保证同一栏目颜色稳定
const AVATAR_COLORS = ['#2563eb', '#7c3aed', '#0891b2', '#c2410c', '#16a34a', '#db2777', '#4f46e5', '#0d9488']

function avatarColor(id) {
  return AVATAR_COLORS[Number(id) % AVATAR_COLORS.length]
}
const rules = {
  name: [{ required: true, message: '请输入栏目名称', trigger: 'blur' }],
  slug: [
    { required: true, message: '请输入栏目标识', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅支持英文、数字、下划线、短横线', trigger: 'blur' },
  ],
}

async function load() {
  loading.value = true
  try {
    const res = await categoryApi.manage()
    categories.value = res.items
  } catch (e) {
    ElMessage.error(String(e))
  } finally {
    loading.value = false
  }
}

function openForm(row) {
  editing.value = row || null
  Object.assign(form, row ? {
    name: row.name,
    slug: row.slug,
    description: row.description || '',
    sort_order: row.sort_order,
    status: row.status,
  } : { name: '', slug: '', description: '', sort_order: 0, status: 'active' })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      await categoryApi.update(editing.value.id, form)
      ElMessage.success('保存成功')
    } else {
      await categoryApi.create(form)
      ElMessage.success('创建成功')
    }
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
    await ElMessageBox.confirm(`确定删除栏目「${row.name}」？该栏目下的文稿关联将被解除。`, '删除确认', { type: 'warning' })
    await categoryApi.remove(row.id)
    ElMessage.success('已删除')
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
      `确定删除选中的 ${selectedRows.value.length} 个栏目？该栏目下的文稿关联将被解除。`,
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
      await categoryApi.remove(row.id)
      ok++
    } catch {
      fail++
    }
  }
  selectedRows.value = []
  if (fail) {
    ElMessage.warning(`已删除 ${ok} 个，失败 ${fail} 个`)
  } else {
    ElMessage.success(`已删除 ${ok} 个栏目`)
  }
  load()
}

onMounted(load)
</script>

<style scoped>
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
  color: #fff;
  font-size: 16px;
  font-weight: 700;
}
</style>

