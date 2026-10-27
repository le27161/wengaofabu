<template>
  <div class="user-admin">
    <div class="admin-head">
      <span class="admin-head__icon">
        <el-icon><User /></el-icon>
      </span>
      <div class="admin-head__text">
        <h1 class="admin-head__title">用户管理</h1>
        <p class="admin-head__sub">账号、角色与状态管理，可创建管理员 / 编辑 / 普通用户</p>
      </div>
      <div class="admin-head__actions">
        <el-button type="danger" plain :disabled="!selectedRows.length" @click="batchRemove">
          <el-icon><Delete /></el-icon>
          批量删除{{ selectedRows.length ? `（${selectedRows.length}）` : '' }}
        </el-button>
        <el-button type="primary" @click="openForm()">创建账号</el-button>
      </div>
    </div>

    <div class="admin-card">
      <div class="table-toolbar">
        <el-input v-model="filters.keyword" placeholder="账号 / 昵称" clearable style="width: 200px" @keyup.enter="reload" @clear="reload" />
        <el-select v-model="filters.role" placeholder="全部角色" clearable style="width: 130px" @change="reload">
          <el-option label="普通用户" value="user" />
          <el-option label="编辑" value="editor" />
          <el-option label="管理员" value="moderator" />
          <el-option label="系统管理员" value="admin" />
        </el-select>
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 130px" @change="reload">
          <el-option label="正常" value="active" />
          <el-option label="冻结" value="frozen" />
        </el-select>
        <el-button type="primary" @click="reload">查询</el-button>
      </div>

      <el-table :data="users" v-loading="loading" @selection-change="handleSelectionChange">
        <!-- 多选列：批量删除用；当前登录账号不可选（后端禁止删除自己） -->
        <el-table-column type="selection" width="48" :selectable="isSelectable" />
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column label="用户" min-width="180">
          <template #default="{ row }">
            <div class="cell-media">
              <el-avatar :size="34" :src="row.avatar || undefined">{{ (row.nickname || row.username).slice(0, 1) }}</el-avatar>
              <div class="cell-title">
                <span class="cell-title__main">{{ row.nickname || row.username }}</span>
                <span class="cell-title__sub">@{{ row.username }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" width="180" show-overflow-tooltip />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <span class="status-badge" :class="roleBadge[row.role]">{{ roleLabel[row.role] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-badge" :class="row.status === 'active' ? 'status-badge--green' : 'status-badge--red'">
              {{ row.status === 'active' ? '正常' : '冻结' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openForm(row)">编辑</el-button>
              <el-button link :type="row.status === 'active' ? 'warning' : 'success'" @click="toggleFreeze(row)">
                {{ row.status === 'active' ? '冻结' : '解冻' }}
              </el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-pager">
        <span class="admin-pager__info">共 {{ total }} 个账号</span>
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="changePage"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑用户' : '创建账号'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" :disabled="Boolean(editing)" />
        </el-form-item>
        <el-form-item v-if="!editing" label="初始密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="编辑" value="editor" />
            <el-option label="管理员" value="moderator" />
            <el-option label="系统管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editing" label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="active">正常</el-radio>
            <el-radio value="frozen">冻结</el-radio>
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
import { Delete, User } from '@element-plus/icons-vue'
import { userApi } from '../../api'
import { useAuthStore } from '../../stores/auth'

const roleLabel = { user: '普通用户', editor: '编辑', moderator: '管理员', admin: '系统管理员' }
const roleBadge = { user: 'status-badge--gray', editor: 'status-badge--orange', moderator: 'status-badge--blue', admin: 'status-badge--red' }
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const filters = reactive({ keyword: '', role: '', status: '' })
// 批量删除：当前勾选的用户；auth 用于禁选当前登录账号
const selectedRows = ref([])
const auth = useAuthStore()
const dialogVisible = ref(false)
const editing = ref(null)
const saving = ref(false)
const formRef = ref()
const form = reactive({ username: '', password: '', nickname: '', email: '', role: 'user', status: 'active' })
const rules = {
  username: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 3, max: 50, message: '账号长度 3-50 位', trigger: 'blur' },
  ],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    const res = await userApi.list({ page: page.value, page_size: pageSize, ...filters })
    users.value = res.items
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

function changePage(p) {
  page.value = p
  load()
}

function openForm(row) {
  editing.value = row || null
  Object.assign(form, row ? {
    username: row.username,
    password: '',
    nickname: row.nickname || '',
    email: row.email || '',
    role: row.role,
    status: row.status,
  } : { username: '', password: '', nickname: '', email: '', role: 'user', status: 'active' })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editing.value) {
      await userApi.update(editing.value.id, {
        nickname: form.nickname,
        email: form.email,
        role: form.role,
        status: form.status,
      })
      ElMessage.success('保存成功')
    } else {
      await userApi.create({
        username: form.username,
        password: form.password,
        nickname: form.nickname,
        email: form.email,
        role: form.role,
      })
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

async function toggleFreeze(row) {
  try {
    const next = row.status === 'active' ? 'frozen' : 'active'
    await userApi.update(row.id, { status: next })
    ElMessage.success(next === 'frozen' ? '账号已冻结' : '账号已解冻')
    load()
  } catch (e) {
    ElMessage.error(String(e))
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username}」？其创建的文稿将一并删除，上传的资源会转移给系统管理员，此操作不可恢复。`,
      '删除确认',
      { type: 'warning' },
    )
    await userApi.remove(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(String(e))
  }
}

// 当前登录账号不允许勾选删除（后端会拒绝，直接禁选更直观）
function isSelectable(row) {
  return row.id !== auth.user?.id
}

function handleSelectionChange(rows) {
  selectedRows.value = rows
}

// 批量删除：一次确认后复用单条删除接口逐个删除，汇总成功/失败数量
async function batchRemove() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedRows.value.length} 个用户？其创建的文稿将一并删除，上传的资源会转移给系统管理员，此操作不可恢复。`,
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
      await userApi.remove(row.id)
      ok++
    } catch {
      fail++
    }
  }
  selectedRows.value = []
  if (fail) {
    ElMessage.warning(`已删除 ${ok} 个，失败 ${fail} 个`)
  } else {
    ElMessage.success(`已删除 ${ok} 个用户`)
  }
  load()
}

onMounted(load)
</script>

<style scoped>
</style>

